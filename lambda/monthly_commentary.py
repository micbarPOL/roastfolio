import json
import os
import random
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone, timedelta
import db

@dataclass
class MonthStats:
    is_green: bool
    is_red: bool
    green_streak: int
    red_streak: int
    prev_green_streak: int
    prev_red_streak: int
    beat_benchmark: bool

# Load comments data globally
COMMENTS_FILE = os.path.join(os.path.dirname(__file__), "data", "monthly_comments.json")
try:
    with open(COMMENTS_FILE, "r") as f:
        _ALL_COMMENTS = json.load(f)
except Exception:
    _ALL_COMMENTS = []

def _get_scenario_key(month: MonthStats) -> str:
    if month.prev_green_streak >= 3 and month.is_red:
        return "streak_breaker_green_to_red"
    if month.prev_red_streak >= 3 and month.is_green:
        return "streak_breaker_red_to_green"
    if month.green_streak >= 3:
        return "active_streak_green"
    if month.red_streak >= 3:
        return "active_streak_red"
    if month.is_green and month.beat_benchmark:
        return "green_beat_benchmark"
    if month.is_green and not month.beat_benchmark:
        return "green_lagged_benchmark"
    if month.is_red and month.beat_benchmark:
        return "red_beat_benchmark"
    return "red_lagged_benchmark"

def get_monthly_wrap_commentary(user_id: str, month: MonthStats, is_email: bool = False) -> str:
    """
    Pick a commentary based on streaks and benchmark outperformance.
    Tone is pulled from user settings.
    Respects cooldowns: 180 days for emails, 7 days for ad hoc.
    """
    profile = db.get_user(user_id) or {}
    tone = (profile.get("settings") or {}).get("roastIntensity", "sarcastic")
    
    scenario_key = _get_scenario_key(month)
    
    # Filter comments by scenario and tone
    candidates = [
        c for c in _ALL_COMMENTS 
        if c.get("scenarioKey") == scenario_key and c.get("tone") == tone
    ]
    
    if not candidates:
        return "No comment available."

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    
    wrap_audit = profile.get("wrapAudit", {})
    available = []
    
    # Check cooldowns
    for c in candidates:
        tid = c["templateId"]
        audit_entry = wrap_audit.get(tid, {})
        
        if is_email:
            last_email_str = audit_entry.get("lastEmail")
            if last_email_str:
                last_email = datetime.fromisoformat(last_email_str)
                if now - last_email < timedelta(days=180):
                    continue
        else:
            last_adhoc_str = audit_entry.get("lastAdhoc")
            if last_adhoc_str:
                last_adhoc = datetime.fromisoformat(last_adhoc_str)
                if not last_adhoc_str.startswith(today_str):
                    if now - last_adhoc < timedelta(days=7):
                        continue
        available.append(c)
        
    if not available:
        # Fallback to the one with the oldest timestamp
        if is_email:
            available = sorted(candidates, key=lambda c: wrap_audit.get(c["templateId"], {}).get("lastEmail", ""))
        else:
            available = sorted(candidates, key=lambda c: wrap_audit.get(c["templateId"], {}).get("lastAdhoc", ""))
            
        if available:
            available = [available[0]]
            
    if is_email:
        chosen = random.choice(available)
    else:
        # Pick random comment every day
        rng = random.Random(f"{user_id}_{today_str}_{scenario_key}")
        chosen = rng.choice(available)

    # Persist the audit trail
    tid = chosen["templateId"]
    if tid not in wrap_audit:
        wrap_audit[tid] = {}
        
    should_update = False
    if is_email:
        wrap_audit[tid]["lastEmail"] = now.isoformat()
        should_update = True
    else:
        last_adhoc_str = wrap_audit[tid].get("lastAdhoc", "")
        if not last_adhoc_str.startswith(today_str):
            wrap_audit[tid]["lastAdhoc"] = now.isoformat()
            should_update = True
            
    if should_update:
        try:
            db.update_user(user_id, {"wrapAudit": wrap_audit})
        except Exception:
            pass

    return chosen["messageTemplate"]
