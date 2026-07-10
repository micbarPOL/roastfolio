import sys
import os
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("lambda"))

os.environ["AWS_REGION"] = "us-west-2"
os.environ["DATA_TABLE"] = "roastfolio-data"
os.environ["TRANSACTIONS_TABLE"] = "roastfolio-transactions"
os.environ["SNAPSHOTS_TABLE"] = "roastfolio-snapshots"
os.environ["USERS_TABLE"] = "roastfolio-users"
os.environ["RETIREMENT_TABLE"] = "roastfolio-retirement-plans"

import handler

event = {
    "httpMethod": "GET",
    "path": "/retirement-plans",
    "pathParameters": None,
    "queryStringParameters": None,
}

handler._get_caller_identity = lambda ev: ("e82153b0-10d1-70c7-dab9-824d6016be82", "test", "test")
handler._require_role = lambda ev, role: ("e82153b0-10d1-70c7-dab9-824d6016be82", None)

try:
    res = handler.handler(event, None)
    print("STATUS:", res.get("statusCode"))
    print("BODY:", res.get("body")[:500] if res.get("body") else None)
except Exception as e:
    print("CRASH:", e)

