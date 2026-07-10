import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class MonthlySummaryContractTests(unittest.TestCase):
    def setUp(self):
        self.index_html = (ROOT / "src" / "index.html").read_text()
        self.dashboard_js = (ROOT / "src" / "scripts" / "dashboard.js").read_text()
        self.statistics_js = (ROOT / "src" / "scripts" / "statistics.js").read_text()
        self.main_css = (ROOT / "src" / "styles" / "main.css").read_text()
        self.handler_py = (ROOT / "lambda" / "handler.py").read_text()
        self.server_py = (ROOT / "server.py").read_text()

    def test_html_elements_exist(self):
        self.assertIn("dash-monthly-summary-card", self.index_html)
        self.assertIn("id=\"monthly-return-val\"", self.index_html)
        self.assertIn("id=\"monthly-return-pct\"", self.index_html)
        self.assertIn("id=\"monthly-benchmarks-btn\"", self.index_html)
        self.assertIn("id=\"monthly-benchmarks-score\"", self.index_html)
        self.assertIn("id=\"monthly-benchmarks-dropdown\"", self.index_html)
        self.assertIn("id=\"monthly-deposit-status\"", self.index_html)
        self.assertIn("id=\"monthly-deposit-bar\"", self.index_html)
        self.assertIn("id=\"monthly-deposit-pct\"", self.index_html)
        self.assertIn("id=\"monthly-return-goal-status\"", self.index_html)
        self.assertIn("id=\"monthly-return-bar\"", self.index_html)
        self.assertIn("id=\"monthly-return-pct-goal\"", self.index_html)

        # Yearly summary elements
        self.assertIn("dash-yearly-summary-card", self.index_html)
        self.assertIn("id=\"yearly-return-val\"", self.index_html)
        self.assertIn("id=\"yearly-return-pct\"", self.index_html)
        self.assertIn("id=\"yearly-benchmarks-btn\"", self.index_html)
        self.assertIn("id=\"yearly-benchmarks-score\"", self.index_html)
        self.assertIn("id=\"yearly-benchmarks-dropdown\"", self.index_html)
        self.assertIn("id=\"yearly-deposit-status\"", self.index_html)
        self.assertIn("id=\"yearly-deposit-bar\"", self.index_html)
        self.assertIn("id=\"yearly-deposit-pct\"", self.index_html)
        self.assertIn("id=\"yearly-return-goal-status\"", self.index_html)
        self.assertIn("id=\"yearly-return-bar\"", self.index_html)
        self.assertIn("id=\"yearly-return-pct-goal\"", self.index_html)

    def test_css_classes_exist(self):
        self.assertIn(".dash-monthly-summary-card", self.main_css)
        self.assertIn(".dash-yearly-summary-card", self.main_css)
        self.assertIn(".monthly-summary-grid", self.main_css)
        self.assertIn(".yearly-summary-grid", self.main_css)
        self.assertIn(".monthly-metric-card", self.main_css)
        self.assertIn(".yearly-metric-card", self.main_css)
        self.assertIn(".monthly-bench-item", self.main_css)
        self.assertIn(".yearly-bench-item", self.main_css)
        self.assertIn(".progress-container", self.main_css)

    def test_js_logic_and_events(self):
        self.assertIn("DASHBOARD_BENCHMARK_COLS", self.dashboard_js)
        self.assertIn("toggleMonthlyBenchmarksList", self.dashboard_js)
        self.assertIn("toggleYearlyBenchmarksList", self.dashboard_js)
        self.assertIn("refreshMonthlySummary", self.dashboard_js)
        self.assertIn("refreshYearlySummary", self.dashboard_js)
        self.assertIn("getCurrentMonthString", self.dashboard_js)
        self.assertIn("getPreviousMonthString", self.dashboard_js)
        self.assertIn("function getMonthlySummaryPeriod(now = new Date())", self.dashboard_js)
        self.assertIn("if (reportDate.getDate() === 1)", self.dashboard_js)
        self.assertIn("function firstSnapshotOnOrAfter(snapshots, date)", self.dashboard_js)
        self.assertIn("function benchmarkReturnForPeriod(returns, monthStr, livePrice, completedMonth)", self.dashboard_js)
        self.assertIn("function previousMonthString(monthStr)", self.dashboard_js)
        self.assertIn("prevMonthReturn?.closePrice", self.dashboard_js)
        self.assertIn("const monthStartSnap = firstSnapshotOnOrAfter(snapshots, monthlyPeriod.startDate)", self.dashboard_js)
        self.assertIn("benchmarkReturnForPeriod(returns, currentMonthStr, livePrice, monthlyPeriod.completedMonth)", self.dashboard_js)
        self.assertIn("getPreviousYearEndString", self.dashboard_js)
        self.assertIn("liveDataReady", self.dashboard_js)
        self.assertIn("window.BENCHMARK_LIVE_PRICES", self.dashboard_js)

    def test_statistics_monthly_history_uses_month_start_periods(self):
        self.assertIn("function _buildPortfolioMonthlyPeriods(snapshots)", self.statistics_js)
        self.assertIn("function _firstSnapshotOnOrAfter(snapshots, date)", self.statistics_js)
        self.assertIn("const completedEnd = _firstSnapshotOnOrAfter(sorted, `${nextMonth}-01`);", self.statistics_js)
        self.assertIn("const rows = _buildPortfolioMonthlyPeriods(data).reverse();", self.statistics_js)
        self.assertIn("const monthlyPeriods = _buildPortfolioMonthlyPeriods(snapshotData);", self.statistics_js)
        self.assertNotIn("function _buildPortfolioMonthlyMap", self.statistics_js)

    def test_backend_live_prices_payload(self):
        self.assertIn("benchmarkLivePrices", self.handler_py)
        self.assertIn("benchmarkLivePrices", self.server_py)
        self.assertIn("MARKET_CAROUSEL_IDS = [", self.handler_py)
        self.assertIn("MSCI_WORLD", self.handler_py)
