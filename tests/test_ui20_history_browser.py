"""Real History screen UI 20 browser coverage."""
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytestmark = [pytest.mark.design, pytest.mark.browser]

sync_api = pytest.importorskip("playwright.sync_api")
import server  # noqa: E402

SETTLE_MS = 900


@pytest.fixture(scope="module")
def base_url():
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("", 0), server.InvestmentHandler)
    port = httpd.server_address[1]
    server.PORT = port
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{port}/index.html?devAuth=1"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            instance = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium is not available: {exc}")
        yield instance
        instance.close()


@pytest.fixture
def open_history(browser, base_url):
    contexts = []

    def _open(width=1440, height=900, theme="dark", section="overview"):
        context = browser.new_context(viewport={"width": width, "height": height}, has_touch=width < 768, service_workers="block")
        contexts.append(context)
        context.add_init_script(f"try{{localStorage.setItem('roastfolio-theme','{theme}');}}catch(e){{}}")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text and "Failed to fetch sparkline" not in m.text else None)
        page.goto(base_url)
        page.evaluate("showTab('history')")
        page.wait_for_selector("#tab-history .hx-sections", timeout=30000)
        page.wait_for_function("() => document.querySelectorAll('#history-wallet-btns .history-wallet-btn').length >= 2", timeout=30000)
        page.wait_for_function("() => document.querySelector('#history-hero-total')?.textContent.includes('PLN')", timeout=30000)
        if section == "summaries":
            page.evaluate("setHistorySection('recaps')")
            page.wait_for_selector("#monthly-audit-root .rc-poster[data-mood]", timeout=30000)
        page.wait_for_timeout(SETTLE_MS)
        return page, errors

    yield _open
    for context in contexts:
        context.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_history_no_horizontal_overflow_and_no_console_errors(open_history, width, height, theme):
    for section in ("overview", "summaries"):
        page, errors = open_history(width, height, theme, section=section)
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 0, f"{section} is {overflow}px wider than {width}px"
        assert not errors, errors


def test_overview_hero_range_wallet_and_return_toggles(open_history):
    page, _ = open_history()
    assert page.locator("#history-hero-total").inner_text().endswith("PLN")
    assert "PLN" in page.locator("#history-hero-invested").inner_text()
    first_total = page.locator("#history-hero-total").inner_text()
    page.locator('[data-history-range="1M"]').click()
    page.wait_for_function("() => document.querySelector('[data-history-range=\"1M\"]')?.getAttribute('aria-selected') === 'true'")
    assert "this month" in page.locator("#history-hero-range").inner_text()
    page.locator("#history-wallet-btns .history-wallet-btn").nth(1).click()
    page.wait_for_timeout(500)
    assert page.locator("#history-hero-total").inner_text() != first_total
    assert page.locator("#returnsChart").is_visible()
    page.locator('[data-history-return-mode="pln"]').click()
    page.wait_for_function("() => !document.querySelector('#history-return-pln-note').hasAttribute('hidden')")
    assert page.locator("#history-benchmark-series").is_hidden()
    page.locator('[data-history-return-mode="pct"]').click()
    page.wait_for_function("() => document.querySelector('#history-benchmark-series') && !document.querySelector('#history-benchmark-series').hidden")
    assert page.locator("#history-benchmark-series").is_visible()


def test_daily_chart_is_scatter_and_stats_update(open_history):
    page, _ = open_history()
    assert page.locator("#dailyChangeChart").get_attribute("data-chart-kind") == "scatter"
    assert page.locator(".hx-daily-wrapper").get_attribute("data-chart-kind") == "scatter"
    assert "Average" in page.locator("#history-daily-stats").inner_text()
    page.locator('[data-history-daily-mode="pln"]').click()
    page.wait_for_function("() => document.querySelector('[data-history-daily-mode=\"pln\"]')?.getAttribute('aria-selected') === 'true'")
    assert "PLN" in page.locator("#history-daily-stats").inner_text()


def test_summaries_poster_navigator_headline_and_invite(open_history):
    page, _ = open_history(section="summaries")
    poster = page.locator(".rc-poster")
    assert poster.get_attribute("data-mood") in {"up", "down", "flat"}
    assert page.get_by_role("tab", name="Yearly Soon").is_disabled()
    assert not page.locator("#recap-show-amounts-switch").is_checked()
    before = page.locator(".rc-poster h1").inner_text()
    page.locator(".rc-step").first.click()
    page.wait_for_timeout(500)
    assert page.locator(".rc-poster h1").inner_text() != before
    assert page.evaluate("""() => MonthlyAuditPresentation.headline({
        period:'2026-08', overall_twr_pct:5, overall_nominal_change_pln:1000,
        carry:{ticker:'XTB', net_contribution_pln:670},
        journey:{benchmark_id:'WIG', benchmark_return_pct:3.08, points:[{date:'2026-08-01', portfolio_pct:0, benchmark_pct:0},{date:'2026-09-01', portfolio_pct:5, benchmark_pct:3.08}]}
    })""") == "You beat the WIG by 1.92 pp, and XTB carried 67% of the gain."
    page.evaluate("""async () => {
        window.MONTHLY_WRAP_DATA = [{...window.MONTHLY_WRAP_DATA[0], period:'2026-10', overall_twr_pct:1, journey:{...window.MONTHLY_WRAP_DATA[0].journey, benchmark_return_pct:2, points:[{date:'2026-10-01',portfolio_pct:0,benchmark_pct:0},{date:'2026-11-01',portfolio_pct:1,benchmark_pct:2}]}}];
        await initMonthlyAudit(true);
    }""")
    assert page.locator(".rc-sticker").count() == 0
