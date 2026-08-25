import os
import sys

os.environ["AWS_REGION"] = "us-west-2"
os.environ["DATA_TABLE"] = "roastfolio-data"
os.environ["TRANSACTIONS_TABLE"] = "roastfolio-transactions"
os.environ["SNAPSHOTS_TABLE"] = "roastfolio-snapshots"
os.environ["USERS_TABLE"] = "roastfolio-users"

sys.path.insert(0, os.path.abspath("lambda"))
import handler
import portfolios

user_id = "e82153b0-10d1-70c7-dab9-824d6016be82"
portfolio_id = "ikze"

holdings = portfolios._list_holdings_raw(user_id, portfolio_id)
# mock price_cache
price_cache = {}
rates_cache = {}
handler.load_s3_cache = lambda: {"date": "2026-07-16"}
s3_cache = handler.load_s3_cache()

results, total, daily_pln, daily_pct = handler.compute_wallet(user_id, portfolio_id, holdings, price_cache, rates_cache, s3_cache)

for r in results:
    if "creo" in str(r.get("name", "")).lower():
        print(f"Computed Holding: {r}")

