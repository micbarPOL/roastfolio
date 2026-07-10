import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from intraday_classifier import hasMeaningfulChangeSinceLastRoast

def test_no_meaningful_change():
    current = {
        "totalPortfolioValue": 10000,
        "dailyChangePct": 1.0,
        "benchmark_return": 0.5,
        "isAth": False,
        "topAsset": "AAPL",
        "worstAsset": "TSLA",
        "drawdownPct": 5.0
    }
    last = {
        "totalPortfolioValue": 10000,
        "portfolioReturnPercent": 1.0,
        "benchmarkReturnPercent": 0.5,
        "isNewATH": False,
        "dailyBestAsset": "AAPL",
        "dailyWorstAsset": "TSLA",
        "currentDrawdownFromATH": 5.0
    }
    assert not hasMeaningfulChangeSinceLastRoast(current, last)

def test_meaningful_portfolio_value_change():
    current = {"totalPortfolioValue": 10100} # 1% change
    last = {"totalPortfolioValue": 10000}
    assert hasMeaningfulChangeSinceLastRoast(current, last)

def test_small_portfolio_value_change():
    current = {"totalPortfolioValue": 10005} # 0.05% change
    last = {"totalPortfolioValue": 10000}
    assert not hasMeaningfulChangeSinceLastRoast(current, last)

def test_meaningful_benchmark_change():
    current = {"benchmark_return": 1.0}
    last = {"benchmarkReturnPercent": 1.15} # 0.15 diff
    assert hasMeaningfulChangeSinceLastRoast(current, last)

def test_meaningful_asset_change():
    current = {"topAsset": "MSFT"}
    last = {"dailyBestAsset": "AAPL"}
    assert hasMeaningfulChangeSinceLastRoast(current, last)

def test_meaningful_ath_change():
    current = {"isAth": True}
    last = {"isNewATH": False}
    assert hasMeaningfulChangeSinceLastRoast(current, last)

def test_meaningful_drawdown_change():
    current = {"drawdownPct": 6.5}
    last = {"currentDrawdownFromATH": 5.0} # 1.5 diff
    assert hasMeaningfulChangeSinceLastRoast(current, last)
