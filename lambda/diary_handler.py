"""DynamoDB-backed Coping Diary (Investment Hypothesis Notebook) helpers.

Schema (single-table context):
  PK: USER#{userId}
  SK: NOTE#{noteId}

Extra records:
  SK: UNJUSTIFIED_TRADE#{timestamp}#{transactionId}

The module exposes CRUD helpers plus a small Lambda routing layer.
"""

from __future__ import annotations

import base64
import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key


_DIARY_TABLE_NAME = os.environ.get("DIARY_TABLE", os.environ.get("DATA_TABLE", "roastfolio-data"))
_diary_table_ref = None
_CHECKPOINT_STATUSES = {"PENDING", "TRUE", "FALSE", "OVERDUE"}
_TICKER_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:\.[A-Z0-9]+)?$")

_MENTION_RE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z][A-Za-z0-9.]*)")
_TAG_RE = re.compile(r"(?<![A-Za-z0-9_])#([A-Za-z][A-Za-z0-9_-]*)(?=$|[^A-Za-z0-9_-])")


def _table():
    global _diary_table_ref
    if _diary_table_ref is None:
        _diary_table_ref = boto3.resource("dynamodb").Table(_DIARY_TABLE_NAME)
    return _diary_table_ref


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pk(user_id: str) -> str:
    return f"USER#{user_id}"


def _note_sk(note_id: str) -> str:
    return f"NOTE#{note_id}"


def _coerce_bool(value, default=False) -> bool:
    if value is None:
        return default
    return bool(value)


def _uniq_keep_order(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        key = value.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _canonicalize_linked_assets(values: list[str]) -> list[str]:
    out: list[str] = []
    for raw in _uniq_keep_order(values):
        ticker = str(raw or "").strip().upper()
        if not ticker:
            continue
        base = ticker.split(".", 1)[0]
        replaced = False
        for idx, existing in enumerate(out):
            existing_base = existing.split(".", 1)[0]
            if existing_base != base:
                continue
            preferred = existing
            if "." in ticker and "." not in existing:
                preferred = ticker
            elif len(ticker) > len(existing):
                preferred = ticker
            out[idx] = preferred
            replaced = True
            break
        if not replaced:
            out.append(ticker)
    return out


def _normalize_title(payload: dict, linked_assets: list[str]) -> str:
    title = str(payload.get("title") or payload.get("topic") or payload.get("ticker") or "").strip()
    if title:
        return title
    if linked_assets:
        return linked_assets[0]
    return "Untitled note"


def parse_mentions_and_tags(text: str) -> tuple[list[str], list[str]]:
    """Extract upper-cased @ticker mentions and #hashtags from arbitrary text."""
    text = str(text or "")

    tickers = []
    for match in _MENTION_RE.finditer(text):
        ticker = str(match.group(1) or "").rstrip(".,;:!?)]}")
        if not re.match(r"^[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z0-9]+)?$", ticker):
            continue
        ticker = ticker.upper()
        tickers.append(ticker)

    tags = []
    for match in _TAG_RE.finditer(text):
        tag = "#" + match.group(1)
        tags.append(tag)

    return _uniq_keep_order(tickers), _uniq_keep_order(tags)


def _normalize_hypothesis(raw: dict | None) -> dict:
    raw = raw or {}
    return {
        "why_buy": str(raw.get("why_buy") or "").strip(),
        "exit_plan": str(raw.get("exit_plan") or "").strip(),
        "risk_factors": str(raw.get("risk_factors") or "").strip(),
    }


def _is_valid_due_date(raw: str) -> bool:
    value = str(raw or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def normalize_hypothesis_checkpoints(raw_list: list[dict] | None) -> list[dict]:
    checkpoints = []
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            continue

        text = str(raw.get("text") or "").strip()
        due_date = str(raw.get("due_date") or "").strip()
        if not text or not _is_valid_due_date(due_date):
            continue

        status = str(raw.get("status") or "PENDING").strip().upper()
        if status not in _CHECKPOINT_STATUSES:
            status = "PENDING"

        resolved_at = raw.get("resolved_at")
        if resolved_at in ("", None):
            resolved_at = None
        else:
            resolved_at = str(resolved_at)

        if status in {"TRUE", "FALSE"} and resolved_at is None:
            resolved_at = _now_iso()
        if status in {"PENDING", "OVERDUE"}:
            resolved_at = None

        checkpoints.append({
            "checkpoint_id": str(raw.get("checkpoint_id") or str(uuid.uuid4())),
            "text": text,
            "due_date": due_date,
            "status": status,
            "resolved_at": resolved_at,
        })

    return checkpoints


def normalize_comments(raw_list: list[dict] | None) -> list[dict]:
    comments = []
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            continue

        text = str(raw.get("text") or "").strip()
        if not text:
            continue

        created_at = str(raw.get("created_at") or _now_iso())
        parent_comment_id = raw.get("parent_comment_id")
        if parent_comment_id in (None, ""):
            parent_comment_id = None
        else:
            parent_comment_id = str(parent_comment_id)

        comments.append({
            "comment_id": str(raw.get("comment_id") or str(uuid.uuid4())),
            "text": text,
            "created_at": created_at,
            "author": str(raw.get("author") or "self"),
            "parent_comment_id": parent_comment_id,
        })

    comments.sort(key=lambda item: str(item.get("created_at") or ""))
    return comments


def _note_public(item: dict | None) -> dict | None:
    if not item:
        return None
    out = dict(item)
    out["note_id"] = str(out.get("SK", "")).replace("NOTE#", "", 1)
    return out


def _note_timestamp_day(note: dict) -> str:
    timestamp = str(note.get("timestamp") or note.get("updatedAt") or note.get("createdAt") or "")
    return timestamp[:10]


def _extract_note_id_from_sk(sk: str) -> str:
    sk = str(sk or "")
    if sk.startswith("NOTE#"):
        return sk.split("#", 1)[1]
    return sk


def _candidate_ticker_note_id(payload: dict, linked_assets: list[str]) -> str | None:
    if payload.get("dedicated_holding_note") and linked_assets:
        return linked_assets[0].upper()
    return None


def _normalize_note_id(raw: str) -> str:
    note_id = str(raw or "").strip()
    if not note_id:
        return note_id
    upper = note_id.upper()
    if _TICKER_ID_RE.match(upper):
        return upper
    return note_id


def create_note(user_id: str, payload: dict) -> dict:
    note_text = str(payload.get("note_text") or "")
    parsed_assets, parsed_tags = parse_mentions_and_tags(note_text)

    linked_assets = _canonicalize_linked_assets([*(payload.get("linked_assets") or []), *parsed_assets])

    user_tags = _uniq_keep_order([*(payload.get("user_tags") or []), *parsed_tags])

    ticker_note_id = _candidate_ticker_note_id(payload, linked_assets)
    note_id = _normalize_note_id(payload.get("note_id") or ticker_note_id or str(uuid.uuid4()))
    if not note_id:
        note_id = str(uuid.uuid4())

    timestamp = str(payload.get("timestamp") or _now_iso())
    hypothesis = _normalize_hypothesis(payload.get("hypothesis"))
    checkpoints = normalize_hypothesis_checkpoints(payload.get("hypothesis_checkpoints") or [])
    comments = normalize_comments(payload.get("comments") or [])
    title = _normalize_title(payload, linked_assets)

    default_active = bool(linked_assets)
    is_active = _coerce_bool(payload.get("is_active"), default=default_active)
    user_override_active = _coerce_bool(payload.get("user_override_active"), default=False)

    item = {
        "PK": _pk(user_id),
        "SK": _note_sk(note_id),
        "GSI1_PK": "ACTIVE_NOTE",
        "GSI1_SK": f"TICKER#{(linked_assets[0] if linked_assets else 'NONE')}",
        "item_type": "DIARY_NOTE",
        "title": title,
        "note_text": note_text,
        "linked_assets": linked_assets,
        "linked_assets_index": [f"TICKER#{ticker}" for ticker in linked_assets],
        "hypothesis": hypothesis,
        "hypothesis_checkpoints": checkpoints,
        "comments": comments,
        "user_tags": user_tags,
        "user_tags_index": [tag.upper() for tag in user_tags],
        "is_active": is_active,
        "user_override_active": user_override_active,
        "is_closed": _coerce_bool(payload.get("is_closed"), default=False),
        "goalpost_change_count": 0,
        "goalpost_change_events": [],
        "goalpost_mover_badge": False,
        "timestamp": timestamp,
        "createdAt": _now_iso(),
        "updatedAt": _now_iso(),
    }

    _table().put_item(Item=item)
    return _note_public(item)


def get_note(user_id: str, note_id: str) -> dict | None:
    resp = _table().get_item(Key={"PK": _pk(user_id), "SK": _note_sk(note_id)})
    return _note_public(resp.get("Item"))


def list_notes(user_id: str, include_closed: bool = False) -> list[dict]:
    resp = _table().query(
        KeyConditionExpression=Key("PK").eq(_pk(user_id)) & Key("SK").begins_with("NOTE#")
    )
    items = [_note_public(item) for item in resp.get("Items", [])]
    notes = [item for item in items if item]
    if include_closed:
        return notes
    return [note for note in notes if not _coerce_bool(note.get("is_closed"), default=False)]


def update_note(user_id: str, note_id: str, updates: dict) -> dict:
    existing = get_note(user_id, note_id)
    if not existing:
        raise ValueError("Note not found")

    now = _now_iso()
    item = dict(existing)
    changed_goalpost_fields = 0
    goalpost_events = list(item.get("goalpost_change_events") or [])

    if "note_text" in updates:
        new_text = str(updates.get("note_text") or "")
        item["note_text"] = new_text
        parsed_assets, parsed_tags = parse_mentions_and_tags(new_text)
        merged_assets = _canonicalize_linked_assets([*(updates.get("linked_assets") or item.get("linked_assets") or []), *parsed_assets])
        item["linked_assets"] = merged_assets
        item["linked_assets_index"] = [f"TICKER#{ticker}" for ticker in item["linked_assets"]]

        merged_tags = _uniq_keep_order([*(updates.get("user_tags") or item.get("user_tags") or []), *parsed_tags])
        item["user_tags"] = merged_tags
        item["user_tags_index"] = [tag.upper() for tag in merged_tags]

    if "linked_assets" in updates and "note_text" not in updates:
        merged_assets = _canonicalize_linked_assets(updates.get("linked_assets") or [])
        item["linked_assets"] = merged_assets
        item["linked_assets_index"] = [f"TICKER#{ticker}" for ticker in item["linked_assets"]]

    if "title" in updates or "topic" in updates or "ticker" in updates:
        item["title"] = _normalize_title(updates, item.get("linked_assets") or [])

    if "user_tags" in updates and "note_text" not in updates:
        merged_tags = _uniq_keep_order(updates.get("user_tags") or [])
        item["user_tags"] = merged_tags
        item["user_tags_index"] = [tag.upper() for tag in merged_tags]

    if "is_closed" in updates:
        item["is_closed"] = _coerce_bool(updates.get("is_closed"), default=False)

    if "is_active" in updates:
        item["is_active"] = _coerce_bool(updates.get("is_active"), default=False)

    if "user_override_active" in updates:
        item["user_override_active"] = _coerce_bool(updates.get("user_override_active"), default=False)

    if "timestamp" in updates:
        item["timestamp"] = str(updates.get("timestamp") or item.get("timestamp") or now)

    if "hypothesis" in updates:
        old_hypothesis = _normalize_hypothesis(item.get("hypothesis") or {})
        new_hypothesis = _normalize_hypothesis(updates.get("hypothesis") or {})

        if new_hypothesis["exit_plan"] and new_hypothesis["exit_plan"] != old_hypothesis["exit_plan"]:
            changed_goalpost_fields += 1
            goalpost_events.append({"field": "exit_plan", "changed_at": now})
        if new_hypothesis["risk_factors"] and new_hypothesis["risk_factors"] != old_hypothesis["risk_factors"]:
            changed_goalpost_fields += 1
            goalpost_events.append({"field": "risk_factors", "changed_at": now})

        merged = dict(old_hypothesis)
        merged.update({k: v for k, v in new_hypothesis.items() if v != ""})
        item["hypothesis"] = merged

    if changed_goalpost_fields:
        item["goalpost_change_count"] = int(item.get("goalpost_change_count") or 0) + changed_goalpost_fields
        item["goalpost_change_events"] = goalpost_events

    if "hypothesis_checkpoints" in updates:
        item["hypothesis_checkpoints"] = normalize_hypothesis_checkpoints(updates.get("hypothesis_checkpoints") or [])

    if "comments" in updates:
        item["comments"] = normalize_comments(updates.get("comments") or [])

    # Keep the first linked ticker as GSI sorting key for active-note scans.
    linked_assets = item.get("linked_assets") or []
    item["GSI1_SK"] = f"TICKER#{(linked_assets[0] if linked_assets else 'NONE')}"
    item["GSI1_PK"] = "ACTIVE_NOTE"
    item["updatedAt"] = now

    _table().put_item(Item=item)
    return _note_public(item)


def delete_note(user_id: str, note_id: str) -> bool:
    existing = get_note(user_id, note_id)
    if not existing:
        return False
    _table().delete_item(Key={"PK": _pk(user_id), "SK": _note_sk(note_id)})
    return True


def append_tag_to_note(user_id: str, note_id: str, tag: str) -> dict:
    note = get_note(user_id, note_id)
    if not note:
        raise ValueError("Note not found")
    tags = _uniq_keep_order([*(note.get("user_tags") or []), tag])
    return update_note(user_id, note_id, {"user_tags": tags})


def append_comment_to_note(
    user_id: str,
    note_id: str,
    text: str,
    parent_comment_id: str | None = None,
    author: str | None = None,
) -> dict:
    note = get_note(user_id, note_id)
    if not note:
        raise ValueError("Note not found")

    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("Comment text is required")

    comments = normalize_comments(note.get("comments") or [])
    comments.append({
        "comment_id": str(uuid.uuid4()),
        "text": clean_text,
        "created_at": _now_iso(),
        "author": str(author or "self"),
        "parent_comment_id": (str(parent_comment_id) if parent_comment_id else None),
    })
    comments = normalize_comments(comments)

    return update_note(user_id, note_id, {"comments": comments})


def toggle_note_active(user_id: str, note_id: str, is_active: bool) -> dict:
    note = get_note(user_id, note_id)
    if not note:
        raise ValueError("Note not found")
    return update_note(
        user_id,
        note_id,
        {
            "is_active": _coerce_bool(is_active, default=False),
            "user_override_active": True,
        },
    )


def set_goalpost_mover_badge(user_id: str, note_id: str) -> dict:
    note = get_note(user_id, note_id)
    if not note:
        raise ValueError("Note not found")

    badges = _uniq_keep_order([*(note.get("badges") or []), "GOALPOST_MOVER"])
    item = dict(note)
    item["badges"] = badges
    item["goalpost_mover_badge"] = True
    item["updatedAt"] = _now_iso()
    _table().put_item(Item=item)
    return _note_public(item)


def evaluate_note_checkpoints(note: dict, today_ymd: str | None = None) -> tuple[bool, list[dict]]:
    today = str(today_ymd or datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    checkpoints = normalize_hypothesis_checkpoints(note.get("hypothesis_checkpoints") or [])
    changed = False

    for cp in checkpoints:
        status = str(cp.get("status") or "PENDING").upper()
        due_date = str(cp.get("due_date") or "")
        if status == "PENDING" and _is_valid_due_date(due_date) and due_date < today:
            cp["status"] = "OVERDUE"
            cp["resolved_at"] = None
            changed = True

    return changed, checkpoints


def sweep_overdue_checkpoints(user_id: str, today_ymd: str | None = None) -> int:
    notes = list_notes(user_id, include_closed=True)
    updated = 0

    for note in notes:
        note_id = str(note.get("note_id") or "")
        if not note_id:
            continue

        changed, checkpoints = evaluate_note_checkpoints(note, today_ymd=today_ymd)
        if not changed:
            continue

        update_note(user_id, note_id, {"hypothesis_checkpoints": checkpoints})
        updated += 1

    return updated


def put_unjustified_trade_flag(
    user_id: str,
    ticker: str,
    transaction_id: str,
    timestamp: str,
    portfolio_id: str | None = None,
) -> dict:
    ts = str(timestamp or _now_iso())
    item = {
        "PK": _pk(user_id),
        "SK": f"UNJUSTIFIED_TRADE#{ts}#{transaction_id}",
        "item_type": "UNJUSTIFIED_TRADE_FLAG",
        "ticker": str(ticker or "").upper(),
        "transactionId": str(transaction_id or ""),
        "portfolioId": portfolio_id,
        "timestamp": ts,
        "createdAt": _now_iso(),
        "updatedAt": _now_iso(),
    }
    _table().put_item(Item=item)
    return item


def _extract_user_id(event: dict) -> str | None:
    rc = event.get("requestContext") or {}
    authorizer = rc.get("authorizer") or {}
    claims = authorizer.get("claims") or {}
    user_id = claims.get("sub")
    if user_id:
        return str(user_id)

    if event.get("userId"):
        return str(event.get("userId"))

    params = event.get("queryStringParameters") or {}
    if params.get("userId"):
        return str(params.get("userId"))

    auth_header = (event.get("headers") or {}).get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            parts = token.split(".")
            if len(parts) == 3:
                padded = parts[1] + "=" * (-len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(padded))
                user_id = payload.get("sub")
                if user_id:
                    return str(user_id)
        except Exception:
            pass

    return None


def _response(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
        },
        "body": json.dumps(payload),
    }


def lambda_handler(event, _context):
    method = str(event.get("httpMethod") or "GET").upper()
    user_id = _extract_user_id(event)
    if not user_id:
        return _response(401, {"error": "Missing user id"})

    path_params = event.get("pathParameters") or {}
    raw_note_id = path_params.get("noteId") or path_params.get("ticker")
    note_id = _normalize_note_id(raw_note_id) if raw_note_id else None
    path_lower = str(event.get("resource") or event.get("path") or "").lower()
    action = str(path_params.get("action") or path_params.get("subresource") or "").lower()

    if method == "OPTIONS":
        return _response(200, {"ok": True})

    try:
        body = event.get("body")
        payload = json.loads(body) if body else {}
    except Exception:
        return _response(400, {"error": "Invalid JSON body"})

    try:
        is_comment_endpoint = action == "comment" or path_lower.endswith("/comment")
        is_toggle_endpoint = action == "toggle-active" or path_lower.endswith("/toggle-active")

        if method == "POST" and is_comment_endpoint and note_id:
            updated = append_comment_to_note(
                user_id=user_id,
                note_id=note_id,
                text=payload.get("text") or payload.get("comment") or "",
                parent_comment_id=payload.get("parent_comment_id"),
                author=payload.get("author"),
            )
            return _response(200, {"note": updated})

        if method == "POST" and is_toggle_endpoint and note_id:
            if "is_active" not in payload:
                raise ValueError("is_active is required")
            updated = toggle_note_active(user_id, note_id, payload.get("is_active"))
            return _response(200, {"note": updated})

        if method == "POST":
            created = create_note(user_id, payload)
            return _response(201, {"note": created})

        if method == "GET" and note_id:
            note = get_note(user_id, note_id)
            if not note:
                return _response(404, {"error": "Note not found"})
            return _response(200, {"note": note})

        if method == "GET":
            include_closed = str((event.get("queryStringParameters") or {}).get("includeClosed", "false")).lower() == "true"
            notes = list_notes(user_id, include_closed=include_closed)
            return _response(200, {"notes": notes})

        if method in {"PUT", "PATCH"} and note_id:
            updated = update_note(user_id, note_id, payload)
            return _response(200, {"note": updated})

        if method == "DELETE" and note_id:
            deleted = delete_note(user_id, note_id)
            if not deleted:
                return _response(404, {"error": "Note not found"})
            return _response(200, {"deleted": True})

        return _response(405, {"error": "Method not allowed"})
    except ValueError as exc:
        return _response(400, {"error": str(exc)})
    except Exception as exc:
        return _response(500, {"error": f"Diary handler failed: {exc}"})
