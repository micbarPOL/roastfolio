"""Optional browser regressions: requires playwright and its Chromium runtime."""
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def browser():
    with playwright.sync_playwright() as runtime:
        instance = runtime.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    tab = context.new_page()
    tab.goto((ROOT / "tests/monthly-audit.browser.html").as_uri())
    results = tab.evaluate("window.fixtureReady")
    assert len(results) == 16 and all(result["passed"] for result in results), results
    yield tab
    context.close()


@pytest.mark.parametrize("width", [360, 390, 768, 1024, 1440])
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_responsive_bento_and_contrast(page, width, theme):
    page.set_viewport_size({"width": width, "height": 1000})
    page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
    geometry = page.evaluate("""() => ({
        overflow: document.documentElement.scrollWidth > innerWidth,
        title: getComputedStyle(document.querySelector('.monthly-audit-hero h1')).color,
        journey: document.querySelector('.ma-journey').getBoundingClientRect().toJSON(),
        milestones: document.querySelector('.ma-milestones').getBoundingClientRect().toJSON(),
    })""")
    assert not geometry["overflow"]
    assert geometry["title"] == "rgb(28, 44, 34)"
    assert page.locator('.ma-return-grid-label').evaluate_all("es => es.every(e => e.getBBox().x >= e.ownerSVGElement.viewBox.baseVal.x)")
    if width <= 768:
        assert geometry["milestones"]["top"] >= geometry["journey"]["bottom"]
    elif width > 1050:
        assert geometry["journey"]["width"] > 1.8 * geometry["milestones"]["width"]
    page.get_by_role("button", name="Share recap", exact=True).click()
    page.locator("[data-download]:enabled").wait_for()
    assert page.locator("[data-private]").is_checked()
    bounds = page.locator("dialog").bounding_box()
    assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width + 1
    assert page.locator("dialog").evaluate("e => e.scrollWidth <= e.clientWidth + 1")
    output = ROOT / "tmp"
    output.mkdir(exist_ok=True)
    if width in (390, 1440):
        page.screenshot(path=str(output / f"monthly-share-{theme}-{width}.png"))
    page.keyboard.press("Escape")
    page.locator("dialog").wait_for(state="detached")
    assert page.get_by_role("button", name="Share recap", exact=True).evaluate("e => e === document.activeElement")
    page.evaluate("scrollTo(0, 0)")
    if width in (390, 1440):
        page.screenshot(path=str(output / f"monthly-bento-{theme}-{width}.png"), full_page=True)


def test_private_png_download_and_explicit_amount_opt_in(page, tmp_path):
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    page.evaluate("Object.defineProperty(navigator, 'canShare', {configurable:true,value:()=>false})")
    page.get_by_role("button", name="Share recap", exact=True).click()
    download_button = page.locator("[data-download]:enabled")
    download_button.wait_for()
    assert page.locator("[data-share]").is_hidden()
    assert "PLN amounts hidden" in page.locator("canvas").get_attribute("aria-label")
    with page.expect_download() as pending:
        download_button.click()
    private_download = pending.value
    assert private_download.suggested_filename == "roastfolio-2026-08-private.png"
    private_path = tmp_path / "private.png"
    private_download.save_as(private_path)
    content = private_path.read_bytes()
    assert content[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(content[16:20], "big") == 1080
    assert int.from_bytes(content[20:24], "big") == 1350
    page.locator("[data-private]").uncheck()
    download_button.wait_for()
    assert "+24,680 PLN" in page.locator("canvas").get_attribute("aria-label")
    with page.expect_download() as pending:
        download_button.click()
    assert pending.value.suggested_filename == "roastfolio-2026-08.png"
    public_path = tmp_path / "public.png"
    pending.value.save_as(public_path)
    assert public_path.read_bytes() != content
    page.keyboard.press("Escape")
    page.locator("dialog").wait_for(state="detached")
    page.get_by_role("button", name="Share recap", exact=True).click()
    download_button.wait_for()
    assert page.locator("[data-private]").is_checked()
    assert requests == []


def test_native_share_user_activation_cancel_and_failure(page):
    page.evaluate("""() => {
        Object.defineProperty(navigator,'canShare',{configurable:true,value:({files}) => files[0] instanceof File});
        Object.defineProperty(navigator,'share',{configurable:true,value:async ({files}) => {
            window.shared = {name:files[0].name,type:files[0].type,size:files[0].size,active:navigator.userActivation.isActive};
            if (window.shareFailure) throw new DOMException('Test cancellation',window.shareFailure);
        }});
    }""")
    downloads = []
    page.on("download", lambda event: downloads.append(event))
    page.get_by_role("button", name="Share recap", exact=True).click()
    share = page.locator("[data-share]:enabled")
    share.wait_for()
    share.click()
    assert "handed" in page.locator(".monthly-share-status").inner_text()
    data = page.evaluate("window.shared")
    assert data["active"] and data["type"] == "image/png" and data["size"] > 10000
    assert data["name"].endswith("-private.png")
    page.evaluate("window.shareFailure = 'AbortError'")
    share.click()
    assert "cancelled" in page.locator(".monthly-share-status").inner_text()
    page.evaluate("window.shareFailure = 'NotAllowedError'")
    share.click()
    assert "Download the PNG instead" in page.locator(".monthly-share-status").inner_text()
    assert downloads == []
    assert page.locator("[data-private]").is_enabled()


def test_missing_sparse_and_long_values(page):
    page.evaluate("""async () => {
        window.MONTHLY_WRAP_DATA = [{...monthlyFixture, period:'2026-09',
            overall_nominal_change_pln:12345678901234,
            journey:null,market_context:null,trading_activity:null,
            drawdown_trajectory_pct:[null,null],trajectory_delta_pp:null}];
        await initMonthlyAudit(true);
    }""")
    assert "Dated return history unavailable" in page.locator(".ma-journey").inner_text()
    assert page.locator(".ma-return-chart").count() == 0
    assert page.locator(".monthly-audit-trajectory").count() == 0
    assert page.locator(".ma-journey-endpoints strong").last.inner_text() == "No data"
    page.set_viewport_size({"width": 360, "height": 900})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator(".ma-nominal strong").evaluate("e => e.scrollWidth <= e.clientWidth + 1")
    page.evaluate("""async () => {
        window.MONTHLY_WRAP_DATA = [{...monthlyFixture,period:'2026-09',drawdown_trajectory_pct:[0,-1,null,-4,-2]}];
        await initMonthlyAudit(true);
    }""")
    page.locator('.ma-return-chart').focus()
    page.keyboard.press('Home')
    page.keyboard.press('ArrowRight')
    page.keyboard.press('ArrowRight')
    assert page.locator(".trajectory-line").count() == 2
    assert page.locator("#ma-journey-value").inner_text() == "2026-08-10 · Portfolio -1.5% · MSCI World · IWDA proxy +0.5%"


def render_case(page, overrides):
    page.evaluate("""async overrides => {
        window.MONTHLY_WRAP_DATA = [{...monthlyFixture, ...overrides, period:'2026-09'}];
        await initMonthlyAudit(true);
    }""", overrides)


@pytest.mark.parametrize("total,leader,anchor", [
    (24680, 8940, -1260), (300, 1200, -900), (-100, 300, -400),
    (0, 100, -100), (0, 0, 0), (100, 80, 20), (-100, -20, -80),
    (None, None, None),
])
def test_movers_share_symmetric_zero_and_pln_scale(page, total, leader, anchor):
    render_case(page, {"overall_nominal_change_pln": total,
                       "carry": {"ticker": "LEADER", "net_contribution_pln": leader},
                       "anchor": {"ticker": "ANCHOR", "net_contribution_pln": anchor}})
    scale = max(abs(total or 0), abs(leader or 0), abs(anchor or 0), 1)
    tracks = page.locator(".ma-contribution-track")
    widths = tracks.evaluate_all("es => es.map(e => e.getBoundingClientRect().width)")
    assert widths[0] == pytest.approx(widths[1])
    zeros = tracks.locator(".ma-track-zero").evaluate_all("es => es.map(e => e.getBoundingClientRect().x)")
    assert zeros[0] == pytest.approx(zeros[1])
    for index, value in enumerate([leader, anchor]):
        track = tracks.nth(index)
        fill = track.locator(".ma-contribution-fill")
        if value is None:
            assert fill.count() == 0
        else:
            position = fill.evaluate("e => ({left:parseFloat(e.style.left),width:parseFloat(e.style.width)})")
            assert position["left"] == pytest.approx(min(50, 50 + value / scale * 50))
            assert position["width"] == pytest.approx(abs(value) / scale * 50, abs=0.0001)
            assert 0 <= position["left"] <= 100
            assert position["left"] + position["width"] <= 100.001
        marker = track.locator(".ma-month-marker")
        if total is None:
            assert marker.count() == 0
        else:
            assert marker.evaluate("e => parseFloat(e.style.left)") == pytest.approx(50 + total / scale * 50)
    assert "Month total" in page.locator(".ma-month-reference").inner_text()
    assert "not necessarily the month total" in page.locator(".ma-movers").inner_text()


@pytest.mark.parametrize("actual,goal", [(300, 100), (-300, 100), (50, 100), (0, 100), (None, 100), (300, None)])
def test_target_has_one_meaningful_signed_track(page, actual, goal):
    render_case(page, {"retirement_target": {"plan_id": "test", "monthly_target_nominal_pln": goal,
                                            "actual_nominal_gain_pln": actual, "pct_achieved": 99999}})
    assert page.locator(".ma-goal svg, .monthly-audit-ring, .monthly-audit-progress").count() == 0
    track = page.locator(".ma-target-track")
    if actual is None or goal is None:
        assert track.count() == 0
        assert page.locator(".ma-target-percent").inner_text() == "No data"
        return
    assert track.count() == 1
    assert page.locator(".ma-target-percent").inner_text() == f"{round(actual / goal * 100):,}%"
    scale = max(goal, abs(actual), 1)
    minimum = -scale if actual < 0 else 0
    marker = page.locator(".ma-target-marker").evaluate("e => parseFloat(e.style.left)")
    assert marker == pytest.approx((goal - minimum) / (scale - minimum) * 100)
    fill = page.locator(".ma-target-fill").evaluate("e => ({left:parseFloat(e.style.left),width:parseFloat(e.style.width)})")
    assert fill["width"] == pytest.approx(abs(actual) / (scale - minimum) * 100)
    if actual < 0:
        assert fill["left"] < 50 and fill["left"] + fill["width"] == pytest.approx(50)


def test_journey_uses_real_dates_return_values_and_independent_null_gaps(page):
    assert page.locator(".ma-return-portfolio").count() == 2
    assert page.locator(".ma-return-benchmark").count() == 1
    points = page.locator(".ma-return-portfolio circle").evaluate_all("es => es.map(e => ({x:+e.getAttribute('cx'),y:+e.getAttribute('cy')}))")
    assert points[1]["x"] - points[0]["x"] == pytest.approx(560 * 3 / 31)
    assert points[2]["x"] - points[1]["x"] == pytest.approx(560 * 6 / 31)
    assert points[2]["y"] > points[0]["y"]  # Negative TWR is below zero, not clamped.
    before = page.locator(".ma-return-series path").evaluate_all("es => es.map(e => e.getAttribute('d'))")
    render_case(page, {"deposits_pln": 999999999, "overall_nominal_change_pln": 999999999})
    after = page.locator(".ma-return-series path").evaluate_all("es => es.map(e => e.getAttribute('d'))")
    assert before == after
    page.locator(".ma-return-chart").focus()
    page.keyboard.press("ArrowRight")
    assert "2026-08-04 · Portfolio +2.1%" in page.locator("#ma-journey-value").inner_text()
    legend = page.locator(".ma-return-legend").inner_text()
    assert "Portfolio · cumulative TWR" in legend and "MSCI World" in legend and "EUR" in legend
    assert "not converted to PLN" in page.locator(".ma-journey").inner_text()
    assert page.locator(".ma-journey details").get_attribute("open") is None


def test_missing_benchmark_does_not_become_a_zero_line(page):
    journey = page.evaluate("({...monthlyFixture.journey, points:monthlyFixture.journey.points.map(p=>({...p,benchmark_pct:null}))})")
    render_case(page, {"journey": journey})
    assert page.locator(".ma-return-benchmark").count() == 0
    assert page.locator(".ma-return-portfolio").count() == 2
    assert "Benchmark return history unavailable" in page.locator(".ma-journey").inner_text()


def test_chart_hover_crosshair_tooltip_and_keyboard(page):
    chart = page.get_by_role('slider', name='Dated cumulative returns')
    assert page.locator('input[type="range"]').count() == 0
    point = page.locator('.ma-return-portfolio circle').nth(2)
    point.hover()
    tooltip = page.get_by_role('tooltip')
    assert tooltip.inner_text() == '2026-08-10 · Portfolio -1.5% · MSCI World · IWDA proxy +0.5%'
    assert chart.get_attribute('aria-valuenow') == '2'
    assert page.locator('.ma-cursor-benchmark').get_attribute('visibility') == 'visible'
    crosshair = page.locator('.ma-return-crosshair').get_attribute('d')
    x = float(point.get_attribute('cx'))
    assert crosshair == f'M{x} 22 V190'
    page.locator('.ma-wordmark').hover()
    assert tooltip.is_hidden()
    chart.focus()
    assert tooltip.is_visible()
    for key, index, date in [('Home', '0', '2026-08-01'), ('ArrowLeft', '0', '2026-08-01'),
                             ('End', '5', '2026-09-01'), ('ArrowRight', '5', '2026-09-01'),
                             ('ArrowLeft', '4', '2026-08-20')]:
        page.keyboard.press(key)
        assert chart.get_attribute('aria-valuenow') == index
        assert date in tooltip.inner_text()
        assert chart.get_attribute('aria-valuetext') == tooltip.inner_text()
    page.keyboard.press('Escape')
    assert tooltip.is_hidden()
    assert page.locator('.ma-return-cursor').get_attribute('visibility') == 'hidden'
    page.keyboard.press('ArrowLeft')
    assert 'Portfolio No data' in tooltip.inner_text()
    assert page.locator('.ma-cursor-portfolio').get_attribute('visibility') == 'hidden'
    assert page.locator('.ma-cursor-benchmark').get_attribute('visibility') == 'visible'
    page.keyboard.press('Tab')
    assert tooltip.is_hidden()
    assert 'Portfolio boundary' not in page.locator('.ma-journey').inner_text()
    assert 'Benchmark quotes' not in page.locator('.ma-journey').inner_text()


def test_chart_mobile_touch_and_tooltip_overflow(browser):
    context = browser.new_context(viewport={'width': 360, 'height': 900}, has_touch=True, is_mobile=True)
    try:
        page = context.new_page()
        page.goto((ROOT / 'tests/monthly-audit.browser.html').as_uri())
        assert all(result['passed'] for result in page.evaluate('window.fixtureReady'))
        point = page.locator('.ma-return-portfolio circle').nth(2)
        point.tap()
        assert '2026-08-10' in page.get_by_role('tooltip').inner_text()
        assert '+0.5%' in page.get_by_role('tooltip').inner_text()
        assert page.locator('.ma-return-chart').get_attribute('aria-valuenow') == '2'
        assert page.locator('.ma-return-chart').evaluate("e => getComputedStyle(e).touchAction") == 'pan-y'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.get_by_role('tooltip').evaluate('e => e.scrollWidth <= e.clientWidth + 1')
    finally:
        context.close()


@pytest.mark.parametrize('values', [[0, 0], [0, 3], [-3, 0], [-3, 3]])
@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_chart_zero_grid_is_solid_distinct_and_not_duplicated(page, values, theme):
    render_case(page, {'journey': {'benchmark_id': 'WIG', 'points': [
        {'date': '2026-08-01', 'portfolio_pct': values[0], 'benchmark_pct': None},
        {'date': '2026-09-01', 'portfolio_pct': values[1], 'benchmark_pct': None},
    ]}})
    page.evaluate('theme => document.documentElement.dataset.theme = theme', theme)
    zero = page.locator('.ma-return-zero')
    assert zero.count() == 1
    style = zero.evaluate('e => ({dash:getComputedStyle(e).strokeDasharray,width:getComputedStyle(e).strokeWidth,color:getComputedStyle(e).stroke})')
    assert style['dash'] == 'none' and style['width'] == '2px'
    for extreme in page.locator('.ma-return-extreme').all():
        other = extreme.evaluate('e => ({dash:getComputedStyle(e).strokeDasharray,color:getComputedStyle(e).stroke})')
        assert other['dash'] != 'none' and other['color'] != style['color']
    labels = page.locator('.ma-return-grid-label').all_text_contents()
    assert labels.count('0.0%') == 1 and len(set(labels)) == len(labels)
    assert page.locator('.ma-return-benchmark').count() == 0


@pytest.mark.parametrize('value', [-2, 0, 2])
@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_wordmark_and_subtle_pattern_preserve_bright_cover(page, value, theme):
    render_case(page, {'overall_twr_pct': value})
    page.evaluate('theme => document.documentElement.dataset.theme = theme', theme)
    assert page.locator('.ma-wordmark').inner_text() == 'roastfolio'
    assert page.locator('.ma-cover-glyph').count() == 0
    styles = page.locator('.monthly-audit-hero').evaluate("""e => ({
        background:getComputedStyle(e).backgroundColor,
        pattern:getComputedStyle(e,'::after').backgroundImage,
        ink:getComputedStyle(e.querySelector('.ma-wordmark')).color,
    })""")
    assert styles['background'] == {-2: 'rgb(242, 197, 176)', 0: 'rgb(212, 202, 242)', 2: 'rgb(208, 245, 176)'}[value]
    assert styles['ink'] == 'rgb(28, 44, 34)'
    assert 'radial-gradient' in styles['pattern']


def test_share_journey_allowlist_valid_dates_numbers_and_safe_metadata(page):
    model = page.evaluate("""() => MonthlyAuditPresentation.buildModel({...monthlyFixture, journey:{
        ...monthlyFixture.journey, benchmark_name:'SECRET-NAME', benchmark_currency:'SECRET-CURRENCY',
        account:{balance:123456}, secret:'SECRET-JOURNEY', points:[
            {date:'2026-08-01',portfolio_pct:0,benchmark_pct:'0',secret:'SECRET-POINT'},
            {date:'2026-08-03',portfolio_pct:'2.5',benchmark_pct:null},
            {date:'2026-08-04',portfolio_pct:null,benchmark_pct:-1},
            {date:'2026-08-05',portfolio_pct:Infinity,benchmark_pct:NaN},
            {date:'2026-08-06',portfolio_pct:true,benchmark_pct:' '},
            {date:'2026-02-30',portfolio_pct:123456,benchmark_pct:123456},
            {date:'SECRET-DATE',portfolio_pct:123456,benchmark_pct:123456}, null
        ]}})""")
    assert model['schemaVersion'] == 2 and 'trajectory' not in model
    journey = model['journey']
    assert set(journey) == {'benchmark_id', 'benchmark_name', 'benchmark_currency', 'points'}
    assert journey['benchmark_name'] == 'MSCI World · IWDA proxy' and journey['benchmark_currency'] == 'EUR'
    assert len(journey['points']) == 5
    assert journey['points'][0] == {'date': '2026-08-01', 'portfolio_pct': 0, 'benchmark_pct': 0}
    assert journey['points'][1]['portfolio_pct'] == 2.5 and journey['points'][1]['benchmark_pct'] == 0
    assert journey['points'][2]['portfolio_pct'] is None and journey['points'][2]['benchmark_pct'] == -1
    for point in journey['points'][3:]:
        assert point['portfolio_pct'] is None and point['benchmark_pct'] == -1
    assert 'SECRET' not in str(model) and '123456' not in str(model)
    unknown = page.evaluate("MonthlyAuditPresentation.buildModel({journey:{benchmark_id:'__proto__',benchmark_name:'SECRET'}}).journey")
    assert unknown == {'benchmark_id': None, 'benchmark_name': 'Benchmark', 'benchmark_currency': None, 'points': []}


def test_share_canvas_draws_dated_return_lines_and_retains_drawdown_text(page):
    drawing = page.evaluate("""() => {
        const canvas = document.createElement('canvas'), ctx = canvas.getContext('2d');
        const labels = [], strokes = [];
        let path = [];
        const spy = new Proxy(ctx, {
            get(target, key) {
                const value = target[key];
                if (typeof value !== 'function') return value;
                return (...args) => {
                    if (key === 'fillText') labels.push(args[0]);
                    if (key === 'beginPath') path = [];
                    if (key === 'moveTo' || key === 'lineTo') path.push([key,...args]);
                    if (key === 'stroke') strokes.push({color:target.strokeStyle,dash:target.getLineDash(),path:[...path]});
                    return value.apply(target,args);
                };
            }, set(target,key,value) {target[key]=value;return true;}
        });
        const poster = {getContext:()=>spy};
        MonthlyAuditPresentation.drawPoster(poster, MonthlyAuditPresentation.buildModel(monthlyFixture));
        return {labels,lines:strokes.filter(s => ['#b8e4ca','#d0c5f4'].includes(s.color) && s.path.some(p=>p[2]>=930))};
    }""")
    assert 'roastfolio' in drawing['labels'] and 'CUMULATIVE RETURNS' in drawing['labels']
    assert '2026-08-01' in drawing['labels'] and '2026-09-01' in drawing['labels']
    assert 'Portfolio · cumulative TWR' in drawing['labels']
    assert any('MSCI World' in label for label in drawing['labels'])
    assert any(label.startswith('Max drawdown') for label in drawing['labels'])
    assert not any('Drawdown through' in label for label in drawing['labels'])
    assert len(drawing['lines']) == 2
    portfolio, benchmark = drawing['lines']
    assert portfolio['dash'] == [] and benchmark['dash'] != []
    assert sum(point[0] == 'moveTo' for point in portfolio['path']) == 2  # Portfolio retains gaps.
    assert sum(point[0] == 'moveTo' for point in benchmark['path']) == 1  # Benchmark is extrapolated without gaps.
    points = portfolio['path']
    assert points[1][1] - points[0][1] == pytest.approx(858 * 3 / 31)
    assert points[2][2] > points[0][2]  # Negative returns below zero, not clamped.


def test_bigger_picture_currencies_calendars_and_seasonality(page):
    rows = page.locator(".ma-market-row")
    assert rows.count() == 6
    assert rows.evaluate_all("es => es.map(e => e.dataset.marketId)") == ["WIG", "DAX", "FTSE100", "SP500", "NASDAQ", "MSCI_WORLD"]
    assert page.locator('.ma-market-group h3').all_text_contents() == ["Poland", "Europe", "US", "World"]
    expected = {"WIG": ("Poland", "PLN"), "MSCI_WORLD": ("World", "EUR"), "SP500": ("US", "USD"),
                "NASDAQ": ("US", "USD"), "DAX": ("Europe", "EUR"), "FTSE100": ("Europe", "GBP")}
    for market_id, (region, currency) in expected.items():
        row = page.locator(f'[data-market-id="{market_id}"]')
        assert currency in row.inner_text()
        assert row.evaluate("e => e.closest('section').getAttribute('aria-label')") == region
        assert row.locator('p, small').count() == 0
    text = page.locator('.ma-seasonality').inner_text()
    for removed in ('Portfolio boundary', 'Market quotes', 'ahead of', 'behind this market'):
        assert removed not in text
    assert page.locator('.ma-seasonality > .ma-footnote').count() == 1
    assert 'native currencies (not PLN-adjusted)' in text
    assert "No data" in page.locator('[data-market-id="FTSE100"] b').inner_text()
    assert "August was negative" in page.locator(".monthly-audit-seasonality").inner_text()


def test_market_context_fetches_and_populates_missing_benchmark_returns(page):
    page.evaluate("""() => {
        window.PortfolioClient = {
            getBenchmarkReturns: async (benchmarkId, from) => ({
                benchmarkId,
                returns: [
                    { month: '2026-08', returnPct: benchmarkId === 'FTSE100' ? 2.34 : 1.5 }
                ]
            })
        };
    }""")
    page.evaluate("() => window.loadMonthlyAuditBenchmarkReturns(true)")
    assert "+2.34%" in page.locator('[data-market-id="FTSE100"] b').inner_text()
    assert "is-positive" in page.locator('[data-market-id="FTSE100"] b').get_attribute("class")


def test_global_market_verdict_one_liner(page):
    # Case 1: Better than global market (portfolio 10% vs MSCI World 4%)
    render_case(page, {
        "overall_twr_pct": 10.0,
        "market_context": [{"id": "MSCI_WORLD", "return_pct": 4.0}],
    })
    verdict = page.locator('#ma-global-market-verdict')
    assert "better than global market" in verdict.locator('.ma-verdict-badge').inner_text().lower()
    assert "You were better than the global market" in verdict.locator('.ma-verdict-copy').inner_text()
    assert "+6.0 pp" in verdict.locator('.ma-verdict-copy').inner_text()
    assert "is-positive" in verdict.get_attribute("class")

    # Case 2: Behind global market (portfolio 2% vs MSCI World 5%)
    render_case(page, {
        "overall_twr_pct": 2.0,
        "market_context": [{"id": "MSCI_WORLD", "return_pct": 5.0}],
    })
    assert "behind global market" in verdict.locator('.ma-verdict-badge').inner_text().lower()
    assert "You were behind the global market" in verdict.locator('.ma-verdict-copy').inner_text()
    assert "3.0 pp" in verdict.locator('.ma-verdict-copy').inner_text()
    assert "is-caution" in verdict.get_attribute("class")


def test_trading_activity_and_missing_vs_confirmed_zero(page):
    text = page.locator(".ma-trading").inner_text()
    for expected in ("Trading activity", "1,400 PLN", "1,000 PLN", "400 PLN", "Dividends received", "+25 PLN", "2026-08-12", "NVDA"):
        assert expected.lower() in text.lower()
    assert page.locator(".ma-transactions li").count() == 2
    assert page.locator(".ma-process, .ma-cover-seal").count() == 0
    render_case(page, {"trading_activity": None})
    text = page.locator(".ma-trading").inner_text()
    assert "0 PLN" not in text and "No data" in text
    assert "Dividend data unavailable" in text and "Transaction details unavailable" in text
    render_case(page, {"trading_activity": {"buy_total_pln": 0, "sell_total_pln": 0, "turnover_pln": 0,
                                          "dividend_total_pln": 0, "transaction_count": 0, "largest_transactions": []}})
    text = page.locator(".ma-trading").inner_text()
    assert "0 PLN" in text and "No BUY or SELL transactions this month" in text
    assert "Dividends received" not in text and "Dividend data unavailable" not in text


def test_schema_fields_are_escaped_and_never_copied_into_share_model(page):
    sentinel = '<img src=x onerror="window.identityLeaked=true">'
    render_case(page, {"userId": "SECRET-IDENTITY", "journey": {"benchmark_name": sentinel},
                       "trading_activity": {"largest_transactions": [{"ticker": sentinel, "date": sentinel, "type": "BUY", "value_pln": 1}]}})
    assert page.locator("#monthly-audit-root img").count() == 0
    model = page.evaluate("JSON.stringify(MonthlyAuditPresentation.buildModel(MONTHLY_WRAP_DATA[0]))")
    assert "SECRET-IDENTITY" not in model and "onerror" not in model and "largest_transactions" not in model


def test_localhost_three_month_schema_and_screenshots(page):
    import re

    html = (ROOT / "src/index.html").read_text()
    mock = next(block for block in re.findall(r"<script>(.*?)</script>", html, re.S) if "window.MONTHLY_WRAP_DATA =" in block)
    page.evaluate(mock)
    items = page.evaluate("window.MONTHLY_WRAP_DATA")
    assert {item["period"] for item in items} == {"2026-06", "2026-07", "2026-08"}
    opening_value = 10000
    for item in items:
        journey = item["journey"]
        assert journey["points"][0]["date"] == journey["start_date"]
        assert journey["points"][-1]["date"] == journey["end_date"]
        assert journey["points"][-1]["portfolio_pct"] == item["overall_twr_pct"]
        # Legacy demo records may omit WIG; the UI still renders six slots honestly.
        assert {market['id'] for market in item['market_context']} >= {"DAX", "FTSE100", "SP500", "NASDAQ", "MSCI_WORLD"}
        activity = item["trading_activity"]
        assert activity["turnover_pln"] == activity["buy_total_pln"] + activity["sell_total_pln"]
        assert activity["transaction_count"] == len(activity["largest_transactions"])
        assert sum(wallet["cash_flow_pln"] for wallet in item["wallet_performance"]) == item["deposits_pln"] - item["withdrawals_pln"]
        assert item["overall_nominal_change_pln"] == pytest.approx(opening_value * item["overall_twr_pct"] / 100)
        opening_value += item["overall_nominal_change_pln"] + item["deposits_pln"] - item["withdrawals_pln"]
        assert item["ath_value_pln"] == pytest.approx(opening_value)
    page.evaluate("initMonthlyAudit(true)")
    assert page.locator(".ma-target-percent").inner_text() == "300%"
    output = ROOT / "tmp"
    output.mkdir(exist_ok=True)
    for period in ["2026-06", "2026-07", "2026-08"]:
        page.evaluate("period => selectMonthlyAuditPeriod(period)", period)
        for theme, width in [("dark", 1440), ("light", 390)]:
            page.set_viewport_size({"width": width, "height": 1000})
            page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / f"monthly-recap-{period}-{theme}-{width}.png"), full_page=True)