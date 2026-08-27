import os
import sys

os.environ["AWS_REGION"] = "us-west-2"
os.environ["DATA_TABLE"] = "roastfolio-data"
os.environ["TRANSACTIONS_TABLE"] = "roastfolio-transactions"
os.environ["SNAPSHOTS_TABLE"] = "roastfolio-snapshots"
os.environ["USERS_TABLE"] = "roastfolio-users"

sys.path.insert(0, os.path.abspath("lambda"))
import portfolios
import snapshots

user_id = "e82153b0-10d1-70c7-dab9-824d6016be82"
portfolio_id = "ikze"

txs = portfolios.list_all_transactions(user_id, portfolio_id)
creotech_txs = [t for t in txs if t.get("ticker") == "CRI"]

print("Found transactions:", len(creotech_txs))
for tx in creotech_txs:
    print(f"Updating tx: {tx['transactionId']}")
    portfolios.update_transaction(user_id, portfolio_id, tx["transactionId"], {"ticker": "CRI.WA"})

holdings = portfolios._list_holdings_raw(user_id, portfolio_id)
creotech_holdings = [h for h in holdings if h.get("ticker") == "CRI"]
print("Found holdings:", len(creotech_holdings))

# update_transaction will NOT update the ticker in the holding if it already existed under a different ticker, wait!
# update_transaction modifies the transaction, then rebuilds holdings.
# rebuild_holdings_from_transactions will recreate the holding, but what if the holdingId is still `creotech--cri-`?
# In `rebuild_holdings_from_transactions`:
# current["ticker"] = ticker or current.get("ticker")
# So `CRI.WA` will overwrite `CRI`.
print("Triggering recalculation...")
from datetime import datetime, timezone
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
snapshots.recalculate_portfolio_snapshots_from_date(user_id, portfolio_id, "2020-01-01")
snapshots.recalculate_summary_snapshots_from_date(user_id, "2020-01-01")
print("Done!")

