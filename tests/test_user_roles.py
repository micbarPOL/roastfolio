import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import db  # noqa: E402


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        user_id = Item["userId"]
        if ConditionExpression == "attribute_not_exists(userId)" and user_id in self.items:
            raise RuntimeError("exists")
        self.items[user_id] = dict(Item)
        return {}

    def get_item(self, Key):
        item = self.items.get(Key["userId"])
        return {"Item": dict(item)} if item else {}

    def update_item(
        self,
        Key,
        UpdateExpression,
        ExpressionAttributeNames,
        ExpressionAttributeValues,
        ConditionExpression=None,
        ReturnValues=None,
    ):
        user_id = Key["userId"]
        if ConditionExpression == "attribute_exists(userId)" and user_id not in self.items:
            raise RuntimeError("missing")
        item = dict(self.items[user_id])
        for placeholder, field in ExpressionAttributeNames.items():
            value_key = next(
                key for expr, key in zip(UpdateExpression.replace("SET ", "").split(", "), ExpressionAttributeValues.keys())
                if expr.startswith(placeholder)
            )
            item[field] = ExpressionAttributeValues[value_key]
        self.items[user_id] = item
        return {"Attributes": dict(item)}


class UserRoleTests(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.patches = [
            patch.object(db, "_table", return_value=self.table),
            patch.object(db, "_now_iso", return_value="2026-05-12T12:00:00Z"),
            patch.object(db, "_ADVANCED_ROLE_EMAILS", {"michal.bardadyn@gmail.com"}),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for p in reversed(self.patches):
            p.stop()

    def test_create_user_assigns_advanced_role_for_whitelisted_email(self):
        profile = db.create_user("user-1", "michal.bardadyn@gmail.com", "Michal")
        self.assertEqual(profile["email"], "michal.bardadyn@gmail.com")
        self.assertEqual(profile["role"], db.ROLE_ADVANCED)

    def test_get_or_create_user_upgrades_existing_whitelisted_user(self):
        self.table.items["user-1"] = {
            "userId": "user-1",
            "email": "michal.bardadyn@gmail.com",
            "nickname": "Michal",
            "role": db.ROLE_BASIC,
            "createdAt": "2026-05-10T12:00:00Z",
            "updatedAt": "2026-05-10T12:00:00Z",
            "settings": db._default_settings(),
            "portfolioMeta": db._default_portfolio_meta(),
            "subscription": db._default_subscription(),
        }

        profile = db.get_or_create_user("user-1", "michal.bardadyn@gmail.com", "Michal")

        self.assertEqual(profile["role"], db.ROLE_ADVANCED)
        self.assertEqual(self.table.items["user-1"]["role"], db.ROLE_ADVANCED)


if __name__ == "__main__":
    unittest.main()
