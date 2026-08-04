"""
Lambda handler — fetches live prices from Yahoo Finance and returns portfolio JSON.
CSV portfolio files are bundled as fallback under ./data/
Price cache is stored in S3 so stale-but-valid prices are used when market is closed.
User profiles are stored in DynamoDB (see db.py).
Portfolios + holdings are stored in DynamoDB (see portfolios.py).
"""

import base64
import json
import os
import re
import time as _time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta, timezone
from time import perf_counter

import boto3
import yfinance as yf

import db          # DynamoDB user-profile helpers
import portfolios  # DynamoDB portfolios + holdings helpers
import retirement_plans
import snapshots   # Daily snapshot + ATH helpers
import roast_engine

CLOUDFRONT_ORIGIN = "https://d750c9gknegtj.cloudfront.net"

TICKER_MAP = {
    "XTB":                          ("XTB.WA",  "PLN"),
    "RAINBOW (RBW)":                ("RBW.WA",  "PLN"),
    "MOBRUK (MBR)":                 ("MBR.WA",  "PLN"),
    "Mobruk":                       ("MBR.WA",  "PLN"),
    "MOBRUK":                       ("MBR.WA",  "PLN"),
    "ARTIFEX":                      ("ART.WA",  "PLN"),
    "Artifex":                      ("ART.WA",  "PLN"),
    "Artifex Mundi":                ("ART.WA",  "PLN"),
    "ARTIFEX MUNDI":                ("ART.WA",  "PLN"),
    "CREOTECH (CRI)":               ("CRI.WA",  "PLN"),
    "CDPROJEKT (CDR)":              ("CDR.WA",  "PLN"),
    "Meta Platforms, Inc. (META)":  ("META",     "USD"),
    "Bitcoin (BTC)":                ("BTC-USD",  "USD"),
}

DATA_DIR     = os.path.join(os.path.dirname(__file__), "data")
CACHE_KEY     = "price-cache.json"
WIG_CACHE_KEY = "wig-history.json"      # legacy key kept for migration compat
BARS_CACHE_KEY = "bars-cache-{}.json"   # formatted with ISO date; one file per day
CACHE_BUCKET  = os.environ.get("CACHE_BUCKET", "")

def _benchmark_cache_key(benchmark_id: str) -> str:
    """Return S3 key for a given benchmark's history cache."""
    return f"benchmark-{benchmark_id}.json"

WALLETS = {
    "Emerytura": os.path.join(DATA_DIR, "myfund.pl_Emerytura_portfelSklad.csv"),
    "IKE":       os.path.join(DATA_DIR, "myfund.pl_IKE_portfelSklad.csv"),
    "IKZE":      os.path.join(DATA_DIR, "myfund.pl_IKZE_portfelSklad.csv"),
    "XTB":       os.path.join(DATA_DIR, "myfund.pl_XTB_portfelSklad.csv"),
}
MARKET_CAROUSEL_IDS = ["WIG", "WIG20", "MWIG40", "SWIG80", "SP500", "NASDAQ", "DAX", "MSCI_WORLD"]


def _query_value(event: dict, key: str, default=None):
    params = event.get("queryStringParameters") or {}
    return params.get(key, default)


def _prices_view(event: dict) -> str:
    view = str(_query_value(event, "view", "full") or "full").strip().lower()
    if view == "lite":
        return "lite"
    if view == "history":
        return "history"
    return "full"

# ── S3 price cache ────────────────────────────────────────────

def load_s3_cache():
    """Load last-known {ticker: [price, daily_pct, ytd_pct]} from S3."""
    if not CACHE_BUCKET:
        return {}
    try:
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=CACHE_BUCKET, Key=CACHE_KEY)
        return json.loads(obj["Body"].read())
    except Exception as e:
        print(f"Cache load skipped: {e}")
        return {}

def save_s3_cache(cache):
    """Persist updated prices to S3 for future fallback."""
    if not CACHE_BUCKET:
        return
    try:
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=CACHE_BUCKET,
            Key=CACHE_KEY,
            Body=json.dumps(cache),
            ContentType="application/json",
        )
        print(f"Price cache saved ({len(cache)} tickers)")
    except Exception as e:
        print(f"Cache save failed: {e}")

# ── WIG index cache ───────────────────────────────────────────

def load_wig_cache():
    """Load cached WIG history from S3. Returns dict with daily/weekly/intraday lists."""
    return load_benchmark_cache("WIG")

def save_wig_cache(data):
    save_benchmark_cache("WIG", data)

# ── Per-ticker bars cache ─────────────────────────────────────
# Stores {ticker: {todayBars, yearBars, ytdPct, ts, date}} for one calendar day.
# todayBars are considered fresh for 3 minutes; yearBars for the full calendar day.
# This avoids re-fetching heavy history() calls on every full Lambda invocation.

def load_bars_cache() -> dict:
    """Load today's bars cache from S3. Returns {} on miss or error."""
    if not CACHE_BUCKET:
        return {}
    key = BARS_CACHE_KEY.format(date.today().isoformat())
    try:
        s3  = boto3.client("s3")
        obj = s3.get_object(Bucket=CACHE_BUCKET, Key=key)
        return json.loads(obj["Body"].read())
    except Exception:
        return {}

def save_bars_cache(bars_data: dict):
    """Persist bars data to S3 keyed by today's date (stale files are auto-ignored)."""
    if not CACHE_BUCKET or not bars_data:
        return
    key = BARS_CACHE_KEY.format(date.today().isoformat())
    try:
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=CACHE_BUCKET, Key=key,
            Body=json.dumps(bars_data),
            ContentType="application/json",
        )
        print(f"Bars cache saved ({len(bars_data)} tickers)")
    except Exception as e:
        print(f"Bars cache save failed: {e}")

def load_benchmark_cache(benchmark_id: str) -> dict:
    """Load cached benchmark history from S3."""
    if not CACHE_BUCKET:
        return {}
    s3_key = _benchmark_cache_key(benchmark_id)
    try:
        s3  = boto3.client("s3")
        obj = s3.get_object(Bucket=CACHE_BUCKET, Key=s3_key)
        return json.loads(obj["Body"].read())
    except Exception as e:
        print(f"{benchmark_id} cache load skipped ({s3_key}): {e}")
        return {}

def save_benchmark_cache(benchmark_id: str, data: dict):
    if not CACHE_BUCKET:
        return
    s3_key = _benchmark_cache_key(benchmark_id)
    try:
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=CACHE_BUCKET,
            Key=s3_key,
            Body=json.dumps(data),
            ContentType="application/json",
        )
        print(f"{benchmark_id} cache saved (daily={len(data.get('daily',[]))}, intraday={len(data.get('intraday',[]))})")
    except Exception as e:
        print(f"{benchmark_id} cache save failed: {e}")

def fetch_benchmark_history(benchmark_id: str, ticker: str, existing: dict) -> dict:
    """
    Fetch OHLCV history for any benchmark ticker via yfinance.

    Strategy:
      - Long history (≤ 1 year): hourly chunks aggregated to daily/weekly/monthly
      - Intraday: last trading day at 1-minute intervals (shown on dashboard by default)
      - Incremental: if cache is recent (< 5 days old) only fetch latest chunk
      - S3 key is per-benchmark so each benchmark has its own cache
    """
    import pandas as pd

    CHUNK_DAYS = 59    # Yahoo Finance max per 60m request
    MAX_CHUNKS = 7     # 7 × 59 ≈ 413 days (> 1 year)
    today      = date.today()
    now        = datetime.now(tz=timezone.utc)
    ticker_obj = yf.Ticker(ticker)

    result   = dict(existing)
    daily_ok = (result.get("version", 1) >= 2 and len(result.get("daily", [])) > 100)

    # Incremental vs full rebuild
    if daily_ok:
        last_t   = result["daily"][-1]["t"]
        days_old = (today - datetime.strptime(last_t, "%Y-%m-%d").date()).days
        n_chunks = min(max(1, days_old // CHUNK_DAYS + 2), MAX_CHUNKS)
        print(f"{benchmark_id}: incremental update ({days_old}d old, {n_chunks} chunks)")
    else:
        n_chunks = MAX_CHUNKS
        result   = {"version": 2}
        print(f"{benchmark_id}: full rebuild ({n_chunks} chunks)")

    # ── Fetch hourly chunks (1-year window) ───────────────────
    chunks = []
    end = now
    for i in range(n_chunks):
        start = end - timedelta(days=CHUNK_DAYS)
        try:
            h = ticker_obj.history(start=start.strftime('%Y-%m-%d'),
                                   end=end.strftime('%Y-%m-%d'),
                                   interval='60m')
            if not h.empty:
                chunks.append(h)
                print(f"  {benchmark_id} chunk {i}: {len(h)} rows")
        except Exception as e:
            print(f"  {benchmark_id} chunk {i} error: {e}")
        end = start - timedelta(days=1)

    if not chunks:
        print(f"{benchmark_id}: no hourly data — using existing cache")
        # Still try to refresh intraday
        try:
            intra_df = ticker_obj.history(period='1d', interval='1m')
            result["intraday"] = _to_ts_rows_plain(intra_df) if not intra_df.empty else []
        except Exception:
            pass
        return result

    recent_df = pd.concat(chunks[::-1])
    recent_df = recent_df[~recent_df.index.duplicated(keep='last')].sort_index()

    # ── Aggregation helpers ───────────────────────────────────
    def _agg_daily(df):
        h = df.copy()
        try:
            h.index = h.index.tz_convert('Europe/Warsaw')
        except Exception:
            h.index = h.index.tz_convert('UTC')
        agg = h.resample('D').agg(
            {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        ).dropna(subset=['Close'])
        return [{'t': idx.strftime('%Y-%m-%d'),
                 'o': round(float(r['Open']),2),  'h': round(float(r['High']),2),
                 'l': round(float(r['Low']),2),   'c': round(float(r['Close']),2),
                 'v': int(r['Volume'] or 0)} for idx, r in agg.iterrows()]

    def _agg_weekly(daily_rows):
        if not daily_rows: return []
        df = pd.DataFrame(daily_rows)
        df['t'] = pd.to_datetime(df['t'])
        agg = df.set_index('t').sort_index().resample('W-MON', closed='left', label='left').agg(
            {'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last', 'v': 'sum'}
        ).dropna(subset=['c'])
        return [{'t': idx.strftime('%Y-%m-%d'),
                 'o': round(float(r['o']),2), 'h': round(float(r['h']),2),
                 'l': round(float(r['l']),2), 'c': round(float(r['c']),2),
                 'v': int(r['v'] or 0)} for idx, r in agg.iterrows()]

    def _agg_monthly(daily_rows):
        if not daily_rows: return []
        df = pd.DataFrame(daily_rows)
        df['t'] = pd.to_datetime(df['t'])
        agg = df.set_index('t').sort_index().resample('MS').agg(
            {'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last', 'v': 'sum'}
        ).dropna(subset=['c'])
        return [{'t': idx.strftime('%Y-%m-%d'),
                 'o': round(float(r['o']),2), 'h': round(float(r['h']),2),
                 'l': round(float(r['l']),2), 'c': round(float(r['c']),2),
                 'v': int(r['v'] or 0)} for idx, r in agg.iterrows()]

    # ── Build daily candles ───────────────────────────────────
    new_daily = _agg_daily(recent_df)
    if daily_ok and n_chunks < MAX_CHUNKS and new_daily:
        cutoff = new_daily[0]["t"]
        existing_daily = [d for d in result.get("daily", []) if d["t"] < cutoff]
        result["daily"] = existing_daily + new_daily
    else:
        result["daily"] = new_daily

    result["weekly"]  = _agg_weekly(result["daily"])
    result["monthly"] = _agg_monthly(result["daily"])
    print(f"{benchmark_id} daily={len(result['daily'])}, weekly={len(result['weekly'])}, "
          f"monthly={len(result['monthly'])}")

    # ── Hourly (last 60d, unix timestamps) ────────────────────
    cutoff_60d = now - timedelta(days=60)
    result["hourly"] = _to_ts_rows_plain(recent_df[recent_df.index >= cutoff_60d])
    print(f"{benchmark_id} hourly: {len(result['hourly'])} bars")

    # ── Intraday 1m (last trading day — default view) ─────────
    try:
        intra_df = ticker_obj.history(period='1d', interval='1m')
        result["intraday"] = _to_ts_rows_plain(intra_df) if not intra_df.empty else []
    except Exception as e:
        print(f"{benchmark_id} intraday error: {e}")
        result["intraday"] = []
    print(f"{benchmark_id} intraday: {len(result['intraday'])} 1m bars")

    result["version"]  = 2
    result["ticker"]   = ticker
    result["updated"]  = today.isoformat()
    return result


def _serialize_benchmark_history(benchmark_data: dict) -> dict:
    return {
        "daily":    benchmark_data.get("daily", []),
        "weekly":   benchmark_data.get("weekly", []),
        "monthly":  benchmark_data.get("monthly", []),
        "hourly":   benchmark_data.get("hourly", []),
        "intraday": benchmark_data.get("intraday", []),
        "updated":  benchmark_data.get("updated", ""),
    }


def _compute_benchmark_daily_pct(benchmark_data: dict, ticker: str | None = None) -> float | None:
    intraday = benchmark_data.get("intraday", [])
    if len(intraday) >= 2:
        open_price = intraday[0].get("o")
        close_price = intraday[-1].get("c")
        if open_price and close_price:
            return round((close_price - open_price) / open_price * 10000) / 100

    daily = benchmark_data.get("daily", [])
    if len(daily) >= 2:
        prev_close = daily[-2].get("c")
        close_price = daily[-1].get("c")
        if prev_close and close_price:
            return round((close_price - prev_close) / prev_close * 10000) / 100

    if ticker:
        try:
            info = yf.Ticker(ticker).fast_info
            price = info.last_price
            prev = info.previous_close
            if price and prev:
                return round((price - prev) / prev * 10000) / 100
        except Exception as info_err:
            print(f"{ticker} fast_info daily % failed (non-fatal): {info_err}")
    return None


def _build_market_carousel_entry(benchmark_id: str, benchmark_data: dict, daily_pct: float | None = None) -> dict | None:
    meta = db.BENCHMARKS.get(benchmark_id)
    if not meta:
        return None
    spark_source = benchmark_data.get("intraday") or benchmark_data.get("daily") or []
    sparkline = [
        {"t": point.get("t"), "c": point.get("c")}
        for point in spark_source[-24:]
        if point.get("c") is not None
    ]
    if not sparkline:
        return None
    return {
        "id": benchmark_id,
        "name": meta["name"],
        "exchange": meta["exchange"],
        "dailyPct": daily_pct if daily_pct is not None else _compute_benchmark_daily_pct(benchmark_data),
        "sparkline": sparkline,
    }

def _to_ts_rows_plain(df):
    """Convert a yfinance DataFrame to [{t, o, h, l, c, v}] with unix timestamps."""
    import pandas as pd
    return [{'t': int(idx.timestamp()),
             'o': round(float(r['Open']),2),  'h': round(float(r['High']),2),
             'l': round(float(r['Low']),2),   'c': round(float(r['Close']),2),
             'v': int(r['Volume'] or 0)}
            for idx, r in df.iterrows() if not pd.isna(r['Close'])]

def fetch_wig_history(existing):
    """Backward-compat wrapper — fetches WIG.WA via the generic benchmark fetcher."""
    return fetch_benchmark_history("WIG", "WIG.WA", existing)

# ── CORS / response helpers ───────────────────────────────────

from decimal import Decimal

import math

class _DecimalEncoder(json.JSONEncoder):
    """DynamoDB returns Decimal for all numeric types — convert to int or float.
    Also converts float NaN/Inf to None so the output is valid JSON."""
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        return super().default(o)

    @staticmethod
    def _sanitize(obj):
        if isinstance(obj, float):
            return None if (math.isnan(obj) or math.isinf(obj)) else obj
        if isinstance(obj, dict):
            return {k: _DecimalEncoder._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_DecimalEncoder._sanitize(v) for v in obj]
        return obj

def _cors_headers(cache_seconds=0):
    h = {
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,PUT,POST,DELETE,OPTIONS",
        "Content-Type": "application/json",
    }
    if cache_seconds:
        h["Cache-Control"] = f"public, max-age={cache_seconds}, stale-while-revalidate={cache_seconds * 2}"
    else:
        h["Cache-Control"] = "no-cache, no-store"
    return h

def _resp(status, body, cache_seconds=0):
    try:
        payload = json.dumps(_DecimalEncoder._sanitize(body), cls=_DecimalEncoder)
    except Exception as e:
        print(f"JSON SERIALIZE ERROR: {e}")
        payload = '{"error": "Internal serialization error"}'
    return {"statusCode": status, "headers": _cors_headers(cache_seconds), "body": payload}


# ── RBAC middleware ───────────────────────────────────────────

def _require_role(event: dict, min_role: str = db.ROLE_BASIC) -> tuple[str | None, dict | None]:
    """
    Validate JWT and check the user has at least `min_role`.

    Returns (user_id, None) on success.
    Returns (None, error_response) if auth fails or role is insufficient.

    Usage:
        user_id, err = _require_role(event, db.ROLE_ADVANCED)
        if err: return err
    """
    if event.get("httpMethod") == "OPTIONS":
        return None, _resp(200, {})

    user_id, _, _ = _get_caller_identity(event)
    if not user_id:
        return None, _resp(401, {"error": "Authentication required"})

    if min_role == db.ROLE_BASIC:
        return user_id, None   # any authenticated user is fine

    # For ADVANCED check: look up the role in DynamoDB
    user_role = db.get_user_role(user_id)
    role_rank = {db.ROLE_BASIC: 0, db.ROLE_ADVANCED: 1}
    if role_rank.get(user_role, 0) < role_rank.get(min_role, 99):
        return None, _resp(403, {
            "error":    "Insufficient permissions",
            "required": min_role,
            "current":  user_role,
        })

    return user_id, None

# ── CSV parsing ───────────────────────────────────────────────

def parse_wallet_csv(path):
    holdings = []
    with open(path, encoding="iso-8859-1") as f:
        lines = f.read().strip().split("\n")
    for line in lines[1:]:
        parts = line.split(";")
        name = parts[0].strip()
        if name.startswith("Razem") or not name:
            continue
        def clean(v): return v.strip().replace("\xa0", "").replace("\u00a0", "").replace(" ", "")
        try:
            units = float(clean(parts[6]))
            pv    = float(clean(parts[9]))
            ticker, currency = TICKER_MAP.get(name, (None, "PLN"))
            holdings.append({"name": name, "units": units, "purchaseValue": pv,
                              "ticker": ticker, "currency": currency})
        except (ValueError, IndexError):
            pass
    return holdings

# ── Price fetching ────────────────────────────────────────────

def get_pln_rate(currency, rates_cache, s3_cache):
    if currency == "PLN":
        return 1.0, 1.0
    key = f"FX_{currency}PLN"
    if key in rates_cache:
        return rates_cache[key]
    try:
        info = yf.Ticker(f"{currency}PLN=X").fast_info
        rate = info.last_price
        prev_rate = info.previous_close or rate
        if rate and rate > 0:
            rates_cache[key] = (rate, prev_rate)
            s3_cache[key] = [rate, 0, 0]   # store for fallback
            return rate, prev_rate
    except Exception:
        pass
    # Fallback to cached rate
    if key in s3_cache:
        rate = s3_cache[key][0]
        rates_cache[key] = (rate, rate)
        print(f"  Using cached FX rate {currency}/PLN: {rate}")
        return rate, rate
    return None, None

def fetch_ticker_data(ticker_sym, include_bars=True, bars_cache=None):
    t = yf.Ticker(ticker_sym)
    info = t.fast_info
    price = info.last_price
    prev_close = info.previous_close
    daily_pct = round(((price - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
    # Intraday session change: today's open → current price (for gauge / commentary)
    open_price = getattr(info, 'open', None)
    intraday_pct = round(((price - open_price) / open_price) * 100, 2) if open_price else daily_pct

    today_bars = []
    year_bars  = []
    ytd_pct = 0.0

    if include_bars:
        now_ts   = _time.time()
        today_str = date.today().isoformat()
        cached   = (bars_cache or {}).get(ticker_sym)

        # todayBars: use S3 cache if < 3 minutes stale, else re-fetch from yfinance
        if cached and now_ts - cached.get('ts', 0) < 180:
            today_bars = list(cached.get('todayBars', []))
            print(f"  {ticker_sym}: todayBars from cache ({len(today_bars)} pts)")
        else:
            try:
                intra = t.history(period='1d', interval='1m')
                for ts, row in intra.iterrows():
                    c = row['Close']
                    if c and c == c:
                        today_bars.append([int(ts.timestamp() * 1000), round(float(c), 4)])
            except Exception:
                pass

        # yearBars: valid for the entire calendar day — re-fetch only on a new trading day
        if cached and cached.get('date') == today_str:
            year_bars = list(cached.get('yearBars', []))
            ytd_pct   = cached.get('ytdPct', 0.0)
            print(f"  {ticker_sym}: yearBars from cache ({len(year_bars)} pts)")
        else:
            try:
                hist = t.history(period='1y', interval='1wk')
                for ts, row in hist.iterrows():
                    c = row['Close']
                    if c and c == c:
                        year_bars.append([int(ts.timestamp() * 1000), round(float(c), 4)])
                if year_bars:
                    ytd_pct = round(((price - year_bars[0][1]) / year_bars[0][1]) * 100, 2)
            except Exception:
                ytd_pct = 0.0

        # Pin the last data point to current price and timestamp
        now_ms = int(now_ts * 1000)
        if today_bars:
            today_bars[-1] = [now_ms, round(price, 4)]
        else:
            today_bars.append([now_ms, round(price, 4)])
        if year_bars:
            year_bars[-1] = [now_ms, round(price, 4)]
        else:
            year_bars.append([now_ms, round(price, 4)])

    return price, daily_pct, intraday_pct, ytd_pct, today_bars, year_bars


def _prefetch_prices_parallel(
    unique_tickers: set,
    include_bars: bool,
    s3_cache: dict,
    price_cache: dict,
    bars_cache: dict | None = None,
):
    """
    Fetch prices (and optionally bars) for all tickers concurrently.
    Populates price_cache and s3_cache in-place; does not re-fetch tickers
    that are already in price_cache.
    """
    needed = [t for t in unique_tickers if t and t not in price_cache]
    if not needed:
        return

    def _fetch_one(ticker):
        try:
            result = fetch_ticker_data(ticker, include_bars=include_bars, bars_cache=bars_cache)
            if result[0] and result[0] > 0:
                return ticker, result
        except Exception as e:
            print(f"  Parallel fetch {ticker} failed: {e}")
        # Fall back to S3 price cache
        if ticker in s3_cache:
            c = s3_cache[ticker]
            return ticker, (c[0], c[1], c[1], c[2], [], [])  # (price, daily, intraday=daily, ytd, [], [])
        return ticker, None

    workers = min(len(needed), 10)
    print(f"Parallel price fetch: {len(needed)} tickers, {workers} workers")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for ticker, result in pool.map(_fetch_one, needed):
            if result:
                price_cache[ticker] = result
                s3_cache[ticker]    = [result[0], result[1], result[3], [], []]


def _compute_benchmark_intraday_pct(ticker: str) -> float | None:
    """Intraday benchmark % change: today's open → current price, via fast_info."""
    try:
        info = yf.Ticker(ticker).fast_info
        price  = info.last_price
        open_p = getattr(info, 'open', None)
        if price and open_p:
            return round((price - open_p) / open_p * 10000) / 100
        # Fallback: prev-close → current when market open price is unavailable
        prev = info.previous_close
        if price and prev:
            return round((price - prev) / prev * 10000) / 100
    except Exception as e:
        print(f"{ticker} intraday pct via fast_info failed (non-fatal): {e}")
    return None

# ── Wallet computation ────────────────────────────────────────

def compute_wallet(user_id, portfolio_id, holdings, price_cache, rates_cache, s3_cache, include_bars=True, use_intraday=False):
    results = []
    for h in holdings:
        entry = dict(h)
        if h["ticker"] is None:
            entry.update({"currentValue": h["purchaseValue"], "pricePLN": 1.0,
                          "priceOriginal": 1.0, "priceOriginalCurrency": "PLN",
                          "dailyChangePct": 0.0, "ytdChangePct": 0.0,
                          "profit": 0.0, "returnPct": 0.0, "dailyChangePLN": 0.0, "pct": 0})
            results.append(entry)
            continue
        try:
            if h["ticker"] not in price_cache:
                try:
                    price, daily_pct, intraday_pct, ytd_pct, today_bars, year_bars = fetch_ticker_data(
                        h["ticker"],
                        include_bars=include_bars,
                    )
                    if price and price > 0:
                        price_cache[h["ticker"]] = (price, daily_pct, intraday_pct, ytd_pct, today_bars, year_bars)
                        s3_cache[h["ticker"]] = [price, daily_pct, ytd_pct, [], []]  # don't cache bar data in S3
                        print(f"  {h['name']:40} {price:.2f} {h['currency']}  {daily_pct:+.2f}% daily  {intraday_pct:+.2f}% intraday")
                    else:
                        raise ValueError("zero/null price")
                except Exception as fetch_err:
                    if h["ticker"] in s3_cache:
                        cached = s3_cache[h["ticker"]]
                        # Use daily_pct as intraday fallback when coming from S3 cache
                        price_cache[h["ticker"]] = (cached[0], cached[1], cached[1], cached[2], [], [])
                        print(f"  {h['name']}: cached price {cached[0]:.2f} (live fetch failed: {fetch_err})")
                    else:
                        print(f"  {h['name']}: no price available, skipping ({fetch_err})")
                        results.append(entry)
                        continue

            price, daily_pct, intraday_pct, ytd_pct, today_bars, year_bars = price_cache[h["ticker"]]
            if not include_bars:
                today_bars = []
                year_bars = []
            rate, prev_rate = get_pln_rate(h["currency"], rates_cache, s3_cache)
            if rate is None:
                print(f"  {h['name']}: no FX rate, skipping")
                results.append(entry)
                continue

            price_pln = price * rate
            cv = round(h["units"] * price_pln, 2)
            profit = round(cv - h["purchaseValue"], 2)
            ret_pct = round((profit / h["purchaseValue"]) * 100, 2) if h["purchaseValue"] else 0
            # Gauge / commentary use intraday (open→current); P/L cards use daily (prev-close→current)
            gauge_pct = intraday_pct if use_intraday else daily_pct
            # Daily PLN change accounts for both stock price AND FX rate movements.
            # Previous value = units × prev_stock_price × prev_fx_rate
            prev_price = price / (1 + gauge_pct / 100) if gauge_pct != 0 else price
            prev_cv = round(h["units"] * prev_price * prev_rate, 2)
            daily_pln = round(cv - prev_cv, 2)

            entry.update({"currentValue": cv, "profit": profit, "returnPct": ret_pct,
                          "pricePLN": round(price_pln, 2), "priceOriginal": round(price, 2),
                          "priceOriginalCurrency": h["currency"],
                          "dailyChangePct": gauge_pct, "ytdChangePct": ytd_pct,
                          "dailyChangePLN": daily_pln, "pct": 0,
                          "todayBars": today_bars, "yearBars": year_bars})
            results.append(entry)
        except Exception as e:
            print(f"ERROR {h['name']}: {e}")
            results.append(entry)

    total = sum(r.get("currentValue", 0) for r in results)
    
    # Calculate total daily change by summing up individual holding daily changes.
    # This ensures perfect consistency with the "Today's Movers" table.
    total_daily_pln = sum(r.get("dailyChangePLN", 0) for r in results)

    for r in results:
        r["pct"] = round((r.get("currentValue", 0) / total) * 100, 2) if total else 0

    total_daily_pln = round(total_daily_pln, 2)
    total_prev = total - total_daily_pln
    total_daily_pct = round((total_daily_pln / total_prev) * 100, 2) if total_prev else 0.0

    return results, round(total, 2), total_daily_pln, total_daily_pct

# ── Widget endpoint ───────────────────────────────────────────
# Reads only from the S3 price cache written by /prices — no live yfinance
# calls, no WIG fetch. Responds in ~50 ms. Payload ~200 bytes.
# Cache-Control: 15 min so CloudFront/CDN serve it without hitting Lambda.

WIDGET_CACHE_KEY = "widget-cache.json"
WIDGET_TTL_SECS  = 900   # 15 minutes — matches iOS widget minimum refresh

def load_widget_cache():
    """Return the last widget snapshot stored by save_widget_cache()."""
    if not CACHE_BUCKET:
        return None
    try:
        s3  = boto3.client("s3")
        obj = s3.get_object(Bucket=CACHE_BUCKET, Key=WIDGET_CACHE_KEY)
        return json.loads(obj["Body"].read())
    except Exception:
        return None

def save_widget_cache(payload):
    """Persist the widget snapshot to S3 after a successful /prices run."""
    if not CACHE_BUCKET:
        return
    try:
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=CACHE_BUCKET,
            Key=WIDGET_CACHE_KEY,
            Body=json.dumps(payload),
            ContentType="application/json",
        )
        print("Widget cache saved.")
    except Exception as e:
        print(f"Widget cache save failed: {e}")

def build_widget_payload(s3_cache, wallets_data, wig_daily_pct):
    """
    Build the minimal widget JSON from a freshly computed wallets_data dict.
    Called after a successful /prices run so the payload is always current.
    """
    emerytura = wallets_data.get("Emerytura", {})
    holdings  = emerytura.get("holdings", [])

    # Find top gainer and top loser among holdings with a live price
    priced = [h for h in holdings if h.get("dailyChangePct") is not None
              and h.get("currentValue", 0) > 0]

    top = max(priced, key=lambda h: h["dailyChangePct"], default=None)
    bot = min(priced, key=lambda h: h["dailyChangePct"], default=None)

    def short_name(full):
        # Strip parenthetical ticker suffix: "XTB" → "XTB", "CDPROJEKT (CDR)" → "CDPROJEKT"
        return full.split("(")[0].strip()

    payload = {
        "ts":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": emerytura.get("total", 0),
        "daily": {
            "pln": emerytura.get("dailyPLN", 0),
            "pct": emerytura.get("dailyPct", 0),
        },
        "wig":   {"pct": wig_daily_pct},
        "top":   {"name": short_name(top["name"]), "pct": top["dailyChangePct"]} if top else None,
        "bot":   {"name": short_name(bot["name"]), "pct": bot["dailyChangePct"]} if bot else None,
    }
    return payload

def widget_handler(event):
    """Handle GET /widget — returns ultra-lightweight portfolio snapshot."""
    if event.get("httpMethod") == "OPTIONS":
        return _resp(200, {})

    # 1. Try serving from the in-S3 widget cache (written by the last /prices run)
    cached = load_widget_cache()
    if cached:
        # Attach staleness flag so the widget can show "stale" indicator
        ts = cached.get("ts", "")
        try:
            age_s = int((datetime.now(timezone.utc) -
                         datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
                         .replace(tzinfo=timezone.utc)).total_seconds())
        except Exception:
            age_s = 0
        cached["stale"] = age_s > WIDGET_TTL_SECS * 2
        print(f"Widget: serving cached snapshot ({age_s}s old)")
        return _resp(200, cached, cache_seconds=WIDGET_TTL_SECS)

    # 2. No widget cache yet — fall back to computing from the price cache
    #    (lightweight: no yfinance, just CSV + S3 cache math)
    print("Widget: no widget cache, computing from price cache")
    try:
        s3_cache    = load_s3_cache()
        price_cache = {}
        rates_cache = {}
        wallets_data = {}
        for wallet_name, csv_path in WALLETS.items():
            holdings = parse_wallet_csv(csv_path)
            results, total, daily_pln, daily_pct = compute_wallet(
                None, wallet_name,
                holdings, price_cache, rates_cache, s3_cache
            )
            wallets_data[wallet_name] = {
                "holdings": results,
                "total":    total,
                "dailyPLN": daily_pln,
                "dailyPct": daily_pct,
            }
        payload = build_widget_payload(s3_cache, wallets_data, None)
        payload["stale"] = True
        return _resp(200, payload, cache_seconds=WIDGET_TTL_SECS)
    except Exception as e:
        print(f"Widget fallback error: {e}")
        return _resp(503, {"error": "widget data unavailable"})


# ── JWT / Cognito helpers ─────────────────────────────────────

def _decode_jwt_payload(token: str) -> dict:
    """Decode the JWT payload without verifying the signature.
    Signature is already verified by API Gateway's Cognito authorizer
    (or we trust the Authorization header from the frontend).
    For production, add a Cognito authorizer to API Gateway."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        # Base64url → bytes → JSON
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = base64.urlsafe_b64decode(padded)
        return json.loads(payload)
    except Exception as e:
        print(f"JWT decode error: {e}")
        return {}


def _get_caller_identity(event: dict) -> tuple[str, str, str]:
    """
    Extract (user_id, email, nickname) from the Authorization header.
    user_id  = Cognito 'sub' claim
    email    = 'email' claim
    nickname = 'nickname' claim (or empty string)
    Returns ("", "", "") if the token is missing or malformed.
    """
    auth_header = (event.get("headers") or {}).get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return "", "", ""
    token = auth_header[7:]
    payload = _decode_jwt_payload(token)
    user_id  = payload.get("sub", "")
    email    = payload.get("email", "")
    nickname = payload.get("nickname", payload.get("cognito:username", ""))
    return user_id, email, nickname


# ── Profile route handlers ────────────────────────────────────

ALLOWED_SETTINGS_KEYS = {"theme", "currency", "defaultWallet", "notifications", "benchmark", "roastIntensity"}


def benchmark_returns_handler(event: dict) -> dict:
    """GET /benchmark-returns — return stored monthly returns for a benchmark."""
    if event.get("httpMethod") == "OPTIONS":
        return _resp(200, {})
    user_id, err = _require_role(event, db.ROLE_BASIC)
    if err:
        return err

    import benchmark_returns as br

    bid    = (_query_value(event, "benchmarkId") or db.DEFAULT_BENCHMARK).upper()
    from_m = _query_value(event, "from", "2020-01")
    if bid not in db.BENCHMARKS:
        bid = db.DEFAULT_BENCHMARK

    items = br.list_monthly_returns(bid, from_ym=from_m)
    out = [
        {
            "month":      i.get("month"),
            "returnPct":  float(i.get("returnPct", 0)),
            "openPrice":  float(i.get("openPrice", 0)),
            "closePrice": float(i.get("closePrice", 0)),
        }
        for i in items
    ]
    return _resp(200, {"benchmarkId": bid, "returns": out})


def benchmarks_handler(event: dict) -> dict:
    """GET /benchmarks — return the full benchmark registry."""
    if event.get("httpMethod") == "OPTIONS":
        return _resp(200, {})
    user_id, err = _require_role(event, db.ROLE_BASIC)
    if err:
        return err
    return _resp(200, {
        "benchmarks": list(db.BENCHMARKS.values()),
        "default":    db.DEFAULT_BENCHMARK,
    })


def profile_handler(event: dict) -> dict:
    """Handle GET / PUT / DELETE /profile"""
    method = event.get("httpMethod", "GET")

    if method == "OPTIONS":
        return _resp(200, {})

    user_id, email, nickname = _get_caller_identity(event)
    if not user_id:
        return _resp(401, {"error": "Missing or invalid Authorization header"})

    # ── GET /profile ─────────────────────────────────────────
    if method == "GET":
        profile = db.get_or_create_user(user_id, email, nickname)
        return _resp(200, profile)

    # ── PUT /profile ─────────────────────────────────────────
    if method == "PUT":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _resp(400, {"error": "Invalid JSON body"})

        updates = {}

        if "nickname" in body:
            nick = str(body["nickname"]).strip()[:40]
            if nick:
                updates["nickname"] = nick

        if "settings" in body and isinstance(body["settings"], dict):
            # Merge with existing — only accept known keys
            current = db.get_user(user_id) or {}
            merged  = dict(current.get("settings") or db._default_settings())
            for k, v in body["settings"].items():
                if k in ALLOWED_SETTINGS_KEYS:
                    if k == "roastIntensity" and v not in ("gentle", "sarcastic", "brutal", "degen"):
                        continue
                    merged[k] = v
            updates["settings"] = merged

        if "portfolioMeta" in body and isinstance(body["portfolioMeta"], dict):
            updates["portfolioMeta"] = body["portfolioMeta"]

        if not updates:
            return _resp(400, {"error": "No valid fields to update"})

        try:
            updated = db.update_user(user_id, updates)
            return _resp(200, updated)
        except ValueError as e:
            return _resp(400, {"error": str(e)})
        except Exception as e:
            print(f"Profile update error: {e}")
            return _resp(500, {"error": "Failed to update profile"})

    # ── DELETE /profile ───────────────────────────────────────
    if method == "DELETE":
        deleted = db.delete_user(user_id)
        if deleted:
            return _resp(200, {"message": "Profile deleted"})
        return _resp(404, {"error": "Profile not found"})

    return _resp(405, {"error": f"Method {method} not allowed"})


# ── TFI fund lookup handler ──────────────────────────────────

def tfi_lookup_handler(event: dict) -> dict:
    """
    GET /tfi/lookup?code=PCS21
    Scrapes bankier.pl for the fund name and last close NAV.
    Returns: { code, name, nav, navDate }
    """
    method = event.get("httpMethod", "GET")
    if method == "OPTIONS":
        return _resp(200, {})
    if method != "GET":
        return _resp(405, {"error": "Method not allowed"})

    user_id, err = _require_role(event, db.ROLE_BASIC)
    if err:
        return err

    code = ((event.get("queryStringParameters") or {}).get("code", "")).strip().upper()
    if not code or len(code) > 20 or not re.match(r'^[A-Z0-9]+$', code):
        return _resp(400, {"error": "Invalid fund code — use the bankier.pl code, e.g. PCS21"})

    url = f"https://www.bankier.pl/fundusze/notowania/{code}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; investment-history-bot/1.0)",
        "Accept-Language": "pl-PL,pl;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="replace")
    except urllib.request.HTTPError as e:
        if e.code == 404:
            return _resp(404, {"error": f"Fund code '{code}' not found on bankier.pl"})
        return _resp(502, {"error": f"bankier.pl error: {e.code}"})
    except Exception as e:
        return _resp(502, {"error": f"Failed to fetch bankier.pl: {e}"})

    # Fund name from <h1>
    name_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    name = re.sub(r'<[^>]+>', '', name_m.group(1)).strip() if name_m else code

    # Last close NAV: <span class="a-quote-item -value">179,16\xa0PLN</span>
    price_m = re.search(
        r'a-quote-item\s+-value">([\d\s]+[,\.]\d{2})\s*(?:\xa0)?PLN', html
    )
    if not price_m:
        return _resp(404, {"error": f"Could not parse NAV for '{code}' — the page structure may have changed"})

    nav = float(
        price_m.group(1).replace("\xa0", "").replace(" ", "").replace(",", ".")
    )

    # Date near the price block
    pos = html.find("a-quote-item")
    date_m = re.search(r'(\d{2}\.\d{2}\.\d{4})', html[max(0, pos - 500):pos + 500])
    nav_date = date_m.group(1) if date_m else None

    return _resp(200, {"code": code, "name": name, "nav": nav, "navDate": nav_date})


# ── Ticker search handler ─────────────────────────────────────

def search_handler(event: dict) -> dict:
    """
    GET /search?q=<query>
    Returns up to 10 Yahoo Finance results for the query.
    Response: { results: [{symbol, name, exchange, type}] }
    """
    method = event.get("httpMethod", "GET")
    if method == "OPTIONS":
        return _resp(200, {})
    if method != "GET":
        return _resp(405, {"error": "Method not allowed"})

    # BASIC role sufficient — all authenticated users can manage their portfolios
    user_id, err = _require_role(event, db.ROLE_BASIC)
    if err:
        return err

    q = (event.get("queryStringParameters") or {}).get("q", "").strip()
    
    # Fetch historical holdings from user's transactions
    historical_holdings = {}
    try:
        user_ports = portfolios.list_portfolios(user_id)
        current_tickers = set()
        
        for p in user_ports:
            pid = p["portfolioId"]
            current_holdings = portfolios.list_holdings(user_id, pid)
            for h in current_holdings:
                ticker = h.get("ticker")
                if ticker:
                    current_tickers.add(ticker)
                    
        for p in user_ports:
            pid = p["portfolioId"]
            txs = portfolios.list_all_transactions(user_id, pid)
            for tx in txs:
                ticker = tx.get("ticker")
                if ticker and ticker not in historical_holdings:
                    is_current = ticker in current_tickers
                    historical_holdings[ticker] = {
                        "symbol": ticker,
                        "name": tx.get("name") or ticker,
                        "exchange": "In Portfolio",
                        "type": "Historical",
                        "isOwned": True,
                        "isCurrent": is_current
                    }
    except Exception as e:
        print(f"Error fetching historical holdings for search: {e}")

    if len(q) < 1:
        # Return all historical holdings if query is empty, current first
        owned_list = sorted(list(historical_holdings.values()), key=lambda x: (not x.get("isCurrent", False), x["symbol"]))
        return _resp(200, {"results": owned_list})

    if len(q) > 50:
        return _resp(400, {"error": "Query too long"})

    q_lower = q.lower()
    matched_owned = [
        h for h in historical_holdings.values()
        if q_lower in h["symbol"].lower() or q_lower in h["name"].lower()
    ]
    matched_owned.sort(key=lambda x: (not x.get("isCurrent", False), x["symbol"]))
    matched_symbols = {h["symbol"] for h in matched_owned}

    try:
        search = yf.Search(q, max_results=10)
        yf_results = []
        for quote in (search.quotes or []):
            symbol = quote.get("symbol", "")
            if not symbol or symbol in matched_symbols:
                continue
            yf_results.append({
                "symbol":   symbol,
                "name":     quote.get("longname") or quote.get("shortname") or symbol,
                "exchange": quote.get("exchDisp") or quote.get("exchange", ""),
                "type":     quote.get("typeDisp") or quote.get("quoteType", ""),
            })
            
        results = matched_owned + yf_results

        # ── Boost Polish exchange (.WA suffix) to the top ─────────
        # If the same company name appears on both WSE and another exchange,
        # the .WA variant should be ranked first for Polish users.
        def _sort_key(r):
            symbol = r.get("symbol", "")
            exchange = r.get("exchange", "").upper()
            is_polish = symbol.endswith(".WA") or "WARSAW" in exchange or "WSE" in exchange or "GPW" in exchange
            return (0 if is_polish else 1)

        results.sort(key=_sort_key)

        return _resp(200, {"results": results})
    except Exception as e:
        print(f"Search error for '{q}': {e}")
        return _resp(500, {"error": "Search failed"})

def benchmark_daily_handler(event: dict) -> dict:
    """
    GET /benchmark-daily?benchmarkId=SP500
    GET /benchmark-daily?ticker=AAPL

    Returns up to 10 years of daily close prices for a benchmark index or
    any yfinance-compatible ticker. Used by the frontend "Return vs Benchmark"
    chart which computes % returns client-side.

    Response: { id, name, daily: [{t: "YYYY-MM-DD", c: float}] }

    Caching: results are stored in S3 under benchmark-daily-max-{id}.json.
    Cache is refreshed if older than 7 days or missing.
    """
    method = event.get("httpMethod", "GET")
    if method == "OPTIONS":
        return _resp(200, {})
    if method != "GET":
        return _resp(405, {"error": "Method not allowed"})

    user_id, err = _require_role(event, db.ROLE_BASIC)
    if err:
        return err

    qs = event.get("queryStringParameters") or {}
    benchmark_id = (qs.get("benchmarkId") or "").strip().upper()
    raw_ticker   = (qs.get("ticker") or "").strip().upper()

    # Resolve benchmark id → ticker and display name
    if benchmark_id and benchmark_id in db.BENCHMARKS:
        meta   = db.BENCHMARKS[benchmark_id]
        ticker = meta["ticker"]
        name   = meta["name"]
        cache_id = benchmark_id
    elif raw_ticker:
        # Custom ticker (e.g. AAPL, CDR.WA)
        # Validate: alphanumeric + dot + hyphen, max 20 chars
        import re as _re
        if not _re.match(r'^[A-Z0-9.\-]{1,20}$', raw_ticker):
            return _resp(400, {"error": "Invalid ticker symbol"})
        ticker   = raw_ticker
        name     = raw_ticker
        cache_id = "CUSTOM_" + raw_ticker.replace(".", "_").replace("-", "_")
    else:
        return _resp(400, {"error": "Provide benchmarkId or ticker parameter"})

    s3_key = f"benchmark-daily-max-{cache_id}.json"

    # Try loading from S3 cache
    cached = {}
    if CACHE_BUCKET:
        try:
            s3  = boto3.client("s3")
            obj = s3.get_object(Bucket=CACHE_BUCKET, Key=s3_key)
            cached = json.loads(obj["Body"].read())
        except Exception:
            cached = {}

    # Check freshness (7-day TTL)
    import datetime as _dt
    updated_str = cached.get("updated", "")
    is_fresh = False
    if updated_str:
        try:
            updated_dt = _dt.datetime.strptime(updated_str, "%Y-%m-%d")
            is_fresh = (_dt.date.today() - updated_dt.date()).days < 7
        except Exception:
            pass

    if is_fresh and cached.get("daily"):
        return _resp(200, {
            "id":    cache_id,
            "name":  cached.get("name", name),
            "daily": cached["daily"],
        }, cache_seconds=3600)

    # Fetch full history via yfinance
    try:
        import yfinance as yf
        import pandas as pd
        tk  = yf.Ticker(ticker)
        df  = tk.history(period="max", interval="1d")
        if df is None or df.empty:
            # Fall back to existing cache even if stale
            if cached.get("daily"):
                return _resp(200, {"id": cache_id, "name": name, "daily": cached["daily"]}, cache_seconds=3600)
            return _resp(404, {"error": f"No data found for {ticker}"})

        # Normalise timezone, keep only Close, drop NaN
        try:
            df.index = df.index.tz_convert("UTC")
        except Exception:
            pass
        df = df.dropna(subset=["Close"])

        daily = [
            {"t": idx.strftime("%Y-%m-%d"), "c": round(float(r["Close"]), 4)}
            for idx, r in df.iterrows()
        ]

        # Persist to S3
        payload = {
            "id":      cache_id,
            "name":    name,
            "ticker":  ticker,
            "daily":   daily,
            "updated": _dt.date.today().isoformat(),
        }
        if CACHE_BUCKET:
            try:
                s3 = boto3.client("s3")
                s3.put_object(
                    Bucket=CACHE_BUCKET,
                    Key=s3_key,
                    Body=json.dumps(payload),
                    ContentType="application/json",
                )
                print(f"benchmark-daily-max: saved {cache_id} ({len(daily)} rows)")
            except Exception as se:
                print(f"benchmark-daily-max cache save failed: {se}")

        return _resp(200, {"id": cache_id, "name": name, "daily": daily}, cache_seconds=3600)

    except Exception as e:
        print(f"benchmark_daily_handler error for {ticker}: {e}")
        # Return cached data even if stale rather than fail completely
        if cached.get("daily"):
            return _resp(200, {"id": cache_id, "name": name, "daily": cached["daily"]}, cache_seconds=300)
        return _resp(500, {"error": f"Failed to fetch data for {ticker}"})


def asset_analysis_handler(event: dict) -> dict:

    """
    GET /asset-analysis?ticker=<ticker>
    Returns 1-year history and basic fundamental properties for the given ticker.
    """
    method = event.get("httpMethod", "GET")
    if method == "OPTIONS":
        return _resp(200, {})
    if method != "GET":
        return _resp(405, {"error": "Method not allowed"})

    # BASIC role sufficient
    user_id, err = _require_role(event, db.ROLE_BASIC)
    if err:
        return err

    ticker_symbol = (event.get("queryStringParameters") or {}).get("ticker", "").strip()
    period_req = (event.get("queryStringParameters") or {}).get("period", "1y").strip()
    
    if not ticker_symbol:
        return _resp(400, {"error": "Missing ticker parameter"})

    yf_period_map = {
        "1d": "1d", "1w": "5d", "1m": "1mo", 
        "ytd": "ytd", "1y": "1y", "5y": "5y", "all": "max"
    }
    yf_interval_map = {
        "1d": "5m", "1w": "1h", "1m": "1d", 
        "ytd": "1d", "1y": "1d", "5y": "1wk", "all": "1mo"
    }
    
    p = yf_period_map.get(period_req, "1y")
    i = yf_interval_map.get(period_req, "1d")

    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        fundamentals = {
            "longName": info.get("longName", ticker_symbol),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "marketCap": info.get("marketCap"),
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "dividendYield": info.get("dividendYield"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
        }
        
        hist = ticker.history(period=p, interval=i)
        history_data = []
        for date, row in hist.iterrows():
            close = row["Close"]
            if isinstance(close, float) and (math.isnan(close) or math.isinf(close)):
                continue
            volume = row.get("Volume") if hasattr(row, "get") else row["Volume"] if "Volume" in row.index else None
            vol_val = None
            if volume is not None:
                try:
                    v = float(volume)
                    vol_val = None if (math.isnan(v) or math.isinf(v)) else int(v)
                except (TypeError, ValueError):
                    pass
            history_data.append({
                "t": date.strftime("%Y-%m-%dT%H:%M:%SZ") if i in ["5m", "1h"] else date.strftime("%Y-%m-%d"),
                "c": float(close),
                "v": vol_val
            })

        # Fetch cashflow data (annual and quarterly)
        cashflow_data = {}
        try:
            cf_annual = ticker.cashflow
            cf_quarterly = ticker.quarterly_cashflow
            
            # Get last 5 years of annual cashflow
            if not cf_annual.empty:
                cf_annual_list = []
                for col in cf_annual.columns[:5]:  # Last 5 years
                    year_data = {"date": col.strftime("%Y") if hasattr(col, 'strftime') else str(col)}
                    for idx in cf_annual.index:
                        val = cf_annual.loc[idx, col]
                        if not (hasattr(val, '__iter__') and len(val) == 0):  # Skip empty values
                            year_data[idx.replace(" ", "")] = float(val) if val == val else None  # NaN check
                    cf_annual_list.append(year_data)
                cashflow_data["annual"] = cf_annual_list
            
            # Get last 8 quarters of quarterly cashflow
            if not cf_quarterly.empty:
                cf_quarterly_list = []
                for col in cf_quarterly.columns[:8]:  # Last 8 quarters
                    quarter_data = {"date": col.strftime("%Y-%m-%d") if hasattr(col, 'strftime') else str(col)}
                    for idx in cf_quarterly.index:
                        val = cf_quarterly.loc[idx, col]
                        if not (hasattr(val, '__iter__') and len(val) == 0):
                            quarter_data[idx.replace(" ", "")] = float(val) if val == val else None
                    cf_quarterly_list.append(quarter_data)
                cashflow_data["quarterly"] = cf_quarterly_list
        except Exception as cf_err:
            print(f"Cashflow fetch error for {ticker_symbol}: {cf_err}")
            cashflow_data = {}

        # Fetch earnings and financials data
        financials_data = {}
        try:
            fin_annual = ticker.financials
            fin_quarterly = ticker.quarterly_financials
            
            # Get last 5 years of annual financials
            if not fin_annual.empty:
                fin_annual_list = []
                for col in fin_annual.columns[:5]:
                    year_data = {"date": col.strftime("%Y") if hasattr(col, 'strftime') else str(col)}
                    for idx in fin_annual.index:
                        val = fin_annual.loc[idx, col]
                        if not (hasattr(val, '__iter__') and len(val) == 0):
                            year_data[idx.replace(" ", "")] = float(val) if val == val else None
                    fin_annual_list.append(year_data)
                financials_data["annual"] = fin_annual_list
            
            # Get last 8 quarters
            if not fin_quarterly.empty:
                fin_quarterly_list = []
                for col in fin_quarterly.columns[:8]:
                    quarter_data = {"date": col.strftime("%Y-%m-%d") if hasattr(col, 'strftime') else str(col)}
                    for idx in fin_quarterly.index:
                        val = fin_quarterly.loc[idx, col]
                        if not (hasattr(val, '__iter__') and len(val) == 0):
                            quarter_data[idx.replace(" ", "")] = float(val) if val == val else None
                    fin_quarterly_list.append(quarter_data)
                financials_data["quarterly"] = fin_quarterly_list
        except Exception as fin_err:
            print(f"Financials fetch error for {ticker_symbol}: {fin_err}")
            financials_data = {}

        # Fetch earnings data (simplified)
        earnings_data = {}
        try:
            earnings_hist = ticker.earnings_history
            if earnings_hist is not None and not earnings_hist.empty:
                earnings_list = []
                for idx, row in earnings_hist.iterrows():
                    earnings_list.append({
                        "quarter": row.get("quarter", ""),
                        "date": row.get("epsActual", ""),
                        "epsEstimate": float(row.get("epsEstimate")) if row.get("epsEstimate") == row.get("epsEstimate") else None,
                        "epsActual": float(row.get("epsActual")) if row.get("epsActual") == row.get("epsActual") else None,
                        "surprise": float(row.get("surprise")) if row.get("surprise") == row.get("surprise") else None,
                    })
                earnings_data = earnings_list[:20]  # Last 20 quarters (5 years)
        except Exception as earn_err:
            print(f"Earnings fetch error for {ticker_symbol}: {earn_err}")
            earnings_data = []

        # Fetch matching transactions
        user_txs = []
        user_ports = portfolios.list_portfolios(user_id)
        for p_info in user_ports:
            pid = p_info.get("portfolioId")
            txs = portfolios.list_all_transactions(user_id, pid)
            for tx in txs:
                if tx.get("ticker") == ticker_symbol and tx.get("type") in ["BUY", "SELL"]:
                    user_txs.append({
                        "date": tx.get("transactionDate", ""),
                        "type": tx.get("type"),
                        "units": float(tx.get("quantity") or 0),
                        "price": float(tx.get("price") or 0),
                        "portfolioId": pid
                    })

        # Sort transactions chronologically
        user_txs.sort(key=lambda x: x["date"])

        return _resp(200, {
            "ticker": ticker_symbol,
            "fundamentals": fundamentals,
            "history": history_data,
            "transactions": user_txs,
            "cashflow": cashflow_data,
            "financials": financials_data,
            "earnings": earnings_data
        })
    except Exception as e:
        print(f"Asset analysis error for '{ticker_symbol}': {e}")
        return _resp(500, {"error": "Failed to fetch asset analysis data"})


# ── Favorites route handler ──────────────────────────────────────────────────

def favorites_handler(event: dict) -> dict:
    """
    GET  /favorites  → get user's favorite tickers
    PUT  /favorites  → update user's favorite tickers
    
    Request body for PUT:
    {
      "favorites": [
        {"ticker": "AAPL", "name": "Apple Inc.", "addedAt": "2026-06-16T10:00:00Z"},
        {"ticker": "CDR.WA", "name": "CD Projekt", "addedAt": "2026-06-16T11:00:00Z"}
      ]
    }
    """
    method = event.get("httpMethod", "GET")
    
    if method == "OPTIONS":
        return _resp(200, {})
    
    # Require authentication
    user_id, err = _require_role(event, db.ROLE_BASIC)
    if err:
        return err
    
    if method == "GET":
        try:
            favorites = db.get_favorites(user_id)
            return _resp(200, {"favorites": favorites})
        except Exception as e:
            print(f"Failed to get favorites for user {user_id}: {e}")
            return _resp(500, {"error": "Failed to fetch favorites"})
    
    elif method == "PUT":
        try:
            body = json.loads(event.get("body", "{}"))
            favorites = body.get("favorites", [])
            
            # Validate structure
            if not isinstance(favorites, list):
                return _resp(400, {"error": "favorites must be an array"})
            
            for fav in favorites:
                if not isinstance(fav, dict) or "ticker" not in fav or "name" not in fav:
                    return _resp(400, {"error": "Each favorite must have ticker and name"})
            
            db.set_favorites(user_id, favorites)
            return _resp(200, {"favorites": favorites, "message": "Favorites updated"})
        except json.JSONDecodeError:
            return _resp(400, {"error": "Invalid JSON"})
        except Exception as e:
            print(f"Failed to save favorites for user {user_id}: {e}")
            return _resp(500, {"error": "Failed to save favorites"})
    
    else:
        return _resp(405, {"error": "Method not allowed"})



# ── Portfolios route handler ──────────────────────────────────

def portfolios_handler(event: dict) -> dict:
    """
    Routes:
      GET    /portfolios                          → list portfolios
      PUT    /portfolios                          → create/update portfolio
      GET    /portfolios/{id}                     → get portfolio + holdings
      DELETE /portfolios/{id}                     → delete portfolio
      GET    /portfolios/{id}/holdings            → list holdings
      PUT    /portfolios/{id}/holdings            → legacy holding upsert (writes ledger tx)
      DELETE /portfolios/{id}/holdings/{hid}      → delete holding
      GET    /portfolios/{id}/transactions        → list transactions
      POST   /portfolios/{id}/transactions        → create BUY/SELL/DEPOSIT/WITHDRAWAL transaction
    PUT    /portfolios/{id}/transactions/{txid} → update transaction and recalculate history
      GET    /portfolios/{id}/snapshots           → list daily snapshots
      GET    /portfolios/{id}/ath                 → get current ATH state
      PUT    /portfolios/{id}/ath                 → manual ATH override / revert to AUTO
    """
    method  = event.get("httpMethod", "GET")
    path    = event.get("path", "")
    params  = event.get("pathParameters") or {}

    if method == "OPTIONS":
        return _resp(200, {})

    # BASIC role sufficient — all authenticated users can manage their portfolios
    user_id, err = _require_role(event, db.ROLE_BASIC)
    if err:
        return err

    portfolio_id = params.get("portfolioId")
    holding_id   = params.get("holdingId")
    transaction_id = params.get("transactionId")
    if not transaction_id and "/transactions/" in path:
        transaction_id = path.rstrip("/").rsplit("/", 1)[-1]

    # ── /portfolios/{id}/holdings/{hid} ──────────────────────
    if portfolio_id and holding_id:
        if method == "DELETE":
            ok = portfolios.delete_holding(user_id, portfolio_id, holding_id)
            return _resp(200, {"deleted": ok}) if ok else _resp(404, {"error": "Holding not found"})
        return _resp(405, {"error": f"Method {method} not allowed"})

    # ── /portfolios/{id}/transactions ─────────────────────────
    if portfolio_id and "/transactions" in path:
        if method == "GET":
            raw_limit = (event.get("queryStringParameters") or {}).get("limit")
            try:
                limit = int(raw_limit) if raw_limit is not None else 200
            except (TypeError, ValueError):
                return _resp(400, {"error": "limit must be an integer"})
            if limit <= 0:
                return _resp(400, {"error": "limit must be greater than 0"})
            return _resp(200, {"transactions": portfolios.list_transactions(user_id, portfolio_id, limit=limit)})
        if method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _resp(400, {"error": "Invalid JSON"})
            try:
                tx = portfolios.record_transaction(user_id, portfolio_id, body)
                return _resp(200, tx)
            except ValueError as e:
                return _resp(400, {"error": str(e)})
        if method == "PUT" and transaction_id:
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _resp(400, {"error": "Invalid JSON"})
            try:
                result = portfolios.update_transaction(user_id, portfolio_id, transaction_id, body)
                from_date = result.get("recalculateFrom") or result.get("transaction", {}).get("transactionDate")
                recalculated = snapshots.recalculate_portfolio_snapshots_from_date(user_id, portfolio_id, from_date)
                summary_updated = snapshots.recalculate_summary_snapshots_from_date(user_id, from_date)
                return _resp(200, {**result, "recalculated": recalculated, "summaryUpdated": summary_updated})
            except ValueError as e:
                return _resp(400, {"error": str(e)})
            except Exception as e:
                return _resp(500, {"error": str(e)})
        return _resp(405, {"error": f"Method {method} not allowed"})

    # ── /portfolios/{id}/snapshots/recalculate ────────────────
    if portfolio_id and "/snapshots/recalculate" in path:
        if method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _resp(400, {"error": "Invalid JSON"})
            from_date = str(body.get("fromDate") or "").strip()
            if not from_date or len(from_date) < 10 or from_date[4:5] != "-" or from_date[7:8] != "-":
                return _resp(400, {"error": "fromDate must be YYYY-MM-DD"})
            from_date = from_date[:10]
            try:
                result = snapshots.recalculate_portfolio_snapshots_from_date(user_id, portfolio_id, from_date)
                summary_updated = snapshots.recalculate_summary_snapshots_from_date(user_id, from_date)
                return _resp(200, {**result, "summaryUpdated": summary_updated})
            except Exception as e:
                return _resp(500, {"error": str(e)})
        return _resp(405, {"error": f"Method {method} not allowed"})

    # ── /portfolios/{id}/snapshots ────────────────────────────
    if portfolio_id and "/snapshots" in path:
        if method == "GET":
            try:
                snaps = snapshots.list_snapshots(user_id, portfolio_id)
                return _resp(200, {"snapshots": snaps})
            except Exception as e:
                import traceback
                err_trace = traceback.format_exc()
                print("SNAPSHOTS ERROR:", err_trace)
                return _resp(500, {"error": str(e), "trace": err_trace})
        return _resp(405, {"error": f"Method {method} not allowed"})

    # ── /portfolios/{id}/ath ──────────────────────────────────
    if portfolio_id and "/ath" in path:
        if method == "GET":
            return _resp(200, {"ath": snapshots.get_portfolio_ath(user_id, portfolio_id)})
        if method == "PUT":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _resp(400, {"error": "Invalid JSON"})
            try:
                source = str(body.get("athSource") or body.get("source") or "MANUAL").strip().upper()
                if source == "AUTO":
                    ath = snapshots.recalculate_ath(user_id, portfolio_id)
                else:
                    ath = snapshots.set_manual_ath(
                        user_id,
                        portfolio_id,
                        body.get("athValue"),
                        body.get("athDate"),
                    )
                return _resp(200, {"ath": ath})
            except ValueError as e:
                return _resp(400, {"error": str(e)})
        return _resp(405, {"error": f"Method {method} not allowed"})

    # ── /portfolios/{id}/holdings ─────────────────────────────
    if portfolio_id and "/holdings" in path:
        if method == "GET":
            return _resp(200, {"holdings": portfolios.list_holdings(user_id, portfolio_id)})
        if method == "PUT":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _resp(400, {"error": "Invalid JSON"})
            try:
                h = portfolios.put_holding(user_id, portfolio_id, body)
                return _resp(200, h)
            except ValueError as e:
                return _resp(400, {"error": str(e)})
        return _resp(405, {"error": f"Method {method} not allowed"})

    # ── /portfolios/{id} ──────────────────────────────────────
    if portfolio_id:
        if method == "GET":
            p = portfolios.get_portfolio(user_id, portfolio_id)
            if not p:
                return _resp(404, {"error": "Portfolio not found"})
            p["holdings"] = portfolios.list_holdings(user_id, portfolio_id)
            p["transactions"] = portfolios.list_transactions(user_id, portfolio_id)
            return _resp(200, p)
        if method == "DELETE":
            ok = portfolios.delete_portfolio(user_id, portfolio_id)
            return _resp(200, {"deleted": ok}) if ok else _resp(404, {"error": "Portfolio not found"})
        return _resp(405, {"error": f"Method {method} not allowed"})

    # ── /portfolios ───────────────────────────────────────────
    if method == "GET":
        return _resp(200, {"portfolios": portfolios.list_portfolios(user_id)})
    if method == "PUT":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _resp(400, {"error": "Invalid JSON"})
        try:
            p = portfolios.put_portfolio(user_id, body)
            return _resp(200, p)
        except ValueError as e:
            return _resp(400, {"error": str(e)})

    return _resp(405, {"error": f"Method {method} not allowed"})


def retirement_plans_handler(event: dict) -> dict:
    """Handle CRUD + simulation for /retirement-plans."""
    method = event.get("httpMethod", "GET")
    if method == "OPTIONS":
        return _resp(200, {})

    user_id, err = _require_role(event, db.ROLE_ADVANCED)
    if err:
        return err

    path = event.get("path", "/retirement-plans")
    path_params = event.get("pathParameters") or {}
    plan_id = path_params.get("planId")
    action = path_params.get("action")

    if not plan_id:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2:
            plan_id = parts[1]
        if len(parts) >= 3:
            action = parts[2]

    if plan_id and action == "simulate":
        if method != "POST":
            return _resp(405, {"error": f"Method {method} not allowed"})
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _resp(400, {"error": "Invalid JSON"})
        try:
            return _resp(200, retirement_plans.simulate_saved_plan(user_id, plan_id, body))
        except ValueError as e:
            return _resp(404, {"error": str(e)})

    if plan_id:
        if method == "GET":
            plan = retirement_plans.get_plan(user_id, plan_id)
            return _resp(200, plan) if plan else _resp(404, {"error": "Plan not found"})
        if method == "DELETE":
            deleted = retirement_plans.delete_plan(user_id, plan_id)
            return _resp(200, {"deleted": deleted}) if deleted else _resp(404, {"error": "Plan not found"})
        return _resp(405, {"error": f"Method {method} not allowed"})

    if method == "GET":
        return _resp(200, {"plans": retirement_plans.list_plans(user_id)})

    if method == "PUT":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _resp(400, {"error": "Invalid JSON"})
        try:
            return _resp(200, retirement_plans.save_plan(user_id, body))
        except ValueError as e:
            return _resp(400, {"error": str(e)})

    return _resp(405, {"error": f"Method {method} not allowed"})


# ── Prices: load holdings from DynamoDB or fall back to CSV ──

def _load_wallets_from_dynamo(user_id: str) -> dict[str, list[dict]] | None:
    """
    Returns {walletName: [holding, ...]} from DynamoDB, or None if the user
    has no portfolios yet (first-time user before migration).

    "Emerytura" is excluded — it was the legacy single-portfolio CSV that held
    all stocks. The primary portfolios (XTB, IKE, IKZE) replace it; their
    aggregate becomes the virtual Summary portfolio.
    """
    EXCLUDED_IDS   = {"emerytura"}
    EXCLUDED_NAMES = {"emerytura"}

    try:
        user_portfolios = portfolios.list_portfolios(user_id)
        if not user_portfolios:
            return None

        result = {}
        for p in user_portfolios:
            pid  = p["portfolioId"]
            name = p["name"]
            # Skip the legacy Emerytura portfolio
            if pid.lower() in EXCLUDED_IDS or name.lower() in EXCLUDED_NAMES:
                print(f"Skipping excluded portfolio: {name} ({pid})")
                continue
            items = portfolios.list_holdings(user_id, pid)
            result[name] = [
                {
                    "name":          h["name"],
                    "units":         float(h.get("units", 0)),
                    "purchaseValue": float(h.get("purchaseValue", 0)),
                    "ticker":        h.get("ticker"),
                    "currency":      h.get("currency", "PLN"),
                }
                for h in items
            ]
        return result if result else None
    except Exception as e:
        print(f"DynamoDB holdings load failed, will use CSV fallback: {e}")
        return None


def _load_wallets_from_csv() -> dict[str, list[dict]]:
    """Always-available CSV fallback (bundled in Lambda package)."""
    result = {}
    for wallet_name, csv_path in WALLETS.items():
        try:
            result[wallet_name] = parse_wallet_csv(csv_path)
        except Exception as e:
            print(f"CSV parse error for {wallet_name}: {e}")
            result[wallet_name] = []
    return result


def _build_summary_wallet(wallets_out: dict) -> dict:
    """
    Compute the virtual Summary wallet by aggregating all real portfolios.

    Holdings with the same ticker are consolidated into one row:
      - units, purchaseValue, currentValue, dailyChangePLN  → summed
      - pricePLN, dailyChangePct, ytdChangePct               → taken from the largest-value lot
      - todayBars, yearBars                                  → taken from the largest-value lot
      - name                                                  → first occurrence

    Summary metrics:
      total     = sum of all wallet totals
      dailyPLN  = sum of all wallet dailyPLN
      dailyPct  = totalDailyPLN / (total - totalDailyPLN) * 100
    """
    total_value = sum(w["total"]    for w in wallets_out.values())
    total_daily = sum(w["dailyPLN"] for w in wallets_out.values())
    base        = total_value - total_daily
    daily_pct   = round((total_daily / base) * 100, 4) if base else 0.0

    # Consolidate holdings by ticker (None-ticker items kept separate by name)
    consolidated: dict[str, dict] = {}
    for w in wallets_out.values():
        for h in w.get("holdings", []):
            key = h.get("ticker") or f"__noticker__{h.get('name', '')}"
            if key not in consolidated:
                consolidated[key] = dict(h)
            else:
                existing = consolidated[key]
                # Use the lot with the larger currentValue as the price/bar reference
                if h.get("currentValue", 0) > existing.get("currentValue", 0):
                    existing["pricePLN"]        = h.get("pricePLN",        existing.get("pricePLN"))
                    existing["priceOriginal"]    = h.get("priceOriginal",   existing.get("priceOriginal"))
                    existing["dailyChangePct"]   = h.get("dailyChangePct",  existing.get("dailyChangePct"))
                    existing["ytdChangePct"]     = h.get("ytdChangePct",    existing.get("ytdChangePct"))
                    existing["todayBars"]        = h.get("todayBars",       existing.get("todayBars"))
                    existing["yearBars"]         = h.get("yearBars",        existing.get("yearBars"))
                # Always sum the money fields
                existing["units"]         = round(existing.get("units", 0)         + h.get("units", 0), 6)
                existing["purchaseValue"] = round(existing.get("purchaseValue", 0) + h.get("purchaseValue", 0), 2)
                existing["currentValue"]  = round(existing.get("currentValue", 0)  + h.get("currentValue", 0), 2)
                existing["dailyChangePLN"]= round(existing.get("dailyChangePLN",0) + h.get("dailyChangePLN", 0), 2)
                existing["profit"]        = round(existing["currentValue"] - existing["purchaseValue"], 2)
                pv = existing["purchaseValue"]
                existing["returnPct"]     = round((existing["profit"] / pv) * 100, 2) if pv else 0.0

    all_holdings = list(consolidated.values())

    # Recompute pct (portfolio weight) for consolidated list
    cv_total = sum(h.get("currentValue", 0) for h in all_holdings)
    for h in all_holdings:
        h["pct"] = round((h.get("currentValue", 0) / cv_total) * 100, 2) if cv_total else 0

    return {
        "holdings": all_holdings,
        "total":    round(total_value, 2),
        "dailyPLN": round(total_daily, 2),
        "dailyPct": round(daily_pct,   4),
    }

def roast_events_handler(event: dict) -> dict:
    import json
    import roast_tracking
    user_id, _, _ = _get_caller_identity(event)
    try:
        body = json.loads(event.get("body") or "{}")
        if user_id:
            body["userId"] = user_id
        result = roast_tracking.record_event(body)
        return _resp(200, result)
    except ValueError as e:
        return _resp(400, {"error": str(e)})
    except Exception as e:
        print(f"roast_events_handler error: {e}")
        return _resp(500, {"error": "Internal server error"})
def roast_report_handler(event: dict) -> dict:
    import roast_tracking
    user_id, _, _ = _get_caller_identity(event)
    # Could optionally enforce that only the admin or specific users can view this
    if not user_id:
        return _resp(401, {"error": "Unauthorized"})
    
    try:
        # Default to 30 days
        days = int(event.get("queryStringParameters", {}).get("days", 30)) if event.get("queryStringParameters") else 30
        report = roast_tracking.get_template_report(days=days)
        return _resp(200, report)
    except Exception as e:
        print(f"roast_report_handler error: {e}")
        return _resp(500, {"error": "Internal server error"})



# ── Lambda entry point ────────────────────────────────────────

def handler(event, context):
    path = event.get("path", "/prices")

    try:
        # Route /profile
        if path.endswith("/profile"):
            return profile_handler(event)

        # Route /benchmark-returns (must come before /benchmarks substring check)
        if path.endswith("/benchmark-returns"):
            return benchmark_returns_handler(event)

        # Route /benchmark-daily (must come before /benchmarks substring check)
        if path.endswith("/benchmark-daily"):
            return benchmark_daily_handler(event)

        # Route /benchmarks
        if path.endswith("/benchmarks"):
            return benchmarks_handler(event)


        # Route /tfi/lookup
        if path.endswith("/tfi/lookup"):
            return tfi_lookup_handler(event)

        # Route /search
        if path.endswith("/search"):
            return search_handler(event)

        # Route /asset-analysis
        if path.endswith("/asset-analysis"):
            return asset_analysis_handler(event)

        # Route /favorites
        if path.endswith("/favorites"):
            return favorites_handler(event)

        # Route /portfolios and sub-paths
        if "/portfolios" in path:
            return portfolios_handler(event)

        # Route /retirement-plans and sub-paths
        if "/retirement-plans" in path:
            return retirement_plans_handler(event)

        # Route /roast-events
        if path.endswith("/roast-events"):
            return roast_events_handler(event)

        # Route /roast-report
        if path.endswith("/roast-report"):
            return roast_report_handler(event)

        # Route /migrate
        if path.endswith("/migrate"):
            from migrate import migrate_handler
            return migrate_handler(event)

        # Route /widget to the lightweight handler
        if path.endswith("/widget"):
            return widget_handler(event)

        if event.get("httpMethod") == "OPTIONS":
            return _resp(200, {})

        request_started = perf_counter()
        prices_view = _prices_view(event)

        # ── History view: on-demand benchmark history (range filter clicked) ──
        if prices_view == "history":
            user_id, _, _ = _get_caller_identity(event)
            benchmark_id = db.DEFAULT_BENCHMARK
            if user_id:
                try:
                    profile = db.get_user(user_id)
                    if profile:
                        bid = profile.get("settings", {}).get("benchmark", db.DEFAULT_BENCHMARK)
                        if bid in db.BENCHMARKS:
                            benchmark_id = bid
                except Exception:
                    pass
            bm_meta   = db.BENCHMARKS[benchmark_id]
            bm_ticker = bm_meta["ticker"]
            try:
                bm_cache = load_benchmark_cache(benchmark_id)
                bm_data  = fetch_benchmark_history(benchmark_id, bm_ticker, bm_cache)
                save_benchmark_cache(benchmark_id, bm_data)
            except Exception as he:
                print(f"{benchmark_id} history fetch error: {he}")
                bm_data = load_benchmark_cache(benchmark_id) or {}
            return _resp(200, {
                "responseMode":  "history",
                "benchmarkId":   benchmark_id,
                "benchmarkName": bm_meta["name"],
                "benchmarkData": _serialize_benchmark_history(bm_data),
                "updatedAt":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        include_deferred = prices_view == "full"
        s3_cache    = load_s3_cache()
        price_cache = {}
        rates_cache = {}
        wallets_out = {}
        portfolio_id_by_name = {}

        # ── Determine holdings source ─────────────────────────
        # Authenticated users always get their own DynamoDB portfolios.
        # CSV fallback is only used for unauthenticated requests (widget etc.).
        # An authenticated user with no portfolios gets empty data — never
        # another user's CSV data.
        user_id, _, _ = _get_caller_identity(event)
        if user_id:
            source_wallets = _load_wallets_from_dynamo(user_id) or {}
            data_source = "dynamodb"
            print(f"User {user_id[:8]}… — {len(source_wallets)} portfolios from DynamoDB")
            try:
                for p in portfolios.list_portfolios(user_id):
                    portfolio_id_by_name[p.get("name", p["portfolioId"])] = p["portfolioId"]
            except Exception as pe:
                print(f"Portfolio metadata load failed (non-fatal): {pe}")
        else:
            source_wallets = _load_wallets_from_csv()
            data_source = "csv"
            print("Unauthenticated request — using CSV fallback")

        # ── Parallel price + bars prefetch ────────────────────
        # Collect every holding ticker plus (for full) the benchmark ticker so
        # the benchmark intraday bars are fetched in the same parallel batch.
        # bars_cache is keyed by ticker symbol — works for any benchmark.
        bars_cache = load_bars_cache() if include_deferred else {}
        all_tickers: set = {
            h.get("ticker") or ""
            for holdings in source_wallets.values()
            for h in holdings
        } - {""}
        # For lite we still prefetch all holdings in parallel; benchmark price
        # is resolved separately via fast_info (no bars needed for lite).
        prefetch_started = perf_counter()
        _prefetch_prices_parallel(
            all_tickers, include_deferred, s3_cache, price_cache,
            bars_cache=bars_cache if include_deferred else None,
        )
        print(f"Parallel prefetch: {perf_counter() - prefetch_started:.3f}s")

        holdings_started = perf_counter()
        for wallet_name, holdings in source_wallets.items():
            pid = portfolio_id_by_name.get(wallet_name, wallet_name)
            results, total, daily_pln, daily_pct = compute_wallet(
                user_id, pid,
                holdings, price_cache, rates_cache, s3_cache,
                include_bars=include_deferred,
                # prev-close → current: market-standard "daily change" shown by brokers.
                use_intraday=False,
            )
            wallets_out[wallet_name] = {
                "holdings": results,
                "total":    total,
                "dailyPLN": daily_pln,
                "dailyPct": daily_pct,
            }
        holdings_duration = perf_counter() - holdings_started

        save_s3_cache(s3_cache)

        # Persist updated bars (todayBars + yearBars) so the next full fetch
        # skips expensive history() calls for any ticker, including the benchmark.
        if include_deferred:
            today_str = date.today().isoformat()
            now_ts    = _time.time()
            for ticker, data in price_cache.items():
                if ticker.startswith("FX_"):
                    continue
                if data[4] or data[5]:  # has todayBars or yearBars
                    bars_cache[ticker] = {
                        "todayBars": data[4], "yearBars": data[5],
                        "ytdPct":    data[3], "ts": now_ts, "date": today_str,
                    }
            save_bars_cache(bars_cache)

        # ── Compute virtual Summary portfolio ─────────────────
        summary = _build_summary_wallet(wallets_out)

        # ── Determine benchmark for this user ─────────────────
        benchmark_id = db.DEFAULT_BENCHMARK
        if user_id:
            try:
                profile = db.get_user(user_id)
                if profile:
                    benchmark_id = profile.get("settings", {}).get("benchmark", db.DEFAULT_BENCHMARK)
                    if benchmark_id not in db.BENCHMARKS:
                        benchmark_id = db.DEFAULT_BENCHMARK
            except Exception as be:
                print(f"Benchmark settings fetch failed (non-fatal): {be}")
        bm_meta = db.BENCHMARKS[benchmark_id]

        # ── Fetch benchmark data ──────────────────────────────────
        bm_out = {"daily": [], "weekly": [], "intraday": [], "hourly": [], "updated": ""}
        benchmark_daily_pct = None
        wig_daily_pct       = None
        market_carousel = []
        benchmark_started = perf_counter()
        try:
            bm_ticker = bm_meta["ticker"]
            if prices_view == "lite":
                # Fast path: prev-close → current via fast_info (market-standard daily %).
                # No history fetch needed — fast_info has previous_close and last_price.
                benchmark_daily_pct = _compute_benchmark_daily_pct({}, bm_ticker)
                if benchmark_daily_pct is None:
                    # Fallback: try cached daily bars
                    bm_cache = load_benchmark_cache(benchmark_id)
                    benchmark_daily_pct = _compute_benchmark_daily_pct(bm_cache, bm_ticker)
            elif prices_view == "full":
                # Full: fetch today's intraday bars for the 1D chart.
                # Historical data (daily/weekly/monthly) is loaded on-demand via view=history.
                # benchmarkDailyPct intentionally NOT set — gauge is frozen from lite.
                # bars_cache is keyed by ticker symbol — works for any user-selected benchmark.
                bm_cached = bars_cache.get(bm_ticker, {})
                bm_bars_fresh = _time.time() - bm_cached.get("ts", 0) < 180
                if bm_bars_fresh and bm_cached.get("todayBars"):
                    bm_out["intraday"] = bm_cached["todayBars"]
                    print(f"  {bm_ticker}: intraday bars from cache ({len(bm_out['intraday'])} pts)")
                else:
                    try:
                        intra_df = yf.Ticker(bm_ticker).history(period='1d', interval='1m')
                        bm_out["intraday"] = _to_ts_rows_plain(intra_df) if not intra_df.empty else []
                        # Store in bars_cache so it is persisted alongside portfolio tickers
                        bars_cache[bm_ticker] = {
                            "todayBars": bm_out["intraday"], "yearBars": bm_cached.get("yearBars", []),
                            "ytdPct":    bm_cached.get("ytdPct", 0.0),
                            "ts": _time.time(), "date": date.today().isoformat(),
                        }
                    except Exception as intra_err:
                        print(f"{benchmark_id} intraday bars fetch failed (non-fatal): {intra_err}")
                        # Fall back to benchmark history cache (S3 daily key)
                        bm_cache = load_benchmark_cache(benchmark_id)
                        bm_out["intraday"] = bm_cache.get("intraday", [])
                benchmark_daily_pct = None  # gauge is owned by lite — don't override

                # Carousel still needs benchmark data; build from intraday
                bm_data_for_carousel = {"intraday": bm_out["intraday"]}
                carousel_cache = {benchmark_id: (bm_data_for_carousel, None)}
                for carousel_id in MARKET_CAROUSEL_IDS:
                    if carousel_id not in db.BENCHMARKS:
                        continue
                    entry = None
                    if carousel_id in carousel_cache:
                        cached_data, cached_pct = carousel_cache[carousel_id]
                        entry = _build_market_carousel_entry(
                            carousel_id, cached_data,
                            cached_pct or _compute_benchmark_daily_pct(cached_data),
                        )
                    else:
                        try:
                            carousel_meta = db.BENCHMARKS[carousel_id]
                            carousel_data = fetch_benchmark_history(
                                carousel_id,
                                carousel_meta["ticker"],
                                load_benchmark_cache(carousel_id),
                            )
                            save_benchmark_cache(carousel_id, carousel_data)
                            entry = _build_market_carousel_entry(
                                carousel_id,
                                carousel_data,
                                _compute_benchmark_daily_pct(carousel_data),
                            )
                        except Exception as carousel_err:
                            print(f"{carousel_id} market carousel fetch failed (non-fatal): {carousel_err}")
                    if entry:
                        market_carousel.append(entry)

            if benchmark_daily_pct is not None:
                print(f"{benchmark_id} intraday %: {benchmark_daily_pct:+.2f}%")
            # WIG backward compat
            if benchmark_id == "WIG":
                wig_daily_pct = benchmark_daily_pct
        except Exception as bm_err:
            print(f"{benchmark_id} benchmark section failed (non-fatal): {bm_err}")
        benchmark_duration = perf_counter() - benchmark_started

        # Keep wig_out alias so widget builder and cached response work
        wig_out = bm_out

        # ── Save lightweight widget snapshot (lite only — it has the intraday %) ──
        if prices_view == "lite":
            try:
                widget_payload = build_widget_payload(s3_cache, wallets_out, wig_daily_pct or benchmark_daily_pct)
                save_widget_cache(widget_payload)
            except Exception as we:
                print(f"Widget snapshot save failed (non-fatal): {we}")

        # ── Response ──────────────────────────────────────────
        # PORTFOLIO_* globals refer to the Summary (aggregate of all wallets).
        # walletSummaries contains per-wallet breakdowns for the carousel.
        # Summary is also included in walletSummaries so the frontend can
        # render it first without special-casing.
        # Wallets ordered by total value descending so carousel + cards show largest first.
        sorted_wallets = sorted(wallets_out.items(), key=lambda x: x[1]["total"], reverse=True)
        wallet_summaries = {}
        all_cashflows = []
        today_str = date.today().isoformat()
        
        for k, v in sorted_wallets:
            pid = portfolio_id_by_name.get(k)
            annual_return = 0.0
            if user_id and pid:
                try:
                    cfs = portfolios.get_portfolio_cashflows(user_id, pid)
                    all_cashflows.extend(cfs)
                    # We copy to avoid mutating the cfs that we extended into all_cashflows,
                    # although get_portfolio_cashflows returns a fresh list, so we can mutate safely.
                    cfs.append((today_str, float(v["total"])))
                    cfs.sort(key=lambda x: x[0])
                    annual_return = round(portfolios.calculate_xirr(cfs), 4)
                except Exception as e:
                    print(f"XIRR error for {k}: {e}")
            wallet_summaries[k] = {"total": v["total"], "dailyPLN": v["dailyPLN"], "dailyPct": v["dailyPct"], "annualReturn": annual_return}

        summary_annual_return = 0.0
        if user_id:
            try:
                all_cashflows.append((today_str, float(summary["total"])))
                all_cashflows.sort(key=lambda x: x[0])
                summary_annual_return = round(portfolios.calculate_xirr(all_cashflows), 4)
            except Exception as e:
                print(f"XIRR error for Summary: {e}")

        wallet_summaries["Summary"] = {
            "total":    summary["total"],
            "dailyPLN": summary["dailyPLN"],
            "dailyPct": summary["dailyPct"],
            "annualReturn": summary_annual_return,
        }
        wallet_holdings = {
            k: v["holdings"]
            for k, v in sorted_wallets
        }
        wallet_holdings["Summary"] = summary["holdings"]

        portfolio_ath = None
        wallet_aths = {}
        ath_started = perf_counter()
        if user_id:
            try:
                portfolio_ath = snapshots.get_portfolio_ath(user_id, "summary")
                for wallet_name in wallet_summaries:
                    pid = "summary" if wallet_name == "Summary" else portfolio_id_by_name.get(wallet_name)
                    if not pid:
                        continue

                    if wallet_name != "Summary":
                        wallet_aths[wallet_name] = snapshots.get_portfolio_ath(user_id, pid)

                today_str = datetime.now().strftime("%Y-%m-%d")
                summary_total = summary.get("total", 0.0)
                if summary_total > 0:
                    rec_val = float(portfolio_ath.get("athValue", 0)) if portfolio_ath else 0.0
                    if not portfolio_ath or summary_total > rec_val:
                        portfolio_ath = {
                            "athValue": summary_total,
                            "athDate": today_str,
                            "athSource": "AUTO",
                        }

                for wallet_name, w_summary in wallet_summaries.items():
                    if wallet_name == "Summary":
                        continue
                    w_total = w_summary.get("total", 0.0)
                    if w_total > 0:
                        w_ath = wallet_aths.get(wallet_name)
                        w_rec_val = float(w_ath.get("athValue", 0)) if w_ath else 0.0
                        if not w_ath or w_total > w_rec_val:
                            wallet_aths[wallet_name] = {
                                "athValue": w_total,
                                "athDate": today_str,
                                "athSource": "AUTO",
                            }
            except Exception as err:
                print(f"Snapshot/ATH load failed (non-fatal): {err}")
        ath_duration = perf_counter() - ath_started

        benchmark_live_prices = {}
        if prices_view == "full":
            for b_id, b_meta in db.BENCHMARKS.items():
                price = None
                if b_id == benchmark_id:
                    if bm_out.get("intraday"):
                        price = bm_out["intraday"][-1]["c"]
                else:
                    for item in market_carousel:
                        if item["id"] == b_id:
                            if item.get("sparkline"):
                                price = item["sparkline"][-1]["c"]
                            break
                if price is None:
                    try:
                        b_cache = load_benchmark_cache(b_id)
                        if b_cache:
                            if b_cache.get("intraday"):
                                price = b_cache["intraday"][-1]["c"]
                            elif b_cache.get("daily"):
                                price = b_cache["daily"][-1]["c"]
                    except Exception:
                        pass
                if price is not None:
                    benchmark_live_prices[b_id] = float(price)

        payload = {
            "updatedAt":               datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "responseMode":            prices_view,
            "walletSummaries":         wallet_summaries,
            "walletHoldings":          wallet_holdings,
            "portfolioData":           summary["holdings"],  # movers table uses Summary
            "portfolioTotalValue":     summary["total"],
            "benchmarkLivePrices":     benchmark_live_prices,
            "portfolioDailyChangePLN": summary["dailyPLN"],
            "portfolioDailyChangePCT": summary["dailyPct"],
            "portfolioAth":            portfolio_ath,
            "walletAths":              wallet_aths,
            "walletPortfolioIds":      portfolio_id_by_name,
            # benchmark fields (user-specific)
            "benchmarkId":             benchmark_id,
            "benchmarkName":           bm_meta["name"],
            "benchmarkDailyPct":       benchmark_daily_pct,
            # Full sends only today's intraday bars (chart 1D view).
            # Historical data (daily/weekly/monthly) is fetched on-demand via view=history.
            "benchmarkData":           bm_out if include_deferred else None,
            "marketCarousel":          market_carousel,
            # legacy WIG fields kept for backward compat
            "wigDailyPct":             wig_daily_pct,
            "wigData":                 wig_out if include_deferred else None,
            "dataSource":              data_source,
        }
        
        roast_data = None
        if prices_view in ("lite", "full") and user_id:
            try:
                roast_bm_pct = benchmark_daily_pct
                if roast_bm_pct is None:
                    roast_bm_pct = _compute_benchmark_daily_pct({}, bm_meta["ticker"])
                    if roast_bm_pct is None:
                        bm_cache = load_benchmark_cache(benchmark_id)
                        roast_bm_pct = _compute_benchmark_daily_pct(bm_cache, bm_meta["ticker"]) or 0.0

                # Compute best/worst assets from summary holdings
                holdings_list = summary.get("holdings", []) if summary.get("holdings") else []
                sorted_holdings = sorted(holdings_list, key=lambda h: h.get("dailyChangePct", 0.0), reverse=True)

                best_h = sorted_holdings[0] if len(sorted_holdings) > 0 else {}
                second_best_h = sorted_holdings[1] if len(sorted_holdings) > 1 else {}
                worst_h = sorted_holdings[-1] if len(sorted_holdings) > 0 else {}
                second_worst_h = sorted_holdings[-2] if len(sorted_holdings) > 1 else {}

                # Compute drawdown from ATH
                ath_val = float(portfolio_ath.get("athValue", 0)) if portfolio_ath else 0.0
                dd_pct = ((summary["total"] - ath_val) / ath_val * 100) if ath_val > 0 and summary["total"] < ath_val else 0.0

                curr_snap = {
                    "totalPortfolioValue": summary["total"],
                    "portfolioValue": summary["total"],
                    "dailyChangePct": summary["dailyPct"],
                    "portfolioReturnPercent": summary["dailyPct"],
                    "isAth": summary["total"] >= ath_val if ath_val > 0 else False,
                    "topAssetPct": best_h.get("dailyChangePct", 0.0),
                    "secondTopAssetPct": second_best_h.get("dailyChangePct") if len(sorted_holdings) > 1 else None,
                    "worstAssetPct": worst_h.get("dailyChangePct", 0.0),
                    "secondWorstAssetPct": second_worst_h.get("dailyChangePct") if len(sorted_holdings) > 1 else None,
                    "dailyBestAsset": best_h.get("ticker", best_h.get("name")),
                    "dailyWorstAsset": worst_h.get("ticker", worst_h.get("name")),
                    "drawdownPct": dd_pct,
                    "currency": "PLN",
                    "holdingsCount": len(sorted_holdings),
                    "holdings": holdings_list,
                }
                bench_snap = {
                    "dailyChangePct": float(roast_bm_pct),
                    "benchmarkReturnPercent": float(roast_bm_pct)
                }
                roast_data = roast_engine.generate_daily_roast(
                    user_id=user_id,
                    current_snapshot=curr_snap,
                    benchmark_snapshot=bench_snap,
                    enable_ai=False,
                    enable_retry=False
                )
            except Exception as e:
                import traceback
                print(f"Roast generation failed (non-fatal): {e}")
                traceback.print_exc()

        payload["roastData"] = roast_data

        total_duration = perf_counter() - request_started
        print(
            f"/prices view={prices_view} timings "
            f"holdings={holdings_duration:.2f}s "
            f"benchmark={benchmark_duration:.2f}s "
            f"ath={ath_duration:.2f}s "
            f"total={total_duration:.2f}s"
        )
        return _resp(200, payload)

    except Exception as e:
        print(f"FATAL: {e}")
        return _resp(500, {"error": str(e)})
