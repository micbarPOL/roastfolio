import sys
sys.path.append("lambda")
import db, snapshots

for u in db.list_users():
    snaps = snapshots.list_snapshots(u["userId"], "summary", limit=2)
    ath = snapshots.get_portfolio_ath(u["userId"], "summary")
    print("User:", u.get("email"))
    print("ATH:", ath)
    print("Snaps:", snaps)
