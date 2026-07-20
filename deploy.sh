#!/usr/bin/env bash
# deploy.sh — build and deploy the Emerytura dashboard to AWS
#
# Usage:
#   ./deploy.sh           → deploy production (default)
#   ./deploy.sh --env dev → deploy development environment
#
# Requirements: aws cli, sam cli  (brew install awscli aws-sam-cli)

set -euo pipefail

# ── Parse arguments ───────────────────────────────────────────────
ENV="prod"
for arg in "$@"; do
  case "$arg" in
    --env) shift; ENV="${1:-prod}" ;;
    --env=*) ENV="${arg#*=}" ;;
  esac
done

if [[ "$ENV" != "prod" && "$ENV" != "dev" ]]; then
  echo "ERROR: --env must be 'prod' or 'dev'" >&2; exit 1
fi

if [[ "${GITHUB_ACTIONS:-false}" != "true" ]]; then
  export AWS_PROFILE="${AWS_PROFILE:-default}"
fi
REGION="${AWS_DEFAULT_REGION:-us-west-2}"

# ── Environment-specific config ───────────────────────────────────
if [[ "$ENV" == "prod" ]]; then
  STACK_NAME="micbarfund-backend"
  SAM_CONFIG_ENV="default"
  # Prod bucket + CF are managed outside SAM
  BUCKET="micbarfund-website"
  CF_DOMAIN="d750c9gknegtj.cloudfront.net"
else
  STACK_NAME="micbarfund-backend-dev"
  SAM_CONFIG_ENV="dev"
  # Dev bucket + CF domain are fetched from stack outputs after deploy
  BUCKET=""          # filled in after deploy
  CF_DOMAIN=""       # filled in after deploy
fi

CF_URL="https://${CF_DOMAIN}"

echo "=== Building Lambda package (env: $ENV) ==="
rm -rf .aws-sam
sam build \
  --region  "$REGION"

echo ""
echo "=== Deploying stack: $STACK_NAME ==="
sam deploy \
  --config-env    "$SAM_CONFIG_ENV" \
  --stack-name    "$STACK_NAME" \
  --region        "$REGION" \
  --capabilities  CAPABILITY_IAM \
  --s3-bucket     "micbarfund-website" \
  --s3-prefix     "sam-artifacts-${ENV}" \
  --force-upload \
  --no-fail-on-empty-changeset

# ── For dev: read bucket + CF domain from stack outputs ───────────
if [[ "$ENV" == "dev" ]]; then
  echo ""
  echo "=== Fetching dev stack outputs ==="
  BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region     "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='DevStaticBucketName'].OutputValue" \
    --output text)

  CF_DOMAIN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region     "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='DevCloudFrontDomain'].OutputValue" \
    --output text)

  CF_URL="https://${CF_DOMAIN}"
  echo "Dev bucket:     $BUCKET"
  echo "Dev CF domain:  $CF_DOMAIN"
fi

echo ""
echo "=== Fetching API URL ==="
API_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region     "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text)

echo ""
echo "=== Fetching Cognito config ==="
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region     "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" \
  --output text)

COGNITO_CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region     "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" \
  --output text)

echo ""
echo "=== Writing config.js to S3 ==="
cat > /tmp/roastfolio-config.js << EOF
window.__CONFIG__ = {
  apiUrl:             "$API_URL",
  cognitoUserPoolId:  "$USER_POOL_ID",
  cognitoClientId:    "$COGNITO_CLIENT_ID",
  cognitoRegion:      "$REGION"
};
EOF

aws s3 cp /tmp/roastfolio-config.js "s3://$BUCKET/scripts/config.js" \
    --content-type "application/javascript" \
    --region  "$REGION"
echo "config.js uploaded (API + Cognito)"
rm -f /tmp/roastfolio-config.js

echo ""
echo "=== Syncing static files to S3 ==="
aws s3 sync src/ "s3://$BUCKET/" \
  --region  "$REGION" \
  --delete \
  --exclude "*.DS_Store" \
  --exclude "scripts/config.js" \
  --exclude "*.json" \
  --exclude "test-comments.html" \
  --exclude "sam-artifacts-*"

echo ""
echo "=== Invalidating CloudFront cache ==="
if [[ "$ENV" == "dev" ]]; then
  # For dev: get distribution ID from stack output
  DIST_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region     "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='DevCloudFrontDomain'].OutputValue" \
    --output text | xargs -I{} aws cloudfront list-distributions \
      --query "DistributionList.Items[?DomainName=='{}'].Id" \
      --output text)
else
  DIST_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?DomainName=='${CF_DOMAIN}'].Id" \
    --output text)
fi

if [ -n "$DIST_ID" ]; then
  aws cloudfront create-invalidation \
    --distribution-id "$DIST_ID" \
    --paths "/*"
  echo "Cache invalidated for distribution: $DIST_ID"
fi

echo ""
echo "✅ Deploy complete! (env: $ENV)"
echo "   Dashboard: $CF_URL"
echo "   API:       $API_URL"
