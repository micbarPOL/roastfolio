#!/usr/bin/env bash
# Shared helpers for the roastfolio_ui_20 merge guard (sourced by the hooks).

FEATURE="roastfolio_ui_20"
PROTECTED="dev test prod"

override_enabled() {
  case "${ALLOW_BRANCH_MERGE:-}" in 1|true|yes) return 0 ;; esac
  return 1
}

# Commits on the feature branch not yet in any protected branch.
# With "remote" only origin/* branches count, so an approved local merge cannot hide commits from the push guard.
feature_only_commits() {
  git show-ref --verify -q "refs/heads/$FEATURE" || return 0
  local refs=() b r
  for b in $PROTECTED; do
    for r in "refs/heads/$b" "refs/remotes/origin/$b"; do
      [ "${1:-}" = "remote" ] && [ "${r#refs/remotes/}" = "$r" ] && continue
      git show-ref --verify -q "$r" && refs+=("$r")
    done
  done
  git rev-list "refs/heads/$FEATURE" --not ${refs[@]+"${refs[@]}"}
}

# Prints feature-only commits found in the newline-separated list on stdin.
intersect_with_feature() {
  comm -12 <(feature_only_commits "$@" | sort) <(sort)
}

block_message() {
  echo "BLOCKED: $FEATURE must not be merged into dev, test or prod until explicitly approved." >&2
  echo "Deploying this branch to dev/test for testing is still allowed." >&2
  echo "Approved override: ALLOW_BRANCH_MERGE=1 <git command>" >&2
}
