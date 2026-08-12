import os
import sys
import base64
import json
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


def test_toggle_active_sets_user_override(monkeypatch):
    user_id = "user-toggle"
    note_id = "CRI.WA"

    monkeypatch.setattr(
        diary_handler,
        "get_note",
        lambda uid, nid: {"PK": f"USER#{uid}", "SK": f"NOTE#{nid}", "note_id": nid} if uid == user_id and nid == note_id else None,
    )

    captured = {}

    def _capture_update(uid, nid, updates):
        captured["uid"] = uid
        captured["nid"] = nid
        captured["updates"] = dict(updates)
        return {"note_id": nid, **updates}

    monkeypatch.setattr(diary_handler, "update_note", _capture_update)

    updated = diary_handler.toggle_note_active(user_id, note_id, False)
    assert updated["note_id"] == note_id
    assert captured["uid"] == user_id
    assert captured["nid"] == note_id
    assert captured["updates"] == {
        "is_active": False,
        "user_override_active": True,
    }


def test_sync_active_flags_respects_manual_override_and_zero_balance(monkeypatch):
    user_id = "user-sweep"

    monkeypatch.setattr(
        trigger_recalc.portfolios,
        "list_portfolios",
        lambda _uid: [{"portfolioId": "p1"}],
    )
    monkeypatch.setattr(
        trigger_recalc.portfolios,
        "list_holdings",
        lambda _uid, _pid: [{"ticker": "AAPL", "units": 3}],
    )

    monkeypatch.setattr(
        trigger_recalc.diary_handler,
        "list_notes",
        lambda *_args, **_kwargs: [
            {
                "note_id": "AAPL",
                "is_active": False,
                "user_override_active": False,
            },
            {
                "note_id": "MSFT",
                "is_active": True,
                "user_override_active": False,
            },
            {
                "note_id": "TSLA",
                "is_active": True,
                "user_override_active": True,
            },
        ],
    )

    updates = []

    def _capture_update(uid, note_id, payload):
        updates.append((uid, note_id, dict(payload)))
        return {"note_id": note_id, **payload}

    monkeypatch.setattr(trigger_recalc.diary_handler, "update_note", _capture_update)

    changed = trigger_recalc.sync_diary_active_flags_with_holdings(user_id)

    assert changed == 2
    assert (user_id, "AAPL", {"is_active": True, "user_override_active": False}) in updates
    assert (user_id, "MSFT", {"is_active": False, "user_override_active": False}) in updates
    assert all(item[1] != "TSLA" for item in updates)


def test_append_comment_keeps_chronological_order(monkeypatch):
    user_id = "user-comments"
    note_id = "XTB.WA"
    state = {
        "note": {
            "PK": f"USER#{user_id}",
            "SK": f"NOTE#{note_id}",
            "note_id": note_id,
            "comments": [
                {
                    "comment_id": "c0",
                    "text": "earliest",
                    "created_at": "2026-08-01T00:00:00Z",
                    "author": "self",
                    "parent_comment_id": None,
                }
            ],
        }
    }

    monkeypatch.setattr(diary_handler, "get_note", lambda _uid, _nid: dict(state["note"]))
    monkeypatch.setattr(diary_handler, "_now_iso", lambda: "2026-08-02T00:00:00Z")

    def _capture_update(_uid, _nid, updates):
        merged = dict(state["note"])
        merged["comments"] = updates["comments"]
        state["note"] = merged
        return merged

    monkeypatch.setattr(diary_handler, "update_note", _capture_update)

    diary_handler.append_comment_to_note(user_id, note_id, "second")
    monkeypatch.setattr(diary_handler, "_now_iso", lambda: "2026-08-03T00:00:00Z")
    diary_handler.append_comment_to_note(user_id, note_id, "third")

    comments = state["note"]["comments"]
    assert [c["text"] for c in comments] == ["earliest", "second", "third"]
    assert [c["created_at"] for c in comments] == [
        "2026-08-01T00:00:00Z",
        "2026-08-02T00:00:00Z",
        "2026-08-03T00:00:00Z",
    ]


def test_extract_user_id_from_authorization_header():
    payload = {"sub": "user-from-jwt", "email": "demo@example.com"}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    token = f"header.{encoded}.signature"

    user_id = diary_handler._extract_user_id({"headers": {"Authorization": f"Bearer {token}"}})

    assert user_id == "user-from-jwt"


def test_create_note_uses_generated_id_for_regular_ticker_notes(monkeypatch):
    saved = {}

    class _FakeTable:
        def put_item(self, Item):
            saved["item"] = dict(Item)

    monkeypatch.setattr(diary_handler, "_table", lambda: _FakeTable())
    monkeypatch.setattr(diary_handler.uuid, "uuid4", lambda: "generated-note-id")
    monkeypatch.setattr(diary_handler, "_now_iso", lambda: "2026-08-12T00:00:00Z")

    note = diary_handler.create_note("user-1", {
        "ticker": "CRI",
        "linked_assets": ["CRI"],
        "note_text": "First thesis",
    })

    assert note["note_id"] == "generated-note-id"
    assert note["title"] == "CRI"
    assert saved["item"]["SK"] == "NOTE#generated-note-id"
    assert saved["item"]["linked_assets"] == ["CRI"]


def test_create_note_keeps_ticker_id_for_dedicated_holding_notes(monkeypatch):
    saved = {}

    class _FakeTable:
        def put_item(self, Item):
            saved["item"] = dict(Item)

    monkeypatch.setattr(diary_handler, "_table", lambda: _FakeTable())
    monkeypatch.setattr(diary_handler, "_now_iso", lambda: "2026-08-12T00:00:00Z")

    note = diary_handler.create_note("user-1", {
        "ticker": "CRI",
        "linked_assets": ["CRI"],
        "note_text": "Single holding note",
        "dedicated_holding_note": True,
    })

    assert note["note_id"] == "CRI"
    assert saved["item"]["SK"] == "NOTE#CRI"


def test_create_note_prefers_more_specific_market_ticker(monkeypatch):
    saved = {}

    class _FakeTable:
        def put_item(self, Item):
            saved["item"] = dict(Item)

    monkeypatch.setattr(diary_handler, "_table", lambda: _FakeTable())
    monkeypatch.setattr(diary_handler.uuid, "uuid4", lambda: "generated-note-id")
    monkeypatch.setattr(diary_handler, "_now_iso", lambda: "2026-08-12T00:00:00Z")

    note = diary_handler.create_note("user-1", {
        "title": "CRI",
        "linked_assets": ["CRI"],
        "note_text": "Watching @CRI.WA closely",
    })

    assert note["title"] == "CRI"
    assert saved["item"]["linked_assets"] == ["CRI.WA"]
