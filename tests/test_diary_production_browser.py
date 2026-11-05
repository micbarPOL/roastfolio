"""Offline browser regressions for the production Coping Diary renderer."""
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

pytestmark = [pytest.mark.design, pytest.mark.browser]
sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
HOST = str(BeautifulSoup((ROOT / "src/index.html").read_text(), "html.parser").select_one("#diary-app-root"))
TOKENS = (ROOT / "design/tokens-v9.css").read_text()
SCRIPT = (ROOT / "src/js/diary.js").read_text()
NOTES = [
    {
        "note_id": "apple",
        "title": "Apple",
        "linked_assets": ["AAPL"],
        "note_text": "Services growth supports the thesis. #quality @AAPL",
        "user_tags": ["#quality"],
        "is_active": True,
        "updatedAt": "2026-09-12T10:00:00Z",
        "hypothesis": {"why_buy": "Durable ecosystem", "exit_plan": "Revisit if services slow", "risk_factors": "Valuation"},
        "hypothesis_checkpoints": [{"checkpoint_id": "apple-check", "text": "Review quarterly results", "status": "PENDING", "due_date": "2027-01-15"}],
        "comments": [{"comment_id": "apple-comment", "text": "Keep position sizing measured.", "created_at": "2026-09-12T10:00:00Z"}],
    },
    {
        "note_id": "microsoft",
        "title": "Microsoft",
        "linked_assets": ["MSFT"],
        "note_text": "Watch cloud margins. #quality #risk",
        "user_tags": ["#quality", "#risk"],
        "is_active": False,
        "updatedAt": "2026-09-10T10:00:00Z",
        "hypothesis": {"why_buy": "", "exit_plan": "", "risk_factors": ""},
        "hypothesis_checkpoints": [],
        "comments": [],
    },
]


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as runner:
        instance = runner.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    instance = browser.new_page(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
    errors = []
    instance.on("pageerror", lambda error: errors.append(str(error)))
    instance.set_content(f'<html data-theme="dark"><head><style>{TOKENS}</style></head><body>{HOST}</body></html>')
    instance.add_script_tag(content="""
        window.__CONFIG__ = {apiUrl: 'http://diary.test'};
        window.AuthGuard = {getIdToken: () => 'offline-test'};
        window.WALLET_HOLDINGS = {IKE: [{ticker: 'AAPL'}]};
        window.mockDiaryNotes = NOTES_PLACEHOLDER;
        window.diaryRequests = [];
        window.fetch = async (url, options = {}) => {
            const method = options.method || 'GET';
            diaryRequests.push({url, method, body: options.body || ''});
            if (url.includes('/diary?')) return {ok: true, json: async () => ({notes: mockDiaryNotes})};
            if (method === 'POST' && url.endsWith('/diary')) {
                const note = {...JSON.parse(options.body), note_id: 'new-entry', createdAt: '2026-09-15T10:00:00Z'};
                mockDiaryNotes = [note, ...mockDiaryNotes];
                return {ok: true, json: async () => ({note})};
            }
            const match = url.match(new RegExp('/diary/([^/]+)'));
            const index = mockDiaryNotes.findIndex(note => note.note_id === decodeURIComponent(match?.[1] || ''));
            if (method === 'PUT' && index >= 0) {
                mockDiaryNotes[index] = {...mockDiaryNotes[index], ...JSON.parse(options.body)};
                return {ok: true, json: async () => ({note: mockDiaryNotes[index]})};
            }
            if (method === 'POST' && url.includes('/toggle-active') && index >= 0) {
                mockDiaryNotes[index].is_active = JSON.parse(options.body).is_active;
                return {ok: true, json: async () => ({note: mockDiaryNotes[index]})};
            }
            return {ok: true, json: async () => ({})};
        };
    """.replace("NOTES_PLACEHOLDER", json.dumps(NOTES)))
    instance.add_script_tag(content=SCRIPT)
    instance.wait_for_function("document.querySelector('#diary-ledger-count')?.textContent === '2 of 2 entries'")
    yield instance
    assert not errors, errors
    instance.close()


def test_desktop_ledger_focus_sheet_and_real_fields(page):
    assert page.locator("#diary-ledger-list [data-note-id]").count() == 2
    assert page.locator("#diary-detail-ticker").inner_text() == "Apple"
    assert page.locator("#diary-why-buy").input_value() == "Durable ecosystem"
    assert page.locator("#diary-detail [data-mention='AAPL']").count() == 1
    assert page.locator("#diary-checklist [data-check-id]").count() == 1
    assert "2" in page.locator("#diary-overview").inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator(".diary-split").evaluate("node => getComputedStyle(node).display") == "grid"


def test_mobile_list_detail_back_and_keyboard_selection(page):
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.locator(".diary-ledger-pane").is_visible()
    assert page.locator(".diary-focus-pane").is_hidden()
    page.locator("[data-note-id='microsoft']").focus()
    page.keyboard.press("Enter")
    assert page.locator("#diary-detail-ticker").inner_text() == "Microsoft"
    assert page.locator(".diary-ledger-pane").is_hidden()
    page.locator("#diary-detail-back").click()
    assert page.locator(".diary-ledger-pane").is_visible()
    assert page.locator(".diary-focus-pane").is_hidden()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_search_tag_and_open_checklist_keep_focus_in_filtered_results(page):
    page.locator("#diary-ledger-filter").fill("MSFT")
    assert page.locator("#diary-ledger-list [data-note-id]").count() == 1
    assert page.locator("#diary-detail-ticker").inner_text() == "Microsoft"
    page.locator("#diary-ledger-filter").fill("")
    page.locator("#diary-tags-cloud [data-filter-tag='#risk']").click()
    assert page.locator("#diary-ledger-list [data-note-id]").count() == 1
    assert page.locator("#diary-detail-ticker").inner_text() == "Microsoft"
    page.locator("#diary-tags-cloud [data-filter-tag='']").click()
    page.locator("#diary-filter-unchecked").check()
    assert page.locator("#diary-ledger-list [data-note-id]").count() == 1
    assert page.locator("#diary-detail-ticker").inner_text() == "Apple"


def test_composer_escape_and_create_opens_new_focus_sheet(page):
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator("#diary-mobile-new-note").click()
    assert page.locator("#diary-compose").is_visible()
    assert page.locator("#diary-compose").get_attribute("aria-hidden") == "false"
    page.keyboard.press("Escape")
    assert page.locator("#diary-compose").is_hidden()
    page.locator("#diary-new-note").click()
    page.locator("#diary-new-ticker").fill("INTC")
    page.locator("#diary-new-text").fill("Monitor demand before the next report. #watch")
    page.locator("#diary-compose-save").click()
    assert page.locator("#diary-detail-ticker").inner_text() == "INTC"
    assert page.locator("[data-note-id]").count() == 3


def test_thesis_save_uses_existing_api_contract(page):
    page.locator("#diary-exit-plan").fill("Revisit at the next earnings report")
    page.locator("#diary-save-thesis").click()
    page.wait_for_function("diaryRequests.some(request => request.method === 'PUT')")
    assert page.evaluate("diaryRequests.find(request => request.method === 'PUT').url.includes('/diary/apple')")