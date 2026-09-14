import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "lambda" / "email_sender.py"
SPEC = importlib.util.spec_from_file_location("roastfolio_email_sender", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(module)
render_periodic_recap_email = module.render_periodic_recap_email


def test_render_weekly_email_contains_privacy_safe_sections():
    payload = {
        "period": "weekly",
        "title": "Twoja Tygodniowa Triada",
        "user_name": "Alicja",
        "wallets": [
            {"name": "IKE", "net_cash_flow": 500, "twr": 3.4},
            {"name": "IKZE", "net_cash_flow": -125, "twr": -0.8},
        ],
        "portfolio_return": 4.7,
        "market": [
            {"label": "WIG20", "value": 1.2},
            {"label": "S&P 500", "value": 2.7},
            {"label": "MSCI World", "value": 2.3},
        ],
        "carry": {"name": "XTB.WA", "value": 12.4},
        "anchor": {"name": "CDR.WA", "value": -8.2},
        "cta_url": "https://app.roastfolio.com/dashboard?source=email"
    }

    html = render_periodic_recap_email(payload)

    assert "Twoja Tygodniowa Triada" in html
    assert "Net Cash Flow" in html
    assert "IKE" in html
    assert "3.4%" in html
    assert "WIG20" in html
    assert "XTB.WA" in html
    assert "CDR.WA" in html
    assert "PLN" not in html
    assert "https://app.roastfolio.com/dashboard?source=email" in html


def test_render_monthly_email_uses_monthly_title_and_diary_statuses():
    payload = {
        "period": "monthly",
        "title": "Miesięczny Audyt Hipotez",
        "wallets": [{"name": "Brokerage", "net_cash_flow": 1200, "twr": 5.5}],
        "portfolio_return": 6.1,
        "market": [
            {"label": "WIG20", "value": 2.1},
            {"label": "S&P 500", "value": 3.6},
            {"label": "MSCI World", "value": 3.1},
        ],
        "carry": {"name": "XTB.WA", "value": 14.2},
        "anchor": {"name": "PRL.WA", "value": -6.7},
        "diary": [
            {"label": "Rebalancing discipline", "status": "verified"},
            {"label": "Inflation hedge thesis", "status": "falsified"},
            {"label": "Quality bias audit", "status": "pending"},
        ],
        "cta_url": "https://app.roastfolio.com/dashboard?source=email"
    }

    html = render_periodic_recap_email(payload)

    assert "Miesięczny Audyt Hipotez" in html
    assert "Rebalancing discipline" in html
    assert "verified" in html.lower()
    assert "falsified" in html.lower()
    assert "pending" in html.lower()
    assert "Net Cash Flow" in html
