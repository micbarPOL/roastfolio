"""Offline regressions for the production Analysis screen and controller."""
from datetime import date, timedelta
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

pytestmark = pytest.mark.browser
sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = BeautifulSoup((ROOT / "src/index.html").read_text(), "html.parser")
SCREEN = DOCUMENT.select_one("#tab-analysis")
SCREEN["class"] = ["tab-content", "active"]
STYLES = "\n".join((ROOT / "src/styles" / name).read_text() for name in (
    "main.css", "tokens-v9.css", "ui20.css", "analysis.css",
))
SCRIPT = (ROOT / "src/scripts/analysis.js").read_text()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as runner:
        instance = runner.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    instance = browser.new_page(viewport={"width": 1440, "height": 1000})
    instance.route("**/*", lambda route: route.fulfill(
        content_type="text/html; charset=utf-8", body=f'<html data-theme="dark"><head><meta charset="utf-8"><style>{STYLES}</style></head><body>{SCREEN}</body></html>',
    ) if route.request.resource_type == "document" else route.abort())
    instance.goto("http://analysis.test/")
    instance.add_script_tag(content="""
        window.requests = [];
        window.charts = [];
        window.__CONFIG__ = {apiUrl: 'http://analysis.test'};
        window.AuthGuard = {getIdToken: () => 'offline-test'};
        window.PortfolioClient = {listPortfolios: async () => ({portfolios: [{portfolioId: 'ike', name: 'IKE'}]})};
        window.isRoastfolioDark = () => document.documentElement.dataset.theme === 'dark';
        window.fetch = async url => {
            if (url.includes('/asset-analysis?')) return new Promise(resolve => requests.push({url, resolve}));
            return {ok: true, json: async () => ({favorites: []})};
        };
        window.LightweightCharts = {createChart: (container, options) => {
            const chart = {options, series: [], removed: false,
                addLineSeries() {const series = {setData(data) {this.data=data;}, setMarkers(markers) {this.markers=markers;}}; this.series.push(series); return series;},
                addHistogramSeries() {return this.addLineSeries();},
                priceScale: () => ({applyOptions() {}}),
                timeScale: () => ({fitContent() {}}),
                subscribeCrosshairMove() {}, applyOptions() {}, remove() {this.removed=true;}
            };
            charts.push(chart);
            return chart;
        }};
    """)
    instance.add_script_tag(content=SCRIPT)
    instance.wait_for_function("document.querySelector('#analysis-portfolio-filter').dataset.loaded === '1'")
    yield instance
    instance.close()


def asset_data(name="Test Company"):
    periods = [{"date": str(year), "TotalRevenue": year * 1000000, "NetIncome": year * 200000} for year in range(2025, 2020, -1)]
    return {
        "currency": "PLN", "financialCurrency": "EUR", "fundamentals": {"longName": name, "fiftyTwoWeekHigh": 180},
        "history": [{"t": str(date(2026, 1, 1) + timedelta(days=offset)), "c": 100 + offset, "v": 1000} for offset in range(80)],
        "transactions": [{"date": "2026-01-05", "type": "BUY", "units": 2, "price": 104, "portfolioId": "ike"}],
        "financials": {"annual": periods, "quarterly": [{"date": "2026-06-30", "TotalRevenue": 123000000}]},
        "cashflow": {"annual": [{"date": "2025", "OperatingCashFlow": 1000000}]},
    }


def load_asset(page, name="Test Company"):
    page.evaluate("() => { window._analysis.loadAssetData('TEST.WA'); }")
    page.evaluate("data => requests.at(-1).resolve({ok: true, json: async () => data})", asset_data(name))
    sync_api.expect(page.locator("#analysis-chart-title")).to_have_text(name)
    sync_api.expect(page.locator("#analysis-content-area")).to_have_attribute("aria-busy", "false")


def test_picker_keeps_asset_and_help_closes_with_escape(page):
    sync_api.expect(page.locator("#analysis-empty-state")).to_be_visible()
    page.locator("#analysis-empty-select").click()
    sync_api.expect(page.locator("#analysis-asset-dialog")).to_be_visible()
    sync_api.expect(page.locator("#analysis-search-input")).to_be_focused()
    load_asset(page)
    sync_api.expect(page.locator("#analysis-asset-dialog")).not_to_be_visible()
    sync_api.expect(page.locator("#analysis-empty-state")).not_to_be_visible()
    page.locator("#analysis-asset-open").click()
    page.keyboard.press("Escape")
    sync_api.expect(page.locator("#analysis-chart-title")).to_have_text("Test Company")
    sync_api.expect(page.locator("#analysis-asset-open")).to_be_focused()
    page.get_by_label("About price history and indicators").click()
    sync_api.expect(page.locator(".analysis-help[open]")).to_have_count(1)
    page.keyboard.press("Escape")
    sync_api.expect(page.locator(".analysis-help[open]")).to_have_count(0)


def test_real_dates_currency_and_local_indicators(page):
    load_asset(page)
    sync_api.expect(page.locator("#analysis-quote-price")).to_have_text("179")
    sync_api.expect(page.locator("#analysis-quote-currency")).to_have_text("PLN")
    sync_api.expect(page.locator("#analysis-statement-currency")).to_contain_text("EUR")
    sync_api.expect(page.locator("#analysis-quote-asof")).to_contain_text("21/03/2026")
    sync_api.expect(page.locator("#analysis-range-return")).to_have_text("+79.00% · 1Y")
    requests_before = page.evaluate("requests.length")
    for name in ("volume", "ma10", "ma20", "ma50", "macd"):
        page.locator(f"#analysis-{name}-toggle").click()
    assert page.evaluate("requests.length") == requests_before
    assert page.evaluate("charts.slice(0,-1).every(chart => chart.removed)")
    sync_api.expect(page.locator("#analysis-ma10-toggle")).to_have_attribute("aria-pressed", "true")
    sync_api.expect(page.locator("#analysis-volume-toggle")).to_have_attribute("aria-pressed", "false")
    page.evaluate("window.dispatchEvent(new Event('roastfolio:themechange'))")
    assert page.evaluate("requests.length") == requests_before


def test_stale_response_cannot_replace_new_asset(page):
    page.evaluate("() => { window._analysis.loadAssetData('OLD'); window._analysis.loadAssetData('NEW'); }")
    page.evaluate("data => requests[1].resolve({ok: true, json: async () => data})", asset_data("Newest Company"))
    sync_api.expect(page.locator("#analysis-chart-title")).to_have_text("Newest Company")
    page.evaluate("data => requests[0].resolve({ok: true, json: async () => data})", asset_data("Old Company"))
    sync_api.expect(page.locator("#analysis-chart-title")).to_have_text("Newest Company")
    assert page.evaluate("charts.length") == 1


def test_error_retry_and_hidden_trade_scope(page):
    page.evaluate("() => { window._analysis.loadAssetData('TEST.WA'); }")
    page.evaluate("requests.at(-1).resolve({ok:false})")
    sync_api.expect(page.locator("#analysis-error")).to_be_visible()
    sync_api.expect(page.locator("#analysis-content-area")).not_to_be_visible()
    page.locator("#analysis-retry").click()
    page.evaluate("data => requests.at(-1).resolve({ok:true,json:async()=>data})", asset_data())
    sync_api.expect(page.locator("#analysis-error")).not_to_be_visible()
    sync_api.expect(page.locator("#analysis-content-area")).to_have_attribute("aria-busy", "false")
    page.locator("#analysis-portfolio-filter").select_option("none")
    page.wait_for_function("requests.length === 3")
    assert "portfolioId=none" not in page.evaluate("requests.at(-1).url")
    page.evaluate("data => requests.at(-1).resolve({ok:true,json:async()=>data})", asset_data())
    sync_api.expect(page.locator("#analysis-content-area")).to_have_attribute("aria-busy", "false")
    assert page.evaluate("(charts.at(-1).series[0].markers || []).length") == 0
    page.locator("#analysis-portfolio-filter").select_option("ike")
    page.wait_for_function("requests.length === 4")
    assert "portfolioId=ike" in page.evaluate("requests.at(-1).url")


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("width", [1440, 1024, 768, 390])
def test_table_layout_periods_and_sticky_metrics(page, theme, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.evaluate("theme => document.documentElement.dataset.theme=theme", theme)
    load_asset(page)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("#tab-analysis").evaluate("element => getComputedStyle(element).backgroundColor") != "rgba(0, 0, 0, 0)"
    assert page.locator(".analysis-fundamentals-card").evaluate("element => getComputedStyle(element).borderRadius") == "0px"
    assert page.locator('[data-range="1y"]').evaluate("""element => {
        const probe = document.createElement('span');
        probe.style.color = 'var(--text-primary)';
        element.append(probe);
        const expected = getComputedStyle(probe).color;
        probe.remove();
        return getComputedStyle(element).color === expected;
    }"""), "Range button must use the v9 --text-primary token"
    table = page.locator("#analysis-financials-table")
    assert table.locator("tbody td").nth(1).evaluate("element => getComputedStyle(element).backgroundColor") == page.locator("#tab-analysis").evaluate("element => getComputedStyle(element).backgroundColor")
    sync_api.expect(table.locator("thead th")).to_have_count(7)
    scroller = page.locator(".analysis-financials-table-wrapper")
    scroller.evaluate("element => element.scrollLeft = 200")
    pinned = table.locator("tbody tr:first-child td:first-child").bounding_box()
    assert abs(pinned["x"] - scroller.bounding_box()["x"]) < 3
    page.locator('[data-period="quarterly"]').click()
    sync_api.expect(table).to_contain_text("2026-06-30")
    page.locator('[data-type="cashflow"]').click()
    sync_api.expect(table).to_contain_text("No data available for this period")
    page.locator('[data-period="annual"]').click()
    sync_api.expect(table).to_contain_text("Operating Cash Flow")