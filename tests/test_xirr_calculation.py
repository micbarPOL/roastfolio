import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import portfolios  # noqa: E402


class XirrCalculationTests(unittest.TestCase):
    def test_calculate_xirr_returns_finite_result_for_valid_cashflows(self):
        result = portfolios.calculate_xirr([
            ("2024-01-01", -1000.0),
            ("2025-01-01", 1100.0),
        ])

        self.assertTrue(math.isfinite(result))
        self.assertAlmostEqual(result, 0.1, places=2)

    def test_calculate_xirr_rejects_non_finite_cashflows(self):
        result = portfolios.calculate_xirr([
            ("2024-01-01", -1000.0),
            ("2025-01-01", float("nan")),
        ])

        self.assertEqual(result, 0.0)

    def test_extract_cashflows_ignores_future_transactions_without_requiring_sorted_input(self):
        cashflows = portfolios.extract_cashflows_from_transactions([
            {"transactionDate": "2026-03-01", "type": "DEPOSIT", "value": 3000},
            {"transactionDate": "2026-01-01", "type": "DEPOSIT", "value": 1000},
            {"transactionDate": "2026-02-01", "type": "WITHDRAWAL", "value": 200},
        ], as_of_date="2026-02-15")

        self.assertEqual(cashflows, [
            ("2026-01-01", -1000.0),
            ("2026-02-01", 200.0),
        ])


if __name__ == "__main__":
    unittest.main()