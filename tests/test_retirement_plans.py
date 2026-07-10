import sys
import unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import retirement_plans  # noqa: E402


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, **_kwargs):
        self._assert_no_float(Item)
        self.items[(Item["userId"], Item["sk"])] = dict(Item)
        return {}

    def _assert_no_float(self, value):
        if isinstance(value, float):
            raise AssertionError("Float values must be converted before DynamoDB writes")
        if isinstance(value, dict):
            for nested in value.values():
                self._assert_no_float(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                self._assert_no_float(nested)

    def get_item(self, Key):
        item = self.items.get((Key["userId"], Key["sk"]))
        return {"Item": dict(item)} if item else {}

    def delete_item(self, Key):
        self.items.pop((Key["userId"], Key["sk"]), None)
        return {}

    def query(self, KeyConditionExpression=None, ScanIndexForward=True, Limit=None, ExclusiveStartKey=None):
        user_id = None
        prefix = None
        if hasattr(KeyConditionExpression, "_values"):
            values = KeyConditionExpression._values
            if len(values) == 2 and hasattr(values[0], "_values") and hasattr(values[1], "_values"):
                user_id = values[0]._values[1]
                prefix = values[1]._values[1]
            elif len(values) == 2:
                user_id = values[1]
        items = [
            dict(value)
            for (uid, sk), value in self.items.items()
            if uid == user_id and (prefix is None or sk.startswith(prefix))
        ]
        items.sort(key=lambda item: item["sk"], reverse=not ScanIndexForward)
        if ExclusiveStartKey:
            start_sk = ExclusiveStartKey.get("sk")
            items = [item for item in items if item["sk"] > start_sk]
        if Limit is not None:
            items = items[:Limit]
        return {"Items": items}

    class _BatchWriter:
        def __init__(self, table):
            self.table = table

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def put_item(self, Item):
            self.table.put_item(Item)

        def delete_item(self, Key):
            self.table.delete_item(Key)

    def batch_writer(self):
        return FakeTable._BatchWriter(self)


class RetirementPlanTests(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.snapshot_rows = [
            {"snapshotDate": "2026-01-31", "portfolioValue": 100000, "investmentValue": 80000},
            {"snapshotDate": "2026-02-28", "portfolioValue": 102500, "investmentValue": 82000},
            {"snapshotDate": "2026-03-31", "portfolioValue": 105000, "investmentValue": 84000},
        ]
        self.patches = [
            patch.object(retirement_plans, "_table", return_value=self.table),
            patch.object(retirement_plans, "_now_iso", return_value="2026-05-14T12:00:00Z"),
            patch.object(retirement_plans.snapshots, "list_snapshots", return_value=self.snapshot_rows),
        ]
        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for patcher in reversed(self.patches):
            patcher.stop()

    def test_normalize_plan_defaults_initial_investment_to_monthly_investment(self):
        plan = retirement_plans.normalize_plan({
            "name": "Base",
            "currentAge": 35,
            "ageStartedInvesting": 28,
            "retirementAge": 65,
            "monthlyInvestment": 2500,
            "expectedYearlyReturnWorking": 7,
            "expectedYearlyReturnAfterRetirement": 4,
            "monthlyRetirementSpending": 6000,
        })
        self.assertEqual(plan["initialInvestmentAmount"], 2500)
        self.assertEqual(plan["annualFeeRate"], 0.0)
        self.assertEqual(plan["schemaVersion"], 1)

    def test_normalize_plan_accepts_annual_fee_rate(self):
        plan = retirement_plans.normalize_plan({
            "name": "Fee aware",
            "currentAge": 35,
            "ageStartedInvesting": 28,
            "retirementAge": 65,
            "monthlyInvestment": 2500,
            "expectedYearlyReturnWorking": 7,
            "expectedYearlyReturnAfterRetirement": 4,
            "monthlyRetirementSpending": 6000,
            "annualFeeRate": 0.45,
        })
        self.assertEqual(plan["annualFeeRate"], 0.45)

    def test_normalize_plan_rejects_malformed_nested_payloads(self):
        with self.assertRaisesRegex(ValueError, "Income streams entries must be objects"):
            retirement_plans.normalize_plan({
                "name": "Base",
                "currentAge": 35,
                "ageStartedInvesting": 28,
                "retirementAge": 65,
                "monthlyInvestment": 2500,
                "expectedYearlyReturnWorking": 7,
                "expectedYearlyReturnAfterRetirement": 4,
                "monthlyRetirementSpending": 6000,
                "retirementIncomeStreams": ["bad"],
            })

    def test_save_plan_persists_latest_result_and_series(self):
        saved = retirement_plans.save_plan("user-1", {
            "name": "Fire path",
            "currentAge": 35,
            "ageStartedInvesting": 25,
            "retirementAge": 60,
            "monthlyInvestment": 3000,
            "expectedYearlyReturnWorking": 7,
            "expectedYearlyReturnAfterRetirement": 4,
            "monthlyRetirementSpending": 7000,
            "initialInvestmentAmount": 3000,
            "monteCarloEnabled": False,
        })
        self.assertEqual(saved["plan"]["name"], "Fire path")
        self.assertEqual(saved["result"]["summary"]["actualStartDate"], "2026-01-31")
        self.assertEqual(saved["result"]["summary"]["currentPortfolioValue"], 105000.0)
        self.assertGreater(saved["result"]["summary"]["retirementPortfolioValue"], 105000.0)
        self.assertTrue(any(sk.startswith("PLAN#") for (_uid, sk) in self.table.items))
        self.assertTrue(any("RESULT#" in sk and "#SEG#" in sk for (_uid, sk) in self.table.items))
        plan_item = self.table.items[("user-1", f"PLAN#{saved['plan']['planId']}")]
        self.assertEqual(plan_item["itemType"], "PLAN")
        self.assertEqual(plan_item["schemaVersion"], 1)
        self.assertEqual(plan_item["planVersion"], 1)
        self.assertEqual(plan_item["createdAt"], "2026-05-14T12:00:00Z")
        self.assertEqual(plan_item["updatedAt"], "2026-05-14T12:00:00Z")
        self.assertIsInstance(plan_item["latestSummary"]["currentPortfolioValue"], Decimal)

    def test_save_plan_without_actual_history_estimates_current_value_from_investing_years(self):
        with patch.object(retirement_plans.snapshots, "list_snapshots", return_value=[]):
            saved = retirement_plans.save_plan("user-1", {
                "name": "Compounding path",
                "currentAge": 37,
                "ageStartedInvesting": 30,
                "retirementAge": 50,
                "monthlyInvestment": 6500,
                "expectedYearlyReturnWorking": 10,
                "expectedYearlyReturnAfterRetirement": 4,
                "monthlyRetirementSpending": 20000,
                "initialInvestmentAmount": 6500,
                "monteCarloEnabled": False,
            })

        self.assertGreater(saved["result"]["summary"]["currentPortfolioValue"], 600000)
        self.assertGreater(saved["result"]["summary"]["retirementPortfolioValue"], saved["result"]["summary"]["currentPortfolioValue"])
        self.assertFalse(saved["result"]["summary"]["transitionDate"].startswith("2026-"))

    def test_annual_fee_drag_reduces_projected_final_value(self):
        payload = {
            "name": "Fee compare",
            "currentAge": 37,
            "ageStartedInvesting": 30,
            "retirementAge": 60,
            "monthlyInvestment": 4000,
            "expectedYearlyReturnWorking": 8,
            "expectedYearlyReturnAfterRetirement": 4,
            "monthlyRetirementSpending": 9000,
            "initialInvestmentAmount": 4000,
            "monteCarloEnabled": False,
        }
        without_fee = retirement_plans.simulate_plan("user-1", retirement_plans.normalize_plan(payload))
        with_fee = retirement_plans.simulate_plan("user-1", retirement_plans.normalize_plan({
            **payload,
            "annualFeeRate": 0.75,
        }))
        self.assertLess(with_fee["summary"]["finalPortfolioValue"], without_fee["summary"]["finalPortfolioValue"])

    def test_monte_carlo_is_deterministic_for_same_inputs(self):
        plan = retirement_plans.normalize_plan({
            "name": "Stable bands",
            "currentAge": 37,
            "ageStartedInvesting": 30,
            "retirementAge": 60,
            "monthlyInvestment": 3000,
            "expectedYearlyReturnWorking": 8,
            "expectedYearlyReturnAfterRetirement": 4,
            "monthlyRetirementSpending": 7500,
            "initialInvestmentAmount": 3000,
            "annualFeeRate": 0.35,
            "monteCarloEnabled": True,
            "monteCarloRuns": 100,
        })
        first = retirement_plans.simulate_plan("user-1", plan)
        second = retirement_plans.simulate_plan("user-1", plan)
        self.assertEqual(first["monteCarlo"], second["monteCarlo"])

    def test_get_plan_reassembles_saved_chart_series(self):
        saved = retirement_plans.save_plan("user-1", {
            "name": "Steady plan",
            "currentAge": 40,
            "ageStartedInvesting": 30,
            "retirementAge": 65,
            "monthlyInvestment": 2000,
            "expectedYearlyReturnWorking": 6,
            "expectedYearlyReturnAfterRetirement": 3,
            "monthlyRetirementSpending": 5000,
            "initialInvestmentAmount": 2000,
            "monteCarloEnabled": False,
        })
        loaded = retirement_plans.get_plan("user-1", saved["plan"]["planId"])
        self.assertEqual(loaded["plan"]["name"], "Steady plan")
        self.assertEqual(loaded["result"]["summary"]["actualEndDate"], "2026-03-31")
        self.assertGreater(len(loaded["result"]["series"]["actual"]), 0)
        self.assertGreater(len(loaded["result"]["series"]["projectedPast"]), 0)
        self.assertGreater(len(loaded["result"]["series"]["futureFromActual"]), 0)
        self.assertGreater(len(loaded["result"]["series"]["futureFromProjected"]), 0)
        self.assertEqual(loaded["result"]["series"]["transitionMarker"][0]["label"], "Retirement")
        self.assertAlmostEqual(float(loaded["result"]["summary"]["targetAge"]), 88.6, places=1)
        self.assertEqual(loaded["plan"]["planVersion"], 1)

    def test_delete_plan_removes_all_related_items(self):
        saved = retirement_plans.save_plan("user-1", {
            "name": "Delete me",
            "currentAge": 45,
            "ageStartedInvesting": 25,
            "retirementAge": 67,
            "monthlyInvestment": 1500,
            "expectedYearlyReturnWorking": 6,
            "expectedYearlyReturnAfterRetirement": 3,
            "monthlyRetirementSpending": 4500,
            "initialInvestmentAmount": 1500,
            "monteCarloEnabled": False,
        })
        self.assertTrue(retirement_plans.delete_plan("user-1", saved["plan"]["planId"]))
        self.assertIsNone(retirement_plans.get_plan("user-1", saved["plan"]["planId"]))
        self.assertFalse(self.table.items)

    def test_updating_existing_plan_increments_plan_version(self):
        saved = retirement_plans.save_plan("user-1", {
            "name": "Versioned",
            "currentAge": 35,
            "ageStartedInvesting": 25,
            "retirementAge": 65,
            "monthlyInvestment": 2000,
            "expectedYearlyReturnWorking": 7,
            "expectedYearlyReturnAfterRetirement": 4,
            "monthlyRetirementSpending": 6000,
            "initialInvestmentAmount": 2000,
            "monteCarloEnabled": False,
        })
        updated = retirement_plans.save_plan("user-1", {
            "planId": saved["plan"]["planId"],
            "name": "Versioned",
            "currentAge": 35,
            "ageStartedInvesting": 25,
            "retirementAge": 66,
            "monthlyInvestment": 2200,
            "expectedYearlyReturnWorking": 7,
            "expectedYearlyReturnAfterRetirement": 4,
            "monthlyRetirementSpending": 6000,
            "initialInvestmentAmount": 2000,
            "monteCarloEnabled": False,
        })
        self.assertEqual(updated["plan"]["planVersion"], 2)
        self.assertEqual(retirement_plans.get_plan("user-1", saved["plan"]["planId"])["plan"]["planVersion"], 2)

    def test_user_isolation_prevents_other_user_access(self):
        saved = retirement_plans.save_plan("user-1", {
            "name": "Private",
            "currentAge": 35,
            "ageStartedInvesting": 25,
            "retirementAge": 65,
            "monthlyInvestment": 2000,
            "expectedYearlyReturnWorking": 7,
            "expectedYearlyReturnAfterRetirement": 4,
            "monthlyRetirementSpending": 6000,
            "initialInvestmentAmount": 2000,
            "monteCarloEnabled": False,
        })
        self.assertIsNone(retirement_plans.get_plan("user-2", saved["plan"]["planId"]))
        self.assertFalse(retirement_plans.delete_plan("user-2", saved["plan"]["planId"]))
        self.assertEqual(len(retirement_plans.list_plans("user-2")), 0)


if __name__ == "__main__":
    unittest.main()
