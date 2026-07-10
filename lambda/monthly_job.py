"""
lambda/monthly_job.py — AWS EventBridge Scheduled Lambda for Monthly Roasts

Invoked on the 1st of every month to compute 30-day performance and generate 
a monthly roast for all active users.
"""

import json
import logging
from datetime import datetime, timezone, timedelta

import db
import snapshots
import roast_engine

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event: dict, context) -> dict:
    """
    Cron trigger entry point.
    """
    logger.info("Starting monthly roast job")
    
    now = datetime.now(timezone.utc)
    target_date = (now.replace(day=1) - timedelta(days=1))
    
    users = db.list_users()
    processed = 0
    failed = 0
    
    for user in users:
        user_id = user.get("userId")
        if not user_id:
            continue
            
        settings = user.get("settings", {})
        if settings.get("roastIntensity") == "off":
            continue
            
        try:
            # Assuming db doesn't expose list_portfolios directly, we can use the same pattern as snapshots.py
            from portfolios import list_portfolios
            ports = list_portfolios(user_id)
            if not ports:
                continue
                
            port = ports[0]
            portfolio_id = port["portfolioId"]
            
            recent_snaps = snapshots.list_snapshots(user_id, portfolio_id, limit=60)
            if not recent_snaps:
                continue
                
            target_month_snaps = [s for s in recent_snaps if s["sk"].split("#")[-1].startswith(target_date.strftime("%Y-%m"))]
            if not target_month_snaps:
                continue
                
            current_snapshot = target_month_snaps[0]
            
            baseline_month_date = target_date.replace(day=1) - timedelta(days=1)
            baseline_month_snaps = [s for s in recent_snaps if s["sk"].split("#")[-1].startswith(baseline_month_date.strftime("%Y-%m"))]
            
            if baseline_month_snaps:
                prev_month_snapshot = baseline_month_snaps[0]
            else:
                prev_month_snapshot = target_month_snaps[-1]
                
            benchmark_monthly_pct = 2.5 # Mocked for MVP
            
            roast_engine.generate_monthly_roast(
                user_id=user_id,
                current_snapshot=current_snapshot,
                prev_month_snapshot=prev_month_snapshot,
                benchmark_monthly_pct=benchmark_monthly_pct,
                enable_ai=True
            )
            processed += 1
            
        except Exception as e:
            logger.error(f"Failed to generate monthly roast for {user_id}: {e}")
            failed += 1
            
    logger.info(f"Finished monthly roasts. Processed: {processed}, Failed: {failed}")
    return {
        "statusCode": 200,
        "body": json.dumps({"processed": processed, "failed": failed})
    }
