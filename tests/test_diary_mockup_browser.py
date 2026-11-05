"""Coping Diary mockup: review, note lifecycle and responsive master-detail navigation."""
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
URL = (ROOT / "design/mockups/diary.html").as_uri()
pytestmark = [pytest.mark.design, pytest.mark.browser]


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as runner:
        instance = runner.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    instance = browser.new_page(reduced_motion="reduce")
    errors = []
    instance.on("pageerror", lambda error: errors.append(str(error)))
    instance.goto(URL)
    yield instance
    assert not errors, errors
    instance.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("width,height", [(1440, 1000), (1024, 900), (768, 1024), (390, 844)])
def test_diary_master_detail_responsive_and_readable(page, theme, width, height):
    page.set_viewport_size({"width": width, "height": height})
    page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("#note-ledger .d-note-row").count() == 4
    assert page.locator("#focus-title").inner_text() == "Apple"
    assert page.locator("#note-mentions [data-mention]").count() == 1
    if width < 768:
        assert not page.locator("#focus-sheet").is_visible()
        page.locator("#note-ledger .d-note-row").nth(1).click()
        assert page.locator("#focus-sheet").is_visible()
        page.locator("#focus-sheet").screenshot(path=f"tmp/diary-{width}-{theme}-focus.png")
        page.locator("#mobile-back").click()
        assert not page.locator("#focus-sheet").is_visible()
    else:
        assert page.locator("#note-ledger").is_visible()
        assert page.locator("#focus-sheet").is_visible()
        page.locator("#focus-sheet").screenshot(path=f"tmp/diary-{width}-{theme}-focus.png")
    page.locator("#note-ledger").screenshot(path=f"tmp/diary-{width}-{theme}-ledger.png")


def test_diary_search_tags_open_checklist_and_selected_note(page):
    page.locator("#ledger-search").fill("MSFT")
    assert page.locator("#note-ledger .d-note-row").count() == 1
    assert page.locator("#focus-title").inner_text() == "Microsoft"
    page.locator("#clear-ledger-filter").click()
    tag = page.locator("#tag-filters button").filter(has_text="#risk")
    tag.click()
    assert page.locator("#note-ledger .d-note-row").count() == 1
    assert "Microsoft" in page.locator("#note-ledger").inner_text()
    page.locator("#clear-ledger-filter").click()
    page.locator("#only-open-checklist").check()
    assert page.locator("#note-ledger .d-note-row").count() == 2
    assert page.locator("#ledger-count").inner_text() == "2 of 4 notes"


def test_diary_note_thesis_checklist_and_comments(page):
    editor = page.locator("#note-text")
    editor.fill("Reasoned entry with #review and @NVDA")
    assert editor.input_value().endswith("@NVDA")
    assert page.locator("#focus-tags").inner_text() == "#review"
    assert page.locator("#note-mentions [data-mention]").inner_text().startswith("@NVDA")
    page.locator("#save-note").click()
    assert "#review" in page.locator("#note-ledger").inner_text()

    page.locator("#why-buy").fill("Durable advantage with measured position size.")
    page.locator("#save-thesis").click()
    assert page.locator("#why-buy").input_value().startswith("Durable")

    page.locator("#new-check-text").fill("Review valuation")
    page.locator("#new-check-date").fill("2026-11-15")
    page.locator("#add-check-form button[type=submit]").click()
    assert "Review valuation" in page.locator("#checklist-items").inner_text()
    page.locator("#checklist-items input[type=checkbox]").last.check()
    assert page.locator("#checklist-count").inner_text().startswith("2 open")

    page.locator("#new-comment").fill("New evidence still supports the timeline.")
    page.locator("#add-comment-form button[type=submit]").click()
    assert "New evidence" in page.locator("#comment-list").inner_text()


def test_diary_create_archive_delete_and_composer_recovery(page):
    page.locator("#new-note").click()
    assert page.locator("#note-composer").evaluate("node => node.classList.contains('is-open')")
    page.keyboard.press("Escape")
    assert not page.locator("#note-composer").evaluate("node => node.classList.contains('is-open')")
    page.locator("#new-note").click()
    page.locator("#composer-ticker").fill("INTC")
    page.locator("#composer-text").fill("Monitor demand before the next report. #watch")
    page.locator("#composer-form").evaluate("form => form.requestSubmit()")
    assert page.locator("#note-ledger .d-note-row").count() == 5
    assert page.locator("#focus-title").inner_text() == "INTC"

    page.locator("#toggle-active").click()
    assert page.locator("#focus-status").inner_text() == "Archived"
    assert page.locator("#toggle-active").get_attribute("aria-pressed") == "false"

    page.on("dialog", lambda dialog: dialog.accept())
    page.locator("#delete-note").click()
    assert page.locator("#note-ledger .d-note-row").count() == 4
    assert page.locator("#focus-title").inner_text() != "INTC"


def test_diary_empty_loading_menu_and_local_sample_state(page, browser):
    empty_page = browser.new_page(reduced_motion="reduce")
    empty_page.goto(URL + "?state=empty")
    assert empty_page.locator("#diary-ledger-empty").is_visible()
    assert empty_page.locator("#focus-empty").is_visible()
    empty_page.locator("#new-note").click()
    empty_page.locator("#composer-ticker").fill("TSLA")
    empty_page.locator("#composer-text").fill("Keep size aligned with risk.")
    empty_page.locator("#composer-form").evaluate("form => form.requestSubmit()")
    assert empty_page.locator("#note-ledger .d-note-row").count() == 1
    assert empty_page.locator("#diary-ledger-empty").is_hidden()

    loading_page = browser.new_page(reduced_motion="reduce")
    loading_page.goto(URL + "?state=loading")
    assert loading_page.locator("#diary-loading").is_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator(".d-menu").click()
    assert page.locator("#diary-menu").is_visible()
    page.keyboard.press("Escape")
    assert page.locator("#diary-menu").is_hidden()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    empty_page.close()
    loading_page.close()