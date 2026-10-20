"""Real Wallets screen UI 20 browser coverage."""
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "design"))

pytestmark = [pytest.mark.design, pytest.mark.browser]

sync_api = pytest.importorskip("playwright.sync_api")
import server  # noqa: E402
import design_system as ds  # noqa: E402
from test_design_mockups_browser import (  # noqa: E402
    COLLECT_TEXT,
    COLLECT_TARGETS,
    measured_contrast,
)

SETTLE_MS = 900
VIEWPORTS = [(1440, 900), (1024, 768), (768, 1024), (390, 844)]
THEMES = ["dark", "light"]
MIN_TARGET = 43.5


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
def open_page(browser, base_url):
    contexts = []

    def _open(width=1440, height=900, theme="dark"):
        context = browser.new_context(viewport={"width": width, "height": height}, has_touch=width < 768, service_workers="block")
        contexts.append(context)
        context.add_init_script(f"try{{localStorage.setItem('roastfolio-theme','{theme}');}}catch(e){{}}")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
        page.goto(base_url)
        page.evaluate("showTab('wallets')")
        page.wait_for_selector("#tab-wallets .w-hero", timeout=30000)
        page.wait_for_selector("#mgmt-wallet-chips-strip .wallet-chip", timeout=30000)
        page.wait_for_function("""() => {
          const holdings = window.WALLET_HOLDINGS || {};
          const fundedWallets = Object.values(holdings).filter(rows => Array.isArray(rows) && rows.length);
          const summary = window.WALLET_SUMMARIES && window.WALLET_SUMMARIES.Summary;
          return fundedWallets.length >= 2 && summary && Number(summary.total) > 0;
        }""", timeout=30000)
        page.evaluate("window.dispatchEvent(new CustomEvent('liveDataReady'))")
        page.wait_for_function("() => document.querySelector('#wob-kpi-total')?.textContent.includes('PLN')", timeout=30000)
        page.wait_for_timeout(SETTLE_MS)
        return page, errors

    yield _open
    for context in contexts:
        context.close()


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_wallets_never_scrolls_sideways_and_has_no_console_errors(open_page, width, height, theme):
    page, errors = open_page(width, height, theme)
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0, f"page is {overflow}px wider than the {width}px viewport"
    assert not errors, errors


def test_switcher_changes_hero_and_all_wallets_is_read_only(open_page):
    page, _ = open_page(1440, 900)
    chips = page.locator("#mgmt-wallet-chips-strip .wallet-chip")
    assert chips.count() >= 2
    first_name = page.locator("#mgmt-holdings-title").inner_text()
    chips.nth(1).click()
    page.wait_for_timeout(300)
    assert page.locator("#mgmt-holdings-title").inner_text() != first_name
    chips.first.click()
    page.wait_for_timeout(300)
    assert page.locator("#tab-wallets").get_attribute("data-readonly") == "true"
    assert page.locator(".w-readonly-note").is_visible()
    assert page.locator("#mgmt-open-trade-btn").is_disabled()
    assert page.locator("#wallet-quick-entry-card").is_hidden()
    assert page.locator("#mgmt-wallet-fab").is_hidden()


def test_all_wallets_summary_is_hydrated_and_aggregated(open_page):
    page, _ = open_page(1440, 900)
    page.locator("#mgmt-wallet-chips-strip .wallet-chip").first.click()
    page.wait_for_timeout(300)
    assert page.locator("#mgmt-holdings-title").inner_text() == "All wallets"
    assert page.locator("#wob-kpi-total").inner_text().replace("\xa0", " ") == "15 308,00 PLN"
    assert "3 holdings · 2 cash" in page.locator("#wallet-hero-counts").inner_text()
    assert page.locator("#wallet-allocation .alloc-bar .seg").count() >= 5
    assert "No allocation yet" not in page.locator("#wallet-allocation .alloc-legend").inner_text()
    assert page.locator("#wallet-allocation .alloc-legend").inner_text().count("%") >= 5


def _select_wallet(page, index):
    page.locator("#mgmt-wallet-chips-strip .wallet-chip").nth(index).click()
    page.wait_for_function(
        "(i) => document.querySelectorAll('#mgmt-wallet-chips-strip .wallet-chip')[i].getAttribute('aria-selected') === 'true'",
        arg=index,
    )
    page.wait_for_timeout(300)


def test_wallet_annual_return_is_xirr_fraction_shown_as_percent(open_page):
    page, _ = open_page(1440, 900)
    _select_wallet(page, 2)
    raw = page.evaluate("""() => {
      const name = document.querySelector('#mgmt-holdings-title').textContent.trim();
      return window.WALLET_SUMMARIES[name].annualReturn;
    }""")
    # Fixture XIRR depends on today's date; it must be a real root, never the -100% floor.
    assert -0.99 < raw < 0
    shown = page.locator("#wob-kpi-return").inner_text()
    assert shown == f"{raw * 100:.2f}%"


def test_holding_rows_show_allocation_share_of_wallet_value(open_page):
    page, _ = open_page(1440, 900)
    _select_wallet(page, 2)
    rows = page.locator("#tab-wallets .wht-row")
    allocs = [t.strip() for t in rows.locator(".wht-alloc-num").all_inner_texts()]
    assert allocs, "expected holding rows"
    assert all(a != "0.0%" for a in allocs)
    total = sum(float(a.rstrip("%")) for a in allocs)
    assert total == pytest.approx(100.0, abs=0.2)


def test_settings_rail_has_benchmark_ath_and_separate_saves(open_page):
    page, _ = open_page(1440, 900)
    _select_wallet(page, 1)
    rail = page.locator("#tab-wallets .w-settings")
    assert page.locator("#wallet-settings-benchmark-current").inner_text().strip()
    assert page.locator("#mgmt-benchmark-select").count() == 1
    page.click("#wallet-settings-benchmark-change")
    assert page.locator("#user-modal #mgmt-benchmark-select").is_visible()
    page.evaluate("closeUserModal()")
    ath_text = page.locator("#wallet-settings-ath-current").inner_text()
    assert ath_text.strip() not in ("", "—")
    rail.locator("summary", has_text="Set ATH manually").click()
    assert page.locator("#wallet-settings-save-ath-btn").is_visible()
    assert page.locator("#wallet-settings-reset-ath-btn").is_visible()
    rail.locator("summary", has_text="Rename wallet").click()
    assert page.locator("#wallet-settings-save-name-btn").is_visible()
    page.fill("#wallet-settings-ath-value", "")
    page.click("#wallet-settings-save-ath-btn")
    assert "positive ATH value" in page.locator("#wallet-settings-ath-flash").inner_text()
    assert page.locator('[id="wallet-settings-name"]').count() == 1


def test_new_wallet_chip_is_single_line_and_dots_hidden_on_desktop(open_page):
    page, _ = open_page(1440, 900)
    box = page.locator("#mgmt-toggle-create-btn").bounding_box()
    spans = page.locator("#mgmt-toggle-create-btn > span")
    tops = [spans.nth(i).bounding_box()["y"] for i in range(spans.count())]
    assert max(tops) - min(tops) < 8
    assert box["height"] <= 56
    assert page.locator("#mgmt-wallet-chips-dots").is_hidden()


def test_cemetery_tab_switches_panels(open_page):
    page, _ = open_page(1440, 900)
    page.get_by_role("tab", name="The Cemetery").click()
    assert page.locator('[data-holdings-view-panel="cemetery"]').is_visible()
    assert page.locator('[data-holdings-view-panel="active"]').is_hidden()


@pytest.mark.parametrize("width,height,expected", [(1440, 900, "right"), (390, 844, "bottom")])
def test_transaction_sheet_opens_and_esc_closes(open_page, width, height, expected):
    page, _ = open_page(width, height)
    page.locator("#mgmt-wallet-chips-strip .wallet-chip").nth(1).click()
    page.wait_for_timeout(300)
    page.locator("#mgmt-open-trade-btn").click()
    sheet = page.locator("#wallet-transaction-card")
    assert sheet.is_visible()
    box = sheet.bounding_box()
    if expected == "right":
        assert box["x"] > width - box["width"] - 40
    else:
        assert box["y"] > height * 0.25 and abs(box["x"]) <= 1
        assert abs((box["y"] + box["height"]) - height) <= 1
    page.keyboard.press("Escape")
    assert sheet.is_hidden()


def test_transaction_sheet_traps_focus_and_returns_to_trigger(open_page):
    page, _ = open_page(1440, 900)
    page.locator("#mgmt-wallet-chips-strip .wallet-chip").nth(1).click()
    page.wait_for_timeout(300)
    page.locator("#mgmt-open-trade-btn").focus()
    page.locator("#mgmt-open-trade-btn").click()
    assert page.locator("#wallet-transaction-card").get_attribute("aria-modal") == "true"
    last_focusable = page.evaluate("""() => {
      const card = document.querySelector('#wallet-transaction-card');
      const focusables = Array.from(card.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'))
        .filter(el => !el.disabled && el.offsetParent !== null);
      focusables.at(-1).focus();
      return focusables.at(-1).id || focusables.at(-1).textContent.trim();
    }""")
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id || document.activeElement.textContent.trim()") != last_focusable
    page.keyboard.press("Escape")
    assert page.evaluate("document.activeElement.id") == "mgmt-open-trade-btn"


def test_sell_button_opens_sheet_with_sell_type(open_page):
    page, _ = open_page(1440, 900)
    page.locator("#mgmt-wallet-chips-strip .wallet-chip").nth(1).click()
    page.wait_for_selector(".wht-btn-sell", timeout=30000)
    page.locator(".wht-btn-sell").first.click()
    assert page.locator("#wallet-transaction-card").is_visible()
    assert page.locator("#mgmt-transaction-type").input_value() == "SELL"
    assert page.locator("#mgmt-type-sell").get_attribute("aria-selected") == "true"


def test_mobile_fab_does_not_cover_last_content(open_page):
    page, _ = open_page(390, 844)
    page.locator("#mgmt-wallet-chips-strip .wallet-chip").nth(1).click()
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(200)
    fab = page.locator("#mgmt-wallet-fab").bounding_box()
    last = page.locator("#wallets-empty-state").bounding_box() or page.locator("#tab-wallets .w-cols").bounding_box()
    assert last["y"] + last["height"] <= fab["y"] or last["y"] > fab["y"] + fab["height"]


def test_touch_targets_are_at_least_44px_at_390(open_page):
    page, _ = open_page(390, 844)
    targets = page.evaluate(COLLECT_TARGETS)
    # Scope to the active wallets surface; the off-canvas sidenav/footer belongs to the shell.
    scoped = page.evaluate("""() => Array.from(document.querySelectorAll('#tab-wallets a[href], #tab-wallets button, #tab-wallets [role="tab"], .bottom-tabs button'))
      .filter(el => !el.closest('[hidden],[aria-hidden="true"]'))
      .map(el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
        return {label: (el.getAttribute('aria-label') || el.textContent).trim().slice(0, 30), cls: el.className,
                w: r.width, h: r.height, shown: r.width > 0 && r.height > 0 && s.visibility !== 'hidden'}; })
      .filter(t => t.shown)""")
    small = [f"{t['label']!r} ({t['cls']}) {t['w']:.0f}x{t['h']:.0f}" for t in scoped
             if t["h"] < MIN_TARGET or t["w"] < MIN_TARGET]
    assert not small, "targets below 44px:\n" + "\n".join(small)


@pytest.mark.parametrize("theme", THEMES)
def test_wallet_text_contrast_meets_wcag(open_page, theme):
    page, _ = open_page(1440, 900, theme)
    items = page.evaluate("""() => {
      const out = [], seen = new Set(); window.__ctNodes = [];
      const root = document.querySelector('#tab-wallets');
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const node = walker.currentNode, text = node.textContent.trim(), el = node.parentElement;
        if (!text || !/[\\p{L}\\p{N}]/u.test(text) || !el || seen.has(el) || el.closest('script,style,svg,[aria-hidden="true"],[hidden],.wallet-settings-summary')) continue;
        seen.add(el);
        const rect = el.getBoundingClientRect(), style = getComputedStyle(el);
        if (!rect.width || !rect.height || style.visibility === 'hidden' || style.display === 'none') continue;
        let visible = true;
        for (let n = el; n; n = n.parentElement) {
          const ns = getComputedStyle(n);
          if (ns.display === 'none' || ns.visibility === 'hidden') { visible = false; break; }
        }
        if (!visible) continue;
        window.__ctNodes.push(node);
        out.push({id: out.length, text: text.slice(0, 40), color: style.color, size: parseFloat(style.fontSize), weight: parseInt(style.fontWeight, 10)});
      }
      return out;
    }""")
    assert len(items) > 30
    measured = measured_contrast(page, items)
    failures = []
    for worst, item in measured:
        large = item["size"] >= 24 or (item["size"] >= 18.66 and item["weight"] >= 700)
        needed = 3.0 if large else 4.5
        if worst < needed:
            failures.append(f"{worst:.2f} < {needed} '{item['text']}' ({item['size']:.0f}px, {item['color']})")
    assert not failures, f"{theme}:\n" + "\n".join(failures)
