import json
import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("observability", ROOT / "lambda" / "observability.py")
observability = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(observability)

pytestmark = pytest.mark.full


def _metric_event(output):
    return json.loads(output.strip().splitlines()[-1])


def test_api_metrics_use_normalized_route_and_do_not_log_request_data(capsys, monkeypatch):
    monkeypatch.setattr(observability, "_ENVIRONMENT", "test")

    @observability.observe_api
    def handler(event, _context):
        return {"statusCode": 200, "body": "ok"}

    handler({"path": "/portfolios/private-id/transactions", "httpMethod": "GET", "headers": {"Authorization": "secret"}}, None)

    output = capsys.readouterr().out
    metric = _metric_event(output)
    assert metric["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "Roastfolio/API"
    assert metric["_aws"]["CloudWatchMetrics"][0]["Dimensions"] == [["Environment", "Route", "Method"]]
    assert metric["Route"] == "/portfolios/{portfolioId}/transactions"
    assert metric["StatusCode"] == 200
    assert metric["RequestCount"] == 1
    assert metric["ErrorCount"] == 0
    assert "secret" not in output


def test_api_metrics_record_failures_and_reraise(capsys):
    @observability.observe_api
    def handler(_event, _context):
        raise RuntimeError("backend failure")

    with pytest.raises(RuntimeError, match="backend failure"):
        handler({"resource": "/prices", "httpMethod": "GET"}, None)

    metric = _metric_event(capsys.readouterr().out)
    assert metric["StatusCode"] == 500
    assert metric["ErrorCount"] == 1
    assert metric["ErrorType"] == "RuntimeError"
    assert "backend failure" not in json.dumps(metric)


def test_prices_exposes_server_duration_and_exact_utf8_payload_bytes(capsys):
    @observability.observe_api
    def handler(_event, _context):
        return {"statusCode": 200, "body": '{"name":"\u0141"}',
                "headers": {"Access-Control-Expose-Headers": "Existing"}}

    response = handler({"resource": "/prices", "httpMethod": "GET",
                        "queryStringParameters": {"view": "lite"}}, None)
    assert response["headers"]["Server-Timing"].startswith("app;dur=")
    assert int(response["headers"]["X-Response-Bytes"]) == len(response["body"].encode("utf-8"))
    assert response["headers"]["Access-Control-Expose-Headers"] == "Existing, Server-Timing, X-Response-Bytes"
    metric = _metric_event(capsys.readouterr().out)
    assert metric["View"] == "lite"
    assert isinstance(metric["ColdStart"], bool)
    assert metric["_aws"]["CloudWatchMetrics"][0]["Dimensions"][-1] == ["Environment", "Route", "Method", "View"]


def test_stage_metrics_include_route_stage_duration_and_failure(capsys):
    with pytest.raises(ValueError):
        with observability.observe_stage("/prices", "GET", "portfolio_load"):
            raise ValueError("private operation detail")

    metric = _metric_event(capsys.readouterr().out)
    assert metric["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "Roastfolio/Performance"
    assert metric["Route"] == "/prices"
    assert metric["Stage"] == "portfolio_load"
    assert metric["StageErrorCount"] == 1
    assert "private operation detail" not in json.dumps(metric)


def test_yahoo_ticker_metrics_measure_fast_info_and_history_without_ticker_dimension(capsys, monkeypatch):
    class FakeFastInfo:
        last_price = 12.5

        def get(self, key, default=None):
            return self.last_price if key == "last_price" else default

    class FakeTicker:
        fast_info = FakeFastInfo()

        def history(self, **_kwargs):
            return [1, 2, 3]

    class FakeYahoo:
        Ticker = lambda *_args: FakeTicker()

    monkeypatch.setattr(observability, "_ENVIRONMENT", "dev")
    ticker = observability.instrument_yahoo_module(FakeYahoo(), "prices").Ticker("PUBLIC.SYMBOL")
    assert ticker.fast_info.last_price == 12.5
    assert ticker.history(period="5d") == [1, 2, 3]

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert len(events) == 3
    assert all(event["Provider"] == "YahooFinance" and event["Feature"] == "prices" for event in events)
    assert {event["Operation"] for event in events} == {"fast_info", "fast_info_last_price", "history_5d"}
    dimensions = events[0]["_aws"]["CloudWatchMetrics"][0]["Dimensions"][0]
    assert dimensions == ["Environment", "Provider", "Feature", "Operation"]
    assert all("Ticker" not in dimension for dimension in dimensions)


def test_instrumented_table_records_duration_capacity_and_item_count(capsys):
    class FakeTable:
        name = "test-portfolios"
        meta = object()

        def query(self, **kwargs):
            assert kwargs["ReturnConsumedCapacity"] == "TOTAL"
            return {"Items": [{"sk": "private-key"}], "ConsumedCapacity": {"CapacityUnits": 2.5}}

    result = observability.instrument_table(FakeTable()).query(KeyConditionExpression="pk = :pk")

    assert len(result["Items"]) == 1
    metric = _metric_event(capsys.readouterr().out)
    assert metric["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "Roastfolio/Storage"
    assert metric["Table"] == "test-portfolios"
    assert metric["Operation"] == "query"
    assert metric["ItemsReturned"] == 1
    assert metric["ConsumedCapacityUnits"] == 2.5
    assert "private-key" not in json.dumps(metric)


def test_instrumented_table_records_storage_errors(capsys):
    class FakeTable:
        name = "test-portfolios"

        def get_item(self, **_kwargs):
            raise RuntimeError("storage unavailable")

    with pytest.raises(RuntimeError):
        observability.instrument_table(FakeTable()).get_item(Key={"userId": "private-user"})

    metric = _metric_event(capsys.readouterr().out)
    assert metric["OperationErrorCount"] == 1
    assert metric["ItemsReturned"] == 0
    assert "private-user" not in json.dumps(metric)


def test_cloudwatch_dashboard_body_is_valid_json_with_performance_and_storage_widgets():
    class CloudFormationLoader(yaml.SafeLoader):
        pass

    def construct_intrinsic(loader, _tag_suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)
        return loader.construct_mapping(node)

    CloudFormationLoader.add_multi_constructor("!", construct_intrinsic)
    template = yaml.load((ROOT / "template.yaml").read_text(), Loader=CloudFormationLoader)
    body, substitutions = template["Resources"]["ObservabilityDashboard"]["Properties"]["DashboardBody"]
    stack_values = {
        "Environment": "dev",
        "AWS::Region": "us-west-2",
        "PricesFunction": "dev-emerytura-live-prices",
        "DataTable": "dev-roastfolio-data",
        "TransactionsTable": "dev-roastfolio-transactions",
        "SnapshotsTable": "dev-roastfolio-snapshots",
        "UsersTable": "dev-roastfolio-users",
        "RetirementPlansTable": "dev-roastfolio-retirement-plans",
        "DiaryTable": "dev-roastfolio-diary",
        "ApiName": "dev-emerytura-prices-api",
    }
    replacements = {**{k: v for k, v in substitutions.items() if isinstance(v, str)}, **stack_values}
    resolved = re.sub(r"\$\{([^}]+)\}", lambda match: replacements[match.group(1)], body)
    dashboard = json.loads(resolved)
    titles = {widget["properties"].get("title", "") for widget in dashboard["widgets"]}

    assert "API duration by route (p95, ms)" in titles
    assert "DynamoDB operation latency (p95, ms)" in titles
    assert "DynamoDB table size (bytes; daily)" in titles
    assert "DynamoDB table items (daily)" in titles
    assert "Lambda concurrency, throttles, errors and duration" in titles
    assert "Yahoo Finance latency by operation (p95, ms)" in titles