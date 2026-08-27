import os
import boto3

dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
table = dynamodb.Table('roastfolio-data')

def get_price(ticker):
    res = table.get_item(Key={"pk": "SYSTEM", "sk": f"PRICE#{ticker}"})
    return res.get("Item")

print(f"CRI: {get_price('CRI')}")
print(f"CRI.WA: {get_price('CRI.WA')}")
