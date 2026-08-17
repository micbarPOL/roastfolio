import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import handler  # noqa: E402


class PricesPayloadTests(unittest.TestCase):
    def test_build_summary_wallet_aggregates_total_daily_and_holdings(self):
        wallets = {
            "XTB": {
                "holdings": [{
                    "name": "Apple",
                    "ticker": "AAPL",
                    "units": 1,
                    "purchaseValue": 80.0,
                    "currentValue": 100.0,
                    "dailyChangePLN": 5.0,
                    "pricePLN": 100.0,
                    "priceOriginal": 25.0,
                    "dailyChangePct": 5.0,
                    "ytdChangePct": 10.0,
                    "todayBars": [],
                    "yearBars": [],
                    "volume": 20000,
                    "avgVolume": 50000,
                    "volumeTz": "America/New_York",
                }],
                "total": 100.0,
                "dailyPLN": 5.0,
                "dailyPct": 5.26,
            },
            "IKE": {
                "holdings": [{
                    "name": "Apple",
                    "ticker": "AAPL",
                    "units": 2,
                    "purchaseValue": 160.0,
                    "currentValue": 240.0,
                    "dailyChangePLN": 12.0,
                    "pricePLN": 120.0,
                    "priceOriginal": 30.0,
                    "dailyChangePct": 5.0,
                    "ytdChangePct": 12.0,
                    "todayBars": [1],
                    "yearBars": [2],
                    "volume": 20000,
                    "avgVolume": 50000,
                    "volumeTz": "America/New_York",
                }, {
                    "name": "Cash",
                    "ticker": None,
                    "units": 1,
                    "purchaseValue": 60.0,
                    "currentValue": 60.0,
                    "dailyChangePLN": 0.0,
                    "pricePLN": 1.0,
                    "priceOriginal": 1.0,
                    "dailyChangePct": 0.0,
                    "ytdChangePct": 0.0,
                    "todayBars": [],
                    "yearBars": [],
                    "volume": 0,
                    "avgVolume": 0,
                    "volumeTz": None,
                }],
                "total": 300.0,
                "dailyPLN": 12.0,
                "dailyPct": 4.17,
            },
        }

        summary = handler._build_summary_wallet(wallets)

        self.assertEqual(summary["total"], 400.0)
        self.assertEqual(summary["dailyPLN"], 17.0)
        self.assertEqual(summary["dailyPct"], 4.4386)
        self.assertEqual(len(summary["holdings"]), 2)

        apple = next(item for item in summary["holdings"] if item["ticker"] == "AAPL")
        self.assertEqual(apple["units"], 3)
        self.assertEqual(apple["purchaseValue"], 240.0)
        self.assertEqual(apple["currentValue"], 340.0)
        self.assertEqual(apple["dailyChangePLN"], 17.0)
        self.assertEqual(apple["pricePLN"], 120.0)
        self.assertEqual(apple["todayBars"], [1])
        self.assertEqual(apple["pct"], 85.0)
        self.assertEqual(apple["volume"], 20000)
        self.assertEqual(apple["avgVolume"], 50000)
        self.assertEqual(apple["volumeTz"], "America/New_York")

    def test_prices_handler_returns_benchmark_ath_and_total_value(self):
        xtb_holdings = [{
            "name": "Apple",
            "ticker": "AAPL",
            "units": 1,
            "purchaseValue": 80.0,
            "currentValue": 100.0,
            "dailyChangePLN": 5.0,
            "pricePLN": 100.0,
            "priceOriginal": 25.0,
            "priceOriginalCurrency": "USD",
            "dailyChangePct": 5.0,
            "ytdChangePct": 10.0,
            "todayBars": [],
            "yearBars": [],
            "pct": 0,
        }]
        ike_holdings = [{
            "name": "Cash",
            "ticker": None,
            "units": 1,
            "purchaseValue": 300.0,
            "currentValue": 300.0,
            "dailyChangePLN": 0.0,
            "pricePLN": 1.0,
            "priceOriginal": 1.0,
            "priceOriginalCurrency": "PLN",
            "dailyChangePct": 0.0,
            "ytdChangePct": 0.0,
            "todayBars": [],
            "yearBars": [],
            "pct": 0,
        }]
        ath_map = {
            "summary": {"portfolioId": "summary", "athValue": 450.0, "athDate": "2026-05-10", "athSource": "AUTO"},
            "xtb-id": {"portfolioId": "xtb-id", "athValue": 120.0, "athDate": "2026-05-10", "athSource": "AUTO"},
            "ike-id": {"portfolioId": "ike-id", "athValue": 330.0, "athDate": "2026-05-10", "athSource": "MANUAL"},
        }

        with patch.object(handler, "_get_caller_identity", return_value=("user-1", "michal.bardadyn@gmail.com", "Michal")), \
             patch.object(handler, "load_s3_cache", return_value={}), \
             patch.object(handler, "save_s3_cache"), \
             patch.object(handler, "_load_wallets_from_dynamo", return_value={
                 "XTB": [{"ticker": "AAPL"}],
                 "IKE": [{"ticker": None}],
             }), \
             patch.object(handler.portfolios, "list_portfolios", return_value=[
                 {"portfolioId": "xtb-id", "name": "XTB"},
                 {"portfolioId": "ike-id", "name": "IKE"},
             ]), \
             patch.object(handler, "compute_wallet", side_effect=[
                 (xtb_holdings, 100.0, 5.0, 5.26),
                 (ike_holdings, 300.0, 0.0, 0.0),
             ]), \
             patch.object(handler.db, "get_user", return_value={"settings": {"benchmark": "SP500"}}), \
             patch.object(handler, "load_benchmark_cache", return_value={"intraday": [{"o": 100.0, "c": 101.0}, {"o": 101.0, "c": 102.0}]}), \
             patch.object(handler, "fetch_benchmark_history", return_value={
                 "daily": [],
                 "weekly": [],
                 "monthly": [],
                 "hourly": [],
                 "intraday": [{"o": 100.0, "c": 101.0}, {"o": 101.0, "c": 102.0}],
                 "updated": "2026-05-12",
             }), \
             patch.object(handler, "save_benchmark_cache"), \
             patch.object(handler, "build_widget_payload", return_value={"ok": True}), \
             patch.object(handler, "save_widget_cache"), \
             patch.object(handler.snapshots, "get_portfolio_ath", side_effect=lambda user_id, portfolio_id: ath_map.get(portfolio_id)), \
             patch.object(handler.snapshots, "list_snapshots", side_effect=AssertionError("daily change should not be derived from snapshots")):
            resp = handler.handler({"path": "/prices", "httpMethod": "GET", "headers": {}}, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])

        self.assertEqual(body["benchmarkId"], "SP500")
        self.assertEqual(body["benchmarkName"], "S&P 500")
        # Full response intentionally returns None for benchmarkDailyPct so the gauge stays
        # frozen at the intraday value set by the lite response (no second commentary flip).
        self.assertIsNone(body["benchmarkDailyPct"])
        self.assertEqual(body["portfolioTotalValue"], 400.0)
        self.assertEqual(body["portfolioDailyChangePLN"], 5.0)
        self.assertEqual(body["portfolioDailyChangePCT"], 1.2658)
        self.assertEqual(body["portfolioAth"]["athValue"], 450.0)
        self.assertEqual(body["walletAths"]["XTB"]["athValue"], 120.0)
        self.assertEqual(body["walletAths"]["IKE"]["athSource"], "MANUAL")
        self.assertEqual(body["walletPortfolioIds"]["XTB"], "xtb-id")
        self.assertEqual(body["walletPortfolioIds"]["IKE"], "ike-id")
        self.assertEqual(body["walletSummaries"]["Summary"]["total"], 400.0)
        market_ids = [item["id"] for item in body["marketCarousel"]]
        self.assertEqual(market_ids, ["WIG", "WIG20", "MWIG40", "SWIG80", "SP500", "NASDAQ", "DAX", "MSCI_WORLD"])
        self.assertTrue(all(item["sparkline"] for item in body["marketCarousel"]))

    def test_prices_handler_lite_view_skips_deferred_benchmark_history(self):
        with patch.object(handler, "_get_caller_identity", return_value=("user-1", "michal.bardadyn@gmail.com", "Michal")), \
             patch.object(handler, "load_s3_cache", return_value={}), \
             patch.object(handler, "save_s3_cache"), \
             patch.object(handler, "_load_wallets_from_dynamo", return_value={"XTB": [{"ticker": "AAPL"}]}), \
             patch.object(handler.portfolios, "list_portfolios", return_value=[{"portfolioId": "xtb-id", "name": "XTB"}]), \
             patch.object(handler, "compute_wallet", return_value=([{
                 "name": "Apple",
                 "ticker": "AAPL",
                 "units": 1,
                 "purchaseValue": 80.0,
                 "currentValue": 100.0,
                 "dailyChangePLN": 5.0,
                 "pricePLN": 100.0,
                 "priceOriginal": 25.0,
                 "priceOriginalCurrency": "USD",
                 "dailyChangePct": 5.0,
                 "ytdChangePct": 0.0,
                 "todayBars": [],
                 "yearBars": [],
                 "pct": 0,
             }], 100.0, 5.0, 5.26)) as mock_compute, \
             patch.object(handler.db, "get_user", return_value={"settings": {"benchmark": "SP500"}}), \
             patch.object(handler, "fetch_benchmark_history") as mock_fetch_benchmark_history, \
             patch.object(handler, "_compute_benchmark_daily_pct", return_value=1.23), \
             patch.object(handler, "build_widget_payload", return_value={"ok": True}), \
             patch.object(handler, "save_widget_cache"), \
             patch.object(handler.snapshots, "get_portfolio_ath", return_value={"athValue": 120.0, "athDate": "2026-05-10", "athSource": "AUTO"}):
            resp = handler.handler({
                "path": "/prices",
                "httpMethod": "GET",
                "headers": {},
                "queryStringParameters": {"view": "lite"},
            }, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["responseMode"], "lite")
        self.assertEqual(body["benchmarkDailyPct"], 1.23)
        self.assertIsNone(body["benchmarkData"])
        self.assertEqual(body["marketCarousel"], [])
        mock_fetch_benchmark_history.assert_not_called()
        self.assertEqual(mock_compute.call_args.kwargs["include_bars"], False)
        self.assertEqual(mock_compute.call_args.kwargs["use_intraday"], False)


if __name__ == "__main__":
    unittest.main()
