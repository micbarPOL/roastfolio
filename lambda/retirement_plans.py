"""
Retirement plan storage + simulation engine.

Table layout (PK=userId, SK typed string):
  PLAN#<planId>                     → plan definition + latest summary
  RESULT#<planId>#LATEST            → latest result metadata
  RESULT#<planId>#RUN#<runId>       → saved simulation run metadata
  RESULT#<planId>#SEG#<runId>#...   → chunked chart series segments
"""

from __future__ import annotations

import math
import os
import random
import re
import uuid
import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

import snapshots


_TABLE_NAME = os.environ.get("RETIREMENT_TABLE", "roastfolio-retirement-plans")
_dynamodb = None
_SEGMENT_SIZE = 180
_MAX_AGE = 100
_PLAN_SCHEMA_VERSION = 1
_RESULT_SCHEMA_VERSION = 1
_MAX_LIST_ITEMS = 24
_MAX_NAME_LENGTH = 80
_MAX_NOTES_LENGTH = 1000
_PLAN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb").Table(_TABLE_NAME)
    return _dynamodb


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _to_float(value, default=0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _to_bool(value, default=False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug[:48] or "retirement-plan"


def _new_plan_id(name: str) -> str:
    return f"{_slugify(name)}-{uuid.uuid4().hex[:8]}"


def _plan_sk(plan_id: str) -> str:
    return f"PLAN#{plan_id}"


def _latest_sk(plan_id: str) -> str:
    return f"RESULT#{plan_id}#LATEST"


def _run_sk(plan_id: str, run_id: str) -> str:
    return f"RESULT#{plan_id}#RUN#{run_id}"


def _segment_sk(plan_id: str, run_id: str, series_key: str, index: int) -> str:
    return f"RESULT#{plan_id}#SEG#{run_id}#{series_key}#{index:03d}"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _date_to_str(value: date | None) -> str | None:
    return value.isoformat() if isinstance(value, date) else None


def _months_between(start: date, end: date) -> int:
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    while months > 0 and _add_months(start, months) > end:
        months -= 1
    while _add_months(start, months + 1) <= end:
        months += 1
    return max(0, months)


def _age_on_date(birth_date: date, as_of: date) -> float:
    return max(0.0, (as_of - birth_date).days / 365.2425)


def _date_from_age(birth_date: date, age_years: float) -> date:
    return _add_months(birth_date, int(round(max(0.0, age_years) * 12)))


def _add_months(start: date, months: int) -> date:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = (next_month - date.resolution).day
    return date(year, month, min(start.day, last_day))


def _annual_rate_to_monthly(percent_rate: float) -> float:
    decimal_rate = percent_rate / 100.0
    if decimal_rate <= -1:
        return -1.0
    return (1.0 + decimal_rate) ** (1.0 / 12.0) - 1.0


def _annual_fee_to_monthly(percent_rate: float) -> float:
    decimal_rate = max(0.0, percent_rate) / 100.0
    if decimal_rate <= 0:
        return 0.0
    if decimal_rate >= 1:
        return 1.0
    return 1.0 - ((1.0 - decimal_rate) ** (1.0 / 12.0))


def _seeded_rng(*parts) -> random.Random:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _sample_regime_return(rng: random.Random, monthly_return: float, monthly_sigma: float) -> float:
    if monthly_sigma <= 0:
        return monthly_return
    regime_roll = rng.random()
    if regime_roll < 0.06:
        realized = rng.gauss(monthly_return - (monthly_sigma * 2.4), monthly_sigma * 2.35)
    elif regime_roll < 0.24:
        realized = rng.gauss(monthly_return - (monthly_sigma * 0.8), monthly_sigma * 1.45)
    else:
        realized = rng.gauss(monthly_return, monthly_sigma)
    return max(-0.95, min(0.75, realized))


def _estimate_current_value_from_plan(plan: dict) -> float:
    current_age = _to_float(plan.get("currentAge"), 0)
    age_started = _to_float(plan.get("ageStartedInvesting"), current_age)
    monthly_investment = max(0.0, _to_float(plan.get("monthlyInvestment"), 0))
    initial_investment = max(0.0, _to_float(plan.get("initialInvestmentAmount"), monthly_investment))
    if age_started >= current_age:
        return round(initial_investment, 2)

    months_investing = max(0, int(round((current_age - age_started) * 12)))
    wealth = initial_investment
    for month_index in range(1, months_investing + 1):
        age = age_started + month_index / 12.0
        annual_return, _ = _return_for_month(plan, age, False)
        monthly_return = _annual_rate_to_monthly(annual_return)
        wealth = max(0.0, wealth * (1.0 + monthly_return))
        wealth = round(max(0.0, wealth + monthly_investment), 2)

    return round(wealth, 2)


def _to_dynamodb_value(value):
    if isinstance(value, bool) or value is None or isinstance(value, (str, int, Decimal)):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_to_dynamodb_value(item) for item in value]
    if isinstance(value, tuple):
        return [_to_dynamodb_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_dynamodb_value(item) for key, item in value.items()}
    return value


def _normalize_label(value: str, fallback: str) -> str:
    label = str(value or fallback).strip()
    return label[:60] or fallback


def _resolve_plan_dates(payload: dict) -> tuple[date, date, date, date, float, float, float, int]:
    today = _utc_today()
    birth_date = _parse_date(payload.get("dateOfBirth"))
    current_age_raw = _to_float(payload.get("currentAge"), 35)
    if birth_date is None:
        birth_date = _date_from_age(today, 0)
        birth_date = _add_months(today, -int(round(max(0.0, current_age_raw) * 12)))

    current_age = round(_age_on_date(birth_date, today), 2)
    investing_start = _parse_date(payload.get("investingStartDate"))
    age_started_raw = _to_float(payload.get("ageStartedInvesting"), current_age)
    if investing_start is None:
        investing_start = _date_from_age(birth_date, age_started_raw)

    retirement_date = _parse_date(payload.get("retirementDate"))
    retirement_age_raw = _to_float(payload.get("retirementAge"), max(current_age, 65))
    if retirement_date is None:
        retirement_date = _date_from_age(birth_date, retirement_age_raw)

    target_age = round(max(retirement_age_raw + 1, min(_to_float(payload.get("targetAge"), payload.get("maxAge") or 88.6), 120)), 1)
    target_date = _parse_date(payload.get("targetDate")) or _date_from_age(birth_date, target_age)

    age_started = round(_age_on_date(birth_date, investing_start), 2)
    retirement_age = round(_age_on_date(birth_date, retirement_date), 2)
    return birth_date, investing_start, retirement_date, target_date, current_age, age_started, retirement_age, target_age


def _validate_age(age: float, label: str):
    if age < 0 or age > 120:
        raise ValueError(f"{label} must be between 0 and 120")


def _validate_age_range(start_age: float, end_age: float, label: str):
    _validate_age(start_age, f"{label} start age")
    _validate_age(end_age, f"{label} end age")
    if end_age < start_age:
        raise ValueError(f"{label} end age must be greater than or equal to start age")


def _ensure_object_list(raw_items, label: str) -> list[dict]:
    if raw_items in (None, ""):
        return []
    if not isinstance(raw_items, list):
        raise ValueError(f"{label} must be an array")
    if len(raw_items) > _MAX_LIST_ITEMS:
        raise ValueError(f"{label} can contain at most {_MAX_LIST_ITEMS} items")
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError(f"{label} entries must be objects")
    return raw_items


def _normalize_income_streams(raw_streams) -> list[dict]:
    streams = []
    for index, raw in enumerate(_ensure_object_list(raw_streams, "Income streams")):
        start_age = _to_float(raw.get("startAge"), 0)
        end_age = _to_float(raw.get("endAge"), _MAX_AGE)
        monthly_amount = _to_float(raw.get("monthlyAmount"), 0)
        _validate_age_range(start_age, end_age, "Income stream")
        if monthly_amount < 0:
            raise ValueError("Income stream monthly amount cannot be negative")
        streams.append({
            "id": str(raw.get("id") or f"income-{index + 1}"),
            "label": _normalize_label(raw.get("label") or raw.get("name"), f"Income {index + 1}"),
            "startAge": start_age,
            "endAge": end_age,
            "monthlyAmount": monthly_amount,
            "inflationLinked": _to_bool(raw.get("inflationLinked"), True),
        })
    return streams


def _normalize_cashflows(raw_cashflows) -> list[dict]:
    cashflows = []
    for index, raw in enumerate(_ensure_object_list(raw_cashflows, "One-time events")):
        age = _to_float(raw.get("age"), 0)
        _validate_age(age, "One-time event age")
        cashflows.append({
            "id": str(raw.get("id") or f"cashflow-{index + 1}"),
            "label": _normalize_label(raw.get("label") or raw.get("name"), f"Cashflow {index + 1}"),
            "age": age,
            "amount": _to_float(raw.get("amount"), 0),
        })
    return cashflows


def _normalize_spending_phases(raw_phases) -> list[dict]:
    phases = []
    for index, raw in enumerate(_ensure_object_list(raw_phases, "Spending phases")):
        start_age = _to_float(raw.get("startAge"), 0)
        end_age = _to_float(raw.get("endAge"), _MAX_AGE)
        monthly_spending = _to_float(raw.get("monthlySpending"), 0)
        _validate_age_range(start_age, end_age, "Spending phase")
        if monthly_spending < 0:
            raise ValueError("Spending phase monthly spending cannot be negative")
        phases.append({
            "id": str(raw.get("id") or f"spending-{index + 1}"),
            "label": _normalize_label(raw.get("label") or raw.get("name"), f"Spending phase {index + 1}"),
            "startAge": start_age,
            "endAge": end_age,
            "monthlySpending": monthly_spending,
            "inflationLinked": _to_bool(raw.get("inflationLinked"), True),
        })
    return phases


def _normalize_return_phases(raw_phases) -> list[dict]:
    phases = []
    for index, raw in enumerate(_ensure_object_list(raw_phases, "Return phases")):
        start_age = _to_float(raw.get("startAge"), 0)
        end_age = _to_float(raw.get("endAge"), _MAX_AGE)
        annual_return = _to_float(raw.get("annualReturn"), 0)
        annual_volatility = _to_float(raw.get("annualVolatility"), 0)
        _validate_age_range(start_age, end_age, "Return phase")
        if annual_return <= -100:
            raise ValueError("Return phase annual return must be greater than -100")
        if annual_volatility < 0 or annual_volatility > 200:
            raise ValueError("Return phase annual volatility must be between 0 and 200")
        phases.append({
            "id": str(raw.get("id") or f"return-{index + 1}"),
            "label": _normalize_label(raw.get("label") or raw.get("name"), f"Return phase {index + 1}"),
            "startAge": start_age,
            "endAge": end_age,
            "annualReturn": annual_return,
            "annualVolatility": annual_volatility,
        })
    return phases


def normalize_plan(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Plan payload must be an object")

    name = str(payload.get("name") or "Retirement Plan").strip()
    if len(name) > _MAX_NAME_LENGTH:
        raise ValueError(f"Plan name must be {_MAX_NAME_LENGTH} characters or fewer")
    if not name:
        raise ValueError("Plan name is required")
    birth_date, investing_start, retirement_date, target_date, current_age, age_started, retirement_age, target_age = _resolve_plan_dates(payload)
    monthly_investment = _to_float(payload.get("monthlyInvestment"), 0)
    initial_investment = _to_float(
        payload.get("initialInvestmentAmount"),
        monthly_investment,
    )
    yearly_return_working = _to_float(payload.get("expectedYearlyReturnWorking"), 7)
    yearly_return_retired = _to_float(payload.get("expectedYearlyReturnAfterRetirement"), 4)
    monthly_retirement_spending = _to_float(payload.get("monthlyRetirementSpending"), 0)
    inflation_rate = _to_float(payload.get("inflationRate"), 0)
    annual_fee_rate = _to_float(payload.get("annualFeeRate"), 0)
    monte_carlo_enabled = _to_bool(payload.get("monteCarloEnabled"), False)
    monte_carlo_runs = max(50, min(int(_to_float(payload.get("monteCarloRuns"), 250)), 1000))
    annual_vol_working = _to_float(payload.get("annualVolatilityWorking"), 15)
    annual_vol_retired = _to_float(payload.get("annualVolatilityRetired"), 8)

    if current_age <= 0:
        raise ValueError("Current age must be greater than 0")
    if investing_start > _utc_today():
        raise ValueError("Investing start date cannot be in the future")
    if investing_start < birth_date:
        raise ValueError("Investing start date cannot be before date of birth")
    if retirement_date <= _utc_today():
        raise ValueError("Retirement date must be in the future")
    if retirement_date <= investing_start:
        raise ValueError("Retirement date must be after investing start date")
    if target_date <= retirement_date:
        raise ValueError("Target age date must be after retirement date")
    if monthly_investment < 0:
        raise ValueError("Monthly investment cannot be negative")
    if initial_investment < 0:
        raise ValueError("Initial investment cannot be negative")
    if monthly_retirement_spending < 0:
        raise ValueError("Monthly retirement spending cannot be negative")
    if annual_fee_rate < 0 or annual_fee_rate > 15:
        raise ValueError("Annual fee rate must be between 0 and 15")
    plan_id = str(payload.get("planId") or payload.get("id") or _new_plan_id(name)).strip()
    if not _PLAN_ID_RE.fullmatch(plan_id):
        raise ValueError("Plan id must contain only lowercase letters, numbers, and dashes")
    notes = str(payload.get("notes") or "").strip()
    if len(notes) > _MAX_NOTES_LENGTH:
        raise ValueError(f"Notes must be {_MAX_NOTES_LENGTH} characters or fewer")

    return {
        "planId": plan_id,
        "name": name,
        "notes": notes,
        "dateOfBirth": birth_date.isoformat(),
        "investingStartDate": investing_start.isoformat(),
        "retirementDate": retirement_date.isoformat(),
        "targetDate": target_date.isoformat(),
        "targetAge": target_age,
        "currentAge": round(current_age, 2),
        "ageStartedInvesting": round(age_started, 2),
        "retirementAge": round(retirement_age, 2),
        "monthlyInvestment": round(monthly_investment, 2),
        "expectedYearlyReturnWorking": round(yearly_return_working, 4),
        "expectedYearlyReturnAfterRetirement": round(yearly_return_retired, 4),
        "monthlyRetirementSpending": round(monthly_retirement_spending, 2),
        "initialInvestmentAmount": round(initial_investment, 2),
        "inflationRate": round(inflation_rate, 4),
        "annualFeeRate": round(annual_fee_rate, 4),
        "monteCarloEnabled": monte_carlo_enabled,
        "monteCarloRuns": monte_carlo_runs,
        "annualVolatilityWorking": round(annual_vol_working, 4),
        "annualVolatilityRetired": round(annual_vol_retired, 4),
        "maxAge": target_age,
        "retirementIncomeStreams": _normalize_income_streams(payload.get("retirementIncomeStreams")),
        "oneTimeCashflows": _normalize_cashflows(payload.get("oneTimeCashflows")),
        "spendingPhases": _normalize_spending_phases(payload.get("spendingPhases")),
        "returnPhases": _normalize_return_phases(payload.get("returnPhases")),
        "schemaVersion": _PLAN_SCHEMA_VERSION,
    }


def _load_actual_series(user_id: str) -> list[dict]:
    rows = snapshots.list_snapshots(user_id, "summary")
    points = []
    for row in rows:
        dt = _parse_date(row.get("snapshotDate"))
        if not dt:
            continue
        points.append({
            "date": dt.isoformat(),
            "value": round(_to_float(row.get("portfolioValue")), 2),
            "investment": round(_to_float(row.get("investmentValue")), 2),
            "phase": "actual",
        })
    points.sort(key=lambda item: item["date"])
    return points


def _phase_for_age(plan: dict, age: float, key: str) -> dict | None:
    for phase in plan.get(key) or []:
        if phase["startAge"] <= age <= phase["endAge"]:
            return phase
    return None


def _income_for_month(plan: dict, age: float, inflation_factor: float) -> float:
    total = 0.0
    for stream in plan.get("retirementIncomeStreams") or []:
        if stream["startAge"] <= age <= stream["endAge"]:
            amount = stream["monthlyAmount"]
            if stream.get("inflationLinked"):
                amount *= inflation_factor
            total += amount
    return total


def _spending_for_month(plan: dict, age: float, inflation_factor: float) -> float:
    phase = _phase_for_age(plan, age, "spendingPhases")
    if phase:
        amount = phase["monthlySpending"]
        if phase.get("inflationLinked"):
            amount *= inflation_factor
        return amount
    return plan["monthlyRetirementSpending"] * inflation_factor


def _return_for_month(plan: dict, age: float, retired: bool) -> tuple[float, float]:
    phase = _phase_for_age(plan, age, "returnPhases")
    if phase:
        return phase["annualReturn"], phase.get("annualVolatility", 0)
    if retired:
        return plan["expectedYearlyReturnAfterRetirement"], plan["annualVolatilityRetired"]
    return plan["expectedYearlyReturnWorking"], plan["annualVolatilityWorking"]


def _event_amount_for_date(plan: dict, birth_date: date, current_date: date) -> float:
    total = 0.0
    for event in plan.get("oneTimeCashflows") or []:
        event_date = _date_from_age(birth_date, event["age"])
        if event_date == current_date:
            total += event["amount"]
    return total


def _value_at_date(points: list[dict], target_date: str, fallback: float) -> float:
    for point in points:
        if point.get("date") >= target_date:
            return round(_to_float(point.get("value")), 2)
    return round(fallback, 2)


def _simulate_monthly(plan: dict, start_date: date, starting_value: float, end_date: date) -> tuple[list[dict], dict]:
    birth_date = _parse_date(plan["dateOfBirth"]) or _utc_today()
    retirement_date = _parse_date(plan["retirementDate"]) or start_date
    horizon_months = max(0, _months_between(start_date, end_date))
    retirement_month = max(0, _months_between(start_date, retirement_date))
    monthly_inflation = _annual_rate_to_monthly(plan["inflationRate"])
    monthly_fee = _annual_fee_to_monthly(_to_float(plan.get("annualFeeRate"), 0))
    wealth = max(0.0, round(starting_value, 2))
    start_age = _age_on_date(birth_date, start_date)
    points = [{
        "date": start_date.isoformat(),
        "value": wealth,
        "netCashflow": 0.0,
        "age": round(start_age, 4),
        "phase": "retirement" if start_date >= retirement_date else "accumulation",
    }]
    depleted_at = None
    retirement_value = wealth if start_date >= retirement_date else None

    for month_index in range(1, horizon_months + 1):
        current_date = _add_months(start_date, month_index)
        age = _age_on_date(birth_date, current_date)
        retired = current_date >= retirement_date
        annual_return, _ = _return_for_month(plan, age, retired)
        monthly_return = _annual_rate_to_monthly(annual_return)
        wealth = max(0.0, wealth * (1.0 + monthly_return))
        wealth = max(0.0, wealth * (1.0 - monthly_fee))

        months_since_retirement = max(0, _months_between(retirement_date, current_date)) if retired else 0
        inflation_factor = (1.0 + monthly_inflation) ** months_since_retirement
        net_cashflow = 0.0

        if retired:
            income = _income_for_month(plan, age, inflation_factor)
            spending = _spending_for_month(plan, age, inflation_factor)
            net_cashflow += income - spending
        else:
            net_cashflow += plan["monthlyInvestment"]

        net_cashflow += _event_amount_for_date(plan, birth_date, current_date)
        wealth = round(max(0.0, wealth + net_cashflow), 2)

        if retired and retirement_value is None:
            retirement_value = wealth

        points.append({
            "date": current_date.isoformat(),
            "value": wealth,
            "netCashflow": round(net_cashflow, 2),
            "age": round(age, 4),
            "phase": "retirement" if retired else "accumulation",
        })

        if retired and depleted_at is None and wealth <= 0:
            depleted_at = {
                "date": current_date.isoformat(),
                "age": round(age, 2),
                "monthIndex": month_index,
            }
            break

    return points, {
        "retirementMonth": retirement_month,
        "retirementDate": retirement_date.isoformat(),
        "retirementValue": round(retirement_value if retirement_value is not None else wealth, 2),
        "depletedAt": depleted_at,
        "endDate": end_date.isoformat(),
    }


def _simulate_monte_carlo(plan: dict, start_date: date, starting_value: float, end_date: date) -> dict | None:
    if not plan.get("monteCarloEnabled"):
        return None

    birth_date = _parse_date(plan["dateOfBirth"]) or _utc_today()
    retirement_date = _parse_date(plan["retirementDate"]) or start_date
    horizon_months = max(0, _months_between(start_date, end_date))
    monthly_inflation = _annual_rate_to_monthly(plan["inflationRate"])
    monthly_fee = _annual_fee_to_monthly(_to_float(plan.get("annualFeeRate"), 0))
    runs = plan["monteCarloRuns"]
    rng = _seeded_rng(
        plan.get("planId"),
        plan.get("dateOfBirth"),
        plan.get("retirementDate"),
        plan.get("targetDate"),
        plan.get("monthlyInvestment"),
        plan.get("monthlyRetirementSpending"),
        plan.get("expectedYearlyReturnWorking"),
        plan.get("expectedYearlyReturnAfterRetirement"),
        plan.get("annualVolatilityWorking"),
        plan.get("annualVolatilityRetired"),
        plan.get("annualFeeRate"),
        start_date.isoformat(),
        round(starting_value, 2),
        end_date.isoformat(),
        runs,
    )
    by_month: list[list[float]] = [[] for _ in range(horizon_months + 1)]
    by_month[0].append(round(starting_value, 2))
    success_count = 0

    for _ in range(runs):
        wealth = max(0.0, round(starting_value, 2))
        depleted = False
        for month_index in range(1, horizon_months + 1):
            current_date = _add_months(start_date, month_index)
            age = plan["currentAge"] + month_index / 12.0
            age = _age_on_date(birth_date, current_date)
            retired = current_date >= retirement_date
            annual_return, annual_volatility = _return_for_month(plan, age, retired)
            monthly_return = _annual_rate_to_monthly(annual_return)
            monthly_sigma = max(0.0, annual_volatility / 100.0 / math.sqrt(12.0))
            realized_return = _sample_regime_return(rng, monthly_return, monthly_sigma)
            wealth = max(0.0, wealth * (1.0 + realized_return))
            wealth = max(0.0, wealth * (1.0 - monthly_fee))

            months_since_retirement = max(0, _months_between(retirement_date, current_date)) if retired else 0
            inflation_factor = (1.0 + monthly_inflation) ** months_since_retirement
            if retired:
                wealth += _income_for_month(plan, age, inflation_factor)
                wealth -= _spending_for_month(plan, age, inflation_factor)
            else:
                wealth += plan["monthlyInvestment"]
            wealth += _event_amount_for_date(plan, birth_date, current_date)
            wealth = round(max(0.0, wealth), 2)
            by_month[month_index].append(wealth)
            if retired and wealth <= 0 and not depleted:
                depleted = True
                break

        if not depleted:
            success_count += 1

    def percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        pos = (len(ordered) - 1) * pct
        lower = int(math.floor(pos))
        upper = int(math.ceil(pos))
        if lower == upper:
            return ordered[lower]
        weight = pos - lower
        return ordered[lower] * (1 - weight) + ordered[upper] * weight

    p10 = []
    p50 = []
    p90 = []
    for month_index, values in enumerate(by_month):
        point_date = _add_months(start_date, month_index).isoformat()
        p10.append({"date": point_date, "value": round(percentile(values, 0.10), 2)})
        p50.append({"date": point_date, "value": round(percentile(values, 0.50), 2)})
        p90.append({"date": point_date, "value": round(percentile(values, 0.90), 2)})

    return {
        "runs": runs,
        "successProbability": round((success_count / runs) * 100.0, 2) if runs else 0.0,
        "p10": p10,
        "p50": p50,
        "p90": p90,
    }


def _chunk_points(points: list[dict]) -> list[list[dict]]:
    return [points[index:index + _SEGMENT_SIZE] for index in range(0, len(points), _SEGMENT_SIZE)] or [[]]


def _summarize_plan(plan: dict, result: dict | None) -> dict:
    summary = {
        "planId": plan["planId"],
        "name": plan["name"],
        "schemaVersion": plan.get("schemaVersion", _PLAN_SCHEMA_VERSION),
        "planVersion": plan.get("planVersion"),
        "dateOfBirth": plan.get("dateOfBirth"),
        "investingStartDate": plan.get("investingStartDate"),
        "retirementDate": plan.get("retirementDate"),
        "targetAge": plan.get("targetAge"),
        "currentAge": plan["currentAge"],
        "retirementAge": plan["retirementAge"],
        "monthlyInvestment": plan["monthlyInvestment"],
        "monthlyRetirementSpending": plan["monthlyRetirementSpending"],
        "expectedYearlyReturnWorking": plan.get("expectedYearlyReturnWorking"),
        "expectedYearlyReturnAfterRetirement": plan.get("expectedYearlyReturnAfterRetirement"),
        "annualFeeRate": plan.get("annualFeeRate", 0),
        "updatedAt": plan.get("updatedAt"),
        "latestRunId": plan.get("latestRunId"),
        "latestSavedAt": plan.get("latestSavedAt"),
    }
    if result:
        summary["latestSummary"] = result.get("summary")
    elif plan.get("latestSummary"):
        summary["latestSummary"] = plan.get("latestSummary")
    return summary


def simulate_plan(user_id: str, plan: dict) -> dict:
    actual = _load_actual_series(user_id)
    latest_actual = actual[-1] if actual else None
    anchor_date = _parse_date((latest_actual or {}).get("date")) or _utc_today()
    investing_start = _parse_date(plan["investingStartDate"]) or anchor_date
    target_date = _parse_date(plan["targetDate"]) or _date_from_age(_parse_date(plan["dateOfBirth"]) or _utc_today(), plan["targetAge"])

    projected_history, projected_history_meta = _simulate_monthly(
        plan,
        investing_start,
        plan["initialInvestmentAmount"],
        anchor_date,
    )
    projected_current = round(_to_float((projected_history[-1] if projected_history else {}).get("value"), plan["initialInvestmentAmount"]), 2)
    actual_current = round(_to_float((latest_actual or {}).get("value"), projected_current), 2)

    future_actual, actual_meta = _simulate_monthly(plan, anchor_date, actual_current, target_date)
    future_projected, projected_meta = _simulate_monthly(plan, anchor_date, projected_current, target_date)
    monte_carlo = _simulate_monte_carlo(plan, anchor_date, actual_current, target_date)
    actual_depletion = actual_meta.get("depletedAt")
    projected_depletion = projected_meta.get("depletedAt")
    actual_final = future_actual[-1]["value"] if future_actual else actual_current
    projected_final = future_projected[-1]["value"] if future_projected else projected_current
    transition_date = plan["retirementDate"]
    actual_retirement_value = _value_at_date(future_actual, transition_date, actual_current)
    projected_retirement_value = _value_at_date(future_projected, transition_date, projected_current)
    months_after_retirement = (
        actual_depletion["monthIndex"] - actual_meta["retirementMonth"] if actual_depletion else
        max(0, len(future_actual) - 1 - actual_meta["retirementMonth"])
    )

    summary = {
        "actualStartDate": actual[0]["date"] if actual else None,
        "actualEndDate": actual[-1]["date"] if actual else None,
        "historicalProjectedStartDate": projected_history[0]["date"] if projected_history else None,
        "forecastEndDate": future_actual[-1]["date"] if future_actual else None,
        "currentPortfolioValue": actual_current,
        "projectedCurrentPortfolioValue": projected_current,
        "retirementPortfolioValue": actual_retirement_value,
        "projectedRetirementPortfolioValue": projected_retirement_value,
        "finalPortfolioValue": round(actual_final, 2),
        "projectedFinalPortfolioValue": round(projected_final, 2),
        "transitionDate": transition_date,
        "portfolioLasts": actual_depletion is None,
        "depletionDate": actual_depletion.get("date") if actual_depletion else None,
        "depletionAge": actual_depletion.get("age") if actual_depletion else None,
        "projectedDepletionDate": projected_depletion.get("date") if projected_depletion else None,
        "projectedDepletionAge": projected_depletion.get("age") if projected_depletion else None,
        "monthsAfterRetirement": months_after_retirement,
        "targetAge": plan["targetAge"],
        "targetDate": plan["targetDate"],
        "lastsToTargetAge": actual_depletion is None,
        "monteCarloSuccessProbability": (monte_carlo or {}).get("successProbability"),
        "assumptionModel": "institutional-lite-v1",
        "annualFeeRate": plan.get("annualFeeRate", 0),
        "historicalMonths": len(actual),
        "projectedHistoricalMonths": len(projected_history),
        "forecastMonths": len(future_actual),
    }

    return {
        "summary": summary,
        "series": {
            "actual": actual,
            "projectedPast": projected_history,
            "futureFromActual": future_actual,
            "futureFromProjected": future_projected,
            "transitionMarker": [{
                "date": transition_date,
                "value": actual_retirement_value,
                "label": "Retirement",
            }],
            "todayMarker": [{
                "date": anchor_date.isoformat(),
                "value": actual_current,
                "label": "Today",
            }],
            "monteCarloP10": (monte_carlo or {}).get("p10", []),
            "monteCarloP50": (monte_carlo or {}).get("p50", []),
            "monteCarloP90": (monte_carlo or {}).get("p90", []),
        },
        "monteCarlo": monte_carlo,
    }


def _write_result_items(user_id: str, plan: dict, result: dict, created_at: str, updated_at: str, plan_version: int) -> dict:
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    latest_summary = result["summary"]
    table = _table()

    plan_item = {
        "userId": user_id,
        "sk": _plan_sk(plan["planId"]),
        "itemType": "PLAN",
        "planId": plan["planId"],
        "name": plan["name"],
        "plan": plan,
        "schemaVersion": _PLAN_SCHEMA_VERSION,
        "planVersion": plan_version,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "latestRunId": run_id,
        "latestSavedAt": updated_at,
        "latestSummary": latest_summary,
    }
    latest_item = {
        "userId": user_id,
        "sk": _latest_sk(plan["planId"]),
        "itemType": "RESULT_LATEST",
        "planId": plan["planId"],
        "schemaVersion": _RESULT_SCHEMA_VERSION,
        "planVersion": plan_version,
        "runId": run_id,
        "savedAt": updated_at,
        "summary": latest_summary,
        "seriesKeys": [key for key, points in result["series"].items() if points],
        "monteCarlo": result.get("monteCarlo"),
    }
    run_item = {
        "userId": user_id,
        "sk": _run_sk(plan["planId"], run_id),
        "itemType": "RESULT_RUN",
        "planId": plan["planId"],
        "schemaVersion": _RESULT_SCHEMA_VERSION,
        "planVersion": plan_version,
        "runId": run_id,
        "savedAt": updated_at,
        "summary": latest_summary,
        "monteCarlo": result.get("monteCarlo"),
    }

    with table.batch_writer() as batch:
        batch.put_item(Item=_to_dynamodb_value(plan_item))
        batch.put_item(Item=_to_dynamodb_value(latest_item))
        batch.put_item(Item=_to_dynamodb_value(run_item))
        for series_key, points in result["series"].items():
            if not points:
                continue
            for index, chunk in enumerate(_chunk_points(points)):
                batch.put_item(Item=_to_dynamodb_value({
                    "userId": user_id,
                    "sk": _segment_sk(plan["planId"], run_id, series_key.upper(), index),
                    "itemType": "RESULT_SEGMENT",
                    "planId": plan["planId"],
                    "schemaVersion": _RESULT_SCHEMA_VERSION,
                    "planVersion": plan_version,
                    "runId": run_id,
                    "seriesKey": series_key,
                    "segmentIndex": index,
                    "points": chunk,
                    "savedAt": updated_at,
                }))

    saved = dict(plan)
    saved.update({
        "createdAt": created_at,
        "updatedAt": updated_at,
        "planVersion": plan_version,
        "latestRunId": run_id,
        "latestSavedAt": updated_at,
        "latestSummary": latest_summary,
    })
    return {
        "plan": saved,
        "result": {
            "runId": run_id,
            "savedAt": updated_at,
            **result,
        },
    }


def save_plan(user_id: str, payload: dict) -> dict:
    plan = normalize_plan(payload)
    existing = _table().get_item(Key={"userId": user_id, "sk": _plan_sk(plan["planId"])}).get("Item") or {}
    created_at = existing.get("createdAt") or _now_iso()
    updated_at = _now_iso()
    plan_version = int(existing.get("planVersion") or 0) + 1
    result = simulate_plan(user_id, plan)
    return _write_result_items(user_id, plan, result, created_at, updated_at, plan_version)


def _load_segments(user_id: str, plan_id: str, run_id: str) -> dict:
    items = []
    response = _table().query(
        KeyConditionExpression=Key("userId").eq(user_id) & Key("sk").begins_with(f"RESULT#{plan_id}#SEG#{run_id}#")
    )
    items.extend(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        response = _table().query(
            KeyConditionExpression=Key("userId").eq(user_id) & Key("sk").begins_with(f"RESULT#{plan_id}#SEG#{run_id}#"),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    series = {}
    for item in sorted(items, key=lambda row: row.get("sk", "")):
        key = item.get("seriesKey")
        series.setdefault(key, [])
        series[key].extend(item.get("points") or [])
    return series


def get_plan(user_id: str, plan_id: str) -> dict | None:
    item = _table().get_item(Key={"userId": user_id, "sk": _plan_sk(plan_id)}).get("Item")
    if not item:
        return None

    latest = _table().get_item(Key={"userId": user_id, "sk": _latest_sk(plan_id)}).get("Item") or {}
    run_id = latest.get("runId") or item.get("latestRunId")
    series = _load_segments(user_id, plan_id, run_id) if run_id else {}
    result = None
    if run_id:
        result = {
            "runId": run_id,
            "savedAt": latest.get("savedAt") or item.get("latestSavedAt"),
            "summary": latest.get("summary") or item.get("latestSummary"),
            "monteCarlo": latest.get("monteCarlo"),
            "series": series,
        }
    plan = dict(item.get("plan") or {})
    plan.update({
        "createdAt": item.get("createdAt"),
        "updatedAt": item.get("updatedAt"),
        "planVersion": item.get("planVersion"),
        "latestRunId": item.get("latestRunId"),
        "latestSavedAt": item.get("latestSavedAt"),
        "latestSummary": item.get("latestSummary"),
    })
    return {"plan": plan, "result": result}


def list_plans(user_id: str) -> list[dict]:
    response = _table().query(
        KeyConditionExpression=Key("userId").eq(user_id) & Key("sk").begins_with("PLAN#")
    )
    items = response.get("Items", [])
    while response.get("LastEvaluatedKey"):
        response = _table().query(
            KeyConditionExpression=Key("userId").eq(user_id) & Key("sk").begins_with("PLAN#"),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    items.sort(key=lambda row: (row.get("updatedAt") or "", row.get("name") or ""), reverse=True)
    return [_summarize_plan(item.get("plan") or {}, None if item.get("plan") is None else item) for item in items]


def simulate_saved_plan(user_id: str, plan_id: str, overrides: dict | None = None) -> dict:
    current = get_plan(user_id, plan_id)
    if not current:
        raise ValueError("Plan not found")
    payload = dict(current["plan"])
    payload.update(overrides or {})
    payload["planId"] = plan_id
    return save_plan(user_id, payload)


def delete_plan(user_id: str, plan_id: str) -> bool:
    response = _table().query(KeyConditionExpression=Key("userId").eq(user_id))
    items = response.get("Items", [])
    while response.get("LastEvaluatedKey"):
        response = _table().query(
            KeyConditionExpression=Key("userId").eq(user_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    to_delete = [
        item for item in items
        if item.get("sk") in {_plan_sk(plan_id), _latest_sk(plan_id)}
        or str(item.get("sk", "")).startswith(f"RESULT#{plan_id}#RUN#")
        or str(item.get("sk", "")).startswith(f"RESULT#{plan_id}#SEG#")
    ]
    if not to_delete:
        return False

    with _table().batch_writer() as batch:
        for item in to_delete:
            batch.delete_item(Key={"userId": user_id, "sk": item["sk"]})
    return True
