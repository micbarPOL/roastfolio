import sys, json
sys.path.append("lambda")
import db, portfolios

for u in db.list_users():
    if u.get("email") == "michal.bardadyn@gmail.com":
        txs = portfolios.list_transactions(u["userId"], "summary")
        for tx in txs:
            if tx["date"].startswith("2026-07-08") or tx["date"].startswith("2026-07-07"):
                print(tx)
