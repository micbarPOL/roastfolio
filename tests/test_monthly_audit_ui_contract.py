from pathlib import Path
import pytest

pytestmark = pytest.mark.smoke

ROOT = Path(__file__).resolve().parents[1]


def test_history_contains_podsumowania_subtab_and_monthly_audit_mount():
    html = (ROOT / "src" / "index.html").read_text()
    assert 'data-history-section="recaps"' in html
    assert '>Summaries<' in html
    assert 'id="monthly-audit-root"' in html
    assert 'scripts/monthly-audit.js' in html
    assert 'styles/monthly-audit.css?v=20260915-interactive3' in html
    assert 'scripts/manage.js?v=20260915-recap2' in html
    assert html.count('scripts/user-profile.js?v=20260915-recap2') == 2
    assert html.index('scripts/monthly-audit-share.js') < html.index('scripts/monthly-audit.js')


def test_history_does_not_restore_local_memory_lane_mocks():
    html = (ROOT / "src" / "index.html").read_text()
    assert "_renderLocalHistoryDummyCards" not in html
    assert "historyOverviewDummyCards" not in html
    assert "historyBenchmarkDummyCards" not in html
    assert "recapCarousel" not in html


def test_monthly_audit_renders_bento_sections_and_real_api_path():
    script = (ROOT / "src" / "scripts" / "monthly-audit.js").read_text()
    expected_titles = {
        "Your money, in motion.",
        "Moments that mattered.",
        "A little perspective.",
        "The bigger goal.",
        "Who moved your month?",
        "What changed hands.",
        "Your returns, side by side.",
    }
    for title in expected_titles:
        assert title in script
    assert "fetchJson('/monthly-wraps')" in script
    assert "fetchJson(`/monthly-wraps?period=" in script
    assert "window.MONTHLY_WRAP_DATA" in script
    assert "Nominal change" in script
    assert "overall_nominal_change_pln" in script
    for number in range(1, 7):
        assert f"'{number:02d} ·" not in script


def test_monthly_audit_uses_dated_returns_and_one_signed_target_track():
    script = (ROOT / "src" / "scripts" / "monthly-audit.js").read_text()
    for field in ("portfolio_pct", "benchmark_pct", "benchmark_currency"):
        assert field in script
    assert "drawdown_trajectory_pct" in script
    assert "!Array.isArray(series) || series.length < 2" in script
    assert 'class="trajectory-lake"' in script
    assert 'class="ma-return-chart"' in script
    assert 'class="ma-target-track"' in script
    assert "monthly-audit-ring" not in script
    assert "monthly-audit-progress" not in script
    assert "coping_diary_audit" not in script
    assert "ma-cover-seal" not in script


def test_market_and_trading_schema_are_consumed_without_fake_zero_defaults():
    script = (ROOT / "src" / "scripts" / "monthly-audit.js").read_text()
    for field in ("market_context", "MSCI_WORLD", "SP500", "NASDAQ", "DAX", "FTSE100",
                  "trading_activity", "buy_total_pln", "sell_total_pln", "turnover_pln",
                  "dividend_total_pln", "transaction_count", "largest_transactions", "value_pln"):
        assert field in script
    assert "dates may differ from portfolio TWR" in script
    assert "Contribution unavailable" in script
    assert "Transaction details unavailable" in script
    assert "not necessarily the month total" in script


def test_monthly_audit_has_editorial_bento_and_adaptive_single_columns():
    css = (ROOT / "src" / "styles" / "monthly-audit.css").read_text()
    assert ".monthly-audit-card" in css
    assert "repeat(12, minmax(0, 1fr))" in css
    assert 'data-theme="light"' in css
    assert "prefers-reduced-motion" in css
    mobile = css[css.index("@media (max-width: 768px)"):]
    assert ".monthly-audit-content" in mobile
    assert "grid-template-columns: 1fr" in mobile


def test_monthly_share_is_local_preview_first_and_private_by_default():
    script = (ROOT / "src" / "scripts" / "monthly-audit-share.js").read_text()
    assert "hideAmounts = true" in script
    assert "nominalChange: hideAmounts ? null" in script
    assert "dialog.showModal()" in script
    assert "canvas.toBlob" in script
    assert "navigator.canShare" in script
    assert "navigator.share({ files: [file]" in script
    assert "URL.revokeObjectURL" in script
    assert "AbortError" in script
    assert "fetch(" not in script


def test_milestones_calendar_widget_and_ath_celebration_contract():
    js = (ROOT / "src" / "scripts" / "monthly-audit.js").read_text()
    css = (ROOT / "src" / "styles" / "monthly-audit.css").read_text()
    chart_js = (ROOT / "src" / "scripts" / "chart.js").read_text()

    # Extremes card integrates monthCalendarWidget and binds milestone hover
    assert "monthCalendarWidget(item)" in js
    assert "bindMilestones(item)" in js
    assert "ma-milestones-calendar" in js
    assert "ma-cal-grid" in js
    assert "ma-cal-days" in js
    assert "ma-cal-dow-row" in js
    assert "ma-cal-tooltip" in js
    assert "Daily returns" in js
    assert "is-ath" in js
    assert "is-best" in js
    assert "is-worst" in js
    assert "🏆" in js

    # CSS has required classes and pulse animation for ATH
    assert ".ma-calendar-section" in css
    assert ".ma-cal-day.is-ath" in css
    assert ".ma-cal-day.is-best" in css
    assert ".ma-cal-day.is-worst" in css
    assert "@keyframes ma-ath-pulse" in css
    assert ".ma-cal-tooltip" in css

    # Chart.js exposes snapshots caching functions for cross-tab availability
    assert "window._loadHistorySnapshots" in chart_js
    assert "window._getHistorySnapshotCache" in chart_js