"""Offline Transactions design: combined filters, local editing and mobile layout."""
from pathlib import Path

import pytest

sync_api = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]
URL = (ROOT / 'design/mockups/transactions.html').as_uri()
pytestmark = [pytest.mark.design, pytest.mark.browser]


@pytest.fixture(scope='module')
def browser():
    with sync_api.sync_playwright() as runner:
        instance = runner.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    instance = browser.new_page(reduced_motion='reduce')
    errors = []
    instance.on('pageerror', lambda error: errors.append(str(error)))
    instance.goto(URL)
    yield instance
    assert not errors, errors
    instance.close()


@pytest.mark.parametrize('theme', ['dark', 'light'])
@pytest.mark.parametrize('width', [1440, 1024, 768, 390])
def test_transactions_layout_and_rendered_assets(page, theme, width):
    page.set_viewport_size({'width': width, 'height': 1000})
    page.evaluate('theme => document.documentElement.dataset.theme = theme', theme)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('#t-rows tr').count() == 12
    assert page.locator('#t-chart svg').count() == 1
    assert page.locator('#t-chart .t-bar').count() == 12
    assert page.locator('[data-day]').count() == 365
    assert page.locator('.t-icon svg').count() > 10
    assert page.locator('.t-main .t-section').evaluate_all("nodes => nodes.every(node => getComputedStyle(node).borderRadius === '0px')")
    if width < 768:
        assert page.locator('.t-month-days button').evaluate_all('nodes => nodes.every(node => node.getBoundingClientRect().width >= 43.5 && node.getBoundingClientRect().height >= 43.5)')


def test_combined_filters_do_not_change_global_turnover(page):
    original = page.locator('#t-total-value').inner_text()
    page.locator('#t-asset').fill('AAPL')
    page.locator('#t-wallet').select_option('Retirement')
    page.locator('[data-field="transactions-filter-operation"] summary').click()
    page.locator('#t-operations input[value="Buy"]').check()
    visible = page.locator('#t-rows').inner_text()
    assert 'AAPL' in visible and 'Buy' in visible and 'Retirement' in visible
    assert 'Sell' not in visible and 'Brokerage' not in visible
    assert page.locator('#t-total-value').inner_text() == original
    assert page.evaluate("transactionsMockup.turnover(transactionsMockup.rows) === transactionsMockup.rows.filter(row => row.operation === 'Buy' || row.operation === 'Sell').reduce((total,row) => total + Math.abs(row.value),0)")


def test_empty_recovery_and_invalid_ranges(page):
    page.locator('#t-asset').fill('not-an-asset')
    assert page.locator('.t-empty').is_visible()
    page.locator('#t-empty-clear').click()
    assert page.locator('#t-rows tr').count() == 12
    page.locator('#t-from').fill('2026-11-03')
    page.locator('#t-to').fill('2026-10-01')
    assert page.locator('#t-filter-error').is_visible()
    assert page.locator('#t-rows tr').count() == 0
    page.locator('#t-clear').click()
    assert page.locator('#t-filter-error').is_hidden()


def test_pagination_and_local_edit(page):
    page.locator('#t-next').click()
    assert page.locator('#t-page').inner_text() == '2 / 7'
    page.locator('#t-rows tr:has(.t-operation-buy) [data-edit]').first.click()
    assert page.locator('#t-edit').is_visible()
    page.locator('#t-edit input[name="asset"]').fill('Updated sample asset')
    page.locator('#t-edit input[name="commission"]').fill('12.5')
    page.locator('#t-edit button[type="submit"]').click()
    assert page.locator('#t-edit').is_hidden()
    assert 'Updated sample asset' in page.locator('#t-rows').inner_text()
    assert page.evaluate("transactionsMockup.rows.some(row => row.asset === 'Updated sample asset' && row.commission === 12.5)")


def test_automatic_rows_and_cash_constraints(page):
    assert page.locator('#t-rows tr:has(.t-auto) [data-edit]').count() == 0
    page.locator('#t-rows tr:has(.t-operation-deposit) [data-edit]').first.click()
    for field in ['asset', 'quantity', 'price', 'commission']:
        assert page.locator(f'#t-edit input[name="{field}"]').is_disabled()
    assert page.locator('#t-edit input[name="value"]').is_enabled()
    page.keyboard.press('Escape')
    assert page.locator('#t-edit').is_hidden()


def test_calendar_day_drills_into_ledger(page):
    active = page.locator('#t-calendar button[data-count="1"]').first
    date = active.get_attribute('data-day')
    active.click()
    assert page.locator('#t-day').is_visible()
    assert page.locator('#t-day-title').inner_text() == date
    page.locator('#t-day-filter').click()
    assert page.locator('#t-from').input_value() == date
    assert page.locator('#t-to').input_value() == date
    assert page.locator('#t-rows tr').count() == 1


def test_mobile_menu_and_help_keyboard(page):
    page.set_viewport_size({'width': 390, 'height': 844})
    page.locator('.t-mobile-menu').click()
    assert page.locator('#transactions-menu').is_visible()
    page.keyboard.press('Escape')
    assert page.locator('#transactions-menu').is_hidden()
    help_button = page.locator('.t-help').first
    help_button.focus()
    page.keyboard.press('Enter')
    assert page.locator('#t-help-turnover').is_visible()
    page.keyboard.press('Escape')
    assert page.locator('#t-help-turnover').is_hidden()