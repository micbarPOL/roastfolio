import pytest

pytestmark = pytest.mark.full

from datetime import datetime, timezone
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import trigger_recalc
import monthly_recalculation


def test_generate_previous_month_wraps_sends_email_only_if_enabled():
    user_enabled = {
        "userId": "user-enabled",
        "email": "enabled@example.com",
        "settings": {"emailNotifications": True},
    }
    user_disabled = {
        "userId": "user-disabled",
        "email": "disabled@example.com",
        "settings": {"emailNotifications": False},
    }

    mock_doc = {
        "period": "2026-08",
        "overall_twr_pct": 2.5,
    }

    sent_calls = []

    def mock_send_if_enabled(profile, doc):
        if profile.get("settings", {}).get("emailNotifications"):
            sent_calls.append(profile["userId"])
            return {"success": True}
        return {"success": False, "skipped": True}

    def mock_get_user(uid):
        if uid == "user-enabled":
            return user_enabled
        if uid == "user-disabled":
            return user_disabled
        return None

    with patch.object(trigger_recalc.wrap_generator, "generate_monthly_wrap", return_value=mock_doc), \
         patch("db.get_user", side_effect=mock_get_user), \
         patch("email_service.send_monthly_recap_email_if_enabled", side_effect=mock_send_if_enabled):
        
        # Run on day one (or force=True)
        results = trigger_recalc.generate_previous_month_wraps(
            now=datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone.utc),
            user_ids=["user-enabled", "user-disabled"],
            force=True,
        )

    assert len(results) == 2
    assert sent_calls == ["user-enabled"]


def test_monthly_recalculation_does_not_send_emails():
    user_id = "user-1"
    job = {
        "job_id": "job-101",
        "user_id": user_id,
        "status": "pending",
        "benchmark_id": "WIG",
        "periods": ["2026-08"],
        "completed_periods": [],
        "failed_periods": [],
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
    }

    mock_send = MagicMock()

    with patch.object(monthly_recalculation, "get_job", return_value=job), \
         patch.object(monthly_recalculation, "_save", return_value=None), \
         patch.object(monthly_recalculation.wrap_generator, "generate_monthly_wrap", return_value={"period": "2026-08"}), \
         patch("email_service.send_monthly_recap_email", mock_send), \
         patch("email_service.send_monthly_recap_email_if_enabled", mock_send):
        
        event = {"action": "recalculate", "user_id": user_id, "job_id": "job-101"}
        monthly_recalculation.run_job(event, None)

    mock_send.assert_not_called()
