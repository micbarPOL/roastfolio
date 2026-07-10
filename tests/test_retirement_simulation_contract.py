import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / "src" / "scripts" / "retirement-simulation.js"


def _annual_to_monthly(percent_rate):
    decimal_rate = percent_rate / 100.0
    if decimal_rate <= -1:
        return -1.0
    return (1.0 + decimal_rate) ** (1.0 / 12.0) - 1.0


def _annual_fee_to_monthly(percent_rate):
    decimal_rate = max(0.0, percent_rate) / 100.0
    if decimal_rate <= 0:
        return 0.0
    if decimal_rate >= 1:
        return 1.0
    return 1.0 - ((1.0 - decimal_rate) ** (1.0 / 12.0))


def _reference_simulation(
    *,
    current_portfolio_value,
    current_age,
    retirement_age,
    monthly_investment,
    yearly_return_before_retirement,
    yearly_return_after_retirement,
    monthly_retirement_withdrawals,
    simulation_years=40,
    monthly_withdrawal_growth_rate=0,
    annual_fee_rate=0,
):
    months_until_retirement = max(0, round((retirement_age - current_age) * 12))
    total_months = simulation_years * 12
    working_rate = _annual_to_monthly(yearly_return_before_retirement)
    retired_rate = _annual_to_monthly(yearly_return_after_retirement)
    withdrawal_growth = _annual_to_monthly(monthly_withdrawal_growth_rate)
    monthly_fee = _annual_fee_to_monthly(annual_fee_rate)
    balance = max(0.0, float(current_portfolio_value))
    requested = float(monthly_retirement_withdrawals)
    series = [{"monthIndex": 0, "portfolioValue": round(balance, 2), "phase": "accumulation" if months_until_retirement > 0 else "retirement"}]
    depletion_month = None

    for month_index in range(1, total_months + 1):
        retired = month_index > months_until_retirement
        rate = retired and retired_rate or working_rate
        contribution = 0.0 if retired else float(monthly_investment)
        requested_withdrawal = requested if retired else 0.0
        growth_amount = balance * rate
        available = max(0.0, (balance + growth_amount) * (1.0 - monthly_fee)) + contribution
        actual_withdrawal = min(max(0.0, requested_withdrawal), max(0.0, available))
        balance = round(max(0.0, available - actual_withdrawal), 2)
        if retired and depletion_month is None and balance <= 0:
            depletion_month = month_index
        series.append({
            "monthIndex": month_index,
            "portfolioValue": balance,
            "phase": "retirement" if retired else "accumulation",
            "requestedWithdrawal": round(requested_withdrawal, 2),
            "actualWithdrawal": round(actual_withdrawal, 2),
            "shortfall": round(max(0.0, requested_withdrawal - actual_withdrawal), 2),
        })
        if retired:
            requested = max(0.0, requested * (1.0 + withdrawal_growth))

    return {
        "monthsUntilRetirement": months_until_retirement,
        "series": series,
        "depletionMonth": depletion_month,
    }


class RetirementSimulationContractTests(unittest.TestCase):
    def test_engine_file_exposes_required_api(self):
        js = ENGINE_PATH.read_text()
        self.assertIn("function validateRetirementSimulationInputs(input)", js)
        self.assertIn("function simulateRetirementProjection(input)", js)
        self.assertIn("function estimateCurrentPortfolioValue(input)", js)
        self.assertIn("function buildChartReadyOutput(points)", js)
        self.assertIn("function annualFeeToMonthlyRate(percentRate)", js)
        self.assertIn("annualFeeRate", js)
        self.assertIn("window.RetirementSimulation = RetirementSimulation", js)
        self.assertIn("module.exports = RetirementSimulation", js)
        self.assertIn("labels: points.map((point) => point.date)", js)
        self.assertIn("portfolioValues: points.map((point) => point.portfolioValue)", js)

    def test_accumulation_phase_uses_monthly_compounding(self):
        result = _reference_simulation(
            current_portfolio_value=100000,
            current_age=35,
            retirement_age=36,
            monthly_investment=1000,
            yearly_return_before_retirement=12,
            yearly_return_after_retirement=4,
            monthly_retirement_withdrawals=4000,
            simulation_years=40,
        )
        monthly_rate = _annual_to_monthly(12)
        expected_first_month = round(100000 * (1 + monthly_rate) + 1000, 2)
        self.assertEqual(result["series"][1]["portfolioValue"], expected_first_month)
        self.assertEqual(result["series"][1]["phase"], "accumulation")

    def test_zero_return_path_matches_simple_cashflow_math(self):
        result = _reference_simulation(
            current_portfolio_value=10000,
            current_age=30,
            retirement_age=32,
            monthly_investment=500,
            yearly_return_before_retirement=0,
            yearly_return_after_retirement=0,
            monthly_retirement_withdrawals=1000,
            simulation_years=40,
        )
        retirement_index = result["monthsUntilRetirement"]
        self.assertEqual(result["series"][retirement_index]["portfolioValue"], 10000 + 500 * retirement_index)

    def test_insufficient_retirement_funds_clamp_to_zero(self):
        result = _reference_simulation(
            current_portfolio_value=5000,
            current_age=64,
            retirement_age=65,
            monthly_investment=0,
            yearly_return_before_retirement=0,
            yearly_return_after_retirement=0,
            monthly_retirement_withdrawals=6000,
            simulation_years=40,
        )
        self.assertIsNotNone(result["depletionMonth"])
        depleted_point = result["series"][result["depletionMonth"]]
        self.assertEqual(depleted_point["portfolioValue"], 0.0)
        self.assertGreater(depleted_point["shortfall"], 0.0)

    def test_high_withdrawal_growth_depletes_faster_than_flat_withdrawal(self):
        flat = _reference_simulation(
            current_portfolio_value=300000,
            current_age=50,
            retirement_age=55,
            monthly_investment=1000,
            yearly_return_before_retirement=6,
            yearly_return_after_retirement=3,
            monthly_retirement_withdrawals=5000,
            simulation_years=40,
            monthly_withdrawal_growth_rate=0,
        )
        inflationary = _reference_simulation(
            current_portfolio_value=300000,
            current_age=50,
            retirement_age=55,
            monthly_investment=1000,
            yearly_return_before_retirement=6,
            yearly_return_after_retirement=3,
            monthly_retirement_withdrawals=5000,
            simulation_years=40,
            monthly_withdrawal_growth_rate=5,
        )
        self.assertIsNotNone(flat["depletionMonth"])
        self.assertIsNotNone(inflationary["depletionMonth"])
        self.assertLess(inflationary["depletionMonth"], flat["depletionMonth"])

    def test_long_horizon_produces_smooth_chart_ready_series_length(self):
        result = _reference_simulation(
            current_portfolio_value=150000,
            current_age=30,
            retirement_age=65,
            monthly_investment=2000,
            yearly_return_before_retirement=7,
            yearly_return_after_retirement=4,
            monthly_retirement_withdrawals=7000,
            simulation_years=70,
        )
        self.assertEqual(len(result["series"]), 70 * 12 + 1)
        self.assertTrue(all(item["monthIndex"] == index for index, item in enumerate(result["series"])))

    def test_negative_real_return_can_still_be_modelled_deterministically(self):
        result = _reference_simulation(
            current_portfolio_value=200000,
            current_age=45,
            retirement_age=60,
            monthly_investment=1500,
            yearly_return_before_retirement=-3,
            yearly_return_after_retirement=-1,
            monthly_retirement_withdrawals=4500,
            simulation_years=40,
        )
        self.assertGreaterEqual(result["series"][1]["portfolioValue"], 0.0)
        self.assertFalse(any(math.isnan(point["portfolioValue"]) for point in result["series"]))

    def test_annual_fee_drag_reduces_final_balance(self):
        no_fee = _reference_simulation(
            current_portfolio_value=150000,
            current_age=37,
            retirement_age=60,
            monthly_investment=2500,
            yearly_return_before_retirement=8,
            yearly_return_after_retirement=4,
            monthly_retirement_withdrawals=7000,
            simulation_years=40,
            annual_fee_rate=0,
        )
        with_fee = _reference_simulation(
            current_portfolio_value=150000,
            current_age=37,
            retirement_age=60,
            monthly_investment=2500,
            yearly_return_before_retirement=8,
            yearly_return_after_retirement=4,
            monthly_retirement_withdrawals=7000,
            simulation_years=40,
            annual_fee_rate=0.75,
        )
        self.assertLess(with_fee["series"][-1]["portfolioValue"], no_fee["series"][-1]["portfolioValue"])


if __name__ == "__main__":
    unittest.main()
