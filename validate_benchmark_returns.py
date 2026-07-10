"""
validate_benchmark_returns.py — local dry-run of benchmark_returns.py.

Fetches monthly returns from yfinance for every benchmark (2020-01 → today)
WITHOUT writing to DynamoDB.  Saves results to benchmark_returns_validation.csv.

Polish indices (WIG.WA family) only work with yfinance 60m (last ~730 days).
Global indices (^GSPC, ^GDAXI …) use standard 1d data back to 2020-01.

Run:
    python3 validate_benchmark_returns.py
"""

import sys
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

# ── Benchmark registry ────────────────────────────────────────────────────

BENCHMARKS = {
    "WIG":        {"ticker": "WIG.WA",    "currency": "PLN"},
    "WIG20":      {"ticker": "WIG20.WA",  "currency": "PLN"},
    "MWIG40":     {"ticker": "mWIG40.WA", "currency": "PLN"},
    "SWIG80":     {"ticker": "sWIG80.WA", "currency": "PLN"},
    "SP500":      {"ticker": "^GSPC",     "currency": "USD"},
    "NASDAQ":     {"ticker": "^IXIC",     "currency": "USD"},
    "DAX":        {"ticker": "^GDAXI",    "currency": "EUR"},
    "MSCI_WORLD": {"ticker": "IWDA.AS",   "currency": "USD"},
}


def _prev_ym(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    m -= 1
    if m < 1:
        m, y = 12, y - 1
    return f"{y}-{m:02d}"


def _add_months(ym, n=1):
    y, m = int(ym[:4]), int(ym[5:7])
    m += n
    while m > 12:
        m -= 12; y += 1
    while m < 1:
        m += 12; y -= 1
    return f"{y}-{m:02d}"


def _today_ym():
    d = date.today()
    return f"{d.year}-{d.month:02d}"


def _is_polish(ticker):
    return ticker.upper().endswith(".WA")


def _fetch_daily(ticker, from_date, to_date):
    """1d interval — works for global indices with any date range."""
    import yfinance as yf
    df = yf.Ticker(ticker).history(start=from_date, end=to_date, interval="1d")
    if df.empty:
        return {}
    closes = {}
    for idx, row in df.iterrows():
        closes[idx.strftime("%Y-%m")] = round(float(row["Close"]), 4)
    return closes


def _fetch_hourly(ticker, from_date, to_date):
    """60m chunks — needed for Polish .WA tickers, limited to last ~730 days."""
    import yfinance as yf
    import pandas as pd

    CHUNK_DAYS = 59
    end_dt   = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    now      = datetime.now(tz=timezone.utc)
    earliest = now - timedelta(days=729)
    start_dt = max(start_dt, earliest)

    chunks = []
    cur_end = min(end_dt, now + timedelta(days=1))
    tkr = yf.Ticker(ticker)
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
        except Exception as e:
            print(f"    60m chunk error: {e}")
        cur_end = cur_start - timedelta(days=1)

    if not chunks:
        return {}

    df = pd.concat(chunks[::-1])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    try:
        df.index = df.index.tz_convert("Europe/Warsaw")
    except Exception:
        df.index = df.index.tz_convert("UTC")

    closes = {}
    for idx, row in df.iterrows():
        closes[idx.strftime("%Y-%m")] = round(float(row["Close"]), 4)
    return closes


def compute_returns(benchmark_id, ticker, from_ym="2020-01", to_ym=None):
    """Compute monthly returns without touching DynamoDB."""
    if not to_ym:
        to_ym = _today_ym()

    fetch_from_ym   = _prev_ym(from_ym)
    fetch_from_date = f"{fetch_from_ym[:4]}-{fetch_from_ym[5:7]}-01"
    fetch_to_ym     = _add_months(to_ym, 1)
    fetch_to_date   = f"{fetch_to_ym[:4]}-{fetch_to_ym[5:7]}-15"

    if _is_polish(ticker):
        note = "60m / last ~730d"
        closes = _fetch_hourly(ticker, fetch_from_date, fetch_to_date)
    else:
        note = "1d / full range"
        closes = _fetch_daily(ticker, fetch_from_date, fetch_to_date)

    print(f"  {benchmark_id:<12} ({ticker:<12})  [{note}]  ", end="", flush=True)

    if not closes:
        print("NO DATA")
        return []

    rows = []
    ym = from_ym
    while ym <= to_ym:
        prev = _prev_ym(ym)
        if ym in closes and prev in closes and closes[prev] > 0:
            ret_pct = round((closes[ym] - closes[prev]) / closes[prev] * 100, 6)
            rows.append({
                "benchmarkId": benchmark_id,
                "ticker":      ticker,
                "month":       ym,
                "openPrice":   closes[prev],
                "closePrice":  closes[ym],
                "returnPct":   ret_pct,
            })
        ym = _add_months(ym, 1)

    first = rows[0]["month"] if rows else "-"
    last  = rows[-1]["month"] if rows else "-"
    print(f"{len(rows)} months  {first}–{last}")
    return rows


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    from_ym = "2020-01"
    to_ym   = _today_ym()
    print(f"\nValidating benchmark returns {from_ym} → {to_ym}\n")
    print("Note: Polish indices (.WA) are limited to the last ~730 days by yfinance.\n")

    all_rows = []
    errors   = []

    for bid, bm in BENCHMARKS.items():
        try:
            rows = compute_returns(bid, bm["ticker"], from_ym=from_ym, to_ym=to_ym)
            all_rows.extend(rows)
        except Exception as exc:
            errors.append((bid, str(exc)))
            print(f"  ERROR: {bid} → {exc}")

    # Write CSV
    out_path = "benchmark_returns_validation.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["benchmarkId", "ticker", "month", "openPrice", "closePrice", "returnPct"],
        )
        writer.writeheader()
        all_rows.sort(key=lambda r: (r["benchmarkId"], r["month"]))
        writer.writerows(all_rows)

    print(f"\nWrote {len(all_rows)} rows → {out_path}")

    # Per-benchmark summary
    print("\nSummary:")
    by_bid = {}
    for r in all_rows:
        by_bid.setdefault(r["benchmarkId"], []).append(r)
    for bid in sorted(by_bid):
        rows = by_bid[bid]
        rets  = [r["returnPct"] for r in rows]
        first = rows[0]["month"]
        last  = rows[-1]["month"]
        avg   = round(sum(rets) / len(rets), 3) if rets else 0
        print(
            f"  {bid:<12} {len(rows):>2} months  {first}–{last}"
            f"  avg={avg:+.2f}%  min={min(rets):+.2f}%  max={max(rets):+.2f}%"
        )

    if errors:
        print(f"\nFailed: {errors}")
        sys.exit(1)


if __name__ == "__main__":
    main()


