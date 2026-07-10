import os
os.environ["AWS_REGION"] = "us-west-2"
os.environ["DATA_TABLE"] = "roastfolio-data"
os.environ["TRANSACTIONS_TABLE"] = "roastfolio-transactions"
os.environ["SNAPSHOTS_TABLE"] = "roastfolio-snapshots"
os.environ["USERS_TABLE"] = "roastfolio-users"
os.environ["RETIREMENT_TABLE"] = "roastfolio-retirement-plans"

import sys
sys.path.insert(0, os.path.abspath("lambda"))
import portfolios
import retirement_plans

user_id = "e82153b0-10d1-70c7-dab9-824d6016be82"
txs = portfolios.list_transactions(user_id, "ikze", limit=1000)

for tx in txs:
    for k, v in tx.items():
        if isinstance(v, set):
            print("FOUND SET IN TX:", tx["transactionId"], k, v)

plans = retirement_plans.list_plans(user_id)
for p in plans:
    for k, v in p.items():
        if isinstance(v, set):
            print("FOUND SET IN PLAN:", p.get("planId"), k, v)

print("Checked DB.")
