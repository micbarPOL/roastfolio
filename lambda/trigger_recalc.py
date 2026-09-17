"""Recalculation sweep with diary automation rules.

Rules implemented:
  1) Missing same-day ticker note for BUY/SELL => UNJUSTIFIED_TRADE flag
  2) Linked ticker drawdown above threshold => auto-tag note with #Coping
  3) >2 goalpost edits during drawdown => activate GOALPOST_MOVER badge
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re

import boto3

import db
import diary_handler
import portfolios
import snapshots
import wrap_generator


_DEFAULT_REGION = os.environ.get("AWS_REGION", "us-west-2")
os.environ["AWS_REGION"] = _DEFAULT_REGION
os.environ.setdefault("DATA_TABLE", "roastfolio-data")
os.environ.setdefault("TRANSACTIONS_TABLE", "roastfolio-transactions")
os.environ.setdefault("SNAPSHOTS_TABLE", "roastfolio-snapshots")
os.environ.setdefault("USERS_TABLE", "roastfolio-users")

_TICKER_NOTE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:\.[A-Z0-9]+)?$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


def _ticker_day_keys_from_notes(notes: list[dict]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for note in notes:
        day = str(note.get("timestamp") or note.get("updatedAt") or note.get("createdAt") or "")[:10]
        if not day:
            continue
        for ticker in note.get("linked_assets") or []:
            t = str(ticker or "").strip().upper()
            if t:
                keys.add((t, day))
    return keys


def detect_unjustified_trades(transactions: list[dict], notes: list[dict]) -> list[dict]:
    """Return BUY/SELL transactions that have no same-day note for the same ticker."""
    note_keys = _ticker_day_keys_from_notes(notes)
    unjustified = []
    for tx in transactions:
        tx_type = str(tx.get("type") or "").upper()
        if tx_type not in {"BUY", "SELL"}:
            continue
        ticker = str(tx.get("ticker") or "").strip().upper()
        tx_day = str(tx.get("transactionDate") or tx.get("createdAt") or "")[:10]
        if not ticker or not tx_day:
            continue
        if (ticker, tx_day) not in note_keys:
            unjustified.append(tx)
    return unjustified


def register_unjustified_trades_for_portfolio(user_id: str, portfolio_id: str) -> int:
    transactions = portfolios.list_all_transactions(user_id, portfolio_id, scan_forward=True)
    notes = diary_handler.list_notes(user_id, include_closed=True)
    unjustified = detect_unjustified_trades(transactions, notes)

    created = 0
    for tx in unjustified:
        tx_id = str(tx.get("transactionId") or "")
        if not tx_id:
            continue
        ticker = str(tx.get("ticker") or "").upper()
        timestamp = str(tx.get("createdAt") or f"{tx.get('transactionDate')}T00:00:00Z" or _now_iso())
        diary_handler.put_unjustified_trade_flag(
            user_id=user_id,
            ticker=ticker,
            transaction_id=tx_id,
            timestamp=timestamp,
            portfolio_id=portfolio_id,
        )
        created += 1
    return created


def _portfolio_drawdown_from_twr_unit_price(user_id: str, portfolio_id: str) -> Decimal:
    history = snapshots.list_snapshots(user_id, portfolio_id, limit=5000)
    if not history:
        return Decimal("0")

    latest = max(history, key=lambda item: str(item.get("snapshotDate") or ""))
    current_unit = _to_decimal(latest.get("unitPrice") or 0)
    if current_unit <= 0:
        return Decimal("0")

    max_unit = max((_to_decimal(snap.get("unitPrice") or 0) for snap in history), default=Decimal("0"))
    if max_unit <= 0 or current_unit >= max_unit:
        return Decimal("0")

    return ((max_unit - current_unit) / max_unit) * Decimal("100")


def build_ticker_drawdown_map(user_id: str) -> dict[str, Decimal]:
    """Approximate per-ticker drawdown by inheriting portfolio-level TWR drawdown."""
    drawdown_by_ticker: dict[str, Decimal] = {}
    for portfolio in portfolios.list_portfolios(user_id):
        portfolio_id = portfolio.get("portfolioId")
        if not portfolio_id or portfolio_id == "summary":
            continue

        drawdown = _portfolio_drawdown_from_twr_unit_price(user_id, portfolio_id)
        if drawdown <= 0:
            continue

        for holding in portfolios.list_holdings(user_id, portfolio_id):
            ticker = str(holding.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            prev = drawdown_by_ticker.get(ticker, Decimal("0"))
            if drawdown > prev:
                drawdown_by_ticker[ticker] = drawdown
    return drawdown_by_ticker


def apply_coping_autotag(user_id: str, drawdown_threshold_pct: Decimal = Decimal("15")) -> int:
    drawdowns = build_ticker_drawdown_map(user_id)
    if not drawdowns:
        return 0

    updated = 0
    for note in diary_handler.list_notes(user_id, include_closed=False):
        note_id = str(note.get("note_id") or "")
        if not note_id:
            continue

        linked_assets = [str(t).strip().upper() for t in note.get("linked_assets") or [] if str(t).strip()]
        if not linked_assets:
            continue

        exceeded = any(drawdowns.get(ticker, Decimal("0")) > drawdown_threshold_pct for ticker in linked_assets)
        if not exceeded:
            continue

        existing_tags = [str(t) for t in note.get("user_tags") or []]
        if any(tag.lower() == "#coping" for tag in existing_tags):
            continue

        diary_handler.append_tag_to_note(user_id, note_id, "#Coping")
        updated += 1
    return updated


def apply_goalpost_mover_badge(user_id: str) -> int:
    drawdowns = build_ticker_drawdown_map(user_id)
    if not drawdowns:
        return 0

    flagged = 0
    for note in diary_handler.list_notes(user_id, include_closed=False):
        note_id = str(note.get("note_id") or "")
        if not note_id:
            continue

        if bool(note.get("goalpost_mover_badge")):
            continue

        events = list(note.get("goalpost_change_events") or [])
        changes = int(note.get("goalpost_change_count") or len(events) or 0)
        if changes <= 2:
            continue

        # Require at least 3 retroactive edits to exit/risk fields before awarding badge.
        tracked_fields = {
            str(event.get("field") or "")
            for event in events
            if isinstance(event, dict)
        }
        if events and not ({"exit_plan", "risk_factors"} & tracked_fields):
            continue

        linked_assets = [str(t).strip().upper() for t in note.get("linked_assets") or [] if str(t).strip()]
        if not linked_assets:
            continue

        drawdown_active = any(drawdowns.get(ticker, Decimal("0")) > Decimal("0") for ticker in linked_assets)
        if not drawdown_active:
            continue

        diary_handler.set_goalpost_mover_badge(user_id, note_id)
        flagged += 1
    return flagged


def _ticker_balances_from_holdings(user_id: str) -> dict[str, Decimal]:
    balances: dict[str, Decimal] = {}
    for portfolio in portfolios.list_portfolios(user_id):
        portfolio_id = portfolio.get("portfolioId")
        if not portfolio_id or portfolio_id == "summary":
            continue
        for holding in portfolios.list_holdings(user_id, portfolio_id):
            ticker = str(holding.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            units = _to_decimal(holding.get("units", 0))
            balances[ticker] = balances.get(ticker, Decimal("0")) + units
    return balances


def sync_diary_active_flags_with_holdings(user_id: str) -> int:
    balances = _ticker_balances_from_holdings(user_id)
    updated = 0

    for note in diary_handler.list_notes(user_id, include_closed=True):
        note_id = str(note.get("note_id") or "").strip().upper()
        if not note_id or not _TICKER_NOTE_ID_RE.match(note_id):
            continue

        user_override = bool(note.get("user_override_active", False))
        if user_override:
            continue

        should_be_active = balances.get(note_id, Decimal("0")) > Decimal("0")
        current_active = bool(note.get("is_active", should_be_active))
        if current_active == should_be_active:
            continue

        diary_handler.update_note(
            user_id,
            note_id,
            {
                "is_active": should_be_active,
                "user_override_active": False,
            },
        )
        updated += 1

    return updated


def sweep_user(user_id: str) -> dict:
    user_portfolios = portfolios.list_portfolios(user_id)

    unjustified_total = 0
    portfolios_recalculated = 0
    summary_recalculated = 0
    overdue_checkpoints_marked = diary_handler.sweep_overdue_checkpoints(user_id)
    active_flags_synced = sync_diary_active_flags_with_holdings(user_id)

    for portfolio in user_portfolios:
        portfolio_id = portfolio.get("portfolioId")
        if not portfolio_id:
            continue

        snaps = snapshots.list_snapshots(user_id, portfolio_id)
        if snaps:
            first_date = min(s["snapshotDate"] for s in snaps)
            snapshots.recalculate_portfolio_snapshots_from_date(user_id, portfolio_id, first_date)
            portfolios_recalculated += 1

        unjustified_total += register_unjustified_trades_for_portfolio(user_id, portfolio_id)

    summary_snaps = snapshots.list_snapshots(user_id, "summary")
    if summary_snaps:
        first_date = min(s["snapshotDate"] for s in summary_snaps)
        snapshots.recalculate_summary_snapshots_from_date(user_id, first_date)
        summary_recalculated += 1

    coping_tagged = apply_coping_autotag(user_id)
    goalpost_badges = apply_goalpost_mover_badge(user_id)

    return {
        "userId": user_id,
        "portfoliosRecalculated": portfolios_recalculated,
        "summaryRecalculated": summary_recalculated,
        "overdueCheckpointsMarked": overdue_checkpoints_marked,
        "unjustifiedTradesFlagged": unjustified_total,
        "copingTagsAdded": coping_tagged,
        "goalpostBadgesActivated": goalpost_badges,
        "activeFlagsSynced": active_flags_synced,
    }


def generate_previous_month_wraps(
    now: datetime | None = None,
    user_ids: list[str] | None = None,
    force: bool = False,
) -> list[dict]:
    """Compile the preceding month's audit for every user on day one."""
    run_at = now or datetime.now(timezone.utc)
    if run_at.day != 1 and not force:
        return []

    previous_month_last_day = run_at.date().replace(day=1) - timedelta(days=1)
    if user_ids is None:
        table = boto3.resource("dynamodb").Table(os.environ["USERS_TABLE"])
        response = table.scan(ProjectionExpression="userId")
        users = response.get("Items", [])
        while response.get("LastEvaluatedKey"):
            response = table.scan(
                ProjectionExpression="userId",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            users.extend(response.get("Items", []))
        user_ids = [str(item["userId"]) for item in users if item.get("userId")]

    results = []
    for user_id in user_ids:
        try:
            document = wrap_generator.generate_monthly_wrap(
                user_id,
                previous_month_last_day.year,
                previous_month_last_day.month,
            )
            try:
                import email_service
                user_profile = db.get_user(user_id)
                if user_profile:
                    email_service.send_monthly_recap_email_if_enabled(user_profile, document)
            except Exception as mail_exc:
                print(f"Monthly wrap email notification failed for {user_id}: {mail_exc}")
            results.append({"userId": user_id, "period": document["period"], "status": "ok"})
        except Exception as exc:
            print(f"Monthly wrap failed for {user_id}: {exc}")
            results.append({"userId": user_id, "period": previous_month_last_day.strftime("%Y-%m"), "status": "error", "error": str(exc)})
    return results


def monthly_wrap_handler(event, _context):
    event = event or {}
    # This Lambda is not an HTTP handler. Only IAM-authorized scheduler/API
    # Lambda invocations may enter it; malformed events must never scan users.
    if not isinstance(event, dict) or "requestContext" in event or "httpMethod" in event:
        raise ValueError("Trusted Lambda invocation required")
    if event.get("action") == "recalculate":
        if set(event) - {"action", "user_id", "job_id"}:
            raise ValueError("Unexpected recalculation fields")
        import monthly_recalculation
        return monthly_recalculation.run_job(event, _context)
    if event.get("action") == "recalculate_snapshots":
        allowed_keys = {"action", "user_id", "portfolio_id", "from_date", "is_cash_only", "old_transaction", "new_transaction"}
        if set(event) - allowed_keys:
            raise ValueError("Unexpected recalculate_snapshots fields")
        user_id = str(event.get("user_id") or "").strip()
        portfolio_id = str(event.get("portfolio_id") or "").strip()
        from_date = str(event.get("from_date") or "").strip()[:10]
        if not user_id or not portfolio_id or not from_date:
            raise ValueError("user_id, portfolio_id, and from_date are required")
        is_cash_only = bool(event.get("is_cash_only", False))
        old_tx = event.get("old_transaction")
        new_tx = event.get("new_transaction")
        port_res = snapshots.recalculate_portfolio_snapshots_from_date(
            user_id,
            portfolio_id,
            from_date,
            is_cash_only=is_cash_only,
            old_transaction=old_tx,
            new_transaction=new_tx,
        )
        summary_res = snapshots.recalculate_summary_snapshots_from_date(user_id, from_date)
        return {
            "statusCode": 200,
            "portfolioRecalculated": port_res,
            "summaryRecalculated": summary_res,
        }
    if event.get("action") != "scheduled" or set(event) - {"action", "asOfDate", "force"}:
        raise ValueError("Explicit scheduled or user-scoped recalculate action required")
    as_of_raw = str(event.get("asOfDate") or "").strip()
    run_at = datetime.fromisoformat(as_of_raw.replace("Z", "+00:00")) if as_of_raw else datetime.now(timezone.utc)
    results = generate_previous_month_wraps(run_at, force=bool(event.get("force", False)))
    return {
        "statusCode": 200,
        "generated": sum(result["status"] == "ok" for result in results),
        "failed": sum(result["status"] == "error" for result in results),
        "results": results,
    }


def run() -> list[dict]:
    results = []
    table = boto3.resource("dynamodb").Table(os.environ["USERS_TABLE"])
    response = table.scan()
    users = response.get("Items", [])

    for item in users:
        user_id = item.get("userId")
        if not user_id:
            continue
        try:
            result = sweep_user(user_id)
            results.append(result)
            print(f"Sweep done for {user_id}: {result}")
        except Exception as exc:
            print(f"Sweep failed for {user_id}: {exc}")

    return results


if __name__ == "__main__":
    run()
