import os
os.environ["AWS_REGION"] = "us-west-2"
os.environ["DATA_TABLE"] = "roastfolio-data"
os.environ["TRANSACTIONS_TABLE"] = "roastfolio-transactions"
os.environ["SNAPSHOTS_TABLE"] = "roastfolio-snapshots"
os.environ["USERS_TABLE"] = "roastfolio-users"

import sys
sys.path.insert(0, os.path.abspath("lambda"))

import boto3
import portfolios, snapshots

def run():
    print("Fetching users from DynamoDB...")
    table = boto3.resource('dynamodb').Table(os.environ["USERS_TABLE"])
    users = table.scan().get("Items", [])
    
    for item in users:
        user_id = item["userId"]
        email = item.get("email", user_id)
        print(f"\nUser: {email} ({user_id})")
        
        user_portfolios = portfolios.list_portfolios(user_id)
        for p in user_portfolios:
            pid = p["portfolioId"]
            print(f"  --> Rebuilding holdings for [{pid}]...")
            holdings = portfolios.rebuild_holdings_from_transactions(user_id, pid)
            active_tickers = [h.get("ticker") or h.get("name") for h in holdings]
            print(f"      Active holdings ({len(holdings)}): {active_tickers}")
            
            snaps = snapshots.list_snapshots(user_id, pid)
            if snaps:
                earliest_date = min(s["snapshotDate"] for s in snaps)
                print(f"      Recalculating snapshots from {earliest_date}...")
                snapshots.recalculate_portfolio_snapshots_from_date(user_id, pid, earliest_date)
        
        print("  --> Recalculating Summary snapshots...")
        summary_snaps = snapshots.list_snapshots(user_id, "summary")
        if summary_snaps:
            earliest_date = min(s["snapshotDate"] for s in summary_snaps)
            print(f"      Recalculating Summary snapshots from {earliest_date}...")
            snapshots.recalculate_summary_snapshots_from_date(user_id, earliest_date)

    print("\nALL PRODUCTION PORTFOLIOS REBUILT & RECALCULATED SUCCESSFULLY!")

if __name__ == "__main__":
    run()
