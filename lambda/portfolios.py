"""
lambda/portfolios.py — DynamoDB portfolios, holdings snapshots, and transaction ledger.

Data table (roastfolio-data):
  PK = userId (Cognito sub)
  SK = PORTFOLIO#<portfolioId> | HOLDING#<portfolioId>#<holdingId>

Transactions table (roastfolio-transactions):
  PK = userId (Cognito sub)
  SK = PORTFOLIO#<portfolioId>#TX#<yyyy-mm-dd>#<transactionId>

Current-state holdings are DERIVED snapshots maintained from BUY/SELL transactions.
The transaction ledger is the source of truth.
"""

import os
import re
import uuid
import math
import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from datetime import datetime, timezone
from decimal import Decimal


def _to_decimal(value) -> Decimal:
    """Convert float/int/str to Decimal for DynamoDB storage."""
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


_DATA_TABLE_NAME = os.environ.get("DATA_TABLE", "roastfolio-data")
_TRANSACTIONS_TABLE_NAME = os.environ.get("TRANSACTIONS_TABLE", "roastfolio-transactions")
_data_table = None
_transactions_table_ref = None
_ddb_client = None
_serializer = TypeSerializer()
_EPSILON = Decimal("0.00000001")
_TRANSACTION_TYPES = {"BUY", "SELL", "DEPOSIT", "WITHDRAWAL", "DIVIDEND", "SPINOFF", "EXTRA_COST", "CASH_ADJUSTMENT"}
_TRANSACTION_TYPES_MESSAGE = "BUY, SELL, DEPOSIT, WITHDRAWAL, DIVIDEND, SPINOFF, EXTRA_COST, or CASH_ADJUSTMENT"
_CASH_HOLDING_ID = "__cash__"
_CASH_HOLDING_NAME = "Cash"
_MARKET_CURRENCY_BY_TICKER = {
    "BTC-USD": "USD",
    "ETH-USD": "USD",
    "META": "USD",
}


def _table():
    global _data_table
    if _data_table is None:
        _data_table = boto3.resource("dynamodb").Table(_DATA_TABLE_NAME)
    return _data_table


def _transactions_table():
    global _transactions_table_ref
    if _transactions_table_ref is None:
        _transactions_table_ref = boto3.resource("dynamodb").Table(_TRANSACTIONS_TABLE_NAME)
    return _transactions_table_ref


def _client():
    global _ddb_client
    if _ddb_client is None:
        _ddb_client = boto3.client("dynamodb")
    return _ddb_client


def _serialize_item(item: dict) -> dict:
    return {k: _serializer.serialize(v) for k, v in item.items() if v is not None}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _portfolio_sk(portfolio_id: str) -> str:
    return f"PORTFOLIO#{portfolio_id}"


def _holding_sk(portfolio_id: str, holding_id: str) -> str:
    return f"HOLDING#{portfolio_id}#{holding_id}"


def _transaction_sk(portfolio_id: str, transaction_date: str, transaction_id: str) -> str:
    return f"PORTFOLIO#{portfolio_id}#TX#{transaction_date}#{transaction_id}"


def _safe_id(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", raw.strip()).lower()[:64]


def _normalize_transaction_date(raw) -> str:
    if raw in (None, ""):
        return _today()
    raw = str(raw).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        date_str = raw
    elif "T" in raw:
        date_str = raw.split("T", 1)[0]
    else:
        raise ValueError("transactionDate must be YYYY-MM-DD")

    if date_str > _today():
        raise ValueError("transactionDate cannot be in the future")
    return date_str


# ── Portfolios ────────────────────────────────────────────────────────────────

def list_portfolios(user_id: str) -> list[dict]:
    resp = _table().query(
        KeyConditionExpression=Key("userId").eq(user_id) & Key("sk").begins_with("PORTFOLIO#")
    )
    items = resp.get("Items", [])
    for it in items:
        it.pop("userId", None)
        it.pop("sk", None)
    return sorted(items, key=lambda x: x.get("order", 999))


def get_portfolio(user_id: str, portfolio_id: str) -> dict | None:
    resp = _table().get_item(Key={"userId": user_id, "sk": _portfolio_sk(portfolio_id)})
    item = resp.get("Item")
    if item:
        item.pop("userId", None)
        item.pop("sk", None)
    return item


def put_portfolio(user_id: str, portfolio: dict) -> dict:
    portfolio_id = _safe_id(portfolio.get("portfolioId") or portfolio.get("name", ""))
    if not portfolio_id:
        raise ValueError("portfolioId or name is required")

    now = _now()
    item = {
        "userId": user_id,
        "sk": _portfolio_sk(portfolio_id),
        "portfolioId": portfolio_id,
        "name": str(portfolio.get("name", portfolio_id)).strip()[:80],
        "type": portfolio.get("type", "real"),
        "currency": portfolio.get("currency", "PLN"),
        "color": portfolio.get("color", "#4a9fd4"),
        "order": int(portfolio.get("order", 99)),
        "updatedAt": now,
    }

    existing = get_portfolio(user_id, portfolio_id)
    item["createdAt"] = (existing or {}).get("createdAt", now)

    _table().put_item(Item=item)
    item.pop("userId")
    item.pop("sk")
    return item


def delete_portfolio(user_id: str, portfolio_id: str) -> bool:
    existing = get_portfolio(user_id, portfolio_id)
    if not existing:
        return False

    holdings = list_holdings(user_id, portfolio_id)
    transactions = list_transactions(user_id, portfolio_id, limit=1000)

    with _table().batch_writer() as batch:
        for h in holdings:
            batch.delete_item(Key={
                "userId": user_id,
                "sk": _holding_sk(portfolio_id, h["holdingId"]),
            })
        batch.delete_item(Key={"userId": user_id, "sk": f"AVCO#{portfolio_id}"})
        batch.delete_item(Key={"userId": user_id, "sk": _portfolio_sk(portfolio_id)})

    with _transactions_table().batch_writer() as batch:
        for tx in transactions:
            batch.delete_item(Key={
                "userId": user_id,
                "sk": _transaction_sk(portfolio_id, tx["transactionDate"], tx["transactionId"]),
            })
    try:
        import snapshots
        snapshots.delete_portfolio_history(user_id, portfolio_id)
    except Exception as e:
        print(f"Snapshot cleanup skipped for {portfolio_id}: {e}")
    return True


def clear_portfolio_ledger(user_id: str, portfolio_id: str) -> None:
    holdings = list_holdings(user_id, portfolio_id)
    transactions = list_transactions(user_id, portfolio_id, limit=5000)

    with _table().batch_writer() as batch:
        for h in holdings:
            batch.delete_item(Key={
                "userId": user_id,
                "sk": _holding_sk(portfolio_id, h["holdingId"]),
            })
        batch.delete_item(Key={"userId": user_id, "sk": f"AVCO#{portfolio_id}"})

    with _transactions_table().batch_writer() as batch:
        for tx in transactions:
            batch.delete_item(Key={
                "userId": user_id,
                "sk": _transaction_sk(portfolio_id, tx["transactionDate"], tx["transactionId"]),
            })
    try:
        import snapshots
        snapshots.delete_portfolio_history(user_id, portfolio_id)
    except Exception as e:
        print(f"Snapshot cleanup skipped for {portfolio_id}: {e}")


# ── Holdings snapshots ────────────────────────────────────────────────────────

def _get_holding_raw(user_id: str, portfolio_id: str, holding_id: str) -> dict | None:
    resp = _table().get_item(Key={"userId": user_id, "sk": _holding_sk(portfolio_id, holding_id)})
    return resp.get("Item")


def _list_holdings_raw(user_id: str, portfolio_id: str) -> list[dict]:
    prefix = f"HOLDING#{portfolio_id}#"
    resp = _table().query(
        KeyConditionExpression=Key("userId").eq(user_id) & Key("sk").begins_with(prefix)
    )
    return resp.get("Items", [])


def list_holdings(user_id: str, portfolio_id: str) -> list[dict]:
    items = _list_holdings_raw(user_id, portfolio_id)
    for it in items:
        it.pop("userId", None)
        it.pop("sk", None)
    return sorted(items, key=lambda x: x.get("name", ""))


def put_holding_snapshot(user_id: str, portfolio_id: str, holding: dict) -> dict:
    holding_id = _safe_id(holding.get("holdingId") or holding.get("name") or holding.get("ticker") or "")
    if not holding_id:
        raise ValueError("holdingId, name, or ticker is required")
    units = _to_decimal(holding.get("units", 0))
    purchase_value = _to_decimal(holding.get("purchaseValue", 0))
    if units <= 0:
        raise ValueError("units must be greater than 0")
    item = {
        "userId": user_id,
        "sk": _holding_sk(portfolio_id, holding_id),
        "portfolioId": portfolio_id,
        "holdingId": holding_id,
        "name": str(holding.get("name") or holding.get("ticker") or holding_id).strip()[:120],
        "ticker": holding.get("ticker") or None,
        "currency": holding.get("currency", "PLN"),
        "units": units,
        "purchaseValue": purchase_value,
        "updatedAt": _now(),
    }
    _table().put_item(Item=item)
    return _holding_public(item)


def replace_holdings_snapshots(user_id: str, portfolio_id: str, holdings: list[dict]) -> list[dict]:
    existing = _list_holdings_raw(user_id, portfolio_id)
    with _table().batch_writer() as batch:
        for item in existing:
            batch.delete_item(Key={"userId": user_id, "sk": item["sk"]})
    with _table().batch_writer() as batch:
        for holding in holdings:
            holding_id = _safe_id(holding.get("holdingId") or holding.get("name") or holding.get("ticker") or "")
            if not holding_id:
                continue
            units = _to_decimal(holding.get("units", 0))
            if units <= 0:
                continue
            batch.put_item(Item={
                "userId": user_id,
                "sk": _holding_sk(portfolio_id, holding_id),
                "portfolioId": portfolio_id,
                "holdingId": holding_id,
                "name": str(holding.get("name") or holding.get("ticker") or holding_id).strip()[:120],
                "ticker": holding.get("ticker") or None,
                "currency": holding.get("currency", "PLN"),
                "units": units,
                "purchaseValue": _to_decimal(holding.get("purchaseValue", 0)),
                "updatedAt": _now(),
            })
    return list_holdings(user_id, portfolio_id)


def list_all_holdings(user_id: str) -> list[dict]:
    resp = _table().query(
        KeyConditionExpression=Key("userId").eq(user_id) & Key("sk").begins_with("HOLDING#")
    )
    items = resp.get("Items", [])
    for it in items:
        it.pop("userId", None)
        it.pop("sk", None)
    return items


def _resolve_existing_holding(user_id: str, portfolio_id: str, holding_id=None, ticker=None, name=None):
    holdings = _list_holdings_raw(user_id, portfolio_id)
    ticker_norm = (ticker or "").strip().upper()
    name_norm = (name or "").strip().lower()

    if holding_id:
        for h in holdings:
            if h.get("holdingId") == holding_id:
                return h
    if ticker_norm:
        for h in holdings:
            if str(h.get("ticker") or "").strip().upper() == ticker_norm:
                return h
    if name_norm:
        for h in holdings:
            if str(h.get("name") or "").strip().lower() == name_norm:
                return h
    return None


def _holding_public(item: dict | None) -> dict | None:
    if not item:
        return None
    item = dict(item)
    item.pop("userId", None)
    item.pop("sk", None)
    return item


# ── Transaction ledger ────────────────────────────────────────────────────────

def list_transactions(user_id: str, portfolio_id: str, limit: int = 200) -> list[dict]:
    prefix = f"PORTFOLIO#{portfolio_id}#TX#"
    resp = _transactions_table().query(
        KeyConditionExpression=Key("userId").eq(user_id) & Key("sk").begins_with(prefix),
        ScanIndexForward=False,
        Limit=limit,
    )
    items = resp.get("Items", [])
    for it in items:
        it.pop("userId", None)
        it.pop("sk", None)
    return items


def list_all_transactions(user_id: str, portfolio_id: str, scan_forward: bool = True) -> list[dict]:
    prefix = f"PORTFOLIO#{portfolio_id}#TX#"
    query_kwargs = {
        "KeyConditionExpression": Key("userId").eq(user_id) & Key("sk").begins_with(prefix),
        "ScanIndexForward": scan_forward,
    }
    items = []
    response = _transactions_table().query(**query_kwargs)
    items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        response = _transactions_table().query(
            **query_kwargs,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    for it in items:
        it.pop("userId", None)
        it.pop("sk", None)
    return items


def calculate_investment_total(user_id: str, portfolio_id: str) -> Decimal:
    total = Decimal("0")
    for tx in list_all_transactions(user_id, portfolio_id, scan_forward=True):
        tx_type = str(tx.get("type") or "").upper()
        value = _to_decimal(tx.get("value", 0))
        if tx_type == "DEPOSIT":
            total += value
        elif tx_type == "WITHDRAWAL":
            total -= value
    return total


def rebuild_holdings_from_transactions(user_id: str, portfolio_id: str) -> list[dict]:
    portfolio = get_portfolio(user_id, portfolio_id)
    if not portfolio:
        raise ValueError("Portfolio not found")

    transactions = list_all_transactions(user_id, portfolio_id, scan_forward=True)
    holdings: dict[str, dict] = {}
    cash_balance = Decimal("0")
    portfolio_currency = str(portfolio.get("currency") or "PLN")

    for tx in transactions:
        tx_type = str(tx.get("type") or "").upper()
        value = _to_decimal(tx.get("value", 0))
        quantity = _to_decimal(tx.get("quantity", 0)) if tx.get("quantity") not in (None, "") else Decimal("0")
        holding_id = str(tx.get("holdingId") or _safe_id(str(tx.get("name") or tx.get("ticker") or "transaction")))
        ticker = tx.get("ticker")
        holding_currency = _MARKET_CURRENCY_BY_TICKER.get(str(ticker or "").upper(), tx.get("currency") or portfolio_currency)

        if tx_type in {"BUY", "SPINOFF"}:
            current = holdings.get(holding_id, {
                "holdingId": holding_id,
                "name": tx.get("name") or tx.get("ticker") or holding_id,
                "ticker": ticker,
                "currency": holding_currency,
                "units": Decimal("0"),
                "purchaseValue": Decimal("0"),
            })
            current["name"] = tx.get("name") or current["name"]
            current["ticker"] = ticker or current.get("ticker")
            current["currency"] = holding_currency
            current["units"] += quantity
            current["purchaseValue"] += value
            holdings[holding_id] = current
            if tx_type == "BUY":
                cash_balance -= value
        elif tx_type == "SELL":
            current = holdings.get(holding_id)
            if not current:
                cash_balance += value
                continue
            old_units = _to_decimal(current.get("units", 0))
            old_purchase_value = _to_decimal(current.get("purchaseValue", 0))
            if old_units <= 0:
                cash_balance += value
                continue
            sell_units = min(quantity, old_units)
            avg_cost = old_purchase_value / old_units if old_units > 0 else Decimal("0")
            new_units = old_units - sell_units
            new_purchase_value = old_purchase_value - (avg_cost * sell_units)
            if abs(new_units) < _EPSILON:
                holdings.pop(holding_id, None)
            else:
                current["units"] = new_units
                current["purchaseValue"] = Decimal("0") if abs(new_purchase_value) < _EPSILON else new_purchase_value
                holdings[holding_id] = current
            cash_balance += value
        elif tx_type == "DEPOSIT":
            cash_balance += value
        elif tx_type == "WITHDRAWAL":
            cash_balance -= value
        elif tx_type == "DIVIDEND":
            cash_balance += value
        elif tx_type == "CASH_ADJUSTMENT":
            cash_balance += value
        elif tx_type == "EXTRA_COST":
            cash_balance -= value

    next_holdings = []
    for item in holdings.values():
        units = _to_decimal(item.get("units", 0))
        if units <= 0:
            continue
        next_holdings.append({
            "holdingId": item["holdingId"],
            "name": item["name"],
            "ticker": item.get("ticker"),
            "currency": item.get("currency") or portfolio_currency,
            "units": units,
            "purchaseValue": _to_decimal(item.get("purchaseValue", 0)),
        })
    if abs(cash_balance) >= _EPSILON:
        next_holdings.append({
            "holdingId": _CASH_HOLDING_ID,
            "name": _CASH_HOLDING_NAME,
            "ticker": None,
            "currency": portfolio_currency,
            "units": cash_balance,
            "purchaseValue": cash_balance,
        })
    return replace_holdings_snapshots(user_id, portfolio_id, next_holdings)


def _cash_holding_candidates(user_id: str, portfolio_id: str) -> list[dict]:
    holdings = _list_holdings_raw(user_id, portfolio_id)
    matches = []
    for item in holdings:
        if item.get("holdingId") == _CASH_HOLDING_ID:
            return [item]
        if item.get("ticker") not in (None, ""):
            continue
        name = str(item.get("name") or "").strip().lower()
        if "cash" in name or "got" in name or "konto" in name:
            matches.append(item)
    return matches


def _get_cash_holding_raw(user_id: str, portfolio_id: str) -> dict | None:
    matches = _cash_holding_candidates(user_id, portfolio_id)
    return matches[0] if matches else None


def _cash_balance(item: dict | None) -> Decimal:
    if not item:
        return Decimal("0")
    units = _to_decimal(item.get("units", 0))
    purchase_value = _to_decimal(item.get("purchaseValue", 0))
    return units if abs(units) >= _EPSILON else purchase_value


def _cash_holding_item(user_id: str, portfolio_id: str, currency: str, balance: Decimal, now: str, existing: dict | None) -> dict:
    holding_id = (existing or {}).get("holdingId") or _CASH_HOLDING_ID
    return {
        "userId": user_id,
        "sk": _holding_sk(portfolio_id, holding_id),
        "portfolioId": portfolio_id,
        "holdingId": holding_id,
        "name": _CASH_HOLDING_NAME,
        "ticker": None,
        "currency": currency,
        "units": balance,
        "purchaseValue": balance,
        "updatedAt": now,
    }


def _transaction_value(tx_type: str, transaction: dict, quantity: Decimal | None, price: Decimal | None, commission: Decimal,
                       affect_cash: bool) -> Decimal:
    raw_value = transaction.get("value")
    if raw_value not in (None, ""):
        value = _to_decimal(raw_value)
        if tx_type == "BUY":
            value = value + commission
        elif tx_type == "SELL":
            value = value - commission
        elif tx_type == "DIVIDEND":
            tax = _to_decimal(transaction.get("tax", 0))
            value = value - commission - tax
    elif tx_type in {"DEPOSIT", "WITHDRAWAL"}:
        fallback = transaction.get("amount", transaction.get("quantity"))
        value = _to_decimal(fallback)
    elif not affect_cash:
        if tx_type == "BUY":
            if transaction.get("purchaseValue") not in (None, ""):
                value = _to_decimal(transaction.get("purchaseValue")) + commission
            elif quantity is not None and price is not None:
                value = quantity * price + commission
            else:
                value = Decimal("0")
        else:
            if quantity is not None and price is not None:
                value = (quantity * price) - commission
            else:
                value = Decimal("0")
    else:
        raise ValueError("value is required for BUY and SELL transactions")

    if tx_type == "SPINOFF" and value == 0:
        return value
    if value <= 0:
        raise ValueError("value must be greater than 0")
    return value


def _derived_price(tx_type: str, quantity: Decimal | None, price: Decimal | None, value: Decimal, commission: Decimal) -> Decimal | None:
    if price is not None or quantity is None or quantity <= 0:
        return price
    gross_value = value - commission if tx_type == "BUY" else value + commission
    if gross_value < 0:
        raise ValueError("value must be greater than or equal to commission")
    return gross_value / quantity


def _tx_public(item: dict) -> dict:
    public_tx = dict(item)
    public_tx.pop("userId", None)
    public_tx.pop("sk", None)
    return public_tx


def update_transaction(user_id: str, portfolio_id: str, transaction_id: str, updates: dict) -> dict:
    portfolio = get_portfolio(user_id, portfolio_id)
    if not portfolio:
        raise ValueError("Portfolio not found")

    transaction_id = str(transaction_id or "").strip()
    if not transaction_id:
        raise ValueError("transactionId is required")

    existing = None
    for tx in list_all_transactions(user_id, portfolio_id, scan_forward=True):
        if str(tx.get("transactionId") or "") == transaction_id:
            existing = tx
            break
    if not existing:
        raise ValueError("Transaction not found")

    updates = updates or {}
    tx_type = str(existing.get("type") or updates.get("type") or "BUY").strip().upper()
    if tx_type not in _TRANSACTION_TYPES:
        raise ValueError(f"type must be {_TRANSACTION_TYPES_MESSAGE}")

    is_cash_tx = tx_type in {"DEPOSIT", "WITHDRAWAL", "EXTRA_COST", "CASH_ADJUSTMENT"}
    requires_quantity = tx_type in {"BUY", "SELL", "DIVIDEND", "SPINOFF"}
    old_date = _normalize_transaction_date(existing.get("transactionDate"))
    transaction_date = _normalize_transaction_date(updates.get("transactionDate", old_date))

    quantity = None
    if requires_quantity:
        quantity_raw = updates.get("quantity", updates.get("units", existing.get("quantity", 0)))
        quantity = _to_decimal(quantity_raw)
        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")

    price_raw = updates.get("price", existing.get("price"))
    price = None if price_raw in (None, "") else _to_decimal(price_raw)
    if price is not None and price < 0:
        raise ValueError("price cannot be negative")

    commission = _to_decimal(updates.get("commission", existing.get("commission", 0)))
    if commission < 0:
        raise ValueError("commission cannot be negative")
    tax = _to_decimal(updates.get("tax", existing.get("tax", 0)))
    if tax < 0:
        raise ValueError("tax cannot be negative")

    if is_cash_tx:
        holding_id = existing.get("holdingId") or _CASH_HOLDING_ID
        name = _CASH_HOLDING_NAME
        ticker = None
        currency = updates.get("currency") or existing.get("currency") or portfolio.get("currency", "PLN")
    else:
        asset_name = str(updates.get("asset") or "").strip()
        name = str(
            updates.get("name")
            or asset_name
            or existing.get("name")
            or updates.get("ticker")
            or existing.get("ticker")
            or existing.get("holdingId")
            or ""
        ).strip()[:120]
        ticker = updates.get("ticker", existing.get("ticker"))
        ticker = str(ticker).strip() if ticker not in (None, "") else None
        holding_id = str(
            updates.get("holdingId")
            or existing.get("holdingId")
            or _safe_id(name or ticker or "")
        ).strip()
        if not holding_id:
            raise ValueError("holdingId, name, or ticker is required")
        currency = updates.get("currency") or existing.get("currency") or portfolio.get("currency", "PLN")

    raw_value = updates.get("value") if "value" in updates else None
    if raw_value not in (None, ""):
        value = _to_decimal(raw_value)
    elif tx_type == "BUY" and quantity is not None and price is not None:
        value = quantity * price + commission
    elif tx_type == "SELL" and quantity is not None and price is not None:
        value = quantity * price - commission
    elif tx_type == "DIVIDEND" and quantity is not None and price is not None:
        value = quantity * price - commission - tax
    else:
        value = _to_decimal(existing.get("value", 0))

    if tx_type == "SPINOFF" and value == 0:
        pass
    elif value <= 0:
        raise ValueError("value must be greater than 0")

    if tx_type in {"BUY", "SELL"}:
        price = _derived_price(tx_type, quantity, price, value, commission)

    now = _now()
    tx_item = dict(existing)
    tx_item.update({
        "userId": user_id,
        "sk": _transaction_sk(portfolio_id, transaction_date, transaction_id),
        "transactionId": transaction_id,
        "portfolioId": portfolio_id,
        "holdingId": holding_id,
        "type": tx_type,
        "ticker": ticker,
        "name": name,
        "currency": currency,
        "quantity": quantity,
        "price": price,
        "value": value,
        "commission": commission,
        "tax": tax,
        "transactionDate": transaction_date,
        "createdAt": existing.get("createdAt") or now,
        "updatedAt": now,
    })
    if "comment" in updates:
        tx_item["comment"] = str(updates.get("comment") or "").strip()[:300]

    old_sk = _transaction_sk(portfolio_id, old_date, transaction_id)
    new_sk = tx_item["sk"]
    transact_items = []
    if old_sk != new_sk:
        transact_items.append({
            "Delete": {
                "TableName": _TRANSACTIONS_TABLE_NAME,
                "Key": _serialize_item({"userId": user_id, "sk": old_sk}),
            }
        })
    transact_items.append({
        "Put": {
            "TableName": _TRANSACTIONS_TABLE_NAME,
            "Item": _serialize_item(tx_item),
        }
    })
    _client().transact_write_items(TransactItems=transact_items)
    holdings = rebuild_holdings_from_transactions(user_id, portfolio_id)

    return {
        "transaction": _tx_public(tx_item),
        "holdings": holdings,
        "recalculateFrom": min(old_date, transaction_date),
    }


def record_transaction(user_id: str, portfolio_id: str, transaction: dict) -> dict:
    portfolio = get_portfolio(user_id, portfolio_id)
    if not portfolio:
        raise ValueError("Portfolio not found")

    tx_type = str(transaction.get("type", "BUY")).strip().upper()
    if tx_type not in _TRANSACTION_TYPES:
        raise ValueError(f"type must be {_TRANSACTION_TYPES_MESSAGE}")

    is_cash_tx = tx_type in {"DEPOSIT", "WITHDRAWAL", "EXTRA_COST", "CASH_ADJUSTMENT"}
    affect_cash = bool(transaction.get("affectCash", True))
    modifies_holding = tx_type in {"BUY", "SELL", "SPINOFF"}
    requires_quantity = tx_type in {"BUY", "SELL", "DIVIDEND", "SPINOFF"}

    quantity = None
    if requires_quantity:
        quantity = _to_decimal(transaction.get("quantity", transaction.get("units", 0)))
        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")

    price = None if transaction.get("price") in (None, "") else _to_decimal(transaction.get("price"))
    if price is not None and price < 0:
        raise ValueError("price cannot be negative")

    commission = _to_decimal(transaction.get("commission", 0))
    if commission < 0:
        raise ValueError("commission cannot be negative")
    tax = _to_decimal(transaction.get("tax", 0))
    if tax < 0:
        raise ValueError("tax cannot be negative")

    comment = str(transaction.get("comment", "")).strip()[:300]
    transaction_date = _normalize_transaction_date(transaction.get("transactionDate"))
    provided_transaction_id = str(transaction.get("transactionId") or "").strip()[:80]
    if provided_transaction_id:
        existing_tx = _transactions_table().get_item(Key={
            "userId": user_id,
            "sk": _transaction_sk(portfolio_id, transaction_date, provided_transaction_id),
        }).get("Item")
        if existing_tx:
            return _tx_public(existing_tx)

    existing = None
    cash_existing = _get_cash_holding_raw(user_id, portfolio_id)
    if is_cash_tx:
        holding_id = (cash_existing or {}).get("holdingId") or _CASH_HOLDING_ID
        name = _CASH_HOLDING_NAME
        ticker = None
        currency = transaction.get("currency") or (cash_existing or {}).get("currency") or portfolio.get("currency", "PLN")
    else:
        existing = _resolve_existing_holding(
            user_id,
            portfolio_id,
            holding_id=transaction.get("holdingId"),
            ticker=transaction.get("ticker"),
            name=transaction.get("name"),
        )

        if tx_type == "SELL" and not existing:
            raise ValueError("Holding not found for SELL transaction")

        holding_id = (existing or {}).get("holdingId") or _safe_id(
            str(transaction.get("holdingId") or transaction.get("name") or transaction.get("ticker") or "")
        )
        if not holding_id:
            raise ValueError("holdingId, name, or ticker is required")

        name = str(
            transaction.get("name")
            or (existing or {}).get("name")
            or transaction.get("ticker")
            or holding_id
        ).strip()[:120]
        ticker = transaction.get("ticker") or (existing or {}).get("ticker") or None
        currency = transaction.get("currency") or (existing or {}).get("currency") or portfolio.get("currency", "PLN")

    value = _transaction_value(tx_type, transaction, quantity, price, commission, affect_cash)
    price = _derived_price(tx_type, quantity, price, value, commission)

    old_units = _to_decimal((existing or {}).get("units", 0))
    old_purchase_value = _to_decimal((existing or {}).get("purchaseValue", 0))

    derived_holding = None
    stock_holding_public = None

    if modifies_holding:
        if tx_type == "BUY":
            new_units = old_units + quantity
            new_purchase_value = old_purchase_value + value
        elif tx_type == "SPINOFF":
            new_units = old_units + quantity
            new_purchase_value = old_purchase_value + value
        else:
            if quantity - old_units > _EPSILON:
                raise ValueError("Insufficient quantity for SELL transaction")
            avg_cost = (old_purchase_value / old_units) if old_units > 0 else Decimal("0")
            reduced_basis = avg_cost * quantity
            new_units = old_units - quantity
            if abs(new_units) < _EPSILON:
                new_units = Decimal("0")
            new_purchase_value = old_purchase_value - reduced_basis
            if new_purchase_value < 0 or abs(new_purchase_value) < _EPSILON:
                new_purchase_value = Decimal("0")

    now = _now()
    transaction_id = provided_transaction_id or str(uuid.uuid4())
    tx_item = {
        "userId": user_id,
        "sk": _transaction_sk(portfolio_id, transaction_date, transaction_id),
        "transactionId": transaction_id,
        "portfolioId": portfolio_id,
        "holdingId": holding_id,
        "type": tx_type,
        "ticker": ticker,
        "name": name,
        "currency": currency,
        "quantity": quantity,
        "price": price,
        "value": value,
        "commission": commission,
        "tax": tax,
        "comment": comment,
        "transactionDate": transaction_date,
        "createdAt": now,
        "importSource": transaction.get("importSource"),
        "importVersion": transaction.get("importVersion"),
        "sourceOperation": transaction.get("sourceOperation"),
    }

    transact_items = [{
        "Put": {
            "TableName": _TRANSACTIONS_TABLE_NAME,
            "Item": _serialize_item(tx_item),
        }
    }]

    if modifies_holding:
        if new_units > 0:
            derived_holding = {
                "userId": user_id,
                "sk": _holding_sk(portfolio_id, holding_id),
                "portfolioId": portfolio_id,
                "holdingId": holding_id,
                "name": name,
                "ticker": ticker,
                "currency": currency,
                "units": new_units,
                "purchaseValue": new_purchase_value,
                "updatedAt": now,
            }
            transact_items.append({
                "Put": {
                    "TableName": _DATA_TABLE_NAME,
                    "Item": _serialize_item(derived_holding),
                }
            })
        elif existing:
            transact_items.append({
                "Delete": {
                    "TableName": _DATA_TABLE_NAME,
                    "Key": _serialize_item({"userId": user_id, "sk": _holding_sk(portfolio_id, holding_id)}),
                }
            })
        stock_holding_public = _holding_public(derived_holding)

    auto_cash_tx = None
    if affect_cash or is_cash_tx or tx_type == "DIVIDEND":
        cash_currency = (cash_existing or {}).get("currency") or portfolio.get("currency", "PLN")
        current_cash = _cash_balance(cash_existing)
        cash_delta = Decimal("0")
        if tx_type == "BUY":
            cash_delta = -value
        elif tx_type == "SELL":
            cash_delta = value
        elif tx_type == "DEPOSIT":
            cash_delta = value
        elif tx_type == "WITHDRAWAL":
            cash_delta = -value
        elif tx_type == "DIVIDEND":
            cash_delta = value
        elif tx_type == "CASH_ADJUSTMENT":
            cash_delta = value
        elif tx_type == "EXTRA_COST":
            cash_delta = -value

        auto_add_cash = bool(transaction.get("autoAddCash")) and tx_type == "BUY"
        deposit_amount = Decimal("0")
        if tx_type == "BUY" and current_cash + cash_delta < -_EPSILON:
            if not auto_add_cash:
                raise ValueError("Insufficient cash balance for BUY transaction")
            deposit_amount = value - current_cash
            if deposit_amount < 0:
                deposit_amount = Decimal("0")
        elif tx_type in {"WITHDRAWAL", "EXTRA_COST"} and current_cash + cash_delta < -_EPSILON:
            raise ValueError(f"Insufficient cash balance for {tx_type} transaction")

        next_cash = current_cash + deposit_amount + cash_delta
        if abs(next_cash) < _EPSILON:
            next_cash = Decimal("0")
        if next_cash < 0:
            raise ValueError("Cash balance cannot become negative")

        if deposit_amount > 0:
            auto_cash_tx_id = str(uuid.uuid4())
            auto_cash_tx = {
                "userId": user_id,
                "sk": _transaction_sk(portfolio_id, transaction_date, auto_cash_tx_id),
                "transactionId": auto_cash_tx_id,
                "portfolioId": portfolio_id,
                "holdingId": (cash_existing or {}).get("holdingId") or _CASH_HOLDING_ID,
                "type": "DEPOSIT",
                "ticker": None,
                "name": _CASH_HOLDING_NAME,
                "currency": cash_currency,
                "quantity": None,
                "price": None,
                "value": deposit_amount,
                "commission": Decimal("0"),
                "comment": f"Auto cash top-up before buying {name}",
                "transactionDate": transaction_date,
                "createdAt": now,
                "automatic": True,
            }
            transact_items.insert(0, {
                "Put": {
                    "TableName": _TRANSACTIONS_TABLE_NAME,
                    "Item": _serialize_item(auto_cash_tx),
                }
            })

        if next_cash > 0:
            cash_holding = _cash_holding_item(user_id, portfolio_id, cash_currency, next_cash, now, cash_existing)
            transact_items.append({
                "Put": {
                    "TableName": _DATA_TABLE_NAME,
                    "Item": _serialize_item(cash_holding),
                }
            })
        elif cash_existing:
            transact_items.append({
                "Delete": {
                    "TableName": _DATA_TABLE_NAME,
                    "Key": _serialize_item({
                        "userId": user_id,
                        "sk": _holding_sk(portfolio_id, cash_existing.get("holdingId") or _CASH_HOLDING_ID),
                    }),
                }
            })

    _client().transact_write_items(TransactItems=transact_items)

    public_tx = _tx_public(tx_item)
    public_tx["holding"] = stock_holding_public
    if auto_cash_tx:
        public_tx["autoCashTransaction"] = _tx_public(auto_cash_tx)
    return public_tx


# ── Legacy compatibility wrappers ─────────────────────────────────────────────

def put_holding(user_id: str, portfolio_id: str, holding: dict) -> dict:
    """Legacy upsert compatibility: convert desired holding state into BUY/SELL ledger entries."""
    name = str(holding.get("name", "")).strip()
    ticker = holding.get("ticker") or None
    existing = _resolve_existing_holding(
        user_id,
        portfolio_id,
        holding_id=holding.get("holdingId"),
        ticker=ticker,
        name=name,
    )

    desired_units = _to_decimal(holding.get("units", 0))
    desired_purchase_value = _to_decimal(holding.get("purchaseValue", 0))
    if desired_units <= 0:
        raise ValueError("units must be greater than 0")

    current_units = _to_decimal((existing or {}).get("units", 0))
    current_purchase_value = _to_decimal((existing or {}).get("purchaseValue", 0))
    delta_units = desired_units - current_units

    if abs(delta_units) < _EPSILON:
        return _holding_public(existing) or {
            "portfolioId": portfolio_id,
            "holdingId": _safe_id(holding.get("holdingId") or name or ticker or ""),
            "name": name,
            "ticker": ticker,
            "currency": holding.get("currency", "PLN"),
            "units": desired_units,
            "purchaseValue": desired_purchase_value,
            "updatedAt": _now(),
        }

    if delta_units > 0:
        delta_purchase = desired_purchase_value - current_purchase_value
        price = None
        if delta_purchase > 0 and delta_units > 0:
            price = delta_purchase / delta_units
        tx = record_transaction(user_id, portfolio_id, {
            "type": "BUY",
            "holdingId": (existing or {}).get("holdingId") or holding.get("holdingId"),
            "name": name or (existing or {}).get("name"),
            "ticker": ticker or (existing or {}).get("ticker"),
            "currency": holding.get("currency") or (existing or {}).get("currency") or "PLN",
            "quantity": delta_units,
            "price": price,
            "value": delta_purchase if delta_purchase > 0 else None,
            "comment": "Legacy holding sync",
            "transactionDate": _today(),
            "affectCash": False,
        })
    else:
        reduced_purchase_value = current_purchase_value - desired_purchase_value
        tx = record_transaction(user_id, portfolio_id, {
            "type": "SELL",
            "holdingId": (existing or {}).get("holdingId") or holding.get("holdingId"),
            "name": name or (existing or {}).get("name"),
            "ticker": ticker or (existing or {}).get("ticker"),
            "currency": holding.get("currency") or (existing or {}).get("currency") or "PLN",
            "quantity": abs(delta_units),
            "value": reduced_purchase_value if reduced_purchase_value > 0 else None,
            "comment": "Legacy holding sync",
            "transactionDate": _today(),
            "affectCash": False,
        })
    return tx.get("holding") or _holding_public(existing)


def delete_holding(user_id: str, portfolio_id: str, holding_id: str) -> bool:
    """Legacy delete compatibility: record a SELL of the full remaining quantity."""
    existing = _get_holding_raw(user_id, portfolio_id, holding_id)
    if not existing:
        return False
    record_transaction(user_id, portfolio_id, {
        "type": "SELL",
        "holdingId": holding_id,
        "name": existing.get("name"),
        "ticker": existing.get("ticker"),
        "currency": existing.get("currency"),
        "quantity": existing.get("units", 0),
        "value": existing.get("purchaseValue", 0),
        "comment": "Legacy holding removal",
        "transactionDate": _today(),
        "affectCash": False,
    })
    return True


# ── Summary (virtual) ─────────────────────────────────────────────────────────

_PORTFOLIO_ORDER = {"emerytura": 1, "ike": 2, "ikze": 3, "xtb": 4}


def get_summary_holdings(user_id: str) -> list[dict]:
    return list_all_holdings(user_id)


def seed_default_portfolios(user_id: str, csv_wallets: dict) -> None:
    for wallet_name, holdings in csv_wallets.items():
        pid = _safe_id(wallet_name)
        order = _PORTFOLIO_ORDER.get(pid, 99)
        existing = get_portfolio(user_id, pid)
        if not existing:
            put_portfolio(user_id, {
                "portfolioId": pid,
                "name": wallet_name,
                "type": "real",
                "currency": "PLN",
                "order": order,
            })
        for h in holdings:
            put_holding(user_id, pid, h)

def calculate_xirr(cashflows: list[tuple[str, float]]) -> float:
    """
    Calculate annualized return using Newton-Raphson.
    cashflows: list of tuples (date_string_YYYY_MM_DD, amount_float)
    """
    if not cashflows or len(cashflows) < 2:
        return 0.0
    try:
        dates = [datetime.fromisoformat(cf[0][:10].replace('Z', '+00:00')) for cf in cashflows]
    except Exception:
        return 0.0
    amounts = [float(cf[1]) for cf in cashflows]
    if any(not math.isfinite(a) for a in amounts):
        return 0.0
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return 0.0
    t0 = dates[0]
    years = [(d - t0).days / 365.0 for d in dates]
    r = 0.1
    for _ in range(100):
        f_r = 0.0
        f_prime_r = 0.0
        try:
            for a, y in zip(amounts, years):
                f_r += a / ((1.0 + r) ** y)
                f_prime_r += -y * a / ((1.0 + r) ** (y + 1))
        except (OverflowError, ZeroDivisionError, ValueError):
            return 0.0
        if not math.isfinite(f_r) or not math.isfinite(f_prime_r):
            return 0.0
        if abs(f_prime_r) < 1e-10:
            break
        r_new = r - f_r / f_prime_r
        if not math.isfinite(r_new):
            return 0.0
        if r_new <= -1.0:
            return -0.9999
        if abs(r_new - r) < 1e-6:
            return r_new
        r = r_new
    return r

def extract_cashflows_from_transactions(txs: list[dict], as_of_date: str | None = None) -> list[tuple[str, float]]:
    cashflows = []
    for tx in txs:
        date_str = str(tx.get('transactionDate') or _today())[:10]
        if as_of_date and date_str > as_of_date:
            continue
            
        tx_type = str(tx.get('type') or '').upper()
        val = float(_to_decimal(tx.get('value', tx.get('amount', 0))))
        affect_cash = tx.get('affectCash')
        if affect_cash is None:
            affect_cash = True
        else:
            affect_cash = bool(affect_cash)
            
        if tx_type == 'DEPOSIT':
            cashflows.append((date_str, -val))
        elif tx_type in ('WITHDRAWAL', 'EXTRA_COST'):
            cashflows.append((date_str, val))
        elif tx_type == 'BUY' and not affect_cash:
            cashflows.append((date_str, -val))
        elif tx_type in ('SELL', 'DIVIDEND') and not affect_cash:
            cashflows.append((date_str, val))
    return cashflows

def get_portfolio_cashflows(user_id: str, portfolio_id: str, as_of_date: str | None = None) -> list[tuple[str, float]]:
    """
    Returns a list of external cashflows (date, amount) for the given portfolio.
    If as_of_date is provided, ignores transactions strictly after that date.
    Deposits are negative amounts, Withdrawals are positive amounts.
    """
    txs = list_all_transactions(user_id, portfolio_id, scan_forward=True)
    return extract_cashflows_from_transactions(txs, as_of_date)
