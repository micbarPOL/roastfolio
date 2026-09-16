import json
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import handler  # noqa: E402


class _WrapTable:
    def __init__(self, item=None):
        self.item = item
        self.keys = []

    def get_item(self, Key):
        self.keys.append(Key)
        return {"Item": self.item} if self.item else {}


class _DynamoResource:
    def __init__(self, table):
        self.table = table

    def Table(self, _name):
        return self.table


def test_monthly_wrap_api_reads_only_authenticated_users_partition():
    table = _WrapTable({
        "PK": "USER#user-1",
        "SK": "WRAP#MONTH#2026-09",
        "period": "2026-09",
        "overall_twr_pct": Decimal("4.25"),
    })
    event = {
        "httpMethod": "GET",
        "path": "/monthly-wraps",
        "requestContext": {"authorizer": {"claims": {"sub": "user-1"}}},
        "queryStringParameters": {"period": "2026-09"},
    }

    with patch.object(
        handler.boto3, "resource", return_value=_DynamoResource(table)
    ):
        response = handler.monthly_wraps_handler(event)

    assert response["statusCode"] == 200
    assert table.keys == [{"PK": "USER#user-1", "SK": "WRAP#MONTH#2026-09"}]
    assert json.loads(response["body"])["item"]["overall_twr_pct"] == 4.25


def test_monthly_wrap_api_rejects_invalid_period():
    event = {
        "httpMethod": "GET",
        "path": "/monthly-wraps",
        "requestContext": {"authorizer": {"claims": {"sub": "user-1"}}},
        "queryStringParameters": {"period": "September"},
    }
    response = handler.monthly_wraps_handler(event)
    assert response["statusCode"] == 400
