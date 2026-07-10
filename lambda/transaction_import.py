import csv
import hashlib
import os
import re
from decimal import Decimal

import portfolios


_SKIP_OPERATIONS = {
    "DYWIDENDA W DRODZE",
    "WYPŁATA DYWIDENDY W DRODZE",
}

_OPERATION_MAP = {
    "KUPNO": "BUY",
    "SPRZEDAŻ": "SELL",
    "WPŁATA": "DEPOSIT",
    "WYPŁATA": "WITHDRAWAL",
    "WPŁATA AUTOMATYCZNA": "DEPOSIT",
    "WYPŁATA AUTOMATYCZNA": "WITHDRAWAL",
    "DYWIDENDA": "DIVIDEND",
    "SPIN-OFF": "SPINOFF",
    "KOSZT NADZWYCZAJNY": "EXTRA_COST",
    "WPŁATA (UZGODNIENIE SALDA KONTA)": "DEPOSIT",
    "WYPŁATA (UZGODNIENIE SALDA KONTA)": "WITHDRAWAL",
}

_SPECIAL_TICKERS = {
    "BITCOIN (BTC)": "BTC-USD",
    "ETHEREUM (ETH)": "ETH-USD",
    "META PLATFORMS, INC. (META)": "META",
}
_ASSET_MARKET_CURRENCY = {
    "BITCOIN (BTC)": "USD",
    "ETHEREUM (ETH)": "USD",
    "META PLATFORMS, INC. (META)": "USD",
}
_FX_RATE_OVERRIDES = {
    ("myfund.pl_Binance_historiaOperacji", "2026-02-20", "BITCOIN (BTC)", "USD"): Decimal("3.5898"),
}


def _clean_cell(value) -> str:
    if value is None:
        return ""
    return str(value).strip().replace("\xa0", "").replace("\u00a0", "").replace(" ", "")


def _decimal_cell(value, default: Decimal | None = Decimal("0")) -> Decimal | None:
    raw = _clean_cell(value)
    if raw in {"", "-"}:
        return default
    return Decimal(raw.replace(",", "."))


def _asset_name(raw: str) -> str:
    name = str(raw or "").strip()
    if name.startswith("Gotówka (") and name.endswith(")"):
        inner = name[len("Gotówka ("):-1].strip()
        if inner:
            return inner
    return name or "Gotówka"


def _derive_ticker(name: str, currency: str | None) -> str | None:
    cleaned = str(name or "").strip()
    if not cleaned or cleaned.lower().startswith("got"):
        return None
    special = _SPECIAL_TICKERS.get(cleaned.upper())
    if special:
        return special
    symbol_match = re.search(r"\(([A-Z0-9.-]+)\)\s*$", cleaned)
    if symbol_match:
        symbol = symbol_match.group(1)
        if currency == "USD":
            return symbol
        if currency == "PLN":
            return f"{symbol}.WA"
        return symbol
    compact = cleaned.replace(" ", "")
    if currency == "PLN" and re.fullmatch(r"[A-Z0-9_-]{2,12}", compact):
        return f"{compact}.WA"
    if currency == "USD" and re.fullmatch(r"[A-Z0-9_-]{1,12}", compact):
        return compact
    return None


def _normalize_asset_currency(name: str, currency: str | None) -> str:
    return _ASSET_MARKET_CURRENCY.get(str(name or "").strip().upper(), currency or "PLN")


def _fx_override_rate(path: str, date: str, asset: str, currency: str) -> Decimal | None:
    base = os.path.basename(path)
    normalized_asset = str(asset or "").strip().upper()
    normalized_currency = str(currency or "").strip().upper()
    for prefix, fx_date, fx_asset, fx_currency in _FX_RATE_OVERRIDES:
        if base.startswith(prefix) and date == fx_date and normalized_asset == fx_asset and normalized_currency == fx_currency:
            return fx_currency and _FX_RATE_OVERRIDES[(prefix, fx_date, fx_asset, fx_currency)]
    return None


def parse_transaction_history_csv(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="cp1250", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        next(reader, None)
        for line_no, raw in enumerate(reader, start=2):
            if not any(cell.strip() for cell in raw):
                continue
            operation_raw = str(raw[1] or "").strip()
            normalized = operation_raw.upper()
            if normalized in _SKIP_OPERATIONS:
                continue
            mapped_type = _OPERATION_MAP.get(normalized)
            if not mapped_type:
                continue

            transaction_date = str(raw[0] or "").strip()
            raw_currency = str(raw[4] or "PLN").strip() or "PLN"
            asset = _asset_name(raw[3] if len(raw) > 3 else "")
            currency = raw_currency
            quantity = abs(_decimal_cell(raw[5] if len(raw) > 5 else "", Decimal("0")) or Decimal("0"))
            price = _decimal_cell(raw[6] if len(raw) > 6 else "", None)
            commission = _decimal_cell(raw[7] if len(raw) > 7 else "", Decimal("0")) or Decimal("0")
            tax = _decimal_cell(raw[8] if len(raw) > 8 else "", Decimal("0")) or Decimal("0")
            value = abs(_decimal_cell(raw[9] if len(raw) > 9 else "", Decimal("0")) or Decimal("0"))
            comment = str(raw[14] if len(raw) > 14 else "").strip()

            fx_rate = _fx_override_rate(path, transaction_date, asset, raw_currency)
            if fx_rate and mapped_type in {"BUY", "SELL", "DIVIDEND", "SPINOFF", "EXTRA_COST"}:
                if price is not None:
                    price = (price * fx_rate)
                commission = commission * fx_rate
                tax = tax * fx_rate
                value = value * fx_rate
                currency = "PLN"

            if mapped_type == "SPINOFF":
                value = Decimal("0")
            if mapped_type in {"DEPOSIT", "WITHDRAWAL", "EXTRA_COST"}:
                quantity = Decimal("0")
                price = None
            if mapped_type == "DIVIDEND" and not comment:
                comment = f"Dividend import for {asset}"
            if "UZGODNIENIE SALDA KONTA" in normalized and not comment:
                comment = "Balance reconciliation imported from CSV history"

            digest = hashlib.sha1("|".join([
                os.path.basename(path),
                str(line_no),
                str(raw[0] if len(raw) > 0 else ""),
                operation_raw,
                asset,
                str(raw[9] if len(raw) > 9 else ""),
            ]).encode("utf-8")).hexdigest()[:16]

            rows.append({
                "lineNo": line_no,
                "transactionDate": transaction_date,
                "type": mapped_type,
                "sourceOperation": operation_raw,
                "name": asset,
                "ticker": _derive_ticker(asset, _normalize_asset_currency(asset, raw_currency)),
                "currency": currency,
                "assetCurrency": _normalize_asset_currency(asset, raw_currency),
                "quantity": quantity,
                "price": price,
                "commission": commission,
                "tax": tax,
                "value": value,
                "comment": comment,
                "transactionId": f"hist-{digest}",
            })
    rows.reverse()
    return rows


def _holding_id_for_row(row: dict) -> str:
    if row["type"] in {"DEPOSIT", "WITHDRAWAL", "EXTRA_COST"}:
        return portfolios._CASH_HOLDING_ID
    return portfolios._safe_id(str(row.get("name") or row.get("ticker") or "transaction"))


def _store_import_transaction(user_id: str, portfolio_id: str, row: dict) -> None:
    transaction_date = portfolios._normalize_transaction_date(row.get("transactionDate"))
    transaction_id = str(row["transactionId"]).strip()
    item = {
        "userId": user_id,
        "sk": portfolios._transaction_sk(portfolio_id, transaction_date, transaction_id),
        "transactionId": transaction_id,
        "portfolioId": portfolio_id,
        "holdingId": _holding_id_for_row(row),
        "type": row["type"],
        "ticker": row.get("ticker"),
        "name": row.get("name"),
        "currency": row.get("currency") or "PLN",
        "quantity": row.get("quantity"),
        "price": row.get("price"),
        "value": row.get("value"),
        "commission": row.get("commission", Decimal("0")),
        "tax": row.get("tax", Decimal("0")),
        "comment": row.get("comment", ""),
        "transactionDate": transaction_date,
        "createdAt": portfolios._now(),
        "importSource": "historical-csv",
        "importVersion": 1,
        "sourceOperation": row.get("sourceOperation"),
    }
    portfolios._transactions_table().put_item(Item={k: v for k, v in item.items() if v is not None})


def _natural_transaction_key(row: dict) -> tuple:
    def decimal_key(value) -> str:
        return str(portfolios._to_decimal(value).normalize())

    return (
        portfolios._normalize_transaction_date(row.get("transactionDate")),
        str(row.get("type") or "").strip().upper(),
        str(row.get("name") or "").strip(),
        str(row.get("ticker") or "").strip(),
        decimal_key(row.get("quantity") or 0),
        decimal_key(row.get("value") or 0),
    )


def import_transaction_history(user_id: str, portfolio_id: str, csv_path: str, rebuild: bool = False) -> dict:
    if not os.path.exists(csv_path):
        return {"status": "missing", "imported": 0, "skipped": 0}

    existing_transactions = portfolios.list_transactions(user_id, portfolio_id, limit=5000)
    existing_holdings = portfolios.list_holdings(user_id, portfolio_id)

    if rebuild or (existing_holdings and not existing_transactions):
        portfolios.clear_portfolio_ledger(user_id, portfolio_id)
        existing_transactions = []

    existing_ids = {str(tx.get("transactionId")) for tx in existing_transactions if tx.get("transactionId")}
    existing_natural_keys = {_natural_transaction_key(tx) for tx in existing_transactions}
    imported = 0
    skipped = 0
    imported_types: dict[str, int] = {}

    for row in parse_transaction_history_csv(csv_path):
        tx_id = row["transactionId"]
        natural_key = _natural_transaction_key(row)
        if tx_id in existing_ids or natural_key in existing_natural_keys:
            skipped += 1
            continue
        _store_import_transaction(user_id, portfolio_id, row)
        imported += 1
        existing_ids.add(tx_id)
        existing_natural_keys.add(natural_key)
        imported_types[row["type"]] = imported_types.get(row["type"], 0) + 1

    return {
        "status": "ok",
        "imported": imported,
        "skipped": skipped,
        "types": imported_types,
        "rebuild": bool(rebuild or (existing_holdings and not existing_transactions)),
    }
