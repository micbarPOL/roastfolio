#!/usr/bin/env python3
"""
Fetch WIG OHLCV history → src/scripts/data-wig.js

Yahoo Finance only provides 2 daily points for WIG.WA, but hourly (60m) data
goes back 730 days. This script fetches hourly in 59-day chunks and aggregates
to daily/weekly/monthly candles (~2 years of history).

Run: .venv/bin/python3 update-wig.py
"""
import json, os, sys
from datetime import datetime, date, timedelta, timezone

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("ERROR: yfinance/pandas not found. Run: .venv/bin/pip install yfinance pandas")
    sys.exit(1)

CACHE_FILE  = "src/scripts/data-wig.js"
TICKER      = "WIG.WA"
CHUNK_DAYS  = 59   # Yahoo Finance 60m limit: max 730 days total
MAX_CHUNKS  = 13   # 13 × 59 ≈ 767 days, covers the 730-day window

def fetch_all_hourly():
    """Fetch hourly bars in 59-day chunks going back up to 730 days."""
    ticker = yf.Ticker(TICKER)
    chunks = []
    end = datetime.now(tz=timezone.utc)
    for i in range(MAX_CHUNKS):
        start = end - timedelta(days=CHUNK_DAYS)
        try:
            h = ticker.history(start=start.strftime('%Y-%m-%d'),
                               end=end.strftime('%Y-%m-%d'),
                               interval='60m')
            if h.empty:
                print(f"  chunk {i}: empty — stopping")
                break
            print(f"  chunk {i}: {start.date()} → {end.date()}: {len(h)} rows")
            chunks.append(h)
        except Exception as e:
            print(f"  chunk {i} error: {e}")
            break
        end = start - timedelta(days=1)
    if not chunks:
        return pd.DataFrame()
    df = pd.concat(chunks[::-1])  # oldest first
    df = df[~df.index.duplicated(keep='last')].sort_index()
    return df

def aggregate_daily(hourly_df):
    """Aggregate hourly OHLCV → daily candles in Warsaw time."""
    h = hourly_df.copy()
    h.index = h.index.tz_convert('Europe/Warsaw')
    agg = h.resample('D').agg(
        {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
    ).dropna(subset=['Close'])
    return [{'t': idx.strftime('%Y-%m-%d'),
             'o': round(float(r['Open']),  2), 'h': round(float(r['High']),  2),
             'l': round(float(r['Low']),   2), 'c': round(float(r['Close']), 2),
             'v': int(r['Volume'] or 0)}
            for idx, r in agg.iterrows()]

def aggregate_weekly(daily_rows):
    if not daily_rows: return []
    df = pd.DataFrame(daily_rows)
    df['t'] = pd.to_datetime(df['t'])
    df = df.set_index('t').sort_index()
    agg = df.resample('W-MON', closed='left', label='left').agg(
        {'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last', 'v': 'sum'}
    ).dropna(subset=['c'])
    return [{'t': idx.strftime('%Y-%m-%d'),
             'o': round(float(r['o']),2), 'h': round(float(r['h']),2),
             'l': round(float(r['l']),2), 'c': round(float(r['c']),2),
             'v': int(r['v'] or 0)} for idx, r in agg.iterrows()]

def aggregate_monthly(daily_rows):
    if not daily_rows: return []
    df = pd.DataFrame(daily_rows)
    df['t'] = pd.to_datetime(df['t'])
    df = df.set_index('t').sort_index()
    agg = df.resample('MS').agg(
        {'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last', 'v': 'sum'}
    ).dropna(subset=['c'])
    return [{'t': idx.strftime('%Y-%m-%d'),
             'o': round(float(r['o']),2), 'h': round(float(r['h']),2),
             'l': round(float(r['l']),2), 'c': round(float(r['c']),2),
             'v': int(r['v'] or 0)} for idx, r in agg.iterrows()]

def df_to_ts_rows(df):
    """Convert DataFrame with DatetimeIndex → list with unix timestamp keys."""
    rows = []
    for idx, r in df.iterrows():
        if pd.isna(r['Close']): continue
        rows.append({'t': int(idx.timestamp()),
                     'o': round(float(r['Open']),  2), 'h': round(float(r['High']),  2),
                     'l': round(float(r['Low']),   2), 'c': round(float(r['Close']), 2),
                     'v': int(r['Volume'] or 0)})
    return rows

def write_js(data, wig_daily_pct):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        f.write(f"// WIG OHLCV cache — {data.get('updated','')}\n")
        f.write(f"var WIG_DAILY_PCT_STATIC = {wig_daily_pct};\n")
        f.write("const WIG_DATA = ")
        f.write(json.dumps(data, separators=(',', ':')))
        f.write(";\n")

if __name__ == "__main__":
    print(f"Fetching {TICKER} history (chunked 60m → aggregated daily)…")

    hourly_df = fetch_all_hourly()
    if hourly_df.empty:
        print("ERROR: No hourly data fetched"); sys.exit(1)

    now    = datetime.now(tz=timezone.utc)
    daily  = aggregate_daily(hourly_df)
    weekly = aggregate_weekly(daily)
    monthly= aggregate_monthly(daily)
    print(f"  Daily:   {len(daily)} days")
    print(f"  Weekly:  {len(weekly)} weeks")
    print(f"  Monthly: {len(monthly)} months")

    # Raw hourly (last 60d, unix timestamps for intraday chart)
    hourly = df_to_ts_rows(hourly_df[hourly_df.index >= now - timedelta(days=60)])
    print(f"  Hourly:  {len(hourly)} bars (last 60d)")

    # 1-minute intraday (last trading day)
    try:
        intra_df = yf.Ticker(TICKER).history(period='1d', interval='1m')
        intraday = df_to_ts_rows(intra_df) if not intra_df.empty else []
    except Exception as e:
        print(f"  Intraday error: {e}")
        intraday = []
    print(f"  Intraday: {len(intraday)} 1m bars")

    # Current daily % — fetch directly from fast_info for the most up-to-date value
    wig_daily_pct = 0.0
    try:
        info = yf.Ticker(TICKER).fast_info
        price = info.last_price
        prev  = info.previous_close
        if price and prev:
            wig_daily_pct = round((price - prev) / prev * 10000) / 100
            print(f"  WIG daily %: {wig_daily_pct:+.2f}%  (price={price:.0f}, prev={prev:.0f})")
    except Exception as e:
        # Fall back to computing from intraday bars
        if intraday and intraday[0]['o']:
            wig_daily_pct = round((intraday[-1]['c'] - intraday[0]['o']) / intraday[0]['o'] * 10000) / 100
        print(f"  fast_info failed ({e}), fallback daily %: {wig_daily_pct:+.2f}%")

    result = {
        'version': 2,
        'updated': date.today().isoformat(),
        'daily':   daily,
        'weekly':  weekly,
        'monthly': monthly,
        'hourly':  hourly,
        'intraday': intraday,
    }

    write_js(result, wig_daily_pct)
    print(f"\n✓ Written to {CACHE_FILE}")
    print(f"  daily={len(daily)}, weekly={len(weekly)}, "
          f"hourly={len(hourly)}, intraday={len(intraday)}, wig_pct={wig_daily_pct:+.2f}%")
