import os
import sys

import pandas as pd
import pytest


sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lambda"))
from drawdown_lakes import DrawdownLakeAnalyzer


def _series(values, start="2026-01-01"):
    idx = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(values, index=idx)


def test_hwm_drawdown_and_single_lake_recovery():
    analyzer = DrawdownLakeAnalyzer()
    data = _series([100, 110, 105, 103, 111])

    result = analyzer.analyze(data)
    daily = result["daily"]

    assert daily["hwm"].tolist() == [100, 110, 110, 110, 111]
    assert daily["lakeId"].tolist() == [0, 0, 1, 1, 0]
    assert daily["isUnderwater"].tolist() == [False, False, True, True, False]
    assert daily["drawdown"].iloc[2] == pytest.approx(-4.5454545, abs=1e-6)
    assert daily["drawdown"].iloc[3] == pytest.approx(-6.3636363, abs=1e-6)

    assert len(result["lakes"]) == 1
    lake = result["lakes"][0]
    assert lake["startDate"] == "2026-01-03"
    assert lake["endDate"] == "2026-01-05"
    assert lake["isOpen"] is False
    assert lake["durationDays"] == 3
    assert lake["peakTroughDepthPct"] == pytest.approx(-6.363636, abs=1e-6)


def test_open_lake_has_open_end_and_current_duration():
    analyzer = DrawdownLakeAnalyzer()
    data = _series([100, 120, 115, 110])

    result = analyzer.analyze(data)
    assert len(result["lakes"]) == 1

    lake = result["lakes"][0]
    assert lake["startDate"] == "2026-01-03"
    assert lake["endDate"] == "Open"
    assert lake["isOpen"] is True
    assert lake["durationDays"] == 2
    assert lake["peakTroughDepthPct"] == pytest.approx(-8.333333, abs=1e-6)


def test_multiple_lakes_and_global_extremes():
    analyzer = DrawdownLakeAnalyzer()
    data = _series([100, 110, 100, 110, 105, 95, 110])

    result = analyzer.analyze(data)
    lakes = result["lakes"]

    assert [lake["lakeId"] for lake in lakes] == [1, 2]

    first = lakes[0]
    assert first["startDate"] == "2026-01-03"
    assert first["endDate"] == "2026-01-04"
    assert first["durationDays"] == 2
    assert first["peakTroughDepthPct"] == pytest.approx(-9.090909, abs=1e-6)

    second = lakes[1]
    assert second["startDate"] == "2026-01-05"
    assert second["endDate"] == "2026-01-07"
    assert second["durationDays"] == 3
    assert second["peakTroughDepthPct"] == pytest.approx(-13.636364, abs=1e-6)

    assert result["deepestLake"]["lakeId"] == 2
    assert result["widestLake"]["lakeId"] == 2


def test_dataframe_input_custom_value_column():
    analyzer = DrawdownLakeAnalyzer(value_col="portfolio_value")
    idx = pd.date_range(start="2026-03-01", periods=4, freq="D")
    frame = pd.DataFrame({"portfolio_value": [10_000, 10_500, 10_200, 10_700]}, index=idx)

    result = analyzer.analyze(frame)
    assert result["daily"]["hwm"].tolist() == [10_000, 10_500, 10_500, 10_700]
    assert len(result["lakes"]) == 1


def test_invalid_non_positive_values_raise():
    analyzer = DrawdownLakeAnalyzer()
    data = _series([100, 0, 101])

    with pytest.raises(ValueError, match="strictly positive"):
        analyzer.analyze(data)
