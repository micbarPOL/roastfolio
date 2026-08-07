import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import snapshots  # noqa: E402


def test_large_deposit_has_zero_twr_daily_return_and_stable_cumulative_return():
    rows = [
        {"date": "2026-01-01", "ending_value": Decimal("100000"), "net_cash_flow": Decimal("100000")},
        {"date": "2026-01-02", "ending_value": Decimal("200000"), "net_cash_flow": Decimal("100000")},
    ]

    series = snapshots.calculate_virtual_unit_series(rows)

    assert series[0]["daily_return"] == Decimal("0.0000")
    assert series[0]["cumulative_return_pct"] == Decimal("0.0000")
    assert series[1]["daily_return"] == Decimal("0.0000")
    assert series[1]["cumulative_return_pct"] == Decimal("0.0000")


def test_large_withdrawal_has_zero_twr_daily_return_and_preserves_prior_cumulative_return():
    rows = [
        {"date": "2026-01-01", "ending_value": Decimal("100000"), "net_cash_flow": Decimal("100000")},
        {"date": "2026-01-02", "ending_value": Decimal("110000"), "net_cash_flow": Decimal("0")},
        {"date": "2026-01-03", "ending_value": Decimal("60000"), "net_cash_flow": Decimal("-50000")},
    ]

    series = snapshots.calculate_virtual_unit_series(rows)

    assert series[1]["daily_return"] == Decimal("0.1000")
    assert series[1]["cumulative_return_pct"] == Decimal("10.0000")
    assert series[2]["daily_return"] == Decimal("0.0000")
    assert series[2]["cumulative_return_pct"] == Decimal("10.0000")
