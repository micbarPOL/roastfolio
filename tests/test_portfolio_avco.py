import os
import sys
from decimal import Decimal

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lambda"))
from portfolio_avco import PortfolioAVCOCalculator


def tx(tx_type, date, ticker="ABC", quantity=0, price=None, value=0, **extra):
    return {
        "type": tx_type,
        "transactionDate": date,
        "ticker": ticker,
        "holdingId": ticker.lower(),
        "name": ticker,
        "quantity": quantity,
        "price": price,
        "value": value,
        **extra,
    }


def position(result, ticker="ABC"):
    return next(row for row in result["positions"] if row["ticker"] == ticker)


def test_weighted_avco_sell_realized_and_dividend_total_return():
    result = PortfolioAVCOCalculator(current_prices={"ABC": 25}).calculate([
        tx("BUY", "2026-01-01", quantity=10, price=10, value=100),
        tx("BUY", "2026-02-01", quantity=10, price=20, value=200),
        tx("SELL", "2026-03-01", quantity=5, price=18, value=90),
        tx("DIVIDEND", "2026-04-01", value=12),
    ])

    row = position(result)
    assert row["status"] == "ACTIVE"
    assert row["shares"] == Decimal("15")
    assert row["avco"] == Decimal("15")
    assert row["realized_return"] == Decimal("15")
    assert row["unrealized_return"] == Decimal("150")
    assert row["dividends_received"] == Decimal("12")
    assert row["total_return"] == Decimal("177")


def test_full_close_then_rebuy_resets_avco():
    result = PortfolioAVCOCalculator(current_prices={"ABC": 45}).calculate([
        tx("BUY", "2026-01-01", quantity=10, price=10, value=100),
        tx("SELL", "2026-02-01", quantity=10, price=12, value=120),
        tx("BUY", "2026-04-01", quantity=3, price=40, value=120),
    ])

    row = position(result)
    assert row["status"] == "ACTIVE"
    assert row["shares"] == Decimal("3")
    assert row["avco"] == Decimal("40")
    assert row["realized_return"] == Decimal("20")
    assert row["unrealized_return"] == Decimal("15")


def test_holding_id_keeps_position_together_after_ticker_correction():
    result = PortfolioAVCOCalculator(current_prices={"ABC.NEW": 30}).calculate([
        tx("BUY", "2026-01-01", ticker="ABC", quantity=2, price=10, value=20),
        tx("BUY", "2026-02-01", ticker="ABC.NEW", quantity=2, price=20, value=40, holdingId="abc"),
    ])

    row = position(result, "ABC.NEW")
    assert len(result["positions"]) == 1
    assert row["holding_id"] == "abc"
    assert row["shares"] == Decimal("4")
    assert row["avco"] == Decimal("15")


def test_closed_position_and_ignored_cash_or_unverified_events():
    result = PortfolioAVCOCalculator().calculate([
        tx("DEPOSIT", "2026-01-01", ticker="", value=1000),
        tx("BUY", "2026-01-02", quantity=4, price=25, value=100),
        tx("SELL", "2026-02-02", quantity=4, price=20, value=80),
        tx("BUY", "2026-03-01", ticker="IGN", quantity=1, price=10, value=10, verified=False),
        tx("EXTRA_COST", "2026-03-02", ticker="", value=5),
    ])

    row = position(result)
    assert row["status"] == "CLOSED"
    assert row["shares"] == 0
    assert row["avco"] == 0
    assert row["realized_return"] == Decimal("-20")
    assert len(result["positions"]) == 1


def test_spinoff_uses_weighted_average_cost():
    row = position(PortfolioAVCOCalculator().calculate([
        tx("BUY", "2026-01-01", quantity=10, price=10, value=100),
        tx("SPINOFF", "2026-02-01", quantity=2, price=0, value=0),
    ]))
    assert row["shares"] == Decimal("12")
    assert row["avco"] == Decimal("100") / Decimal("12")


def test_wash_sale_badge_for_loss_rebuy_within_30_days():
    row = position(PortfolioAVCOCalculator(current_prices={"ABC": 9}).calculate([
        tx("BUY", "2026-01-01", quantity=10, price=10, value=100),
        tx("SELL", "2026-02-01", quantity=10, price=8, value=80),
        tx("BUY", "2026-02-20", quantity=5, price=9, value=45),
    ]))
    assert row["gamification"]["badges"]["wash_sale_violator"] is True
    assert row["gamification"]["metadata"]["wash_sale_violator"]["days_between"] == 19


def test_paper_hands_fomo_badge_after_minor_gain_and_market_rally():
    row = position(PortfolioAVCOCalculator(current_prices={"ABC": 140}).calculate([
        tx("BUY", "2026-01-01", quantity=10, price=100, value=1000),
        tx("SELL", "2026-02-01", quantity=10, price=104, value=1040),
    ]))
    assert row["gamification"]["badges"]["paper_hands_fomo"] is True
    assert row["gamification"]["metadata"]["paper_hands_fomo"]["closure_return_pct"] == Decimal("4.00")


def test_clown_bagholder_badge_for_dust_after_major_loss_sale():
    row = position(PortfolioAVCOCalculator(
        current_prices={"ABC": 1},
        current_values={"ABC": 1},
    ).calculate([
        tx("BUY", "2026-01-01", quantity=100, price=5, value=500),
        tx("SELL", "2026-02-01", quantity=99, price=1, value=99),
    ]))
    assert row["status"] == "ACTIVE"
    assert row["gamification"]["badges"]["clown_bagholder"] is True


def test_oversell_is_rejected():
    with pytest.raises(ValueError, match="exceeds active shares"):
        PortfolioAVCOCalculator().calculate([
            tx("BUY", "2026-01-01", quantity=1, price=10, value=10),
            tx("SELL", "2026-02-01", quantity=2, price=12, value=24),
        ])