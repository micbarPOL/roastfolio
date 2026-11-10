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
    page.wait_for_function("""() => {
        const chart = _historyCharts.returnsChart;
        return chart && chart.data.datasets.every(dataset => {
            const first = dataset.data.find(value => value != null);
            return first == null || first === 0;
        });
    }""")
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


def test_history_benchmark_rejects_corrupt_wig_and_keeps_real_returns(open_history):
    page, _ = open_history()
    result = page.evaluate("""() => ({
        corrupt: _alignBenchmarkSeries([{t:'2019-07-25',c:284},{t:'2026-11-03',c:157647.9375}], ['2026-11-02','2026-11-03']),
        valid: _alignBenchmarkSeries([{t:'2026-11-02',c:156000},{t:'2026-11-03',c:157647.9375}], ['2026-11-02','2026-11-03']),
        weekend: _alignBenchmarkSeries([{t:'2026-11-06',c:100},{t:'2026-11-09',c:102}], ['2026-11-06','2026-11-07','2026-11-09'])
    })""")
    assert result['corrupt'] == [None, None]
    assert result['valid'] == [0, 1.06]
    assert result['weekend'] == [0, 0, 2]


def test_filtered_return_rebases_portfolio_and_benchmark(open_history):
    page, _ = open_history()
    result = page.evaluate("""async () => {
        const savedRange = _historyRange;
        const savedSelection = new Set(_historySelectedBenchmarks);
        const savedLoader = _loadHistoryBenchmark;
        const rows = [
            {date:'2026-10-01', value:218, investment:100, cumulativeReturnPct:118},
            {date:'2026-10-02', value:239.8, investment:100, cumulativeReturnPct:139.8},
            {date:'2026-10-03', value:196.2, investment:100, cumulativeReturnPct:96.2}
        ];
        const read = () => _historyCharts.returnsChart.data.datasets.map(d => [...d.data]);
        const results = {};
        try {
            _historySelectedBenchmarks.clear();
            _historySelectedBenchmarks.add('WIG');
            _loadHistoryBenchmark = async () => ({name:'WIG', daily:[
                {t:'2026-10-01', c:100}, {t:'2026-10-02', c:105}, {t:'2026-10-03', c:95}
            ]});
            for (const range of ['1W', '1M', 'YTD', '1Y', '3Y', '5Y', 'ALL']) {
                _historyRange = range;
                await _makeCumulativeReturnChart('returnsChart', rows, 'pct');
                results[range] = read();
            }
            _historyRange = '1M';
            await _makeCumulativeReturnChart('returnsChart', rows, 'pln');
            results.pln = read()[0];
            const withoutTwr = rows.map(({cumulativeReturnPct, ...row}) => row);
            await _makeCumulativeReturnChart('returnsChart', withoutTwr, 'pct');
            results.fallback = read()[0];
            await _makeCumulativeReturnChart('returnsChart', [rows[0]], 'pct');
            results.single = read()[0];
            const missing = rows.map(row => ({...row}));
            missing[0].cumulativeReturnPct = null;
            await _makeCumulativeReturnChart('returnsChart', missing, 'pct');
            results.missing = read()[0];
            await _makeCumulativeReturnChart('returnsChart', rows.map(row => ({
                ...row, cumulativeReturnPct:-100
            })), 'pct');
            results.zeroBase = read()[0];
            await _makeCumulativeReturnChart('returnsChart', rows.map((row, i) => ({
                ...row, cumulativeReturnPct:[-50, -45, -55][i]
            })), 'pct');
            results.negativeBase = read()[0];
            await _makeCumulativeReturnChart('returnsChart', rows.map((row, i) => ({
                ...row, cumulativeReturnPct:null, unitPrice:[218.004, 239.8044, 196.2036][i]
            })), 'pct');
            results.unitPrice = read()[0];
        } finally {
            _historyRange = savedRange;
            _historySelectedBenchmarks.clear();
            savedSelection.forEach(id => _historySelectedBenchmarks.add(id));
            _loadHistoryBenchmark = savedLoader;
        }
        return results;
    }""")
    for selected_range in ('1W', '1M', 'YTD', '1Y', '3Y', '5Y'):
        assert result[selected_range] == [[0, 10, -10], [0, 5, -5]]
    assert result['ALL'] == [[118, 139.8, 96.2], [0, 5, -5]]
    assert result['pln'] == [118, 139.8, 96.2]
    assert result['fallback'] == [0, 10, -10]
    assert result['single'] == [0]
    assert result['missing'][0:2] == [None, 0]
    assert result['zeroBase'] == [None, None, None]
    assert result['negativeBase'] == [0, 10, -10]
    assert result['unitPrice'] == [0, 10, -10]


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
    switch_track = page.locator(".rc-switch .rc-switch-track")
    assert switch_track.is_visible()
    box = switch_track.bounding_box()
    assert box and box["width"] >= 30 and box["height"] >= 18
    switch_track.click()
    assert page.locator("#recap-show-amounts-switch").is_checked()
    switch_track.click()
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
