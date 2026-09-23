import pytest

pytestmark = pytest.mark.full

"""Backend-only numerical, cache and schema regressions for monthly recaps."""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda"))
import handler
import wrap_generator as wraps


def snap(day, unit, value=1000):
    return {"snapshotDate": day, "unitPrice": unit, "portfolioValue": value}


def test_journey_same_baseline_as_monthly_twr_no_interpolation():
    rows = [snap("2026-08-31", 50), snap("2026-09-01", 100),
            snap("2026-09-03", 110, 9000), snap("2026-10-01", 120, 8000)]
    prices = {"2026-08-31": Decimal(80), "2026-09-01": Decimal(100),
              "2026-09-02": Decimal(105), "2026-10-01": Decimal(110)}
    result = wraps._journey(rows, date(2026, 9, 1), date(2026, 10, 1), "SP500", prices)
    assert result["points"] == [
        {"date": "2026-09-01", "portfolio_pct": 0, "benchmark_pct": 0},
        {"date": "2026-09-02", "portfolio_pct": None, "benchmark_pct": 5},
        {"date": "2026-09-03", "portfolio_pct": 10, "benchmark_pct": None},
        {"date": "2026-10-01", "portfolio_pct": 20, "benchmark_pct": 10},
    ]
    performance = wraps._monthly_performance(rows, date(2026, 9, 1), date(2026, 10, 1), Decimal(7000))
    assert result["points"][-1]["portfolio_pct"] == performance["twr_pct"]
    assert result["benchmark_return_pct"] == 10
    assert result["benchmark_currency"] == "USD"


def test_weekend_boundaries_disclose_quote_dates_without_forward_filling_points():
    rows = [snap("2026-08-01", 100), snap("2026-08-02", 101), snap("2026-09-01", 105)]
    prices = {"2026-07-31": Decimal(100), "2026-08-03": Decimal(102), "2026-09-01": Decimal(110)}
    result = wraps._journey(rows, date(2026, 8, 1), date(2026, 9, 1), "SP500", prices)
    assert result["start_date"] == "2026-08-01"
    assert result["benchmark_start_price_date"] == "2026-07-31"
    assert result["points"][0]["benchmark_pct"] is None
    assert result["points"][1]["benchmark_pct"] is None
    assert result["benchmark_return_pct"] == 10


@pytest.mark.parametrize("prices", [{}, {"2026-09-02": Decimal(100)}, {"2025-01-01": Decimal(100)}])
def test_missing_or_stale_baseline_never_becomes_zero_return(prices):
    result = wraps._journey([snap("2026-09-01", 100), snap("2026-10-01", 110)],
                            date(2026, 9, 1), date(2026, 10, 1), "SP500", prices)
    assert result["benchmark_return_pct"] is None
    assert all(point["benchmark_pct"] is None for point in result["points"])


def test_no_month_snapshots_does_not_use_a_future_month():
    rows = [snap("2026-10-01", 100), snap("2026-11-01", 110)]
    result = wraps._journey(rows, date(2026, 9, 1), date(2026, 10, 1), "WIG", {})
    assert result["points"] == []
    assert result["start_date"] is None
    assert wraps._seasonality(rows, 2027, 9, Decimal(10))["historical_years_count"] == 0


def test_journey_uses_same_last_available_endpoint_as_monthly_performance():
    rows = [snap("2026-09-02", 100), snap("2026-09-29", 90)]
    result = wraps._journey(rows, date(2026, 9, 1), date(2026, 10, 1), "WIG", {})
    assert result["start_date"] == "2026-09-02"
    assert result["end_date"] == "2026-09-29"
    assert result["points"][-1]["portfolio_pct"] == -10


def test_market_month_returns_are_calendar_close_to_close_and_keep_missing(monkeypatch):
    monkeypatch.setattr(wraps, "selected_benchmark", lambda _: "SP500")
    calls = []
    def history(bid, start, end):
        calls.append(bid)
        return {} if bid == "FTSE100" else {
            "2026-08-31": Decimal(100), "2026-09-01": Decimal(105),
            "2026-09-30": Decimal(110), "2026-10-01": Decimal(120),
        }
    monkeypatch.setattr(wraps, "_benchmark_daily", history)
    monkeypatch.setattr(wraps, "_stored_benchmark_return", lambda bid, ym: None)
    result = wraps._market_comparison("u", [snap("2026-09-01", 100), snap("2026-10-01", 110)],
                                     date(2026, 9, 1), date(2026, 10, 1))
    assert len(calls) == 6  # selected benchmark shared with market context
    assert [item["id"] for item in result["market_context"]] == list(wraps.MARKET_CONTEXT_IDS)
    assert [item["return_pct"] for item in result["market_context"]] == [10, 10, None, 10, 10, 10]
    assert result["journey"]["benchmark_return_pct"] == Decimal("14.2857")
    assert result["market_context"][0]["currency"] == "PLN"
    assert result["market_context"][2]["currency"] == "GBP"


def test_market_month_returns_fall_back_to_stored_benchmark_returns_when_daily_empty(monkeypatch):
    monkeypatch.setattr(wraps, "selected_benchmark", lambda _: "SP500")
    monkeypatch.setattr(wraps, "_benchmark_daily", lambda bid, start, end: {})
    def fake_stored(bid, ym):
        return Decimal("3.2500") if bid == "WIG" and ym == "2026-09" else None
    monkeypatch.setattr(wraps, "_stored_benchmark_return", fake_stored)
    result = wraps._market_comparison("u", [snap("2026-09-01", 100), snap("2026-10-01", 110)],
                                     date(2026, 9, 1), date(2026, 10, 1))
    wig_entry = next(item for item in result["market_context"] if item["id"] == "WIG")
    assert wig_entry["return_pct"] == Decimal("3.2500")
    sp500_entry = next(item for item in result["market_context"] if item["id"] == "SP500")
    assert sp500_entry["return_pct"] is None


def test_trading_activity_uses_settled_pln_values_filters_period_and_top_five():
    transactions = [{"type": "BUY", "value": n, "currency": "USD", "ticker": str(n),
                     "transactionDate": "2026-09-10"} for n in range(1, 7)]
    transactions += [
        {"type": "SELL", "value": -50, "ticker": "AAA", "transactionDate": "2026-09-01"},
        {"type": "DIVIDEND", "value": 10, "transactionDate": "2026-09-30"},
        {"type": "DEPOSIT", "value": 1000, "transactionDate": "2026-09-20"},
        {"type": "WITHDRAWAL", "value": 30, "transactionDate": "2026-09-20"},
        {"type": "BUY", "value": 999, "transactionDate": "2026-10-01"},
    ]
    result = wraps._trading_activity(wraps._transactions_in_period(
        transactions, date(2026, 9, 1), date(2026, 10, 1)))
    assert result["buy_total_pln"] == 21
    assert result["sell_total_pln"] == 50
    assert result["turnover_pln"] == 71
    assert result["dividend_total_pln"] == 10
    assert result["transaction_count"] == 7
    assert [tx["value_pln"] for tx in result["largest_transactions"]] == [50, 6, 5, 4, 3]
    assert result["largest_transactions"][0] == {
        "date": "2026-09-01", "type": "SELL", "ticker": "AAA", "value_pln": 50,
    }


def test_empty_trading_activity_is_real_zero_not_missing():
    result = wraps._trading_activity([])
    assert result["turnover_pln"] == result["dividend_total_pln"] == result["transaction_count"] == 0
    assert result["largest_transactions"] == []


def test_cached_daily_range_never_downloads_or_invents_missing_days(monkeypatch):
    cache = {"daily": [{"t": "2026-09-01", "c": 100}],
             "daily_ranges": [{"start": "2026-08-24", "end": "2026-10-01"}]}
    monkeypatch.setattr(handler, "load_benchmark_cache", lambda _: cache)
    fetch = Mock(side_effect=AssertionError("must use existing cache"))
    monkeypatch.setattr(handler, "fetch_benchmark_history", fetch)
    result = wraps._benchmark_daily("SP500", date(2026, 9, 1), date(2026, 10, 1))
    assert result == {"2026-09-01": Decimal(100)}
    fetch.assert_not_called()


def test_absent_daily_data_uses_shared_fetcher_and_persists_shared_cache(monkeypatch):
    cache = {"daily": [{"t": "2020-01-01", "c": 80}]}
    updated = {"daily": [*cache["daily"], {"t": "2020-02-03", "c": 100}]}
    monkeypatch.setattr(handler, "load_benchmark_cache", lambda _: cache)
    fetch, save = Mock(return_value=updated), Mock()
    monkeypatch.setattr(handler, "fetch_benchmark_history", fetch)
    monkeypatch.setattr(handler, "save_benchmark_cache", save)
    result = wraps._benchmark_daily("SP500", date(2020, 2, 1), date(2020, 3, 1))
    fetch.assert_called_once_with("SP500", "^GSPC", cache, start_date="2020-02-01", end_date="2020-03-01")
    save.assert_called_once_with("SP500", updated)
    assert result["2020-02-03"] == 100


def test_daily_fetch_supports_old_dates_and_preserves_other_cached_data(monkeypatch):
    frame = pd.DataFrame({"Open": [99, 1], "High": [102, 1], "Low": [98, 1],
                          "Close": [100, float("nan")], "Volume": [20, 0]},
                         index=pd.to_datetime(["2020-02-03", "2020-02-04"]))
    ticker = Mock()
    ticker.history.return_value = frame
    monkeypatch.setattr(handler.yf, "Ticker", lambda _: ticker)
    cache = {"daily": [{"t": "2019-01-01", "c": 80}], "hourly": ["unchanged"], "version": 2}
    result = handler.fetch_benchmark_history("SP500", "^GSPC", cache,
                                             start_date="2020-02-01", end_date="2020-03-01")
    ticker.history.assert_called_once_with(start="2020-02-01", end="2020-03-02", interval="1d", auto_adjust=True)
    assert [row["t"] for row in result["daily"]] == ["2019-01-01", "2020-02-03"]
    assert result["hourly"] == ["unchanged"]
    assert len(cache["daily"]) == 1


def test_daily_fetch_failure_retains_cache_without_fabricated_coverage(monkeypatch):
    ticker = Mock()
    ticker.history.side_effect = RuntimeError("provider unavailable")
    monkeypatch.setattr(handler.yf, "Ticker", lambda _: ticker)
    cache = {"daily": [{"t": "2020-01-01", "c": 100}]}
    assert handler.fetch_benchmark_history("SP500", "^GSPC", cache,
                                          start_date="2020-02-01", end_date="2020-03-01") == cache


def test_selected_benchmark_uses_only_requested_users_profile(monkeypatch):
    get_user = Mock(return_value={"settings": {"benchmark": "NASDAQ"}})
    monkeypatch.setattr(wraps.db, "get_user", get_user)
    assert wraps.selected_benchmark("user-1") == "NASDAQ"
    get_user.assert_called_once_with("user-1")
    get_user.return_value = {"settings": {"benchmark": "invalid"}}
    assert wraps.selected_benchmark("user-1") == wraps.db.DEFAULT_BENCHMARK


def test_wig_recap_aggregates_hourly_quotes_in_warsaw_time(monkeypatch):
    frame = pd.DataFrame({"Open": [100, 101, 103], "High": [102, 105, 106],
                          "Low": [99, 100, 102], "Close": [101, 104, 105],
                          "Volume": [10, 20, 30]}, index=pd.to_datetime([
                              "2026-07-01T07:00Z", "2026-07-01T15:00Z", "2026-07-03T15:00Z"]))
    ticker = Mock()
    ticker.history.side_effect = lambda **kw: frame if kw["interval"] == "60m" else pd.DataFrame()
    monkeypatch.setattr(handler.yf, "Ticker", lambda _: ticker)
    result = handler.fetch_benchmark_history("WIG", "WIG.WA", {},
                                             start_date="2026-07-01", end_date="2026-08-01")
    assert [(r["t"], r["c"]) for r in result["daily"]] == [("2026-07-01", 104), ("2026-07-03", 105)]
    assert result["daily"][0]["o"] == 100
    assert result["daily"][0]["v"] == 30
    assert result["daily_ranges"] == [{"start": "2026-07-01", "end": "2026-07-03"}]


def test_wig_hourly_failure_keeps_existing_cache_and_no_coverage(monkeypatch):
    ticker = Mock()
    ticker.history.side_effect = RuntimeError("unavailable")
    monkeypatch.setattr(handler.yf, "Ticker", lambda _: ticker)
    cache = {"daily": [{"t": "2026-06-30", "c": 100}]}
    assert handler.fetch_benchmark_history("WIG", "WIG.WA", cache,
                                          start_date="2026-07-01", end_date="2026-08-01") == cache