from decimal import Decimal
from unittest.mock import MagicMock
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import wrap_generator


def test_trailing_turnover_average_with_history(monkeypatch):
    # Mock table with 3 past months of wrap data
    mock_table = MagicMock()
    def get_item(Key):
        sk = Key["SK"]
        if sk == "WRAP#MONTH#2026-08":
            return {"Item": {"trading_activity": {"turnover_pln": Decimal("30000.00")}}}
        elif sk == "WRAP#MONTH#2026-07":
            return {"Item": {"trading_activity": {"turnover_pln": Decimal("15000.00")}}}
        elif sk == "WRAP#MONTH#2026-06":
            return {"Item": {"trading_activity": {"turnover_pln": Decimal("45000.00")}}}
        return {}

    mock_table.get_item.side_effect = get_item
    monkeypatch.setattr(wrap_generator, "_wrap_table", lambda: mock_table)

    avg = wrap_generator._trailing_turnover_average("user-1", 2026, 9)
    # (30000 + 15000 + 45000) / 3 = 30000
    assert avg == Decimal("30000.00")


def test_trailing_turnover_average_no_history(monkeypatch):
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}
    monkeypatch.setattr(wrap_generator, "_wrap_table", lambda: mock_table)

    avg = wrap_generator._trailing_turnover_average("user-1", 2026, 9)
    assert avg is None
