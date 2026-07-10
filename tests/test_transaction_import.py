import csv
import sys
import tempfile
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
import transaction_import  # noqa: E402


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


class TransactionImportTests(unittest.TestCase):
    def test_lambda_bundle_contains_canonical_history_csvs(self):
        for wallet in ("IKE", "IKZE", "XTB", "Schwab", "Binance"):
            self.assertTrue((ROOT / "lambda" / "data" / f"myfund.pl_{wallet}_historiaOperacji.csv").exists())

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
        self.data_table.put_item({
            "userId": self.user_id,
            "sk": portfolios._holding_sk(self.portfolio_id, "legacy"),
            "portfolioId": self.portfolio_id,
            "holdingId": "legacy",
            "name": "Legacy seeded holding",
            "ticker": "OLD.WA",
            "currency": "PLN",
            "units": Decimal("5"),
            "purchaseValue": Decimal("500"),
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

    def _write_csv(self, rows, prefix="tmp"):
        header = [
            "Data", "Operacja", "Konto", "Walor", "Waluta", "Liczba jednostek", "Cena", "Prowizja",
            "Podatek", "Wartość", "Stan konta po operacji", "Liczba jednostek po operacji",
            "Konto inwestycyjne", "Automatycznie dodana", "Komentarz", "",
        ]
        handle = tempfile.NamedTemporaryFile("w", encoding="cp1250", newline="", suffix=".csv", prefix=prefix, delete=False)
        with handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(header)
            writer.writerows(rows)
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def test_import_rebuilds_holdings_from_history_when_only_legacy_holdings_exist(self):
        path = self._write_csv([
            ["2026-05-11", "Dywidenda", "Gotówka", "XTB", "PLN", "10", "5.45", "-", "10.42", "44.58", "44.58", "10", "Bez konta", "Tak", "", ""],
            ["2026-05-10", "Kupno", "Gotówka", "XTB", "PLN", "10", "10.00", "0.00", "0.00", "-100.00", "0.00", "10", "Bez konta", "Nie", "", ""],
            ["2026-05-09", "Wpłata", "Gotówka", "Gotówka", "PLN", "-", "-", "-", "-", "100.00", "100.00", "", "", "Nie", "", ""],
        ])

        result = transaction_import.import_transaction_history(self.user_id, self.portfolio_id, path)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["imported"], 3)
        holdings = portfolios.list_holdings(self.user_id, self.portfolio_id)
        self.assertEqual([h for h in holdings if h["holdingId"] == "legacy"], [])
        self.assertEqual(holdings, [])
        txs = portfolios.list_transactions(self.user_id, self.portfolio_id, limit=10)
        self.assertEqual(len(txs), 3)

    def test_import_is_idempotent_for_same_csv(self):
        path = self._write_csv([
            ["2026-05-10", "Kupno", "Gotówka", "XTB", "PLN", "10", "10.00", "0.00", "0.00", "-100.00", "0.00", "10", "Bez konta", "Nie", "", ""],
            ["2026-05-09", "Wpłata", "Gotówka", "Gotówka", "PLN", "-", "-", "-", "-", "100.00", "100.00", "", "", "Nie", "", ""],
        ])

        first = transaction_import.import_transaction_history(self.user_id, self.portfolio_id, path)
        second = transaction_import.import_transaction_history(self.user_id, self.portfolio_id, path)

        self.assertEqual(first["imported"], 2)
        self.assertEqual(second["imported"], 0)
        self.assertEqual(second["skipped"], 2)
        txs = portfolios.list_transactions(self.user_id, self.portfolio_id, limit=10)
        self.assertEqual(len(txs), 2)

    def test_import_skips_existing_legacy_transaction_with_different_id(self):
        self.tx_table.put_item({
            "userId": self.user_id,
            "sk": portfolios._transaction_sk(self.portfolio_id, "2026-05-10", "legacy-uuid"),
            "transactionId": "legacy-uuid",
            "portfolioId": self.portfolio_id,
            "holdingId": "xtb",
            "type": "BUY",
            "ticker": "XTB.WA",
            "name": "XTB",
            "currency": "PLN",
            "quantity": 10,
            "price": 10,
            "value": 100,
            "commission": 0,
            "tax": 0,
            "transactionDate": "2026-05-10",
            "createdAt": "2026-05-10T00:00:00Z",
        })
        path = self._write_csv([
            ["2026-05-10", "Kupno", "Gotówka", "XTB", "PLN", "10", "10.00", "0.00", "0.00", "-100.00", "0.00", "10", "Bez konta", "Nie", "", ""],
        ])

        result = transaction_import.import_transaction_history(self.user_id, self.portfolio_id, path)

        self.assertEqual(result["imported"], 0)
        self.assertEqual(result["skipped"], 1)
        txs = portfolios.list_transactions(self.user_id, self.portfolio_id, limit=10)
        self.assertEqual(len(txs), 1)

    def test_import_tolerates_insufficient_cash_history_by_storing_rows_directly(self):
        path = self._write_csv([
            ["2022-01-26", "Kupno", "Gotówka", "TSGAMES (TEN)", "PLN", "2", "238.80", "5.00", "0.00", "-482.60", "13.89", "27", "Bez konta", "Nie", "", ""],
            ["2022-01-26", "Kupno", "Gotówka", "VOTUM (VOT)", "PLN", "40", "17.48", "5.00", "0.00", "-704.20", "496.49", "333", "Bez konta", "Nie", "", ""],
            ["2022-01-26", "Kupno", "Gotówka", "Vanguard LifeStrategy 80% Equity UCITS ETF (EUR) Accumulating (V80A.DE)", "PLN", "25", "133.078", "19.00", "0.00", "-3345.95", "1200.69", "25", "Bez konta", "Nie", "", ""],
            ["2022-01-26", "Kupno", "Gotówka", "TSGAMES (TEN)", "PLN", "6", "249.80", "5.85", "0.00", "-1504.65", "4546.64", "25", "Bez konta", "Nie", "", ""],
            ["2022-01-05", "Kupno", "Gotówka", "VOTUM (VOT)", "PLN", "35", "17.54", "5.00", "0.00", "-618.90", "5283.74", "293", "Bez konta", "Nie", "", ""],
            ["2022-01-05", "Kupno", "Gotówka", "TSGAMES (TEN)", "PLN", "2", "364.20", "5.00", "0.00", "-733.40", "5902.64", "19", "Bez konta", "Nie", "", ""],
            ["2022-01-01", "Wpłata", "Gotówka", "Gotówka", "PLN", "-", "-", "-", "-", "7317.00", "7317.00", "", "", "Nie", "", ""],
        ])

        result = transaction_import.import_transaction_history(self.user_id, self.portfolio_id, path)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["imported"], 7)
        txs = portfolios.list_transactions(self.user_id, self.portfolio_id, limit=10)
        self.assertEqual(len(txs), 7)

    def test_import_tolerates_sell_before_buy_same_day_history(self):
        path = self._write_csv([
            ["2025-05-07", "Kupno", "Gotówka", "HORTICO (HOR)", "PLN", "145", "8.88", "0.00", "0.00", "-1287.60", "13912.88", "0", "Bez konta", "Nie", "", ""],
            ["2025-05-07", "Kupno", "Gotówka", "HORTICO (HOR)", "PLN", "1355", "8.84", "0.00", "0.00", "-11978.20", "15200.48", "-145", "Bez konta", "Nie", "", ""],
            ["2025-05-07", "Sprzedaż", "Gotówka", "HORTICO (HOR)", "PLN", "-1500", "8.73", "0.00", "0.00", "13095.00", "27178.68", "-1500", "Bez konta", "Nie", "", ""],
        ])

        result = transaction_import.import_transaction_history(self.user_id, self.portfolio_id, path)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["imported"], 3)
        txs = portfolios.list_transactions(self.user_id, self.portfolio_id, limit=10)
        self.assertEqual(len(txs), 3)

    def test_import_maps_automatic_cash_movements(self):
        path = self._write_csv([
            ["2026-05-10", "Wypłata automatyczna", "Gotówka", "Gotówka", "USD", "-", "-", "-", "-", "-4.68", "0", "", "", "Tak", "Auto cash withdrawal", ""],
            ["2026-05-09", "Wpłata automatyczna", "Gotówka", "Gotówka", "USD", "-", "-", "-", "-", "6241.98", "6241.98", "", "", "Tak", "Auto cash deposit", ""],
        ])

        result = transaction_import.import_transaction_history(self.user_id, self.portfolio_id, path)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["imported"], 2)
        self.assertEqual(result["types"], {"DEPOSIT": 1, "WITHDRAWAL": 1})
        txs = portfolios.list_transactions(self.user_id, self.portfolio_id, limit=10)
        self.assertEqual([tx["type"] for tx in txs], ["WITHDRAWAL", "DEPOSIT"])

    def test_rebuild_holdings_from_history_tracks_special_assets(self):
        path = self._write_csv([
            ["2026-04-10", "Kupno", "Gotówka", "Bitcoin (BTC)", "PLN", "0.00574", "261128.0000", "0.00", "0.00", "-1498.8747", "4.40", "0.10140441", "Bez konta", "Nie", "", ""],
            ["2026-02-27", "Kupno", "Gotówka", "Bitcoin (BTC)", "PLN", "0.03477459", "241987.0000", "90.00", "0.00", "-8504.9987", "3.27", "0.09566441", "Bez konta", "Nie", "", ""],
            ["2026-02-20", "Kupno", "Gotówka", "Bitcoin (BTC)", "USD", "0.01207", "68162.8500", "33.54", "0.00", "-856.263889", "8.27", "0.06088982", "Bez konta", "Nie", "", ""],
            ["2026-02-20", "Wpłata", "Gotówka", "Gotówka", "PLN", "-", "-", "-", "-", "3000.00", "3071.98", "", "", "Nie", "", ""],
            ["2025-05-15", "Kupno", "Gotówka", "Meta Platforms, Inc. (META)", "PLN", "11", "2269.8113", "0.00", "0.00", "-24967.92", "0", "11", "Bez konta", "Nie", "", ""],
        ], prefix="myfund.pl_Binance_historiaOperacji_")

        result = transaction_import.import_transaction_history(self.user_id, self.portfolio_id, path)

        self.assertEqual(result["status"], "ok")
        rebuilt = portfolios.rebuild_holdings_from_transactions(self.user_id, self.portfolio_id)
        by_ticker = {holding.get("ticker"): holding for holding in rebuilt if holding.get("ticker")}
        self.assertAlmostEqual(float(by_ticker["BTC-USD"]["units"]), 0.05258459, places=8)
        self.assertEqual(by_ticker["BTC-USD"]["currency"], "USD")
        self.assertEqual(by_ticker["META"]["units"], Decimal("11"))
        self.assertEqual(by_ticker["META"]["currency"], "USD")

        txs = portfolios.list_transactions(self.user_id, self.portfolio_id, limit=10)
        binance_usd_buy = next(tx for tx in txs if tx["name"] == "Bitcoin (BTC)" and tx["transactionDate"] == "2026-02-20")
        self.assertEqual(binance_usd_buy["currency"], "PLN")
        self.assertAlmostEqual(float(binance_usd_buy["price"]), 244690.99893, places=5)


if __name__ == "__main__":
    unittest.main()
