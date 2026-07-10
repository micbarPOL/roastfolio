import os
os.environ["AWS_REGION"] = "us-west-2"  # Default region
os.environ["DATA_TABLE"] = "roastfolio-data"
os.environ["TRANSACTIONS_TABLE"] = "roastfolio-transactions"
os.environ["SNAPSHOTS_TABLE"] = "roastfolio-snapshots"
os.environ["USERS_TABLE"] = "roastfolio-users"

import sys
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("lambda"))

import boto3
import portfolios, snapshots, db

def run():
    print("Fetching users...")
    table = boto3.resource('dynamodb').Table(os.environ["USERS_TABLE"])
    response = table.scan()
    for item in response.get('Items', []):
        user_id = item["userId"]
        print(f"User: {user_id}")
        
        user_portfolios = portfolios.list_portfolios(user_id)
        
        for p in user_portfolios:
            pid = p["portfolioId"]
            snaps = snapshots.list_snapshots(user_id, pid)
            if not snaps:
                continue
            
            # Find the earliest snapshot missing XIRR
            missing_dates = [s["snapshotDate"] for s in snaps if s.get("xirr") is None]
            
            if missing_dates:
                first_missing = min(missing_dates)
                print(f"  [{pid}] Missing XIRR starting from {first_missing}. Triggering recalculate...")
                snapshots.recalculate_portfolio_snapshots_from_date(user_id, pid, first_missing)
            else:
                # Force recalculate from beginning anyway as requested: 
                # "can you trigger recalculate_portfolio_snapshots_from_date() for prod wallets?"
                # Let's just recalculate from the beginning for all prod wallets to be safe.
                first_date = snaps[0]["snapshotDate"]
                print(f"  [{pid}] Triggering full recalculate from {first_date}...")
                snapshots.recalculate_portfolio_snapshots_from_date(user_id, pid, first_date)
            
        print("  Recalculating Summary...")
        summary_snaps = snapshots.list_snapshots(user_id, "summary")
        if summary_snaps:
            missing_dates = [s["snapshotDate"] for s in summary_snaps if s.get("xirr") is None]
            if missing_dates:
                first_missing = min(missing_dates)
                print(f"  [summary] Missing XIRR starting from {first_missing}. Recalculating...")
                snapshots.recalculate_summary_snapshots_from_date(user_id, first_missing)
            else:
                first_date = summary_snaps[0]["snapshotDate"]
                print(f"  [summary] Triggering full recalculate from {first_date}...")
                snapshots.recalculate_summary_snapshots_from_date(user_id, first_date)

if __name__ == "__main__":
    run()
