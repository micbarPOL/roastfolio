import boto3
from decimal import Decimal

db = boto3.resource('dynamodb')
table = db.Table('roastfolio-snapshots')

# Just scan for now since it's a dev env
response = table.scan()
for item in response.get('Item', []) + response.get('Items', []):
    print(item)
