"""benchmark_returns.py — Monthly benchmark return storage and calculation.

Stores pre-computed monthly returns for each benchmark index in SnapshotsTable
using a shared partition key "__benchmarks__".

DynamoDB schema (SnapshotsTable):
  PK  userId:      "__benchmarks__"   (never conflicts with a real Cognito UUID)
  SK  sk:          "BENCHMARK#<id>#MONTH#<YYYY-MM>"

Item attributes:
  benchmarkId  str      e.g. "WIG"
  month        str      "YYYY-MM"
  returnPct    Decimal  (close − prev_close) / prev_close × 100
  openPrice    Decimal  last-trading-day close of the PREVIOUS month
  closePrice   Decimal  last-trading-day close of THIS month
  updatedAt    str      ISO-8601 UTC

Lambda handler supports three invocations:
  Scheduled (EventBridge, day 2 of each month):
      {} or {"action": "update"}
      → saves the just-completed month's return for every benchmark

  Manual backfill (invoke directly via AWS Console / CLI):
      {"action": "backfill", "from": "2020-01"}
      → fills every benchmark from from_ym to today

  Targeted single benchmark:
      {"action": "update", "benchmarkId": "WIG"}
      → updates only that benchmark
"""

import os
import json
from datetime import date, datetime, timezone
from decimal import Decimal

import boto3
import yfinance as yf
from boto3.dynamodb.conditions import Key

SNAPSHOTS_TABLE = os.environ.get("SNAPSHOTS_TABLE", "")

# Special partition key — Cognito UUIDs never match this value.
_BENCHMARK_PK = "__benchmarks__"


# ── DynamoDB helpers ──────────────────────────────────────────────────────

def _table():
    region = os.environ.get("AWS_REGION", "eu-central-1")
    ddb = boto3.resource("dynamodb", region_name=region)
    return ddb.Table(SNAPSHOTS_TABLE)


def _sk(benchmark_id: str, ym: str) -> str:
    return f"BENCHMARK#{benchmark_id}#MONTH#{ym}"


# ── YYYY-MM arithmetic ────────────────────────────────────────────────────

def _prev_ym(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    m -= 1
    if m < 1:
        m, y = 12, y - 1
    return f"{y}-{m:02d}"


def _add_months(ym: str, n: int = 1) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    m += n
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    return f"{y}-{m:02d}"


def _today_ym() -> str:
    d = date.today()
    return f"{d.year}-{d.month:02d}"


# ── Public read API ───────────────────────────────────────────────────────

def list_monthly_returns(benchmark_id: str, from_ym: str | None = None) -> list[dict]:
    """
    Return stored monthly returns for a benchmark, sorted ascending by month.
    Optionally filters to months >= from_ym.
    """
    tbl = _table()
    prefix = f"BENCHMARK#{benchmark_id}#MONTH#"
    items: list[dict] = []
    kwargs: dict = {
        "KeyConditionExpression":
            Key("userId").eq(_BENCHMARK_PK) & Key("sk").begins_with(prefix)
    }
    while True:
        resp = tbl.query(**kwargs)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek

    if from_ym:
        items = [i for i in items if i.get("month", "") >= from_ym]
    items.sort(key=lambda x: x.get("month", ""))
    return items


# ── yfinance helpers ──────────────────────────────────────────────────────

def _is_polish_ticker(ticker: str) -> bool:
    """WIG.WA, WIG20.WA etc. only work with yfinance 60m (last 730 days).
    Global tickers (^GSPC, ^GDAXI, IWDA.AS …) work fine with 1d for any range."""
    return ticker.upper().endswith(".WA")


def _fetch_last_trading_day_closes_daily(
    ticker: str, from_date_str: str, to_date_str: str
) -> dict[str, float]:
    """Daily bars → {YYYY-MM: last_trading_day_close}. Works for global indices."""
    tkr = yf.Ticker(ticker)
    df = tkr.history(start=from_date_str, end=to_date_str, interval="1d")
    if df.empty:
        return {}
    closes: dict[str, float] = {}
    for idx, row in df.iterrows():
        ym = idx.strftime("%Y-%m")
        closes[ym] = round(float(row["Close"]), 4)
    return closes


def _fetch_last_trading_day_closes_hourly(
    ticker: str, from_date_str: str, to_date_str: str
) -> dict[str, float]:
    """
    Hourly 60m bars in 59-day chunks → {YYYY-MM: last_trading_day_close}.
    Needed for Polish (.WA) tickers — yfinance only returns hourly data for them,
    limited to the last 730 days.
    """
    from datetime import datetime, timedelta, timezone
    import pandas as pd

    CHUNK_DAYS = 59
    tkr = yf.Ticker(ticker)

    end_dt = datetime.strptime(to_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_dt = datetime.strptime(from_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    # yfinance 60m limit: cannot go back more than 730 days from now
    earliest = now - timedelta(days=729)
    start_dt = max(start_dt, earliest)

    chunks: list = []
    cur_end = min(end_dt, now + timedelta(days=1))
    while cur_end > start_dt:
        cur_start = max(cur_end - timedelta(days=CHUNK_DAYS), start_dt)
        try:
            h = tkr.history(
                start=cur_start.strftime("%Y-%m-%d"),
                end=cur_end.strftime("%Y-%m-%d"),
                interval="60m",
            )
            if not h.empty:
                chunks.append(h)
        except Exception as exc:
            print(f"[benchmark_returns] 60m chunk error for {ticker}: {exc}")
        cur_end = cur_start - timedelta(days=1)

    if not chunks:
        return {}

    df = pd.concat(chunks[::-1])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    try:
        df.index = df.index.tz_convert("Europe/Warsaw")
    except Exception:
        df.index = df.index.tz_convert("UTC")

    closes: dict[str, float] = {}
    for idx, row in df.iterrows():
        ym = idx.strftime("%Y-%m")
        closes[ym] = round(float(row["Close"]), 4)
    return closes


def _fetch_last_trading_day_closes(
    ticker: str, from_date_str: str, to_date_str: str
) -> dict[str, float]:
    """Dispatch to hourly (Polish .WA) or daily (global) fetcher."""
    if _is_polish_ticker(ticker):
        return _fetch_last_trading_day_closes_hourly(ticker, from_date_str, to_date_str)
    return _fetch_last_trading_day_closes_daily(ticker, from_date_str, to_date_str)


# ── Core computation ──────────────────────────────────────────────────────

def compute_and_save_monthly_returns(
    benchmark_id: str,
    ticker: str,
    from_ym: str = "2020-01",
    to_ym: str | None = None,
    overwrite: bool = True,
) -> int:
    """
    Fetch daily history, derive end-of-month closes, calculate and persist
    monthly percentage returns.  Returns the count of records written.

    A monthly return is defined as:
        (close_last_trading_day_month_M − close_last_trading_day_month_M-1)
        / close_last_trading_day_month_M-1  × 100
    """
    if not to_ym:
        to_ym = _today_ym()

    # Need the previous month's close to compute from_ym's return.
    fetch_from_ym = _prev_ym(from_ym)
    fetch_from_date = f"{fetch_from_ym[:4]}-{fetch_from_ym[5:7]}-01"

    # yfinance end is exclusive — use mid-month one month past to_ym.
    fetch_to_ym = _add_months(to_ym, 1)
    fetch_to_date = f"{fetch_to_ym[:4]}-{fetch_to_ym[5:7]}-15"

    print(
        f"[benchmark_returns] fetching {benchmark_id} ({ticker}) "
        f"{fetch_from_date} → {fetch_to_date}"
    )

    closes = _fetch_last_trading_day_closes(ticker, fetch_from_date, fetch_to_date)
    if not closes:
        print(f"[benchmark_returns] no data returned for {benchmark_id}")
        return 0

    tbl = _table()
    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    saved = 0

    ym = from_ym
    while ym <= to_ym:
        prev = _prev_ym(ym)
        if ym in closes and prev in closes:
            prev_close = closes[prev]
            curr_close = closes[ym]
            if prev_close > 0:
                ret_pct = round((curr_close - prev_close) / prev_close * 100, 6)
                item = {
                    "userId":      _BENCHMARK_PK,
                    "sk":          _sk(benchmark_id, ym),
                    "benchmarkId": benchmark_id,
                    "month":       ym,
                    "returnPct":   Decimal(str(ret_pct)),
                    "openPrice":   Decimal(str(prev_close)),
                    "closePrice":  Decimal(str(curr_close)),
                    "updatedAt":   now_str,
                }
                if overwrite:
                    tbl.put_item(Item=item)
                    saved += 1
                else:
                    existing = tbl.get_item(
                        Key={"userId": _BENCHMARK_PK, "sk": _sk(benchmark_id, ym)}
                    ).get("Item")
                    if not existing:
                        tbl.put_item(Item=item)
                        saved += 1
        ym = _add_months(ym, 1)

    print(f"[benchmark_returns] saved {saved} records for {benchmark_id}")
    return saved


def update_last_completed_month(benchmark_id: str, ticker: str) -> int:
    """
    Recalculate and save the monthly return for the most recently completed
    calendar month.  Call from the day-2-of-month EventBridge schedule.
    """
    curr_ym = _today_ym()
    last_ym = _prev_ym(curr_ym)
    return compute_and_save_monthly_returns(
        benchmark_id, ticker, from_ym=last_ym, to_ym=last_ym
    )


# ── Lambda handler ────────────────────────────────────────────────────────

def handler(event, context):  # noqa: ANN001 (context typed by AWS)
    """
    Entry point invoked by EventBridge schedule or manual Lambda invocations.

    Event shapes:
      {}                                       → monthly update (all benchmarks)
      {"action": "update"}                     → same
      {"action": "update",  "benchmarkId": "WIG"}   → single benchmark
      {"action": "backfill", "from": "2020-01"}      → full historical backfill
      {"action": "backfill", "from": "2020-01", "to": "2024-12"}  → range
    """
    from db import BENCHMARKS  # imported here to keep module importable standalone

    action = event.get("action", "update")
    from_ym = event.get("from", "2020-01")
    only_bid = event.get("benchmarkId")

    targets: dict = (
        {only_bid: BENCHMARKS[only_bid]}
        if only_bid and only_bid in BENCHMARKS
        else dict(BENCHMARKS)
    )

    results: dict = {}

    if action == "backfill":
        to_ym = event.get("to")
        for bid, bm in targets.items():
            try:
                count = compute_and_save_monthly_returns(
                    bid, bm["ticker"], from_ym=from_ym, to_ym=to_ym
                )
                results[bid] = {"saved": count}
            except Exception as exc:
                results[bid] = {"error": str(exc)}
                print(f"[benchmark_returns] {bid} backfill error: {exc}")
    else:
        # Regular monthly update — save last completed month only.
        for bid, bm in targets.items():
            try:
                count = update_last_completed_month(bid, bm["ticker"])
                results[bid] = {"saved": count}
            except Exception as exc:
                results[bid] = {"error": str(exc)}
                print(f"[benchmark_returns] {bid} update error: {exc}")

    return {"statusCode": 200, "body": json.dumps(results)}
