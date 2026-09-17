import json
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import handler


class _MockWrapTable:
    def __init__(self, item=None):
        self.item = item

    def get_item(self, Key):
        return {"Item": self.item} if self.item else {}


class _MockDynamoResource:
    def __init__(self, table):
        self.table = table

    def Table(self, _name):
        return self.table


def test_monthly_wrap_send_email_options_preflight():
    event = {
        "httpMethod": "OPTIONS",
        "path": "/monthly-wraps/email",
    }
    resp = handler.monthly_wrap_send_email_handler(event)
    assert resp["statusCode"] == 200
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
    assert "Authorization" in resp["headers"]["Access-Control-Allow-Headers"]


def test_monthly_wrap_send_email_rejects_unauthenticated():
    event = {
        "httpMethod": "POST",
        "path": "/monthly-wraps/email",
        "body": json.dumps({"period": "2026-08"}),
    }
    resp = handler.monthly_wrap_send_email_handler(event)
    assert resp["statusCode"] == 401


def test_monthly_wrap_send_email_rejects_invalid_period():
    event = {
        "httpMethod": "POST",
        "path": "/monthly-wraps/email",
        "requestContext": {"authorizer": {"claims": {"sub": "user-123"}}},
        "body": json.dumps({"period": "invalid-date"}),
    }
    resp = handler.monthly_wrap_send_email_handler(event)
    assert resp["statusCode"] == 400
    assert "period must use YYYY-MM format" in json.loads(resp["body"])["error"]


def test_monthly_wrap_send_email_returns_404_when_wrap_missing():
    table = _MockWrapTable(item=None)
    event = {
        "httpMethod": "POST",
        "path": "/monthly-wraps/email",
        "requestContext": {"authorizer": {"claims": {"sub": "user-123"}}},
        "body": json.dumps({"period": "2026-08"}),
    }

    with patch.object(handler.boto3, "resource", return_value=_MockDynamoResource(table)):
        resp = handler.monthly_wrap_send_email_handler(event)

    assert resp["statusCode"] == 404
    assert "Monthly audit not found" in json.loads(resp["body"])["error"]


def test_monthly_wrap_send_email_success():
    wrap_item = {
        "PK": "USER#user-123",
        "SK": "WRAP#MONTH#2026-08",
        "period": "2026-08",
        "overall_twr_pct": Decimal("3.5"),
    }
    user_profile = {
        "userId": "user-123",
        "email": "user@example.com",
        "settings": {
            "emailNotifications": False,  # Note: manual trigger sends even if auto notifications are off!
            "notificationEmails": ["extra@example.com"],
        },
    }

    table = _MockWrapTable(item=wrap_item)
    mock_send = MagicMock(return_value={"success": True, "message_id": "msg-111", "recipients": ["user@example.com", "extra@example.com"]})

    event = {
        "httpMethod": "POST",
        "path": "/monthly-wraps/email",
        "requestContext": {"authorizer": {"claims": {"sub": "user-123"}}},
        "body": json.dumps({"period": "2026-08"}),
    }

    with patch.object(handler.boto3, "resource", return_value=_MockDynamoResource(table)), \
         patch.object(handler.db, "get_user", return_value=user_profile), \
         patch("email_service.send_monthly_recap_email", mock_send):
        resp = handler.monthly_wrap_send_email_handler(event)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert "user@example.com" in body["recipients"]
    assert "extra@example.com" in body["recipients"]
    mock_send.assert_called_once()
