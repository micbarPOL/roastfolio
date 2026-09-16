import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

os.environ.setdefault("AWS_REGION", "us-west-2")
os.environ.setdefault("DATA_TABLE", "roastfolio-data")
os.environ.setdefault("TRANSACTIONS_TABLE", "roastfolio-transactions")
os.environ.setdefault("SNAPSHOTS_TABLE", "roastfolio-snapshots")
os.environ.setdefault("USERS_TABLE", "roastfolio-users")

import wrap_generator  # noqa: E402
import trigger_recalc  # noqa: E402


def _snapshot(day, value, unit_price):
    return {
        "snapshotDate": day,
        "portfolioValue": Decimal(str(value)),
        "unitPrice": Decimal(str(unit_price)),
    }


def test_monthly_performance_isolates_cash_flow_and_uses_month_boundaries():
    rows = [
        _snapshot("2026-08-31", 950, 95),
        _snapshot("2026-09-01", 1000, 100),
        _snapshot("2026-09-30", 1290, 119),
        _snapshot("2026-10-01", 1300, 120),
    ]

    result = wrap_generator._monthly_performance(
        rows, date(2026, 9, 1), date(2026, 10, 1), Decimal("100")
    )

    assert result == {
        "start_value_pln": Decimal("1000.00"),
        "end_value_pln": Decimal("1300.00"),
        "twr_pct": Decimal("20.0000"),
        "nominal_change_pln": Decimal("200.00"),
    }


def test_cash_flow_sums_deposits_minus_withdrawals():
    transactions = [
        {"type": "DEPOSIT", "value": Decimal("500")},
        {"type": "WITHDRAWAL", "value": Decimal("125")},
        {"type": "BUY", "value": Decimal("300")},
    ]
    assert wrap_generator._cash_flow(transactions) == Decimal("375.00")
    assert wrap_generator._cash_flow_breakdown(transactions) == {
        "deposits_pln": Decimal("500.00"),
        "withdrawals_pln": Decimal("125.00"),
        "net_cash_flow_pln": Decimal("375.00"),
    }


def test_extremes_tracks_ath_drawdown_trajectory_and_daily_moves():
    rows = [
        _snapshot("2026-08-31", 1100, 110),
        _snapshot("2026-09-01", 1000, 100),
        _snapshot("2026-09-02", 1200, 110),
        _snapshot("2026-09-10", 900, 90),
        _snapshot("2026-09-20", 1400, 125),
    ]
    transactions = [{"type": "DEPOSIT", "value": 100, "transactionDate": "2026-09-02"}]

    result = wrap_generator._extremes(
        rows, transactions, date(2026, 9, 1), date(2026, 10, 1), date(2026, 9, 30)
    )

    assert result["is_new_ath"] is True
    assert result["ath_date"] == "2026-09-20"
    assert result["ath_value_pln"] == Decimal("1400.00")
    assert result["days_since_ath"] == 10
    assert result["max_drawdown_date"] == "2026-09-10"
    assert result["max_drawdown_pct"] == Decimal("-18.1818")
    assert result["start_drawdown_pct"] == Decimal("-9.0909")
    assert result["end_drawdown_pct"] == Decimal("0.0000")
    assert result["trajectory_delta_pp"] == Decimal("9.0909")
    assert result["drawdown_trajectory_pct"] == [
        Decimal("-9.0909"),
        Decimal("0.0000"),
        Decimal("-18.1818"),
        Decimal("0.0000"),
    ]
    assert result["best_day"] == {"date": "2026-09-20", "change_pln": Decimal("500.00")}
    assert result["worst_day"] == {"date": "2026-09-10", "change_pln": Decimal("-300.00")}


def test_seasonality_compares_prior_same_calendar_months():
    rows = [
        _snapshot("2024-09-01", 1000, 100),
        _snapshot("2024-10-01", 900, 90),
        _snapshot("2025-09-01", 1000, 100),
        _snapshot("2025-10-01", 1100, 110),
    ]

    result = wrap_generator._seasonality(rows, 2026, 9, Decimal("5"))

    assert result["historical_years_count"] == 2
    assert result["negative_years_count"] == 1
    assert result["positive_years_count"] == 1
    assert result["avg_negative_pct"] == Decimal("-10.0000")
    assert result["avg_positive_pct"] == Decimal("10.0000")
    assert result["historical_average_pct"] == Decimal("0.0000")
    assert result["outperformed_seasonal_history"] is True


def test_retirement_target_uses_primary_active_plan(monkeypatch):
    monkeypatch.setattr(
        wrap_generator.retirement_plans,
        "list_plans",
        lambda _user_id: [
            {"planId": "secondary", "monthlyInvestment": 500},
            {"planId": "primary", "monthlyInvestment": 1000, "isPrimary": True},
        ],
    )

    result = wrap_generator._retirement_target("user-1", Decimal("750"))

    assert result["plan_id"] == "primary"
    assert result["monthly_target_nominal_pln"] == Decimal("1000.00")
    assert result["actual_nominal_gain_pln"] == Decimal("750.00")
    assert result["pct_achieved"] == Decimal("75.0000")


def test_avco_reports_month_realized_delta_and_active_unrealized(monkeypatch):
    ledger = {
        "wallet": [
            {"type": "BUY", "ticker": "AAA", "holdingId": "aaa", "quantity": 10, "price": 10, "value": 100, "transactionDate": "2026-08-01"},
            {"type": "SELL", "ticker": "AAA", "holdingId": "aaa", "quantity": 5, "price": 15, "value": 75, "transactionDate": "2026-09-10"},
        ]
    }
    monkeypatch.setattr(
        wrap_generator.portfolio_avco,
        "load_portfolio_avco",
        lambda *_args: {"active": [{"unrealized_return": Decimal("30")}], "closed": []},
    )

    result = wrap_generator._avco_gains("user-1", ledger, date(2026, 9, 1), date(2026, 10, 1))

    assert result == {"realized_pln": Decimal("25.00"), "unrealized_pln": Decimal("30.00")}


def test_asset_contribution_selects_carry_anchor_and_trade_context(monkeypatch):
    monkeypatch.setattr(
        wrap_generator,
        "_asset_values_at_boundaries",
        lambda *_args: (
            {"AAA": Decimal("100"), "BBB": Decimal("100")},
            {"AAA": Decimal("150"), "BBB": Decimal("80")},
            {"AAA": "Alpha", "BBB": "Beta"},
        ),
    )
    ledgers = {
        "wallet": [
            {"type": "BUY", "ticker": "AAA", "name": "Alpha", "value": 20, "transactionDate": "2026-09-05"}
        ]
    }

    result = wrap_generator._asset_contributions(
        "user-1", ledgers, date(2026, 9, 1), date(2026, 10, 1)
    )

    assert result["carry"]["ticker"] == "AAA"
    assert result["carry"]["net_contribution_pln"] == Decimal("30.00")
    assert result["carry"]["context_note"] == "Price move + bought 20 PLN"
    assert result["anchor"]["ticker"] == "BBB"
    assert result["anchor"]["net_contribution_pln"] == Decimal("-20.00")
    assert result["anchor"]["context_note"] == "Pure price movement, no trades"


def test_diary_audit_counts_activity_average_and_maturing_checkpoints(monkeypatch):
    notes = [
        {"updatedAt": "2026-09-05", "hypothesis_checkpoints": [
            {"due_date": "2026-09-10", "status": "TRUE"},
            {"due_date": "2026-09-20", "status": "FALSE"},
            {"due_date": "2026-09-25", "status": "PENDING"},
        ]},
        {"createdAt": "2026-09-12", "updatedAt": "2026-10-02"},
        {"updatedAt": "2026-08-05"},
        {"updatedAt": "2026-08-15"},
        {"updatedAt": "2026-07-05"},
        {"updatedAt": "2026-07-15"},
        {"updatedAt": "2026-06-05"},
        {"updatedAt": "2026-06-15"},
    ]
    monkeypatch.setattr(wrap_generator.diary_handler, "list_notes", lambda *_args, **_kwargs: notes)

    result = wrap_generator._diary_audit(
        "user-1", date(2026, 9, 1), date(2026, 10, 1), date(2026, 9, 30)
    )

    assert result["current_month_entries"] == 2
    assert result["three_month_avg_entries"] == Decimal("2.0000")
    assert result["activity_dropped_warning"] is False
    assert result["checkpoints_true"] == 1
    assert result["checkpoints_false"] == 1
    assert result["checkpoints_overdue"] == 1


def test_generate_monthly_wrap_persists_exact_single_table_keys_and_wallet_split(monkeypatch):
    summary = [_snapshot("2026-09-01", 1000, 100), _snapshot("2026-10-01", 1200, 120)]
    wallet_a = [_snapshot("2026-09-01", 600, 100), _snapshot("2026-10-01", 650, 130)]
    wallet_b = [_snapshot("2026-09-01", 400, 100), _snapshot("2026-10-01", 550, 110)]
    monkeypatch.setattr(
        wrap_generator.portfolios,
        "list_portfolios",
        lambda _user_id: [{"portfolioId": "a", "name": "A"}, {"portfolioId": "b", "name": "B"}],
    )
    ledgers = {
        "a": [{"type": "DEPOSIT", "value": 20, "transactionDate": "2026-09-10"}],
        "b": [{"type": "DEPOSIT", "value": 30, "transactionDate": "2026-09-10"}],
    }
    monkeypatch.setattr(
        wrap_generator.portfolios,
        "list_all_transactions",
        lambda _user_id, portfolio_id, **_kwargs: ledgers[portfolio_id],
    )
    monkeypatch.setattr(
        wrap_generator.snapshots,
        "list_snapshots",
        lambda _user_id, portfolio_id, **_kwargs: {"summary": summary, "a": wallet_a, "b": wallet_b}[portfolio_id],
    )
    monkeypatch.setattr(wrap_generator, "_extremes", lambda *_args: {})
    monkeypatch.setattr(wrap_generator, "_seasonality", lambda *_args: {})
    monkeypatch.setattr(wrap_generator, "_retirement_target", lambda *_args: {})
    monkeypatch.setattr(wrap_generator, "_avco_gains", lambda *_args: {})
    monkeypatch.setattr(wrap_generator, "_asset_contributions", lambda *_args: {"carry": None, "anchor": None})
    monkeypatch.setattr(wrap_generator, "_diary_audit", lambda *_args: {})
    monkeypatch.setattr(wrap_generator.db, "get_user", lambda _user: {"settings": {"benchmark": "SP500"}})
    monkeypatch.setattr(wrap_generator, "_benchmark_daily", lambda *_args: {
        "2026-08-31": Decimal("90"), "2026-09-01": Decimal("100"),
        "2026-09-30": Decimal("105"), "2026-10-01": Decimal("110"),
    })

    writes = []
    monkeypatch.setattr(wrap_generator, "_wrap_table", lambda: type("Table", (), {"put_item": lambda _self, **kwargs: writes.append(kwargs["Item"])})())

    result = wrap_generator.generate_monthly_wrap("user-42", 2026, 9)

    assert result["PK"] == "USER#user-42"
    assert result["SK"] == "WRAP#MONTH#2026-09"
    assert result["cash_flow_pln"] == Decimal("50.00")
    assert result["deposits_pln"] == Decimal("50.00")
    assert result["withdrawals_pln"] == Decimal("0.00")
    assert result["overall_twr_pct"] == Decimal("20.0000")
    assert result["journey"]["points"][-1]["portfolio_pct"] == result["overall_twr_pct"]
    assert result["journey"]["benchmark_id"] == "SP500"
    assert result["journey"]["benchmark_return_pct"] == Decimal("10.0000")
    assert [row["id"] for row in result["market_context"]] == list(wrap_generator.MARKET_CONTEXT_IDS)
    assert result["trading_activity"]["turnover_pln"] == 0
    assert result["overall_nominal_change_pln"] == Decimal("150.00")
    assert result["best_efficiency_wallet"]["portfolio_id"] == "a"
    assert result["primary_profit_engine_wallet"]["portfolio_id"] == "b"
    assert writes == [result]


def test_monthly_sweep_generates_preceding_month_only_on_day_one(monkeypatch):
    calls = []
    monkeypatch.setattr(
        trigger_recalc.wrap_generator,
        "generate_monthly_wrap",
        lambda user_id, year, month: calls.append((user_id, year, month)) or {"period": f"{year:04d}-{month:02d}"},
    )

    skipped = trigger_recalc.generate_previous_month_wraps(
        datetime(2026, 10, 2, tzinfo=timezone.utc), user_ids=["user-1"]
    )
    generated = trigger_recalc.generate_previous_month_wraps(
        datetime(2026, 10, 1, tzinfo=timezone.utc), user_ids=["user-1", "user-2"]
    )

    assert skipped == []
    assert calls == [("user-1", 2026, 9), ("user-2", 2026, 9)]
    assert generated == [
        {"userId": "user-1", "period": "2026-09", "status": "ok"},
        {"userId": "user-2", "period": "2026-09", "status": "ok"},
    ]