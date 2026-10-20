"""Intraday payload metadata without any external calls."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

pytestmark = pytest.mark.full
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda"))
import handler


def test_candles_are_not_replaced_with_live_quotes():
    index = pd.date_range("2026-10-14 09:00", periods=2, freq="min", tz="Europe/Warsaw")
    frame = pd.DataFrame({"Open": [100.0, 101.0], "Close": [101.0, 102.0]}, index=index)
    ticker = SimpleNamespace(
        fast_info=SimpleNamespace(last_price=999.0, previous_close=95.0, open=100.0,
                                  last_volume=100, ten_day_average_volume=1000, timezone="Europe/Warsaw"),
        history=lambda **kwargs: frame,
        history_metadata={"currentTradingPeriod": {"regular": {"start": int(index[0].timestamp())}}},
    )
    cache = {}
    with patch.object(handler.yf, "Ticker", return_value=ticker):
        result = handler.fetch_ticker_data("TEST", bars_cache=cache)
    assert result[4] == [[int(t.timestamp() * 1000), price] for t, price in zip(index, [101.0, 102.0])]
    assert cache["TEST"]["intradayBaseline"] == {
        "openTime": int(index[0].timestamp() * 1000),
        "openPrice": 100.0,
        "previousClose": 95.0,
        "sessionStart": int(index[0].timestamp() * 1000),
    }


def test_cached_candles_keep_original_fetch_time():
    now = 1800000000
    cache = {"TEST": {
        "ts": now - 120, "date": handler.date.today().isoformat(),
        "todayBars": [[now * 1000 - 180000, 101.0]],
        "comparisonBars": [[now * 1000 - 180000, 101.0]],
        "yearBars": [[now * 1000, 100.0]], "ytdPct": 1.0,
        "intradayBaseline": {"openTime": now * 1000 - 180000, "openPrice": 100.0, "previousClose": 95.0},
    }}
    ticker = SimpleNamespace(fast_info=SimpleNamespace(last_price=999.0, previous_close=95.0,
                             open=100.0, last_volume=100, ten_day_average_volume=1000, timezone="Europe/Warsaw"))
    with patch.object(handler.yf, "Ticker", return_value=ticker), patch.object(handler._time, "time", return_value=now):
        result = handler.fetch_ticker_data("TEST", bars_cache=cache)
    assert result[4] == [[now * 1000 - 180000, 101.0]]
    assert cache["TEST"]["ts"] == now - 120


def test_wallet_exposes_unrounded_fx_and_baseline():
    baseline = {"openTime": 1000, "openPrice": 100.0, "previousClose": 95.0}
    holding = {"ticker": "TEST", "name": "Stock", "currency": "USD",
               "units": 2, "purchaseValue": 700.0}
    prices = {"TEST": (101.0, 1.0, 1.0, 0.0, [[1000, 101.0]], [], 0, 0, "America/New_York")}
    with patch.object(handler, "get_pln_rate", return_value=(4.123456, 4.0)):
        rows, *_ = handler.compute_wallet(
            None, "test", [holding], prices, {}, {}, bars_cache={"TEST": {"intradayBaseline": baseline}},
        )
    assert rows[0]["intradayFxRate"] == 4.123456
    assert rows[0]["intradayBaseline"] == baseline


def test_two_day_history_keeps_sparklines_on_latest_instrument_day():
    index = pd.DatetimeIndex([
        "2026-10-13 23:59:00+00:00", "2026-10-14 00:00:00+00:00", "2026-10-14 00:01:00+00:00",
    ])
    frame = pd.DataFrame({"Open": [95.0, 100.0, 101.0], "Close": [96.0, 101.0, 102.0]}, index=index)
    ticker = SimpleNamespace(
        fast_info=SimpleNamespace(last_price=102.0, previous_close=96.0, open=100.0,
                                  last_volume=100, ten_day_average_volume=1000, timezone="UTC"),
        history=lambda **kwargs: frame,
        history_metadata={},
    )
    cache = {}
    with patch.object(handler.yf, "Ticker", return_value=ticker):
        result = handler.fetch_ticker_data("TEST", bars_cache=cache)
    assert len(result[4]) == 2
    assert len(cache["TEST"]["comparisonBars"]) == 3
    assert cache["TEST"]["intradayBaseline"]["openTime"] == int(index[1].timestamp() * 1000)


def test_expired_history_records_new_fetch_time_even_if_baseline_unchanged():
    now = 1800000000
    index = pd.date_range("2026-10-14 09:00", periods=2, freq="min", tz="Europe/Warsaw")
    frame = pd.DataFrame({"Open": [100.0, 101.0], "Close": [101.0, 102.0]}, index=index)
    baseline = {"openTime": int(index[0].timestamp() * 1000), "openPrice": 100.0,
                "previousClose": 95.0, "sessionStart": int(index[0].timestamp() * 1000)}
    cache = {"TEST": {"ts": now - 181, "intradayBaseline": baseline, "comparisonBars": [[1000, 100.0]]}}
    ticker = SimpleNamespace(
        fast_info=SimpleNamespace(last_price=102.0, previous_close=95.0, open=100.0,
                                  last_volume=100, ten_day_average_volume=1000, timezone="Europe/Warsaw"),
        history=lambda **kwargs: frame,
        history_metadata={"currentTradingPeriod": {"regular": {"start": int(index[0].timestamp())}}},
    )
    with patch.object(handler.yf, "Ticker", return_value=ticker), patch.object(handler._time, "time", return_value=now):
        handler.fetch_ticker_data("TEST", bars_cache=cache)
    assert cache["TEST"]["intradayBaseline"] == baseline
    assert cache["TEST"]["ts"] == now


def test_session_metadata_timestamps_are_epoch_seconds():
    # yfinance >= 0.2.x converts currentTradingPeriod bounds to pandas Timestamps.
    start = pd.Timestamp("2026-10-14 09:00", tz="Europe/Warsaw")
    end = pd.Timestamp("2026-10-14 17:00", tz="Europe/Warsaw")
    metadata = {"currentTradingPeriod": {"regular": {"start": start, "end": end}}}
    assert handler._regular_session(metadata) == (int(start.timestamp()), int(end.timestamp()))
    assert handler._regular_session({"currentTradingPeriod": {"regular": {"start": 1, "end": 2}}}) == (1, 2)
    assert handler._regular_session(None) == (None, None)
    assert handler._regular_session({"currentTradingPeriod": {"regular": {"start": "x"}}}) == (None, None)


def test_timestamp_session_metadata_sets_baseline_and_serializes():
    index = pd.date_range("2026-10-14 09:00", periods=2, freq="min", tz="Europe/Warsaw")
    frame = pd.DataFrame({"Open": [100.0, 101.0], "Close": [101.0, 102.0]}, index=index)
    ticker = SimpleNamespace(
        fast_info=SimpleNamespace(last_price=102.0, previous_close=95.0, open=100.0,
                                  last_volume=100, ten_day_average_volume=1000, timezone="Europe/Warsaw"),
        history=lambda **kwargs: frame,
        history_metadata={"currentTradingPeriod": {"regular": {"start": index[0], "end": index[-1]}}},
    )
    cache = {}
    with patch.object(handler.yf, "Ticker", return_value=ticker):
        handler.fetch_ticker_data("TEST", bars_cache=cache)
    assert cache["TEST"]["intradayBaseline"]["sessionStart"] == int(index[0].timestamp() * 1000)
    assert handler._resp(200, cache)["statusCode"] == 200


def test_unserializable_response_is_reported_as_server_error():
    response = handler._resp(200, {"session": {"start": object()}})
    assert response["statusCode"] == 500
    assert "serialization" in response["body"]
