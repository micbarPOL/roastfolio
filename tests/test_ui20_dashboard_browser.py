"""The real dashboard (src/) on the UI 20 branch, in a real browser: layout, behaviour, frames, touch targets.

Serves src/ with the repo's mock API (server.InvestmentHandler) on a free port; no browser window is opened.
Needs Playwright Chromium and network access for the chart CDNs. Run with ./test.sh design.
"""
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

SETTLE_MS = 700  # entrance animations and canvas fade-in after the data arrives
THEMES = ["dark", "light"]
VIEWPORTS = [(1440, 900), (1024, 768), (768, 1024), (390, 844)]
MIN_TARGET = 43.5  # 44px minus sub-pixel rounding

FRAMELESS_SCAN = """() => {
  const out = [];
  for (const el of document.querySelectorAll('#tab-dashboard *')) {
    if (el.closest('svg, .glass-island, .card-cl-overlay, canvas, .bench-chart, .eng-strip, .segmented, .market-index-carousel, .roast-reactions')) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 160 || r.height < 72) continue;
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') continue;
    const radius = Math.max(...['TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'].map(k => parseFloat(s['border' + k + 'Radius']) || 0));
    if (radius < 12) continue;
    const border = ['Top', 'Right', 'Bottom', 'Left'].some(k => parseFloat(s['border' + k + 'Width']) > 0 && s['border' + k + 'Style'] !== 'none');
    const fill = s.backgroundColor !== 'rgba(0, 0, 0, 0)' || s.backgroundImage !== 'none';
    if (border || fill || s.boxShadow !== 'none') out.push(`${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]} ${Math.round(r.width)}x${Math.round(r.height)} radius ${radius}`);
  }
  return out;
}"""

COLLECT_TARGETS = """() => Array.from(document.querySelectorAll('#tab-dashboard a[href], #tab-dashboard button, .bottom-tabs button'))
  .filter(el => !el.closest('[hidden],[aria-hidden="true"]') && el.id !== 'tv-attr-logo')  // the chart library's licence mark is third-party
  .map(el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return {label: (el.getAttribute('aria-label') || el.textContent).trim().slice(0, 30), cls: String(el.className).slice(0, 40),
            w: r.width, h: r.height, shown: r.width > 0 && r.height > 0 && s.visibility !== 'hidden'}; })
  .filter(t => t.shown)"""


@pytest.fixture(scope="module")
def base_url():
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("", 0), server.InvestmentHandler)
    port = httpd.server_address[1]
    server.PORT = port  # the mock config.js points the API at this port
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{port}/index.html"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            instance = p.chromium.launch()
        except Exception as exc:  # browser binary missing
            pytest.skip(f"Chromium is not available: {exc}")
        yield instance
        instance.close()


@pytest.fixture
def open_page(browser, base_url):
    contexts = []

    def _open(width=1440, height=900, theme="dark", reduced=False, storage=None):
        context = browser.new_context(
            viewport={"width": width, "height": height},
            has_touch=width < 768,
            reduced_motion="reduce" if reduced else "no-preference",
        )
        contexts.append(context)
        entries = {"roastfolio-theme": theme, **(storage or {})}
        context.add_init_script("try{" + "".join(f"localStorage.setItem('{k}','{v}');" for k, v in entries.items()) + "}catch(e){}")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base_url)
        page.wait_for_selector("#tab-dashboard .hero")
        page.wait_for_selector("#dash-breakdown .m-row", timeout=30000)
        page.wait_for_selector("#gauge-benchmark-tooltip .roast-msg", timeout=30000)
        page.wait_for_selector(".market-ticker-lane", timeout=30000)
        page.wait_for_timeout(SETTLE_MS)
        return page, errors

    yield _open
    for context in contexts:
        context.close()


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_dashboard_never_scrolls_sideways_and_has_no_script_errors(open_page, width, height, theme):
    page, errors = open_page(width, height, theme)
    assert page.evaluate("document.documentElement.dataset.theme") == theme
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0, f"page is {overflow}px wider than the {width}px viewport"
    assert not errors, errors


@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_intraday_comparison_renders_real_chart_and_saved_window(open_page, width, height):
    page, errors = open_page(width, height)
    page.evaluate("""() => {
        const start = IntradayComparison.localTime('2026-10-14', '09:00', 'Europe/Warsaw');
        const end = start + 8 * 3600000;
        const now = end + 2 * 3600000;
        Date.now = () => now;
        window.BENCHMARK_ID = 'WIG';
        window.BENCHMARK_NAME = 'WIG';
        window.BENCHMARK_DATA = {session: {start: start/1000, end: end/1000}, intraday: []};
        for (let t = start; t < end; t += 60000) {
            BENCHMARK_DATA.intraday.push({t: t/1000, o: 100, c: 101});
        }
        window.PORTFOLIO_DATA = window.PORTFOLIO_DATA.map(holding => {
            if (!holding.ticker) return holding;
            const price = holding.priceOriginal;
            const todayBars = [];
            for (let t = start; t < now; t += 60000) todayBars.push([t, price * (t < end ? 1.01 : 1.02)]);
            return {...holding, todayBars, comparisonBars: todayBars, intradayFxRate: 1,
                intradayBaseline: {openTime: start, openPrice: price}};
        });
        document.dispatchEvent(new CustomEvent('liveDataReady'));
    }""")
    page.select_option("#intraday-comparison-window", "day")
    chart_data = page.evaluate("""() => {
        const chart = Chart.getChart('intraday-comparison-chart');
        return {portfolio: chart.data.datasets[0].data.at(-1),
            benchmark: chart.data.datasets[1].data.at(-1),
            count: chart.data.datasets[0].data.length,
            closureMarker: chart.config.plugins[0].id};
    }""")
    assert chart_data["count"] == 586
    assert chart_data["portfolio"]["y"] > 0
    assert chart_data["benchmark"]["y"] is None
    assert chart_data["closureMarker"] == "benchmarkSessionClose"
    timings = page.evaluate("DashboardPerformance.snapshot()")
    assert any(sample["name"] == "intraday-synthesis" for sample in timings["samples"])
    assert any(sample["name"] == "intraday-render" and sample.get("status") == "ok"
               for sample in timings["samples"])
    assert any(sample["name"] == "api-parse" for sample in timings["samples"])
    assert "Benchmark closed 17:00" in page.locator("#intraday-comparison-status").inner_text()
    page.select_option("#intraday-comparison-window", "session")
    assert page.evaluate("Chart.getChart('intraday-comparison-chart').data.datasets[0].data.length") == 481
    assert page.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0
    assert not errors, errors


@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_intraday_baseline_note_is_a_compact_dismissible_tooltip(open_page, width, height):
    page, errors = open_page(width, height)
    tip = page.locator("#intraday-comparison-basis")
    button = page.locator(".intraday-info-btn")
    page.evaluate("document.documentElement.style.scrollBehavior = 'auto'")  # Playwright's hover scroll misfires with smooth scrolling
    button.evaluate("el => el.scrollIntoView({block: 'center'})")  # keep it clear of the sticky header
    assert not tip.is_visible()
    if width >= 768:  # touch viewports report hover: none, so only focus and tap open the tip there
        button.hover()
        page.wait_for_timeout(250)
        assert tip.is_visible()
        page.mouse.move(0, 0)
    button.focus()
    page.wait_for_timeout(250)
    assert tip.is_visible()
    assert "yesterday's close" in tip.inner_text()
    box = tip.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= width
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)
    assert not tip.is_visible()
    page.evaluate("document.activeElement.blur()")
    page.mouse.move(0, 0)
    button.evaluate("el => el.click()")  # a tap without focus or hover, as on iOS Safari
    page.wait_for_timeout(250)
    assert tip.is_visible()
    page.evaluate("document.body.click()")
    page.wait_for_timeout(250)
    assert not tip.is_visible()
    assert not errors, errors


def _tops(page, selectors):
    return [page.locator(f"#tab-dashboard {s}").first.bounding_box()["y"] for s in selectors]


def test_desktop_layout_order_matches_the_decisions(open_page):
    page, _ = open_page(1440, 900)
    main = ["section.hero", "section.bench", "section.ath-six", "section.summary"]
    ys = _tops(page, main)
    assert ys == sorted(ys), f"main column order is wrong: {dict(zip(main, ys))}"
    rail = _tops(page, ["section.movers", "section.accounts"])
    assert rail == sorted(rail)
    hero = page.locator("#tab-dashboard section.hero").bounding_box()
    assert page.locator("#tab-dashboard section.movers").bounding_box()["x"] > hero["x"] + hero["width"] - 40
    assert page.locator("#tab-dashboard section.accounts").bounding_box()["x"] > hero["x"] + hero["width"] - 40


def test_mobile_layout_order_matches_the_decisions(open_page):
    page, _ = open_page(390, 844)
    order = ["section.hero", "section.bench", "section.movers", "section.accounts", "section.ath-six", "section.summary"]
    ys = _tops(page, order)
    assert ys == sorted(ys), f"mobile order is wrong: {dict(zip(order, ys))}"
    assert page.locator("#tab-dashboard section.movers").bounding_box()["x"] < 40


def test_every_dashboard_value_is_still_present(open_page):
    page, _ = open_page(1440, 900)
    for selector in ("#dash-total-value", "#dash-daily-pln", "#gauge-lead", "#dash-ath-lake", "#monthly-return-val",
                     "#monthly-benchmarks-score", "#monthly-deposit-status", "#monthly-return-goal-status", "#dash-breakdown"):
        assert page.locator(selector).count() == 1, selector
    assert "PLN" in page.inner_text("#dash-total-value")
    assert page.locator("#dash-breakdown .m-row").count() >= 1
    assert page.locator("#gaugeChart").count() == 1


def test_ticker_tape_is_mounted_once(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator("[data-market-carousel]").count() == 1
    assert page.locator(".market-ticker-lane").count() == 1


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_dashboard_has_no_boxed_areas(open_page, width, height, theme):
    page, _ = open_page(width, height, theme)
    boxes = page.evaluate(FRAMELESS_SCAN)
    assert not boxes, "rounded boxes on the frameless dashboard (D-026):\n" + "\n".join(boxes)


@pytest.mark.parametrize("theme", THEMES)
def test_dashboard_sections_paint_no_background_rectangles(open_page, theme):
    page, _ = open_page(1440, 900, theme)
    filled = page.evaluate("""() => Array.from(document.querySelectorAll(
        '#tab-dashboard section, .market-index-carousel, .market-index-carousel-shell, .market-index-carousel-track'))
      .filter(el => { const s = getComputedStyle(el); return s.backgroundColor !== 'rgba(0, 0, 0, 0)' || s.backgroundImage !== 'none'; })
      .map(el => el.tagName.toLowerCase() + '.' + String(el.className).split(' ')[0])""")
    assert not filled, f"sections paint a fill (frame by another name): {filled}"


def test_dashboard_stays_frameless_with_everything_open(open_page):
    page, _ = open_page(1440, 900)
    page.locator(".roast-toggle").first.click()
    page.locator(".acct-toggle").first.click()
    page.locator("#monthly-benchmarks-btn").click()
    page.click("#tab-summary-yearly")
    boxes = page.evaluate(FRAMELESS_SCAN)
    assert not boxes, "\n".join(boxes)


def test_roast_reactions_stay_hidden_until_tapped(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator("#roast-reactions").is_hidden()
    page.locator(".roast-toggle").first.click()
    assert page.locator("#roast-reactions").is_visible()
    assert page.get_attribute(".roast-toggle", "aria-expanded") == "true"
    page.locator(".roast-toggle").first.click()
    assert page.locator("#roast-reactions").is_hidden()


def test_roast_message_does_not_use_the_legacy_banner_styles(open_page):
    page, _ = open_page(1440, 900)
    size = page.evaluate("parseFloat(getComputedStyle(document.querySelector('.roast-msg')).fontSize)")
    assert size >= 20, f"roast headline is only {size}px"
    assert page.locator(".bm-msg").count() == 0


def test_account_rows_expand_in_place(open_page):
    page, _ = open_page(1440, 900)
    toggle = page.locator(".acct-toggle").first
    panel_id = toggle.get_attribute("aria-controls")
    assert page.locator(f"#{panel_id}").is_hidden()
    toggle.click()
    assert page.locator(f"#{panel_id}").is_visible()
    assert toggle.get_attribute("aria-expanded") == "true"


def test_summary_switches_between_month_and_year(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator("#panel-summary-monthly").is_visible()
    assert page.locator("#panel-summary-yearly").is_hidden()
    page.click("#tab-summary-yearly")
    assert page.locator("#panel-summary-yearly").is_visible()
    assert page.locator("#panel-summary-monthly").is_hidden()
    assert page.get_attribute("#tab-summary-yearly", "aria-selected") == "true"
    page.focus("#tab-summary-yearly")
    page.keyboard.press("ArrowLeft")
    assert page.locator("#panel-summary-monthly").is_visible()
    assert page.evaluate("document.activeElement.id") == "tab-summary-monthly"


def test_benchmark_comparison_dropdown_still_opens(open_page):
    page, _ = open_page(1440, 900)
    page.click("#monthly-benchmarks-btn")
    assert page.locator("#monthly-benchmarks-dropdown").is_visible()


def test_floating_player_shows_the_total_and_scrolls_to_top(open_page):
    page, _ = open_page(1440, 900)
    player = page.locator("#tab-dashboard .d-player")
    assert player.is_visible()
    box = player.bounding_box()
    assert 0 <= box["y"] and box["y"] + box["height"] <= 900, f"the player is outside the viewport: {box}"
    page.evaluate("window.scrollTo(0, 600)")
    assert abs(player.bounding_box()["y"] - box["y"]) < 1, "the player must stay fixed while scrolling"
    assert page.inner_text("#dash-player-total").replace("\u00a0", " ") == page.inner_text("#dash-total-value").replace("\u00a0", " ")
    page.evaluate("window.scrollTo(0, 600)")
    page.click(".d-player-top")
    page.wait_for_function("window.scrollY < 5")


def test_sidebar_collapses_to_a_rail_and_remembers_it(open_page):
    page, _ = open_page(1440, 900)
    full = page.locator("#sidenav").bounding_box()["width"]
    page.click("#sidenav-collapse")
    page.wait_for_function("document.getElementById('sidenav').dataset.state === 'collapsed'")
    rail = page.locator("#sidenav").bounding_box()["width"]
    assert rail < full / 2 and rail >= 56
    assert page.get_attribute("#sidenav-collapse", "aria-pressed") == "true"
    assert page.evaluate("localStorage.getItem('roastfolio-sidebar')") == "collapsed"
    page.keyboard.press("Control+b")
    page.wait_for_function("document.getElementById('sidenav').dataset.state === 'expanded'")


def test_collapsed_sidebar_is_restored_on_load(open_page):
    page, _ = open_page(1440, 900, storage={"roastfolio-sidebar": "collapsed"})
    assert page.evaluate("document.getElementById('sidenav').dataset.state") == "collapsed"


def test_theme_switch_changes_the_page(open_page):
    page, _ = open_page(1440, 900, "dark")
    dark = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg-canvas').trim()")
    page.click('[data-theme-choice="light"]')
    assert page.evaluate("document.documentElement.dataset.theme") == "light"
    light = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg-canvas').trim()")
    assert dark and light and dark != light


def test_other_tabs_still_open_and_hide_the_dashboard(open_page):
    page, _ = open_page(1440, 900)
    page.evaluate("showTab('wallets')")
    assert page.locator("#tab-wallets").is_visible()
    assert page.locator("#tab-dashboard").is_hidden()
    assert page.locator("#tab-dashboard .d-player").is_hidden()
    page.evaluate("showTab('dashboard')")
    assert page.locator("#tab-dashboard").is_visible()


def test_mobile_uses_bottom_tabs_and_a_drawer(open_page):
    page, _ = open_page(390, 844)
    assert page.locator(".bottom-tabs").is_visible()
    assert page.locator("#sidenav").bounding_box()["x"] < 0 or not page.locator("#sidenav").is_visible()
    page.click(".bottom-tab[data-tab='wallets']")
    assert page.locator("#tab-wallets").is_visible()


def test_desktop_hides_the_bottom_tabs(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator(".bottom-tabs").is_hidden()


@pytest.mark.parametrize("width,height", [(1440, 900), (1024, 768), (768, 1024), (390, 844)])
def test_header_is_compact_and_groups_title_with_live_status(open_page, width, height):
    page, errors = open_page(width, height)
    header = page.locator(".brand-header").bounding_box()
    title = page.locator("#header-tab-indicator").bounding_box()
    status = page.locator("#live-data-status").bounding_box()
    assert header["height"] <= 52
    # Phones keep the menu button before the title; nothing else (no logo, no centred brand) sits in the row.
    lead = page.locator(".sidenav-toggle-btn").bounding_box()["width"] if width < 768 else 0
    assert title["x"] - header["x"] - lead <= 24
    assert page.locator(".brand-header .brand-logo-btn").is_hidden()
    assert page.locator(".brand-header .brand-title").is_hidden()
    commentary = page.locator("header .market-commentary")
    if commentary.is_visible() and commentary.inner_text().strip():
        assert commentary.evaluate("el => getComputedStyle(el).textAlign") in ("left", "start")
        assert abs(commentary.bounding_box()["x"] + 1 - (title["x"] if width >= 768 else header["x"] + 12)) <= 14
    assert 8 <= status["x"] - title["x"] - title["width"] <= 24
    assert abs(title["y"] + title["height"] / 2 - status["y"] - status["height"] / 2) <= 2
    page.evaluate("showTab('wallets')")
    assert page.locator("#header-tab-indicator").inner_text() == "Wallets"
    assert page.locator("#live-data-status").is_visible()
    assert not errors, errors


def test_header_wraps_long_status_without_overflow(open_page):
    page, _ = open_page(768, 1024)
    page.locator("#live-data-status").evaluate(
        "el => el.textContent = 'Using cached prices while refreshing. '.repeat(12)"
    )
    assert page.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0
    assert page.locator("#header-tab-indicator").is_visible()


@pytest.mark.parametrize("width,height", [(390, 844)])
def test_touch_targets_are_at_least_44px(open_page, width, height):
    page, _ = open_page(width, height)
    small = [f"{t['label']!r} ({t['cls']}) {t['w']:.0f}x{t['h']:.0f}" for t in page.evaluate(COLLECT_TARGETS)
             if t["h"] < MIN_TARGET or t["w"] < MIN_TARGET]
    assert not small, "targets below 44px:\n" + "\n".join(small)


def test_reduced_motion_stops_the_ticker(open_page):
    page, _ = open_page(1440, 900, reduced=True)
    assert page.evaluate("getComputedStyle(document.querySelector('.market-ticker-lane')).animationName") == "none"


def test_phone_hero_puts_roast_and_gauge_side_by_side(open_page):
    page, _ = open_page(390, 844)
    roast = page.locator("#gauge-benchmark-tooltip").bounding_box()
    gauge = page.locator("#gaugeChart").bounding_box()
    total = page.locator("#dash-total-value").bounding_box()
    assert roast["x"] + roast["width"] <= gauge["x"]
    assert gauge["y"] < roast["y"] + roast["height"] and roast["y"] < gauge["y"] + gauge["height"]
    assert total["y"] > max(roast["y"] + roast["height"], gauge["y"] + gauge["height"])
    canvas = page.evaluate("() => { const c = document.getElementById('gaugeChart'); const r = c.getBoundingClientRect(); return [c.width, c.height, r.width, r.height]; }")
    assert abs(canvas[0] / canvas[1] - canvas[2] / canvas[3]) < 0.05  # drawn at its displayed size, not stretched


def _set_ath(page, ath_value):
    page.evaluate("""ath => { window._SNAPSHOT_ATH = null; window.PORTFOLIO_ATH = {athValue: ath, athDate: '2026-10-01'};
        renderSummaryCards(); renderAthCelebration('dash-ath-celebration'); }""", ath_value)
    page.wait_for_timeout(1400)


def _lake(page):
    return page.evaluate("""() => { const box = s => document.querySelector('#dash-ath-lake ' + s).getBoundingClientRect().toJSON();
        const lake = document.getElementById('dash-ath-lake');
        return { state: lake.dataset.state, label: lake.getAttribute('aria-label'), lake: lake.getBoundingClientRect().toJSON(),
                 ath: box('.lake-ath'), now: box('.lake-now'), athTag: box('.lake-ath .lake-tag'), nowTag: box('.lake-tag-now'),
                 nowText: document.querySelector('#dash-ath-lake .lake-tag-now').textContent }; }""")


def _overlap(a, b):
    return a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"] and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]


@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_lake_shows_small_drawdowns_and_rises_above_the_ath(open_page, width, height):
    page, errors = open_page(width, height)
    total = page.evaluate("PORTFOLIO_TOTAL_VALUE")
    _set_ath(page, round(total / (1 - 0.003), 2))  # 0.3% under the high: invisible on the old linear scale
    lake = _lake(page)
    assert lake["state"] == "below" and lake["lake"]["width"] >= 300
    assert lake["now"]["y"] - lake["ath"]["y"] >= 15
    assert lake["nowText"] == "now −0.30%"
    assert not _overlap(lake["athTag"], lake["nowTag"])
    assert "0.30% below" in lake["label"]

    deep = _lake(page) if not _set_ath(page, total * 2) else None
    assert lake["now"]["y"] < deep["now"]["y"] <= deep["lake"]["y"] + deep["lake"]["height"]

    _set_ath(page, round(total / 1.012, 2))
    above = _lake(page)
    assert above["state"] == "above" and above["now"]["y"] < above["ath"]["y"] - 15
    assert not _overlap(above["athTag"], above["nowTag"])
    assert page.locator("#dash-ath-lake .lake-peak").evaluate("el => getComputedStyle(el).opacity") == "1"
    assert not errors, errors


def test_new_ath_banner_breaks_out_once_per_record(open_page):
    page, errors = open_page(1440, 900)
    _set_ath(page, round(page.evaluate("PORTFOLIO_TOTAL_VALUE") - 183, 2))
    banner = page.locator("#dash-ath-celebration")
    assert banner.is_visible()
    assert banner.locator(".ath20-badge").inner_text().lower() == "new all-time high"
    assert "+183 PLN above the previous peak" in banner.locator(".ath20-meta").inner_text()
    page.wait_for_timeout(300)
    assert page.locator("#dash-ath-celebration .ath20-line").evaluate("el => parseFloat(getComputedStyle(el).strokeDashoffset)") < 0.01  # fully drawn
    page.evaluate("document.querySelector('#dash-ath-celebration .ath20').dataset.marker = 'kept'")
    page.evaluate("renderDashboard()")
    assert page.evaluate("document.querySelector('#dash-ath-celebration .ath20').dataset.marker") == "kept"  # no replay on refresh
    page.evaluate("window.PORTFOLIO_ATH = {athValue: PORTFOLIO_TOTAL_VALUE * 2, athDate: '2026-10-01'}; renderAthCelebration('dash-ath-celebration')")
    assert banner.is_hidden()
    assert not errors, errors


def test_clicking_roastfolio_logo_triggers_refresh_live_prices(open_page):
    page, errors = open_page(1440, 900)
    page.evaluate("""() => {
        window.__refreshCallCount = 0;
        const orig = window.refreshLivePrices;
        window.refreshLivePrices = function() {
            window.__refreshCallCount++;
            return orig ? orig() : Promise.resolve();
        };
    }""")
    page.locator(".sidenav-header .sidenav-brand").click()
    assert page.evaluate("window.__refreshCallCount") == 1
    assert not errors, errors
