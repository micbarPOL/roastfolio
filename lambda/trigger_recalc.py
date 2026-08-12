"""Recalculation sweep with diary automation rules.

Rules implemented:
  1) Missing same-day ticker note for BUY/SELL => UNJUSTIFIED_TRADE flag
  2) Linked ticker drawdown above threshold => auto-tag note with #Coping
  3) >2 goalpost edits during drawdown => activate GOALPOST_MOVER badge
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
import re

import boto3

import db
import diary_handler
import portfolios
import snapshots


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
