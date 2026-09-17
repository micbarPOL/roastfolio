import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))

import email_service


def test_get_recipient_emails():
    profile = {
        "userId": "user-1",
        "email": "Primary@example.com ",
        "settings": {
            "notificationEmails": [
                "secondary@example.com",
                "PRIMARY@example.com",  # duplicate
                "  third@work.co ",
                "invalid-email-address",
                "",
                None,
            ]
        }
    }

    recipients = email_service.get_recipient_emails(profile)
    assert recipients == ["primary@example.com", "secondary@example.com", "third@work.co"]

    without_primary = email_service.get_recipient_emails(profile, include_default=False)
    assert without_primary == ["secondary@example.com", "third@work.co"]


def test_render_monthly_recap_email_positive_return():
    profile = {
        "userId": "user-1",
        "email": "investor@example.com",
        "nickname": "Michał",
    }
    wrap = {
        "period": "2026-08",
        "overall_twr_pct": 4.25,
        "overall_nominal_change_pln": 12500,
        "cash_flow_pln": 3000,
        "deposits_pln": 5000,
        "withdrawals_pln": 2000,
        "max_drawdown_pct": -1.8,
        "benchmark_id": "WIG",
        "benchmark_return_pct": 2.1,
        "best_efficiency_wallet": {"name": "Emerytura", "twr_pct": 5.1},
        "primary_profit_engine_wallet": {"name": "Emerytura", "nominal_change_pln": 9500},
    }

    subject, text_body, html_body = email_service.render_monthly_recap_email(profile, wrap)

    assert "August 2026" in subject
    assert "+4.25%" in subject
    assert "Michał" in text_body
    assert "A little more momentum." in text_body
    assert "+4.25%" in text_body
    assert "12 500 PLN" in text_body
    assert "#4ade80" in html_body  # Positive emerald color
    assert "Emerytura" in html_body
    assert "roastfolio" in html_body


def test_render_monthly_recap_email_negative_return():
    profile = {
        "userId": "user-2",
        "email": "trader@example.com",
    }
    wrap = {
        "period": "2026-07",
        "overall_twr_pct": -3.5,
        "overall_nominal_change_pln": -8200,
        "cash_flow_pln": 0,
        "deposits_pln": 0,
        "withdrawals_pln": 0,
        "max_drawdown_pct": -5.2,
        "benchmark_id": "SP500",
        "benchmark_return_pct": -1.2,
    }

    subject, text_body, html_body = email_service.render_monthly_recap_email(profile, wrap)

    assert "July 2026" in subject
    assert "-3.50%" in subject
    assert "A step back. The story continues." in text_body
    assert "#f87171" in html_body  # Negative red color


def test_send_monthly_recap_email_success():
    profile = {"userId": "user-1", "email": "test@example.com"}
    wrap = {"period": "2026-08", "overall_twr_pct": 2.0}

    mock_ses = MagicMock()
    mock_ses.send_email.return_value = {"MessageId": "msg-12345"}

    res = email_service.send_monthly_recap_email(
        profile, wrap, recipients=["test@example.com"], ses_client=mock_ses
    )

    assert res["success"] is True
    assert res["message_id"] == "msg-12345"
    assert res["recipients"] == ["test@example.com"]
    mock_ses.send_email.assert_called_once()
    call_kwargs = mock_ses.send_email.call_args[1]
    assert call_kwargs["Destination"]["ToAddresses"] == ["test@example.com"]


def test_send_monthly_recap_email_handles_ses_client_error():
    profile = {"userId": "user-1", "email": "test@example.com"}
    wrap = {"period": "2026-08", "overall_twr_pct": 2.0}

    mock_ses = MagicMock()
    mock_ses.send_email.side_effect = ClientError(
        {"Error": {"Code": "MessageRejected", "Message": "Email address is not verified"}},
        "SendEmail",
    )

    res = email_service.send_monthly_recap_email(
        profile, wrap, recipients=["test@example.com"], ses_client=mock_ses
    )

    assert res["success"] is False
    assert res["unverified"] is True
    assert "Email address is not verified" in res["error"]


def test_send_monthly_recap_email_if_enabled():
    profile_disabled = {
        "userId": "user-1",
        "email": "disabled@example.com",
        "settings": {"emailNotifications": False, "notifications": False},
    }
    profile_enabled = {
        "userId": "user-2",
        "email": "enabled@example.com",
        "settings": {"emailNotifications": True},
    }
    wrap = {"period": "2026-08", "overall_twr_pct": 1.5}

    mock_ses = MagicMock()
    mock_ses.send_email.return_value = {"MessageId": "msg-ok"}

    # Should skip when disabled
    res_disabled = email_service.send_monthly_recap_email_if_enabled(
        profile_disabled, wrap, ses_client=mock_ses
    )
    assert res_disabled["success"] is False
    assert res_disabled.get("skipped") is True
    mock_ses.send_email.assert_not_called()

    # Should send when enabled
    res_enabled = email_service.send_monthly_recap_email_if_enabled(
        profile_enabled, wrap, ses_client=mock_ses
    )
    assert res_enabled["success"] is True
    assert res_enabled["message_id"] == "msg-ok"
    mock_ses.send_email.assert_called_once()


def test_render_monthly_recap_email_benchmark_resolution_from_journey_and_market_context():
    profile = {"userId": "user-1", "email": "test@example.com"}
    # Wrap without top-level benchmark_return_pct, but with journey.benchmark_return_pct
    wrap_with_journey = {
        "period": "2026-08",
        "journey": {
            "benchmark_id": "WIG",
            "benchmark_return_pct": 2.9465,
        },
    }
    subject, text_body, html_body = email_service.render_monthly_recap_email(profile, wrap_with_journey)
    assert "Benchmark (WIG):           +2.95%" in text_body
    assert "+2.95%" in html_body

    # Wrap where benchmark is in market_context
    wrap_with_market_context = {
        "period": "2026-08",
        "benchmark_id": "SP500",
        "market_context": [
            {"id": "WIG", "name": "WIG Index", "return_pct": 1.5},
            {"id": "SP500", "name": "S&P 500", "return_pct": -0.85},
        ],
    }
    subject2, text_body2, html_body2 = email_service.render_monthly_recap_email(profile, wrap_with_market_context)
    assert "Benchmark (SP500):" in text_body2
    assert "-0.85%" in text_body2
    assert "-0.85%" in html_body2


def test_render_monthly_recap_email_hide_cash_explicit_and_settings():
    profile_with_settings = {
        "userId": "user-1",
        "email": "test@example.com",
        "settings": {"hideCashInNotifications": True},
    }
    wrap = {
        "period": "2026-08",
        "overall_twr_pct": 3.2,
        "overall_nominal_change_pln": 5400,
        "cash_flow_pln": 0,
        "deposits_pln": 0,
        "withdrawals_pln": 0,
        "primary_profit_engine_wallet": {"name": "Główny", "nominal_change_pln": 5400},
    }

    # Hide cash derived from profile settings
    _, text_body, html_body = email_service.render_monthly_recap_email(profile_with_settings, wrap)
    assert "• Nominal Change:              --- (amounts hidden)" in text_body
    assert "• Net Cash Flow:               --- (amounts hidden)" in text_body
    assert "Primary Profit Engine:       Główny (---)" in text_body
    assert "5 400 PLN" not in text_body
    assert "5 400 PLN" not in html_body
    assert "privacy mode" in html_body

    # Explicit override hide_cash=False overrules settings
    _, text_body2, html_body2 = email_service.render_monthly_recap_email(profile_with_settings, wrap, hide_cash=False)
    assert "+5 400 PLN" in text_body2
    assert "+5 400 PLN" in html_body2
    assert "privacy mode" not in html_body2

    # Explicit override hide_cash=True when setting is False
    profile_default = {"userId": "user-1", "email": "test@example.com", "settings": {"hideCashInNotifications": False}}
    _, text_body3, html_body3 = email_service.render_monthly_recap_email(profile_default, wrap, hide_cash=True)
    assert "• Nominal Change:              --- (amounts hidden)" in text_body3
    assert "privacy mode" in html_body3


def test_render_monthly_recap_email_svg_journey_chart():
    profile = {"userId": "user-1", "email": "test@example.com"}
    wrap = {
        "period": "2026-08",
        "benchmark_id": "WIG",
        "journey": {
            "benchmark_id": "WIG",
            "points": [
                {"date": "2026-08-01", "portfolio_pct": 0.0, "benchmark_pct": 0.0},
                {"date": "2026-08-10", "portfolio_pct": 2.5, "benchmark_pct": 1.2},
                {"date": "2026-08-20", "portfolio_pct": 1.8, "benchmark_pct": 2.1},
                {"date": "2026-08-31", "portfolio_pct": 4.5, "benchmark_pct": 2.8},
            ],
        },
    }

    _, text_body, html_body = email_service.render_monthly_recap_email(profile, wrap)
    assert "<svg" in html_body
    assert "<polygon" in html_body
    assert "<!--[if !mso]><!-->" in html_body
    assert "<!--[if mso]>" in html_body
    assert "CUMULATIVE JOURNEY" in html_body
    assert "BEAT BENCHMARK BY +1.70%" in html_body
    assert "+4.50%" in html_body
    assert "+2.80%" in html_body
    assert "Beat benchmark by +1.70%" in text_body


def test_render_monthly_recap_email_calendar_heatmap():
    profile = {"userId": "user-1", "email": "test@example.com"}
    wrap = {
        "period": "2026-08",
        "daily_moves": [
            {"date": "2026-08-03", "change_pct": 1.25, "is_ath": False},
            {"date": "2026-08-04", "change_pct": -0.85, "is_ath": False},
            {"date": "2026-08-05", "change_pct": 2.10, "is_ath": True},
        ],
    }

    _, text_body, html_body = email_service.render_monthly_recap_email(profile, wrap)
    assert "DAILY CALENDAR HEATMAP" in html_body
    assert "+1.2%" in html_body
    assert "-0.8%" in html_body  # round half-to-even in Python float formatting
    assert "+2.1%" in html_body
    assert "#f59e0b" in html_body  # ATH highlight border
    assert "Best day:" in html_body
    assert "08-05 (+2.10%)" in html_body
    assert "Worst day:" in html_body
    assert "08-04 (-0.85%)" in html_body
    assert "Best day 08-05 (+2.10%)" in text_body
    assert "Worst day 08-04 (-0.85%)" in text_body


def test_render_monthly_recap_email_leader_and_anchor():
    profile = {"userId": "user-1", "email": "test@example.com"}
    wrap = {
        "period": "2026-08",
        "carry": {
            "ticker": "CDR.WA",
            "name": "CD Projekt",
            "net_contribution_pln": 3240,
            "context_note": "Pure price move",
        },
        "anchor": {
            "ticker": "TSGAMES.WA",
            "name": "Ten Square Games",
            "net_contribution_pln": -1890,
            "context_note": "Sold 2,500 PLN",
        },
    }

    _, text_body, html_body = email_service.render_monthly_recap_email(profile, wrap)
    assert "WHO MOVED YOUR MONTH" in html_body
    assert "MONTH LEADER" in html_body
    assert "CDR.WA" in html_body
    assert "+3 240 PLN" in html_body
    assert "Pure price move" in html_body
    assert "MONTH ANCHOR" in html_body
    assert "TSGAMES.WA" in html_body
    assert "-1 890 PLN" in html_body
    assert "Sold 2,500 PLN" in html_body
    assert "Month Leader: CDR.WA (+3 240 PLN) - Pure price move" in text_body
    assert "Month Anchor: TSGAMES.WA (-1 890 PLN) - Sold 2,500 PLN" in text_body


def test_render_monthly_recap_email_market_context_and_seasonality():
    profile = {"userId": "user-1", "email": "test@example.com"}
    wrap = {
        "period": "2026-09",
        "market_context": [
            {"id": "WIG", "name": "WIG", "return_pct": 3.22},
            {"id": "DAX", "name": "DAX", "return_pct": 1.87},
            {"id": "SP500", "name": "S&P 500", "return_pct": 2.14},
            {"id": "NASDAQ", "name": "NASDAQ", "return_pct": 3.61},
            {"id": "FTSE100", "name": "FTSE 100", "return_pct": -0.42},
            {"id": "MSCI_WORLD", "name": "MSCI World", "return_pct": 2.14},
        ],
        "historical_years_count": 3,
        "negative_years_count": 1,
        "positive_years_count": 2,
        "avg_negative_pct": -1.2,
        "avg_positive_pct": 2.8,
        "outperformed_seasonal_history": True,
    }

    _, text_body, html_body = email_service.render_monthly_recap_email(profile, wrap)
    assert "WIG (Poland)" in html_body
    assert "+3.22%" in html_body
    assert "DAX (Germany)" in html_body
    assert "S&P 500 (US)" in html_body
    assert "MSCI World" in html_body
    assert "SEASONALITY &bull; SEPTEMBER" in html_body
    assert "September was negative in 1 of 3 observations" in html_body
    assert "Current result beat seasonal history" in html_body
    assert "Beat seasonal history" in text_body

    # Test seasonality omitted when historical_years_count <= 1
    wrap_no_seasonality = dict(wrap)
    wrap_no_seasonality["historical_years_count"] = 1
    _, text_body2, html_body2 = email_service.render_monthly_recap_email(profile, wrap_no_seasonality)
    assert "SEASONALITY" not in html_body2
    assert "Seasonality" not in text_body2


def test_render_monthly_recap_email_trading_activity_and_privacy():
    profile = {"userId": "user-1", "email": "test@example.com"}
    wrap = {
        "period": "2026-08",
        "trading_activity": {
            "turnover_pln": 45000,
            "avg_12m_turnover_pln": 30000,
            "buy_total_pln": 28000,
            "sell_total_pln": 17000,
            "largest_transactions": [
                {"date": "2026-08-05", "type": "BUY", "ticker": "CDR.WA", "value_pln": 12500},
                {"date": "2026-08-18", "type": "SELL", "ticker": "PKO.WA", "value_pln": 8200},
            ],
        },
    }

    # Normal mode
    _, text_body, html_body = email_service.render_monthly_recap_email(profile, wrap, hide_cash=False)
    assert "TRADING ACTIVITY" in html_body
    assert "45 000 PLN" in html_body
    assert "30 000 PLN" in html_body
    assert "28 000 PLN" in html_body
    assert "17 000 PLN" in html_body
    assert "TOP 5 TRANSACTIONS" in html_body
    assert "CDR.WA" in html_body
    assert "12 500 PLN" in html_body
    assert "BUY" in html_body
    assert "SELL" in html_body

    # Privacy mode: all PLN numbers masked with ---
    _, text_body_priv, html_body_priv = email_service.render_monthly_recap_email(profile, wrap, hide_cash=True)
    assert "Turnover: ---" in html_body_priv
    assert "45 000 PLN" not in html_body_priv
    assert "30 000 PLN" not in html_body_priv
    assert "12 500 PLN" not in html_body_priv
    assert "---" in html_body_priv


