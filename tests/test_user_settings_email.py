import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import db
import handler


def test_default_settings_contains_email_notifications_disabled():
    settings = db._default_settings()
    assert settings["emailNotifications"] is False
    assert settings["notifications"] is False
    assert settings["hideCashInNotifications"] is False
    assert settings["notificationEmails"] == []


def test_profile_handler_updates_email_notifications_and_recipients():
    existing_user = {
        "userId": "user-42",
        "email": "user@example.com",
        "nickname": "Tester",
        "settings": db._default_settings(),
    }

    import base64
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "user-42", "email": "user@example.com", "nickname": "Tester"}).encode()).decode().rstrip("=")
    token = f"{header}.{payload}.sig"

    event = {
        "httpMethod": "PUT",
        "path": "/profile",
        "headers": {"Authorization": f"Bearer {token}"},
        "body": json.dumps({
            "settings": {
                "emailNotifications": True,
                "hideCashInNotifications": True,
                "notificationEmails": [
                    "WORK@Company.com",
                    " work@company.com ",  # duplicate
                    "personal@gmail.com",
                    "invalid-email",
                ],
            }
        }),
    }

    updated_storage = {}

    def mock_update_user(uid, updates):
        updated_storage.update(updates)
        return {"userId": uid, **updates}

    with patch.object(handler.db, "get_user", return_value=existing_user), \
         patch.object(handler.db, "update_user", side_effect=mock_update_user):
        resp = handler.profile_handler(event)

    assert resp["statusCode"] == 200
    saved_settings = updated_storage["settings"]
    assert saved_settings["emailNotifications"] is True
    assert saved_settings["notifications"] is True
    assert saved_settings["hideCashInNotifications"] is True
    assert saved_settings["notificationEmails"] == ["work@company.com", "personal@gmail.com"]
