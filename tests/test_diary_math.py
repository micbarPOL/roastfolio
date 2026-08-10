import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

# Ensure stable defaults for local imports.
os.environ.setdefault("AWS_REGION", "us-west-2")
os.environ.setdefault("DATA_TABLE", "roastfolio-data")
os.environ.setdefault("TRANSACTIONS_TABLE", "roastfolio-transactions")
os.environ.setdefault("SNAPSHOTS_TABLE", "roastfolio-snapshots")
os.environ.setdefault("USERS_TABLE", "roastfolio-users")

import diary_handler  # noqa: E402
import trigger_recalc  # noqa: E402


def test_parse_mentions_and_tags_ignores_trailing_punctuation():
    text = (
        "Conviction update: @xtb.wa, maybe hedge with (@AAPL)! "
        "Watch @CDR.WA... #FOMO #ValuePlay, and again @aapl?"
    )

    linked_assets, tags = diary_handler.parse_mentions_and_tags(text)

    assert linked_assets == ["XTB.WA", "AAPL", "CDR.WA"]
    assert tags == ["#FOMO", "#ValuePlay"]


def test_unjustified_trade_flag_created_without_same_day_note(monkeypatch):
    user_id = "user-42"
    portfolio_id = "xtb"

    tx = {
        "transactionId": "tx-1",
        "type": "BUY",
        "ticker": "AAPL",
        "transactionDate": "2026-08-10",
        "createdAt": "2026-08-10T09:00:00Z",
    }

    monkeypatch.setattr(trigger_recalc.portfolios, "list_all_transactions", lambda *_args, **_kwargs: [tx])
    monkeypatch.setattr(trigger_recalc.diary_handler, "list_notes", lambda *_args, **_kwargs: [])

    writes = []

    def _capture_flag(**kwargs):
        writes.append(kwargs)
        return kwargs

    monkeypatch.setattr(trigger_recalc.diary_handler, "put_unjustified_trade_flag", _capture_flag)

    created = trigger_recalc.register_unjustified_trades_for_portfolio(user_id, portfolio_id)

    assert created == 1
    assert len(writes) == 1
    assert writes[0]["user_id"] == user_id
    assert writes[0]["portfolio_id"] == portfolio_id
    assert writes[0]["ticker"] == "AAPL"
    assert writes[0]["transaction_id"] == "tx-1"


def test_hypothesis_checkpoint_normalization_and_overdue_transition():
    checkpoints = diary_handler.normalize_hypothesis_checkpoints([
        {
            "text": "Polish travel volume up 15% YoY",
            "due_date": "2026-08-01",
            "status": "PENDING",
            "resolved_at": None,
        },
        {
            "text": "Ignore invalid due date",
            "due_date": "2026-13-40",
            "status": "PENDING",
        },
        {
            "text": "Revenue guidance hit",
            "due_date": "2026-08-20",
            "status": "TRUE",
        },
    ])

    assert len(checkpoints) == 2
    assert checkpoints[0]["status"] == "PENDING"
    assert checkpoints[0]["resolved_at"] is None
    assert checkpoints[1]["status"] == "TRUE"
    assert isinstance(checkpoints[1]["resolved_at"], str)

    changed, evaluated = diary_handler.evaluate_note_checkpoints(
        {"hypothesis_checkpoints": checkpoints},
        today_ymd="2026-08-10",
    )
    assert changed is True
    assert evaluated[0]["status"] == "OVERDUE"
    assert evaluated[0]["resolved_at"] is None
    assert evaluated[1]["status"] == "TRUE"


def test_goalpost_mover_badge_activated_after_multiple_edits_in_drawdown(monkeypatch):
    user_id = "user-77"
    note_id = "XTB.WA"

    monkeypatch.setattr(trigger_recalc, "build_ticker_drawdown_map", lambda _uid: {"XTB.WA": 18})
    monkeypatch.setattr(
        trigger_recalc.diary_handler,
        "list_notes",
        lambda *_args, **_kwargs: [
            {
                "note_id": note_id,
                "linked_assets": ["XTB.WA"],
                "goalpost_mover_badge": False,
                "goalpost_change_count": 3,
                "goalpost_change_events": [
                    {"field": "exit_plan", "changed_at": "2026-08-01T10:00:00Z"},
                    {"field": "risk_factors", "changed_at": "2026-08-02T10:00:00Z"},
                    {"field": "exit_plan", "changed_at": "2026-08-03T10:00:00Z"},
                ],
            }
        ],
    )

    calls = []

    def _mark_badge(uid, nid):
        calls.append((uid, nid))
        return {"ok": True}

    monkeypatch.setattr(trigger_recalc.diary_handler, "set_goalpost_mover_badge", _mark_badge)

    flagged = trigger_recalc.apply_goalpost_mover_badge(user_id)
    assert flagged == 1
    assert calls == [(user_id, note_id)]
