"""
snapshots.py — daily portfolio snapshots and ATH tracking.

Snapshots table (roastfolio-snapshots):
  PK = userId
  SK = PORTFOLIO#<portfolioId>#SNAPSHOT#<YYYY-MM-DD> | PORTFOLIO#<portfolioId>#ATH

Rules:
  - one daily snapshot per user + portfolio + snapshotDate
  - ATH is derived from snapshot history unless manually overridden
  - virtual "summary" portfolio is supported for aggregate dashboard ATH
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

import boto3
import yfinance as yf
from boto3.dynamodb.conditions import Key

import db
import portfolios


_SNAPSHOTS_TABLE_NAME = os.environ.get("SNAPSHOTS_TABLE", "roastfolio-snapshots")
_snapshots_table_ref = None

_WARSAW_TZ = ZoneInfo("Europe/Warsaw")
_TWOPLACES = Decimal("0.01")
_FOURPLACES = Decimal("0.0001")
_XIRR_CALCULATION_VERSION = "investment-history-v1"


def _table():
    global _snapshots_table_ref
    if _snapshots_table_ref is None:
        _snapshots_table_ref = boto3.resource("dynamodb").Table(_SNAPSHOTS_TABLE_NAME)
    return _snapshots_table_ref


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_snapshot_date(raw) -> str:
    if raw in (None, ""):
        return warsaw_snapshot_date()
    raw = str(raw).strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    raise ValueError("snapshotDate must be YYYY-MM-DD")


def warsaw_snapshot_date(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    local_now = current.astimezone(_WARSAW_TZ)
    return (local_now.date() - timedelta(days=1)).isoformat()


def _snapshot_sk(portfolio_id: str, snapshot_date: str) -> str:
    return f"PORTFOLIO#{portfolio_id}#SNAPSHOT#{snapshot_date}"


def _ath_sk(portfolio_id: str) -> str:
    return f"PORTFOLIO#{portfolio_id}#ATH"


def _public_item(item: dict | None) -> dict | None:
    if not item:
        return None
    item = dict(item)
    item.pop("userId", None)
    item.pop("sk", None)
    return item


def _quantize_money(value) -> Decimal:
    return _to_decimal(value).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)


def _quantize_pct(value) -> Decimal:
    return _to_decimal(value).quantize(_FOURPLACES, rounding=ROUND_HALF_UP)


def _missing_xirr(value) -> bool:
    if value in (None, ""):
        return True
    try:
        decimal_value = _to_decimal(value)
    except Exception:
        return True
    return not decimal_value.is_finite()


def _needs_xirr_backfill(snapshot: dict) -> bool:
    if _missing_xirr(snapshot.get("xirr")):
        return True
    return str(snapshot.get("xirrVersion") or "") != _XIRR_CALCULATION_VERSION


def _xirr_from_investment_history(snapshots: list[dict], as_of_date: str) -> Decimal:
    cashflows: list[tuple[str, float]] = []
    terminal_value = Decimal("0")
    previous_investment: Decimal | None = None

    for snapshot in sorted(snapshots, key=lambda item: str(item.get("snapshotDate", ""))):
        snapshot_date = str(snapshot.get("snapshotDate", ""))[:10]
        if not snapshot_date or snapshot_date > as_of_date:
            continue

        investment_value = _to_decimal(snapshot.get("investmentValue") or 0)
        delta = investment_value if previous_investment is None else investment_value - previous_investment
        if abs(delta) >= _TWOPLACES:
            cashflows.append((snapshot_date, float(-delta)))
        previous_investment = investment_value

        if snapshot_date == as_of_date:
            terminal_value = _to_decimal(snapshot.get("portfolioValue") or 0)

    cashflows.append((as_of_date, float(terminal_value)))
    cashflows.sort(key=lambda item: item[0])
    return Decimal(str(round(portfolios.calculate_xirr(cashflows), 4)))


def _clean_csv_cell(value) -> str:
    if value is None:
        return ""
    return str(value).strip().replace("\xa0", "").replace("\u00a0", "").replace(" ", "")


def _decimal_csv_cell(value, default: Decimal | None = Decimal("0")) -> Decimal | None:
    raw = _clean_csv_cell(value)
    if raw in {"", "-"}:
        return default
    return Decimal(raw.replace(",", "."))


def list_snapshots(user_id: str, portfolio_id: str, limit: int | None = None) -> list[dict]:
    prefix = f"PORTFOLIO#{portfolio_id}#SNAPSHOT#"
    query_kwargs = {
        "KeyConditionExpression": Key("userId").eq(user_id) & Key("sk").begins_with(prefix),
        "ScanIndexForward": False,
    }
    if limit is not None:
        query_kwargs["Limit"] = limit

    items = []
    resp = _table().query(**query_kwargs)
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp and (limit is None or len(items) < limit):
        page_kwargs = dict(query_kwargs)
        if limit is not None:
            page_kwargs["Limit"] = max(limit - len(items), 1)
        resp = _table().query(
            **page_kwargs,
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))

    if limit is not None:
        items = items[:limit]
    items = [_public_item(item) for item in items]
    return [item for item in items if item]


def get_portfolio_ath(user_id: str, portfolio_id: str) -> dict | None:
    resp = _table().get_item(Key={"userId": user_id, "sk": _ath_sk(portfolio_id)})
    item = _public_item(resp.get("Item"))

    if not item or item.get("athSource") != "MANUAL":
        snapshots_list = list_snapshots(user_id, portfolio_id, limit=5000)
        if snapshots_list:
            best_snap = max(snapshots_list, key=lambda s: (_to_decimal(s.get("portfolioValue", 0)), str(s.get("snapshotDate", ""))))
            best_val = _quantize_money(best_snap["portfolioValue"])
            rec_val = float(item.get("athValue", 0)) if item else 0.0
            if not item or float(best_val) > rec_val:
                now = _now_iso()
                item = {
                    "userId": user_id,
                    "sk": _ath_sk(portfolio_id),
                    "portfolioId": portfolio_id,
                    "athValue": best_val,
                    "athDate": str(best_snap["snapshotDate"]),
                    "athSource": "AUTO",
                    "createdAt": (item or {}).get("createdAt", now),
                    "updatedAt": now,
                }
                try:
                    _table().put_item(Item=item)
                except Exception as err:
                    print(f"Failed to update sync ATH item: {err}")

    return item


def set_manual_ath(user_id: str, portfolio_id: str, ath_value, ath_date) -> dict:
    value = _quantize_money(ath_value)
    if value <= 0:
        raise ValueError("athValue must be greater than 0")

    snapshot_date = _normalize_snapshot_date(ath_date)
    now = _now_iso()
    item = {
        "userId": user_id,
        "sk": _ath_sk(portfolio_id),
        "portfolioId": portfolio_id,
        "athValue": value,
        "athDate": snapshot_date,
        "athSource": "MANUAL",
        "updatedAt": now,
    }
    existing = get_portfolio_ath(user_id, portfolio_id)
    item["createdAt"] = (existing or {}).get("createdAt", now)
    _table().put_item(Item=item)
    return _public_item(item)


def recalculate_ath(user_id: str, portfolio_id: str) -> dict | None:
    snapshots = list_snapshots(user_id, portfolio_id, limit=5000)
    if not snapshots:
        _table().delete_item(Key={"userId": user_id, "sk": _ath_sk(portfolio_id)})
        return None

    best = max(snapshots, key=lambda item: (_to_decimal(item["portfolioValue"]), str(item["snapshotDate"])))
    now = _now_iso()
    item = {
        "userId": user_id,
        "sk": _ath_sk(portfolio_id),
        "portfolioId": portfolio_id,
        "athValue": _quantize_money(best["portfolioValue"]),
        "athDate": best["snapshotDate"],
        "athSource": "AUTO",
        "updatedAt": now,
    }
    existing = get_portfolio_ath(user_id, portfolio_id)
    item["createdAt"] = (existing or {}).get("createdAt", now)
    _table().put_item(Item=item)
    return _public_item(item)


def store_daily_snapshot(user_id: str, portfolio_id: str, snapshot: dict, overwrite: bool = False) -> dict:
    snapshot_date = _normalize_snapshot_date(snapshot.get("snapshotDate"))
    existing = _table().get_item(Key={"userId": user_id, "sk": _snapshot_sk(portfolio_id, snapshot_date)}).get("Item")
    if existing and not overwrite:
        raise ValueError(f"Snapshot already exists for {portfolio_id} on {snapshot_date}")

    portfolio_value = _quantize_money(snapshot.get("portfolioValue", 0))
    if portfolio_value < 0:
        raise ValueError("portfolioValue cannot be negative")

    benchmark_value = snapshot.get("benchmarkValue")
    if benchmark_value not in (None, ""):
        benchmark_value = _quantize_money(benchmark_value)
        if benchmark_value < 0:
            raise ValueError("benchmarkValue cannot be negative")

    daily_return = snapshot.get("dailyReturn")
    if daily_return not in (None, ""):
        daily_return = _quantize_pct(daily_return)
    elif existing and existing.get("dailyReturn") not in (None, ""):
        daily_return = _quantize_pct(existing.get("dailyReturn"))

    investment_value = snapshot.get("investmentValue")
    if investment_value not in (None, ""):
        investment_value = _quantize_money(investment_value)
        if investment_value < 0:
            raise ValueError("investmentValue cannot be negative")
    elif existing and existing.get("investmentValue") not in (None, ""):
        investment_value = _quantize_money(existing.get("investmentValue"))

    benchmark_id = snapshot.get("benchmarkId", existing.get("benchmarkId") if existing else None)

    xirr_value = snapshot.get("xirr")
    xirr_version = snapshot.get("xirrVersion")
    if xirr_value not in (None, ""):
        xirr_value = _to_decimal(xirr_value)
        if not _missing_xirr(xirr_value) and not xirr_version:
            xirr_version = _XIRR_CALCULATION_VERSION
    elif existing and existing.get("xirr") not in (None, ""):
        xirr_value = _to_decimal(existing.get("xirr"))
        xirr_version = existing.get("xirrVersion")

    now = _now_iso()
    item = {
        "userId": user_id,
        "sk": _snapshot_sk(portfolio_id, snapshot_date),
        "portfolioId": portfolio_id,
        "snapshotDate": snapshot_date,
        "portfolioValue": portfolio_value,
        "investmentValue": investment_value,
        "benchmarkId": benchmark_id,
        "benchmarkValue": benchmark_value,
        "dailyReturn": daily_return,
        "xirr": xirr_value,
        "updatedAt": now,
    }
    if xirr_version:
        item["xirrVersion"] = str(xirr_version)
    item["createdAt"] = (existing or {}).get("createdAt", now)
    _table().put_item(Item=item)

    ath = get_portfolio_ath(user_id, portfolio_id)
    if not ath:
        recalculate_ath(user_id, portfolio_id)
    else:
        ath_value = _to_decimal(ath.get("athValue", 0))
        if portfolio_value >= ath_value:
            _table().put_item(Item={
                "userId": user_id,
                "sk": _ath_sk(portfolio_id),
                "portfolioId": portfolio_id,
                "athValue": portfolio_value,
                "athDate": snapshot_date,
                "athSource": "AUTO",
                "createdAt": ath.get("createdAt", now),
                "updatedAt": now,
            })
        elif existing and str(existing.get("snapshotDate")) == str(ath.get("athDate")) and portfolio_value < ath_value:
            recalculate_ath(user_id, portfolio_id)

    return _public_item(item)


def delete_portfolio_history(user_id: str, portfolio_id: str) -> None:
    snapshots = list_snapshots(user_id, portfolio_id, limit=5000)
    with _table().batch_writer() as batch:
        for snapshot in snapshots:
            batch.delete_item(Key={"userId": user_id, "sk": _snapshot_sk(portfolio_id, snapshot["snapshotDate"])})
        batch.delete_item(Key={"userId": user_id, "sk": _ath_sk(portfolio_id)})


def parse_wallet_value_history_csv(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="cp1250", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        next(reader, None)
        for raw in reader:
            cleaned = [_clean_csv_cell(cell) for cell in raw]
            if not any(cleaned):
                continue
            snapshot_date = str(raw[0] or "").strip()
            if not snapshot_date:
                continue
            values = [cell for cell in cleaned[1:] if cell not in {"", "-"}]
            portfolio_value = _decimal_csv_cell(values[0], None) if values else None
            investment_value = _decimal_csv_cell(values[-1], None) if values else None
            if portfolio_value is None or investment_value is None:
                continue
            rows.append({
                "snapshotDate": snapshot_date,
                "portfolioValue": _quantize_money(portfolio_value),
                "investmentValue": _quantize_money(investment_value),
            })
    return rows


def import_wallet_value_history(user_id: str, portfolio_id: str, csv_path: str) -> dict:
    rows = parse_wallet_value_history_csv(csv_path)
    delete_portfolio_history(user_id, portfolio_id)
    imported = 0
    for row in rows:
        store_daily_snapshot(user_id, portfolio_id, row, overwrite=True)
        imported += 1
    ath = recalculate_ath(user_id, portfolio_id)
    return {
        "portfolioId": portfolio_id,
        "imported": imported,
        "ath": ath,
    }


def _get_close_pair(symbol: str, cache: dict[str, tuple[Decimal, Decimal]]) -> tuple[Decimal, Decimal]:
    if symbol in cache:
        return cache[symbol]

    last_close = None
    prev_close = None
    try:
        history = yf.Ticker(symbol).history(period="7d", interval="1d", auto_adjust=False)
        closes = [row["Close"] for _, row in history.iterrows() if row["Close"] == row["Close"]]
        if closes:
            last_close = _to_decimal(float(closes[-1]))
            prev_close = _to_decimal(float(closes[-2] if len(closes) >= 2 else closes[-1]))
    except Exception:
        pass

    if last_close is None:
        info = yf.Ticker(symbol).fast_info
        if not info.last_price:
            raise ValueError(f"No close data for {symbol}")
        last_close = _to_decimal(info.last_price)
        prev_close = _to_decimal(info.previous_close or info.last_price)

    cache[symbol] = (last_close, prev_close)
    return cache[symbol]


def _get_fx_close_pair(currency: str, cache: dict[str, tuple[Decimal, Decimal]]) -> tuple[Decimal, Decimal]:
    if currency == "PLN":
        return Decimal("1"), Decimal("1")
    return _get_close_pair(f"{currency}PLN=X", cache)


def calculate_portfolio_snapshot(holdings: list[dict]) -> dict:
    price_cache: dict[str, tuple[Decimal, Decimal]] = {}
    fx_cache: dict[str, tuple[Decimal, Decimal]] = {}

    total_value = Decimal("0")
    total_prev = Decimal("0")

    for holding in holdings:
        units = _to_decimal(holding.get("units", 0))
        purchase_value = _to_decimal(holding.get("purchaseValue", 0))
        ticker = holding.get("ticker")
        currency = holding.get("currency", "PLN")

        if not ticker:
            total_value += purchase_value
            total_prev += purchase_value
            continue

        close_price, prev_close = _get_close_pair(ticker, price_cache)
        close_fx, prev_fx = _get_fx_close_pair(currency, fx_cache)

        current_value = units * close_price * close_fx
        previous_value = units * prev_close * prev_fx

        total_value += current_value
        total_prev += previous_value

    total_value = _quantize_money(total_value)
    total_prev = _quantize_money(total_prev)
    daily_return = Decimal("0")
    if total_prev > 0:
        daily_return = _quantize_pct(((total_value - total_prev) / total_prev) * 100)

    return {
        "portfolioValue": total_value,
        "dailyReturn": daily_return,
    }


def calculate_benchmark_close(benchmark_id: str) -> Decimal:
    meta = db.BENCHMARKS.get(benchmark_id) or db.BENCHMARKS[db.DEFAULT_BENCHMARK]
    close_price, _ = _get_close_pair(meta["ticker"], {})
    return _quantize_money(close_price)


def generate_user_snapshots(user_id: str, snapshot_date: str | None = None, overwrite: bool = False) -> dict:
    snapshot_date = _normalize_snapshot_date(snapshot_date)
    profile = db.get_user(user_id) or {}
    benchmark_id = profile.get("settings", {}).get("benchmark", db.DEFAULT_BENCHMARK)
    if benchmark_id not in db.BENCHMARKS:
        benchmark_id = db.DEFAULT_BENCHMARK

    benchmark_value = calculate_benchmark_close(benchmark_id)
    created = 0
    skipped = 0
    portfolios_out = []
    summary_holdings = []
    summary_investment = Decimal("0")
    
    user_portfolios = portfolios.list_portfolios(user_id)

    for portfolio in user_portfolios:
        portfolio_id = portfolio["portfolioId"]
        holdings = portfolios.list_holdings(user_id, portfolio_id)
        summary_holdings.extend(holdings)
        snapshot = calculate_portfolio_snapshot(holdings)
        investment_value = _quantize_money(portfolios.calculate_investment_total(user_id, portfolio_id))
        summary_investment += investment_value
        
        xirr_history = [s for s in list_snapshots(user_id, portfolio_id) if str(s.get("snapshotDate", "")) < snapshot_date]
        xirr_history.append({
            "snapshotDate": snapshot_date,
            "portfolioValue": snapshot["portfolioValue"],
            "investmentValue": investment_value,
        })
        snap_xirr = _xirr_from_investment_history(xirr_history, snapshot_date)
        
        payload = {
            "snapshotDate": snapshot_date,
            "portfolioValue": snapshot["portfolioValue"],
            "investmentValue": investment_value,
            "benchmarkId": benchmark_id,
            "benchmarkValue": benchmark_value,
            "dailyReturn": snapshot["dailyReturn"],
            "xirr": snap_xirr,
            "xirrVersion": _XIRR_CALCULATION_VERSION,
        }
        try:
            store_daily_snapshot(user_id, portfolio_id, payload, overwrite=overwrite)
            created += 1
        except ValueError as exc:
            if "already exists" in str(exc):
                skipped += 1
            else:
                raise
        portfolios_out.append({
            "portfolioId": portfolio_id,
            "name": portfolio.get("name", portfolio_id),
            "portfolioValue": snapshot["portfolioValue"],
            "investmentValue": investment_value,
            "dailyReturn": snapshot["dailyReturn"],
        })

    if portfolios_out:
        summary_snapshot = calculate_portfolio_snapshot(summary_holdings)
        xirr_history = [s for s in list_snapshots(user_id, "summary") if str(s.get("snapshotDate", "")) < snapshot_date]
        xirr_history.append({
            "snapshotDate": snapshot_date,
            "portfolioValue": summary_snapshot["portfolioValue"],
            "investmentValue": _quantize_money(summary_investment),
        })
        summary_xirr = _xirr_from_investment_history(xirr_history, snapshot_date)
        try:
            store_daily_snapshot(user_id, "summary", {
                "snapshotDate": snapshot_date,
                "portfolioValue": summary_snapshot["portfolioValue"],
                "investmentValue": _quantize_money(summary_investment),
                "benchmarkId": benchmark_id,
                "benchmarkValue": benchmark_value,
                "dailyReturn": summary_snapshot["dailyReturn"],
                "xirr": summary_xirr,
                "xirrVersion": _XIRR_CALCULATION_VERSION,
            }, overwrite=overwrite)
            created += 1
        except ValueError as exc:
            if "already exists" in str(exc):
                skipped += 1
            else:
                raise

    return {
        "userId": user_id,
        "snapshotDate": snapshot_date,
        "benchmarkId": benchmark_id,
        "benchmarkValue": benchmark_value,
        "created": created,
        "skipped": skipped,
        "portfolios": portfolios_out,
    }


def handler(event, _context):
    event = event or {}
    snapshot_date = _normalize_snapshot_date(event.get("snapshotDate"))
    overwrite = bool(event.get("overwrite"))
    results = []
    failures = []

    for user in db.list_users():
        user_id = user.get("userId")
        if not user_id:
            continue
        try:
            backfill_missing_xirr(user_id)
            results.append(generate_user_snapshots(user_id, snapshot_date=snapshot_date, overwrite=overwrite))
        except Exception as exc:
            failures.append({"userId": user_id, "error": str(exc)})

    return {
        "ok": len(failures) == 0,
        "snapshotDate": snapshot_date,
        "processedUsers": len(results),
        "failedUsers": failures,
        "results": results,
    }


# ── Historical snapshot recalculation ────────────────────────────────────────

def _fetch_price_history_range(
    tickers: set,
    fx_currencies: set,
    from_date: str,
    to_date: str,
) -> dict:
    """
    Fetches daily close prices for yfinance-compatible symbols over a date range.
    Returns: {symbol: {date_str: Decimal}}  Missing dates (non-trading days) are absent.
    """
    price_history: dict = {}
    end_str = (datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=3)).strftime("%Y-%m-%d")

    all_symbols = list(tickers)
    for currency in fx_currencies:
        all_symbols.append(f"{currency}PLN=X")

    def capture_symbol_history(symbol: str, hist) -> None:
        sym_prices: dict = {}
        if hist is None or hist.empty:
            price_history[symbol] = sym_prices
            return
        for idx, row in hist.iterrows():
            date_str = idx.strftime("%Y-%m-%d")
            close = row.get("Close")
            if close is not None and close == close:  # filter NaN
                sym_prices[date_str] = _to_decimal(float(close))
        price_history[symbol] = sym_prices

    if all_symbols:
        try:
            batch_history = yf.download(
                all_symbols,
                start=from_date,
                end=end_str,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                timeout=15,
                group_by="ticker",
            )
        except Exception:
            batch_history = None

        if batch_history is not None and not batch_history.empty:
            columns = getattr(batch_history, "columns", None)
            is_multi = bool(getattr(columns, "nlevels", 1) > 1)
            for symbol in all_symbols:
                try:
                    if is_multi:
                        if symbol in columns.get_level_values(0):
                            capture_symbol_history(symbol, batch_history[symbol])
                        elif symbol in columns.get_level_values(-1) and "Close" in columns.get_level_values(0):
                            capture_symbol_history(symbol, batch_history.xs(symbol, axis=1, level=-1))
                        else:
                            price_history[symbol] = {}
                    else:
                        capture_symbol_history(symbol, batch_history if len(all_symbols) == 1 else None)
                except Exception:
                    price_history[symbol] = {}

    for symbol in all_symbols:
        if symbol in price_history:
            continue
        try:
            hist = yf.download(
                symbol,
                start=from_date,
                end=end_str,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=5,
                multi_level_index=False,
            )
            capture_symbol_history(symbol, hist)
        except Exception:
            price_history[symbol] = {}

    return price_history


def _price_at_or_before(
    price_history: dict,
    symbol: str,
    date: str,
) -> "Decimal | None":
    """Return the closest available closing price on or before `date`."""
    hist = price_history.get(symbol)
    if not hist:
        return None
    candidates = [d for d in hist if d <= date]
    if not candidates:
        return None
    return hist[max(candidates)]


def _holdings_at_date(all_transactions: list, as_of_date: str) -> list:
    """
    Replay `all_transactions` (sorted ascending by transactionDate) up to and
    including `as_of_date` to derive the holdings composition at that point.
    Returns a list of dicts: {holdingId, ticker, currency, units, purchaseValue}
    plus a synthetic CASH holding when the cash balance is non-zero.
    """
    _EPS = Decimal("0.00000001")
    holdings: dict = {}
    cash = Decimal("0")

    for tx in all_transactions:
        tx_date = str(tx.get("transactionDate") or "").strip()[:10]
        if tx_date > as_of_date:
            break

        tx_type = str(tx.get("type", "")).upper()
        qty = _to_decimal(tx.get("quantity") or 0)
        value = _to_decimal(tx.get("value") or 0)
        h_id = str(tx.get("holdingId") or "")
        ticker = tx.get("ticker")
        currency = tx.get("currency") or "PLN"
        
        import portfolios
        if ticker:
            currency = portfolios._MARKET_CURRENCY_BY_TICKER.get(str(ticker).upper(), currency)

        if tx_type in ("BUY", "SPINOFF"):
            cur = holdings.get(h_id) or {
                "holdingId": h_id,
                "ticker": ticker,
                "currency": currency,
                "units": Decimal("0"),
                "purchaseValue": Decimal("0"),
            }
            if ticker:
                cur["ticker"] = ticker
            if currency:
                cur["currency"] = currency
            cur["units"] += qty
            cur["purchaseValue"] += value
            holdings[h_id] = cur
            if tx_type == "BUY":
                cash -= value
        elif tx_type == "SELL":
            cur = holdings.get(h_id)
            if cur and cur["units"] > _EPS:
                sell_units = min(qty, cur["units"])
                frac = sell_units / cur["units"]
                cur["purchaseValue"] = cur["purchaseValue"] * (1 - frac)
                cur["units"] -= sell_units
                if cur["units"] <= _EPS:
                    holdings.pop(h_id, None)
                else:
                    holdings[h_id] = cur
            cash += value
        elif tx_type == "DEPOSIT":
            cash += value
        elif tx_type == "WITHDRAWAL":
            cash -= value
        elif tx_type == "DIVIDEND":
            cash += value
        elif tx_type == "CASH_ADJUSTMENT":
            cash += value
        elif tx_type == "EXTRA_COST":
            cash -= value

    result = [h for h in holdings.values() if _to_decimal(h.get("units", 0)) > _EPS]
    if abs(cash) >= Decimal("0.01"):
        result.append({
            "holdingId": "CASH",
            "ticker": None,
            "currency": "PLN",
            "units": cash,
            "purchaseValue": cash,
        })
    return result


def _investment_total_at_date(all_transactions: list, as_of_date: str) -> Decimal:
    """Cumulative DEPOSIT minus WITHDRAWAL up to and including `as_of_date`."""
    total = Decimal("0")
    for tx in all_transactions:
        tx_date = str(tx.get("transactionDate") or "").strip()[:10]
        if tx_date > as_of_date:
            break
        tx_type = str(tx.get("type", "")).upper()
        value = _to_decimal(tx.get("value") or 0)
        
        affect_cash = tx.get("affectCash")
        if affect_cash is None:
            affect_cash = True
        else:
            affect_cash = bool(affect_cash)
            
        if tx_type == "DEPOSIT":
            total += value
        elif tx_type in ("WITHDRAWAL", "EXTRA_COST"):
            total -= value
        elif tx_type == "BUY" and not affect_cash:
            total += value
        elif tx_type in ("SELL", "DIVIDEND") and not affect_cash:
            total -= value
    return total


def recalculate_portfolio_snapshots_from_date(
    user_id: str,
    portfolio_id: str,
    from_date: str,
) -> dict:
    """
    Recalculates `portfolioValue`, `investmentValue`, and `dailyReturn` for all
    existing snapshots of `portfolio_id` on or after `from_date`.

    Algorithm per snapshot date:
      1. Replay all transactions up to that date → holdings composition.
      2. Look up historical closing prices (bulk-fetched from yfinance).
         Assets with a TFI: prefix or no ticker fall back to purchaseValue.
      3. Sum: portfolioValue = Σ(units × close × fx).
      4. investmentValue = cumulative DEPOSIT − WITHDRAWAL up to that date.

    Returns: {"updated": int, "fromDate": str, "portfolioId": str}
    """
    all_transactions = portfolios.list_all_transactions(user_id, portfolio_id, scan_forward=True)
    all_snapshots = list_snapshots(user_id, portfolio_id)
    xirr_history = [dict(s) for s in all_snapshots]
    xirr_history_by_date = {str(s["snapshotDate"]): s for s in xirr_history}
    snapshots_to_update = sorted(
        [s for s in all_snapshots if str(s.get("snapshotDate", "")) >= from_date],
        key=lambda s: s["snapshotDate"],
    )
    if not snapshots_to_update:
        return {"updated": 0, "fromDate": from_date, "portfolioId": portfolio_id}

    max_date = snapshots_to_update[-1]["snapshotDate"]

    # Collect yfinance-compatible tickers and FX currencies
    yf_tickers: set = set()
    yf_currencies: set = set()
    for tx in all_transactions:
        ticker = tx.get("ticker")
        if ticker and not str(ticker).upper().startswith("TFI:"):
            yf_tickers.add(str(ticker))
        currency = tx.get("currency") or "PLN"
        if currency and currency != "PLN":
            yf_currencies.add(str(currency))

    price_history = _fetch_price_history_range(yf_tickers, yf_currencies, from_date, max_date)

    now = _now_iso()
    updated = 0
    prev_value: "Decimal | None" = None  # for dailyReturn

    with _table().batch_writer() as batch:
        for snapshot in snapshots_to_update:
            snap_date = snapshot["snapshotDate"]
            holdings = _holdings_at_date(all_transactions, snap_date)

            portfolio_value = Decimal("0")
            for h in holdings:
                ticker = h.get("ticker")
                currency = h.get("currency") or "PLN"
                units = _to_decimal(h.get("units", 0))
                purchase_value = _to_decimal(h.get("purchaseValue", 0))

                if not ticker or str(ticker).upper().startswith("TFI:"):
                    portfolio_value += purchase_value
                    continue

                close_price = _price_at_or_before(price_history, ticker, snap_date)
                fx_rate = (
                    _price_at_or_before(price_history, f"{currency}PLN=X", snap_date)
                    if currency != "PLN"
                    else Decimal("1")
                )
                if close_price is not None and fx_rate is not None:
                    portfolio_value += units * close_price * fx_rate
                else:
                    # No historical price available — fall back to purchase value
                    portfolio_value += purchase_value

            portfolio_value = _quantize_money(portfolio_value)
            investment_value = _quantize_money(_investment_total_at_date(all_transactions, snap_date))

            daily_return = Decimal("0")
            if prev_value is not None and prev_value > 0:
                daily_return = _quantize_pct(((portfolio_value - prev_value) / prev_value) * 100)
            elif snapshot.get("dailyReturn") not in (None, ""):
                daily_return = _to_decimal(snapshot["dailyReturn"])
            prev_value = portfolio_value
            
            xirr_snapshot = xirr_history_by_date.get(str(snap_date))
            if xirr_snapshot is not None:
                xirr_snapshot["portfolioValue"] = portfolio_value
                xirr_snapshot["investmentValue"] = investment_value
            snap_xirr = _xirr_from_investment_history(xirr_history, snap_date)

            item: dict = {
                "userId": user_id,
                "sk": _snapshot_sk(portfolio_id, snap_date),
                "portfolioId": portfolio_id,
                "snapshotDate": snap_date,
                "portfolioValue": portfolio_value,
                "investmentValue": investment_value,
                "dailyReturn": daily_return,
                "xirr": snap_xirr,
                "xirrVersion": _XIRR_CALCULATION_VERSION,
                "updatedAt": now,
                "createdAt": snapshot.get("createdAt", now),
            }
            if snapshot.get("benchmarkId"):
                item["benchmarkId"] = snapshot["benchmarkId"]
            if snapshot.get("benchmarkValue") not in (None, ""):
                item["benchmarkValue"] = _quantize_money(snapshot["benchmarkValue"])

            batch.put_item(Item=item)
            updated += 1

    recalculate_ath(user_id, portfolio_id)
    return {"updated": updated, "fromDate": from_date, "portfolioId": portfolio_id}


def recalculate_summary_snapshots_from_date(user_id: str, from_date: str) -> int:
    """
    Rebuilds summary portfolio snapshots for all dates >= `from_date` by
    aggregating portfolioValue and investmentValue across all real portfolios.
    Should be called after recalculate_portfolio_snapshots_from_date.
    Returns the number of summary snapshots updated.
    """
    user_portfolios = [
        p for p in portfolios.list_portfolios(user_id)
        if p.get("portfolioId") != "summary"
    ]
    all_summary_snapshots = list_snapshots(user_id, "summary")
    xirr_history = [dict(s) for s in all_summary_snapshots]
    xirr_history_by_date = {str(s["snapshotDate"]): s for s in xirr_history}
    summary_snapshots = sorted(
        [s for s in all_summary_snapshots if str(s.get("snapshotDate", "")) >= from_date],
        key=lambda s: s["snapshotDate"],
    )
    if not summary_snapshots:
        return 0

    # Build a lookup: portfolioId -> {date_str -> snapshot}
    portfolio_snap_map: dict = {}
    for p in user_portfolios:
        pid = p["portfolioId"]
        snaps = list_snapshots(user_id, pid)
        portfolio_snap_map[pid] = {str(s["snapshotDate"]): s for s in snaps}

    now = _now_iso()
    updated = 0
    with _table().batch_writer() as batch:
        for summary_snap in summary_snapshots:
            snap_date = summary_snap["snapshotDate"]
            total_portfolio_value = Decimal("0")
            total_investment_value = Decimal("0")
            for snaps_by_date in portfolio_snap_map.values():
                day_snap = snaps_by_date.get(snap_date)
                if day_snap:
                    total_portfolio_value += _to_decimal(day_snap.get("portfolioValue", 0))
                    total_investment_value += _to_decimal(day_snap.get("investmentValue", 0))

            xirr_snapshot = xirr_history_by_date.get(str(snap_date))
            if xirr_snapshot is not None:
                xirr_snapshot["portfolioValue"] = total_portfolio_value
                xirr_snapshot["investmentValue"] = total_investment_value
            snap_xirr = _xirr_from_investment_history(xirr_history, snap_date)

            item: dict = {
                "userId": user_id,
                "sk": _snapshot_sk("summary", snap_date),
                "portfolioId": "summary",
                "snapshotDate": snap_date,
                "portfolioValue": _quantize_money(total_portfolio_value),
                "investmentValue": _quantize_money(total_investment_value),
                "xirr": snap_xirr,
                "xirrVersion": _XIRR_CALCULATION_VERSION,
                "updatedAt": now,
                "createdAt": summary_snap.get("createdAt", now),
            }
            if summary_snap.get("benchmarkId"):
                item["benchmarkId"] = summary_snap["benchmarkId"]
            if summary_snap.get("benchmarkValue") not in (None, ""):
                item["benchmarkValue"] = _quantize_money(summary_snap["benchmarkValue"])
            if summary_snap.get("dailyReturn") not in (None, ""):
                item["dailyReturn"] = _to_decimal(summary_snap["dailyReturn"])

            batch.put_item(Item=item)
            updated += 1

    recalculate_ath(user_id, "summary")
    return updated


def recalculate_snapshot_xirr_from_date(user_id: str, portfolio_id: str, from_date: str) -> int:
    all_snapshots = sorted(list_snapshots(user_id, portfolio_id), key=lambda item: item["snapshotDate"])
    snapshots_to_update = [snapshot for snapshot in all_snapshots if str(snapshot.get("snapshotDate", "")) >= from_date]
    if not snapshots_to_update:
        return 0

    now = _now_iso()
    updated = 0
    for snapshot in snapshots_to_update:
        snap_date = snapshot["snapshotDate"]
        item = dict(snapshot)
        item["userId"] = user_id
        item["sk"] = _snapshot_sk(portfolio_id, snap_date)
        item["portfolioId"] = portfolio_id
        item["snapshotDate"] = snap_date
        item["xirr"] = _xirr_from_investment_history(all_snapshots, snap_date)
        item["xirrVersion"] = _XIRR_CALCULATION_VERSION
        item["updatedAt"] = now
        item["createdAt"] = snapshot.get("createdAt", now)
        _table().put_item(Item=item)
        updated += 1

    return updated


def backfill_missing_xirr(user_id: str):
    """
    Scans all snapshots for the user. If any snapshot is missing 'xirr' or has
    an older XIRR calculation version, triggers recalculation starting from the
    earliest affected snapshot.
    """
    user_portfolios = portfolios.list_portfolios(user_id)
    
    # 1. Backfill real portfolios
    for p in user_portfolios:
        pid = p["portfolioId"]
        snaps = list_snapshots(user_id, pid)
        affected = [s for s in snaps if _needs_xirr_backfill(s)]
        if not affected:
            continue
            
        first_affected = min(s["snapshotDate"] for s in affected)
        print(f"Missing or stale XIRR for {user_id} / {pid} starting {first_affected}. Triggering recalculate.")
        recalculate_snapshot_xirr_from_date(user_id, pid, first_affected)

    # 2. Backfill summary portfolio
    summary_snaps = list_snapshots(user_id, "summary")
    summary_affected = [s for s in summary_snaps if _needs_xirr_backfill(s)]
    if summary_affected:
        first_affected = min(s["snapshotDate"] for s in summary_affected)
        print(f"Missing or stale XIRR for {user_id} / summary starting {first_affected}. Triggering recalculate.")
        recalculate_snapshot_xirr_from_date(user_id, "summary", first_affected)
