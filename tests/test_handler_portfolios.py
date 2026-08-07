import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import handler  # noqa: E402


class PortfolioHandlerTests(unittest.TestCase):
    def setUp(self):
        self.auth_patch = patch.object(handler, "_require_role", return_value=("user-1", None))
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)

    def _event(self, method, path, path_params=None, body=None, query=None):
        return {
            "httpMethod": method,
            "path": path,
            "pathParameters": path_params or {},
            "body": body,
            "queryStringParameters": query,
        }

    def test_get_transactions_route(self):
        with patch.object(handler.portfolios, "list_transactions", return_value=[{"transactionId": "1"}]) as mock_list:
            resp = handler.portfolios_handler(self._event(
                "GET",
                "/portfolios/xtb/transactions",
                {"portfolioId": "xtb"},
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["transactions"], [{"transactionId": "1"}])
        mock_list.assert_called_once_with("user-1", "xtb", limit=200)

    def test_get_transactions_route_honors_limit_query(self):
        with patch.object(handler.portfolios, "list_transactions", return_value=[{"transactionId": "1"}]) as mock_list:
            resp = handler.portfolios_handler(self._event(
                "GET",
                "/portfolios/xtb/transactions",
                {"portfolioId": "xtb"},
                query={"limit": "1000"},
            ))
        self.assertEqual(resp["statusCode"], 200)
        mock_list.assert_called_once_with("user-1", "xtb", limit=1000)

    def test_post_transaction_route(self):
        with patch.object(handler.portfolios, "record_transaction", return_value={"transactionId": "tx-1", "type": "BUY"}) as mock_record:
            resp = handler.portfolios_handler(self._event(
                "POST",
                "/portfolios/xtb/transactions",
                {"portfolioId": "xtb"},
                body=json.dumps({"type": "BUY", "ticker": "AAPL", "quantity": 1}),
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["transactionId"], "tx-1")
        mock_record.assert_called_once()

    def test_put_transaction_route_updates_and_recalculates_history(self):
        update_result = {
            "transaction": {"transactionId": "tx-1", "transactionDate": "2025-05-04"},
            "recalculateFrom": "2025-05-01",
        }
        with patch.object(handler.portfolios, "update_transaction", return_value=update_result) as mock_update, \
             patch.object(handler.snapshots, "recalculate_portfolio_snapshots_from_date", return_value={"updated": 4}) as mock_recalc, \
             patch.object(handler.snapshots, "recalculate_summary_snapshots_from_date", return_value=2) as mock_summary:
            resp = handler.portfolios_handler(self._event(
                "PUT",
                "/portfolios/xtb/transactions/tx-1",
                {"portfolioId": "xtb", "transactionId": "tx-1"},
                body=json.dumps({"quantity": 2, "price": 125, "transactionDate": "2025-05-04"}),
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["transaction"], {"transactionId": "tx-1", "transactionDate": "2025-05-04"})
        self.assertEqual(body["recalculated"], {"updated": 4})
        self.assertEqual(body["summaryUpdated"], 2)
        mock_update.assert_called_once_with(
            "user-1",
            "xtb",
            "tx-1",
            {"quantity": 2, "price": 125, "transactionDate": "2025-05-04"},
        )
        mock_recalc.assert_called_once_with("user-1", "xtb", "2025-05-01")
        mock_summary.assert_called_once_with("user-1", "2025-05-01")

    def test_post_transaction_invalid_json(self):
        resp = handler.portfolios_handler(self._event(
            "POST",
            "/portfolios/xtb/transactions",
            {"portfolioId": "xtb"},
            body="{bad json",
        ))
        self.assertEqual(resp["statusCode"], 400)

    def test_get_portfolio_includes_transactions_and_holdings(self):
        with patch.object(handler.portfolios, "get_portfolio", return_value={"portfolioId": "xtb", "name": "XTB"}), \
             patch.object(handler.portfolios, "list_holdings", return_value=[{"holdingId": "aapl"}]), \
             patch.object(handler.portfolio_avco, "load_portfolio_avco", return_value={
                 "active": [{
                     "holding_id": "aapl",
                     "avco": 100,
                     "realized_return": 12,
                     "unrealized_return": 25,
                     "dividends_received": 3,
                     "total_return": 40,
                     "gamification": {"badges": {}},
                 }],
                 "closed": [{
                     "holding_id": "msft",
                     "ticker": "MSFT",
                     "name": "Microsoft",
                     "status": "CLOSED",
                     "shares": 0,
                     "avco": 0,
                     "realized_return": 20,
                     "unrealized_return": 0,
                     "dividends_received": 5,
                     "total_return": 25,
                     "first_buy_date": "2025-01-01",
                     "last_sell_date": "2026-01-01",
                     "gamification": {"badges": {}},
                 }],
                 "updated_at": "2026-07-03T10:00:00Z",
             }), \
             patch.object(handler.portfolios, "list_transactions", return_value=[{"transactionId": "tx-1"}]):
            resp = handler.portfolios_handler(self._event(
                "GET",
                "/portfolios/xtb",
                {"portfolioId": "xtb"},
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["holdings"][0]["avco"], 100)
        self.assertEqual(body["holdings"][0]["totalReturn"], 40)
        self.assertEqual(body["closedHoldings"][0]["holdingId"], "msft")
        self.assertEqual(body["closedHoldings"][0]["totalReturn"], 25)
        self.assertEqual(body["closedHoldings"][0]["firstBuyDate"], "2025-01-01")
        self.assertEqual(body["transactions"], [{"transactionId": "tx-1"}])

    def test_validation_error_returns_400(self):
        with patch.object(handler.portfolios, "record_transaction", side_effect=ValueError("Insufficient quantity for SELL transaction")):
            resp = handler.portfolios_handler(self._event(
                "POST",
                "/portfolios/xtb/transactions",
                {"portfolioId": "xtb"},
                body=json.dumps({"type": "SELL", "ticker": "AAPL", "quantity": 99}),
            ))
        self.assertEqual(resp["statusCode"], 400)
        body = json.loads(resp["body"])
        self.assertIn("Insufficient quantity", body["error"])

    def test_get_snapshots_route(self):
        with patch.object(handler.snapshots, "list_snapshots", return_value=[{"snapshotDate": "2026-05-11"}]) as mock_list:
            resp = handler.portfolios_handler(self._event(
                "GET",
                "/portfolios/xtb/snapshots",
                {"portfolioId": "xtb"},
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["snapshots"], [{"snapshotDate": "2026-05-11"}])
        mock_list.assert_called_once_with("user-1", "xtb")

    def test_get_ath_route(self):
        with patch.object(handler.snapshots, "get_portfolio_ath", return_value={"athValue": 1234, "athSource": "AUTO"}) as mock_get:
            resp = handler.portfolios_handler(self._event(
                "GET",
                "/portfolios/xtb/ath",
                {"portfolioId": "xtb"},
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["ath"]["athValue"], 1234)
        mock_get.assert_called_once_with("user-1", "xtb")

    def test_put_manual_ath_route(self):
        with patch.object(handler.snapshots, "set_manual_ath", return_value={"athValue": 1500, "athSource": "MANUAL"}) as mock_set:
            resp = handler.portfolios_handler(self._event(
                "PUT",
                "/portfolios/xtb/ath",
                {"portfolioId": "xtb"},
                body=json.dumps({"athValue": 1500, "athDate": "2026-05-01"}),
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["ath"]["athSource"], "MANUAL")
        mock_set.assert_called_once_with("user-1", "xtb", 1500, "2026-05-01")

    def test_put_auto_ath_route_recalculates(self):
        with patch.object(handler.snapshots, "recalculate_ath", return_value={"athValue": 1200, "athSource": "AUTO"}) as mock_recalc:
            resp = handler.portfolios_handler(self._event(
                "PUT",
                "/portfolios/xtb/ath",
                {"portfolioId": "xtb"},
                body=json.dumps({"athSource": "AUTO"}),
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["ath"]["athSource"], "AUTO")
        mock_recalc.assert_called_once_with("user-1", "xtb")

    def test_search_handler_returns_yahoo_autocomplete_shape(self):
        fake_search = type("FakeSearch", (), {
            "quotes": [{
                "symbol": "AAPL",
                "longname": "Apple Inc.",
                "exchDisp": "NASDAQ",
                "typeDisp": "Equity",
            }]
        })()
        with patch.object(handler.yf, "Search", return_value=fake_search) as mock_search:
            resp = handler.search_handler({
                "httpMethod": "GET",
                "queryStringParameters": {"q": "aapl"},
            })
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["results"][0]["symbol"], "AAPL")
        self.assertEqual(body["results"][0]["name"], "Apple Inc.")
        self.assertEqual(body["results"][0]["exchange"], "NASDAQ")
        mock_search.assert_called_once_with("aapl", max_results=10)

    def test_migrate_removes_legacy_portfolios(self):
        import migrate  # noqa: E402

        event = {
            "httpMethod": "POST",
            "body": "{}",
            "headers": {"Authorization": "Bearer token"},
        }
        with patch.dict(migrate.os.environ, {"DATA_TABLE": "roastfolio-snapshots"}), \
             patch.object(migrate, "_get_caller_identity", return_value=("user-1", "user@example.com", "nick")), \
             patch.object(migrate.portfolios, "list_portfolios", return_value=[
                 {"portfolioId": "emerytura", "name": "Emerytura"},
                 {"portfolioId": "other", "name": "Other"},
                 {"portfolioId": "ike", "name": "IKE"},
             ]), \
             patch.object(migrate.os.path, "exists", side_effect=lambda path: path.endswith("myfund.pl_Schwab_historiaOperacji.csv") or path.endswith("myfund.pl_Binance_historiaOperacji.csv") or path.endswith("historiaOperacji.csv")), \
             patch.object(migrate.portfolios, "delete_portfolio") as mock_delete, \
             patch.object(migrate, "parse_wallet_csv", return_value=[]) as mock_parse, \
             patch.object(migrate, "import_transaction_history", return_value={"status": "ok", "imported": 0, "skipped": 0}), \
             patch.object(migrate.portfolios, "rebuild_holdings_from_transactions", return_value=[{"holdingId": "btc"}]), \
             patch.object(migrate.portfolios, "get_portfolio", side_effect=lambda _user_id, portfolio_id: {"portfolioId": "ike"} if portfolio_id == "ike" else None), \
             patch.object(migrate.portfolios, "replace_holdings_snapshots", return_value=[]), \
             patch.object(migrate.portfolios, "put_portfolio") as mock_put_portfolio:
            resp = migrate.migrate_handler(event)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["cleanedPortfolios"], ["emerytura", "other"])
        self.assertEqual(mock_delete.call_count, 2)
        self.assertEqual(mock_parse.call_count, 3)
        created_ids = [call.args[1]["portfolioId"] for call in mock_put_portfolio.call_args_list]
        self.assertEqual(created_ids, ["ikze", "xtb", "schwab", "binance"])
        self.assertIn("Schwab", body["wallets"])
        self.assertIn("Binance", body["wallets"])

    def test_search_handler_rejects_overlong_query(self):
        resp = handler.search_handler({
            "httpMethod": "GET",
            "queryStringParameters": {"q": "X" * 51},
        })
        self.assertEqual(resp["statusCode"], 400)
        body = json.loads(resp["body"])
        self.assertEqual(body["error"], "Query too long")

    def test_benchmarks_handler_includes_extended_index_catalog(self):
        resp = handler.benchmarks_handler({
            "httpMethod": "GET",
            "path": "/benchmarks",
        })
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        benchmark_ids = {item["id"] for item in body["benchmarks"]}
        self.assertIn("MWIG40", benchmark_ids)
        self.assertIn("SWIG80", benchmark_ids)
        self.assertIn("DAX", benchmark_ids)
        self.assertIn("NASDAQ", benchmark_ids)

    def test_retirement_plans_get_route(self):
        with patch.object(handler.retirement_plans, "list_plans", return_value=[{"planId": "plan-1"}]) as mock_list:
            resp = handler.retirement_plans_handler(self._event(
                "GET",
                "/retirement-plans",
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["plans"], [{"planId": "plan-1"}])
        mock_list.assert_called_once_with("user-1")

    def test_retirement_plan_put_route(self):
        with patch.object(handler.retirement_plans, "save_plan", return_value={"plan": {"planId": "plan-1"}, "result": {"runId": "run-1"}}) as mock_save:
            resp = handler.retirement_plans_handler(self._event(
                "PUT",
                "/retirement-plans",
                body=json.dumps({
                    "name": "Retirement",
                    "currentAge": 35,
                    "ageStartedInvesting": 25,
                    "retirementAge": 65,
                    "monthlyInvestment": 2000,
                    "expectedYearlyReturnWorking": 7,
                    "expectedYearlyReturnAfterRetirement": 4,
                    "monthlyRetirementSpending": 6000,
                }),
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["plan"]["planId"], "plan-1")
        mock_save.assert_called_once()

    def test_retirement_plan_get_route(self):
        with patch.object(handler.retirement_plans, "get_plan", return_value={"plan": {"planId": "plan-1"}, "result": {"summary": {}}}) as mock_get:
            resp = handler.retirement_plans_handler(self._event(
                "GET",
                "/retirement-plans/plan-1",
                {"planId": "plan-1"},
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["plan"]["planId"], "plan-1")
        mock_get.assert_called_once_with("user-1", "plan-1")

    def test_retirement_plan_simulate_route(self):
        with patch.object(handler.retirement_plans, "simulate_saved_plan", return_value={"plan": {"planId": "plan-1"}, "result": {"runId": "run-2"}}) as mock_sim:
            resp = handler.retirement_plans_handler(self._event(
                "POST",
                "/retirement-plans/plan-1/simulate",
                {"planId": "plan-1", "action": "simulate"},
                body=json.dumps({"monthlyInvestment": 2500}),
            ))
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["result"]["runId"], "run-2")
        mock_sim.assert_called_once_with("user-1", "plan-1", {"monthlyInvestment": 2500})

    def test_retirement_plan_put_invalid_json_returns_400(self):
        resp = handler.retirement_plans_handler(self._event(
            "PUT",
            "/retirement-plans",
            body="{bad",
        ))
        self.assertEqual(resp["statusCode"], 400)

    def test_retirement_plan_put_validation_error_returns_400(self):
        with patch.object(handler.retirement_plans, "save_plan", side_effect=ValueError("Plan name is required")):
            resp = handler.retirement_plans_handler(self._event(
                "PUT",
                "/retirement-plans",
                body=json.dumps({}),
            ))
        self.assertEqual(resp["statusCode"], 400)
        self.assertIn("Plan name is required", json.loads(resp["body"])["error"])

    def test_retirement_plan_handler_honors_authz_failure(self):
        with patch.object(handler, "_require_role", return_value=(None, handler._resp(403, {"error": "Insufficient permissions"}))):
            resp = handler.retirement_plans_handler(self._event(
                "GET",
                "/retirement-plans",
            ))
        self.assertEqual(resp["statusCode"], 403)
        self.assertEqual(json.loads(resp["body"])["error"], "Insufficient permissions")


if __name__ == "__main__":
    unittest.main()
