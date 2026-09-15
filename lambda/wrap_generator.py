"""Pre-compile Roastfolio monthly audit documents for DynamoDB."""

from __future__ import annotations

import calendar
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import boto3

import db
import diary_handler
import portfolio_avco
import portfolios
import retirement_plans
import snapshots


ZERO = Decimal("0")
MONEY = Decimal("0.01")
PCT = Decimal("0.0001")
MARKET_CONTEXT_IDS = ("WIG", "DAX", "FTSE100", "SP500", "NASDAQ", "MSCI_WORLD")


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return ZERO
    return Decimal(str(value))


def _money(value: Any) -> Decimal:
    return _decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _pct(value: Any) -> Decimal:
    return _decimal(value).quantize(PCT, rounding=ROUND_HALF_UP)


def _month_bounds(year: int, month: int) -> tuple[date, date, date]:
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    start = date(year, month, 1)
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, next_month, next_month.fromordinal(next_month.toordinal() - 1)


def _snapshot_date(item: dict) -> str:
    return str(item.get("snapshotDate") or item.get("date") or "")[:10]


def _ordered_snapshots(items: list[dict]) -> list[dict]:
    return sorted((item for item in items if _snapshot_date(item)), key=_snapshot_date)


def _with_unit_prices(items: list[dict]) -> list[dict]:
    ordered = _ordered_snapshots(items)
    if all(item.get("unitPrice") not in (None, "") for item in ordered):
        return ordered
    calculated = snapshots.calculate_virtual_unit_series(ordered)
    by_date = {str(row.get("date")): row.get("unit_price") for row in calculated}
    return [{**item, "unitPrice": item.get("unitPrice") or by_date.get(_snapshot_date(item))} for item in ordered]


def _period_boundaries(items: list[dict], start: date, next_month: date) -> tuple[dict | None, dict | None]:
    ordered = _ordered_snapshots(items)
    start_key = start.isoformat()
    end_key = next_month.isoformat()
    start_snapshot = next((item for item in ordered if _snapshot_date(item) >= start_key), None)
    if not start_snapshot or _snapshot_date(start_snapshot) >= end_key:
        return None, None
    end_snapshot = next((item for item in ordered if _snapshot_date(item) >= end_key), None)
    if end_snapshot is None:
        end_snapshot = next((item for item in reversed(ordered) if _snapshot_date(item) < end_key), None)
    if start_snapshot and end_snapshot and _snapshot_date(end_snapshot) < _snapshot_date(start_snapshot):
        end_snapshot = None
    return start_snapshot, end_snapshot


def _monthly_performance(items: list[dict], start: date, next_month: date, cash_flow: Decimal) -> dict:
    ordered = _with_unit_prices(items)
    start_snapshot, end_snapshot = _period_boundaries(ordered, start, next_month)
    if not start_snapshot or not end_snapshot:
        return {
            "start_value_pln": ZERO,
            "end_value_pln": ZERO,
            "twr_pct": ZERO,
            "nominal_change_pln": ZERO,
        }

    start_value = _decimal(start_snapshot.get("portfolioValue"))
    end_value = _decimal(end_snapshot.get("portfolioValue"))
    start_unit = _decimal(start_snapshot.get("unitPrice"))
    end_unit = _decimal(end_snapshot.get("unitPrice"))
    twr_pct = ((end_unit / start_unit) - Decimal("1")) * Decimal("100") if start_unit else ZERO
    return {
        "start_value_pln": _money(start_value),
        "end_value_pln": _money(end_value),
        "twr_pct": _pct(twr_pct),
        "nominal_change_pln": _money(end_value - start_value - cash_flow),
    }


def _transaction_value(transaction: dict) -> Decimal:
    return abs(_decimal(transaction.get("value")))


def selected_benchmark(user_id: str) -> str:
    profile = db.get_user(user_id) or {}
    benchmark_id = (profile.get("settings") or {}).get("benchmark", db.DEFAULT_BENCHMARK)
    return benchmark_id if benchmark_id in db.BENCHMARKS else db.DEFAULT_BENCHMARK


def _benchmark_daily(benchmark_id: str, start: date, end: date) -> dict[str, Decimal]:
    # Runtime import avoids coupling the API module's imports to the generator.
    from handler import load_benchmark_cache, fetch_benchmark_history, save_benchmark_cache

    cache = load_benchmark_cache(benchmark_id)
    start_key, end_key = start.isoformat(), end.isoformat()
    covered = any(
        row.get("start", "9999") <= start_key and row.get("end", "") >= end_key
        for row in cache.get("daily_ranges", [])
    )
    dates = {row.get("t") for row in cache.get("daily", [])}
    required_weekdays = {
        (start + timedelta(days=offset)).isoformat()
        for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() < 5
    }
    if not covered and not required_weekdays.issubset(dates):
        updated = fetch_benchmark_history(
            benchmark_id, db.BENCHMARKS[benchmark_id]["ticker"], cache,
            start_date=start_key, end_date=end_key,
        )
        if updated != cache:
            save_benchmark_cache(benchmark_id, updated)
        cache = updated
    prices = {}
    for row in cache.get("daily", []):
        try:
            price = _decimal(row.get("c"))
            day = date.fromisoformat(str(row.get("t"))).isoformat()
            if price.is_finite() and price > ZERO:
                prices[day] = price
        except (ValueError, ArithmeticError):
            continue
    return prices


def _asof_close(prices: dict[str, Decimal], day: str) -> tuple[str | None, Decimal | None]:
    # A boundary may be a weekend/holiday. Disclose the actual quote date and
    # never use a future quote or an indefinitely stale price.
    earliest = (date.fromisoformat(day) - timedelta(days=7)).isoformat()
    quote_day = max((key for key in prices if earliest <= key <= day), default=None)
    return quote_day, prices.get(quote_day) if quote_day else None


def _price_return(start_price: Decimal | None, end_price: Decimal | None) -> Decimal | None:
    if start_price is None or end_price is None or start_price <= ZERO:
        return None
    return _pct((end_price / start_price - 1) * 100)


def _journey(items: list[dict], start: date, next_month: date, benchmark_id: str,
             prices: dict[str, Decimal]) -> dict:
    meta = db.BENCHMARKS[benchmark_id]
    result = {
        "benchmark_id": benchmark_id, "benchmark_name": meta["name"],
        "benchmark_currency": meta["currency"], "points": [],
        "benchmark_return_pct": None, "start_date": None, "end_date": None,
        "benchmark_start_price_date": None, "benchmark_end_price_date": None,
    }
    ordered = _with_unit_prices(items)
    first, last = _period_boundaries(ordered, start, next_month)
    if not first or not last:
        return result
    first_day, last_day = _snapshot_date(first), _snapshot_date(last)
    start_quote, base_price = _asof_close(prices, first_day)
    end_quote, end_price = _asof_close(prices, last_day)
    base_unit = _decimal(first.get("unitPrice"))
    units = {_snapshot_date(row): _decimal(row.get("unitPrice")) for row in ordered}
    days = sorted({day for day in set(units) | set(prices) if first_day <= day <= last_day})
    result.update({
        "start_date": first_day, "end_date": last_day,
        "benchmark_start_price_date": start_quote, "benchmark_end_price_date": end_quote,
        "benchmark_return_pct": _price_return(base_price, end_price),
        "points": [{
            "date": day,
            "portfolio_pct": _price_return(base_unit, units.get(day)) if units.get(day, ZERO) > ZERO else None,
            # No interpolation or forward-filled daily points, even on weekends.
            "benchmark_pct": _price_return(base_price, prices.get(day)),
        } for day in days],
    })
    return result


def _market_comparison(user_id: str, items: list[dict], start: date, next_month: date,
                       benchmark_id: str | None = None) -> dict:
    benchmark_id = benchmark_id or selected_benchmark(user_id)
    if benchmark_id not in db.BENCHMARKS:
        raise ValueError("Unknown benchmark")
    _, last = _period_boundaries(items, start, next_month)
    end = max(next_month, date.fromisoformat(_snapshot_date(last))) if last else next_month
    histories = {
        bid: _benchmark_daily(bid, start - timedelta(days=8), end)
        for bid in dict.fromkeys((benchmark_id, *MARKET_CONTEXT_IDS))
    }
    market_context = []
    for bid in MARKET_CONTEXT_IDS:
        meta = db.BENCHMARKS[bid]
        baseline_day, baseline = _asof_close(histories[bid], (start - timedelta(days=1)).isoformat())
        close_day, close = _asof_close(histories[bid], (next_month - timedelta(days=1)).isoformat())
        market_context.append({
            "id": bid, "name": meta["name"], "currency": meta["currency"],
            "return_pct": _price_return(baseline, close),
            "start_price_date": baseline_day, "end_price_date": close_day,
        })
    return {"journey": _journey(items, start, next_month, benchmark_id, histories[benchmark_id]),
            "market_context": market_context}


def _trading_activity(transactions: list[dict]) -> dict:
    # Ledger value is the settled PLN amount (BUY includes commission; SELL
    # and DIVIDEND are net of stored fees/tax). currency describes the asset.
    totals = {kind: ZERO for kind in ("BUY", "SELL", "DIVIDEND")}
    trades = []
    for tx in transactions:
        kind = str(tx.get("type") or "").upper()
        if kind not in totals:
            continue
        value = _transaction_value(tx)
        totals[kind] += value
        if kind in {"BUY", "SELL"}:
            trades.append({"date": str(tx.get("transactionDate") or "")[:10],
                           "type": kind, "ticker": tx.get("ticker") or tx.get("holdingId"),
                           "value_pln": _money(value)})
    return {
        "buy_total_pln": _money(totals["BUY"]), "sell_total_pln": _money(totals["SELL"]),
        "turnover_pln": _money(totals["BUY"] + totals["SELL"]),
        "dividend_total_pln": _money(totals["DIVIDEND"]), "transaction_count": len(trades),
        "largest_transactions": sorted(trades, key=lambda tx: (-tx["value_pln"], tx["date"], str(tx["ticker"])))[:5],
    }


def _transactions_in_period(transactions: list[dict], start: date, next_month: date) -> list[dict]:
    start_key = start.isoformat()
    end_key = next_month.isoformat()
    return [
        transaction for transaction in transactions
        if start_key <= str(transaction.get("transactionDate") or "")[:10] < end_key
    ]


def _cash_flow(transactions: list[dict]) -> Decimal:
    return _cash_flow_breakdown(transactions)["net_cash_flow_pln"]


def _cash_flow_breakdown(transactions: list[dict]) -> dict:
    deposits = ZERO
    withdrawals = ZERO
    for transaction in transactions:
        transaction_type = str(transaction.get("type") or "").upper()
        if transaction_type == "DEPOSIT":
            deposits += _transaction_value(transaction)
        elif transaction_type == "WITHDRAWAL":
            withdrawals += _transaction_value(transaction)
    return {
        "deposits_pln": _money(deposits),
        "withdrawals_pln": _money(withdrawals),
        "net_cash_flow_pln": _money(deposits - withdrawals),
    }


def _extremes(items: list[dict], transactions: list[dict], start: date, next_month: date, month_end: date) -> dict:
    ordered = _with_unit_prices(items)
    start_key = start.isoformat()
    end_key = next_month.isoformat()
    through_month = [item for item in ordered if _snapshot_date(item) < end_key]
    month_items = [item for item in through_month if _snapshot_date(item) >= start_key]
    before_month = [item for item in through_month if _snapshot_date(item) < start_key]
    if not month_items:
        return {
            "is_new_ath": False,
            "ath_date": None,
            "ath_value_pln": None,
            "days_since_ath": None,
            "max_drawdown_pct": ZERO,
            "max_drawdown_date": None,
            "start_drawdown_pct": ZERO,
            "end_drawdown_pct": ZERO,
            "trajectory_delta_pp": ZERO,
            "drawdown_trajectory_pct": [],
            "best_day": None,
            "worst_day": None,
        }

    previous_ath = max((_decimal(item.get("portfolioValue")) for item in before_month), default=Decimal("-Infinity"))
    monthly_ath_item = max(month_items, key=lambda item: _decimal(item.get("portfolioValue")))
    monthly_ath_value = _decimal(monthly_ath_item.get("portfolioValue"))
    is_new_ath = monthly_ath_value > previous_ath

    running_value_ath = Decimal("-Infinity")
    last_ath_date = None
    running_unit_ath = ZERO
    drawdowns: dict[str, Decimal] = {}
    for item in through_month:
        item_date = _snapshot_date(item)
        value = _decimal(item.get("portfolioValue"))
        if value >= running_value_ath:
            running_value_ath = value
            last_ath_date = item_date
        unit_price = _decimal(item.get("unitPrice"))
        running_unit_ath = max(running_unit_ath, unit_price)
        drawdowns[item_date] = ((unit_price / running_unit_ath) - Decimal("1")) * Decimal("100") if running_unit_ath else ZERO

    month_drawdowns = [(item, drawdowns[_snapshot_date(item)]) for item in month_items]
    max_drawdown_item, max_drawdown = min(month_drawdowns, key=lambda pair: pair[1])
    start_drawdown = month_drawdowns[0][1]
    end_drawdown = month_drawdowns[-1][1]

    cash_flow_by_date: dict[str, Decimal] = defaultdict(Decimal)
    for transaction in transactions:
        transaction_date = str(transaction.get("transactionDate") or "")[:10]
        transaction_type = str(transaction.get("type") or "").upper()
        if transaction_type == "DEPOSIT":
            cash_flow_by_date[transaction_date] += _transaction_value(transaction)
        elif transaction_type == "WITHDRAWAL":
            cash_flow_by_date[transaction_date] -= _transaction_value(transaction)

    daily_moves = []
    for index, item in enumerate(through_month):
        item_date = _snapshot_date(item)
        if item_date < start_key or index == 0:
            continue
        previous = through_month[index - 1]
        move = (
            _decimal(item.get("portfolioValue"))
            - _decimal(previous.get("portfolioValue"))
            - cash_flow_by_date.get(item_date, ZERO)
        )
        daily_moves.append({"date": item_date, "change_pln": _money(move)})

    best_day = max(daily_moves, key=lambda item: item["change_pln"]) if daily_moves else None
    worst_day = min(daily_moves, key=lambda item: item["change_pln"]) if daily_moves else None
    return {
        "is_new_ath": is_new_ath,
        "ath_date": _snapshot_date(monthly_ath_item) if is_new_ath else None,
        "ath_value_pln": _money(monthly_ath_value) if is_new_ath else None,
        "days_since_ath": (month_end - date.fromisoformat(last_ath_date)).days if last_ath_date else None,
        "max_drawdown_pct": _pct(max_drawdown),
        "max_drawdown_date": _snapshot_date(max_drawdown_item),
        "start_drawdown_pct": _pct(start_drawdown),
        "end_drawdown_pct": _pct(end_drawdown),
        "trajectory_delta_pp": _pct(end_drawdown - start_drawdown),
        "drawdown_trajectory_pct": [_pct(drawdown) for _, drawdown in month_drawdowns],
        "best_day": best_day,
        "worst_day": worst_day,
    }


def _seasonality(items: list[dict], year: int, month: int, current_twr_pct: Decimal) -> dict:
    returns = []
    for historical_year in sorted({_snapshot_date(item)[:4] for item in items if _snapshot_date(item)}):
        candidate_year = int(historical_year)
        if candidate_year >= year:
            continue
        start, next_month, _ = _month_bounds(candidate_year, month)
        performance = _monthly_performance(items, start, next_month, ZERO)
        start_snapshot, end_snapshot = _period_boundaries(items, start, next_month)
        if start_snapshot and end_snapshot:
            returns.append(performance["twr_pct"])

    positives = [value for value in returns if value > ZERO]
    negatives = [value for value in returns if value < ZERO]
    historical_average = sum(returns, ZERO) / len(returns) if returns else ZERO
    return {
        "historical_years_count": len(returns),
        "negative_years_count": len(negatives),
        "positive_years_count": len(positives),
        "avg_negative_pct": _pct(sum(negatives, ZERO) / len(negatives)) if negatives else ZERO,
        "avg_positive_pct": _pct(sum(positives, ZERO) / len(positives)) if positives else ZERO,
        "historical_average_pct": _pct(historical_average),
        "outperformed_seasonal_history": bool(returns and current_twr_pct > historical_average),
    }


def _select_primary_plan(plans: list[dict]) -> dict | None:
    active = [plan for plan in plans if plan.get("active", plan.get("isActive", True)) is not False]
    if not active:
        return None
    return next(
        (plan for plan in active if plan.get("isPrimary") is True or plan.get("primary") is True),
        active[0],
    )


def _retirement_target(user_id: str, actual_gain: Decimal) -> dict:
    plan = _select_primary_plan(retirement_plans.list_plans(user_id))
    if not plan:
        return {
            "plan_id": None,
            "monthly_target_nominal_pln": ZERO,
            "actual_nominal_gain_pln": _money(actual_gain),
            "pct_achieved": ZERO,
        }
    target = _decimal(plan.get("monthlyTargetNominalPln", plan.get("monthlyInvestment", 0)))
    achieved = (actual_gain / target) * Decimal("100") if target else ZERO
    return {
        "plan_id": plan.get("planId"),
        "monthly_target_nominal_pln": _money(target),
        "actual_nominal_gain_pln": _money(actual_gain),
        "pct_achieved": _pct(achieved),
    }


def _avco_gains(user_id: str, ledgers: dict[str, list[dict]], start: date, next_month: date) -> dict:
    realized = ZERO
    unrealized = ZERO
    start_key = start.isoformat()
    end_key = next_month.isoformat()
    for portfolio_id, transactions in ledgers.items():
        before = [tx for tx in transactions if str(tx.get("transactionDate") or "")[:10] < start_key]
        through = [tx for tx in transactions if str(tx.get("transactionDate") or "")[:10] < end_key]
        before_result = portfolio_avco.PortfolioAVCOCalculator().calculate(before)
        through_result = portfolio_avco.PortfolioAVCOCalculator().calculate(through)
        realized_before = sum((_decimal(row.get("realized_return")) for row in before_result["positions"]), ZERO)
        realized_through = sum((_decimal(row.get("realized_return")) for row in through_result["positions"]), ZERO)
        realized += realized_through - realized_before
        loaded = portfolio_avco.load_portfolio_avco(user_id, portfolio_id)
        unrealized += sum((_decimal(row.get("unrealized_return")) for row in loaded.get("active", [])), ZERO)
    return {
        "realized_pln": _money(realized),
        "unrealized_pln": _money(unrealized),
    }


def _asset_values_at_boundaries(
    user_id: str, ledgers: dict[str, list[dict]], start_date: str, end_date: str
) -> tuple[dict[str, Decimal], dict[str, Decimal], dict[str, str]]:
    start_values: dict[str, Decimal] = defaultdict(Decimal)
    end_values: dict[str, Decimal] = defaultdict(Decimal)
    names: dict[str, str] = {}

    for portfolio_id, transactions in ledgers.items():
        portfolio = portfolios.get_portfolio(user_id, portfolio_id) or {}
        currency = str(portfolio.get("currency") or "PLN")
        boundary_holdings = {
            start_date: snapshots._holdings_at_date(transactions, start_date, currency),
            end_date: snapshots._holdings_at_date(transactions, end_date, currency),
        }
        tickers = {
            str(holding.get("ticker"))
            for holdings in boundary_holdings.values() for holding in holdings
            if holding.get("ticker") and not str(holding.get("ticker")).upper().startswith("TFI:")
        }
        currencies = {
            str(holding.get("currency") or currency)
            for holdings in boundary_holdings.values() for holding in holdings
            if str(holding.get("currency") or currency) != "PLN"
        }
        try:
            price_history = snapshots._fetch_price_history_range(tickers, currencies, start_date, end_date)
        except Exception:
            price_history = {}

        for boundary_date, target in ((start_date, start_values), (end_date, end_values)):
            for holding in boundary_holdings[boundary_date]:
                ticker = str(holding.get("ticker") or holding.get("holdingId") or "CASH").upper()
                if ticker == "CASH":
                    continue
                names[ticker] = next(
                    (str(tx.get("name")) for tx in reversed(transactions) if str(tx.get("ticker") or tx.get("holdingId") or "").upper() == ticker and tx.get("name")),
                    ticker,
                )
                units = _decimal(holding.get("units"))
                purchase_value = _decimal(holding.get("purchaseValue"))
                holding_currency = str(holding.get("currency") or currency)
                if not holding.get("ticker") or ticker.startswith("TFI:"):
                    value = purchase_value
                else:
                    market_currency = snapshots._market_currency_for_asset(ticker, holding_currency)
                    price = snapshots._price_at_or_before(price_history, str(holding.get("ticker")), boundary_date)
                    fx = snapshots._price_at_or_before(price_history, f"{market_currency}PLN=X", boundary_date) if market_currency != "PLN" else Decimal("1")
                    value = units * price * fx if price is not None and fx is not None else purchase_value
                target[ticker] += value
    return dict(start_values), dict(end_values), names


def _asset_contributions(user_id: str, ledgers: dict[str, list[dict]], start: date, next_month: date) -> dict:
    start_values, end_values, names = _asset_values_at_boundaries(
        user_id, ledgers, start.isoformat(), (next_month.fromordinal(next_month.toordinal() - 1)).isoformat()
    )
    activity: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"buys": ZERO, "sells": ZERO, "dividends": ZERO})
    for transactions in ledgers.values():
        for transaction in _transactions_in_period(transactions, start, next_month):
            ticker = str(transaction.get("ticker") or transaction.get("holdingId") or "").upper()
            if not ticker:
                continue
            names[ticker] = str(transaction.get("name") or names.get(ticker) or ticker)
            transaction_type = str(transaction.get("type") or "").upper()
            if transaction_type == "BUY":
                activity[ticker]["buys"] += _transaction_value(transaction)
            elif transaction_type == "SELL":
                activity[ticker]["sells"] += _transaction_value(transaction)
            elif transaction_type == "DIVIDEND":
                activity[ticker]["dividends"] += _transaction_value(transaction)

    contributions = []
    for ticker in sorted(set(start_values) | set(end_values) | set(activity)):
        stats = activity[ticker]
        contribution = (
            end_values.get(ticker, ZERO) - start_values.get(ticker, ZERO)
            + stats["sells"] - stats["buys"] + stats["dividends"]
        )
        context_parts = []
        if stats["buys"]:
            context_parts.append(f"bought {stats['buys']:,.0f} PLN")
        if stats["sells"]:
            context_parts.append(f"sold {stats['sells']:,.0f} PLN")
        context_note = "Price move + " + " and ".join(context_parts) if context_parts else "Pure price movement, no trades"
        contributions.append({
            "ticker": ticker,
            "name": names.get(ticker, ticker),
            "net_contribution_pln": _money(contribution),
            "context_note": context_note,
        })

    if not contributions:
        return {"carry": None, "anchor": None}
    return {
        "carry": max(contributions, key=lambda item: item["net_contribution_pln"]),
        "anchor": min(contributions, key=lambda item: item["net_contribution_pln"]),
    }


def _diary_audit(user_id: str, start: date, next_month: date, month_end: date) -> dict:
    notes = diary_handler.list_notes(user_id, include_closed=True)
    start_key = start.isoformat()
    end_key = next_month.isoformat()

    def note_in_period(note: dict, period_start: str, period_end: str) -> bool:
        timestamps = {
            str(note.get(field) or "")[:10]
            for field in ("createdAt", "updatedAt", "timestamp")
            if note.get(field)
        }
        return any(period_start <= timestamp < period_end for timestamp in timestamps)

    current_count = sum(note_in_period(note, start_key, end_key) for note in notes)
    previous_counts = []
    cursor_year, cursor_month = start.year, start.month
    for _ in range(3):
        cursor_month -= 1
        if cursor_month == 0:
            cursor_year -= 1
            cursor_month = 12
        previous_start, previous_end, _ = _month_bounds(cursor_year, cursor_month)
        previous_counts.append(sum(
            note_in_period(note, previous_start.isoformat(), previous_end.isoformat()) for note in notes
        ))
    three_month_average = Decimal(sum(previous_counts)) / Decimal("3")

    checkpoint_counts = {"TRUE": 0, "FALSE": 0, "OVERDUE": 0}
    for note in notes:
        for checkpoint in note.get("hypothesis_checkpoints") or []:
            due_date = str(checkpoint.get("due_date") or "")[:10]
            if not (start_key <= due_date < end_key):
                continue
            status = str(checkpoint.get("status") or "PENDING").upper()
            if status in {"TRUE", "FALSE", "OVERDUE"}:
                checkpoint_counts[status] += 1
            elif status == "PENDING" and due_date <= month_end.isoformat():
                checkpoint_counts["OVERDUE"] += 1

    return {
        "current_month_entries": current_count,
        "three_month_avg_entries": _pct(three_month_average),
        "activity_dropped_warning": current_count < three_month_average * Decimal("0.7"),
        "checkpoints_true": checkpoint_counts["TRUE"],
        "checkpoints_false": checkpoint_counts["FALSE"],
        "checkpoints_overdue": checkpoint_counts["OVERDUE"],
    }


def _wrap_table():
    table_name = os.environ.get("WRAPS_TABLE", os.environ.get("DIARY_TABLE", "roastfolio-diary"))
    return boto3.resource("dynamodb").Table(table_name)


def _dynamodb_value(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _dynamodb_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dynamodb_value(item) for item in value]
    return value


def generate_monthly_wrap(user_id: str, year: int, month: int, *, benchmark_id: str | None = None) -> dict:
    """Compile and persist one complete monthly audit document."""
    if not str(user_id or "").strip():
        raise ValueError("user_id is required")
    start, next_month, month_end = _month_bounds(int(year), int(month))
    period_key = start.strftime("%Y-%m")

    portfolio_rows = [
        row for row in portfolios.list_portfolios(user_id)
        if row.get("portfolioId") and row.get("portfolioId") != "summary"
    ]
    ledgers = {
        str(row["portfolioId"]): portfolios.list_all_transactions(user_id, str(row["portfolioId"]), scan_forward=True)
        for row in portfolio_rows
    }
    monthly_transactions = {
        portfolio_id: _transactions_in_period(transactions, start, next_month)
        for portfolio_id, transactions in ledgers.items()
    }
    cash_flow_breakdown = _cash_flow_breakdown([
        transaction for rows in monthly_transactions.values() for transaction in rows
    ])
    total_cash_flow = cash_flow_breakdown["net_cash_flow_pln"]

    summary_snapshots = snapshots.list_snapshots(user_id, "summary", limit=5000)
    overall = _monthly_performance(summary_snapshots, start, next_month, total_cash_flow)
    wallet_performance = []
    for portfolio in portfolio_rows:
        portfolio_id = str(portfolio["portfolioId"])
        wallet_cash_flow = _cash_flow(monthly_transactions[portfolio_id])
        performance = _monthly_performance(
            snapshots.list_snapshots(user_id, portfolio_id, limit=5000), start, next_month, wallet_cash_flow
        )
        wallet_performance.append({
            "portfolio_id": portfolio_id,
            "name": portfolio.get("name") or portfolio_id,
            "cash_flow_pln": wallet_cash_flow,
            **performance,
        })

    best_wallet = max(wallet_performance, key=lambda item: item["twr_pct"], default=None)
    profit_engine = max(wallet_performance, key=lambda item: abs(item["nominal_change_pln"]), default=None)
    document = {
        "PK": f"USER#{user_id}",
        "SK": f"WRAP#MONTH#{period_key}",
        "report_type": "MONTHLY_AUDIT",
        "period": period_key,
        "year": int(year),
        "month": int(month),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cash_flow_pln": total_cash_flow,
        "deposits_pln": cash_flow_breakdown["deposits_pln"],
        "withdrawals_pln": cash_flow_breakdown["withdrawals_pln"],
        "overall_twr_pct": overall["twr_pct"],
        "overall_nominal_change_pln": overall["nominal_change_pln"],
        "start_value_pln": overall["start_value_pln"],
        "end_value_pln": overall["end_value_pln"],
        **_market_comparison(user_id, summary_snapshots, start, next_month, benchmark_id),
        "trading_activity": _trading_activity([
            transaction for rows in monthly_transactions.values() for transaction in rows
        ]),
        "wallet_performance": wallet_performance,
        "best_efficiency_wallet": best_wallet,
        "primary_profit_engine_wallet": profit_engine,
        **_extremes(
            summary_snapshots,
            [transaction for rows in ledgers.values() for transaction in rows],
            start,
            next_month,
            month_end,
        ),
        **_seasonality(summary_snapshots, int(year), int(month), overall["twr_pct"]),
        "retirement_target": _retirement_target(user_id, overall["nominal_change_pln"]),
        "avco_gains": _avco_gains(user_id, ledgers, start, next_month),
        **_asset_contributions(user_id, ledgers, start, next_month),
        "coping_diary_audit": _diary_audit(user_id, start, next_month, month_end),
    }
    document = _dynamodb_value(document)
    _wrap_table().put_item(Item=document)
    return document