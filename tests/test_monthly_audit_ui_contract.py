from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_history_contains_podsumowania_subtab_and_monthly_audit_mount():
    html = (ROOT / "src" / "index.html").read_text()
    assert 'data-history-section="recaps"' in html
    assert '>Podsumowania<' in html
    assert 'id="monthly-audit-root"' in html
    assert 'scripts/monthly-audit.js' in html


def test_monthly_audit_renders_six_required_cards_and_real_api_path():
    script = (ROOT / "src" / "scripts" / "monthly-audit.js").read_text()
    expected_titles = {
        "Przepływy i wynik portfeli",
        "Statystyki i ekstrema miesiąca",
        "Kontekst historyczny i sezonowość",
        "Plan emerytalny i zyski",
        "Lider i kotwica miesiąca",
        "Audyt Coping Diary i aktywność",
    }
    for title in expected_titles:
        assert title in script
    assert "fetchJson('/monthly-wraps')" in script
    assert "fetchJson(`/monthly-wraps?period=" in script
    assert "window.MONTHLY_WRAP_DATA" in script


def test_monthly_audit_has_glass_cards_timeline_and_mobile_single_columns():
    css = (ROOT / "src" / "styles" / "main.css").read_text()
    assert ".monthly-audit-card" in css
    assert "backdrop-filter: blur(12px)" in css
    assert "rgba(17, 24, 39, 0.7)" in css
    assert ".monthly-audit-month.is-active" in css
    assert "border-color: #a855f7" in css
    mobile = css[css.index("@media (max-width: 768px)", css.index("History: Monthly Audit")):]
    assert ".monthly-audit-summary-grid" in mobile
    assert "grid-template-columns: 1fr" in mobile