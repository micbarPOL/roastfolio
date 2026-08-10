import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import snapshots  # noqa: E402


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, **_kwargs):
        self.items[(Item["userId"], Item["sk"])] = dict(Item)
        return {}

    def get_item(self, Key):
        item = self.items.get((Key["userId"], Key["sk"]))
        return {"Item": dict(item)} if item else {}

    def delete_item(self, Key):
        self.items.pop((Key["userId"], Key["sk"]), None)
        return {}

    def scan(self, **_kwargs):
        return {"Items": [dict(item) for item in self.items.values()]}

    def query(self, KeyConditionExpression=None, ScanIndexForward=True, Limit=None, ExclusiveStartKey=None):
        user_id = None
        prefix = None
        if hasattr(KeyConditionExpression, "_values"):
            values = KeyConditionExpression._values
            if len(values) == 2 and hasattr(values[0], "_values") and hasattr(values[1], "_values"):
                user_id = values[0]._values[1]
                prefix = values[1]._values[1]
        items = [dict(v) for (uid, sk), v in self.items.items() if uid == user_id and (prefix is None or sk.startswith(prefix))]
        items.sort(key=lambda x: x["sk"], reverse=not ScanIndexForward)
        if ExclusiveStartKey:
            start_sk = ExclusiveStartKey.get("sk")
            items = [item for item in items if item["sk"] < start_sk] if not ScanIndexForward else [item for item in items if item["sk"] > start_sk]
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

    def batch_writer(self):
        return FakeTable._BatchWriter(self)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.patches = [
            patch.object(snapshots, "_table", return_value=self.table),
            patch.object(snapshots, "_now_iso", return_value="2026-05-12T00:05:00Z"),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for p in reversed(self.patches):
            p.stop()

    def test_store_snapshot_sets_auto_ath(self):
        snapshot = snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-11",
            "portfolioValue": 1000,
            "investmentValue": 700,
            "benchmarkId": "WIG",
            "benchmarkValue": 80000,
            "dailyReturn": 1.2345,
        })
        self.assertEqual(snapshot["portfolioValue"], Decimal("1000.00"))
        self.assertEqual(snapshot["investmentValue"], Decimal("700.00"))
        ath = snapshots.get_portfolio_ath("user-1", "xtb")
        self.assertEqual(ath["athValue"], Decimal("1000.00"))
        self.assertEqual(ath["athDate"], "2026-05-11")
        self.assertEqual(ath["athSource"], "AUTO")

    def test_duplicate_snapshot_prevented(self):
        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-11",
            "portfolioValue": 1000,
        })
        with self.assertRaisesRegex(ValueError, "already exists"):
            snapshots.store_daily_snapshot("user-1", "xtb", {
                "snapshotDate": "2026-05-11",
                "portfolioValue": 1200,
            })

    def test_manual_ath_keeps_higher_value_than_today(self):
        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-10",
            "portfolioValue": 1000,
        })
        snapshots.set_manual_ath("user-1", "xtb", 1500, "2026-05-01")
        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-11",
            "portfolioValue": 1200,
        })
        ath = snapshots.get_portfolio_ath("user-1", "xtb")
        self.assertEqual(ath["athValue"], Decimal("1500.00"))
        self.assertEqual(ath["athSource"], "MANUAL")

    def test_manual_ath_is_overridden_when_today_value_is_higher(self):
        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-10",
            "portfolioValue": 1000,
        })
        snapshots.set_manual_ath("user-1", "xtb", 1100, "2026-05-01")
        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-11",
            "portfolioValue": 1200,
        })

        ath = snapshots.get_portfolio_ath("user-1", "xtb")
        self.assertEqual(ath["athValue"], Decimal("1200.00"))
        self.assertEqual(ath["athDate"], "2026-05-11")
        self.assertEqual(ath["athSource"], "AUTO")

    def test_recalculate_ath_uses_highest_snapshot(self):
        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-09",
            "portfolioValue": 1000,
        })
        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-10",
            "portfolioValue": 1250,
        })
        snapshots.set_manual_ath("user-1", "xtb", 1500, "2026-05-01")

        ath = snapshots.recalculate_ath("user-1", "xtb")
        self.assertEqual(ath["athValue"], Decimal("1250.00"))
        self.assertEqual(ath["athDate"], "2026-05-10")
        self.assertEqual(ath["athSource"], "AUTO")

    def test_snapshot_validation_rejects_negative_values(self):
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            snapshots.store_daily_snapshot("user-1", "xtb", {
                "snapshotDate": "2026-05-11",
                "portfolioValue": -1,
            })
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            snapshots.store_daily_snapshot("user-1", "xtb", {
                "snapshotDate": "2026-05-11",
                "portfolioValue": 1,
                "investmentValue": -1,
            })

    def test_calculate_portfolio_snapshot_uses_close_pairs(self):
        with patch.object(snapshots, "_get_close_pair", side_effect=[
            (Decimal("100"), Decimal("95")),
            (Decimal("4"), Decimal("4")),
        ]), patch.object(snapshots, "_get_fx_close_pair", return_value=(Decimal("4"), Decimal("4"))):
            result = snapshots.calculate_portfolio_snapshot([
                {"ticker": "AAPL", "currency": "USD", "units": 2, "purchaseValue": 500},
                {"ticker": None, "currency": "PLN", "units": 1, "purchaseValue": 100},
            ])
        self.assertEqual(result["portfolioValue"], Decimal("900.00"))
        self.assertEqual(result["dailyReturn"], Decimal("4.6512"))

    def test_warsaw_snapshot_date_uses_previous_local_day(self):
        dt = datetime(2026, 5, 12, 0, 15, tzinfo=timezone.utc)
        self.assertEqual(snapshots.warsaw_snapshot_date(dt), "2026-05-11")

    def test_scheduler_handler_reports_results(self):
        with patch.object(snapshots.db, "list_users", return_value=[{"userId": "u1"}, {"userId": "u2"}]), \
             patch.object(snapshots, "generate_user_snapshots", side_effect=[
                 {"userId": "u1", "created": 3, "skipped": 0},
                 {"userId": "u2", "created": 2, "skipped": 1},
             ]):
            result = snapshots.handler({"snapshotDate": "2026-05-11"}, None)
        self.assertTrue(result["ok"])
        self.assertEqual(result["processedUsers"], 2)
        self.assertEqual(result["snapshotDate"], "2026-05-11")

    def test_generate_user_snapshots_persists_benchmark_and_summary_ath(self):
        with patch.object(snapshots.db, "get_user", return_value={"settings": {"benchmark": "SP500"}}), \
             patch.object(snapshots.portfolios, "list_portfolios", return_value=[
                  {"portfolioId": "xtb", "name": "XTB"},
                  {"portfolioId": "cash", "name": "Cash"},
              ]), \
             patch.object(snapshots.portfolios, "list_holdings", side_effect=[
                  [{"ticker": "AAA", "currency": "PLN", "units": 1, "purchaseValue": 80}],
                  [{"ticker": None, "currency": "PLN", "units": 1, "purchaseValue": 50}],
              ]), \
             patch.object(snapshots.portfolios, "calculate_investment_total", side_effect=[
                 Decimal("120"),
                 Decimal("80"),
             ]), \
             patch.object(snapshots, "_get_close_pair", return_value=(Decimal("100"), Decimal("80"))), \
             patch.object(snapshots, "calculate_benchmark_close", return_value=Decimal("5000")):
            result = snapshots.generate_user_snapshots("user-1", snapshot_date="2026-05-11")

        self.assertEqual(result["benchmarkId"], "SP500")
        self.assertEqual(result["benchmarkValue"], Decimal("5000.00"))
        self.assertEqual(result["created"], 3)

        xtb_snapshot = snapshots.list_snapshots("user-1", "xtb")[0]
        summary_snapshot = snapshots.list_snapshots("user-1", "summary")[0]
        summary_ath = snapshots.get_portfolio_ath("user-1", "summary")

        self.assertEqual(xtb_snapshot["benchmarkId"], "SP500")
        self.assertEqual(xtb_snapshot["benchmarkValue"], Decimal("5000.00"))
        self.assertEqual(xtb_snapshot["investmentValue"], Decimal("120.00"))
        self.assertEqual(summary_snapshot["portfolioValue"], Decimal("150.00"))
        self.assertEqual(summary_snapshot["investmentValue"], Decimal("200.00"))
        self.assertEqual(summary_snapshot["benchmarkId"], "SP500")
        self.assertEqual(summary_ath["athValue"], Decimal("150.00"))
        self.assertEqual(summary_ath["athDate"], "2026-05-11")
        self.assertEqual(summary_ath["athSource"], "AUTO")

    def test_import_wallet_value_history_overwrites_portfolio_snapshots(self):
        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-09",
            "portfolioValue": 999,
            "investmentValue": 500,
        })
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="cp1250") as handle:
            handle.write("Data;Wartosc;Inwestycja\n")
            handle.write("2026-05-10;1000,50;900,25\n")
            handle.write("2026-05-11;1100,75;950,00\n")
            csv_path = handle.name
        self.addCleanup(lambda: Path(csv_path).unlink(missing_ok=True))

        result = snapshots.import_wallet_value_history("user-1", "xtb", csv_path)

        self.assertEqual(result["imported"], 2)
        rows = snapshots.list_snapshots("user-1", "xtb")
        self.assertEqual([row["snapshotDate"] for row in rows], ["2026-05-11", "2026-05-10"])
        self.assertEqual(rows[0]["portfolioValue"], Decimal("1100.75"))
        self.assertEqual(rows[0]["investmentValue"], Decimal("950.00"))
        self.assertEqual(rows[1]["portfolioValue"], Decimal("1000.50"))
        self.assertEqual(rows[1]["investmentValue"], Decimal("900.25"))
        ath = snapshots.get_portfolio_ath("user-1", "xtb")
        self.assertEqual(ath["athValue"], Decimal("1100.75"))
        self.assertEqual(ath["athDate"], "2026-05-11")

    def test_list_snapshots_returns_full_history_by_default(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for day in range(450):
            snapshots.store_daily_snapshot("user-1", "summary", {
                "snapshotDate": (start + timedelta(days=day)).strftime("%Y-%m-%d"),
                "portfolioValue": 1000 + day,
                "investmentValue": 800 + day,
            }, overwrite=True)
        rows = snapshots.list_snapshots("user-1", "summary")
        self.assertEqual(len(rows), 450)

    def test_missing_ath_rebuilds_from_highest_historical_snapshot(self):
        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-09",
            "portfolioValue": 1400,
        })
        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-10",
            "portfolioValue": 1200,
        })
        self.table.delete_item({"userId": "user-1", "sk": "PORTFOLIO#xtb#ATH"})

        snapshots.store_daily_snapshot("user-1", "xtb", {
            "snapshotDate": "2026-05-11",
            "portfolioValue": 1300,
        })

        ath = snapshots.get_portfolio_ath("user-1", "xtb")
        self.assertEqual(ath["athValue"], Decimal("1400.00"))
        self.assertEqual(ath["athDate"], "2026-05-09")
        self.assertEqual(ath["athSource"], "AUTO")

    def test_backfill_missing_xirr_treats_blank_and_nan_as_missing(self):
        self.table.put_item(Item={
            "userId": "user-1",
            "sk": "PORTFOLIO#xtb#SNAPSHOT#2026-05-09",
            "portfolioId": "xtb",
            "snapshotDate": "2026-05-09",
            "portfolioValue": Decimal("1000"),
            "xirr": Decimal("0.10"),
            "xirrVersion": snapshots._XIRR_CALCULATION_VERSION,
        })
        self.table.put_item(Item={
            "userId": "user-1",
            "sk": "PORTFOLIO#xtb#SNAPSHOT#2026-05-10",
            "portfolioId": "xtb",
            "snapshotDate": "2026-05-10",
            "portfolioValue": Decimal("1100"),
            "xirr": "",
        })
        self.table.put_item(Item={
            "userId": "user-1",
            "sk": "PORTFOLIO#summary#SNAPSHOT#2026-05-11",
            "portfolioId": "summary",
            "snapshotDate": "2026-05-11",
            "portfolioValue": Decimal("1100"),
            "xirr": Decimal("NaN"),
        })

        with patch.object(snapshots.portfolios, "list_portfolios", return_value=[{"portfolioId": "xtb"}]), \
             patch.object(snapshots, "recalculate_snapshot_xirr_from_date") as recalc_xirr:
            snapshots.backfill_missing_xirr("user-1")

        self.assertEqual(recalc_xirr.call_count, 2)
        recalc_xirr.assert_any_call("user-1", "xtb", "2026-05-10")
        recalc_xirr.assert_any_call("user-1", "summary", "2026-05-11")

    def test_backfill_missing_xirr_treats_unversioned_values_as_stale(self):
        self.table.put_item(Item={
            "userId": "user-1",
            "sk": "PORTFOLIO#xtb#SNAPSHOT#2026-05-09",
            "portfolioId": "xtb",
            "snapshotDate": "2026-05-09",
            "portfolioValue": Decimal("1000"),
            "xirr": Decimal("0.8595"),
        })
        self.table.put_item(Item={
            "userId": "user-1",
            "sk": "PORTFOLIO#xtb#SNAPSHOT#2026-05-10",
            "portfolioId": "xtb",
            "snapshotDate": "2026-05-10",
            "portfolioValue": Decimal("1100"),
            "xirr": Decimal("0.10"),
            "xirrVersion": snapshots._XIRR_CALCULATION_VERSION,
        })

        with patch.object(snapshots.portfolios, "list_portfolios", return_value=[{"portfolioId": "xtb"}]), \
             patch.object(snapshots, "recalculate_snapshot_xirr_from_date") as recalc_xirr:
            snapshots.backfill_missing_xirr("user-1")

        recalc_xirr.assert_called_once_with("user-1", "xtb", "2026-05-09")

    def test_recalculate_snapshot_xirr_uses_investment_history_without_revaluing_snapshot(self):
        self.table.put_item(Item={
            "userId": "user-1",
            "sk": "PORTFOLIO#summary#SNAPSHOT#2024-01-01",
            "portfolioId": "summary",
            "snapshotDate": "2024-01-01",
            "portfolioValue": Decimal("1000"),
            "investmentValue": Decimal("1000"),
            "xirr": Decimal("9.99"),
        })
        self.table.put_item(Item={
            "userId": "user-1",
            "sk": "PORTFOLIO#summary#SNAPSHOT#2025-01-01",
            "portfolioId": "summary",
            "snapshotDate": "2025-01-01",
            "portfolioValue": Decimal("1100"),
            "investmentValue": Decimal("1000"),
            "xirr": Decimal("9.99"),
        })

        updated = snapshots.recalculate_snapshot_xirr_from_date("user-1", "summary", "2025-01-01")

        item = self.table.get_item(Key={"userId": "user-1", "sk": "PORTFOLIO#summary#SNAPSHOT#2025-01-01"})["Item"]
        self.assertEqual(updated, 1)
        self.assertEqual(item["portfolioValue"], Decimal("1100"))
        self.assertEqual(item["investmentValue"], Decimal("1000"))
        self.assertEqual(item["xirrVersion"], snapshots._XIRR_CALCULATION_VERSION)
        self.assertAlmostEqual(float(item["xirr"]), 0.10, places=2)

    def test_build_net_cash_flow_by_date_includes_affect_cash_false_legacy_flows(self):
        flows = snapshots._build_net_cash_flow_by_date([
            {"transactionDate": "2022-01-03", "type": "DEPOSIT", "value": "1000"},
            {"transactionDate": "2022-01-04", "type": "BUY", "value": "600", "affectCash": False},
            {"transactionDate": "2022-01-05", "type": "SELL", "value": "200", "affectCash": False},
            {"transactionDate": "2022-01-06", "type": "DIVIDEND", "value": "50", "affectCash": False},
            {"transactionDate": "2022-01-07", "type": "WITHDRAWAL", "value": "100"},
        ])

        self.assertEqual(flows["2022-01-03"], Decimal("1000"))
        self.assertEqual(flows["2022-01-04"], Decimal("600"))
        self.assertEqual(flows["2022-01-05"], Decimal("-200"))
        self.assertEqual(flows["2022-01-06"], Decimal("-50"))
        self.assertEqual(flows["2022-01-07"], Decimal("-100"))

    def test_fetch_price_history_range_uses_lookback_buffer_for_weekends(self):
        with patch("yfinance.download") as mock_download:
            mock_download.return_value = None
            snapshots._fetch_price_history_range({"XTB.WA"}, set(), "2026-08-08", "2026-08-08")
            kwargs = mock_download.call_args[1]
            self.assertEqual(kwargs["start"], "2026-07-25")

    def test_wa_ticker_does_not_double_convert_fx_when_holding_currency_is_usd(self):
        with patch.object(snapshots, "_get_close_pair", return_value=(Decimal("168.00"), Decimal("168.00"))):
            result = snapshots.calculate_portfolio_snapshot([
                {"ticker": "XTB.WA", "currency": "USD", "units": 100, "purchaseValue": 5000},
            ])
            self.assertEqual(result["portfolioValue"], Decimal("16800.00"))

    def test_foreign_currency_cash_is_converted_in_calculate_portfolio_snapshot(self):
        with patch.object(snapshots, "_get_fx_close_pair", return_value=(Decimal("4.00"), Decimal("4.00"))):
            result = snapshots.calculate_portfolio_snapshot([
                {"ticker": None, "currency": "USD", "units": 1000, "purchaseValue": 1000},
            ])
            self.assertEqual(result["portfolioValue"], Decimal("4000.00"))

    def test_holdings_at_date_respects_affect_cash_false(self):
        holdings = snapshots._holdings_at_date([
            {"transactionDate": "2026-08-01", "type": "DEPOSIT", "value": "1000"},
            {"transactionDate": "2026-08-02", "type": "BUY", "value": "800", "quantity": "10", "ticker": "XTB.WA", "affectCash": False},
        ], "2026-08-05")
        cash_holding = next(h for h in holdings if h.get("holdingId") == "CASH")
        self.assertEqual(cash_holding["units"], Decimal("1000"))


if __name__ == "__main__":
    unittest.main()
