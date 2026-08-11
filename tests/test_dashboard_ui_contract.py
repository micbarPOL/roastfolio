import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DashboardUiContractTests(unittest.TestCase):
    def setUp(self):
        self.index_html = (ROOT / "src" / "index.html").read_text()
        self.dashboard_js = (ROOT / "src" / "scripts" / "dashboard.js").read_text()
        self.main_css = (ROOT / "src" / "styles" / "main.css").read_text()
        self.service_worker_js = (ROOT / "src" / "service-worker.js").read_text()
        self.user_profile_js = (ROOT / "src" / "scripts" / "user-profile.js").read_text()
        self.live_data_js = (ROOT / "src" / "scripts" / "live-data.js").read_text()

    def test_basic_user_only_has_dashboard_portfolio_user_and_wallet_access(self):
        self.assertNotIn("id=\"manage-btn\"", self.index_html)
        self.assertIn("openUserModal()", self.index_html)
        self.assertIn("showTab('dashboard')", self.index_html)
        self.assertIn("showTab('wallets')", self.index_html)
        self.assertIn("showTab('portfolio')", self.index_html)
        self.assertNotIn("scripts/data.js", self.index_html)
        self.assertNotIn("scripts/data-returns.js", self.index_html)

        self.assertIn("data-role=\"ADVANCED\" onclick=\"showTab('history');closeSidenav()\"", self.index_html)
        self.assertIn("data-role=\"ADVANCED\" onclick=\"showTab('statistics');closeSidenav()\"", self.index_html)
        self.assertIn("data-role=\"ADVANCED\" onclick=\"showTab('transactions');closeSidenav()\"", self.index_html)
        self.assertIn("document.querySelectorAll('[data-role=\"ADVANCED\"]')", self.user_profile_js)
        self.assertIn("btn.classList.add('tab-locked')", self.user_profile_js)

    def test_main_gauge_exposes_benchmark_and_portfolio_return_hooks(self):
        self.assertIn("id=\"gaugeChart\"", self.index_html)
        self.assertIn("id=\"gauge-benchmark-tooltip\"", self.index_html)
        self.assertIn("id=\"dash-daily-pln\"", self.index_html)

    def test_gauge_sarcastic_comment_uses_readable_typography(self):
        self.assertIn("styles/main.css?v=20260702c", self.index_html)
        self.assertIn("const CACHE_NAME = 'roastfolio-v66';", self.service_worker_js)
        self.assertIn("font-family: 'Aptos', 'Segoe UI', 'Helvetica Neue', sans-serif !important;", self.main_css)
        self.assertIn("font-style: normal;", self.main_css)
        self.assertIn("line-height: 1.55 !important;", self.main_css)
        self.assertIn(":root[data-theme=\"light\"] .bm-modern-roast .bm-msg", self.main_css)
        self.assertIn("#gauge-benchmark-tooltip.bm-modern-roast.bm-reveal .bm-msg", self.main_css)

        self.assertIn("const tooltipId = canvas.id === 'gaugeChart-mobile'", self.dashboard_js)
        self.assertIn(": 'gauge-benchmark-tooltip';", self.dashboard_js)
        self.assertIn("ctx.fillText(`${sign}${displayValue}%`", self.dashboard_js)
        self.assertIn("benchmarkValue != null", self.dashboard_js)
        self.assertIn("const benchmarkLabel = window.BENCHMARK_NAME || window.BENCHMARK_ID || 'Benchmark';", self.dashboard_js)
        self.assertIn("dailyPlnEl.innerHTML", self.dashboard_js)
        self.assertIn("dailyChangePLNSafe", self.dashboard_js)
        self.assertIn("pricePLNSafe", self.dashboard_js)
        portfolio_chart_js = (ROOT / "src" / "scripts" / "portfolio-chart.js").read_text()
        self.assertIn("const currentValue = Number.isFinite(Number(d.currentValue)) ? Number(d.currentValue) : 0;", portfolio_chart_js)
        self.assertIn("const purchaseValue = Number.isFinite(Number(d.purchaseValue)) ? Number(d.purchaseValue) : 0;", portfolio_chart_js)

    def test_market_commentary_is_visible_in_header_contract(self):
        self.assertIn("id=\"market-commentary\"", self.index_html)
        self.assertIn("data-market-commentary", self.index_html)
        self.assertIn("function renderMarketCommentary(pct, benchmarkName)", self.live_data_js)
        self.assertIn("const targets = Array.from(document.querySelectorAll('[data-market-commentary]'));", self.live_data_js)
        self.assertIn("Render a sarcastic Sheldon-style market commentary in the header.", self.live_data_js)
        self.assertIn("renderMarketCommentary(_bmVal, _bmName);", self.live_data_js)

    def test_mobile_gauge_exposes_benchmark_sarcasm_contract(self):
        self.assertIn("id=\"gauge-benchmark-tooltip-mobile\"", self.index_html)
        self.assertIn("canvas.id === 'gaugeChart-mobile'", self.dashboard_js)
        self.assertIn("? 'gauge-benchmark-tooltip-mobile'", self.dashboard_js)

    def test_live_data_prefers_chart_series_for_benchmark_pct(self):
        self.assertIn("function _benchmarkDailyPctCacheKey(benchmarkId)", self.live_data_js)
        self.assertIn("window.__walletBootstrapState = 'checking';", self.live_data_js)
        self.assertIn("async function checkWalletBootstrapState()", self.live_data_js)
        self.assertIn("document.dispatchEvent(new CustomEvent('walletBootstrapReady'", self.live_data_js)
        self.assertIn("if (!hasWallets && window.__walletBootstrapState === 'empty') return;", self.live_data_js)
        self.assertIn("if (window.__walletBootstrapState !== 'empty')", self.dashboard_js)
        self.assertIn("let walletsDone = false;", self.index_html)
        self.assertIn("document.addEventListener('walletBootstrapReady'", self.index_html)
        self.assertIn("function _buildApiUrl(view)", self.live_data_js)
        self.assertIn("const liteOk = await doFetch('lite');", self.live_data_js)
        self.assertIn("void doFetch('full', 1, { background: true });", self.live_data_js)
        self.assertIn("preserveDeferredData: isLite", self.live_data_js)
        self.assertIn("function _captureGaugeTooltipState()", self.live_data_js)
        self.assertIn("function _restoreGaugeTooltipState(snapshot)", self.live_data_js)
        self.assertIn("function _captureMarketCommentaryState()", self.live_data_js)
        self.assertIn("function _restoreMarketCommentaryState(snapshot)", self.live_data_js)
        self.assertIn("const freezeSecondaryNarrative = background && !isLite;", self.live_data_js)
        self.assertIn("const frozenGaugeComment = freezeSecondaryNarrative ? _captureGaugeTooltipState() : null;", self.live_data_js)
        self.assertIn("const frozenMarketCommentary = freezeSecondaryNarrative ? _captureMarketCommentaryState() : null;", self.live_data_js)
        self.assertIn("if (frozenGaugeComment) _restoreGaugeTooltipState(frozenGaugeComment);", self.live_data_js)
        self.assertIn("_restoreMarketCommentaryState(frozenMarketCommentary);", self.live_data_js)
        self.assertIn("const benchmarkPayload = data.benchmarkData || data.wigData || null;", self.live_data_js)
        self.assertIn("computeBenchmarkDailyPct(benchmarkPayload, window.BENCHMARK_ID)", self.live_data_js)
        self.assertIn("window.MARKET_CAROUSEL = Array.isArray(data.marketCarousel) ? data.marketCarousel : [];", self.live_data_js)
        self.assertIn("e.name === 'AbortError'", self.live_data_js)
        self.assertIn("const RETRY_TIMEOUT_MS = 45000;", self.live_data_js)
        self.assertIn("return doFetch(view, attempt + 1, options);", self.live_data_js)
        self.assertNotIn("reloadScript('scripts/portfolio-data.js')", self.live_data_js)

    def test_market_index_carousel_hooks_exist(self):
        self.assertIn("id=\"market-index-carousel\"", self.index_html)
        self.assertIn("id=\"market-index-carousel-top-mobile\"", self.index_html)
        self.assertIn("data-market-carousel", self.index_html)
        self.assertIn("market-index-carousel-shell", self.index_html)
        self.assertIn("function renderMarketIndexCarousel()", self.dashboard_js)
        self.assertIn("function getMarketCarouselShells()", self.dashboard_js)
        self.assertIn("market-ticker-item", self.dashboard_js)
        self.assertIn("@keyframes marketTickerScroll", self.main_css)
        self.assertIn("margin-left: -24px;", self.main_css)
        self.assertIn("margin-bottom: -24px;", self.main_css)
        self.assertIn("window.MARKET_CAROUSEL", self.dashboard_js)

    def test_benchmark_chart_can_reset_to_smart_range(self):
        wig_chart_js = (ROOT / "src" / "scripts" / "wig-chart.js").read_text()
        self.assertIn("let _benchmarkRangeUserSelected = false;", wig_chart_js)
        self.assertIn("window.resetBenchmarkRangeAuto = function()", wig_chart_js)
        self.assertIn("!_benchmarkRangeUserSelected", wig_chart_js)

    def test_ath_celebration_hooks_exist(self):
        self.assertIn("id=\"dash-ath-celebration\"", self.index_html)
        self.assertIn("const ATH_CELEBRATION_NOTES = [", self.dashboard_js)
        self.assertIn("function isPortfolioAtNewAth()", self.dashboard_js)
        self.assertIn("function renderAthCelebration(targetId)", self.dashboard_js)
        self.assertIn("function athCelebrationMarkup(title, note, gain)", self.dashboard_js)
        self.assertIn("ath-hologram", self.dashboard_js)
        self.assertIn("ath-record-core", self.dashboard_js)
        self.assertIn("athRecordCore", self.main_css)
        self.assertIn(":root[data-theme=\"light\"] .gauge-ath-celebration", self.main_css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.main_css)

    def test_service_worker_prefers_fresh_shell_assets(self):
        self.assertIn("const CACHE_NAME = 'roastfolio-v66';", self.service_worker_js)
        self.assertIn("/scripts/ledger-transactions.js", self.service_worker_js)
        self.assertIn("function isShellAsset(url, request)", self.service_worker_js)
        self.assertIn("request.mode === 'navigate'", self.service_worker_js)
        self.assertIn("self.addEventListener('message'", self.service_worker_js)
        self.assertIn("event.data.type === 'SKIP_WAITING'", self.service_worker_js)
        self.assertIn("reg.update().catch(() => {});", self.index_html)
        self.assertIn("service-worker.js?v=20260702b", self.index_html)

    def test_gauge_animation_uses_modern_neon_transition_hooks(self):
        self.assertIn("const _pulseP = (_animProgress && _animProgress.pulse != null)", self.dashboard_js)
        self.assertIn("gauge-booting", self.dashboard_js)
        self.assertIn("gauge-booted", self.dashboard_js)
        self.assertIn("const trackRadius = r - arcWidth * 0.22;", self.dashboard_js)
        self.assertIn("const isDarkTheme = typeof window.isRoastfolioDark === 'function'", self.dashboard_js)
        self.assertIn("const isLightTheme = !isDarkTheme;", self.dashboard_js)
        self.assertIn("function valueToGaugeAngle(rawValue, progress)", self.dashboard_js)
        self.assertIn("const neonScaleSegments = [", self.dashboard_js)
        self.assertIn("const portfolioAngleForDiff = valueToGaugeAngle(clamped, _portP);", self.dashboard_js)
        self.assertIn("const diffArcColor = isAhead ? diffGreen : diffRed;", self.dashboard_js)
        self.assertIn("ctx.strokeStyle = diffArcColor;", self.dashboard_js)
        self.assertIn("ctx.strokeStyle = benchmarkMarkerColor;", self.dashboard_js)
        self.assertIn("const valueTextColor = isLightTheme", self.dashboard_js)
        self.assertIn("const valueTextGlow = isLightTheme", self.dashboard_js)
        self.assertIn("const needleColor = isLightTheme", self.dashboard_js)
        self.assertIn("const needleOutline = isLightTheme", self.dashboard_js)
        self.assertIn("const needleBladeGradient = ctx.createLinearGradient", self.dashboard_js)
        self.assertIn("function drawNeedleBlade(offset)", self.dashboard_js)
        self.assertIn("ctx.fillStyle = needleBladeGradient;", self.dashboard_js)
        self.assertIn("ctx.lineWidth = Math.max(isCompact ? 5 : 6, trackWidth * 1.05);", self.dashboard_js)
        self.assertIn("needleX + needleDx * needleTipReach", self.dashboard_js)
        self.assertIn("const scaleLabels = ['-2%', '0%', '+2%'];", self.dashboard_js)
        self.assertNotIn("ctx.setLineDash([4, 6]);", self.dashboard_js)
        self.assertIn("const portP = easeOutQuint(Math.min(elapsed / PORT_END, 1));", self.dashboard_js)
        self.assertIn("contain: paint;", self.main_css)
        self.assertIn("splash-to-gauge", self.index_html)
        self.assertIn("body.splash-to-gauge", self.main_css)
        self.assertIn("styles/main.css?v=20260702c", self.index_html)
        self.assertIn("scripts/dashboard.js?v=20260709b", self.index_html)
        self.assertIn("candleTransmitOut", self.main_css)
        self.assertIn("gaugeCardHandoff", self.main_css)
        self.assertIn("roastTransmissionSweep", self.main_css)

    def test_todays_movers_excludes_cash(self):
        self.assertIn("function isCashHoldingItem(item)", self.dashboard_js)
        self.assertIn("filter(d => !isCashHoldingItem(d))", self.dashboard_js)


if __name__ == "__main__":
    unittest.main()
