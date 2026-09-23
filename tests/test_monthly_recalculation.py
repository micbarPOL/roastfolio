import pytest

pytestmark = pytest.mark.full

"""No AWS/network: authenticated API, user isolation, async worker and SAM contract."""
import copy
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from boto3.dynamodb.conditions import ConditionExpressionBuilder

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lambda"))
import handler
import monthly_recalculation as jobs
import trigger_recalc


class Table:
    def __init__(self):
        self.items = {}
        self.queries = []
        self.reads = []
        for user, period in [("u1", "2020-01"), ("u1", "2020-02"), ("u2", "2020-03"), ("u1", "9999-01")]:
            self.put_item(Item={"PK": f"USER#{user}", "SK": f"WRAP#MONTH#{period}"})

    def put_item(self, Item):
        self.items[(Item["PK"], Item["SK"])] = copy.deepcopy(Item)

    def get_item(self, Key, **kwargs):
        self.reads.append(Key)
        item = self.items.get((Key["PK"], Key["SK"]))
        return {"Item": copy.deepcopy(item)} if item else {}

    def query(self, **kwargs):
        self.queries.append(kwargs)
        values = ConditionExpressionBuilder().build_expression(kwargs["KeyConditionExpression"]).attribute_value_placeholders.values()
        pk = next(value for value in values if value.startswith("USER#"))
        items = [item for (key, sk), item in sorted(self.items.items()) if key == pk and sk.startswith("WRAP#MONTH#")]
        start = next((idx + 1 for idx, row in enumerate(items) if row == kwargs.get("ExclusiveStartKey")), 0)
        page = items[start:start + 1]
        return {"Items": copy.deepcopy(page), **({"LastEvaluatedKey": page[-1]} if start + 1 < len(items) else {})}


@pytest.fixture
def backend(monkeypatch):
    table = Table()
    monkeypatch.setattr(jobs.wrap_generator, "_wrap_table", lambda: table)
    monkeypatch.setattr(jobs.wrap_generator, "selected_benchmark", lambda user: "NASDAQ")
    client = Mock()
    client.invoke.return_value = {"StatusCode": 202}
    monkeypatch.setattr(jobs.boto3, "client", lambda name: client)
    monkeypatch.setenv("MONTHLY_WRAP_FUNCTION_NAME", "dev-roastfolio-monthly-wrap")
    monkeypatch.setenv("ALLOW_DEV_AUTH_HEADER", "true")
    return table, client


def jwt(sub):
    payload = json.dumps({"sub": sub}).encode()
    header = json.dumps({"alg": "none", "typ": "JWT"}).encode()
    def b64(data):
        return __import__("base64").urlsafe_b64encode(data).decode().rstrip("=")
    return f"{b64(header)}.{b64(payload)}.sig"


def event(method="POST", body=None, user="u1", query=None):
    return {"httpMethod": method, "path": "/monthly-wraps/recalculate",
            "body": json.dumps(body if body is not None else {}),
            "queryStringParameters": query,
            "requestContext": {"authorizer": {"claims": {"sub": user}}}}


def test_api_accepts_async_job_paginates_only_callers_historical_wraps(backend):
    table, client = backend
    response = handler.handler(event(body={"consent": True}), None)
    assert response["statusCode"] == 202
    job = json.loads(response["body"])
    assert job["status"] == "accepted"
    assert job["benchmark_id"] == "NASDAQ"
    assert job["periods"] == ["2020-01", "2020-02"]
    assert job["completed_periods"] == job["failed_periods"] == []
    assert "PK" not in job and "SK" not in job
    assert len(table.queries) == 3
    invoke = client.invoke.call_args.kwargs
    assert invoke["InvocationType"] == "Event"
    assert invoke["FunctionName"] == "dev-roastfolio-monthly-wrap"
    assert json.loads(invoke["Payload"]) == {"action": "recalculate", "user_id": "u1", "job_id": job["job_id"]}


@pytest.mark.parametrize("payload", [{}, {"consent": True}, {"periods": ["2020-02"]}])
def test_consent_is_optional_and_period_subset_supported(backend, payload):
    job = jobs.create_job("u1", payload)
    assert job["periods"] == payload.get("periods", ["2020-01", "2020-02"])


@pytest.mark.parametrize("payload", [
    {"consent": False}, {"consent": "true"}, {"consent": 1}, {"user_id": "u2"},
    {"userId": "u2"}, {"user_ids": ["u2"]}, {"benchmark_id": "SP500"},
    {"action": "scheduled"}, {"periods": ["2020-03"]}, {"periods": ["9999-01"]},
    {"periods": ["2020-13"]}, {"periods": "2020-01"}, {"periods": []}, {"periods": None}, [],
])
def test_rejects_cross_user_scope_declined_consent_and_bad_payload(backend, payload):
    response = handler.handler(event(body=payload), None)
    assert response["statusCode"] == 400
    backend[1].invoke.assert_not_called()


def test_valid_bearer_header_without_authorizer_authenticates_in_dev_mode(backend):
    request = event(body={"consent": True}, user="u1")
    request.pop("requestContext")
    request["headers"] = {"Authorization": f"Bearer {jwt('u1')}"}
    response = handler.handler(request, None)
    assert response["statusCode"] == 202
    job = json.loads(response["body"])
    assert job["status"] == "accepted"
    assert job["benchmark_id"] == "NASDAQ"
    assert job["periods"] == ["2020-01", "2020-02"]
    assert backend[1].invoke.called


def test_forged_bearer_header_without_authorizer_never_authenticates(backend):
    request = event()
    request.pop("requestContext")
    request["headers"] = {"Authorization": "Bearer not-a-valid-jwt"}
    assert handler.handler(request, None)["statusCode"] == 401
    request["path"] = "/monthly-wraps"
    assert handler.handler(request, None)["statusCode"] == 401
    assert backend[0].queries == []
    backend[1].invoke.assert_not_called()


def test_status_reads_only_authenticated_partition(backend):
    job = jobs.create_job("u1", {})
    response = handler.handler(event("GET", query={"job_id": job["job_id"]}), None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "accepted"
    response = handler.handler(event("GET", user="u2", query={"job_id": job["job_id"]}), None)
    assert response["statusCode"] == 404
    assert backend[0].reads[-1] == {"PK": "USER#u2", "SK": f"WRAP#JOB#{job['job_id']}"}


def test_invalid_json_job_id_and_method(backend):
    request = event()
    request["body"] = "{bad"
    assert handler.handler(request, None)["statusCode"] == 400
    assert handler.handler(event("GET", query={"job_id": "../../other-user"}), None)["statusCode"] == 400
    assert handler.handler(event("PUT"), None)["statusCode"] == 405


def test_no_history_completes_without_invoking_worker(backend):
    job = jobs.create_job("empty-user", {})
    assert job["status"] == "completed"
    assert job["periods"] == []
    backend[1].invoke.assert_not_called()


def test_enqueue_failure_persists_failed_status_and_returns_503(backend):
    backend[1].invoke.side_effect = RuntimeError("AWS unavailable")
    assert handler.handler(event(), None)["statusCode"] == 503
    stored_jobs = [value for (_, sk), value in backend[0].items.items() if sk.startswith("WRAP#JOB#")]
    assert len(stored_jobs) == 1
    assert stored_jobs[0]["status"] == "failed"


def test_worker_scopes_user_freezes_benchmark_and_retry_skips_finished(backend, monkeypatch):
    job = jobs.create_job("u1", {})
    generate = Mock(return_value={})
    monkeypatch.setattr(jobs.wrap_generator, "generate_monthly_wrap", generate)
    monkeypatch.setattr(jobs.wrap_generator, "selected_benchmark", lambda _: "SP500")
    scan = Mock(side_effect=AssertionError("must never scan users"))
    monkeypatch.setattr(trigger_recalc.boto3, "resource", scan)
    worker_event = {"action": "recalculate", "user_id": "u1", "job_id": job["job_id"]}
    result = trigger_recalc.monthly_wrap_handler(worker_event, None)
    assert result["status"] == "completed"
    assert result["completed_periods"] == ["2020-01", "2020-02"]
    assert [call.args for call in generate.call_args_list] == [("u1", 2020, 1), ("u1", 2020, 2)]
    assert all(call.kwargs == {"benchmark_id": "NASDAQ"} for call in generate.call_args_list)
    trigger_recalc.monthly_wrap_handler(worker_event, None)
    assert generate.call_count == 2
    scan.assert_not_called()


def test_worker_failure_is_reported_but_other_months_continue(backend, monkeypatch):
    job = jobs.create_job("u1", {})
    monkeypatch.setattr(jobs.wrap_generator, "generate_monthly_wrap", Mock(side_effect=[RuntimeError("oops"), {}]))
    result = jobs.run_job({"user_id": "u1", "job_id": job["job_id"]})
    assert result["status"] == "completed_with_errors"
    assert result["failed_periods"] == ["2020-01"]
    assert result["completed_periods"] == ["2020-02"]


def test_near_timeout_continues_via_same_user_scoped_lambda(backend, monkeypatch):
    job = jobs.create_job("u1", {})
    generate = Mock()
    monkeypatch.setattr(jobs.wrap_generator, "generate_monthly_wrap", generate)
    context = Mock()
    context.get_remaining_time_in_millis.side_effect = [200000, 90000]
    result = jobs.run_job({"user_id": "u1", "job_id": job["job_id"]}, context)
    assert result["status"] == "running"
    assert result["completed_periods"] == ["2020-01"]
    assert backend[1].invoke.call_count == 2
    assert json.loads(backend[1].invoke.call_args.kwargs["Payload"])["user_id"] == "u1"
    jobs.run_job({"user_id": "u1", "job_id": job["job_id"]})
    assert generate.call_count == 2


@pytest.mark.parametrize("worker_request", [
    {}, {"action": "unknown"}, {"user_ids": ["u1"]},
    {"action": "scheduled", "user_id": "u1"},
    {"action": "scheduled", "requestContext": {}},
    {"action": "scheduled", "httpMethod": "POST"},
    {"action": "recalculate"},
    {"action": "recalculate", "user_id": "u1", "job_id": "a" * 32, "user_ids": ["u2"]},
])
def test_worker_never_falls_back_to_all_users_for_invalid_event(backend, monkeypatch, worker_request):
    all_users = Mock()
    monkeypatch.setattr(trigger_recalc, "generate_previous_month_wraps", all_users)
    with pytest.raises(ValueError):
        trigger_recalc.monthly_wrap_handler(worker_request, None)
    all_users.assert_not_called()


def test_trusted_scheduler_still_processes_all_users(monkeypatch):
    scheduled = Mock(return_value=[{"status": "ok"}, {"status": "error"}])
    monkeypatch.setattr(trigger_recalc, "generate_previous_month_wraps", scheduled)
    result = trigger_recalc.monthly_wrap_handler({"action": "scheduled", "asOfDate": "2026-09-01"}, None)
    assert result["generated"] == result["failed"] == 1
    assert scheduled.call_args.kwargs == {"force": False}

def test_monthly_wrap_handler_recalculate_snapshots(monkeypatch):
    mock_port_recalc = Mock(return_value={"updated": 10})
    mock_sum_recalc = Mock(return_value=10)
    monkeypatch.setattr(trigger_recalc.snapshots, "recalculate_portfolio_snapshots_from_date", mock_port_recalc)
    monkeypatch.setattr(trigger_recalc.snapshots, "recalculate_summary_snapshots_from_date", mock_sum_recalc)

    event = {
        "action": "recalculate_snapshots",
        "user_id": "user-test",
        "portfolio_id": "xtb",
        "from_date": "2026-08-01",
        "is_cash_only": True,
        "old_transaction": {"type": "DEPOSIT"},
        "new_transaction": {"type": "DEPOSIT"},
    }
    result = trigger_recalc.monthly_wrap_handler(event, None)
    assert result["statusCode"] == 200
    assert result["portfolioRecalculated"] == {"updated": 10}
    assert result["summaryRecalculated"] == 10
    mock_port_recalc.assert_called_once_with(
        "user-test", "xtb", "2026-08-01",
        is_cash_only=True,
        old_transaction={"type": "DEPOSIT"},
        new_transaction={"type": "DEPOSIT"},
    )
    mock_sum_recalc.assert_called_once_with("user-test", "2026-08-01")


def test_sam_routes_auth_cache_and_worker_permissions():
    import yaml
    class Loader(yaml.SafeLoader):
        pass
    Loader.add_multi_constructor("!", lambda loader, tag, node:
                                 loader.construct_scalar(node) if isinstance(node, yaml.ScalarNode)
                                 else loader.construct_sequence(node))
    resources = yaml.load((ROOT / "template.yaml").read_text(), Loader=Loader)["Resources"]
    prices = resources["PricesFunction"]["Properties"]
    for name in ("MonthlyWrapsGet", "MonthlyWrapsRecalculatePost", "MonthlyWrapsRecalculateGet", "MonthlyWrapsEmailPost"):
        auth = prices["Events"][name]["Properties"]["Auth"]
        if isinstance(auth, list):
            auth = next((item for item in auth if isinstance(item, dict) and "Authorizer" in item), {})
        assert auth.get("Authorizer") == "MonthlyWrapCognito"
    assert prices["Environment"]["Variables"]["MONTHLY_WRAP_FUNCTION_NAME"] == "MonthlyWrapFunction"
    worker = resources["MonthlyWrapFunction"]["Properties"]
    assert worker["Handler"] == "trigger_recalc.monthly_wrap_handler"
    assert "CACHE_BUCKET" in worker["Environment"]["Variables"]
    assert "s3:PutObject" in str(worker["Policies"])
    assert "lambda:InvokeFunction" in str(worker["Policies"])
    assert json.loads(resources["MonthlyWrapSchedule"]["Properties"]["Target"]["Input"]) == {"action": "scheduled"}