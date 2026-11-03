"""Statistics mockup only: financial consistency, filters, keyboard and offline rendering."""
import io
import re
import sys
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "design"))
import design_system as ds

sync_api = pytest.importorskip("playwright.sync_api")
pytestmark = [pytest.mark.design, pytest.mark.browser]
URL = (ROOT / "design/mockups/statistics.html").as_uri()
VIEWPORTS = [(1440, 900), (1024, 768), (768, 1024), (390, 844)]


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        instance = playwright.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def open_statistics(browser):
    contexts = []

    def open_page(width=1440, height=900, theme="dark", state=None, reduced=False):
        context = browser.new_context(viewport={"width": width, "height": height},
                                      has_touch=width < 768,
                                      reduced_motion="reduce" if reduced else "no-preference")
        contexts.append(context)
        context.route(re.compile(r"^https?://"), lambda route: route.abort())
        page = context.new_page()
        errors, external = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: external.append(request.url) if request.url.startswith("http") else None)
        page.goto(f"{URL}?theme={theme}" + (f"&state={state}" if state else ""))
        page.wait_for_function("Boolean(window.statisticsMockup)")
        assert not errors, errors
        assert not external, external
        return page

    yield open_page
    for context in contexts:
        context.close()


def financial_number(text):
    return float(text.replace(",", "").replace(" PLN", "").replace("%", "").replace(" pp", ""))


def show_snapshots(page):
    page.locator('[data-field="statistics-snapshots"] > summary').click()


@pytest.mark.parametrize("width,height", VIEWPORTS)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_statistics_offline_layout_tokens_and_rendered_charts(open_statistics, width, height, theme):
    page = open_statistics(width, height, theme)
    assert page.locator("html").get_attribute("data-theme") == theme
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator('.sidebar-nav [aria-current="page"]').get_attribute("data-field") == "nav-statistics"
    assert page.locator('[data-field="nav-portfolio"]').get_attribute("aria-current") is None
    assert page.locator('span.nav-item[data-field="nav-portfolio"]').count() == 1
    assert page.locator('[data-field="nav-portfolio"]').get_attribute("href") is None
    assert page.locator('a[href*="portfolio"]').count() == 0
    assert "v15.7.1" in page.locator('[data-field="brand-footer"]').inner_text()
    assert page.locator('#records-wallet,[data-field="statistics-record-wallet"]').count() == 0
    assert "statistics-record-wallet" not in ds.screen_fields("statistics")
    assert "all wallets in the summary" in page.locator("#help-records").text_content()
    assert "all wallets in the summary" in page.locator("#help-benchmarks").text_content()
    assert page.locator('[data-field="statistics-screen"]').inner_text().count("pending owner approval") == 1
    missing = page.evaluate("""fields => fields.filter(field => !document.querySelector(`[data-field="${field}"]`))""", ds.screen_fields("statistics"))
    assert not missing
    numbers = page.locator(".s-record-value,.s-main td,.s-main output")
    assert numbers.count() > 60
    assert numbers.evaluate_all("els => els.every(el => getComputedStyle(el).fontVariantNumeric.includes('tabular-nums'))")
    for selector in ("#unit-chart", "#drawdown-chart"):
        chart = page.locator(selector)
        chart.scroll_into_view_if_needed()
        assert chart.locator("svg").get_attribute("aria-label")
        assert chart.locator("path").count() >= 2
        image = Image.open(io.BytesIO(chart.screenshot())).convert("RGB")
        raw = image.tobytes()
        pixels = [tuple(raw[index:index + 3]) for index in range(0, len(raw), 3)]
        assert image.width >= 300 and image.height >= 160
        assert len(set(pixels)) > 50, "blank chart screenshot"
        line_color = chart.locator(".s-line-price" if selector == "#unit-chart" else ".s-line-dd").evaluate("el => getComputedStyle(el).stroke")
        target = tuple(round(channel) for channel in ds.parse_color(line_color)[:3])
        matching = sum(1 for pixel in pixels if max(abs(pixel[index] - target[index]) for index in range(3)) < 35)
        assert matching > 30, "chart line missing from rendered pixels"
    page.screenshot(full_page=True)
    assert page.locator(".s-main h1,.s-main h2,.s-record-value").evaluate_all("""els => els.every(el => {
      const box = el.getBoundingClientRect();
      return box.left >= 0 && box.right <= innerWidth && el.scrollWidth <= el.clientWidth + 1;
    })""")


def test_statistics_records_match_snapshot_and_trade_extremes(open_statistics):
    page = open_statistics()
    wallet_id = "summary"
    expected = page.evaluate("""id => {
      const {rows,transactions} = statisticsMockup.data[id];
      const ath = rows.reduce((best,row) => row.value > best.value ? row : best);
      const profit = rows.reduce((best,row) => row.value-row.invested > best.value-best.invested ? row : best);
      const days = rows.slice(1).map((row,index) => ({date: row.date,
        gain: row.value-rows[index].value-row.invested+rows[index].invested,
        pct: (row.value-rows[index].value-row.invested+rows[index].invested)/rows[index].value*100}));
      const bestPct = days.reduce((best,row) => row.pct > best.pct ? row : best);
      const worstPct = days.reduce((best,row) => row.pct < best.pct ? row : best);
      const bestGain = days.reduce((best,row) => row.gain > best.gain ? row : best);
      const worstGain = days.reduce((best,row) => row.gain < best.gain ? row : best);
      const recent = transactions.filter(row => row.date >= '2026-05-01').length/6;
      const prior = transactions.filter(row => row.date >= '2025-11-01' && row.date < '2026-05-01').length/6;
      return {ath,profit,bestPct,worstPct,bestGain,worstGain,recent,prior,last:rows.at(-1)};
    }""", wallet_id)
    checks = {"record-ath": expected["ath"]["value"],
              "record-profit": expected["profit"]["value"] - expected["profit"]["invested"],
              "record-best-day-pct": expected["bestPct"]["pct"],
              "record-worst-day-pct": expected["worstPct"]["pct"],
              "record-best-day-pln": expected["bestGain"]["gain"],
              "record-worst-day-pln": expected["worstGain"]["gain"]}
    for field, value in checks.items():
        displayed = page.locator(f'[data-field="{field}"] .s-record-value').inner_text()
        assert financial_number(displayed) == pytest.approx(value, abs=0.0051)
    for field, key in [("record-ath", "ath"), ("record-profit", "profit"), ("record-best-day-pct", "bestPct"), ("record-worst-day-pct", "worstPct"), ("record-best-day-pln", "bestGain"), ("record-worst-day-pln", "worstGain")]:
        expected_date = date.fromisoformat(expected[key]["date"]).strftime("%d %b %Y").replace(" Sep ", " Sept ")
        assert expected_date in page.locator(f'[data-field="{field}"]').inner_text()
    activity = page.locator('[data-field="record-transactions"]')
    assert financial_number(activity.locator(".s-record-value").inner_text()) == pytest.approx(expected["recent"], abs=0.051)
    assert f"avg {expected['prior']:.1f}/mo" in activity.inner_text()
    assert page.locator("#monthly-records [data-field]").count() == 3
    assert page.locator("#daily-records [data-field]").count() == 5


@pytest.mark.parametrize("width", [1440, 390])
def test_statistics_benchmark_pp_wins_missing_and_mobile_disclosure(open_statistics, width):
    page = open_statistics(width, 900)
    expected = page.evaluate("""() => {
      const months = statisticsMockup.monthly(statisticsMockup.data.summary.rows).reverse();
      return {rows: months.slice(0,6).map(row => ({pct:row.pct, values:Array.from({length:8},(_,index) => statisticsMockup.benchmarkReturn(row.month,index))})),
        wins: Array.from({length:8},(_,index) => {const available = months.filter(row => statisticsMockup.benchmarkReturn(row.month,index) !== null);
          return [available.filter(row => row.pct > statisticsMockup.benchmarkReturn(row.month,index)).length,available.length];})};
    }""")
    for index, counts in enumerate(expected["wins"]):
        assert page.locator(".s-win strong").nth(index).inner_text() == f"{counts[0]} / {counts[1]}"
        assert counts[1] < 58
    table = page.locator("#benchmark-table")
    if width == 390:
        row = page.locator(".s-month-row").first
        assert row.locator("table").is_hidden()
        row.locator("summary").focus()
        page.keyboard.press("Enter")
        assert row.locator("table").is_visible()
        table = row.locator("table")
        assert table.locator("tbody tr").count() == 8
        cells = table.locator("tbody td")
    else:
        assert table.locator("thead th").count() == 10
        cells = table.locator("tbody tr").first.locator("td").filter(has=page.locator(".s-delta"))
    for index, value in enumerate(expected["rows"][0]["values"]):
        cell = cells.nth(index)
        if value is None:
            assert "N/A" in cell.inner_text() and "Unavailable" in cell.inner_text()
        else:
            assert financial_number(cell.locator(".s-delta").inner_text()) == pytest.approx(expected["rows"][0]["pct"] - value, abs=0.0051)
    first = page.locator("#benchmark-pagination").inner_text()
    page.get_by_role("button", name="Next benchmark page", exact=True).click()
    assert page.locator("#benchmark-pagination").inner_text() != first
    page.get_by_role("button", name="Previous benchmark page", exact=True).click()
    assert page.locator("#benchmark-pagination").inner_text() == first
    assert "N/A" in page.locator("#benchmark-table").inner_text()


def test_statistics_filters_are_independent_and_recalculate(open_statistics):
    page = open_statistics()
    show_snapshots(page)
    sections = ["#alltime-records", "#monthly-records", "#daily-records", "#benchmark-wins", "#benchmark-table", "#benchmark-mobile", "#unit-chart", "#heatmap-table", "#snapshot-table"]
    before = [page.locator(selector).inner_html() for selector in sections]
    for index, wallet in enumerate(["underwater", "heatmap", "snapshot"], start=6):
        page.select_option(f"#{wallet}-wallet", "ike")
        after = [page.locator(selector).inner_html() for selector in sections]
        assert after[index] != before[index]
        assert all(after[other] == before[other] for other in range(len(sections)) if other != index)
        before = after
    assert page.locator("#underwater-wallet").input_value() == "ike"
    assert page.locator("#heatmap-wallet").input_value() == "ike"
    assert page.locator("#snapshot-wallet").input_value() == "ike"
    assert "updated" in page.locator("#filter-status").inner_text()


def test_statistics_underwater_ranges_lake_selection_and_keyboard_inspection(open_statistics):
    page = open_statistics()
    extremes = page.locator(".s-extremes").inner_text()
    paths = []
    for selection, start in [("ALL", "01 Jan 2022"), ("3Y", "30 Oct 2023"), ("1Y", "30 Oct 2025"), ("YTD", "01 Jan 2026")]:
        page.locator(f'[data-range="{selection}"]').click()
        assert start in page.locator("#unit-chart svg").get_attribute("aria-label")
        assert page.locator(".s-extremes").inner_text() == extremes
        assert page.locator('[data-field="statistics-underwater-range"] [aria-pressed="true"]').count() == 1
        paths.append(page.locator(".s-line-price").get_attribute("d"))
    assert len(set(paths)) == 4
    page.locator('[data-range="ALL"]').click()
    old = page.locator("#lake-detail").inner_text()
    old_drawdown = page.locator(".s-line-dd").get_attribute("d")
    options = page.locator("#lake-select option").evaluate_all("els => els.map(el => el.value)")
    current = page.locator("#lake-select").input_value()
    page.select_option("#lake-select", next(value for value in options if value != current))
    assert page.locator("#lake-detail").inner_text() != old
    assert page.locator(".s-line-dd").get_attribute("d") != old_drawdown
    assert page.locator(".s-selected-lake").count() == 2
    slider = page.locator("#chart-inspect")
    slider.focus()
    page.keyboard.press("Home")
    assert "01 Jan 2022" in page.locator("#chart-reading").inner_text()
    first = page.locator("#chart-reading").inner_text()
    page.keyboard.press("ArrowRight")
    assert page.locator("#chart-reading").inner_text() != first
    assert slider.get_attribute("aria-valuetext") == page.locator("#chart-reading").inner_text()
    target = page.evaluate("""() => {
        const rows=statisticsMockup.data.summary.rows, lakes=statisticsMockup.lakeCatalog(rows);
        const lake=lakes.find(item => item.id !== statisticsMockup.state.lake);
        return {id:lake.id,fraction:rows.findIndex(row => row.date === lake.trough.date)/(rows.length-1)};
    }""")
    chart = page.locator("#unit-chart svg")
    box = chart.bounding_box()
    chart.click(position={"x": 54 + target["fraction"] * (box["width"] - 64), "y": 60})
    assert page.locator("#lake-select").input_value() == target["id"]
    lake_slider = page.locator("#lake-inspect")
    lake_slider.focus()
    initial = page.locator("#lake-reading").inner_text()
    page.keyboard.press("Home")
    assert page.locator("#lake-reading").inner_text() != initial
    assert lake_slider.get_attribute("aria-valuetext") == page.locator("#lake-reading").inner_text()


@pytest.mark.parametrize("wallet_id", ["summary", "ike", "growth"])
def test_statistics_heatmap_units_and_calendar_averages(open_statistics, wallet_id):
    page = open_statistics()
    page.select_option("#heatmap-wallet", wallet_id)
    expected = page.evaluate("""id => {
      const rows = statisticsMockup.data[id].rows;
      const values = [];
      for (let year=2022; year<=2026; year++) {
        const january = rows.filter(row => row.date.startsWith(`${year}-01`));
        const start = rows.findLast(row => row.date < `${year}-01-01`) || january[0], end = january.at(-1);
        const flow = end.invested-start.invested, gain=end.value-start.value-flow;
        values.push({gain,pct:gain/(start.value+flow/2)*100});
      }
      return {pct:values.reduce((sum,row) => sum+row.pct,0)/values.length, pln:values.reduce((sum,row) => sum+row.gain,0)/values.length};
    }""", wallet_id)
    for unit in ("pct", "pln"):
        page.locator(f'[data-unit="{unit}"]').click()
        displayed = page.locator("#heatmap-table tfoot td").first.inner_text()
        assert financial_number(displayed) == pytest.approx(expected[unit], abs=0.0051)
        assert page.locator("#heatmap-table tbody tr").first.locator("td").nth(10).inner_text() == "N/A"
        assert page.locator('[data-field="statistics-heatmap-unit"] [aria-pressed="true"]').count() == 1


@pytest.mark.parametrize("wallet_id", ["summary", "ike", "growth"])
def test_statistics_snapshot_balances_dietz_xirr_and_paging(open_statistics, wallet_id):
    page = open_statistics()
    show_snapshots(page)
    page.select_option("#snapshot-wallet", wallet_id)
    for frequency in ("monthly", "daily"):
        page.locator(f'[data-frequency="{frequency}"]').click()
        expected = page.evaluate("""({id,frequency}) => {
          const wallet = statisticsMockup.data[id], rows = wallet.rows, end=rows.at(-1);
          const start = frequency === 'daily' ? rows.at(-2) : rows.findLast(row => row.date < end.date.slice(0,7)+'-01');
          const flow=end.invested-start.invested, gain=end.value-start.value-flow;
          const xirr=end.xirr/100, first=Date.parse(wallet.flows[0].date);
          const residual=wallet.flows.filter(flow => flow.date <= end.date).reduce((sum,flow) => sum-flow.amount/(1+xirr)**((Date.parse(flow.date)-first)/86400000/365),0)+end.value/(1+xirr)**((Date.parse(end.date)-first)/86400000/365);
          return {value:end.value,invested:end.invested,gain,pct:gain/(start.value+flow/2)*100,xirr:end.xirr,residual};
        }""", {"id": wallet_id, "frequency": frequency})
        cells = page.locator("#snapshot-table tbody tr").first.locator("td")
        for index, key in enumerate(["value", "invested", "gain", "pct", "xirr"]):
            assert financial_number(cells.nth(index).inner_text()) == pytest.approx(expected[key], abs=0.0051)
        assert abs(expected["residual"]) < 0.0001
        previous = page.locator("#snapshot-table tbody").inner_text()
        page.get_by_role("button", name="Next snapshot page", exact=True).click()
        assert page.locator("#snapshot-table tbody").inner_text() != previous
        page.get_by_role("button", name="Previous snapshot page", exact=True).click()
        assert page.locator("#snapshot-table tbody").inner_text() == previous
    known = page.evaluate("statisticsMockup.annualReturn([{date:'2025-01-01',amount:1000}],1100,'2026-01-01')")
    assert known == pytest.approx(10, abs=1e-8)
    assert page.evaluate("statisticsMockup.annualReturn([{date:'2026-01-01',amount:1000}],1001,'2026-01-02')") is None


def test_statistics_summary_cash_flows_unit_price_and_hwm_are_coherent(open_statistics):
    page = open_statistics()
    assert page.evaluate("""() => {
      const {summary,ike,growth}=statisticsMockup.data;
      return summary.rows.every((row,index) => {
        const previous=summary.rows[index-1];
        const expectedUnit=previous ? previous.unit*(1+(row.value-previous.value-row.invested+previous.invested)/previous.value) : 100;
        const invested=summary.flows.filter(flow => flow.date <= row.date).reduce((sum,flow) => sum+flow.amount,0);
        return Math.abs(row.value-ike.rows[index].value-growth.rows[index].value)<1e-7 && Math.abs(row.invested-invested)<1e-7
          && Math.abs(row.unit-expectedUnit)<1e-7 && Math.abs(row.hwm-Math.max(previous?.hwm || 100,row.unit))<1e-7
          && Math.abs(row.drawdown-(row.unit/row.hwm-1)*100)<1e-7;
      });
    }""")


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_statistics_accessible_disclosures_tooltips_and_touch_targets(open_statistics, width, height):
    page = open_statistics(width, height, reduced=True)
    for summary in page.locator(".s-section > summary").all():
        parent = summary.locator("..")
        was_open = parent.get_attribute("open") is not None
        summary.focus()
        page.keyboard.press("Space")
        assert (parent.get_attribute("open") is not None) != was_open
        page.keyboard.press("Enter")
        assert (parent.get_attribute("open") is not None) == was_open
    for help_button in page.locator(".s-help:visible").all():
        help_button.focus()
        tooltip = page.locator(f"#{help_button.get_attribute('aria-describedby')}")
        assert tooltip.is_visible()
        bounds = tooltip.bounding_box()
        assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width
        page.keyboard.press("Escape")
        assert tooltip.is_hidden()
        help_button.click()
        assert tooltip.is_visible()
    controls = page.locator(".s-main button:visible,.s-main select:visible,.s-main input:visible,.s-section > summary:visible")
    assert controls.evaluate_all("els => els.every(el => {const box=el.getBoundingClientRect();return box.width>=44 && box.height>=44;})")
    assert page.locator(".s-section > summary > svg").first.evaluate("el => getComputedStyle(el).transitionDuration") == "0s"
    if width == 390:
        page.get_by_role("button", name="Open menu", exact=True).click()
        assert page.get_by_role("dialog", name="More navigation").is_visible()
        assert page.locator('.s-drawer-links [aria-current="page"]').inner_text() == "Statistics"
        page.locator(".drawer-close").focus()
        page.keyboard.press("Shift+Tab")
        assert page.locator('#statistics-menu [data-theme-choice="light"]').evaluate("el => el === document.activeElement")
        page.keyboard.press("Escape")
        assert page.locator("#statistics-menu").is_hidden()
        assert page.locator(".drawer-open").evaluate("el => el === document.activeElement")


def test_statistics_empty_loading_and_recovery(open_statistics):
    empty = open_statistics(state="empty")
    assert empty.locator('[data-field="statistics-empty"]').is_visible()
    assert empty.locator('[data-field="statistics-records"]').is_hidden()
    empty.get_by_role("button", name="Show sample history", exact=True).click()
    assert empty.locator('[data-field="statistics-empty"]').is_hidden()
    assert empty.locator('[data-field="statistics-records"]').is_visible()
    loading = open_statistics(state="loading")
    assert loading.get_by_role("status", name="Loading statistics").is_visible()
    assert loading.locator(".cl-candle").count() == 3
    assert loading.locator('[data-field="statistics-records"]').is_hidden()