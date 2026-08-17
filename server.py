#!/usr/bin/env python3
"""
Local dev server for investment-history.
Runs update-prices.py automatically on each page refresh of index.html.
Usage: python3 server.py

Also exposes POST /refresh to run update-all.sh on demand (used by the UI button).

Mock API (auto-active when no config.js):
  GET/PUT   /profile
  GET       /portfolios
  PUT       /portfolios
  GET/DELETE /portfolios/{id}
  GET/PUT   /portfolios/{id}/holdings
  DELETE    /portfolios/{id}/holdings/{holdingId}
  GET/POST  /portfolios/{id}/transactions
  DELETE    /portfolios/{id}/transactions/{txId}
  GET       /portfolios/{id}/snapshots
  GET/PUT   /portfolios/{id}/ath
  GET       /benchmarks
  GET       /search?q=...
  GET       /tfi/lookup?code=...
"""

import http.server
import socketserver
import subprocess
import sys
import os
import re
import time
import json
import copy
import math
import random
import webbrowser
from datetime import datetime, date, timedelta, timezone
from threading import Thread, Lock
from urllib.parse import urlparse, parse_qs

PORT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8080
ROOT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'update-prices.py')
UPDATE_ALL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'update-all.sh')

# Debounce: only run update if at least 30s have passed since last run
_last_update = 0
_update_lock = Lock()
_update_version = 0   # increments every time a fresh update completes


# ── Mock API data store ─────────────────────────────────────────────────────

def _iso(d):
    return d.strftime('%Y-%m-%dT%H:%M:%SZ') if isinstance(d, datetime) else d.isoformat() + 'T00:00:00Z'

def _gen_snapshots(portfolio_id, start_value, invested, days=2200):
    """Generate plausible multi-year daily snapshots (2020-2026) with random-walk portfolio value."""
    random.seed(abs(hash(portfolio_id)) % 100000)
    snaps = []
    v = start_value
    inv = invested
    today = date.today()
    for i in range(days, 0, -1):
        d = today - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        if d.day == 1 and i < days:
            inv += random.choice([500, 1000, 1500, 2000])
            v += inv * 0.05
        v *= 1 + random.gauss(0.0006, 0.012)
        snaps.append({
            'snapshotDate':    d.isoformat(),
            'portfolioId':     portfolio_id,
            'portfolioValue':  round(v, 2),
            'investmentValue': round(inv, 2),
            'dailyReturn':     round(random.gauss(0.05, 1.1), 4),
            'benchmarkId':     'WIG',
            'benchmarkValue':  round(50000 + (days - i) * 18 + random.gauss(0, 400), 2),
            'xirr':            round(random.gauss(0.15, 0.05), 4),
        })
    return snaps

def _xirr(cashflows):
    """
    Calculate annualized return using Newton-Raphson.
    cashflows: list of tuples (date_string_or_date, amount_float)
    """
    if not cashflows or len(cashflows) < 2:
        return 0.0
    try:
        if isinstance(cashflows[0][0], str):
            dates = [datetime.fromisoformat(cf[0].replace('Z', '+00:00')[:10]) for cf in cashflows]
        else:
            dates = [cf[0] for cf in cashflows]
    except Exception:
        return 0.0
    amounts = [cf[1] for cf in cashflows]
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return 0.0
    t0 = dates[0]
    years = [(d - t0).days / 365.0 for d in dates]
    r = 0.1
    for _ in range(100):
        f_r = 0.0
        f_prime_r = 0.0
        for a, y in zip(amounts, years):
            f_r += a / ((1.0 + r) ** y)
            f_prime_r += -y * a / ((1.0 + r) ** (y + 1))
        if abs(f_prime_r) < 1e-10:
            break
        r_new = r - f_r / f_prime_r
        if abs(r_new - r) < 1e-6:
            return r_new
        r = r_new
        if r <= -1.0:
            return -0.9999
    return r

# ── Mock prices helpers ────────────────────────────────────────────────────

_MOCK_PRICES = [
    {'name': 'CD Projekt',  'ticker': 'CDR.WA', 'currency': 'PLN', 'units': 10,  'purchaseValue': 1350.00, 'price': 148.5,  'dailyPct':  0.81, 'portfolioId': 'demo', 'walletName': 'Demo Portfolio', 'volume': 185000, 'avgVolume': 312000, 'volumeTz': 'Europe/Warsaw'},
    {'name': 'XTB',         'ticker': 'XTB.WA', 'currency': 'PLN', 'units': 25,  'purchaseValue': 3250.00, 'price': 142.2,  'dailyPct':  1.14, 'portfolioId': 'demo', 'walletName': 'Demo Portfolio', 'volume': 420000, 'avgVolume': 540000, 'volumeTz': 'Europe/Warsaw'},
    {'name': 'Cash',        'ticker': None,      'currency': 'PLN', 'units': 1,   'purchaseValue': 5000.00, 'price': 5000.0, 'dailyPct':  0.0,  'portfolioId': 'demo', 'walletName': 'Demo Portfolio', 'volume': 0, 'avgVolume': 0, 'volumeTz': None},
    {'name': 'KGHM',        'ticker': 'KGH.WA', 'currency': 'PLN', 'units': 20,  'purchaseValue': 3200.00, 'price': 173.4,  'dailyPct': -0.34, 'portfolioId': 'ike',  'walletName': 'IKE', 'volume': 650000, 'avgVolume': 800000, 'volumeTz': 'Europe/Warsaw'},
    {'name': 'Cash IKE',    'ticker': None,      'currency': 'PLN', 'units': 1,   'purchaseValue': 1800.00, 'price': 1800.0, 'dailyPct':  0.0,  'portfolioId': 'ike',  'walletName': 'IKE', 'volume': 0, 'avgVolume': 0, 'volumeTz': None},
]

def _enrich(row):
    row = dict(row)
    val    = round(row['units'] * row['price'], 2)
    chgPLN = round(val * row['dailyPct'] / 100, 2)
    row['value']                 = val
    row['currentValue']          = val
    row['pricePLN']              = row['price']           # dashboard table
    row['priceOriginal']         = row['price']
    row['priceOriginalCurrency'] = row.get('currency', 'PLN')
    row['dailyChangePLN']        = chgPLN                  # dashboard table
    row['dailyChangePct']        = row['dailyPct']          # dashboard table
    row['dailyPLN']              = chgPLN                  # wallet summary aggregation
    row['gain']                  = round(val - row['purchaseValue'], 2)
    row['profit']                = row['gain']
    if row['purchaseValue'] > 0:
        row['returnPct']         = round((row['profit'] / row['purchaseValue']) * 100, 2)
    else:
        row['returnPct']         = 0.0
    row['todayBars']             = []
    row['yearBars']              = []
    row['volume']                = row.get('volume', 0)
    row['avgVolume']             = row.get('avgVolume', 0)
    row['volumeTz']              = row.get('volumeTz', 'Europe/Warsaw' if row.get('ticker') else None)
    return row

def _fake_wig_data():
    """Generate simple fake WIG intraday + daily bars so the benchmark chart renders."""
    import random as _r
    _r.seed(99)
    now_utc  = datetime.now(timezone.utc)
    base     = 90000.0
    # ~8 intraday hourly bars (09:00–16:00 Warsaw = 07:00–14:00 UTC on a summer day)
    intraday = []
    price    = base
    for i in range(8):
        t     = int(now_utc.replace(hour=7, minute=0, second=0, microsecond=0).timestamp() * 1000) + i * 3600000
        price = round(price * (1 + _r.uniform(-0.003, 0.004)), 2)
        intraday.append({'t': t, 'o': base, 'h': price + 50, 'l': price - 50, 'c': price, 'v': 500000})
    # 30 daily bars going back 30 calendar days
    daily = []
    price = base
    for i in range(30, 0, -1):
        t     = int((now_utc - timedelta(days=i)).replace(hour=16, minute=0, second=0, microsecond=0).timestamp() * 1000)
        price = round(price * (1 + _r.uniform(-0.008, 0.010)), 2)
        daily.append({'t': t, 'o': price - 20, 'h': price + 80, 'l': price - 80, 'c': price, 'v': 800000})
    return {'intraday': intraday, 'daily': daily, 'weekly': [], 'monthly': [], 'hourly': []}


def _mock_prices(view='full'):
    rows  = [_enrich(r) for r in _MOCK_PRICES]
    now   = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    wallets = {}
    for r in rows:
        wn = r['walletName']
        if wn not in wallets:
            wallets[wn] = {'total': 0, 'invested': 0, 'dailyPLN': 0}
        wallets[wn]['total']    += r['value']
        wallets[wn]['invested'] += r['purchaseValue']
        wallets[wn]['dailyPLN'] += r['dailyPLN']
    for wn, w in wallets.items():
        w['total']    = round(w['total'], 2)
        w['invested'] = round(w['invested'], 2)
        w['dailyPLN'] = round(w['dailyPLN'], 2)
        w['dailyPct'] = round(w['dailyPLN'] / w['total'] * 100, 4) if w['total'] else 0
    total     = round(sum(w['total']    for w in wallets.values()), 2)
    invested  = round(sum(w['invested'] for w in wallets.values()), 2)
    dailyPLN  = round(sum(w['dailyPLN'] for w in wallets.values()), 2)
    dailyPct  = round(dailyPLN / total * 100, 4) if total else 0
    wallets['Summary'] = {'total': total, 'invested': invested, 'dailyPLN': dailyPLN, 'dailyPct': dailyPct}
    portfolio_ids = {r['walletName']: r['portfolioId'] for r in rows}
    portfolio_ids['Summary'] = 'summary'
    
    # Calculate XIRR for each wallet
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    all_cashflows = []
    for wn, w in wallets.items():
        if wn == 'Summary': continue
        pid = portfolio_ids.get(wn)
        txs = _mock.get('transactions', {}).get(pid, [])
        cashflows = []
        for tx in txs:
            tx_type = str(tx.get('type') or '').upper()
            val = float(tx.get('amount') or tx.get('value') or 0)
            affect_cash = tx.get('affectCash')
            if affect_cash is None:
                affect_cash = True
            else:
                affect_cash = bool(affect_cash)
                
            date_val = str(tx.get('date') or tx.get('transactionDate') or today_str)[:10]

            if tx_type == 'DEPOSIT':
                cashflows.append((date_val, -val))
            elif tx_type in ('WITHDRAWAL', 'EXTRA_COST'):
                cashflows.append((date_val, val))
            elif tx_type == 'BUY' and not affect_cash:
                cashflows.append((date_val, -val))
            elif tx_type in ('SELL', 'DIVIDEND') and not affect_cash:
                cashflows.append((date_val, val))
        
        all_cashflows.extend(cashflows)
        # Add current value
        cashflows.append((today_str, w['total']))
        cashflows.sort(key=lambda x: x[0])
        w['annualReturn'] = round(_xirr(cashflows), 4)

    # Summary XIRR
    all_cashflows.append((today_str, wallets['Summary']['total']))
    all_cashflows.sort(key=lambda x: x[0])
    wallets['Summary']['annualReturn'] = round(_xirr(all_cashflows), 4)

    wallet_holdings = {}
    for r in rows:
        wallet_holdings.setdefault(r['walletName'], []).append(r)
    if view == 'lite':
        rows_out = []
    elif view == 'history':
        return {
            'responseMode':   'history',
            'benchmarkId':    'WIG',
            'benchmarkName':  'WIG',
            'benchmarkData':  {'intraday': [], 'daily': [], 'weekly': [], 'monthly': [], 'hourly': []},
        }
    else:
        rows_out = rows
    return {
        'responseMode':         view,
        'updatedAt':            now,
        'walletSummaries':      wallets,
        'portfolioTotalValue':  total,
        'portfolioInvestedValue': invested,
        'portfolioDailyChangePLN': dailyPLN,
        'portfolioDailyChangePCT': dailyPct,
        'portfolioAth':         {'athValue': round(total * 1.06, 2), 'athDate': '2026-04-15'},
        'walletAths':           {wn: {'athValue': round(w['total'] * 1.06, 2), 'athDate': '2026-04-15'} for wn, w in wallets.items()},
        'walletPortfolioIds':   portfolio_ids,
        'walletHoldings':       wallet_holdings,
        'portfolioData':        rows_out,
        'benchmarkId':          'WIG',
        'benchmarkName':        'WIG',
        'benchmarkDailyPct':    0.42,
        'benchmarkData':        _fake_wig_data() if view != 'lite' else None,
        'benchmarkLivePrices': {
            'WIG': 92000.0,
            'WIG20': 2420.0,
            'MWIG40': 6410.0,
            'SWIG80': 25200.0,
            'SP500': 5320.0,
            'NASDAQ': 17100.0,
            'DAX': 18500.0,
            'MSCI_WORLD': 342.0
        } if view == 'full' else {},
        'marketCarousel':       [
            {'id': 'WIG', 'name': 'WIG', 'exchange': 'GPW', 'dailyPct': 0.42, 'sparkline': [{'t': 1, 'c': 92000.0}]},
            {'id': 'WIG20', 'name': 'WIG20', 'exchange': 'GPW', 'dailyPct': -0.15, 'sparkline': [{'t': 1, 'c': 2420.0}]},
            {'id': 'MWIG40', 'name': 'mWIG40', 'exchange': 'GPW', 'dailyPct': 0.85, 'sparkline': [{'t': 1, 'c': 6410.0}]},
            {'id': 'SWIG80', 'name': 'sWIG80', 'exchange': 'GPW', 'dailyPct': 1.20, 'sparkline': [{'t': 1, 'c': 25200.0}]},
            {'id': 'SP500', 'name': 'S&P 500', 'exchange': 'NYSE', 'dailyPct': 0.50, 'sparkline': [{'t': 1, 'c': 5320.0}]},
            {'id': 'NASDAQ', 'name': 'NASDAQ', 'exchange': 'NASDAQ', 'dailyPct': 0.90, 'sparkline': [{'t': 1, 'c': 17100.0}]},
            {'id': 'DAX', 'name': 'DAX', 'exchange': 'Xetra', 'dailyPct': -0.22, 'sparkline': [{'t': 1, 'c': 18500.0}]},
            {'id': 'MSCI_WORLD', 'name': 'MSCI World', 'exchange': 'Euronext', 'dailyPct': 0.35, 'sparkline': [{'t': 1, 'c': 342.0}]}
        ] if view == 'full' else [],
    }


def _build_mock_state():
    snaps_summary = _gen_snapshots('summary', start_value=22700, invested=18700)
    snaps_demo    = _gen_snapshots('demo',    start_value=14500, invested=11700)
    snaps_ike     = _gen_snapshots('ike',     start_value=8200,  invested=7000)
    ath_summary   = max(snaps_summary, key=lambda s: s['portfolioValue'])
    ath_demo      = max(snaps_demo,    key=lambda s: s['portfolioValue'])
    ath_ike       = max(snaps_ike,     key=lambda s: s['portfolioValue'])
    return {
        'user': {
            'userId':    'dev-user-localhost',
            'email':     'dev@localhost',
            'nickname':  'Dev User',
            'role':      'ADVANCED',
            'createdAt': '2020-01-01T00:00:00Z',
            'updatedAt': '2026-01-01T00:00:00Z',
            'settings':  {'theme': 'dark', 'currency': 'PLN'},
        },
        'portfolios': {
            'demo': {
                'portfolioId': 'demo', 'name': 'Demo Portfolio',
                'currency': 'PLN', 'color': '#4a9fd4', 'order': 0, 'type': 'real',
                'createdAt': '2026-01-15T10:00:00Z',
            },
            'ike': {
                'portfolioId': 'ike', 'name': 'IKE',
                'currency': 'PLN', 'color': '#6e56cf', 'order': 1, 'type': 'real',
                'createdAt': '2026-02-01T10:00:00Z',
            },
        },
        'holdings': {
            'demo': [
                {'holdingId': 'cdr', 'portfolioId': 'demo', 'name': 'CD Projekt',
                 'ticker': 'CDR.WA', 'currency': 'PLN', 'units': 10, 'purchaseValue': 1350.00},
                {'holdingId': 'xtb', 'portfolioId': 'demo', 'name': 'XTB',
                 'ticker': 'XTB.WA', 'currency': 'PLN', 'units': 25, 'purchaseValue': 3250.00},
                {'holdingId': 'cash', 'portfolioId': 'demo', 'name': 'Cash',
                 'ticker': None, 'currency': 'PLN', 'units': 1, 'purchaseValue': 5000.00},
            ],
            'ike': [
                {'holdingId': 'kghm', 'portfolioId': 'ike', 'name': 'KGHM',
                 'ticker': 'KGH.WA', 'currency': 'PLN', 'units': 20, 'purchaseValue': 3200.00},
                {'holdingId': 'cash-ike', 'portfolioId': 'ike', 'name': 'Cash IKE',
                 'ticker': None, 'currency': 'PLN', 'units': 1, 'purchaseValue': 1800.00},
            ],
        },
        'transactions': {
            'demo': [
                {'sk': 'PORTFOLIO#demo#TX#2026-01-15#dep-001', 'type': 'DEPOSIT',  'date': '2026-01-15', 'amount': 10000, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-01-16#buy-001', 'type': 'BUY',      'date': '2026-01-16', 'ticker': 'CDR.WA', 'name': 'CD Projekt', 'units': 10, 'pricePerUnit': 135, 'amount': 1350, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-02-03#buy-002', 'type': 'BUY',      'date': '2026-02-03', 'ticker': 'XTB.WA', 'name': 'XTB', 'units': 25, 'pricePerUnit': 130, 'amount': 3250, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-03-10#dep-002', 'type': 'DEPOSIT',  'date': '2026-03-10', 'amount': 1700, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-04-22#sell-001','type': 'SELL',     'date': '2026-04-22', 'ticker': 'CDR.WA', 'name': 'CD Projekt', 'units': 2, 'pricePerUnit': 148, 'amount': 296, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-05-05#dep-003', 'type': 'DEPOSIT',  'date': '2026-05-05', 'amount': 2000, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-05-12#buy-003', 'type': 'BUY',      'date': '2026-05-12', 'ticker': 'CDR.WA', 'name': 'CD Projekt', 'units': 5, 'pricePerUnit': 150, 'amount': 750, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-05-18#buy-004', 'type': 'BUY',      'date': '2026-05-18', 'ticker': 'XTB.WA', 'name': 'XTB', 'units': 10, 'pricePerUnit': 140, 'amount': 1400, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-05-28#sell-002','type': 'SELL',     'date': '2026-05-28', 'ticker': 'CDR.WA', 'name': 'CD Projekt', 'units': 3, 'pricePerUnit': 155, 'amount': 465, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-06-02#dep-004', 'type': 'DEPOSIT',  'date': '2026-06-02', 'amount': 1500, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-06-05#buy-005', 'type': 'BUY',      'date': '2026-06-05', 'ticker': 'XTB.WA', 'name': 'XTB', 'units': 15, 'pricePerUnit': 135, 'amount': 2025, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-06-08#sell-003','type': 'SELL',     'date': '2026-06-08', 'ticker': 'XTB.WA', 'name': 'XTB', 'units': 5, 'pricePerUnit': 142, 'amount': 710, 'currency': 'PLN', 'portfolioId': 'demo'},
                {'sk': 'PORTFOLIO#demo#TX#2026-06-10#buy-006', 'type': 'BUY',      'date': '2026-06-10', 'ticker': 'CDR.WA', 'name': 'CD Projekt', 'units': 8, 'pricePerUnit': 160, 'amount': 1280, 'currency': 'PLN', 'portfolioId': 'demo'},
            ],
            'ike': [
                {'sk': 'PORTFOLIO#ike#TX#2026-02-01#dep-001',  'type': 'DEPOSIT',  'date': '2026-02-01', 'amount': 5000, 'currency': 'PLN', 'portfolioId': 'ike'},
                {'sk': 'PORTFOLIO#ike#TX#2026-02-05#buy-001',  'type': 'BUY',      'date': '2026-02-05', 'ticker': 'KGH.WA', 'name': 'KGHM', 'units': 20, 'pricePerUnit': 160, 'amount': 3200, 'currency': 'PLN', 'portfolioId': 'ike'},
                {'sk': 'PORTFOLIO#ike#TX#2026-04-01#dep-002',  'type': 'DEPOSIT',  'date': '2026-04-01', 'amount': 2000, 'currency': 'PLN', 'portfolioId': 'ike'},
                {'sk': 'PORTFOLIO#ike#TX#2026-05-04#dep-003',  'type': 'DEPOSIT',  'date': '2026-05-04', 'amount': 1500, 'currency': 'PLN', 'portfolioId': 'ike'},
                {'sk': 'PORTFOLIO#ike#TX#2026-05-15#buy-002',  'type': 'BUY',      'date': '2026-05-15', 'ticker': 'KGH.WA', 'name': 'KGHM', 'units': 5, 'pricePerUnit': 165, 'amount': 825, 'currency': 'PLN', 'portfolioId': 'ike'},
                {'sk': 'PORTFOLIO#ike#TX#2026-06-03#dep-004',  'type': 'DEPOSIT',  'date': '2026-06-03', 'amount': 1000, 'currency': 'PLN', 'portfolioId': 'ike'},
                {'sk': 'PORTFOLIO#ike#TX#2026-06-09#buy-003',  'type': 'BUY',      'date': '2026-06-09', 'ticker': 'KGH.WA', 'name': 'KGHM', 'units': 10, 'pricePerUnit': 170, 'amount': 1700, 'currency': 'PLN', 'portfolioId': 'ike'},
            ],
        },
        'snapshots': {
            'summary': snaps_summary,
            'demo':    snaps_demo,
            'ike':     snaps_ike,
        },
        'ath': {
            'summary': {'portfolioId': 'summary', 'athValue': ath_summary['portfolioValue'], 'athDate': ath_summary['snapshotDate'], 'athSource': 'AUTO'},
            'demo':    {'portfolioId': 'demo',    'athValue': ath_demo['portfolioValue'],    'athDate': ath_demo['snapshotDate'],    'athSource': 'AUTO'},
            'ike':     {'portfolioId': 'ike',     'athValue': ath_ike['portfolioValue'],     'athDate': ath_ike['snapshotDate'],     'athSource': 'AUTO'},
        },
    }

_mock = _build_mock_state()


# ── Price update helpers ────────────────────────────────────────────────────

def run_price_update():
    global _last_update, _update_version
    with _update_lock:
        now = time.time()
        if now - _last_update < 30:
            print('  ⏭  Skipping update (ran less than 30s ago)')
            return
        _last_update = now

    print('\n🔄 Fetching live prices...')
    try:
        result = subprocess.run(
            [sys.executable, SCRIPT],
            cwd=os.path.dirname(SCRIPT),
            capture_output=True, text=True, timeout=120
        )
        for line in result.stdout.splitlines():
            if any(k in line for k in ['✓', 'ERROR', 'Gotówka']) or '→' in line:
                print(' ', line)
        if result.returncode != 0:
            print('  ⚠️  Update error:', result.stderr[:300])
        else:
            _update_version += 1
            print(f'  ✓ Update complete (v{_update_version})')
    except subprocess.TimeoutExpired:
        print('  ⚠️  Price update timed out after 120s')
    except Exception as e:
        print(f'  ⚠️  Error running update-prices.py: {e}')


def run_full_refresh():
    global _last_update, _update_version
    print('\n🔄 Running full refresh (update-all.sh)...')
    try:
        result = subprocess.run(
            ['bash', UPDATE_ALL],
            cwd=os.path.dirname(UPDATE_ALL),
            capture_output=True, text=True, timeout=180
        )
        _last_update = time.time()
        if result.returncode == 0:
            _update_version += 1
        lines = (result.stdout + result.stderr).splitlines()
        for line in lines:
            print(' ', line)
        return result.returncode == 0, lines
    except subprocess.TimeoutExpired:
        return False, ['Timed out after 180s']
    except Exception as e:
        return False, [str(e)]


# ── HTTP handler ────────────────────────────────────────────────────────────

def _json_resp(handler, data, status=200):
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', len(body))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Cache-Control', 'no-cache')
    handler.end_headers()
    handler.wfile.write(body)

def _read_body(handler):
    length = int(handler.headers.get('Content-Length', 0))
    if not length:
        return {}
    try:
        return json.loads(handler.rfile.read(length))
    except Exception:
        return {}

def _cors_headers(handler):
    handler.send_response(204)
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    handler.end_headers()


class InvestmentHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        # Prevent the browser from HTTP-caching any response in local dev so
        # edited JS/CSS files are always served fresh (no stale script errors).
        self.send_header('Cache-Control', 'no-cache, must-revalidate')
        super().end_headers()

    # ── routing helpers ─────────────────────────────────────────

    def _parsed(self):
        p = urlparse(self.path)
        return p.path, parse_qs(p.query)

    def _route_mock(self, method):
        """Returns True if a mock API route matched and was handled."""
        path, qs = self._parsed()

        # /prices?view=lite|full|history
        if path == '/prices':
            view = qs.get('view', ['full'])[0]
            _json_resp(self, _mock_prices(view))
            return True

        # /benchmark-returns
        if path == '/benchmark-returns':
            bm_id = qs.get('benchmarkId', ['WIG'])[0]
            
            import csv
            files = {
                "WIG":        "wig_m.csv",
                "WIG20":      "wig20_m.csv",
                "MWIG40":     "mwig40_m.csv",
                "SWIG80":     "swig80_m.csv",
                "MSCI_WORLD": "MSCI_m.csv",
                "NASDAQ":     "nasdaq.csv",
                "DAX":        "dax.csv",
                "SP500":      "sp500.csv",
            }
            fname = files.get(bm_id)
            returns = []
            if fname:
                csv_path = os.path.join(ROOT, 'data', fname)
                if os.path.exists(csv_path):
                    rows = []
                    with open(csv_path, newline="", encoding="utf-8") as fh:
                        reader = csv.DictReader(fh)
                        for row in reader:
                            date_str = row.get("Date", "").strip()
                            close_str = row.get("Close", "").strip()
                            if date_str and close_str:
                                try:
                                    close = float(close_str)
                                    ym = date_str[:7]
                                    if close > 0:
                                        rows.append((ym, close))
                                except ValueError:
                                    pass
                    rows.sort(key=lambda x: x[0])
                    for i in range(1, len(rows)):
                        prev_ym, prev_close = rows[i - 1]
                        curr_ym, curr_close = rows[i]
                        ret_pct = (curr_close - prev_close) / prev_close * 100
                        returns.append({
                            'month': curr_ym,
                            'returnPct': round(ret_pct, 4),
                            'closePrice': round(curr_close, 4)
                        })
                    returns.reverse()
            _json_resp(self, {'returns': returns})
            return True

        # /retirement-plans
        if path == '/retirement-plans':
            if method == 'GET':
                _json_resp(self, {'plans': _mock.get('retirement_plans', [])})
            elif method == 'PUT':
                body = _read_body(self)
                import uuid
                pid = body.get('planId') or str(uuid.uuid4())[:8]
                body['planId'] = pid
                result = {
                    'summary': {
                        'currentPortfolioValue': 14500.0,
                        'projectedCurrentPortfolioValue': 14500.0,
                        'retirementPortfolioValue': 350000.0,
                        'projectedRetirementPortfolioValue': 350000.0,
                        'finalPortfolioValue': 1200000.0,
                        'projectedFinalPortfolioValue': 1200000.0,
                        'monthsAfterRetirement': 360,
                        'lastsToTargetAge': True,
                        'targetAge': 88.6,
                        'depletionDate': None,
                        'targetDate': '2077-12-01',
                        'transitionDate': '2046-12-01',
                    },
                    'series': {
                        'actual': [],
                        'projected': [],
                    }
                }
                plan_entry = {
                    'plan': body,
                    'result': result,
                }
                if 'retirement_plans' not in _mock:
                    _mock['retirement_plans'] = []
                existing = [p for p in _mock['retirement_plans'] if p.get('planId') == pid]
                if existing:
                    idx = _mock['retirement_plans'].index(existing[0])
                    _mock['retirement_plans'][idx] = body
                else:
                    _mock['retirement_plans'].append(body)
                _json_resp(self, plan_entry)
            return True

        # /retirement-plans/{id}
        m = re.match(r'^/retirement-plans/([^/]+)$', path)
        if m:
            pid = m.group(1)
            if method == 'GET':
                plans = _mock.get('retirement_plans', [])
                plan = next((p for p in plans if p.get('planId') == pid), None)
                if plan:
                    result = {
                        'summary': {
                            'currentPortfolioValue': 14500.0,
                            'projectedCurrentPortfolioValue': 14500.0,
                            'retirementPortfolioValue': 350000.0,
                            'projectedRetirementPortfolioValue': 350000.0,
                            'finalPortfolioValue': 1200000.0,
                            'projectedFinalPortfolioValue': 1200000.0,
                            'monthsAfterRetirement': 360,
                            'lastsToTargetAge': True,
                            'targetAge': 88.6,
                            'depletionDate': None,
                            'targetDate': '2077-12-01',
                            'transitionDate': '2046-12-01',
                        },
                        'series': {
                            'actual': [],
                            'projected': [],
                        }
                    }
                    _json_resp(self, {'plan': plan, 'result': result})
                else:
                    _json_resp(self, {'error': 'not found'}, 404)
            elif method == 'DELETE':
                if 'retirement_plans' in _mock:
                    _mock['retirement_plans'] = [p for p in _mock['retirement_plans'] if p.get('planId') != pid]
                _json_resp(self, {'message': 'deleted'})
            return True

        # /retirement-plans/{id}/simulate
        m = re.match(r'^/retirement-plans/([^/]+)/simulate$', path)
        if m:
            pid = m.group(1)
            if method == 'POST':
                plans = _mock.get('retirement_plans', [])
                plan = next((p for p in plans if p.get('planId') == pid), None)
                if plan:
                    result = {
                        'summary': {
                            'currentPortfolioValue': 14500.0,
                            'projectedCurrentPortfolioValue': 14500.0,
                            'retirementPortfolioValue': 350000.0,
                            'projectedRetirementPortfolioValue': 350000.0,
                            'finalPortfolioValue': 1200000.0,
                            'projectedFinalPortfolioValue': 1200000.0,
                            'monthsAfterRetirement': 360,
                            'lastsToTargetAge': True,
                            'targetAge': 88.6,
                            'depletionDate': None,
                            'targetDate': '2077-12-01',
                            'transitionDate': '2046-12-01',
                        },
                        'series': {
                            'actual': [],
                            'projected': [],
                        }
                    }
                    _json_resp(self, {'plan': plan, 'result': result})
                else:
                    _json_resp(self, {'error': 'not found'}, 404)
            return True

        # /test-templates
        if path == '/test-templates':
            import os, json
            templates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lambda', 'roast_templates.json')
            feedback_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lambda', 'feedback.json')
            
            if method == 'GET':
                if os.path.exists(templates_path):
                    with open(templates_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    feedback_data = {}
                    if os.path.exists(feedback_path):
                        with open(feedback_path, 'r', encoding='utf-8') as f:
                            try:
                                feedback_data = json.load(f)
                            except:
                                pass
                                
                    # Merge feedback
                    for t in data:
                        tid = t.get('templateId')
                        msg = t.get('messageTemplate')
                        # Check by templateId or messageTemplate
                        if tid in feedback_data:
                            t['feedback'] = feedback_data[tid].get('action')
                        elif msg in feedback_data:
                            t['feedback'] = feedback_data[msg].get('action')

                    # Merge production telemetry counts (last 30 days)
                    try:
                        import sys
                        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lambda'))
                        os.environ["ROAST_EVENTS_TABLE"] = os.environ.get("ROAST_EVENTS_TABLE", "roastfolio-roast-events")
                        import roast_tracking
                        report = roast_tracking.get_template_report(days=30)
                        sc_stats = report.get("scenarios", {})
                        tmpl_stats = report.get("templates", {})
                        for t in data:
                            tid = t.get('templateId')
                            sc = t.get('scenarioKey')
                            t['prodPicks'] = tmpl_stats.get(tid, {}).get('displayCount', 0)
                            t['scenarioProdPicks'] = sc_stats.get(sc, {}).get('displayed', 0)
                    except Exception as tel_err:
                        pass
                            
                    _json_resp(self, data)
                else:
                    _json_resp(self, [], 404)
            elif method == 'POST':
                body = _read_body(self)
                template_id = body.get('templateId')
                message = body.get('messageTemplate')
                action = body.get('action') # 'stay' or 'remove'
                
                feedback_data = {}
                if os.path.exists(feedback_path):
                    with open(feedback_path, 'r', encoding='utf-8') as f:
                        try:
                            feedback_data = json.load(f)
                        except:
                            pass
                            
                # Key by messageTemplate to survive UUID regeneration
                key = message if message else template_id
                feedback_data[key] = {
                    'templateId': template_id,
                    'messageTemplate': message,
                    'action': action,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                with open(feedback_path, 'w', encoding='utf-8') as f:
                    json.dump(feedback_data, f, indent=2, ensure_ascii=False)
                    
                _json_resp(self, {'status': 'ok'})
            return True

        # /profile
        if path == '/profile':
            if method == 'GET':
                _json_resp(self, _mock['user'])
            elif method in ('PUT', 'PATCH'):
                body = _read_body(self)
                if 'nickname' in body:
                    _mock['user']['nickname'] = body['nickname']
                if 'settings' in body:
                    _mock['user']['settings'].update(body['settings'])
                _mock['user']['updatedAt'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                _json_resp(self, _mock['user'])
            elif method == 'DELETE':
                _json_resp(self, {'message': 'account deleted (mock)'})
            return True

        # /benchmarks
        if path == '/benchmarks':
            _json_resp(self, {'benchmarks': [
                {'id': 'WIG', 'name': 'WIG', 'ticker': 'WIG.WA', 'currency': 'PLN'},
                {'id': 'SP500', 'name': 'S&P 500', 'ticker': '^GSPC', 'currency': 'USD'},
            ]})
            return True

        # /search?q=
        if path == '/search':
            q = (qs.get('q', [''])[0] or '').lower()
            results = [
                {'symbol': 'CDR.WA',  'name': 'CD Projekt',     'exchange': 'WSE',    'type': 'Equity'},
                {'symbol': 'XTB.WA',  'name': 'XTB S.A.',       'exchange': 'WSE',    'type': 'Equity'},
                {'symbol': 'KGH.WA',  'name': 'KGHM',           'exchange': 'WSE',    'type': 'Equity'},
                {'symbol': 'PKN.WA',  'name': 'PKN Orlen',      'exchange': 'WSE',    'type': 'Equity'},
                {'symbol': 'AAPL',    'name': 'Apple Inc.',      'exchange': 'NASDAQ', 'type': 'Equity'},
                {'symbol': 'MSFT',    'name': 'Microsoft Corp.', 'exchange': 'NASDAQ', 'type': 'Equity'},
            ]
            filtered = [r for r in results if q in r['symbol'].lower() or q in r['name'].lower()] if q else results
            _json_resp(self, {'results': filtered})
            return True

        if path == '/asset-analysis':
            ticker = qs.get('ticker', ['AAPL'])[0]
            period = qs.get('period', ['1y'])[0]
            
            # Map period to days for fake data
            period_days = {"1d": 1, "1w": 7, "1m": 30, "ytd": 150, "1y": 250, "5y": 1250, "all": 2500}.get(period, 250)
            
            history = []
            base_price = 150.0
            import random
            from datetime import timedelta
            
            for i in range(period_days):
                d = datetime.now() - timedelta(days=period_days-i)
                base_price += random.uniform(-2, 2)
                history.append({"t": d.strftime("%Y-%m-%d"), "c": round(base_price, 2)})
                
            # Filter mock transactions for this ticker
            mock_txs = []
            for pid, txs in _mock.get('transactions', {}).items():
                for tx in txs:
                    if tx.get('ticker') == ticker:
                        mock_txs.append({
                            "date": tx.get("transactionDate", ""),
                            "type": tx.get("type"),
                            "units": float(tx.get("quantity") or 0),
                            "price": float(tx.get("price") or 0),
                            "portfolioId": pid
                        })
            mock_txs.sort(key=lambda x: x["date"])
                
            _json_resp(self, {
                "ticker": ticker,
                "fundamentals": {
                    "longName": ticker + " Mock Inc.",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                    "marketCap": 3000000000000,
                    "trailingPE": 25.4,
                    "forwardPE": 22.1,
                    "dividendYield": 0.015,
                    "fiftyTwoWeekHigh": 190.5,
                    "fiftyTwoWeekLow": 120.0
                },
                "history": history,
                "transactions": mock_txs
            })
            return True

        # /tfi/lookup?code=
        if path == '/tfi/lookup':
            code = (qs.get('code', [''])[0] or '').strip().upper()
            _MOCK_FUNDS = {
                'PCS21':  ('PKO Akcji Polskich',                  179.16, '20.05.2026'),
                'PKODLU': ('PKO Obligacji Długoterminowych',       212.45, '20.05.2026'),
                'PGS1':   ('Pekao Akcji Polskich',                  98.32, '20.05.2026'),
                'NNAPL':  ('NN Akcji',                             154.80, '20.05.2026'),
            }
            if code in _MOCK_FUNDS:
                name, nav, nav_date = _MOCK_FUNDS[code]
                _json_resp(self, {'code': code, 'name': name, 'nav': nav, 'navDate': nav_date})
            else:
                _json_resp(self, {'error': f'Fund code {code!r} not found on bankier.pl'}, 404)
            return True

        # /portfolios
        if path == '/portfolios':
            if method == 'GET':
                _json_resp(self, {'portfolios': list(_mock['portfolios'].values())})
            elif method == 'PUT':
                body = _read_body(self)
                pid = body.get('portfolioId') or body.get('name', 'new').lower().replace(' ', '-')
                _mock['portfolios'][pid] = {**body, 'portfolioId': pid, 'type': body.get('type', 'real')}
                _mock['holdings'].setdefault(pid, [])
                _mock['transactions'].setdefault(pid, [])
                _mock['snapshots'].setdefault(pid, [])
                _json_resp(self, _mock['portfolios'][pid])
            return True

        # /portfolios/{id}
        m = re.match(r'^/portfolios/([^/]+)$', path)
        if m:
            pid = m.group(1)
            if method == 'GET':
                p = _mock['portfolios'].get(pid)
                if not p:
                    _json_resp(self, {'error': 'not found'}, 404); return True
                _json_resp(self, {**p, 'holdings': _mock['holdings'].get(pid, [])})
            elif method == 'DELETE':
                _mock['portfolios'].pop(pid, None)
                _mock['holdings'].pop(pid, None)
                _mock['transactions'].pop(pid, None)
                _mock['snapshots'].pop(pid, None)
                _json_resp(self, {'message': 'deleted'})
            return True

        # /portfolios/{id}/holdings
        m = re.match(r'^/portfolios/([^/]+)/holdings$', path)
        if m:
            pid = m.group(1)
            if method == 'GET':
                _json_resp(self, {'holdings': _mock['holdings'].get(pid, [])})
            elif method == 'PUT':
                body = _read_body(self)
                holdings = body if isinstance(body, list) else body.get('holdings', [body])
                _mock['holdings'][pid] = holdings
                _json_resp(self, {'holdings': holdings})
            return True

        # /portfolios/{id}/holdings/{holdingId}
        m = re.match(r'^/portfolios/([^/]+)/holdings/([^/]+)$', path)
        if m:
            pid, hid = m.group(1), m.group(2)
            if method == 'DELETE':
                _mock['holdings'][pid] = [h for h in _mock['holdings'].get(pid, []) if h.get('holdingId') != hid]
                _json_resp(self, {'message': 'deleted'})
            return True

        # /portfolios/{id}/transactions
        m = re.match(r'^/portfolios/([^/]+)/transactions$', path)
        if m:
            pid = m.group(1)
            if method == 'GET':
                limit = int((qs.get('limit', [200])[0]))
                txs = _mock['transactions'].get(pid, [])
                _json_resp(self, {'transactions': txs[:limit]})
            elif method == 'POST':
                body = _read_body(self)
                import uuid
                body.setdefault('sk', f'PORTFOLIO#{pid}#TX#{body.get("date","2026-01-01")}#{uuid.uuid4().hex[:8]}')
                body['portfolioId'] = pid
                _mock['transactions'].setdefault(pid, []).insert(0, body)
                _json_resp(self, body, 201)
            return True

        # /portfolios/{id}/transactions/{txId}
        m = re.match(r'^/portfolios/([^/]+)/transactions/(.+)$', path)
        if m:
            pid, tx_id = m.group(1), m.group(2)
            if method == 'DELETE':
                _mock['transactions'][pid] = [t for t in _mock['transactions'].get(pid, []) if t.get('sk') != tx_id]
                _json_resp(self, {'message': 'deleted'})
            return True

        # /portfolios/{id}/snapshots
        m = re.match(r'^/portfolios/([^/]+)/snapshots$', path)
        if m:
            pid = m.group(1)
            if method == 'GET':
                limit = int(qs.get('limit', [365])[0])
                snaps = _mock['snapshots'].get(pid, [])
                _json_resp(self, {'snapshots': snaps[-limit:]})
            elif method == 'POST':
                body = _read_body(self)
                _mock['snapshots'].setdefault(pid, []).append(body)
                _json_resp(self, body, 201)
            return True

        # /portfolios/{id}/ath
        m = re.match(r'^/portfolios/([^/]+)/ath$', path)
        if m:
            pid = m.group(1)
            if method == 'GET':
                ath = _mock['ath'].get(pid)
                _json_resp(self, ath or {'error': 'not found'}, 200 if ath else 404)
            elif method == 'PUT':
                body = _read_body(self)
                _mock['ath'][pid] = {**_mock['ath'].get(pid, {}), **body, 'portfolioId': pid}
                _json_resp(self, _mock['ath'][pid])
            return True

        return False

    # ── HTTP verbs ──────────────────────────────────────────────

    def do_GET(self):
        path, _ = self._parsed()

        if path in ('/', '/index.html', ''):
            pass  # mock mode: prices served from /prices, no real update needed
        elif path == '/status':
            _json_resp(self, {'version': _update_version, 'updatedAt': _last_update})
            return
        elif path == '/scripts/config.js':
            # Serve a localhost mock config — makes apiUrl resolve so /profile,
            # /portfolios, and /prices all work without a real AWS deployment.
            # cognitoClientId is empty so auth-guard stays disabled.
            body = (
                'window.__CONFIG__ = {\n'
                f'  apiUrl:            "http://localhost:{PORT}/prices",\n'
                '  cognitoClientId:   "",\n'
                '  cognitoUserPoolId: "",\n'
                '  cognitoRegion:     "us-east-1"\n'
                '};\n'
            ).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', len(body))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(body)
            return
        elif path == '/service-worker.js':
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Service-Worker-Allowed', '/')
        elif path == '/manifest.json':
            manifest_path = os.path.join(ROOT, 'manifest.json')
            try:
                with open(manifest_path, 'rb') as _f:
                    body = _f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/manifest+json')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                self.send_error(404, 'manifest.json not found')
            return
        elif self._route_mock('GET'):
            return

        super().do_GET()

    def do_POST(self):
        path, _ = self._parsed()
        if path == '/refresh':
            success, lines = run_full_refresh()
            _json_resp(self, {'ok': success, 'log': lines}, 200 if success else 500)
        elif self._route_mock('POST'):
            pass
        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        if not self._route_mock('PUT'):
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        if not self._route_mock('DELETE'):
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        _cors_headers(self)

    def log_message(self, format, *args):
        if not args or not isinstance(args[0], str):
            return
        parts = args[0].split()
        method = parts[0] if len(parts) > 0 else ''
        path   = parts[1] if len(parts) > 1 else ''
        # Only log mutations — GET floods the terminal during normal page load
        if method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            if any(path.startswith(p) for p in ('/profile', '/portfolios', '/benchmarks', '/search', '/refresh', '/prices')):
                print(f'  [mock] {args[0]}')


def open_browser():
    time.sleep(1.0)
    webbrowser.open(f'http://localhost:{PORT}')


if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', PORT), InvestmentHandler) as httpd:
        print(f'🚀 Investment dashboard at http://localhost:{PORT}')
        print(f'   Mock API: /prices, /profile, /portfolios, /transactions, /snapshots')
        print(f'   POST /refresh → runs update-all.sh (optional, real data).')
        print(f'   Press Ctrl+C to stop.\n')
        Thread(target=open_browser, daemon=True).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\n✓ Server stopped.')

