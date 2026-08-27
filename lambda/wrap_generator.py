"""Wrap generation utilities for weekly, monthly, and yearly portfolio summaries.

The Wrap concept stores a compact performance summary for each time window under a
single-table DynamoDB pattern:

  PK = USER#{userId}
  SK = WRAP#<WEEK|MONTH|YEAR>#<periodKey>

The generated document is intentionally lightweight so it can be queried quickly
for dashboard cards and roast/reporting workflows.
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

import boto3

_DATA_TABLE_NAME = os.environ.get("DATA_TABLE", "roastfolio-data")
_data_table = None


def _table():
    global _data_table
    if _data_table is None:
        _data_table = boto3.resource("dynamodb").Table(_DATA_TABLE_NAME)
    return _data_table


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


def _q6(value) -> Decimal:
    return _to_decimal(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _coerce_date(value) -> str:
    if value in (None, ""):
        raise ValueError("snapshotDate is required")
    raw = str(value).strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return raw[:10]


def wrap_period_key(period_type: str, value: str | datetime) -> str:
    """Return the canonical period key for a wrap row.

    Examples:
      WEEK  -> 2026-W31
      MONTH -> 2026-07
      YEAR  -> 2026
    """
    period = str(period_type or "").upper()
    if isinstance(value, datetime):
        d = value.date()
    else:
        d = datetime.fromisoformat(str(value)[:10]).date()

    if period == "WEEK":
        iso_year, iso_week, _ = d.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if period == "MONTH":
        return d.strftime("%Y-%m")
    if period == "YEAR":
        return d.strftime("%Y")
    raise ValueError(f"Unsupported wrap period: {period_type}")


def summarize_window(period_type: str, rows: Iterable[dict]) -> dict:
    """Compute a normalized summary from a window of daily snapshot rows."""
    ordered = sorted(
        (row for row in (rows or []) if row),
        key=lambda row: _coerce_date(row.get("snapshotDate") or row.get("date") or row.get("day")),
    )
    if not ordered:
        return {
            "periodType": str(period_type).upper(),
            "periodKey": None,
            "startDate": None,
            "endDate": None,
            "returnPct": 0.0,
            "benchmarkReturnPct": 0.0,
            "benchmarkMarginPct": 0.0,
            "carryPct": 0.0,
            "twrReturnPct": 0.0,
            "netCashFlow": 0.0,
            "windowDays": 0,
        }

    start_row = ordered[0]
    end_row = ordered[-1]
    start_date = _coerce_date(start_row.get("snapshotDate") or start_row.get("date") or start_row.get("day"))
    end_date = _coerce_date(end_row.get("snapshotDate") or end_row.get("date") or end_row.get("day"))
    period_key = wrap_period_key(period_type, end_date)

    start_value = _to_decimal(start_row.get("portfolioValue") or start_row.get("ending_value") or 0)
    end_value = _to_decimal(end_row.get("portfolioValue") or end_row.get("ending_value") or 0)
    net_cash_flow = sum(
        (_to_decimal(row.get("netCashFlow") or row.get("net_cash_flow") or 0) for row in ordered),
        Decimal("0"),
    )
    benchmark_start = _to_decimal(start_row.get("benchmarkValue") or start_row.get("benchmark_value") or 0)
    benchmark_end = _to_decimal(end_row.get("benchmarkValue") or end_row.get("benchmark_value") or 0)

    return_pct = Decimal("0")
    if start_value != 0:
        return_pct = ((end_value / start_value) - Decimal("1")) * Decimal("100")

    twr_return_pct = return_pct

    benchmark_return_pct = Decimal("0")
    if benchmark_start != 0:
        benchmark_return_pct = ((benchmark_end / benchmark_start) - Decimal("1")) * Decimal("100")

    benchmark_margin_pct = return_pct - benchmark_return_pct
    carry_pct = benchmark_return_pct

    return {
        "periodType": str(period_type).upper(),
        "periodKey": period_key,
        "startDate": start_date,
        "endDate": end_date,
        "returnPct": float(_q6(return_pct)),
        "benchmarkReturnPct": float(_q6(benchmark_return_pct)),
        "benchmarkMarginPct": float(_q6(benchmark_margin_pct)),
        "carryPct": float(_q6(carry_pct)),
        "twrReturnPct": float(_q6(twr_return_pct)),
        "netCashFlow": float(_q6(net_cash_flow)),
        "windowDays": max(len(ordered) - 1, 0),
    }


def build_wrap_document(user_id: str, period_type: str, period_key: str | None, rows: Iterable[dict]) -> dict:
    """Construct a compact Wrap document with the DynamoDB schema reserved for it."""
    ordered = sorted(
        (row for row in (rows or []) if row),
        key=lambda row: _coerce_date(row.get("snapshotDate") or row.get("date") or row.get("day")),
    )
    if not ordered:
        raise ValueError("Wrap rows cannot be empty")

    summary = summarize_window(period_type, ordered)
    resolved_key = period_key or summary["periodKey"]
    if not resolved_key:
        raise ValueError("periodKey is required")

    doc = {
        "userId": user_id,
        "pk": f"USER#{user_id}",
        "sk": f"WRAP#{str(period_type).upper()}#{resolved_key}",
        "periodType": str(period_type).upper(),
        "periodKey": str(resolved_key),
        "startDate": summary["startDate"],
        "endDate": summary["endDate"],
        "returnPct": summary["returnPct"],
        "benchmarkReturnPct": summary["benchmarkReturnPct"],
        "benchmarkMarginPct": summary["benchmarkMarginPct"],
        "carryPct": summary["carryPct"],
        "twrReturnPct": summary["twrReturnPct"],
        "netCashFlow": summary["netCashFlow"],
        "windowDays": summary["windowDays"],
        "maturityEligible": True,
    }
    return doc


def put_wrap_document(user_id: str, period_type: str, period_key: str | None, rows: Iterable[dict]) -> dict:
    doc = build_wrap_document(user_id, period_type, period_key, rows)
    _table().put_item(Item={
        "userId": user_id,
        "sk": doc["sk"],
        "pk": doc["pk"],
        **{key: value for key, value in doc.items() if key not in {"userId", "pk", "sk"}},
    })
    return doc


def list_wraps(user_id: str, period_type: str | None = None, limit: int | None = None) -> list[dict]:
    prefix = "WRAP#"
    if period_type:
        prefix = f"WRAP#{str(period_type).upper()}#"
    resp = _table().query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("userId").eq(user_id) & boto3.dynamodb.conditions.Key("sk").begins_with(prefix),
        ScanIndexForward=False,
        Limit=limit,
    )
    return resp.get("Items", [])
