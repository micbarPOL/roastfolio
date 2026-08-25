import os
import sys

os.environ["AWS_REGION"] = "us-west-2"
os.environ["DATA_TABLE"] = "roastfolio-data"
os.environ["TRANSACTIONS_TABLE"] = "roastfolio-transactions"
os.environ["SNAPSHOTS_TABLE"] = "roastfolio-snapshots"
os.environ["USERS_TABLE"] = "roastfolio-users"
os.environ["RETIREMENT_TABLE"] = "roastfolio-retirement-plans"

sys.path.insert(0, os.path.abspath("lambda"))
import portfolios

user_id = "e82153b0-10d1-70c7-dab9-824d6016be82"
portfolio_id = "ikze"

txs = portfolios.list_all_transactions(user_id, portfolio_id)
print(f"Total transactions in IKZE: {len(txs)}")

creotech_txs = [t for t in txs if "creotech" in str(t.get("name", "")).lower() or "creotech" in str(t.get("ticker", "")).lower()]

print(f"Creotech transactions: {len(creotech_txs)}")
for tx in creotech_txs:
    print(tx)

holdings = portfolios._list_holdings_raw(user_id, portfolio_id)
creotech_holdings = [h for h in holdings if "creotech" in str(h.get("name", "")).lower() or "creotech" in str(h.get("ticker", "")).lower()]
for h in creotech_holdings:
    print(f"Holding: {h}")

