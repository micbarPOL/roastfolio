def backfill_missing_xirr(user_id: str):
    """
    Scans all snapshots for the user. If any snapshot is missing 'xirr',
    calculates and saves it without fully rebuilding the snapshot.
    """
    user_portfolios = portfolios.list_portfolios(user_id)
    all_summary_transactions = []
    
    # 1. Backfill real portfolios
    for p in user_portfolios:
        pid = p["portfolioId"]
        txs = portfolios.list_all_transactions(user_id, pid, scan_forward=True)
        all_summary_transactions.extend(txs)
        
        snaps = list_snapshots(user_id, pid)
        missing = [s for s in snaps if s.get("xirr") is None]
        if not missing:
            continue
            
        print(f"Backfilling XIRR for {user_id} / {pid} ({len(missing)} snapshots)")
        for snapshot in missing:
            snap_date = snapshot["snapshotDate"]
            portfolio_value = snapshot.get("portfolioValue", 0)
            cfs = portfolios.extract_cashflows_from_transactions(txs, snap_date)
            cfs.append((snap_date, float(portfolio_value)))
            cfs.sort(key=lambda x: x[0])
            snap_xirr = Decimal(str(round(portfolios.calculate_xirr(cfs), 4)))
            
            _table().update_item(
                Key={"userId": user_id, "sk": snapshot["sk"]},
                UpdateExpression="SET xirr = :xirr",
                ExpressionAttributeValues={":xirr": snap_xirr}
            )

    # 2. Backfill summary portfolio
    summary_snaps = list_snapshots(user_id, "summary")
    summary_missing = [s for s in summary_snaps if s.get("xirr") is None]
    if summary_missing:
        print(f"Backfilling XIRR for {user_id} / summary ({len(summary_missing)} snapshots)")
        for snapshot in summary_missing:
            snap_date = snapshot["snapshotDate"]
            portfolio_value = snapshot.get("portfolioValue", 0)
            cfs = portfolios.extract_cashflows_from_transactions(all_summary_transactions, snap_date)
            cfs.append((snap_date, float(portfolio_value)))
            cfs.sort(key=lambda x: x[0])
            snap_xirr = Decimal(str(round(portfolios.calculate_xirr(cfs), 4)))
            
            _table().update_item(
                Key={"userId": user_id, "sk": snapshot["sk"]},
                UpdateExpression="SET xirr = :xirr",
                ExpressionAttributeValues={":xirr": snap_xirr}
            )
