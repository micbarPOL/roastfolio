import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
LAMBDA_DIR = os.path.join(ROOT, "lambda")
if LAMBDA_DIR not in sys.path:
    sys.path.insert(0, LAMBDA_DIR)

from wrap_generator import build_wrap_document, summarize_window, wrap_period_key


def test_wrap_period_key_uses_week_month_and_year_format():
    assert wrap_period_key("WEEK", "2026-07-27") == "2026-W31"
    assert wrap_period_key("MONTH", "2026-07-27") == "2026-07"
    assert wrap_period_key("YEAR", "2026-07-27") == "2026"


def test_build_wrap_document_tracks_return_and_margin():
    rows = [
        {"snapshotDate": "2026-07-20", "portfolioValue": 1000, "benchmarkValue": 900, "netCashFlow": 0, "unitPrice": 100},
        {"snapshotDate": "2026-07-26", "portfolioValue": 1120, "benchmarkValue": 980, "netCashFlow": 50, "unitPrice": 110},
    ]

    doc = build_wrap_document("user-1", "WEEK", "2026-W30", rows)

    assert doc["userId"] == "user-1"
    assert doc["sk"] == "WRAP#WEEK#2026-W30"
    assert doc["periodType"] == "WEEK"
    assert doc["periodKey"] == "2026-W30"
    assert doc["startDate"] == "2026-07-20"
    assert doc["endDate"] == "2026-07-26"
    assert doc["returnPct"] == pytest.approx(12.0)
    assert doc["benchmarkMarginPct"] == pytest.approx(3.1111111111)
    assert doc["carryPct"] == pytest.approx(8.8888888889)
    assert doc["twrReturnPct"] == pytest.approx(12.0)
    assert doc["maturityEligible"] is True


def test_summarize_window_aggregates_period_values_for_monthly_wrap():
    rows = [
        {"snapshotDate": "2026-07-01", "portfolioValue": 950, "benchmarkValue": 900, "netCashFlow": 0},
        {"snapshotDate": "2026-07-15", "portfolioValue": 1050, "benchmarkValue": 930, "netCashFlow": 50},
        {"snapshotDate": "2026-07-31", "portfolioValue": 1110, "benchmarkValue": 980, "netCashFlow": 50},
    ]

    summary = summarize_window("MONTH", rows)

    assert summary["startDate"] == "2026-07-01"
    assert summary["endDate"] == "2026-07-31"
    assert summary["returnPct"] == pytest.approx(16.8421052632)
    assert summary["netCashFlow"] == pytest.approx(100.0)
    assert summary["benchmarkMarginPct"] == pytest.approx(7.953216)
    assert summary["periodKey"] == "2026-07"
