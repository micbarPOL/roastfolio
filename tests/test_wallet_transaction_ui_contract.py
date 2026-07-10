import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WalletTransactionUiContractTests(unittest.TestCase):
    def test_transaction_form_contains_required_fields(self):
        html = (ROOT / "src" / "index.html").read_text()
        required_ids = [
            "mgmt-search-input",
            "mgmt-transaction-date",
            "mgmt-units-input",
            "mgmt-total-input",
            "mgmt-commission-input",
            "mgmt-comment-input",
            "mgmt-max-qty-btn",
            "mgmt-form-errors",
            "mgmt-search-status",
            "mgmt-auto-cash-checkbox",
            "mgmt-type-deposit",
            "mgmt-type-withdrawal",
            "mgmt-transaction-summary",
            "mgmt-summary-cash-effect",
            "mgmt-submit-status",
        ]
        for field_id in required_ids:
            self.assertIn(f'id="{field_id}"', html)
        self.assertIn('id="mgmt-benchmark-setting"', html)
        self.assertIn('id="mgmt-open-trade-btn"', html)
        self.assertIn('class="wallet-sticky-top"', html)

    def test_manage_controller_exposes_autocomplete_validation_and_optimistic_hooks(self):
        js = (ROOT / "src" / "scripts" / "manage.js").read_text()
        tx_js = (ROOT / "src" / "scripts" / "transactions.js").read_text()
        ledger_js = (ROOT / "src" / "scripts" / "ledger-transactions.js").read_text()
        stats_js = (ROOT / "src" / "scripts" / "statistics.js").read_text()
        chart_js = (ROOT / "src" / "scripts" / "chart.js").read_text()
        portfolio_js = (ROOT / "src" / "scripts" / "portfolio-chart.js").read_text()
        retirement_engine_js = (ROOT / "src" / "scripts" / "retirement-simulation.js").read_text()
        retirement_chart_js = (ROOT / "src" / "scripts" / "retirement-chart.js").read_text()
        retirement_js = (ROOT / "src" / "scripts" / "retirement-plans.js").read_text()
        html = (ROOT / "src" / "index.html").read_text()
        css = (ROOT / "src" / "styles" / "main.css").read_text()
        required_symbols = [
            "function onSearchKeyDown(",
            "function onSearchBlur(",
            "function validateTransactionForm(",
            "function fillMaxQuantity(",
            "function _applyOptimisticTransaction(",
            "Searching Yahoo Finance",
            "Insufficient quantity.",
            "benchmarkSettingEl.style.display = isSummary ? '' : 'none';",
            "function _isCashTransactionType(",
            "autoAddCash",
            "Insufficient cash.",
            "function openTransactionsPanel(",
            "function closeTransactionsPanel(",
            "function setTransactionsPanelMode(",
            "function handleTransactionDraftChange(",
            "_renderHoldingsSkeleton",
            "wallet-trade-submit-status",
        ]
        for symbol in required_symbols:
            self.assertIn(symbol, js)
        self.assertIn(".wallet-sticky-top.is-condensed", css)
        self.assertIn("window.dispatchEvent(new CustomEvent('portfolioTransactionSaved'", js)
        self.assertIn("window.LedgerTransactions", ledger_js)
        self.assertIn("PortfolioClient.listTransactions", ledger_js)
        self.assertIn("PortfolioClient.migrate()", ledger_js)
        self.assertIn("const BACKFILL_WALLETS = new Set(['IKE', 'IKZE', 'XTB', 'Schwab', 'Binance']);", ledger_js)
        self.assertIn("function shouldAttemptBackfill(rows, emptyWallets)", ledger_js)
        self.assertIn("id && id !== 'summary' && name !== 'summary'", ledger_js)
        self.assertIn("emptyWallets", ledger_js)
        self.assertIn("Missing history for wallets", ledger_js)
        self.assertIn("Backfill migration failed; using currently available live rows.", ledger_js)
        self.assertIn("row.wallet || ''", ledger_js)
        self.assertIn("window.refreshTransactionsTabData = refreshTransactionsTabData", tx_js)
        self.assertIn("window.LedgerTransactions.loadRows", tx_js)
        self.assertIn("window.addEventListener('portfolioTransactionSaved'", tx_js)
        self.assertIn("<th>Wallet</th>", tx_js)
        self.assertIn("row.wallet || '—'", tx_js)
        self.assertIn("function isTurnoverOperation(operation)", tx_js)
        self.assertIn(".filter(row => isTurnoverOperation(row.operation))", tx_js)
        self.assertIn("window.LedgerTransactions", stats_js)
        self.assertIn("loadRows()", stats_js)
        self.assertIn("PortfolioClient.listSnapshots('summary')", stats_js)
        self.assertNotIn("INVESTMENT_DATA", stats_js)
        self.assertIn("showTab('transactions'", html)
        self.assertIn("refreshTransactionsTabData()", html)
        self.assertIn("scripts/ledger-transactions.js", html)
        self.assertNotIn("scripts/data-transactions.js", html)
        self.assertIn('id="portfolio-wallet-mini-charts"', html)
        self.assertIn('id="holdings-wallet-tabs"', html)
        self.assertIn('id="holdings-wallet-sections"', html)
        self.assertIn('id="history-wallet-btns"', html)
        self.assertIn('id="history-range-btns"', html)
        self.assertIn('data-history-range="ALL"', html)
        self.assertIn('data-history-range="5Y"', html)
        self.assertIn('data-history-range="3Y"', html)
        self.assertIn('data-history-range="1Y"', html)
        self.assertIn('data-history-range="YTD"', html)
        self.assertIn('data-history-range="1M"', html)
        self.assertIn('data-history-range="1W"', html)
        self.assertIn('id="history-return-mode-btns"', html)
        self.assertIn('data-history-return-mode="pct"', html)
        self.assertIn('data-history-return-mode="pln"', html)
        self.assertIn("function _walletDomId(", portfolio_js)
        self.assertIn("function renderWalletBreakdowns(", portfolio_js)
        self.assertIn("async function renderHistoryTab(", chart_js)
        self.assertNotIn("const HISTORY_START =", chart_js)
        self.assertIn("let _historyRange = 'ALL';", chart_js)
        self.assertIn("let _historyReturnMode = 'pct';", chart_js)
        self.assertIn("function _filterHistoryRows(", chart_js)
        self.assertIn("window.setHistoryRange = function setHistoryRange(range)", chart_js)
        self.assertIn("window.setHistoryReturnMode = function setHistoryReturnMode(mode)", chart_js)
        self.assertIn("function _makeCumulativeReturnChart(canvasId, data, mode)", chart_js)
        self.assertIn("showTab('retirement'", html)
        self.assertIn('id="tab-retirement"', html)
        self.assertIn('id="retirement-plan-list"', html)
        self.assertIn('id="retirement-warning-banner"', html)
        self.assertIn('id="retirement-years-left"', html)
        self.assertIn('id="retirement-transition-date"', html)
        self.assertIn('id="retirement-duration-hero"', html)
        self.assertIn('id="retirement-summary-duration"', html)
        self.assertIn('id="retirement-summary-spending"', html)
        self.assertIn('id="retirement-range-btns"', html)
        self.assertIn('id="retirement-chart-scale-mode"', html)
        self.assertIn('id="retirement-chart-y-zoom"', html)
        self.assertIn('id="retirement-chart-y-pan"', html)
        self.assertIn('id="retirement-chart-fit-all-btn"', html)
        self.assertIn('id="retirement-chart-focus-lower-btn"', html)
        self.assertIn('id="retirement-chart-log-btn"', html)
        self.assertIn('id="retirement-annual-fee-rate"', html)
        self.assertIn('data-retirement-range="ALL"', html)
        self.assertIn('data-retirement-range="10Y"', html)
        self.assertIn('data-retirement-range="5Y"', html)
        self.assertIn('data-retirement-range="3Y"', html)
        self.assertIn('data-retirement-range="1Y"', html)
        self.assertIn('id="retirement-plan-name"', html)
        self.assertIn('id="retirement-birth-date"', html)
        self.assertIn('id="retirement-started-date"', html)
        self.assertIn('id="retirement-retirement-age"', html)
        self.assertIn('id="retirement-target-age-display"', html)
        self.assertIn('id="retirement-income-streams"', html)
        self.assertIn('id="retirement-forecast-chart"', html)
        self.assertIn('class="retirement-band-help"', html)
        self.assertIn('class="retirement-action-bar"', html)
        self.assertIn('class="retirement-advanced-details"', html)
        self.assertIn("scripts/retirement-simulation.js", html)
        self.assertIn("scripts/retirement-chart.js", html)
        self.assertIn("scripts/retirement-plans.js", html)
        self.assertIn("initRetirementTab()", html)
        self.assertIn("window.RetirementSimulation", retirement_engine_js)
        self.assertIn("simulateRetirementProjection", retirement_engine_js)
        self.assertIn("validateRetirementSimulationInputs", retirement_engine_js)
        self.assertIn("resolveDateInputs", retirement_engine_js)
        self.assertIn("targetAge", retirement_engine_js)
        self.assertIn("window.RetirementChart", retirement_chart_js)
        self.assertIn("buildRetirementChartModel", retirement_chart_js)
        self.assertIn("filterHistoricalRange", retirement_chart_js)
        self.assertIn("compressLongTimeline", retirement_chart_js)
        self.assertIn("createRetirementChart", retirement_chart_js)
        self.assertIn("window.RetirementPlansClient", retirement_js)
        self.assertIn("window.RetirementForecast", retirement_js)
        self.assertIn("async function initRetirementTab()", retirement_js)
        self.assertIn("RetirementPlansClient.savePlan", retirement_js)
        self.assertIn("RetirementPlansClient.simulatePlan", retirement_js)
        self.assertIn("RetirementPlansClient.deletePlan", retirement_js)
        self.assertIn("_applyPreview", retirement_js)
        self.assertIn("_renderWarning", retirement_js)
        self.assertIn("_bindDraftInputs", retirement_js)
        self.assertIn("_setBusy", retirement_js)
        self.assertIn("_validateDraftSimulation", retirement_js)
        self.assertIn("_syncRangeButtons", retirement_js)
        self.assertIn("_restoreChartPrefs", retirement_js)
        self.assertIn("_syncChartControls", retirement_js)
        self.assertIn("annualFeeRate", retirement_js)
        self.assertIn("retirement-chart-scroll-surface", retirement_js)
        self.assertIn("retirement-birth-date", retirement_js)
        self.assertIn("retirement-started-date", retirement_js)
        self.assertIn("retirement-retirement-age", retirement_js)
        self.assertIn("PortfolioClient.listSnapshots('summary')", retirement_js)
        self.assertIn("window.setRetirementChartRange", retirement_js)
        self.assertIn("RetirementChart.buildRetirementChartModel", retirement_js)
        self.assertIn("RetirementChart.createRetirementChart", retirement_js)
        self.assertIn("new Chart(canvas", retirement_chart_js)
        self.assertIn(".retirement-screen", css)
        self.assertIn(".retirement-warning-banner", css)
        self.assertIn(".retirement-action-bar", css)
        self.assertIn(".retirement-range-btns", css)
        self.assertIn(".retirement-range-btn", css)
        self.assertIn(".retirement-chart-controls", css)
        self.assertIn(".retirement-chart-scale-helper", css)
        self.assertIn(".retirement-advanced-details", css)
        self.assertIn(".retirement-layout", css)
        self.assertIn(".retirement-plan-chip", css)
        self.assertIn(".retirement-chart-wrapper", css)
        self.assertIn(".retirement-band-help", css)

    def test_transactions_table_supports_inline_editing(self):
        html = (ROOT / "src" / "index.html").read_text()
        tx_js = (ROOT / "src" / "scripts" / "transactions.js").read_text()
        ledger_js = (ROOT / "src" / "scripts" / "ledger-transactions.js").read_text()
        client_js = (ROOT / "src" / "scripts" / "portfolios.js").read_text()
        css = (ROOT / "src" / "styles" / "main.css").read_text()

        self.assertIn("updateTransaction(portfolioId, transactionId, body)", client_js)
        self.assertIn("/transactions/${encodeURIComponent(transactionId)}", client_js)
        self.assertIn("transactionId: String(tx.transactionId || '')", ledger_js)
        self.assertIn("portfolioId: String(tx.portfolioId || portfolio?.portfolioId || '')", ledger_js)
        self.assertIn('data-tx-save', tx_js)
        self.assertIn('class="tx-edit-input"', tx_js)
        self.assertIn("function handleTransactionSave(button)", tx_js)
        self.assertIn("PortfolioClient.updateTransaction", tx_js)
        self.assertIn("portfolioHistoryRecalculated", tx_js)
        self.assertIn("function renderMobileEditPanel(row, actionHtml)", tx_js)
        self.assertIn('class="tx-mobile-edit-row"', tx_js)
        self.assertIn("tx-op-short", tx_js)
        self.assertIn("<th>Save</th>", html)
        self.assertIn(".tx-save-btn", css)
        self.assertIn(".tx-row-error", css)
        self.assertIn(".tx-mobile-edit-panel", css)
        self.assertIn("#tx-table th:nth-child(2)", css)
        self.assertIn(".tx-op-short", css)


if __name__ == "__main__":
    unittest.main()
