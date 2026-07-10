"""
lambda/db.py — DynamoDB user-profile helpers for Roastfolio

Table: roastfolio-users
  PK:  userId  (Cognito sub — stable UUID for the lifetime of the account)

Schema example
--------------
{
  "userId":    "a1b2c3d4-...",          # Cognito sub
  "email":     "you@example.com",       # from Cognito idToken claim
  "nickname":  "WarrenFromWarsaw",      # mutable display name
  "createdAt": "2026-05-11T17:00:00Z",  # ISO-8601 UTC, set once
  "updatedAt": "2026-05-11T18:30:00Z",  # updated on every write

  "settings": {
    "theme":           "dark",          # "dark" | "light" | "auto"
    "currency":        "PLN",           # display currency for totals
    "defaultWallet":   "Emerytura",     # which gauge to show first
    "notifications":   false            # push / email notifications
  },

  "portfolioMeta": {
    "wallets":     ["Emerytura", "XTB", "IKE", "IKZE"],
    "lastSyncAt":  "2026-05-11T18:00:00Z",
    "totalValuePLN": 95420.50
  },

  "subscription": {
    "tier":             "free",         # "free" | "premium"
    "validUntil":       null,           # ISO-8601 or null for free
    "stripeCustomerId": null            # future Stripe integration
  }
}

GSI1  email-index
  PK: email  →  projects userId + nickname
  Use: admin dedup, email existence check
"""

import os
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone

_TABLE_NAME = os.environ.get("USERS_TABLE", "roastfolio-users")
_dynamodb    = None   # lazy singleton


def _table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb").Table(_TABLE_NAME)
    return _dynamodb


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Default structures ────────────────────────────────────────────────────────

ROLES = ("BASIC", "ADVANCED")
ROLE_BASIC    = "BASIC"
ROLE_ADVANCED = "ADVANCED"
_ADVANCED_ROLE_EMAILS = {
    email.strip().lower()
    for email in os.environ.get("ADVANCED_USER_EMAILS", "michal.bardadyn@gmail.com").split(",")
    if email.strip()
}

# ── Benchmark registry ────────────────────────────────────────
# Scalable catalogue of supported benchmark indices.
# Add new entries here — no other backend changes needed.
BENCHMARKS = {
    "WIG": {
        "id":          "WIG",
        "name":        "WIG",
        "ticker":      "WIG.WA",
        "currency":    "PLN",
        "exchange":    "Warsaw Stock Exchange",
        "description": "Polish broad-market index",
    },
    "WIG20": {
        "id":          "WIG20",
        "name":        "WIG20",
        "ticker":      "WIG20.WA",
        "currency":    "PLN",
        "exchange":    "Warsaw Stock Exchange",
        "description": "Top 20 Polish companies",
    },
    "MWIG40": {
        "id":          "MWIG40",
        "name":        "mWIG40",
        "ticker":      "mWIG40.WA",
        "currency":    "PLN",
        "exchange":    "Warsaw Stock Exchange",
        "description": "Medium Polish companies",
    },
    "SWIG80": {
        "id":          "SWIG80",
        "name":        "sWIG80",
        "ticker":      "sWIG80.WA",
        "currency":    "PLN",
        "exchange":    "Warsaw Stock Exchange",
        "description": "Small Polish companies",
    },
    "SP500": {
        "id":          "SP500",
        "name":        "S&P 500",
        "ticker":      "^GSPC",
        "currency":    "USD",
        "exchange":    "NYSE",
        "description": "US large-cap benchmark",
    },
    "NASDAQ": {
        "id":          "NASDAQ",
        "name":        "NASDAQ",
        "ticker":      "^IXIC",
        "currency":    "USD",
        "exchange":    "NASDAQ",
        "description": "US technology-heavy benchmark",
    },
    "DAX": {
        "id":          "DAX",
        "name":        "DAX",
        "ticker":      "^GDAXI",
        "currency":    "EUR",
        "exchange":    "Xetra",
        "description": "German blue-chip benchmark",
    },
    "MSCI_WORLD": {
        "id":          "MSCI_WORLD",
        "name":        "MSCI World",
        "ticker":      "IWDA.AS",
        "currency":    "USD",
        "exchange":    "Euronext Amsterdam",
        "description": "Global equity benchmark",
    },
}
DEFAULT_BENCHMARK = "WIG"


def _default_settings() -> dict:
    return {
        "theme":         "dark",
        "currency":      "PLN",
        "defaultWallet": "Emerytura",
        "notifications": False,
        "benchmark":     DEFAULT_BENCHMARK,
        "roastIntensity": "sarcastic",
    }


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _default_role_for_email(email: str) -> str:
    return ROLE_ADVANCED if _normalize_email(email) in _ADVANCED_ROLE_EMAILS else ROLE_BASIC


def _default_subscription() -> dict:
    return {
        "tier":             "free",
        "validUntil":       None,
        "stripeCustomerId": None,
    }


def _default_portfolio_meta() -> dict:
    return {
        "wallets":       ["Emerytura", "XTB", "IKE", "IKZE"],
        "lastSyncAt":    None,
        "totalValuePLN": None,
    }


# ── CRUD ──────────────────────────────────────────────────────────────────────

def get_user(user_id: str) -> dict | None:
    """
    Fetch a user profile by userId (Cognito sub).
    Returns the item dict or None if not found.

    Lambda example:
        from db import get_user
        profile = get_user(user_id)
        if profile is None:
            return _resp(404, {"error": "User not found"})
    """
    resp = _table().get_item(Key={"userId": user_id})
    return resp.get("Item")


def list_users() -> list[dict]:
    items = []
    kwargs = {}
    while True:
        resp = _table().scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


def create_user(user_id: str, email: str, nickname: str) -> dict:
    """
    Create a new user profile on first login.
    Idempotent via condition expression — safe to call on every login.

    Returns the created item.
    Raises ResourceInUseException if the user already exists
    (caller should catch ConditionalCheckFailedException and fall through).

    Lambda example:
        from db import create_user
        try:
            profile = create_user(user_id, email, nickname)
        except client.exceptions.ConditionalCheckFailedException:
            profile = get_user(user_id)   # already exists
    """
    now = _now_iso()
    normalized_email = _normalize_email(email)
    item = {
        "userId":        user_id,
        "email":         normalized_email,
        "nickname":      nickname,
        "role":          _default_role_for_email(normalized_email),
        "createdAt":     now,
        "updatedAt":     now,
        "settings":      _default_settings(),
        "portfolioMeta": _default_portfolio_meta(),
        "subscription":  _default_subscription(),
    }
    # condition_expression ensures we never overwrite an existing profile
    _table().put_item(
        Item=item,
        ConditionExpression="attribute_not_exists(userId)",
    )
    return item


def get_or_create_user(user_id: str, email: str, nickname: str) -> dict:
    """
    Fetch profile; create it if it doesn't exist yet.
    Ideal for the first-login upsert pattern.

    Lambda example:
        from db import get_or_create_user
        profile = get_or_create_user(user_id, email, nickname)
    """
    profile = get_user(user_id)
    if profile is not None:
        if _default_role_for_email(email) == ROLE_ADVANCED and profile.get("role") != ROLE_ADVANCED:
            return set_user_role(user_id, ROLE_ADVANCED)
        return profile
    try:
        return create_user(user_id, email, nickname)
    except Exception:
        # Race condition — another invocation created it just now
        return get_user(user_id)


def update_user(user_id: str, updates: dict) -> dict:
    """
    Partial update: only the keys in `updates` are written.
    Allowed top-level keys: nickname, settings, portfolioMeta, subscription, role, favorites.
    Raises ValueError for forbidden keys (userId, email, createdAt).

    Lambda example:
        from db import update_user
        profile = update_user(user_id, {
            "nickname": "NewName",
            "settings": {"theme": "light", "currency": "PLN",
                         "defaultWallet": "XTB", "notifications": True}
        })
    """
    IMMUTABLE = {"userId", "email", "createdAt"}
    ALLOWED   = {"nickname", "settings", "portfolioMeta", "subscription", "role", "favorites"}

    bad = set(updates.keys()) & IMMUTABLE
    if bad:
        raise ValueError(f"Cannot update immutable fields: {bad}")

    unknown = set(updates.keys()) - ALLOWED
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    if not updates:
        return get_user(user_id)

    updates["updatedAt"] = _now_iso()

    # Build UpdateExpression dynamically
    set_parts  = []
    expr_names  = {}
    expr_values = {}

    for i, (k, v) in enumerate(updates.items()):
        placeholder = f"#f{i}"
        value_key   = f":v{i}"
        set_parts.append(f"{placeholder} = {value_key}")
        expr_names[placeholder]  = k
        expr_values[value_key]   = v

    resp = _table().update_item(
        Key={"userId": user_id},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ConditionExpression="attribute_exists(userId)",
        ReturnValues="ALL_NEW",
    )
    return resp.get("Attributes", {})


def delete_user(user_id: str) -> bool:
    """
    Hard-delete a user profile.
    Returns True if deleted, False if user didn't exist.

    Lambda example:
        from db import delete_user
        if not delete_user(user_id):
            return _resp(404, {"error": "User not found"})
    """
    try:
        _table().delete_item(
            Key={"userId": user_id},
            ConditionExpression="attribute_exists(userId)",
        )
        return True
    except Exception:
        return False


def get_user_by_email(email: str) -> dict | None:
    """
    Look up a user by email via GSI1 (email-index).
    Returns the projected item { userId, email, nickname } or None.

    Lambda example:
        from db import get_user_by_email
        hit = get_user_by_email("user@example.com")
    """
    resp = _table().query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email),
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def get_user_role(user_id: str) -> str:
    """Return the user's role (BASIC or ADVANCED), defaulting to BASIC if not set."""
    user = get_user(user_id)
    if not user:
        return ROLE_BASIC
    return user.get("role", ROLE_BASIC)


def set_user_role(user_id: str, role: str) -> dict:
    """Set user role. role must be one of ROLES."""
    if role not in ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of {ROLES}")
    return update_user(user_id, {"role": role})


# ── Favorites management ────────────────────────────────────────────────────

def get_favorites(user_id: str) -> list:
    """
    Get user's favorite tickers for analysis screen.
    Returns list of favorite objects: [{"ticker": "AAPL", "name": "Apple Inc.", "addedAt": "2026-06-16T10:00:00Z"}, ...]
    """
    user = get_user(user_id)
    if not user:
        return []
    return user.get("favorites", [])


def set_favorites(user_id: str, favorites: list) -> dict:
    """
    Set user's favorites list.
    favorites: list of dicts with ticker, name, addedAt
    """
    return update_user(user_id, {"favorites": favorites})
