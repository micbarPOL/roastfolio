"""Mockup behaviour in a real browser: overflow, contrast, touch targets and the interactions the decisions promise.

Needs Playwright Chromium. Run with ./test.sh design.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "design"))
import design_system as ds  # noqa: E402

pytestmark = [pytest.mark.design, pytest.mark.browser]

sync_api = pytest.importorskip("playwright.sync_api")

URL = (ds.MOCKUPS / "dashboard.html").as_uri()
SETTLE_MS = 1500
VIEWPORTS = [(1440, 900), (1024, 768), (768, 1024), (390, 844)]
THEMES = ["dark", "light"]
MIN_TARGET = 43.5  # 44px minus sub-pixel rounding

COLLECT_TEXT = """() => {
  const out = [], seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const text = node.textContent.trim();
    const el = node.parentElement;
    if (!text || !el || seen.has(el) || el.closest('script,style,svg,[aria-hidden="true"],[hidden]')) continue;
    seen.add(el);
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    if (!rect.width || !rect.height || style.visibility === 'hidden') continue;
    let opacity = 1; const chain = [];
    for (let n = el; n; n = n.parentElement) {
      const s = getComputedStyle(n);
      opacity *= parseFloat(s.opacity);
      chain.push(s.backgroundColor);
    }
    if (opacity < 0.99) continue;
    out.push({text: text.slice(0, 40), color: style.color, size: parseFloat(style.fontSize), weight: parseInt(style.fontWeight, 10), chain});
  }
  return out;
}"""

COLLECT_TARGETS = """() => Array.from(document.querySelectorAll('a[href], button, [role="tab"]'))
  .filter(el => !el.closest('[hidden],[aria-hidden="true"]'))
  .map(el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return {label: (el.getAttribute('aria-label') || el.textContent).trim().slice(0, 30), cls: el.className,
            w: r.width, h: r.height, shown: r.width > 0 && r.height > 0 && s.visibility !== 'hidden'}; })
  .filter(t => t.shown)"""


def parse_css_color(value):
    value = value.strip()
    match = re.fullmatch(r"color\(srgb ([\d.]+) ([\d.]+) ([\d.]+)(?: / ([\d.]+))?\)", value)
    if match:
        r, g, b, a = match.groups()
        return float(r) * 255, float(g) * 255, float(b) * 255, float(a) if a is not None else 1.0
    return ds.parse_color(value)


def effective_background(chain):
    """Composite computed background colours from the root down to the element."""
    base = (255.0, 255.0, 255.0)
    for value in reversed(chain):
        rgba = parse_css_color(value)
        if rgba and rgba[3] > 0:
            base = ds.composite(rgba, base)
    return base


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
def open_page(browser):
    contexts = []

    def _open(width=1440, height=900, query="", reduced=False):
        context = browser.new_context(
            viewport={"width": width, "height": height},
            has_touch=width < 768,
            reduced_motion="reduce" if reduced else "no-preference",
        )
        contexts.append(context)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        page.on("requestfailed", lambda r: errors.append(f"requestfailed: {r.url}"))
        page.goto(URL + (f"?{query}" if query else ""))
        page.wait_for_timeout(SETTLE_MS)
        return page, errors

    yield _open
    for context in contexts:
        context.close()


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_loads_cleanly_and_never_scrolls_sideways(open_page, width, height, theme):
    page, errors = open_page(width, height, f"theme={theme}")
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0, f"page is {overflow}px wider than the {width}px viewport"
    assert not errors, errors


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_text_contrast_meets_wcag_aa(open_page, width, height, theme):
    page, _ = open_page(width, height, f"theme={theme}")
    items = page.evaluate(COLLECT_TEXT)
    assert len(items) > 60, f"only {len(items)} text elements inspected; the collector is not seeing the page"
    failures = []
    for item in items:
        fg = parse_css_color(item["color"])
        bg = effective_background(item["chain"])
        text_color = ds.composite(fg, bg) if fg[3] < 1 else fg[:3]
        ratio = ds.contrast_ratio(text_color, bg)
        large = item["size"] >= 24 or (item["size"] >= 18.66 and item["weight"] >= 700)
        needed = 3.0 if large else 4.5
        if ratio < needed:
            failures.append(f"{ratio:.2f} < {needed} '{item['text']}' ({item['size']:.0f}px, {item['color']})")
    assert not failures, f"{theme} {width}px:\n" + "\n".join(failures)


def test_touch_targets_are_at_least_44px_on_mobile(open_page):
    page, _ = open_page(390, 844)
    page.click(".drawer-open")
    page.wait_for_timeout(400)
    small = [f"{t['label']!r} {t['w']:.0f}x{t['h']:.0f} ({t['cls']})" for t in page.evaluate(COLLECT_TARGETS)
             if t["w"] < MIN_TARGET or t["h"] < MIN_TARGET]
    assert not small, "targets under 44px (Section 1.2):\n" + "\n".join(small)


def test_desktop_shows_sidebar_and_hides_bottom_tabs(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator(".sidebar-nav").is_visible()
    assert not page.locator(".bottom-tabs").is_visible()
    assert not page.locator(".drawer-open").is_visible()


def test_mobile_shows_bottom_tabs_and_drawer_instead_of_sidebar(open_page):
    page, _ = open_page(390, 844)
    assert not page.locator(".sidebar-nav").is_visible()
    assert page.locator(".bottom-tabs").is_visible()
    tabs = page.locator(".bottom-tabs a")
    assert tabs.count() == 4
    assert page.locator(".mobile-side-drawer").is_hidden()
    page.click(".drawer-open")
    assert page.locator(".mobile-side-drawer").is_visible()
    page.click(".drawer-close")
    assert page.locator(".mobile-side-drawer").is_hidden()
    page.click(".drawer-open")
    page.click(".drawer-backdrop", position={"x": 370, "y": 400})
    assert page.locator(".mobile-side-drawer").is_hidden()


def test_sidebar_collapses_to_icon_rail_and_back(open_page):
    page, _ = open_page(1440, 900)
    width = lambda: page.locator(".sidebar-nav").bounding_box()["width"]  # noqa: E731
    assert abs(width() - 240) <= 1
    page.click(".sidebar-collapse")
    page.wait_for_timeout(450)
    assert abs(width() - 64) <= 1
    assert page.locator(".sidebar-nav .nav-label").first.is_hidden()
    assert page.locator(".nav-item", has_text="").first.is_visible()
    page.keyboard.press("Control+b")
    page.wait_for_timeout(450)
    assert abs(width() - 240) <= 1
    assert page.locator(".sidebar-nav .nav-label").first.is_visible()


def test_summary_card_switches_between_month_and_year(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator("#panel-monthly").is_visible() and page.locator("#panel-yearly").is_hidden()
    page.click("#tab-yearly")
    assert page.locator("#panel-yearly").is_visible() and page.locator("#panel-monthly").is_hidden()
    assert page.get_attribute("#tab-yearly", "aria-selected") == "true"
    assert page.locator('[data-field="yearly-return-pln"]').is_visible()
    page.focus("#tab-yearly")
    page.keyboard.press("ArrowLeft")
    assert page.locator("#panel-monthly").is_visible()


def test_benchmark_lists_open_in_place(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator("#bm-monthly").is_hidden()
    page.click('[aria-controls="bm-monthly"]')
    assert page.locator("#bm-monthly").is_visible()
    assert page.locator("#bm-monthly li").count() == 5


def test_gauge_has_two_modes(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator('[data-field="gauge-daily"]').is_visible()
    assert page.locator('[data-field="gauge-ath"]').is_hidden()
    page.click("#tab-gauge-ath")
    assert page.locator('[data-field="gauge-ath"]').is_visible()
    assert page.locator('[data-field="gauge-daily"]').is_hidden()
    assert page.evaluate("document.querySelector('.gauge-widget').style.getPropertyValue('--angle')") == "-17.8deg"
    page.click("#tab-gauge-daily")
    assert page.evaluate("document.querySelector('.gauge-widget').style.getPropertyValue('--angle')") == "25.2deg"


def test_roast_reactions_stay_hidden_until_the_card_is_tapped(open_page):
    page, _ = open_page(390, 844)
    assert page.locator(".roast-reactions").is_hidden()
    page.tap(".roast-toggle")
    assert page.locator(".roast-reactions").is_visible()
    assert page.get_attribute(".roast-toggle", "aria-expanded") == "true"
    assert page.locator(".roast-reactions button").count() == 4
    page.tap(".roast-toggle")
    assert page.locator(".roast-reactions").is_hidden()


def test_wallet_cards_expand_in_place(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator("#wallet-xtb-more").is_hidden()
    page.click('[aria-controls="wallet-xtb-more"]')
    assert page.locator("#wallet-xtb-more").is_visible()
    assert page.get_attribute('[aria-controls="wallet-xtb-more"]', "aria-expanded") == "true"


def test_theme_switch_changes_the_tokens_in_use(open_page):
    page, _ = open_page(1440, 900)
    reg = ds.registry()
    canvas = lambda: tuple(round(c) for c in parse_css_color(  # noqa: E731
        page.evaluate("getComputedStyle(document.body).backgroundColor"))[:3])
    assert canvas() == tuple(ds.parse_color(reg["dark"]["--bg-canvas"])[:3])
    page.click('.sidebar-foot [data-theme-choice="light"]')
    assert page.evaluate("document.documentElement.dataset.theme") == "light"
    assert canvas() == tuple(ds.parse_color(reg["light"]["--bg-canvas"])[:3])


def test_movers_range_toggle_changes_the_sparklines(open_page):
    page, _ = open_page(1440, 900)
    before = page.get_attribute(".mover-row .spark-line", "points")
    page.click('[data-field="mover-range-toggle"] [data-range="1y"]')
    assert page.get_attribute(".mover-row .spark-line", "points") != before


def test_benchmark_chart_switches_type_and_range(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator(".bench-svg polyline.bench-line").count() == 1
    page.click('[data-field="bench-type"] [data-type="candle"]')
    assert page.locator(".bench-svg rect.candle-up, .bench-svg rect.candle-down").count() > 10
    page.click('[data-field="bench-range"] [data-range="1Y"]')
    assert page.inner_text('[data-field="bench-change"]') == "-8.15%"
    assert "down" in page.get_attribute('[data-field="bench-change"]', "class").split()


def test_loading_state_shows_the_candle_loader(open_page):
    page, _ = open_page(1440, 900, "state=loading")
    assert page.locator('[data-field="state-loading"]').is_visible()
    assert page.locator(".card-cl-overlay .cl-candle").first.is_visible()


def test_empty_state_replaces_the_dashboard(open_page):
    page, _ = open_page(1440, 900, "state=empty")
    assert page.locator('[data-field="state-empty"]').is_visible()
    assert page.locator(".dash-grid").is_hidden()


def test_ath_celebration_appears_on_demand(open_page):
    default, _ = open_page(1440, 900)
    assert default.locator('[data-field="ath-celebration"]').is_hidden()
    shown, _ = open_page(1440, 900, "state=ath")
    assert shown.locator('[data-field="ath-celebration"]').is_visible()


def test_reduced_motion_stops_looping_animations(open_page):
    page, errors = open_page(1440, 900, reduced=True)
    assert page.evaluate("getComputedStyle(document.querySelector('.ticker-track')).animationName") == "none"
    assert not errors
    assert page.inner_text('[data-field="total-value"]').replace("\u00a0", " ") == "348 520,50 PLN"


def test_ticker_tape_is_mounted_once(open_page):
    page, _ = open_page(1440, 900)
    assert page.locator(".ticker-tape-container").count() == 1
    assert page.locator('.ticker-tape-container [data-field^="index-"]').count() == 6
