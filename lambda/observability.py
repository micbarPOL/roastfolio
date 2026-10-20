"""Low-overhead CloudWatch Embedded Metric Format instrumentation."""
from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from functools import wraps
from time import perf_counter
from typing import Any, Callable


_ENVIRONMENT = os.environ.get("APP_ENV", "unknown")
_COLD_START = True
_DYNAMODB_METHODS = {
    "delete_item", "get_item", "put_item", "query", "scan", "update_item",
}


def _emit(namespace: str, dimensions: list[list[str]], values: dict[str, tuple[float, str]], fields: dict[str, Any]) -> None:
    metrics = [{"Name": name, "Unit": unit} for name, (_, unit) in values.items()]
    payload = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{"Namespace": namespace, "Dimensions": dimensions, "Metrics": metrics}],
        },
        **fields,
        **{name: value for name, (value, _) in values.items()},
    }
    print(json.dumps(payload, separators=(",", ":"), default=str))


def normalize_route(event: dict) -> str:
    resource = event.get("resource")
    if resource:
        return str(resource)

    path = str(event.get("path") or "/")
    path = re.sub(r"/[0-9a-fA-F-]{16,}(?=/|$)", "/{id}", path)
    parts = path.strip("/").split("/")
    if len(parts) > 1 and parts[0] == "portfolios":
        parts[1] = "{portfolioId}"
    elif len(parts) > 1 and parts[0] in {"retirement-plans", "monthly-wraps"}:
        if parts[1] not in {"email", "recalculate", "send-email"}:
            parts[1] = "{id}"
    return "/" + "/".join(part for part in parts if part) if path != "/" else "/"


def observe_api(function: Callable) -> Callable:
    @wraps(function)
    def wrapped(event: dict, context: Any):
        global _COLD_START
        cold_start = _COLD_START
        _COLD_START = False
        started = perf_counter()
        status_code = 500
        error_type = ""
        try:
            response = function(event, context)
            status_code = int((response or {}).get("statusCode", 200))
            if normalize_route(event) == "/prices" and isinstance(response, dict):
                duration = (perf_counter() - started) * 1000
                body = response.get("body", "")
                body_bytes = len(body.encode("utf-8")) if isinstance(body, str) else 0
                headers = response.setdefault("headers", {})
                headers["Server-Timing"] = f"app;dur={duration:.3f}"
                headers["X-Response-Bytes"] = str(body_bytes)
                exposed = headers.get("Access-Control-Expose-Headers", "")
                headers["Access-Control-Expose-Headers"] = ", ".join(filter(None, [
                    exposed, "Server-Timing", "X-Response-Bytes",
                ]))
            return response
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            method = str(event.get("httpMethod") or "UNKNOWN").upper()
            route = normalize_route(event)
            view = (event.get("queryStringParameters") or {}).get("view", "full")
            view = view if view in {"lite", "full", "history"} else "unknown"
            dimensions = [["Environment", "Route", "Method"]]
            if route == "/prices":
                dimensions.append(["Environment", "Route", "Method", "View"])
            values = {
                "RequestCount": (1, "Count"),
                "ErrorCount": (1 if status_code >= 500 else 0, "Count"),
                "DurationMs": (round((perf_counter() - started) * 1000, 3), "Milliseconds"),
            }
            _emit(
                "Roastfolio/API",
                dimensions,
                values,
                {
                    "eventType": "api_request",
                    "Environment": _ENVIRONMENT,
                    "Route": route,
                    "Method": method,
                    "StatusCode": status_code,
                    "ErrorType": error_type,
                    "View": view if route == "/prices" else "not-applicable",
                    "ColdStart": cold_start,
                    "RequestId": getattr(context, "aws_request_id", "") if context else "",
                },
            )

    return wrapped


@contextmanager
def observe_stage(route: str, method: str, stage: str):
    started = perf_counter()
    failed = 0
    try:
        yield
    except Exception:
        failed = 1
        raise
    finally:
        _emit(
            "Roastfolio/Performance",
            [["Environment", "Route", "Stage"]],
            {
                "StageCount": (1, "Count"),
                "StageErrorCount": (failed, "Count"),
                "StageDurationMs": (round((perf_counter() - started) * 1000, 3), "Milliseconds"),
            },
            {"eventType": "api_stage", "Environment": _ENVIRONMENT, "Route": route, "Method": method, "Stage": stage, "Error": failed},
        )


class InstrumentedTable:
    """Measure DynamoDB resource calls without logging keys or item contents."""

    def __init__(self, table: Any):
        self._table = table
        self.name = getattr(table, "name", type(table).__name__)

    def __getattr__(self, name: str) -> Any:
        operation = getattr(self._table, name)
        if name not in _DYNAMODB_METHODS or not callable(operation):
            return operation

        def measured(*args: Any, **kwargs: Any):
            if getattr(self._table, "meta", None) is not None:
                kwargs.setdefault("ReturnConsumedCapacity", "TOTAL")
            started = perf_counter()
            error_count = 0
            result = None
            try:
                result = operation(*args, **kwargs)
                return result
            except Exception:
                error_count = 1
                raise
            finally:
                duration_ms = round((perf_counter() - started) * 1000, 3)
                items = result.get("Items") if isinstance(result, dict) else None
                if items is None and isinstance(result, dict):
                    items = [result["Item"]] if result.get("Item") else []
                consumed = result.get("ConsumedCapacity") if isinstance(result, dict) else None
                capacity_units = float((consumed or {}).get("CapacityUnits", 0) or 0)
                _emit(
                    "Roastfolio/Storage",
                    [["Environment", "Table", "Operation"]],
                    {
                        "OperationCount": (1, "Count"),
                        "OperationErrorCount": (error_count, "Count"),
                        "OperationDurationMs": (duration_ms, "Milliseconds"),
                        "ItemsReturned": (len(items or []), "Count"),
                        "ConsumedCapacityUnits": (capacity_units, "Count"),
                    },
                    {
                        "eventType": "dynamodb_operation",
                        "Environment": _ENVIRONMENT,
                        "Table": self.name,
                        "Operation": name,
                        "Error": error_count,
                    },
                )

        return measured


def instrument_table(table: Any) -> InstrumentedTable:
    return table if isinstance(table, InstrumentedTable) else InstrumentedTable(table)


def _observe_yahoo(feature: str, operation: str, callback: Callable[[], Any]) -> Any:
    started = perf_counter()
    error_count = 0
    try:
        return callback()
    except Exception:
        error_count = 1
        raise
    finally:
        _emit(
            "Roastfolio/Dependencies",
            [["Environment", "Provider", "Feature", "Operation"]],
            {
                "CallCount": (1, "Count"),
                "ErrorCount": (error_count, "Count"),
                "DurationMs": (round((perf_counter() - started) * 1000, 3), "Milliseconds"),
            },
            {
                "eventType": "dependency_call",
                "Environment": _ENVIRONMENT,
                "Provider": "YahooFinance",
                "Feature": feature,
                "Operation": operation,
                "Error": error_count,
            },
        )


class _ObservedFastInfo:
    def __init__(self, value: Any, feature: str):
        self._value = value
        self._feature = feature

    def get(self, key: str, *args: Any, **kwargs: Any) -> Any:
        return _observe_yahoo(self._feature, "fast_info_get", lambda: self._value.get(key, *args, **kwargs))

    def __getitem__(self, key: str) -> Any:
        return _observe_yahoo(self._feature, "fast_info_item", lambda: self._value[key])

    def __getattr__(self, name: str) -> Any:
        return _observe_yahoo(self._feature, f"fast_info_{name}", lambda: getattr(self._value, name))


class _ObservedTicker:
    def __init__(self, ticker: Any, feature: str):
        self._ticker = ticker
        self._feature = feature

    @property
    def fast_info(self) -> _ObservedFastInfo:
        value = _observe_yahoo(self._feature, "fast_info", lambda: self._ticker.fast_info)
        return _ObservedFastInfo(value, self._feature)

    @property
    def info(self) -> Any:
        return _observe_yahoo(self._feature, "info", lambda: self._ticker.info)

    def history(self, *args: Any, **kwargs: Any) -> Any:
        interval = kwargs.get("interval")
        period = kwargs.get("period")
        operation = f"history_{interval}" if interval in {"1m", "1d", "1wk", "60m", "1h"} else (
            f"history_{period}" if period in {"1d", "5d", "14d", "7d", "1y", "max"} else "history_range"
        )
        return _observe_yahoo(self._feature, operation, lambda: self._ticker.history(*args, **kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ticker, name)


class _ObservedYahooModule:
    def __init__(self, module: Any, feature: str):
        self._module = module
        self._feature = feature

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._module, name)
        if name != "Ticker":
            return value

        def ticker_factory(*args: Any, **kwargs: Any) -> _ObservedTicker:
            ticker = value(*args, **kwargs)
            return _ObservedTicker(ticker, self._feature)

        return ticker_factory


def instrument_yahoo_module(module: Any, feature: str) -> Any:
    return _ObservedYahooModule(module, feature)