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
SCREENS = {
    "dashboard": URL,
    **{p.stem: p.as_uri() for p in sorted(ds.EXPLORATIONS.glob("dashboard-*.html"))},
    "wallets": (ds.MOCKUPS / "wallets.html").as_uri(),
    "history": (ds.MOCKUPS / "history.html").as_uri(),
}
ROAST_SCREENS = [s for s in SCREENS if s.startswith("dashboard")]
SETTLE_MS = 1500
VIEWPORTS = [(1440, 900), (1024, 768), (768, 1024), (390, 844)]
THEMES = ["dark", "light"]
MIN_TARGET = 43.5  # 44px minus sub-pixel rounding

COLLECT_TEXT = """() => {
  const out = [], seen = new Set();
  window.__ctNodes = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const text = node.textContent.trim();
    const el = node.parentElement;
    if (!text || !/[\\p{L}\\p{N}]/u.test(text) || !el || seen.has(el) || el.closest('script,style,svg,[aria-hidden="true"],[hidden]')) continue;
    seen.add(el);
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    if (!rect.width || !rect.height || style.visibility === 'hidden') continue;
    if (el.closest('.ticker-track') && (rect.left >= innerWidth || rect.right <= 0)) continue;
    let opacity = 1;
    for (let n = el; n; n = n.parentElement) opacity *= parseFloat(getComputedStyle(n).opacity);
    if (opacity < 0.99) continue;
    window.__ctNodes.push(node);
    out.push({id: out.length, text: text.slice(0, 40), color: style.color, size: parseFloat(style.fontSize), weight: parseInt(style.fontWeight, 10)});
  }
  return out;
}"""

LOCATE_TEXT = """(ids) => ids.map(id => {
  const node = window.__ctNodes[id];
  const el = node.parentElement;
  const range = document.createRange();
  range.selectNodeContents(node);
  const r = range.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const clear = [[cx, cy], [r.left + 1, r.top + 1], [r.right - 1, r.top + 1], [r.left + 1, r.bottom - 1], [r.right - 1, r.bottom - 1]].every(([x, y]) => {
    const top = document.elementFromPoint(x, y);
    return top && (el.contains(top) || top.contains(el));
  });
  const visible = r.width > 0 && r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight && clear;
  return {id, x: r.left, y: r.top, w: r.width, h: r.height, visible};
})"""

BRING_INTO_VIEW = """(id) => { window.__ctNodes[id].parentElement.scrollIntoView({block: 'center', inline: 'center', behavior: 'instant'}); }"""

def _screen_file(stem):
    return next(p for p in (ds.MOCKUPS / f"{stem}.html", ds.EXPLORATIONS / f"{stem}.html") if p.exists())


FRAMELESS = [stem for stem in SCREENS if "data-frameless" in _screen_file(stem).read_text(encoding="utf-8")]

FRAMELESS_SCAN = """() => {
  const out = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (el.closest('svg, .glass-island, .empty-state-card, .card-cl-overlay, .rc-poster')) continue;
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

HIDE_TEXT = ("*, *::before, *::after { color: transparent !important; -webkit-text-fill-color: transparent !important; "
             "text-shadow: none !important; transition: none !important; animation-play-state: paused !important; }")

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


def background_pixels(image, box):
    """Sample at most ~500 rendered pixels from inside a text box."""
    left, top = max(0, int(box["x"])), max(0, int(box["y"]))
    right, bottom = min(image.width, int(box["x"] + box["w"]) + 1), min(image.height, int(box["y"] + box["h"]) + 1)
    if right <= left or bottom <= top:
        return []
    region = image.crop((left, top, right, bottom)).convert("RGB")
    region = region.resize((min(region.width, 40), min(region.height, 12)))
    raw = region.tobytes()
    return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]


def measured_contrast(page, items):
    """Real contrast per text element: hide the text, screenshot, and compare the colour with the pixels behind it."""
    Image = pytest.importorskip("PIL.Image")
    import io
    page.add_style_tag(content=HIDE_TEXT)
    page.wait_for_timeout(150)
    height = page.evaluate("document.documentElement.scrollHeight")
    viewport = page.evaluate("innerHeight")
    pending = {item["id"]: item for item in items}
    results = {}

    def measure(image, spots):
        for spot in spots:
            if not spot["visible"] or spot["id"] not in pending:
                continue
            item = pending.pop(spot["id"])
            pixels = background_pixels(image, spot)
            if not pixels:
                continue
            fg = parse_css_color(item["color"])
            ratios = sorted(ds.contrast_ratio(ds.composite(fg, px) if fg[3] < 1 else fg[:3], px) for px in pixels)
            results[item["id"]] = (ratios[len(ratios) // 10], item)

    for scroll in range(0, max(1, height), max(1, viewport - 120)):
        if not pending:
            break
        page.evaluate("(y) => window.scrollTo(0, y)", scroll)
        page.wait_for_timeout(120)
        measure(Image.open(io.BytesIO(page.screenshot())), page.evaluate(LOCATE_TEXT, list(pending)))
    for ident in list(pending)[:200]:
        if ident not in pending:
            continue
        page.evaluate(BRING_INTO_VIEW, ident)
        page.wait_for_timeout(60)
        measure(Image.open(io.BytesIO(page.screenshot())), page.evaluate(LOCATE_TEXT, [ident]))
    return list(results.values())


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

    def _open(width=1440, height=900, query="", reduced=False, screen="dashboard"):
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
        page.goto(SCREENS[screen] + (f"?{query}" if query else ""))
        page.wait_for_timeout(SETTLE_MS)
        return page, errors

    yield _open
    for context in contexts:
        context.close()


@pytest.mark.parametrize("screen", list(SCREENS))
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_loads_cleanly_and_never_scrolls_sideways(open_page, width, height, theme, screen):
    page, errors = open_page(width, height, f"theme={theme}", screen=screen)
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0, f"page is {overflow}px wider than the {width}px viewport"
    assert not errors, errors


@pytest.mark.parametrize("screen", list(SCREENS))
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_text_contrast_meets_wcag_aa(open_page, width, height, theme, screen):
    page, _ = open_page(width, height, f"theme={theme}", screen=screen)
    items = page.evaluate(COLLECT_TEXT)
    assert len(items) > 60, f"only {len(items)} text elements inspected; the collector is not seeing the page"
    measured = measured_contrast(page, items)
    assert len(measured) > 0.7 * len(items), f"only {len(measured)} of {len(items)} text elements could be measured"
    failures = []
    for worst, item in measured:
        large = item["size"] >= 24 or (item["size"] >= 18.66 and item["weight"] >= 700)
        needed = 3.0 if large else 4.5
        if worst < needed:
            failures.append(f"{worst:.2f} < {needed} '{item['text']}' ({item['size']:.0f}px, {item['color']})")
    assert not failures, f"{screen} {theme} {width}px:\n" + "\n".join(failures)


@pytest.mark.parametrize("screen", list(SCREENS))
def test_touch_targets_are_at_least_44px_on_mobile(open_page, screen):
    page, _ = open_page(390, 844, screen=screen)
    page.click(".drawer-open")
    page.wait_for_timeout(400)
    small = [f"{t['label']!r} {t['w']:.0f}x{t['h']:.0f} ({t['cls']})" for t in page.evaluate(COLLECT_TARGETS)
             if t["w"] < MIN_TARGET or t["h"] < MIN_TARGET]
    assert not small, "targets under 44px (Section 1.2):\n" + "\n".join(small)


@pytest.mark.parametrize("screen", ROAST_SCREENS)
def test_roast_reactions_stay_hidden_until_tapped_on_every_screen(open_page, screen):
    page, _ = open_page(390, 844, screen=screen)
    assert page.locator(".roast-reactions").is_hidden()
    page.tap(".roast-toggle")
    assert page.locator(".roast-reactions").is_visible()


@pytest.mark.parametrize("screen", list(SCREENS))
def test_every_screen_keeps_the_same_navigation(open_page, screen):
    page, _ = open_page(1440, 900, screen=screen)
    assert page.locator(".sidebar-nav").is_visible()
    assert page.locator('.sidebar-nav [data-field^="nav-"]').count() == 10
    assert page.locator(".ticker-tape-container").count() == 1
    mobile, _ = open_page(390, 844, screen=screen)
    assert mobile.locator(".bottom-tabs a").count() == 4


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


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
@pytest.mark.parametrize("screen", FRAMELESS)
def test_frameless_screens_have_no_boxed_areas(open_page, screen, width, height, theme):
    page, _ = open_page(width, height, f"theme={theme}", screen=screen)
    boxes = page.evaluate(FRAMELESS_SCAN)
    assert not boxes, "rounded boxes found on a frameless screen (D-026):\n" + "\n".join(boxes)


@pytest.mark.parametrize("screen", FRAMELESS)
def test_frameless_screens_stay_frameless_with_everything_open(open_page, screen):
    page, _ = open_page(1440, 900, screen=screen)
    if screen == "wallets":
        page.click(".w-new")
        for button in page.locator(".disclosure:visible").all():
            button.click()
        page.click("#tab-cemetery")
    elif screen == "history":
        page.click('[data-field="history-return-mode"] [data-mode="pln"]')
        page.click("#tab-summaries")
    else:
        for selector in (".roast-toggle", ".disclosure", ".wallet-toggle"):
            page.locator(selector).first.click()
        page.click("#tab-yearly")
        page.locator(".disclosure:visible").first.click()
    boxes = page.evaluate(FRAMELESS_SCAN)
    assert not boxes, "\n".join(boxes)


def _tops(page, selectors):
    return [page.locator(s).first.bounding_box()["y"] for s in selectors]


def test_desktop_layout_order_matches_the_decisions(open_page):
    page, _ = open_page(1440, 900, screen="dashboard-d-player-v2")
    main = ["section.hero", "section.bench", "section.ath-six", "section.summary"]
    ys = _tops(page, main)
    assert ys == sorted(ys), f"main column order is wrong: {dict(zip(main, ys))}"
    rail = _tops(page, ["section.movers", "section.accounts"])
    assert rail == sorted(rail)
    assert page.locator("section.movers").bounding_box()["x"] > page.locator("section.hero").bounding_box()["x"] + 600
    assert page.locator("section.accounts").bounding_box()["x"] > page.locator("section.bench").bounding_box()["x"] + 600


def test_mobile_layout_order_matches_the_decisions(open_page):
    page, _ = open_page(390, 844, screen="dashboard-d-player-v2")
    order = ["section.hero", "section.bench", "section.movers", "section.accounts", "section.ath-six", "section.summary"]
    ys = _tops(page, order)
    assert ys == sorted(ys), f"mobile order is wrong: {dict(zip(order, ys))}"
    assert page.locator("section.movers").bounding_box()["x"] < 40


def test_hero_gauge_and_player_agree_with_the_hero_numbers(open_page):
    page, _ = open_page(1440, 900, screen="dashboard-d-player-v2")
    assert page.inner_text('[data-field="gauge-daily"] .gauge-value') == page.inner_text('[data-field="daily-pct"]')
    assert page.inner_text(".d-player-total").replace("\u00a0", " ") == page.inner_text('[data-field="total-value"]').replace("\u00a0", " ")
    assert page.evaluate("document.querySelector('.gauge-widget').style.getPropertyValue('--angle')") == "25.2deg"


# ---------------------------------------------------------------- wallets (Appendix B)


def test_wallet_switcher_updates_the_hero_and_all_wallets_is_read_only(open_page):
    page, errors = open_page(1440, 900, screen="wallets")
    assert page.text_content('[data-field="wallet-name"]') == "XTB Brokerage"
    assert page.locator(".h-act .trade-btn:visible").count() > 0
    page.click('.w-chip[data-wallet="all"]')
    assert page.text_content('[data-field="wallet-name"]') == "All wallets"
    assert page.inner_text('[data-field="wallet-total"]').replace("\u00a0", " ") == "348 520,50 PLN"
    assert page.locator(".w-readonly-note").is_visible()
    assert page.locator(".h-act .trade-btn:visible").count() == 0
    assert page.locator('[data-field="wallet-delete"]').is_hidden()
    assert page.locator('[data-field="quick-entry-input"]').is_hidden()
    page.click('.w-chip[data-wallet="ike"]')
    assert page.locator(".w-readonly-note").is_hidden()
    assert page.locator('[data-field="wallet-delete"]').is_visible()
    assert not errors, errors


def test_wallet_holdings_switch_to_the_cemetery_and_filter(open_page):
    page, _ = open_page(1440, 900, screen="wallets")
    page.click("#tab-cemetery")
    assert page.locator("#panel-active").is_hidden()
    assert page.locator(".g-table tbody tr:visible").count() == 3
    page.select_option('[data-field="cemetery-filter"]', "Still held")
    assert page.locator(".g-table tbody tr:visible").count() == 0


def test_new_wallet_opens_an_inline_form(open_page):
    page, _ = open_page(1440, 900, screen="wallets")
    assert page.locator('[data-field="wallet-create"]').is_hidden()
    page.click(".w-new")
    assert page.locator('[data-field="wallet-create"]').is_visible()
    assert page.evaluate("document.activeElement.closest('[data-field=\"wallet-create\"]') !== null")


@pytest.mark.parametrize("width,height,opener", [(1440, 900, '[data-field="tx-open"]'), (390, 844, ".w-fab")])
def test_transaction_sheet_opens_switches_type_and_closes(open_page, width, height, opener):
    page, _ = open_page(width, height, screen="wallets")
    sheet = page.locator(".tx-sheet")
    assert sheet.is_hidden()
    page.click(opener)
    assert sheet.is_visible()
    page.evaluate("Promise.all(document.querySelector('.tx-sheet').getAnimations().map(a => a.finished))")
    box = sheet.bounding_box()
    if width < 768:
        assert abs(box["y"] + box["height"] - height) < 2, "the phone sheet must sit at the bottom"
    else:
        assert box["x"] > width / 2, "the desktop sheet must open on the right"
    page.click('[data-field="tx-type"] [data-type="Sell"]')
    assert "Sell" in page.inner_text('[data-field="tx-submit"]')
    page.keyboard.press("Escape")
    assert sheet.is_hidden()


def test_sell_button_opens_the_sheet_on_sell(open_page):
    page, _ = open_page(1440, 900, screen="wallets")
    page.locator(".trade-btn.is-sell").first.click()
    assert page.get_attribute('[data-field="tx-type"] [data-type="Sell"]', "aria-selected") == "true"


def test_mobile_fab_never_covers_the_last_content(open_page):
    page, _ = open_page(390, 844, screen="wallets")
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(100)
    fab = page.locator(".w-fab").bounding_box()
    last = page.locator(".w-settings").bounding_box()
    assert last["y"] + last["height"] <= fab["y"], "the floating button covers the end of the page (D-040)"


def test_wallets_loading_and_empty_states(open_page):
    page, _ = open_page(1440, 900, "state=loading", screen="wallets")
    assert page.locator('[data-field="wallets-loading"]').is_visible()
    page, _ = open_page(1440, 900, "state=empty", screen="wallets")
    assert page.locator('[data-field="wallets-empty"]').is_visible()
    assert page.locator(".w-page").is_hidden()


# ---------------------------------------------------------------- history (Appendix C)


def test_history_tabs_switch_between_overview_and_summaries(open_page):
    page, errors = open_page(1440, 900, screen="history")
    assert page.locator("#panel-overview").is_visible() and page.locator("#panel-summaries").is_hidden()
    page.click("#tab-summaries")
    assert page.get_attribute("#tab-summaries", "aria-selected") == "true"
    assert page.locator("#panel-summaries").is_visible() and page.locator("#panel-overview").is_hidden()
    page, _ = open_page(390, 844, "tab=summaries", screen="history")
    assert page.locator('[data-field="recap-title"]').is_visible()
    assert not errors


def test_history_range_drives_the_hero(open_page):
    page, _ = open_page(1440, 900, screen="history")
    label = page.locator('[data-h="range-label"]')
    total = page.inner_text('[data-h="gain"]')
    page.click('[data-field="history-range"] [data-range="ALL"]')
    assert page.get_attribute('[data-range="ALL"]', "aria-selected") == "true"
    assert label.inner_text() != "in the last year"
    assert page.inner_text('[data-h="gain"]') != total


def test_history_return_pln_mode_hides_benchmarks(open_page):
    page, _ = open_page(1440, 900, screen="history")
    series = page.locator('[data-field="history-benchmark-series"]')
    assert series.is_visible() and page.locator('[data-note="pln"]').is_hidden()
    page.click('[data-field="history-return-mode"] [data-mode="pln"]')
    assert series.is_hidden() and page.locator('[data-note="pln"]').is_visible()
    assert page.locator('[data-end-wrap="s1"]').is_hidden()


def test_history_benchmark_chips_toggle_series(open_page):
    page, _ = open_page(1440, 900, screen="history")
    chip = page.locator('.series-chip[data-series="s2"]')
    assert chip.get_attribute("aria-pressed") == "false" and page.locator('[data-end-wrap="s2"]').is_hidden()
    chip.click()
    assert chip.get_attribute("aria-pressed") == "true" and page.locator('[data-end-wrap="s2"]').is_visible()


def test_recap_month_picker_and_journey_slider(open_page):
    page, _ = open_page(1440, 900, "tab=summaries", screen="history")
    assert page.inner_text('[data-rc="month"]') == "August 2026"
    page.click('.rc-step[data-step="1"]')
    assert page.inner_text('[data-rc="month"]') == "September 2026"
    assert page.inner_text('[data-rc="kind"]') == "Live MTD."
    page.click('.rc-step[data-step="-1"]')
    page.click('.rc-step[data-step="-1"]')
    assert page.inner_text('[data-rc="kind"]') == "Wrapped."
    assert page.get_attribute(".rc-poster:not(.rc-poster-mini)", "data-mood") == "down"
    assert not page.locator('[data-rc="sticker"]').is_visible()
    page.click("#rc-kind-year")
    assert page.inner_text('[data-rc="month"]') == "2025"
    assert page.text_content('[data-rc="edition"]') == "Yearly audit"
    assert page.locator('[data-field="recap-year-picker"]').is_visible()
    assert not page.locator('[data-field="recap-month-picker"]').is_visible()
    page.click("#rc-kind-month")
    date = page.inner_text('[data-j="date"]')
    page.fill("#rc-scrub", "3")
    assert page.inner_text('[data-j="date"]') != date


def test_history_daily_scatter(open_page):
    page, _ = open_page(1440, 900, screen="history")
    assert page.locator(".hx-daily .hx-scatter-svg .dot").count() > 20
    assert page.locator(".hx-daily .hx-scatter-svg .avg-line").count() == 1


def test_history_loading_and_empty_states(open_page):
    page, _ = open_page(1440, 900, "state=loading", screen="history")
    assert page.locator('[data-field="history-loading"]').is_visible()
    page, _ = open_page(1440, 900, "state=empty", screen="history")
    assert page.locator('[data-field="history-empty"]').is_visible()
