/**
 * Benchmark Chart — Yahoo Finance-style
 * Uses TradingView Lightweight Charts v4 (loaded from CDN)
 * Data fed by live-data.js (Lambda benchmarkData payload)
 */

let _benchmarkChart      = null;
let _benchmarkMainSeries = null;
let _benchmarkVolSeries  = null;
let _benchmarkData       = null;
let _benchmarkRange      = null;   // set on first render
let _benchmarkRangeUserSelected = false;
let _benchmarkChartType  = 'line'; // 'line' | 'candle'

// ── Session detection ─────────────────────────────────────────
// WSE Warsaw: Mon–Fri 09:00–17:05 CET (UTC+1) / CEST (UTC+2)
function isWseSessionOpen() {
    const now = new Date();
    const dow = now.getUTCDay(); // 0=Sun, 6=Sat
    if (dow === 0 || dow === 6) return false;
    const m = now.getUTCMonth(); // 0=Jan
    const offset = (m >= 2 && m <= 9) ? 2 : 1; // CEST vs CET
    const warsawMin = now.getUTCHours() * 60 + now.getUTCMinutes() + offset * 60;
    return warsawMin >= 9 * 60 && warsawMin < 17 * 60 + 5;
}

function pickSmartRange(benchmarkData) {
    const hasIntra  = (benchmarkData.intraday || []).length > 0;
    if (hasIntra) return '1D';
    return '1Y';
}

// ── Data filtering ────────────────────────────────────────────
function getFilteredPoints(benchmarkData, range) {
    if (range === '1D') {
        // Always show today's 1-minute intraday data
        if ((benchmarkData.intraday || []).length > 0) return benchmarkData.intraday;
        // Fallback: last day from hourly if intraday unavailable
        const hourly = benchmarkData.hourly || [];
        if (hourly.length > 0) {
            const lastTs  = hourly[hourly.length - 1].t;
            const lastDay = new Date(lastTs * 1000).toISOString().slice(0, 10);
            const cutoff  = new Date(lastDay).getTime() / 1000;
            return hourly.filter(p => p.t >= cutoff);
        }
        const daily = benchmarkData.daily || [];
        return daily.length ? [daily[daily.length - 1]] : [];
    }

    const srcMap = { 'YTD': 'daily', '1Y': 'daily' };
    const points = benchmarkData[srcMap[range] || 'daily'] || [];
    const now    = new Date();
    let cutoff   = null;

    if      (range === 'YTD') { cutoff = `${now.getFullYear()}-01-01`; }
    else if (range === '1Y')  { const d = new Date(now); d.setFullYear(d.getFullYear() - 1); cutoff = d.toISOString().slice(0, 10); }

    return cutoff ? points.filter(p => p.t >= cutoff) : points;
}

// ── Helpers ───────────────────────────────────────────────────
function fmtP(v) {
    return typeof v === 'number' ? v.toLocaleString('pl-PL', { maximumFractionDigits: 2 }) : '—';
}

function updateBenchmarkChartLabels() {
    const name = window.BENCHMARK_NAME || 'Benchmark';
    const title = document.getElementById('benchmark-chart-title');
    const noData = document.getElementById('benchmark-no-data');
    if (title) title.textContent = name;
    if (noData) noData.textContent = `Refresh prices to load ${name} chart data`;
}

function getBenchmarkThemeColors() {
    const isDark = typeof window.isRoastfolioDark === 'function'
        ? window.isRoastfolioDark()
        : window.matchMedia('(prefers-color-scheme: dark)').matches;
    return isDark
        ? {
            background: 'transparent',
            text: '#c8e3f5',
            grid: 'rgba(255,255,255,0.05)',
            crosshair: '#6ea8c8',
            label: '#0ea5e9',
        }
        : {
            background: 'transparent',
            text: '#102033',
            grid: 'rgba(0,80,120,0.08)',
            crosshair: '#3d8aa8',
            label: '#009ec3',
        };
}

function destroyBenchmarkChart() {
    if (_benchmarkChart) {
        _benchmarkChart.remove();
        _benchmarkChart = null;
        _benchmarkMainSeries = null;
        _benchmarkVolSeries = null;
    }
}

// ── Main render ───────────────────────────────────────────────
function renderBenchmarkChart(benchmarkData, range, chartType) {
    if (!benchmarkData) return;
    _benchmarkData = benchmarkData;
    if (range) {
        _benchmarkRange = range;
    } else if (!_benchmarkRange || !_benchmarkRangeUserSelected) {
        _benchmarkRange = pickSmartRange(benchmarkData);
    }
    if (chartType) _benchmarkChartType = chartType;
    updateBenchmarkChartLabels();

    const container = document.getElementById('benchmarkChartContainer');
    if (!container) return;

    if (typeof LightweightCharts === 'undefined') {
        container.innerHTML = '<p style="padding:20px;color:#888">Chart library failed to load</p>';
        return;
    }

    destroyBenchmarkChart();

    const noData = document.getElementById('benchmark-no-data');
    const clLoader = document.getElementById('benchmark-cl-loader');
    if (clLoader) clLoader.style.display = 'flex';

    const points = getFilteredPoints(_benchmarkData, _benchmarkRange);

    if (!points.length) {
        if (noData) noData.style.display = '';
        if (clLoader) clLoader.style.display = 'none';
        return;
    }
    if (noData) noData.style.display = 'none';
    if (clLoader) clLoader.style.display = 'none';

    const firstC = points[0].c;
    const lastC  = points[points.length - 1].c;

    // Selected-range performance (for secondary line when range is not 1D)
    const rangeBase = (_benchmarkRange === '1D' && points[0] && typeof points[0].o === 'number')
        ? points[0].o
        : firstC;
    const rangeDiff = rangeBase ? (lastC - rangeBase) : 0;
    const rangePct = rangeBase ? (rangeDiff / rangeBase * 100) : 0;
    const rangeUp = rangeDiff >= 0;

    // Primary badge value must always be current daily change (1D), aligned with gauge/comment source.
    const dailyPctRaw = (typeof window.BENCHMARK_DAILY_PCT === 'number' && !Number.isNaN(window.BENCHMARK_DAILY_PCT))
        ? window.BENCHMARK_DAILY_PCT
        : (typeof window.computeBenchmarkDailyPct === 'function' ? window.computeBenchmarkDailyPct(_benchmarkData || benchmarkData, window.BENCHMARK_ID) : null);
    const dailyPct = (typeof dailyPctRaw === 'number' && !Number.isNaN(dailyPctRaw)) ? dailyPctRaw : null;
    const dailyUp = (dailyPct == null) ? true : dailyPct >= 0;
    const color  = dailyUp ? '#16a34a' : '#dc2626';

    // Change badge
    const badge = document.getElementById('benchmark-change-badge');
    if (badge) {
        const dailyText = dailyPct == null
            ? '—'
            : `${dailyUp ? '+' : ''}${dailyPct.toFixed(2)}%`;
        const primary = `<span class="wig-badge-primary">${dailyUp ? '▲' : '▼'} ${dailyText} 1D</span>`;

        if (_benchmarkRange !== '1D' && rangeBase) {
            const rangeLabel = _benchmarkRange === 'YTD' ? 'YTD' : _benchmarkRange === '1Y' ? '1Y' : _benchmarkRange;
            const rangeText = `${rangeUp ? '+' : ''}${rangePct.toFixed(2)}%`;
            const secondary = `<span class="wig-badge-secondary">${rangeLabel}: ${rangeUp ? '▲' : '▼'} ${rangeText}</span>`;
            badge.innerHTML = primary + secondary;
            badge.classList.add('wig-change-badge--stacked');
        } else {
            badge.innerHTML = primary;
            badge.classList.remove('wig-change-badge--stacked');
        }
        badge.style.color = color;
    }

    const intraday = _benchmarkRange === '1D';
    const theme = getBenchmarkThemeColors();

    _benchmarkChart = LightweightCharts.createChart(container, {
        autoSize: true,
        layout: { background: { color: theme.background }, textColor: theme.text, fontSize: 12 },
        grid: { vertLines: { color: theme.grid }, horzLines: { color: theme.grid } },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: { color: theme.crosshair, width: 1, style: 1, labelBackgroundColor: theme.label },
            horzLine: { color: theme.crosshair, width: 1, style: 1, labelBackgroundColor: theme.label },
        },
        rightPriceScale: {
            borderVisible: false,
            scaleMargins: { top: 0.08, bottom: 0.22 },
        },
        localization: {
            timeFormatter: (time) => {
                const d = new Date(typeof time === 'number' ? time * 1000 : time);
                return new Intl.DateTimeFormat('pl-PL', {
                    timeZone: 'Europe/Warsaw',
                    year: 'numeric', month: '2-digit', day: '2-digit',
                    ...(intraday ? { hour: '2-digit', minute: '2-digit' } : {}),
                }).format(d);
            },
        },
        timeScale: {
            borderVisible: false,
            timeVisible: intraday,
            secondsVisible: false,
            fixLeftEdge: true,
            fixRightEdge: true,
            tickMarkFormatter: (time, tickMarkType) => {
                const d = new Date(typeof time === 'number' ? time * 1000 : time);
                const opts = { timeZone: 'Europe/Warsaw' };
                if (intraday) {
                    return new Intl.DateTimeFormat('pl-PL', { ...opts, hour: '2-digit', minute: '2-digit' }).format(d);
                }
                // For daily/weekly/monthly show day+month, or just year at year boundaries
                if (tickMarkType <= 1) { // year or month tick
                    return new Intl.DateTimeFormat('pl-PL', { ...opts, month: 'short', year: 'numeric' }).format(d);
                }
                return new Intl.DateTimeFormat('pl-PL', { ...opts, day: '2-digit', month: 'short' }).format(d);
            },
        },
    });

    // Main series: Candlestick or Area
    if (_benchmarkChartType === 'candle') {
        _benchmarkMainSeries = _benchmarkChart.addCandlestickSeries({
            upColor:         '#16a34a', downColor:       '#dc2626',
            borderUpColor:   '#16a34a', borderDownColor: '#dc2626',
            wickUpColor:     '#16a34a', wickDownColor:   '#dc2626',
        });
        _benchmarkMainSeries.setData(points.map(p => ({
            time: p.t, open: p.o, high: p.h, low: p.l, close: p.c,
        })));
    } else {
        _benchmarkMainSeries = _benchmarkChart.addAreaSeries({
            lineColor: color,
            topColor:    dailyUp ? 'rgba(22,163,74,0.15)' : 'rgba(220,38,38,0.15)',
            bottomColor: 'rgba(255,255,255,0)',
            lineWidth: 2,
            crosshairMarkerVisible: true,
            crosshairMarkerRadius: 4,
            crosshairMarkerBackgroundColor: color,
        });
        _benchmarkMainSeries.setData(points.map(p => ({ time: p.t, value: p.c })));
    }

    // Volume histogram (bottom 15% of chart)
    if (points.some(p => p.v > 0)) {
        _benchmarkVolSeries = _benchmarkChart.addHistogramSeries({
            priceScaleId: 'vol',
            priceFormat: { type: 'volume' },
        });
        _benchmarkChart.priceScale('vol').applyOptions({
            scaleMargins: { top: 0.85, bottom: 0 },
        });
        _benchmarkVolSeries.setData(points.map((p, i) => ({
            time:  p.t,
            value: p.v,
            color: (i === 0 || p.c >= (points[i - 1]?.c ?? p.c))
                   ? 'rgba(22,163,74,0.3)' : 'rgba(220,38,38,0.3)',
        })));
    }

    _benchmarkChart.timeScale().fitContent();

    // OHLC/price legend on crosshair hover
    const legend = document.getElementById('benchmark-ohlc-legend');
    _benchmarkChart.subscribeCrosshairMove(param => {
        if (!legend || !_benchmarkMainSeries) return;
        if (!param.point || !param.seriesData.has(_benchmarkMainSeries)) {
            legend.innerHTML = '';
            return;
        }
        const d = param.seriesData.get(_benchmarkMainSeries);
        if (_benchmarkChartType === 'candle') {
            const up = d.close >= d.open;
            const c  = up ? '#16a34a' : '#dc2626';
            legend.innerHTML =
                `<span class="wig-ohlc-l">O</span> ${fmtP(d.open)} ` +
                `<span class="wig-ohlc-l">H</span> ${fmtP(d.high)} ` +
                `<span class="wig-ohlc-l">L</span> ${fmtP(d.low)} ` +
                `<span class="wig-ohlc-l">C</span> <span style="color:${c}">${fmtP(d.close)}</span>`;
        } else {
            legend.innerHTML = `<strong style="color:${color}">${fmtP(d.value)}</strong> pkt`;
        }
    });

    syncBenchmarkButtons();
}

window.addEventListener('roastfolio:themechange', () => {
    if (_benchmarkData) renderBenchmarkChart(_benchmarkData, _benchmarkRange, _benchmarkChartType);
});

function syncBenchmarkButtons() {
    document.querySelectorAll('.benchmark-range-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.range === _benchmarkRange));
    document.querySelectorAll('.benchmark-type-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.type === _benchmarkChartType));
}

window.setBenchmarkRange = function(range) {
    _benchmarkRangeUserSelected = true;
    _benchmarkRange = range;

    // Historical ranges need daily data that is fetched on-demand (not bundled in the full response).
    if (range !== '1D') {
        const hasDailyData = window.BENCHMARK_DATA && (window.BENCHMARK_DATA.daily || []).length > 0;
        if (!hasDailyData && typeof window.fetchBenchmarkHistory === 'function') {
            // Show a loading placeholder while the history lambda wakes up
            const noData = document.getElementById('benchmark-no-data');
            if (noData) { noData.textContent = 'Loading historical data…'; noData.style.display = ''; }
            window.fetchBenchmarkHistory().then(() => {
                // applyLiveData (history) already calls renderBenchmarkChart; nothing more needed
            }).catch(() => {
                if (noData) { noData.textContent = 'Failed to load history — try again'; noData.style.display = ''; }
            });
            return;
        }
    }

    renderBenchmarkChart(_benchmarkData, range, _benchmarkChartType);
};

window.setBenchmarkChartType = function(type) {
    _benchmarkChartType = type;
    renderBenchmarkChart(_benchmarkData, _benchmarkRange, type);
};

window.resetBenchmarkRangeAuto = function() {
    _benchmarkRangeUserSelected = false;
    _benchmarkRange = null;
};

window.renderBenchmarkChart = renderBenchmarkChart;
window.updateBenchmarkChartLabels = updateBenchmarkChartLabels;
window.setWigRange = window.setBenchmarkRange;
window.setWigChartType = window.setBenchmarkChartType;
window.renderWigChart = window.renderBenchmarkChart;
