import sys, json
sys.path.append("lambda")
import db, handler
from datetime import datetime

event = {
    "path": "/prices",
    "httpMethod": "GET",
    "requestContext": {
        "authorizer": {
            "jwt": {
                "claims": {
                    "sub": "some_sub",
                    "email": "michal.bardadyn@gmail.com",
                    "nickname": "michal.bardadyn@gmail.com"
                }
            }
        }
    },
    "queryStringParameters": {
        "view": "full"
    }
}
# We need to set the user id in db for this mock to work properly
for u in db.list_users():
    if u.get("email") == "michal.bardadyn@gmail.com":
        event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"] = u["userId"]
        break

response = handler.handler(event, None)
body = json.loads(response["body"])
print("Total Value:", body.get("portfolioTotalValue"))
print("Daily PLN:", body.get("portfolioDailyChangePLN"))
print("ATH:", body.get("portfolioAth"))
