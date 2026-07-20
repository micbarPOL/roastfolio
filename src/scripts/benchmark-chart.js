/**
 * benchmark-chart.js — "Return vs Benchmark" multi-series cumulative % return chart.
 *
 * Sits in the History tab. Lets the user pick one or more wallets and one or
 * more benchmarks (predefined indices + custom ticker search) and overlays their
 * cumulative % return from the start of the selected time window.
 *
 * Dependencies (loaded before this script):
 *   - Chart.js (global `Chart`)
 *   - portfolios.js (window.PortfolioClient)
 *   - chart.js  (_loadHistorySnapshots available as window function from chart.js)
 */

// ── Constants ────────────────────────────────────────────────────────────────

const BM_PREDEFINED = [
    { id: 'WIG',        name: 'WIG',         group: 'Warsaw' },
    { id: 'WIG20',      name: 'WIG20',        group: 'Warsaw' },
    { id: 'MWIG40',     name: 'mWIG40',       group: 'Warsaw' },
    { id: 'SWIG80',     name: 'sWIG80',       group: 'Warsaw' },
    { id: 'SP500',      name: 'S&P 500',      group: 'US' },
    { id: 'NASDAQ',     name: 'NASDAQ',       group: 'US' },
    { id: 'DAX',        name: 'DAX',          group: 'Europe' },
    { id: 'MSCI_WORLD', name: 'MSCI World',   group: 'Global' },
];

const BM_CANVAS_ID = 'benchmarkVsPortfolioChart';

// Curated palette — wallet colors (solid lines)
const WALLET_COLORS = [
    '#7db7d9', '#f4a261', '#e9c46a', '#2a9d8f', '#e76f51',
    '#90be6d', '#f9c74f', '#a8dadc', '#c77dff', '#ff6b6b',
];
// Benchmark colors (dashed lines)
const BM_COLORS = [
    '#f87171', '#fb923c', '#facc15', '#4ade80', '#34d399',
    '#22d3ee', '#818cf8', '#c084fc', '#f472b6', '#94a3b8',
];
// Dash patterns for benchmarks
const BM_DASHES = [
    [6, 3], [4, 4], [8, 3, 2, 3], [2, 4], [10, 3],
    [6, 2, 2, 2], [3, 3], [8, 2], [4, 2, 2, 2], [5, 5],
];

// ── State ────────────────────────────────────────────────────────────────────

let _bmRange            = '1Y';
let _selectedWallets    = new Set(['summary']);
let _selectedBenchmarks = new Set(['SP500']);
let _customTickers      = new Map();   // ticker → display name
let _chartInstance      = null;
let _snapshotCache      = null;
let _bmDailyCache       = new Map();   // id → {daily, name}
let _panelOpen          = false;

// ── Theme helpers ─────────────────────────────────────────────────────────────

function _darkMode() {
    return typeof window.isRoastfolioDark === 'function' ? window.isRoastfolioDark() : true;
}
function _textColor() {
    return _darkMode() ? '#e2e8f0' : '#102033';
}
function _gridColor(strong) {
    if (_darkMode()) return strong ? 'rgba(255,255,255,0.22)' : 'rgba(255,255,255,0.07)';
    return strong ? 'rgba(0, 96, 128, 0.28)' : 'rgba(0, 96, 128, 0.10)';
}

// ── Date / range helpers ──────────────────────────────────────────────────────

function _cutoffDate(range) {
    const now = new Date();
    const shift = function(y, m, d) {
        const r = new Date(now);
        if (y) r.setFullYear(r.getFullYear() + y);
        if (m) r.setMonth(r.getMonth() + m);
        if (d) r.setDate(r.getDate() + d);
        return r;
    };
    if (range === '10Y') return shift(-10, 0, 0);
    if (range === '5Y')  return shift(-5,  0, 0);
    if (range === '1Y')  return shift(-1,  0, 0);
    if (range === '6M')  return shift(0,  -6, 0);
    if (range === '3M')  return shift(0,  -3, 0);
    if (range === '1M')  return shift(0,  -1, 0);
    return null;
}

/** Forward-fill benchmark closes to match label dates. */
function _alignBenchmarkToLabels(bmDaily, labels) {
    const map = new Map(bmDaily.map(function(p) { return [p.t, p.c]; }));
    const result = [];
    let lastKnown = null;
    for (let i = 0; i < labels.length; i++) {
        if (map.has(labels[i])) lastKnown = map.get(labels[i]);
        result.push(lastKnown);
    }
    return result;
}

// ── Data loading ──────────────────────────────────────────────────────────────

async function _loadSnapshotData(force) {
    if (_snapshotCache && !force) return _snapshotCache;
    if (!window.PortfolioClient) return { summary: [], wallets: {} };
    try {
        const portfoliosResp = await PortfolioClient.listPortfolios();
        const portfolios = Array.isArray(portfoliosResp && portfoliosResp.portfolios) ? portfoliosResp.portfolios : [];
        const realPortfolios = portfolios.filter(function(p) {
            return String((p && p.portfolioId) || '').toLowerCase() !== 'summary';
        });

        const snapshotCalls = await Promise.all(
            [PortfolioClient.listSnapshots('summary').catch(function() { return { snapshots: [] }; })]
            .concat(realPortfolios.map(function(p) {
                return PortfolioClient.listSnapshots(p.portfolioId).catch(function() { return { snapshots: [] }; });
            }))
        );

        const summaryResp = snapshotCalls[0];
        const walletResps = snapshotCalls.slice(1);

        function sortRows(items) {
            return (items || [])
                .map(function(r) {
                    return {
                        date: String(r.snapshotDate || '').slice(0, 10),
                        value: Number(r.portfolioValue || 0),
                        investment: Number(r.investmentValue || 0),
                    };
                })
                .filter(function(r) { return r.date; })
                .sort(function(a, b) { return a.date.localeCompare(b.date); });
        }

        const wallets = {};
        realPortfolios.forEach(function(portfolio, index) {
            const name = String(portfolio.name || portfolio.portfolioId || '');
            wallets[name] = sortRows(walletResps[index] && walletResps[index].snapshots);
        });

        _snapshotCache = {
            summary: sortRows(summaryResp && summaryResp.snapshots),
            wallets: wallets,
        };
    } catch (e) {
        console.warn('[benchmark-chart] Failed to load snapshot data:', e);
        _snapshotCache = { summary: [], wallets: {} };
    }
    return _snapshotCache;
}

async function _loadBenchmarkDaily(idOrTicker, isCustom) {
    if (_bmDailyCache.has(idOrTicker)) return _bmDailyCache.get(idOrTicker);
    if (!window.PortfolioClient) return { daily: [], name: idOrTicker };
    try {
        const resp = await PortfolioClient.getBenchmarkDaily(idOrTicker, isCustom);
        const entry = { daily: (resp && resp.daily) || [], name: (resp && resp.name) || idOrTicker };
        _bmDailyCache.set(idOrTicker, entry);
        return entry;
    } catch (e) {
        console.warn('[benchmark-chart] Failed to load daily data for', idOrTicker, e);
        const entry = { daily: [], name: idOrTicker };
        _bmDailyCache.set(idOrTicker, entry);
        return entry;
    }
}

// ── Chart rendering ───────────────────────────────────────────────────────────

async function renderBenchmarkComparisonChart(force) {
    const canvas = document.getElementById(BM_CANVAS_ID);
    if (!canvas) return;

    _showBmMessage('Loading comparison data\u2026');

    try {
        // Load snapshot data and all selected benchmarks in parallel
        const bmIds = Array.from(_selectedBenchmarks);
        // Fetch snapshot first
        const snapData = await _loadSnapshotData(force);
        
        // Fetch benchmarks sequentially to avoid hitting Yahoo Finance rate limits
        // on cache misses (parallel requests from Lambda get tarpitted)
        const bmDataList = [];
        for (let i = 0; i < bmIds.length; i++) {
            const id = bmIds[i];
            const data = await _loadBenchmarkDaily(id, _customTickers.has(id));
            bmDataList.push(data);
        }

        // Build wallet series (date → TWR index)
        const walletSeriesMap = new Map();
        Array.from(_selectedWallets).forEach(function(wKey) {
            const rows = wKey === 'summary' ? snapData.summary : (snapData.wallets[wKey] || []);
            if (rows.length > 1) {
                let twrIndex = 1.0;
                let prevVal = null;
                let prevInv = null;
                
                const twrSeries = rows.map(function(r) {
                    if (prevVal !== null && prevInv !== null && prevVal > 0) {
                        const netCashFlow = r.investment - prevInv;
                        let dailyReturn = (r.value - netCashFlow) / prevVal - 1;
                        if (dailyReturn < -1) dailyReturn = -1; // Floor at -100% loss
                        twrIndex = twrIndex * (1 + dailyReturn);
                    }
                    prevVal = r.value;
                    prevInv = r.investment;
                    
                    return { t: r.date, v: twrIndex };
                });
                walletSeriesMap.set(wKey, twrSeries);
            }
        });

        const cutoff = _cutoffDate(_bmRange);

        // Build union of all date labels in the selected range
        const allDates = new Set();
        walletSeriesMap.forEach(function(series) {
            series.forEach(function(p) {
                if (!cutoff || new Date(p.t + 'T00:00:00') >= cutoff) allDates.add(p.t);
            });
        });
        bmDataList.forEach(function(bm) {
            (bm.daily || []).forEach(function(p) {
                if (!cutoff || new Date(p.t + 'T00:00:00') >= cutoff) allDates.add(p.t);
            });
        });

        const labels = Array.from(allDates).sort();

        if (labels.length === 0) {
            _showBmMessage('No data in the selected time range.');
            return;
        }

        const datasets = [];

        // --- Wallet datasets (solid lines) ---
        let wColorIdx = 0;
        walletSeriesMap.forEach(function(series, wKey) {
            const label = wKey === 'summary' ? 'My Portfolio (Total)' : ('Portfolio: ' + wKey);
            const color = WALLET_COLORS[wColorIdx % WALLET_COLORS.length];
            wColorIdx++;

            // Build map of date → value
            const valMap = new Map(series.map(function(p) { return [p.t, p.v]; }));

            // Forward-fill and filter to labels
            let lastV = null;
            const aligned = labels.map(function(lbl) {
                if (valMap.has(lbl)) lastV = valMap.get(lbl);
                return lastV;
            });

            // Find first non-null in range
            const firstNonNull = aligned.find(function(v) { return v != null && v > 0; });
            if (!firstNonNull) return;
            const baseVal = firstNonNull;

            const pctData = aligned.map(function(v) {
                return v == null ? null : ((v / baseVal) - 1) * 100;
            });

            datasets.push({
                label: label,
                data: pctData,
                borderColor: color,
                backgroundColor: 'transparent',
                borderWidth: 2.5,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.15,
                spanGaps: true,
                order: 2,
            });
        });

        // --- Benchmark datasets (dashed lines) ---
        let bmColorIdx = 0;
        bmIds.forEach(function(id, idx) {
            const bm = bmDataList[idx];
            if (!bm || !bm.daily || bm.daily.length === 0) return;

            const color = BM_COLORS[bmColorIdx % BM_COLORS.length];
            const dash  = BM_DASHES[bmColorIdx % BM_DASHES.length];
            bmColorIdx++;

            const aligned = _alignBenchmarkToLabels(bm.daily, labels);

            // Filter to cutoff window: find the earliest entry
            let cutoffIdx = 0;
            if (cutoff) {
                for (let i = 0; i < labels.length; i++) {
                    if (new Date(labels[i] + 'T00:00:00') >= cutoff) { cutoffIdx = i; break; }
                }
            }

            // Find first non-null value in range
            let baseVal = null;
            for (let i = cutoffIdx; i < aligned.length; i++) {
                if (aligned[i] != null && aligned[i] > 0) { baseVal = aligned[i]; break; }
            }
            if (!baseVal) return;

            const pctData = aligned.map(function(v, i) {
                if (i < cutoffIdx) return null;
                return v == null ? null : ((v / baseVal) - 1) * 100;
            });

            const displayName = _customTickers.get(id) || bm.name || id;

            datasets.push({
                label: displayName,
                data: pctData,
                borderColor: color,
                backgroundColor: 'transparent',
                borderWidth: 2,
                borderDash: dash,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.15,
                spanGaps: true,
                order: 3,
            });
        });

        if (datasets.length === 0) {
            _showBmMessage('Select at least one wallet or benchmark to compare.');
            return;
        }

        _clearBmMessage();
        _destroyBmChart();

        _chartInstance = new Chart(canvas, {
            type: 'line',
            data: { labels: labels, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: _textColor(),
                            boxWidth: 24,
                            font: { size: 12 },
                            generateLabels: function(chart) {
                                return chart.data.datasets.map(function(ds, i) {
                                    return {
                                        text: ds.label,
                                        fillStyle: ds.borderColor,
                                        strokeStyle: ds.borderColor,
                                        lineWidth: ds.borderWidth,
                                        lineDash: ds.borderDash || [],
                                        datasetIndex: i,
                                        hidden: !chart.isDatasetVisible(i),
                                    };
                                });
                            },
                        },
                    },
                    tooltip: {
                        callbacks: {
                            title: function(ctx) { return ctx[0] ? ctx[0].label : ''; },
                            label: function(ctx) {
                                const v = ctx.parsed.y;
                                if (v == null || isNaN(v)) return null;
                                return ctx.dataset.label + ': ' + (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: {
                            maxTicksLimit: (_bmRange === '5Y' || _bmRange === '10Y') ? 8 : 10,
                            maxRotation: 45,
                            color: _textColor(),
                            callback: function(val) {
                                const lbl = this.getLabelForValue(val);
                                if (!lbl) return '';
                                const d = new Date(lbl);
                                if (isNaN(d.getTime())) return lbl;
                                return d.toLocaleString('en-US', { month: 'short', year: 'numeric' });
                            },
                        },
                        grid: { color: _gridColor(false) },
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Cumulative Return (%)',
                            color: _textColor(),
                            font: { size: 11 },
                        },
                        ticks: {
                            color: _textColor(),
                            callback: function(v) { return (v >= 0 ? '+' : '') + v.toFixed(0) + '%'; },
                        },
                        grid: {
                            color: function(ctx) {
                                return ctx.tick.value === 0 ? _gridColor(true) : _gridColor(false);
                            },
                        },
                    },
                },
            },
        });
    } catch (err) {
        console.error('[benchmark-chart] Render error:', err);
        _showBmMessage('Failed to load comparison data.');
    }
}

function _destroyBmChart() {
    if (_chartInstance) { _chartInstance.destroy(); _chartInstance = null; }
    const existing = Chart.getChart(BM_CANVAS_ID);
    if (existing) existing.destroy();
}

function _showBmMessage(msg) {
    _destroyBmChart();
    const canvas = document.getElementById(BM_CANVAS_ID);
    if (!canvas) return;
    canvas.style.display = 'none';
    const wrap = canvas.parentElement;
    if (!wrap) return;
    let el = wrap.querySelector('.bm-vs-empty');
    if (!el) {
        el = document.createElement('div');
        el.className = 'bm-vs-empty';
        wrap.appendChild(el);
    }
    el.textContent = msg;
    el.style.display = 'flex';
}

function _clearBmMessage() {
    const canvas = document.getElementById(BM_CANVAS_ID);
    if (!canvas) return;
    canvas.style.display = '';
    const wrap = canvas.parentElement;
    if (!wrap) return;
    const el = wrap.querySelector('.bm-vs-empty');
    if (el) el.style.display = 'none';
}

// ── Selector Panel ────────────────────────────────────────────────────────────

function _buildSelectorPanel() {
    const panel = document.getElementById('bm-vs-panel');
    if (!panel) return;

    const wallets = _snapshotCache
        ? ['summary'].concat(Object.keys(_snapshotCache.wallets).sort())
        : ['summary'];

    const walletHTML = wallets.map(function(k) {
        const label = k === 'summary' ? 'Total Portfolio' : k;
        const active = _selectedWallets.has(k);
        return '<button class="bm-vs-pill' + (active ? ' bm-vs-pill--active' : '') + '" data-bm-wallet="' + k + '" onclick="window._bmToggleWallet(\'' + k + '\')">' + label + '</button>';
    }).join('');

    const bmHTML = BM_PREDEFINED.map(function(bm) {
        const active = _selectedBenchmarks.has(bm.id);
        return '<button class="bm-vs-pill' + (active ? ' bm-vs-pill--active' : '') + '" data-bm-id="' + bm.id + '" onclick="window._bmToggleBenchmark(\'' + bm.id + '\')">' + bm.name + '</button>';
    }).join('');

    const customHTML = Array.from(_customTickers.entries()).map(function(entry) {
        const ticker = entry[0];
        const name   = entry[1];
        const active = _selectedBenchmarks.has(ticker);
        return '<button class="bm-vs-pill' + (active ? ' bm-vs-pill--active' : '') + '" data-bm-id="' + ticker + '" onclick="window._bmToggleBenchmark(\'' + ticker + '\')">' + name + ' <span class="bm-vs-pill-remove" onclick="event.stopPropagation();window._bmRemoveCustom(\'' + ticker + '\')">\u00d7</span></button>';
    }).join('');

    panel.innerHTML = '<div class="bm-vs-panel-header">'
        + '<span class="bm-vs-panel-title">Select Series</span>'
        + '<button class="bm-vs-panel-close" onclick="window.closeBenchmarkSelector()">\u2715</button>'
        + '</div>'
        + '<div class="bm-vs-panel-section">'
        + '<div class="bm-vs-panel-label">Wallets</div>'
        + '<div class="bm-vs-pills">' + walletHTML + '</div>'
        + '</div>'
        + '<div class="bm-vs-panel-section">'
        + '<div class="bm-vs-panel-label">Benchmarks</div>'
        + '<div class="bm-vs-pills">' + bmHTML + customHTML + '</div>'
        + '</div>'
        + '<div class="bm-vs-panel-section">'
        + '<div class="bm-vs-panel-label">Add Custom Stock / Index</div>'
        + '<div class="bm-vs-search-row"><input class="bm-vs-search" id="bm-vs-search-input" type="text" placeholder="Search ticker or name\u2026" autocomplete="off" oninput="window._bmSearchInput(this.value)"><button class="bm-vs-search-clear" onclick="document.getElementById(\'bm-vs-search-input\').value=\'\';window._bmSearchInput(\'\');">\u2715</button></div>'
        + '<div class="bm-vs-search-results" id="bm-vs-search-results"></div>'
        + '</div>';
}

let _searchDebounce = null;

window._bmSearchInput = function(q) {
    clearTimeout(_searchDebounce);
    const resultsEl = document.getElementById('bm-vs-search-results');
    if (!resultsEl) return;
    if (!q || q.trim().length < 1) { resultsEl.innerHTML = ''; return; }
    resultsEl.innerHTML = '<div class="bm-vs-search-loading">Searching\u2026</div>';
    _searchDebounce = setTimeout(async function() {
        try {
            const cfg = window.__CONFIG__ || window.APP_CONFIG || {};
            const base = (cfg.apiUrl || '').replace(/\/prices$/, '');
            const token = window.AuthGuard && AuthGuard.getIdToken ? AuthGuard.getIdToken() : '';
            const resp = await fetch(base + '/search?q=' + encodeURIComponent(q.trim()), {
                headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
            });
            const data = await resp.json();
            const results = (data && data.results) || [];
            if (results.length === 0) {
                resultsEl.innerHTML = '<div class="bm-vs-search-loading">No results found.</div>';
                return;
            }
            resultsEl.innerHTML = results.slice(0, 8).map(function(r) {
                const sym  = (r.symbol || '').replace(/'/g, "\\'");
                const name = (r.name   || '').replace(/'/g, "\\'");
                return '<div class="bm-vs-search-result" onclick="window._bmAddCustom(\'' + sym + '\',\'' + name + '\')">'
                    + '<span class="bm-vs-result-symbol">' + (r.symbol || '') + '</span>'
                    + '<span class="bm-vs-result-name">' + (r.name || '') + '</span>'
                    + '<span class="bm-vs-result-exch">' + (r.exchange || '') + '</span>'
                    + '</div>';
            }).join('');
        } catch (e) {
            resultsEl.innerHTML = '<div class="bm-vs-search-loading">Search failed.</div>';
        }
    }, 350);
};

window._bmAddCustom = function(ticker, name) {
    _customTickers.set(ticker, name || ticker);
    _selectedBenchmarks.add(ticker);
    _buildSelectorPanel();
    renderBenchmarkComparisonChart();
};

window._bmRemoveCustom = function(ticker) {
    _customTickers.delete(ticker);
    _selectedBenchmarks.delete(ticker);
    _bmDailyCache.delete(ticker);
    _buildSelectorPanel();
    renderBenchmarkComparisonChart();
};

window._bmToggleWallet = function(key) {
    if (_selectedWallets.has(key)) {
        if (_selectedWallets.size > 1) _selectedWallets.delete(key);
    } else {
        _selectedWallets.add(key);
    }
    _buildSelectorPanel();
    renderBenchmarkComparisonChart();
};

window._bmToggleBenchmark = function(id) {
    if (_selectedBenchmarks.has(id)) {
        _selectedBenchmarks.delete(id);
    } else {
        _selectedBenchmarks.add(id);
    }
    _buildSelectorPanel();
    renderBenchmarkComparisonChart();
};

// ── Public API ────────────────────────────────────────────────────────────────

window.renderBenchmarkComparisonChart = renderBenchmarkComparisonChart;

window.setBenchmarkRange = function(range) {
    _bmRange = range;
    document.querySelectorAll('[data-bm-range]').forEach(function(btn) {
        btn.classList.toggle('active', btn.getAttribute('data-bm-range') === range);
    });
    renderBenchmarkComparisonChart();
};

window.openBenchmarkSelector = async function() {
    const panel = document.getElementById('bm-vs-panel');
    if (!panel) return;
    await _loadSnapshotData();
    _panelOpen = true;
    _buildSelectorPanel();
    panel.removeAttribute('hidden');
    panel.classList.add('bm-vs-panel--open');
};

window.closeBenchmarkSelector = function() {
    const panel = document.getElementById('bm-vs-panel');
    if (!panel) return;
    _panelOpen = false;
    panel.classList.remove('bm-vs-panel--open');
    panel.setAttribute('hidden', '');
};

// Close panel on outside click
document.addEventListener('click', function(e) {
    if (!_panelOpen) return;
    const panel = document.getElementById('bm-vs-panel');
    const btn   = document.getElementById('bm-vs-picker-btn');
    if (!panel || !btn) return;
    if (!panel.contains(e.target) && !btn.contains(e.target)) {
        window.closeBenchmarkSelector();
    }
});

// ── Lifecycle ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        if (document.getElementById(BM_CANVAS_ID)) {
            renderBenchmarkComparisonChart();
        }
    }, 900);
});

document.addEventListener('liveDataReady', function() {
    _snapshotCache = null;
    renderBenchmarkComparisonChart();
});

window.addEventListener('portfolioHistoryRecalculated', function() {
    _snapshotCache = null;
    renderBenchmarkComparisonChart();
});
