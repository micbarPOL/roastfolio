#!/usr/bin/env python3
"""
Fetches live stock prices from Yahoo Finance and Polish TFI fund NAV from bankier.pl,
then updates portfolio-data.js.
Run this script to refresh prices before opening the web app.
Usage: python3 update-prices.py
"""

import json
import sys
import re
import urllib.request
from datetime import datetime, date

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed. Run: pip3 install yfinance")
    sys.exit(1)

# Map holding name → (yahoo ticker, currency)
TICKER_MAP = {
    "XTB":                          ("XTB.WA",   "PLN"),
    "RAINBOW (RBW)":                ("RBW.WA",   "PLN"),
    "MOBRUK (MBR)":                 ("MBR.WA",   "PLN"),
    "CREOTECH (CRI)":               ("CRI.WA",   "PLN"),
    "CDPROJEKT (CDR)":              ("CDR.WA",   "PLN"),
    "Meta Platforms, Inc. (META)":  ("META",      "USD"),
    "Bitcoin (BTC)":                ("BTC-USD",   "USD"),
}

# Map holding name → bankier.pl fund ticker code
# Find the code at https://www.bankier.pl/fundusze/notowania — it's in the URL.
# Example: https://www.bankier.pl/fundusze/notowania/PCS21 → ticker is "PCS21"
TFI_TICKER_MAP = {
    # "PKO Akcji Polskich":          "PCS21",
    # "PKO Obligacji Długoterminowych": "PKODLU",
    # Add your fund names (as they appear in the myfund.pl CSV) and their tickers here.
}

# Wallets: label → CSV path  (Emerytura first — it gets the full holdings detail)
WALLETS = {
    "Emerytura": "src/data/myfund.pl_Emerytura_portfelSklad.csv",
    "IKE":       "src/data/myfund.pl_IKE_portfelSklad.csv",
    "IKZE":      "src/data/myfund.pl_IKZE_portfelSklad.csv",
    "XTB":       "src/data/myfund.pl_XTB_portfelSklad.csv",
}

def parse_wallet_csv(path):
    """Return list of {name, units, purchaseValue, currency} skipping totals row."""
    holdings = []
    with open(path, encoding='iso-8859-1') as f:
        lines = f.read().strip().split('\n')
    for line in lines[1:]:
        parts = line.split(';')
        name = parts[0].strip()
        if name.startswith('Razem') or not name:
            continue
        def clean(v): return v.strip().replace('\xa0', '').replace('\u00a0', '').replace(' ', '')
        try:
            units = float(clean(parts[6]))
            pv    = float(clean(parts[9]))
            ticker, currency = TICKER_MAP.get(name, (None, "PLN"))
            tfi_ticker = TFI_TICKER_MAP.get(name)
            holdings.append({"name": name, "units": units, "purchaseValue": pv,
                              "ticker": ticker, "tfi_ticker": tfi_ticker,
                              "currency": currency})
        except (ValueError, IndexError):
            pass
    return holdings

def get_pln_rate(currency, rates_cache):
    if currency == "PLN":
        return 1.0
    if currency in rates_cache:
        return rates_cache[currency]
    try:
        rate = yf.Ticker(f"{currency}PLN=X").fast_info.last_price
        print(f"  {currency}/PLN rate: {rate:.4f}")
        rates_cache[currency] = rate
        return rate
    except Exception as e:
        print(f"  WARNING: Could not fetch {currency}/PLN rate: {e}")
        return None

def fetch_nav_bankier(bankier_ticker):
    """Fetch current NAV (PLN) for a Polish TFI fund from bankier.pl.
    Returns (price_float, nav_date_str) or (None, None) on failure.
    No API key required — price is embedded in the page HTML.
    """
    url = f"https://www.bankier.pl/fundusze/notowania/{bankier_ticker}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; investment-history-bot/1.0)",
        "Accept-Language": "pl-PL,pl;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WARNING: bankier.pl fetch failed for {bankier_ticker}: {e}")
        return None, None
    # Price: <span class="a-quote-item -value">179,16\xa0PLN</span>
    price_m = re.search(r'a-quote-item\s+-value">([\d\s]+[,\.][\d]{2})\s*(?:\xa0)?PLN', html)
    # Date: e.g. "18.05.2026" near the price header
    pos = html.find("a-quote-item")
    date_m  = re.search(r'(\d{2}\.\d{2}\.\d{4})', html[max(0, pos - 500):pos + 500])
    if not price_m:
        print(f"  WARNING: could not parse NAV for {bankier_ticker} from bankier.pl")
        return None, None
    price = float(price_m.group(1).replace("\xa0", "").replace(" ", "").replace(",", "."))
    nav_date = date_m.group(1) if date_m else None
    return price, nav_date


def fetch_ticker_data(ticker_sym):
    """Fetch price, daily %, YTD %, today's 1m bars, and last-year weekly bars."""
    t = yf.Ticker(ticker_sym)
    info = t.fast_info
    price = info.last_price
    prev_close = info.previous_close
    daily_pct = round(((price - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

    today_bars = []  # [[ts_ms, close], ...]
    year_bars  = []  # [[ts_ms, close], ...]
    ytd_pct = 0.0

    try:
        intra = t.history(period='1d', interval='1m')
        for ts, row in intra.iterrows():
            c = row['Close']
            if c and c == c:  # not NaN
                today_bars.append([int(ts.timestamp() * 1000), round(float(c), 4)])
    except Exception:
        pass

    try:
        hist = t.history(period='1y', interval='1wk')
        for ts, row in hist.iterrows():
            c = row['Close']
            if c and c == c:
                year_bars.append([int(ts.timestamp() * 1000), round(float(c), 4)])
        if year_bars:
            ytd_pct = round(((price - year_bars[0][1]) / year_bars[0][1]) * 100, 2)
        # append live price as final point for both series
        import time as _time
        now_ms = int(_time.time() * 1000)
        today_bars.append([now_ms, round(price, 4)])
        year_bars.append([now_ms, round(price, 4)])
    except Exception:
        ytd_pct = 0.0

    vol = getattr(info, 'last_volume', None)
    avg_vol = getattr(info, 'ten_day_average_volume', None) or getattr(info, 'three_month_average_volume', None)
    tz = getattr(info, 'timezone', None)
    vol_val = int(vol) if (vol is not None and vol == vol and not math.isnan(vol)) else 0
    avg_vol_val = int(avg_vol) if (avg_vol is not None and avg_vol == avg_vol and not math.isnan(avg_vol)) else 0

    return price, daily_pct, ytd_pct, today_bars, year_bars, vol_val, avg_vol_val, tz

def compute_wallet(wallet_name, holdings, price_cache, rates_cache):
    """Compute all metrics for a wallet's holdings. price_cache is shared across wallets."""
    results = []
    for h in holdings:
        entry = dict(h)
        if h["ticker"] is None and not h.get("tfi_ticker"):
            entry.update({"currentValue": h["purchaseValue"], "pricePLN": 1.0,
                          "priceOriginal": 1.0, "priceOriginalCurrency": "PLN",
                          "dailyChangePct": 0.0, "ytdChangePct": 0.0,
                          "profit": 0.0, "returnPct": 0.0, "dailyChangePLN": 0.0, "pct": 0,
                          "volume": 0, "avgVolume": 0, "volumeTz": None})
            results.append(entry)
            continue

        if h["ticker"] is None and h.get("tfi_ticker"):
            tfi_key = f"tfi:{h['tfi_ticker']}"
            if tfi_key not in price_cache:
                nav, nav_date = fetch_nav_bankier(h["tfi_ticker"])
                price_cache[tfi_key] = nav
                if nav:
                    print(f"  {h['name']:40} {nav:.2f} PLN  (NAV {nav_date or '?'})")
            nav = price_cache.get(tfi_key)
            if nav is None:
                results.append(entry)
                continue
            cv = round(h["units"] * nav, 2)
            profit = round(cv - h["purchaseValue"], 2)
            ret_pct = round((profit / h["purchaseValue"]) * 100, 2) if h["purchaseValue"] else 0
            entry.update({"currentValue": cv, "profit": profit, "returnPct": ret_pct,
                          "pricePLN": round(nav, 2), "priceOriginal": round(nav, 2),
                          "priceOriginalCurrency": "PLN",
                          "dailyChangePct": 0.0, "ytdChangePct": 0.0,
                          "dailyChangePLN": 0.0, "pct": 0,
                          "todayBars": [], "yearBars": [],
                          "volume": 0, "avgVolume": 0, "volumeTz": None})
            results.append(entry)
            continue

        try:
            # Fetch from cache or live
            if h["ticker"] not in price_cache:
                price, daily_pct, ytd_pct, today_bars, year_bars, vol_val, avg_vol_val, tz = fetch_ticker_data(h["ticker"])
                price_cache[h["ticker"]] = (price, daily_pct, ytd_pct, today_bars, year_bars, vol_val, avg_vol_val, tz)
                print(f"  {h['name']:40} {price:.2f} {h['currency']}  Daily: {daily_pct:+.2f}%  YTD: {ytd_pct:+.2f}%")
            price, daily_pct, ytd_pct, today_bars, year_bars, vol_val, avg_vol_val, tz = price_cache[h["ticker"]]

            rate = get_pln_rate(h["currency"], rates_cache)
            if rate is None:
                results.append(entry)
                continue

            price_pln = price * rate
            cv = round(h["units"] * price_pln, 2)
            profit = round(cv - h["purchaseValue"], 2)
            ret_pct = round((profit / h["purchaseValue"]) * 100, 2) if h["purchaseValue"] else 0
            daily_pln = round(cv - cv / (1 + daily_pct / 100), 2) if daily_pct != 0 else 0.0

            entry.update({"currentValue": cv, "profit": profit, "returnPct": ret_pct,
                          "pricePLN": round(price_pln, 2), "priceOriginal": round(price, 2),
                          "priceOriginalCurrency": h["currency"],
                          "dailyChangePct": daily_pct, "ytdChangePct": ytd_pct,
                          "dailyChangePLN": daily_pln, "pct": 0,
                          "todayBars": today_bars, "yearBars": year_bars,
                          "volume": vol_val, "avgVolume": avg_vol_val, "volumeTz": tz})
            results.append(entry)

        except Exception as e:
            print(f"  ERROR {h['name']}: {e}")
            results.append(entry)

    # Compute portfolio % and wallet totals
    total = sum(r.get("currentValue", 0) for r in results)
    total_daily_pln = 0.0
    for r in results:
        r["pct"] = round((r.get("currentValue", 0) / total) * 100, 2) if total else 0
        total_daily_pln += r.get("dailyChangePLN", 0)

    total_daily_pln = round(total_daily_pln, 2)
    total_prev = total - total_daily_pln
    total_daily_pct = round((total_daily_pln / total_prev) * 100, 2) if total_prev else 0.0

    return results, round(total, 2), total_daily_pln, total_daily_pct

def write_js(wallets_data, updated_at):
    output_path = "src/scripts/portfolio-data.js"

    with open(output_path, "w") as f:
        f.write(f"// Portfolio data — auto-updated by update-prices.py\n")
        f.write(f"// Last updated: {updated_at}\n\n")
        f.write(f"var PORTFOLIO_UPDATED_AT = '{updated_at}';\n\n")

        # Write per-wallet summary for the dashboard
        f.write("var WALLET_SUMMARIES = {\n")
        for name, (results, total, daily_pln, daily_pct) in wallets_data.items():
            f.write(f"  {json.dumps(name)}: {{ total: {total}, dailyPLN: {daily_pln}, dailyPct: {daily_pct} }},\n")
        f.write("};\n\n")

        # Write Emerytura full holdings (used by Portfolio tab)
        emerytura_results, total, daily_pln, daily_pct = wallets_data["Emerytura"]
        f.write(f"var PORTFOLIO_TOTAL_VALUE = {total};\n")
        f.write(f"var PORTFOLIO_DAILY_CHANGE_PLN = {daily_pln};\n")
        f.write(f"var PORTFOLIO_DAILY_CHANGE_PCT = {daily_pct};\n\n")
        f.write("var PORTFOLIO_DATA = [\n")
        for r in emerytura_results:
            today_bars = json.dumps(r.get('todayBars', []))
            year_bars  = json.dumps(r.get('yearBars', []))
            f.write(
                f"  {{ name: {json.dumps(r['name'])}, "
                f"currentValue: {r.get('currentValue', 0)}, "
                f"purchaseValue: {r['purchaseValue']}, "
                f"pct: {r.get('pct', 0)}, "
                f"profit: {r.get('profit', 0)}, "
                f"returnPct: {r.get('returnPct', 0)}, "
                f"pricePLN: {r.get('pricePLN', 0)}, "
                f"priceOriginal: {r.get('priceOriginal', 0)}, "
                f"priceOriginalCurrency: {json.dumps(r.get('priceOriginalCurrency', 'PLN'))}, "
                f"dailyChangePct: {r.get('dailyChangePct', 0)}, "
                f"dailyChangePLN: {r.get('dailyChangePLN', 0)}, "
                f"ytdChangePct: {r.get('ytdChangePct', 0)}, "
                f"todayBars: {today_bars}, "
                f"yearBars: {year_bars} }},\n"
            )
        f.write("];\n")

    print(f"\n✓ Written to {output_path}")
    for name, (_, total, daily_pln, daily_pct) in wallets_data.items():
        print(f"  {name:12} {total:>14,.2f} PLN  |  Today: {daily_pln:>+12,.2f} PLN ({daily_pct:+.2f}%)")
    print(f"✓ Last updated: {updated_at}")

def generate_returns_data():
    """
    Parse myfund.pl_Emerytura_StopaZwrotuWOkresach.csv and write data-returns.js.
    Preserves any hand-corrected mWIG40 values already in the JS file.
    """
    import re, os

    CSV_PATH = "src/data/myfund.pl_Emerytura_StopaZwrotuWOkresach.csv"
    OUT_PATH  = "src/scripts/data-returns.js"

    if not os.path.exists(CSV_PATH):
        print(f"  ⚠ {CSV_PATH} not found — skipping returns data")
        return

    # Load existing JS to preserve hand-corrected values
    existing = {}
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH) as f:
                m = re.search(r'\[.*\]', f.read(), re.DOTALL)
            if m:
                for row in json.loads(m.group(0)):
                    existing[row['period']] = row
        except Exception:
            pass

    def safe(v):
        try: return float(v.strip()) if v.strip() else None
        except: return None

    with open(CSV_PATH, encoding='iso-8859-2') as f:
        lines = f.read().strip().split('\n')

    rows = []
    for line in lines[1:]:
        parts = line.split(';')
        if len(parts) < 7 or not parts[0].strip():
            continue
        period = parts[0].strip()
        mwig_csv = safe(parts[8]) if len(parts) > 8 else None
        if mwig_csv == 0.0:
            mwig_csv = None

        # Prefer hand-corrected value from existing JS over raw CSV.
        # Treat both None and 0.0 in JS as "no correction" so a real CSV value
        # can fill it in, and so CSV 0.0 can never overwrite a real JS value.
        prev = existing.get(period, {})
        prev_mwig = prev.get('mwig40')
        mwig = prev_mwig if (prev_mwig is not None and prev_mwig != 0.0) else mwig_csv

        rows.append({
            'period':    period,
            'emerytura': safe(parts[1]),
            'wig':       safe(parts[2]),
            'wig20':     safe(parts[3]),
            'inflation': safe(parts[4]),
            'deposits':  safe(parts[5]),
            'sp500':     safe(parts[6]),
            'mwig40':    mwig,
        })

    output  = '// Monthly returns data — auto-generated from CSV + verified mWIG40 values\n'
    output += 'var RETURNS_DATA = ' + json.dumps(rows, separators=(',', ':')) + ';\n'
    with open(OUT_PATH, 'w') as f:
        f.write(output)

    filled = sum(1 for r in rows if r['mwig40'] is not None)
    print(f"✓ {OUT_PATH} — {len(rows)} months, mWIG40 filled for {filled}/{len(rows)}")


if __name__ == "__main__":
    print("Fetching live prices from Yahoo Finance...\n")
    price_cache = {}
    rates_cache = {}
    wallets_data = {}
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for wallet_name, csv_path in WALLETS.items():
        print(f"\n── {wallet_name} ──")
        holdings = parse_wallet_csv(csv_path)
        results, total, daily_pln, daily_pct = compute_wallet(wallet_name, holdings, price_cache, rates_cache)
        wallets_data[wallet_name] = (results, total, daily_pln, daily_pct)

    write_js(wallets_data, updated_at)

    print("\n── Monthly returns data ──")
    generate_returns_data()

    print("\nDone! Refresh your browser to see updated prices.")

