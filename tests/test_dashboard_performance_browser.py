"""Privacy, persistence and actual page instrumentation contracts."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser
sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def page():
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("http://performance.test/**", lambda route: route.fulfill(
            content_type="text/html", body='<link rel="manifest" href="manifest.json?v=15.0.0">',
        ))
        page.goto("http://performance.test/")
        page.add_script_tag(path=str(ROOT / "src/scripts/dashboard-performance.js"))
        yield page
        browser.close()


def test_only_approved_numeric_metrics_are_recorded(page):
    snapshot = page.evaluate("""() => {
        DashboardPerformance.record('api-headers', 125, {
            view: 'full', responseBytes: 12345, serverMs: 80, token: 'SECRET',
            holdings: ['PRIVATE'], userId: 'USER', url: '/prices?token=SECRET'
        });
        DashboardPerformance.record('PRIVATE', 10);
        DashboardPerformance.record('api-parse', -1);
        DashboardPerformance.record('api-parse', NaN);
        DashboardPerformance.mark('full-ready');
        DashboardPerformance.mark('PRIVATE');
        return DashboardPerformance.snapshot();
    }""")
    assert len(snapshot["samples"]) == 1
    assert snapshot["samples"][0]["responseBytes"] == 12345
    assert snapshot["milestones"]["full-ready"] > 0
    assert "SECRET" not in str(snapshot)
    assert "PRIVATE" not in str(snapshot)
    assert "USER" not in str(snapshot)


def test_history_is_bounded_to_twenty_loads(page):
    for _ in range(23):
        page.reload()
        page.add_script_tag(path=str(ROOT / "src/scripts/dashboard-performance.js"))
        page.evaluate("DashboardPerformance.mark('full-ready')")
    sessions = page.evaluate("JSON.parse(localStorage.getItem('roastfolio-dashboard-performance-v1'))")
    assert len(sessions) == 20
    assert all(session["schemaVersion"] == 1 for session in sessions)
    page.evaluate("DashboardPerformance.clear()")
    assert page.evaluate("localStorage.getItem('roastfolio-dashboard-performance-v1')") is None


def test_first_readiness_mark_is_not_overwritten_and_samples_are_bounded(page):
    result = page.evaluate("""() => {
        DashboardPerformance.mark('lite-ready');
        const first = DashboardPerformance.snapshot().milestones['lite-ready'];
        for (let i = 0; i < 150; i++) DashboardPerformance.record('dashboard-render', 1);
        DashboardPerformance.mark('lite-ready');
        const result = DashboardPerformance.snapshot();
        return {first, result};
    }""")
    assert result["first"] == result["result"]["milestones"]["lite-ready"]
    assert len(result["result"]["samples"]) == 120


def test_export_downloads_json_without_portfolio_data(page):
    page.evaluate("DashboardPerformance.record('intraday-synthesis', 1, {pointCount: 481, holdingCount: 15})")
    with page.expect_download() as download:
        page.evaluate("DashboardPerformance.export()")
    assert download.value.suggested_filename == "roastfolio-dashboard-performance.json"
