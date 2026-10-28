"""Offline browser tests of the intraday calculation and dashboard controller."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser
sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "src/scripts/intraday-comparison.js").read_text()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        instance = p.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    page = browser.new_page()
    page.route("http://intraday.test/**", lambda route: route.fulfill(
        content_type="text/html",
        body="""<select id="intraday-comparison-window">
        <option value="session">Benchmark session</option><option value="day">24 hours</option>
        </select><div style="height:240px"><canvas id="intraday-comparison-chart"></canvas></div>
        <p id="intraday-comparison-status"></p>""",
    ))
    page.goto("http://intraday.test/")
    page.add_script_tag(content="""
        window.charts = [];
        window.Chart = class {
            constructor(canvas, config) { this.config = config; window.charts.push(this); }
            destroy() { this.destroyed = true; }
        };
        window.AuthGuard = { getUserId: () => 'test-user' };
    """)
    page.add_script_tag(content=SCRIPT)
    yield page
    page.close()


def fixture(page, *, benchmark_id="WIG", date="2026-10-14", mode="session", now="19:00"):
    return page.evaluate("""({ benchmarkId, date, mode, now }) => {
        const zone = benchmarkId === 'SP500' ? 'America/New_York' : 'Europe/Warsaw';
        const open = benchmarkId === 'SP500' ? '09:30' : '09:00';
        const start = IntradayComparison.localTime(date, open, zone);
        const end = IntradayComparison.localTime(date, benchmarkId === 'SP500' ? '16:00' : '17:00', zone);
        const dayNow = IntradayComparison.localTime(date, now, zone);
        const benchmark = { session: {start: start/1000, end: end/1000}, intraday: [] };
        const prices = [];
        for (let t = start; t < end; t += 60000) {
            benchmark.intraday.push({t: t/1000, o: 100, c: 101});
        }
        for (let t = start; t < dayNow; t += 60000) prices.push([t, t < end ? 110 : 120]);
        return { benchmarkId, benchmark, mode, now: dayNow, holdings: [
            {name: 'Stock', ticker: 'TEST', units: 2, intradayFxRate: 4,
                intradayBaseline: {openTime: start, openPrice: 100, previousClose: 90},
                todayBars: prices},
            {name: 'Cash', ticker: null, currentValue: 200}
        ] };
    }""", {"benchmarkId": benchmark_id, "date": date, "mode": mode, "now": now})


def synthesize(page, data):
    return page.evaluate("data => IntradayComparison.synthesize(data)", data)


def test_cash_weighting_and_common_baseline(page):
    result = synthesize(page, fixture(page))
    assert result["openValue"] == 1000
    assert result["points"][0]["portfolioPct"] == 0
    assert result["points"][0]["benchmarkPct"] == 0
    assert result["points"][1]["portfolioPct"] == pytest.approx(8)
    assert result["points"][1]["benchmarkPct"] == pytest.approx(1)
    assert result["points"][1]["spreadPp"] == pytest.approx(7)
    assert len(result["points"]) == 481
    assert result["points"][-1]["timestamp"] == result["end"]


def test_portfolio_line_is_delayed_like_the_benchmark_quotes(page):
    data = fixture(page, now="12:00")
    result = synthesize(page, data)
    delayed = data["now"] - 15 * 60000
    assert result["quoteDelay"] == 15 * 60000
    assert result["points"][-1]["timestamp"] == delayed
    assert result["portfolioAsOf"] <= delayed
    assert result["benchmarkAsOf"] <= delayed


def test_first_fifteen_minutes_wait_for_delayed_quotes(page):
    data = fixture(page, now="09:10")
    message = page.evaluate("""data => { try { IntradayComparison.synthesize(data); return null; }
        catch (error) { return error.message; } }""", data)
    assert message == "Quotes are delayed 15 minutes; the chart starts at 09:15."


def test_after_close_portfolio_continues_benchmark_does_not(page):
    result = synthesize(page, fixture(page, mode="day"))
    assert len(result["points"]) == 586  # 09:00 to 18:45 (19:00 minus the 15-minute quote delay)
    assert result["points"][-1]["portfolioPct"] == pytest.approx(16)
    assert result["points"][-1]["benchmarkPct"] is None
    assert result["points"][-1]["spreadPp"] is None
    final_benchmark = [p for p in result["points"] if p["benchmarkPct"] is not None][-1]
    assert final_benchmark["timestamp"] == result["end"]
    assert result["axisEnd"] - result["axisStart"] == 24 * 3600000


def test_provider_early_close(page):
    data = fixture(page, benchmark_id="SP500", mode="day")
    data["benchmark"]["session"]["end"] -= 3 * 3600
    result = synthesize(page, data)
    assert result["end"] - result["start"] == 3.5 * 3600000
    assert [p for p in result["points"] if p["benchmarkPct"] is not None][-1]["timestamp"] == result["end"]


@pytest.mark.parametrize(("date", "utc_hour"), [("2026-01-14", 8), ("2026-07-14", 7)])
def test_warsaw_dst(page, date, utc_hour):
    result = synthesize(page, fixture(page, date=date))
    assert (result["start"] // 3600000) % 24 == utc_hour
    assert result["end"] - result["start"] == 8 * 3600000


@pytest.mark.parametrize(("date", "utc_hour"), [("2026-03-16", 13), ("2026-11-02", 14)])
def test_us_dst_not_fixed_to_warsaw(page, date, utc_hour):
    result = synthesize(page, fixture(page, benchmark_id="SP500", date=date))
    assert (result["start"] // 3600000) % 24 == utc_hour
    assert result["end"] - result["start"] == 6.5 * 3600000


def test_later_exchange_uses_previous_close_without_looking_ahead(page):
    data = fixture(page)
    start = data["benchmark"]["session"]["start"] * 1000
    holding = data["holdings"][0]
    holding["intradayBaseline"]["openTime"] = start + 6 * 3600000
    holding["intradayBaseline"]["sessionStart"] = start + 6 * 3600000
    holding["intradayBaseline"]["previousClose"] = 100
    holding["todayBars"] = [[start + 6 * 3600000, 120]]
    result = synthesize(page, data)
    assert result["points"][359]["portfolioPct"] == 0
    assert result["points"][360]["portfolioPct"] == 0
    assert result["points"][361]["portfolioPct"] == pytest.approx(16)


def test_missing_holding_does_not_renormalize(page):
    data = fixture(page)
    data["holdings"][0]["todayBars"] = []
    with pytest.raises(sync_api.Error, match="No holdings were excluded"):
        synthesize(page, data)


def test_late_first_benchmark_print_is_used_as_opening_value(page):
    data = fixture(page)
    data["benchmark"]["intraday"].pop(0)
    result = synthesize(page, data)
    assert result["points"][0]["portfolioPct"] == 0
    assert result["points"][0]["benchmarkPct"] is None
    assert result["points"][1]["benchmarkPct"] == 0
    assert result["points"][2]["benchmarkPct"] == pytest.approx(1)
    assert result["points"][2]["portfolioPct"] == pytest.approx(8)
    assert any("Benchmark first print 09:01" in w for w in result["warnings"])


def test_missing_opening_candle_is_unavailable(page):
    data = fixture(page)
    del data["benchmark"]["intraday"][:16]
    with pytest.raises(sync_api.Error, match="opening candle is missing"):
        synthesize(page, data)


def test_missing_stock_open_does_not_substitute_previous_close(page):
    data = fixture(page)
    holding = data["holdings"][0]
    start = holding["intradayBaseline"]["openTime"]
    holding["intradayBaseline"]["sessionStart"] = start
    holding["intradayBaseline"]["openTime"] += 60000
    holding["todayBars"].pop(0)
    with pytest.raises(sync_api.Error, match="Session-start price unavailable"):
        synthesize(page, data)


def test_previous_candles_do_not_overwrite_opening_baseline(page):
    data = fixture(page)
    holding = data["holdings"][0]
    start = holding["intradayBaseline"]["openTime"]
    holding["todayBars"].insert(0, [start - 60000, 95])
    result = synthesize(page, data)
    assert result["points"][0]["portfolioPct"] == 0
    assert result["points"][1]["portfolioPct"] == pytest.approx(8)


def test_sparse_prices_are_carried_forward_with_warning(page):
    data = fixture(page, mode="day")
    data["holdings"][0]["todayBars"] = data["holdings"][0]["todayBars"][:4]
    result = synthesize(page, data)
    assert result["points"][4]["portfolioPct"] == pytest.approx(8)
    assert result["points"][5]["portfolioPct"] == pytest.approx(8)
    assert result["portfolioAsOf"] == result["start"] + 4 * 60000
    assert any("carried forward" in warning for warning in result["warnings"])


def test_comparison_history_preserves_baseline_across_ticker_midnight(page):
    data = fixture(page, benchmark_id="SP500", mode="day")
    holding = data["holdings"][0]
    # The latest instrument-local day's sparkline no longer contains the shared baseline.
    holding["comparisonBars"] = holding["todayBars"]
    holding["todayBars"] = holding["todayBars"][-5:]
    holding["intradayBaseline"] = None
    start = data["benchmark"]["session"]["start"] * 1000
    holding["comparisonBars"].insert(0, [start - 60000, 100])
    result = synthesize(page, data)
    assert result["openValue"] == 1000
    assert result["points"][1]["portfolioPct"] == pytest.approx(8)


def test_millisecond_benchmark_timestamps_are_supported(page):
    data = fixture(page)
    for bar in data["benchmark"]["intraday"]:
        bar["t"] *= 1000
    result = synthesize(page, data)
    assert result["points"][1]["benchmarkPct"] == pytest.approx(1)


def test_benchmark_change_does_not_relabel_previous_benchmark_data(page):
    data = fixture(page)
    data["benchmark"]["benchmarkId"] = "SP500"
    with pytest.raises(sync_api.Error, match="Waiting for WIG minute bars"):
        synthesize(page, data)


def test_old_session_and_missing_metadata_are_disclosed(page):
    data = fixture(page)
    data["now"] += 2 * 86400000
    data["benchmark"].pop("session")
    result = synthesize(page, data)
    assert any("not today" in warning for warning in result["warnings"])
    assert any("metadata unavailable" in warning for warning in result["warnings"])


def test_duplicate_holdings_are_valued_without_price_averaging(page):
    data = fixture(page)
    stock = dict(data["holdings"][0])
    stock["units"] = 1
    data["holdings"].append(stock)
    result = synthesize(page, data)
    assert result["openValue"] == 1400
    assert result["points"][1]["portfolioPct"] == pytest.approx(120 / 1400 * 100)


def test_window_preference_events_and_tooltip(page):
    data = fixture(page, mode="day")
    page.evaluate("""data => {
        window.PORTFOLIO_DATA = data.holdings;
        window.BENCHMARK_DATA = data.benchmark;
        window.BENCHMARK_ID = data.benchmarkId;
        Date.now = () => data.now;
        document.dispatchEvent(new CustomEvent('liveDataReady'));
    }""", data)
    assert page.locator("#intraday-comparison-status").inner_text().startswith("2026-10-14")
    page.select_option("#intraday-comparison-window", "day")
    assert page.evaluate("localStorage.getItem('intraday-comparison-window:test-user')") == "day"
    assert page.evaluate("charts.at(-1).config.data.datasets[1].data.at(-1).y") is None
    assert page.evaluate("""() => charts.at(-1).config.options.plugins.tooltip.callbacks.afterBody(
        [{dataIndex: 1}])""") == "Spread: 7.00 pp"
    assert page.evaluate("""() => charts.at(-1).config.options.plugins.tooltip.callbacks.afterBody(
        [{dataIndex: 600}])""") == "Comparison unavailable at this minute"
    page.add_script_tag(content=SCRIPT)
    assert page.locator("#intraday-comparison-window").input_value() == "day"


def test_calculation_for_fifteen_holdings(page):
    data = fixture(page, mode="day")
    data["holdings"] = [dict(data["holdings"][0], ticker=f"TEST{i}") for i in range(15)] + data["holdings"][1:]
    result = page.evaluate("""data => {
        const start = performance.now();
        const output = IntradayComparison.synthesize(data);
        return { elapsed: performance.now() - start, count: output.points.length };
    }""", data)
    assert result["count"] == 586
    # A generous regression budget, not a claim of sub-2ms execution on every device.
    assert result["elapsed"] < 100
