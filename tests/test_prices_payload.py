import pytest

pytestmark = pytest.mark.full

import json
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd


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

    def test_build_summary_wallet_consolidates_polish_ticker_variations(self):
        wallets = {
            "IKE": {
                "holdings": [{
                    "name": "XTB",
                    "ticker": "XTB.WA",
                    "units": 500,
                    "purchaseValue": 40000.0,
                    "currentValue": 70000.0,
                    "dailyChangePLN": 1200.0,
                    "pricePLN": 140.0,
                    "priceOriginal": 140.0,
                    "priceOriginalCurrency": "PLN",
                    "dailyChangePct": 1.74,
                    "ytdChangePct": 25.0,
                    "todayBars": [140.0],
                    "yearBars": [],
                    "volume": 100000,
                    "avgVolume": 150000,
                    "volumeTz": "Europe/Warsaw",
                }],
                "total": 70000.0,
                "dailyPLN": 1200.0,
                "dailyPct": 1.74,
            },
            "XTB": {
                "holdings": [{
                    "name": "XTB",
                    "ticker": "XTB",
                    "units": 3000,
                    "purchaseValue": 400000.0,
                    "currentValue": 420000.0,
                    "dailyChangePLN": 0.0,
                    "pricePLN": 0.0,
                    "priceOriginal": 0.0,
                    "priceOriginalCurrency": "PLN",
                    "dailyChangePct": 0.0,
                    "ytdChangePct": 0.0,
                    "todayBars": [],
                    "yearBars": [],
                    "volume": 0,
                    "avgVolume": 0,
                    "volumeTz": None,
                }],
                "total": 420000.0,
                "dailyPLN": 0.0,
                "dailyPct": 0.0,
            },
        }

        summary = handler._build_summary_wallet(wallets)
        self.assertEqual(len(summary["holdings"]), 1)
        xtb = summary["holdings"][0]
        self.assertEqual(xtb["ticker"], "XTB.WA")
        self.assertEqual(xtb["name"], "XTB")
        self.assertEqual(xtb["units"], 3500)
        self.assertEqual(xtb["purchaseValue"], 440000.0)
        self.assertEqual(xtb["currentValue"], 490000.0)
        self.assertEqual(xtb["pricePLN"], 140.0)
        self.assertEqual(xtb["dailyChangePct"], 1.74)
        self.assertEqual(xtb["todayBars"], [140.0])

    def test_prices_handler_returns_benchmark_ath_and_total_value(self):
        candles = pd.DataFrame(
            {"Open": [100.0], "High": [102.0], "Low": [100.0], "Close": [102.0], "Volume": [0]},
            index=pd.date_range("2026-11-05 09:30", periods=1, tz="America/New_York"),
        )
        benchmark_ticker = SimpleNamespace(
            history=lambda **kwargs: candles,
            history_metadata={"chartPreviousClose": 98.0, "previousClose": 97.0},
        )
        bars_cache = {"^GSPC": {"ts": handler._time.time(), "todayBars": [{"o": 100.0, "c": 102.0}]}}
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

        with ExitStack() as stack:
            ticker_fetch = stack.enter_context(patch.object(handler.yf, "Ticker", return_value=benchmark_ticker))
            stack.enter_context(patch.object(handler, "load_bars_cache", return_value=bars_cache))
            stack.enter_context(patch.object(handler, "save_bars_cache"))
            stack.enter_context(patch.object(handler, "_get_caller_identity", return_value=("user-1", "michal.bardadyn@gmail.com", "Michal")))
            stack.enter_context(patch.object(handler, "load_s3_cache", return_value={}))
            stack.enter_context(patch.object(handler, "save_s3_cache"))
            stack.enter_context(patch.object(handler, "_load_wallets_from_dynamo", return_value={
                "XTB": [{"ticker": "AAPL"}], "IKE": [{"ticker": None}],
            }))
            stack.enter_context(patch.object(handler.portfolios, "list_portfolios", return_value=[
                {"portfolioId": "xtb-id", "name": "XTB"}, {"portfolioId": "ike-id", "name": "IKE"},
            ]))
            stack.enter_context(patch.object(handler, "compute_wallet", side_effect=[
                (xtb_holdings, 100.0, 5.0, 5.26), (ike_holdings, 300.0, 0.0, 0.0),
                (xtb_holdings, 100.0, 5.0, 5.26), (ike_holdings, 300.0, 0.0, 0.0),
            ]))
            stack.enter_context(patch.object(handler.db, "get_user", return_value={"settings": {"benchmark": "SP500"}}))
            stack.enter_context(patch.object(handler, "load_benchmark_cache", return_value={
                "intraday": [{"o": 100.0, "c": 101.0}, {"o": 101.0, "c": 102.0}],
            }))
            stack.enter_context(patch.object(handler, "save_benchmark_cache"))
            stack.enter_context(patch.object(handler, "build_widget_payload", return_value={"ok": True}))
            stack.enter_context(patch.object(handler, "save_widget_cache"))
            stack.enter_context(patch.object(handler.snapshots, "get_portfolio_ath", side_effect=lambda user_id, portfolio_id: ath_map.get(portfolio_id)))
            stack.enter_context(patch.object(handler.snapshots, "list_snapshots", side_effect=AssertionError("daily change should not be derived from snapshots")))
            resp = handler.handler({"path": "/prices", "httpMethod": "GET", "headers": {}}, None)
            self.assertEqual(json.loads(resp["body"])["benchmarkData"]["previousClose"], 98.0)
            self.assertEqual(bars_cache["^GSPC"]["previousClose"], 98.0)
            benchmark_fetches = [call for call in ticker_fetch.call_args_list if call.args == ("^GSPC",)]
            self.assertTrue(benchmark_fetches)
            with patch.object(handler, "_compute_benchmark_daily_pct", return_value=1.23):
                ticker_fetch.reset_mock()
                cached_resp = handler.handler({"path": "/prices", "httpMethod": "GET", "headers": {}}, None)
            self.assertEqual(json.loads(cached_resp["body"])["benchmarkData"]["previousClose"], 98.0)
            self.assertFalse([call for call in ticker_fetch.call_args_list if call.args == ("^GSPC",)])

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


@pytest.mark.parametrize("fetch_result", ["valid", "error", "corrupt"])
def test_benchmark_daily_rejects_corrupt_wig_cache_and_recovers(fetch_result):
    from datetime import date
    from io import BytesIO
    from unittest.mock import Mock

    corrupt = [{"t": "2019-07-25", "c": 284.0}, {"t": "2026-11-03", "c": 157647.9375}]
    valid = [{"t": "2026-11-02", "c": 156000.0}, {"t": "2026-11-03", "c": 157647.9375}]
    cache = {"updated": date.today().isoformat(), "daily": corrupt}
    storage = Mock()
    storage.get_object.return_value = {"Body": BytesIO(json.dumps(cache).encode())}
    ticker = Mock()
    corrupt_frame = pd.DataFrame({"Close": [row["c"] for row in corrupt]}, index=pd.to_datetime([row["t"] for row in corrupt]))
    valid_frame = pd.DataFrame({"Close": [155000.0, 156000.0, 157647.9375]},
                              index=pd.to_datetime(["2026-11-02 09:00", "2026-11-02 16:00", "2026-11-03 16:00"]).tz_localize("Europe/Warsaw"))
    ticker.history.side_effect = RuntimeError("Yahoo unavailable") if fetch_result == "error" else [
        corrupt_frame, valid_frame if fetch_result == "valid" else corrupt_frame]
    with patch.object(handler, "_require_role", return_value=("test-user", None)), \
         patch.object(handler, "CACHE_BUCKET", "test-bucket"), \
         patch.object(handler.boto3, "client", return_value=storage), \
         patch("yfinance.Ticker", return_value=ticker):
        response = handler.benchmark_daily_handler({"httpMethod": "GET", "queryStringParameters": {"benchmarkId": "WIG"}})
    if fetch_result != "valid":
        assert response["statusCode"] == 500
        storage.put_object.assert_not_called()
    else:
        assert response["statusCode"] == 200
        assert json.loads(response["body"])["daily"] == valid
        assert ticker.history.call_args_list[-1].kwargs == {"period": "2y", "interval": "60m"}
        assert json.loads(storage.put_object.call_args.kwargs["Body"])["daily"] == valid


@pytest.mark.parametrize("rows", [[], [{"t": "2026-11-03", "c": 0}],
    [{"t": "2026-11-02", "c": 100}, {"t": "2026-11-03", "c": 50000}],
    [{"t": "2026-11-02", "c": 100}, {"t": "2026-11-03", "c": float("nan")}],
])
def test_benchmark_daily_invalid_history_is_not_cacheable(rows):
    assert not handler._valid_benchmark_daily(rows)


if __name__ == "__main__":
    unittest.main()
