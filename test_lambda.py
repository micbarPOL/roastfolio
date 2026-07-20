import sys
import json
from lambda.handler import benchmark_daily_handler

event = {
    "httpMethod": "GET",
    "requestContext": {
        "authorizer": {
            "claims": {
                "email": "michal@example.com",
                "custom:role": "1"
            }
        }
    },
    "queryStringParameters": {
        "benchmarkId": "SP500"
    }
}
res = benchmark_daily_handler(event)
print("Status:", res["statusCode"])
body = json.loads(res["body"])
print("Keys:", body.keys())
if "daily" in body:
    print("Daily length:", len(body["daily"]))
    if len(body["daily"]) > 0:
        print("First 3:", body["daily"][:3])
