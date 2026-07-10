def backfill_xirr_if_empty(user_id: str):
    portfolios_list = portfolios.list_portfolios(user_id)
    portfolios_list.append({"portfolioId": "summary"})
    
    for p in portfolios_list:
        pid = p["portfolioId"]
        snaps = list_snapshots(user_id, pid)
        missing = [s for s in snaps if s.get("xirr") is None]
        if not missing:
            continue
            
        print(f"Backfilling XIRR for user {user_id} portfolio {pid} ({len(missing)} snapshots)")
        
        if pid == "summary":
            # For summary, get all transactions from all real wallets
            all_txs = []
            for real_p in user_portfolios: # need user_portfolios here
                pass # Wait, let's just use the exact logic we wrote for recalculate summary
