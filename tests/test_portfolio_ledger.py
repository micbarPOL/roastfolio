import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from boto3.dynamodb.types import TypeDeserializer


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import portfolios  # noqa: E402


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[(Item["userId"], Item["sk"])] = dict(Item)
        return {}

    def get_item(self, Key):
        item = self.items.get((Key["userId"], Key["sk"]))
        return {"Item": dict(item)} if item else {}

    def delete_item(self, Key):
        self.items.pop((Key["userId"], Key["sk"]), None)
        return {}

    def query(self, KeyConditionExpression=None, ScanIndexForward=True, Limit=None):
        user_id = None
        prefix = None
        if hasattr(KeyConditionExpression, "_values"):
            values = KeyConditionExpression._values
            if len(values) == 2 and hasattr(values[0], "_values") and hasattr(values[1], "_values"):
                user_id = values[0]._values[1]
                prefix = values[1]._values[1]
            elif len(values) == 2:
                user_id = values[1]
        items = [dict(v) for (uid, sk), v in self.items.items() if uid == user_id and (prefix is None or sk.startswith(prefix))]
        items.sort(key=lambda x: x["sk"], reverse=not ScanIndexForward)
        if Limit is not None:
            items = items[:Limit]
        return {"Items": items}

    class _BatchWriter:
        def __init__(self, table):
            self.table = table

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def delete_item(self, Key):
            self.table.delete_item(Key)

        def put_item(self, Item):
            self.table.put_item(Item)

    def batch_writer(self):
        return FakeTable._BatchWriter(self)


class FakeClient:
    def __init__(self, data_table, tx_table):
        self.data_table = data_table
        self.tx_table = tx_table
        self.deserializer = TypeDeserializer()

    def _deserialize_map(self, wire_map):
        return {k: self.deserializer.deserialize(v) for k, v in wire_map.items()}

    def transact_write_items(self, TransactItems):
        for item in TransactItems:
            if "Put" in item:
                put = item["Put"]
                decoded = self._deserialize_map(put["Item"])
                table = self.tx_table if put["TableName"] == portfolios._TRANSACTIONS_TABLE_NAME else self.data_table
                table.put_item(decoded)
            elif "Delete" in item:
                delete = item["Delete"]
                decoded = self._deserialize_map(delete["Key"])
                table = self.tx_table if delete["TableName"] == portfolios._TRANSACTIONS_TABLE_NAME else self.data_table
                table.delete_item(decoded)
        return {}


class PortfolioLedgerTests(unittest.TestCase):
    def setUp(self):
        self.data_table = FakeTable()
        self.tx_table = FakeTable()
        self.client = FakeClient(self.data_table, self.tx_table)
        self.user_id = "user-1"
        self.portfolio_id = "xtb"
        self.data_table.put_item({
            "userId": self.user_id,
            "sk": portfolios._portfolio_sk(self.portfolio_id),
            "portfolioId": self.portfolio_id,
            "name": "XTB",
            "type": "real",
            "currency": "PLN",
            "color": "#4a9fd4",
            "order": 1,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
        })

        self.patches = [
            patch.object(portfolios, "_table", return_value=self.data_table),
            patch.object(portfolios, "_transactions_table", return_value=self.tx_table),
            patch.object(portfolios, "_client", return_value=self.client),
            patch.object(portfolios, "_now", return_value="2026-05-12T10:00:00Z"),
            patch.object(portfolios, "_today", return_value="2026-05-12"),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(self._cleanup_patches)

    def _cleanup_patches(self):
        for p in reversed(self.patches):
            p.stop()

    def _deposit_cash(self, amount, transaction_date="2026-05-09"):
        return portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "DEPOSIT",
            "value": amount,
            "transactionDate": transaction_date,
            "comment": "Seed cash",
        })

    def test_buy_creates_holding_and_transaction(self):
        self._deposit_cash(250)
        tx = portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY",
            "ticker": "AAPL",
            "name": "Apple",
            "currency": "USD",
            "quantity": 2,
            "value": 205,
            "commission": 5,
            "comment": "Initial buy",
            "transactionDate": "2026-05-10",
        })

        holdings = portfolios.list_holdings(self.user_id, self.portfolio_id)
        stock = next(h for h in holdings if h.get("ticker") == "AAPL")
        cash = next(h for h in holdings if h.get("ticker") is None)
        self.assertEqual(stock["units"], Decimal("2"))
        self.assertEqual(stock["purchaseValue"], Decimal("205"))
        self.assertEqual(cash["purchaseValue"], Decimal("45"))
        self.assertEqual(tx["type"], "BUY")
        self.assertEqual(tx["value"], Decimal("205"))

        transactions = portfolios.list_transactions(self.user_id, self.portfolio_id)
        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[0]["comment"], "Initial buy")

    def test_update_transaction_recomputes_value_moves_date_and_rebuilds_holdings(self):
        self._deposit_cash(500, transaction_date="2026-05-01")
        tx = portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY",
            "ticker": "AAPL",
            "name": "Apple",
            "currency": "USD",
            "quantity": 2,
            "price": 100,
            "value": 205,
            "commission": 5,
            "transactionDate": "2026-05-10",
        })

        result = portfolios.update_transaction(self.user_id, self.portfolio_id, tx["transactionId"], {
            "quantity": 3,
            "price": 110,
            "commission": 4,
            "transactionDate": "2026-05-08",
            "name": "Apple Inc.",
            "ticker": "AAPL",
        })

        self.assertEqual(result["recalculateFrom"], "2026-05-08")
        self.assertEqual(result["transaction"]["value"], Decimal("334"))
        self.assertEqual(result["transaction"]["name"], "Apple Inc.")
        old_key = {"userId": self.user_id, "sk": portfolios._transaction_sk(self.portfolio_id, "2026-05-10", tx["transactionId"])}
        new_key = {"userId": self.user_id, "sk": portfolios._transaction_sk(self.portfolio_id, "2026-05-08", tx["transactionId"])}
        self.assertNotIn("Item", self.tx_table.get_item(old_key))
        self.assertIn("Item", self.tx_table.get_item(new_key))

        holdings = portfolios.list_holdings(self.user_id, self.portfolio_id)
        stock = next(h for h in holdings if h.get("ticker") == "AAPL")
        cash = next(h for h in holdings if h.get("ticker") is None)
        self.assertEqual(stock["units"], Decimal("3"))
        self.assertEqual(stock["purchaseValue"], Decimal("334"))
        self.assertEqual(cash["purchaseValue"], Decimal("166"))

    def test_second_buy_accumulates_units_and_cost(self):
        self._deposit_cash(700)
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY", "ticker": "AAPL", "name": "Apple", "currency": "USD",
            "quantity": 2, "value": 200, "transactionDate": "2026-05-10",
        })
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY", "ticker": "AAPL", "name": "Apple", "currency": "USD",
            "quantity": 3, "value": 332, "commission": 2, "transactionDate": "2026-05-11",
        })

        holding = next(h for h in portfolios.list_holdings(self.user_id, self.portfolio_id) if h.get("ticker") == "AAPL")
        self.assertEqual(holding["units"], Decimal("5"))
        self.assertEqual(holding["purchaseValue"], Decimal("532"))

    def test_buy_with_value_and_commission_updates_cost_basis(self):
        self._deposit_cash(205)
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY", "ticker": "AAPL", "name": "Apple", "currency": "USD",
            "quantity": 2, "value": 205, "commission": 5, "transactionDate": "2026-05-10",
        })

        holding = next(h for h in portfolios.list_holdings(self.user_id, self.portfolio_id) if h.get("ticker") == "AAPL")
        self.assertEqual(holding["units"], Decimal("2"))
        self.assertEqual(holding["purchaseValue"], Decimal("205"))

    def test_sell_reduces_units_and_cost_basis(self):
        self._deposit_cash(400)
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY", "ticker": "AAPL", "name": "Apple", "currency": "USD",
            "quantity": 4, "value": 400, "transactionDate": "2026-05-10",
        })

        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "SELL", "ticker": "AAPL", "name": "Apple", "currency": "USD",
            "quantity": 1, "value": 120, "transactionDate": "2026-05-11",
        })

        holdings = portfolios.list_holdings(self.user_id, self.portfolio_id)
        holding = next(h for h in holdings if h.get("ticker") == "AAPL")
        cash = next(h for h in holdings if h.get("ticker") is None)
        self.assertEqual(holding["units"], Decimal("3"))
        self.assertEqual(holding["purchaseValue"], Decimal("300"))
        self.assertEqual(cash["purchaseValue"], Decimal("120"))

    def test_sell_to_zero_removes_holding(self):
        self._deposit_cash(100)
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY", "ticker": "AAPL", "name": "Apple", "currency": "USD",
            "quantity": 1, "value": 100, "transactionDate": "2026-05-10",
        })

        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "SELL", "ticker": "AAPL", "name": "Apple", "currency": "USD",
            "quantity": 1, "value": 90, "transactionDate": "2026-05-11",
        })

        holdings = portfolios.list_holdings(self.user_id, self.portfolio_id)
        self.assertEqual([h for h in holdings if h.get("ticker") == "AAPL"], [])
        self.assertEqual(next(h for h in holdings if h.get("ticker") is None)["purchaseValue"], Decimal("90"))

    def test_sell_rejects_insufficient_quantity(self):
        self._deposit_cash(100)
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY", "ticker": "AAPL", "name": "Apple", "currency": "USD",
            "quantity": 1, "value": 100, "transactionDate": "2026-05-10",
        })

        with self.assertRaisesRegex(ValueError, "Insufficient quantity"):
            portfolios.record_transaction(self.user_id, self.portfolio_id, {
                "type": "SELL", "ticker": "AAPL", "name": "Apple", "currency": "USD",
                "quantity": 2, "value": 200, "transactionDate": "2026-05-11",
            })

    def test_sell_requires_existing_holding(self):
        with self.assertRaisesRegex(ValueError, "Holding not found"):
            portfolios.record_transaction(self.user_id, self.portfolio_id, {
                "type": "SELL", "ticker": "AAPL", "name": "Apple", "currency": "USD",
                "quantity": 1, "price": 100, "transactionDate": "2026-05-11",
            })

    def test_invalid_transaction_type_rejected(self):
        with self.assertRaisesRegex(ValueError, "BUY, SELL, DEPOSIT, WITHDRAWAL, DIVIDEND, SPINOFF, EXTRA_COST, or CASH_ADJUSTMENT"):
            portfolios.record_transaction(self.user_id, self.portfolio_id, {
                "type": "BONUS", "ticker": "AAPL", "name": "Apple", "quantity": 1,
            })

    def test_invalid_transaction_date_rejected(self):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            portfolios.record_transaction(self.user_id, self.portfolio_id, {
                "type": "BUY", "ticker": "AAPL", "name": "Apple", "quantity": 1,
                "transactionDate": "12-05-2026",
            })

    def test_legacy_put_holding_creates_buy_transaction(self):
        holding = portfolios.put_holding(self.user_id, self.portfolio_id, {
            "ticker": "MSFT",
            "name": "Microsoft",
            "currency": "USD",
            "units": 2,
            "purchaseValue": 400,
        })
        self.assertEqual(holding["units"], Decimal("2"))
        txs = portfolios.list_transactions(self.user_id, self.portfolio_id)
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]["type"], "BUY")

    def test_deposit_creates_cash_position(self):
        tx = self._deposit_cash(123.45)
        holdings = portfolios.list_holdings(self.user_id, self.portfolio_id)
        cash = next(h for h in holdings if h.get("ticker") is None)
        self.assertEqual(cash["name"], "Cash")
        self.assertEqual(cash["purchaseValue"], Decimal("123.45"))
        self.assertEqual(tx["type"], "DEPOSIT")

    def test_withdrawal_reduces_cash_position(self):
        self._deposit_cash(200)
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "WITHDRAWAL",
            "value": 75,
            "transactionDate": "2026-05-10",
        })
        cash = next(h for h in portfolios.list_holdings(self.user_id, self.portfolio_id) if h.get("ticker") is None)
        self.assertEqual(cash["purchaseValue"], Decimal("125"))

    def test_buy_rejects_when_cash_is_insufficient(self):
        with self.assertRaisesRegex(ValueError, "Insufficient cash balance"):
            portfolios.record_transaction(self.user_id, self.portfolio_id, {
                "type": "BUY",
                "ticker": "AAPL",
                "name": "Apple",
                "currency": "USD",
                "quantity": 1,
                "value": 100,
                "transactionDate": "2026-05-10",
            })

    def test_buy_with_auto_cash_adds_deposit_before_trade(self):
        tx = portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY",
            "ticker": "AAPL",
            "name": "Apple",
            "currency": "USD",
            "quantity": 1,
            "value": 100,
            "transactionDate": "2026-05-10",
            "autoAddCash": True,
        })
        holdings = portfolios.list_holdings(self.user_id, self.portfolio_id)
        self.assertEqual([h for h in holdings if h.get("ticker") is None], [])
        self.assertEqual(next(h for h in holdings if h.get("ticker") == "AAPL")["purchaseValue"], Decimal("100"))
        txs = portfolios.list_transactions(self.user_id, self.portfolio_id)
        self.assertEqual(len(txs), 2)
        self.assertEqual({entry["type"] for entry in txs}, {"BUY", "DEPOSIT"})
        self.assertEqual(tx["autoCashTransaction"]["value"], Decimal("100"))

    def test_sell_adds_cash_position(self):
        self._deposit_cash(100)
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY",
            "ticker": "AAPL",
            "name": "Apple",
            "currency": "USD",
            "quantity": 1,
            "value": 100,
            "transactionDate": "2026-05-10",
        })
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "SELL",
            "ticker": "AAPL",
            "name": "Apple",
            "currency": "USD",
            "quantity": 1,
            "value": 120,
            "transactionDate": "2026-05-11",
        })
        cash = next(h for h in portfolios.list_holdings(self.user_id, self.portfolio_id) if h.get("ticker") is None)
        self.assertEqual(cash["purchaseValue"], Decimal("120"))

    def test_rebuild_preserves_cash_when_sell_lacks_current_holding(self):
        self.tx_table.put_item({
            "userId": self.user_id,
            "sk": portfolios._transaction_sk(self.portfolio_id, "2026-05-10", "legacy-sell"),
            "transactionId": "legacy-sell",
            "portfolioId": self.portfolio_id,
            "holdingId": "aapl",
            "type": "SELL",
            "ticker": "AAPL",
            "name": "Apple",
            "currency": "USD",
            "quantity": Decimal("1"),
            "value": Decimal("120"),
            "transactionDate": "2026-05-10",
        })

        holdings = portfolios.rebuild_holdings_from_transactions(self.user_id, self.portfolio_id)

        cash = next(h for h in holdings if h.get("ticker") is None)
        self.assertEqual(cash["purchaseValue"], Decimal("120"))

    def test_buy_requires_value_when_cash_affects_trade(self):
        self._deposit_cash(100)
        with self.assertRaisesRegex(ValueError, "value is required"):
            portfolios.record_transaction(self.user_id, self.portfolio_id, {
                "type": "BUY",
                "ticker": "AAPL",
                "name": "Apple",
                "currency": "USD",
                "quantity": 1,
                "transactionDate": "2026-05-10",
            })

    def test_dividend_adds_cash_without_changing_units(self):
        self._deposit_cash(100)
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "BUY",
            "ticker": "XTB.WA",
            "name": "XTB",
            "currency": "PLN",
            "quantity": 10,
            "value": 100,
            "transactionDate": "2026-05-10",
        })
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "DIVIDEND",
            "ticker": "XTB.WA",
            "name": "XTB",
            "currency": "PLN",
            "quantity": 10,
            "price": Decimal("5.45"),
            "value": Decimal("44.58"),
            "tax": Decimal("10.42"),
            "transactionDate": "2026-05-11",
        })

        holdings = portfolios.list_holdings(self.user_id, self.portfolio_id)
        stock = next(h for h in holdings if h.get("ticker") == "XTB.WA")
        cash = next(h for h in holdings if h.get("ticker") is None)
        self.assertEqual(stock["units"], Decimal("10"))
        self.assertEqual(stock["purchaseValue"], Decimal("100"))
        self.assertEqual(cash["purchaseValue"], Decimal("44.58"))

    def test_spinoff_adds_zero_basis_holding(self):
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "SPINOFF",
            "ticker": "CRQ.WA",
            "name": "CRQUANTUM (CRQ)",
            "currency": "PLN",
            "quantity": 150,
            "price": Decimal("45.8868"),
            "value": Decimal("0"),
            "transactionDate": "2026-04-07",
        })
        holding = next(h for h in portfolios.list_holdings(self.user_id, self.portfolio_id) if h.get("ticker") == "CRQ.WA")
        self.assertEqual(holding["units"], Decimal("150"))
        self.assertEqual(holding["purchaseValue"], Decimal("0"))

    def test_extra_cost_reduces_cash_balance(self):
        self._deposit_cash(200)
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "EXTRA_COST",
            "value": Decimal("174.48"),
            "transactionDate": "2024-07-12",
            "comment": "Historical extraordinary cost",
        })
        cash = next(h for h in portfolios.list_holdings(self.user_id, self.portfolio_id) if h.get("ticker") is None)
        self.assertEqual(cash["purchaseValue"], Decimal("25.52"))

    def test_cash_adjustment_adds_cash_without_investment_total(self):
        portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "type": "CASH_ADJUSTMENT",
            "value": Decimal("1090.64"),
            "transactionDate": "2026-01-24",
            "comment": "Opening cash reconciliation",
        })

        cash = next(h for h in portfolios.list_holdings(self.user_id, self.portfolio_id) if h.get("ticker") is None)
        self.assertEqual(cash["purchaseValue"], Decimal("1090.64"))
        self.assertEqual(portfolios.calculate_investment_total(self.user_id, self.portfolio_id), Decimal("0"))

    def test_import_transaction_id_is_idempotent(self):
        self._deposit_cash(200)
        first = portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "transactionId": "hist-test-1",
            "type": "BUY",
            "ticker": "AAPL",
            "name": "Apple",
            "currency": "USD",
            "quantity": 1,
            "value": 100,
            "transactionDate": "2026-05-10",
        })
        second = portfolios.record_transaction(self.user_id, self.portfolio_id, {
            "transactionId": "hist-test-1",
            "type": "BUY",
            "ticker": "AAPL",
            "name": "Apple",
            "currency": "USD",
            "quantity": 1,
            "value": 100,
            "transactionDate": "2026-05-10",
        })
        holdings = portfolios.list_holdings(self.user_id, self.portfolio_id)
        stock = next(h for h in holdings if h.get("ticker") == "AAPL")
        self.assertEqual(stock["units"], Decimal("1"))
        self.assertEqual(first["transactionId"], second["transactionId"])


if __name__ == "__main__":
    unittest.main()
