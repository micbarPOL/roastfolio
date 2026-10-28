const _historyCharts = {};
let _historyLoadPromise = null;
let _cachedHistoryData = null;
let _historyRange = '1Y';
let _historyReturnMode = 'pct';
let _historyMonthlyMetric = 'gain'; // 'gain' | 'deposit'
let _historyDailyMode = 'pct';
let _historyWalletKey = 'summary'; // 'summary' | wallet name
const _historyBenchmarks = [
    { id: 'WIG', label: 'WIG', color: '#f59e0b' },
    { id: 'SP500', label: 'S&P 500', color: '#a855f7' },
    { id: 'MSCI_WORLD', label: 'MSCI World', color: '#6a8ba8' },
];
const _historySelectedBenchmarks = new Set(['WIG']);
const _historyBenchmarkCache = new Map();
function _chartTextColor() {
    return (typeof window.isRoastfolioDark === 'function' && !window.isRoastfolioDark()) ? '#102033' : '#e2e8f0';
}

function _chartGridColor(strong = false) {
    const light = typeof window.isRoastfolioDark === 'function' && !window.isRoastfolioDark();
    if (light) return strong ? 'rgba(0, 96, 128, 0.28)' : 'rgba(0, 96, 128, 0.10)';
    return strong ? 'rgba(255,255,255,0.22)' : 'rgba(255,255,255,0.07)';
}

function _chartDotColor() {
    return (typeof window.isRoastfolioDark === 'function' && !window.isRoastfolioDark()) ? 'rgba(0, 126, 160, 0.82)' : 'rgba(168,216,234,0.82)';
}

function _cssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
}

function _isCompatibleLivePoint(rows, liveValue) {
    const value = Number(liveValue);
    if (!Number.isFinite(value) || value <= 0 || !rows || !rows.length) return false;
    const latest = Number(rows[rows.length - 1].value || 0);
    if (!Number.isFinite(latest) || latest <= 0) return true;
    const ratio = value / latest;
    return ratio >= 0.55 && ratio <= 1.45;
}

function _fmtHistoryMoney(value, showSign = false) {
    if (value == null || value === '' || !Number.isFinite(Number(value))) return '—';
    const amount = Number(value);
    const sign = amount < 0 ? '-' : showSign && amount > 0 ? '+' : '';
    return `${sign}${Math.abs(amount).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN`;
}

function _fmtHistoryPct(value, showSign = false, digits = 2) {
    if (value == null || value === '' || !Number.isFinite(Number(value))) return '—';
    const amount = Number(value);
    const sign = showSign && amount > 0 ? '+' : '';
    return `${sign}${amount.toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
}

function _historyTone(value) {
    const n = Number(value);
    return n > 0 ? 'up' : n < 0 ? 'down' : '';
}

function _destroyHistoryChart(canvasId) {
    const existing = _historyCharts[canvasId] || Chart.getChart(canvasId);
    if (existing) existing.destroy();
    delete _historyCharts[canvasId];
}

function _setChartMessage(canvasId, message) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    _destroyHistoryChart(canvasId);
    const wrap = canvas.parentElement;
    if (!wrap) return;
    let note = wrap.querySelector('.history-empty-state');
    if (!note) {
        note = document.createElement('div');
        note.className = 'history-empty-state';
        note.style.cssText = 'display:flex;align-items:center;justify-content:center;height:100%;color:#888;font-size:13px;text-align:center;padding:24px;';
        wrap.appendChild(note);
    }
    note.textContent = message;
    canvas.style.display = 'none';
}

function _clearChartMessage(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const wrap = canvas.parentElement;
    if (!wrap) return;
    const note = wrap.querySelector('.history-empty-state');
    if (note) note.remove();
    canvas.style.display = '';
}

function _findChartLoader(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    return canvas.parentElement ? canvas.parentElement.querySelector('.history-chart-loader') : null;
}

function _showHistoryChartLoader(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const wrap = canvas.parentElement;
    if (!wrap) return;
    let loader = wrap.querySelector('.history-chart-loader');
    if (!loader) {
        loader = document.createElement('div');
        loader.className = 'history-chart-loader';
        loader.innerHTML = `
            <div class="cl-loader">
                <div class="cl-candles">
                    <div class="cl-candle cl-bull" style="--d:0s"><span class="cl-body" style="--t:15%;--h:55%"></span></div>
                    <div class="cl-candle cl-bear" style="--d:.18s"><span class="cl-body" style="--t:28%;--h:48%"></span></div>
                    <div class="cl-candle cl-bull" style="--d:.36s"><span class="cl-body" style="--t:8%;--h:38%"></span></div>
                    <div class="cl-candle cl-bull" style="--d:.54s"><span class="cl-body" style="--t:5%;--h:65%"></span></div>
                    <div class="cl-candle cl-bear" style="--d:.72s"><span class="cl-body" style="--t:32%;--h:42%"></span></div>
                    <div class="cl-candle cl-bull" style="--d:.90s"><span class="cl-body" style="--t:10%;--h:58%"></span></div>
                </div>
                <span class="cl-loader-text">Loading chart…</span>
            </div>
        `;
        wrap.appendChild(loader);
    }
    wrap.classList.add('is-loading');
    loader.style.display = 'flex';
    loader.style.opacity = '1';
    const note = wrap.querySelector('.history-empty-state');
    if (note) note.style.display = 'none';
    if (canvas) {
        canvas.style.visibility = 'hidden';
        canvas.style.opacity = '0';
    }
}

function _hideHistoryChartLoader(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const wrap = canvas.parentElement;
    if (!wrap) return;
    const loader = wrap.querySelector('.history-chart-loader');
    if (loader) {
        loader.style.opacity = '0';
        setTimeout(() => {
            loader.style.display = 'none';
        }, 180);
    }
    wrap.classList.remove('is-loading');
    const note = wrap.querySelector('.history-empty-state');
    if (note) note.style.display = 'flex';
    canvas.style.visibility = '';
    canvas.style.opacity = '';
}

function _getResamplingStrategy(range, dates) {
    // Show full daily resolution across all ranges (ALL, 5Y, 3Y, 1Y, YTD, 1M, 1W)
    return 'daily';
}

function _resampleHistoryDates(dates, strategy) {
    if (strategy === 'daily') return dates;
    
    const grouped = new Map();
    dates.forEach(d => {
        let key = d;
        if (strategy === 'monthly') {
            key = d.substring(0, 7); // YYYY-MM
        } else if (strategy === 'weekly') {
            const dt = new Date(d + 'T00:00:00');
            const epochDays = Math.floor(dt.getTime() / 86400000);
            key = 'W' + Math.floor((epochDays + 3) / 7);
        }
        grouped.set(key, d);
    });
    return Array.from(grouped.values()).sort();
}

function _resampleHistoryRows(rows, strategy) {
    if (strategy === 'daily') return rows;
    const keptDates = new Set(_resampleHistoryDates(rows.map(r => r.date), strategy));
    return rows.filter(r => keptDates.has(r.date));
}

function _sortSnapshotsAscending(items) {
    const sorted = [...(items || [])]
        .map(item => ({
            date: String(item.snapshotDate || '').slice(0, 10),
            value: Number(item.portfolioValue || 0),
            investment: Number(item.investmentValue || 0),
            unitPrice: item.unitPrice ?? item.unit_price ?? null,
            cumulativeReturnPct: item.cumulativeReturnPct ?? item.cumulative_return_pct ?? null,
        }))
        .filter(item => item.date)
        .sort((a, b) => a.date.localeCompare(b.date));

    let runningMax = 0;
    let lastAthDate = '';
    for (const row of sorted) {
        row.isAthPeak = false;
        if (row.value > runningMax) {
            runningMax = row.value;
            lastAthDate = row.date;
            row.isAthPeak = true;
        }
        row.runningAth = runningMax;
        row.lastAthDate = lastAthDate;
    }
    return sorted;
}

function _walletHistoryCanvasId(name) {
    return 'historyChartWallet-' + String(name || '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}

function _isFiniteNumber(value) {
    const n = Number(value);
    return Number.isFinite(n);
}

function _resolveTwrPct(row) {
    if (row && row.cumulativeReturnPct != null && row.cumulativeReturnPct !== '') {
        const pct = Number(row.cumulativeReturnPct);
        if (Number.isFinite(pct)) return pct;
    }
    if (row && row.unitPrice != null && row.unitPrice !== '') {
        const unit = Number(row.unitPrice);
        if (Number.isFinite(unit) && unit > 0) return ((unit / 100) - 1) * 100;
    }
    return null;
}

function _twrCarryForDate(rows, dateStr) {
    const previous = [...(rows || [])]
        .reverse()
        .find(row => row && row.date < dateStr && _resolveTwrPct(row) != null);

    if (!previous) return { unitPrice: null, cumulativeReturnPct: null };
    return {
        unitPrice: _isFiniteNumber(previous.unitPrice) ? Number(previous.unitPrice) : null,
        cumulativeReturnPct: _isFiniteNumber(previous.cumulativeReturnPct) ? Number(previous.cumulativeReturnPct) : _resolveTwrPct(previous),
    };
}

function _renderWalletBtns(walletNames) {
    const strip = document.getElementById('history-wallet-btns');
    if (!strip) return;
    const all = ['summary', ...walletNames];
    strip.innerHTML = all.map(key => {
        const label = key === 'summary' ? 'Total' : key;
        const active = key === _historyWalletKey;
        return `<button class="history-wallet-btn hx-chip${active ? ' is-active' : ''}" type="button" role="tab" aria-selected="${active ? 'true' : 'false'}" data-wallet-key="${key}" onclick="setHistoryWallet('${key.replace(/'/g, "\\'")}')">${label}</button>`;
    }).join('');
}

async function _loadHistorySnapshots(force = false) {
    if (!window.PortfolioClient) return { summary: [], wallets: {} };
    if (_cachedHistoryData && !force) return _cachedHistoryData;
    if (_historyLoadPromise && !force) return _historyLoadPromise;

    _historyLoadPromise = (async () => {
        const portfoliosResp = await PortfolioClient.listPortfolios();
        const portfolios = Array.isArray(portfoliosResp?.portfolios) ? portfoliosResp.portfolios : [];
        const realPortfolios = portfolios.filter(p => String(p?.portfolioId || '').toLowerCase() !== 'summary');

        const snapshotCalls = await Promise.all([
            PortfolioClient.listSnapshots('summary').catch(() => ({ snapshots: [] })),
            ...realPortfolios.map(p => PortfolioClient.listSnapshots(p.portfolioId).catch(() => ({ snapshots: [] }))),
        ]);

        const [summaryResp, ...walletResps] = snapshotCalls;
        let summaryRows = _sortSnapshotsAscending(summaryResp?.snapshots || []);
        if (typeof window !== 'undefined' && window.PORTFOLIO_TOTAL_VALUE && _isCompatibleLivePoint(summaryRows, window.PORTFOLIO_TOTAL_VALUE)) {
            const now = new Date();
            const todayStr = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
            const hasToday = summaryRows.some(d => d.date === todayStr);
            let latestInvestment = 0;
            if (summaryRows.length > 0) {
                latestInvestment = summaryRows[summaryRows.length - 1].investment;
            }
            const twrCarry = _twrCarryForDate(summaryRows, todayStr);
            if (!hasToday) {
                summaryRows.push({
                    date: todayStr,
                    value: Number(window.PORTFOLIO_TOTAL_VALUE),
                    investment: latestInvestment,
                    unitPrice: twrCarry.unitPrice,
                    cumulativeReturnPct: twrCarry.cumulativeReturnPct,
                });
            } else {
                summaryRows = summaryRows.map(d => d.date === todayStr ? {
                    ...d,
                    value: Number(window.PORTFOLIO_TOTAL_VALUE),
                    unitPrice: d.unitPrice ?? twrCarry.unitPrice,
                    cumulativeReturnPct: d.cumulativeReturnPct ?? twrCarry.cumulativeReturnPct,
                } : d);
            }
            // Recalculate ATH and peaks
            let runningMax = 0;
            let lastAthDate = '';
            for (const row of summaryRows) {
                row.isAthPeak = false;
                if (row.value > runningMax) {
                    runningMax = row.value;
                    lastAthDate = row.date;
                    row.isAthPeak = true;
                }
                row.runningAth = runningMax;
                row.lastAthDate = lastAthDate;
            }
        }

        const wallets = {};
        realPortfolios.forEach((portfolio, index) => {
            const name = String(portfolio.name || portfolio.portfolioId || '');
            let walletRows = _sortSnapshotsAscending(walletResps[index]?.snapshots || []);
            const walletSummary = window.WALLET_SUMMARIES && window.WALLET_SUMMARIES[name];
            const liveWalletVal = walletSummary && walletSummary.total != null ? Number(walletSummary.total) : null;
            if (typeof window !== 'undefined' && liveWalletVal != null && _isCompatibleLivePoint(walletRows, liveWalletVal)) {
                const now = new Date();
                const todayStr = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
                const hasToday = walletRows.some(d => d.date === todayStr);
                let latestInvestment = 0;
                if (walletRows.length > 0) {
                    latestInvestment = walletRows[walletRows.length - 1].investment;
                }
                const twrCarry = _twrCarryForDate(walletRows, todayStr);
                if (!hasToday) {
                    walletRows.push({
                        date: todayStr,
                        value: liveWalletVal,
                        investment: latestInvestment,
                        unitPrice: twrCarry.unitPrice,
                        cumulativeReturnPct: twrCarry.cumulativeReturnPct,
                    });
                } else {
                    walletRows = walletRows.map(d => d.date === todayStr ? {
                        ...d,
                        value: liveWalletVal,
                        unitPrice: d.unitPrice ?? twrCarry.unitPrice,
                        cumulativeReturnPct: d.cumulativeReturnPct ?? twrCarry.cumulativeReturnPct,
                    } : d);
                }
                // Recalculate ATH and peaks for wallet
                let runningMax = 0;
                let lastAthDate = '';
                for (const row of walletRows) {
                    row.isAthPeak = false;
                    if (row.value > runningMax) {
                        runningMax = row.value;
                        lastAthDate = row.date;
                        row.isAthPeak = true;
                    }
                    row.runningAth = runningMax;
                    row.lastAthDate = lastAthDate;
                }
            }
            wallets[name] = walletRows;
        });

        _cachedHistoryData = {
            summary: summaryRows,
            wallets,
        };
        return _cachedHistoryData;
    })();

    try {
        return await _historyLoadPromise;
    } finally {
        _historyLoadPromise = null;
    }
}

function _fmtMoneyTick(value) {
    return Number(value || 0).toLocaleString('pl-PL', { maximumFractionDigits: 0 });
}

function _shiftDate(date, years = 0, months = 0, days = 0) {
    const next = new Date(date.getTime());
    if (years) next.setFullYear(next.getFullYear() + years);
    if (months) next.setMonth(next.getMonth() + months);
    if (days) next.setDate(next.getDate() + days);
    return next;
}

function _historyCutoff(range, latestDateStr) {
    if (!latestDateStr || range === 'ALL') return null;
    const latest = new Date(latestDateStr + 'T00:00:00');
    if (Number.isNaN(latest.getTime())) return null;
    if (range === '5Y') return _shiftDate(latest, -5);
    if (range === '3Y') return _shiftDate(latest, -3);
    if (range === '1Y') return _shiftDate(latest, -1);
    if (range === 'YTD') return new Date(latest.getFullYear(), 0, 1);
    if (range === '1M') return new Date(latest.getFullYear(), latest.getMonth(), 1);
    if (range === '1W') return _shiftDate(latest, 0, 0, -6);
    return null;
}

function _filterHistoryRows(rows, range) {
    if (!Array.isArray(rows) || rows.length === 0) return [];
    const cutoff = _historyCutoff(range, rows[rows.length - 1]?.date || '');
    if (!cutoff) return [...rows];
    const filtered = rows.filter(row => {
        const date = new Date(row.date + 'T00:00:00');
        return !Number.isNaN(date.getTime()) && date >= cutoff;
    });
    if (filtered.length >= 2) return filtered;
    return rows.slice(-Math.min(rows.length, 2));
}

function _filterHistoryRowsWithAnchor(rows, range) {
    if (!Array.isArray(rows) || rows.length === 0) return [];
    const filtered = _filterHistoryRows(rows, range);
    const cutoff = _historyCutoff(range, rows[rows.length - 1]?.date || '');
    if (!cutoff || filtered.length === 0) return filtered;

    const anchor = [...rows].reverse().find(row => {
        const date = new Date(row.date + 'T00:00:00');
        return !Number.isNaN(date.getTime()) && date < cutoff;
    });
    if (!anchor) return filtered;
    if (anchor.date === filtered[0]?.date) return filtered;
    return [anchor, ...filtered];
}

function _setHistoryButtonState(selector, attrName, value) {
    document.querySelectorAll(selector).forEach(button => {
        const active = button.getAttribute(attrName) === value;
        button.classList.toggle('active', active);
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-selected', String(active));
        if (button.getAttribute('role') === 'tab') {
            button.tabIndex = active ? 0 : -1;
        }
    });
}

const _historyXAxisCallback = function(val) {
    const label = this.getLabelForValue(val);
    if (!label) return '';
    const date = new Date(label);
    if (isNaN(date.getTime())) return label;
    return date.toLocaleString('en-US', { month: 'short', year: 'numeric' });
};

function _updateAthPeaksForChartData(data, activeRows) {
    if (!data || !data.length) return;

    let priorMax = 0;
    if (activeRows && activeRows.length > 0 && data[0].date) {
        const startDate = data[0].date;
        for (let i = 0; i < activeRows.length; i++) {
            if (activeRows[i].date < startDate) {
                if (activeRows[i].runningAth > priorMax) {
                    priorMax = activeRows[i].runningAth;
                }
            } else {
                break;
            }
        }
    }

    let runningMax = priorMax;
    for (let i = 0; i < data.length; i++) {
        const row = data[i];
        if (row.value > runningMax) {
            runningMax = row.value;
            row.isAthPeak = true;
        } else {
            row.isAthPeak = false;
        }
        row.runningAth = runningMax;
    }
}

function _makeLineChart(canvasId, data, compact, athInfo = null, activeRows = null) {
    if (!data || !data.length) {
        _setChartMessage(canvasId, 'No snapshot history yet.');
        return;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    _clearChartMessage(canvasId);
    _destroyHistoryChart(canvasId);

    if (activeRows) {
        _updateAthPeaksForChartData(data, activeRows);
    } else {
        _updateAthPeaksForChartData(data, data);
    }

    // Compute absolute last ATH
    let absoluteLastAthValue = athInfo && athInfo.athValue != null ? Number(athInfo.athValue) : null;
    let absoluteLastAthDate = athInfo && athInfo.athDate ? String(athInfo.athDate).slice(0, 10) : null;

    const computedMax = data.length > 0 ? data[data.length - 1].runningAth : 0;
    if (absoluteLastAthValue == null || computedMax > absoluteLastAthValue) {
        absoluteLastAthValue = computedMax;
        absoluteLastAthDate = data.length > 0 ? data[data.length - 1].lastAthDate : null;
    }

    let starDate = null;
    if (absoluteLastAthDate && data.some(d => d.date === absoluteLastAthDate)) {
        starDate = absoluteLastAthDate;
    } else {
        let maxPeakVal = -1;
        for (const row of data) {
            if (row.isAthPeak && row.value > maxPeakVal) {
                maxPeakVal = row.value;
                starDate = row.date;
            }
        }
    }

    const datasets = [
        {
            label: 'Value',
            data: data.map(d => d.value),
            borderColor: _cssVar('--accent-primary', '#2b88cf'),
            backgroundColor: 'rgba(43, 136, 207, 0.14)',
            borderWidth: compact ? 1.5 : 2.5,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.15,
            fill: true,
        },
        {
            label: 'Invested capital',
            data: data.map(d => d.investment),
            borderColor: _cssVar('--text-muted', '#6a8ba8'),
            backgroundColor: 'transparent',
            borderWidth: compact ? 1.2 : 1.5,
            borderDash: [6, 5],
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.15,
            fill: false,
        },
    ];

    _historyCharts[canvasId] = new Chart(canvas, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: ctx => 'Date: ' + ctx[0].label,
                        label: ctx => {
                            return ctx.dataset.label + ': ' + Number(ctx.parsed.y || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN';
                        },
                        afterBody: items => {
                            const index = items[0].dataIndex;
                            const row = data[index];
                            if (row && row.runningAth) {
                                return 'ATH at Date: ' + Number(row.runningAth).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN';
                            }
                            return '';
                        }
                    },
                },
            },
            scales: {
                x: { ticks: { maxTicksLimit: compact ? 6 : 10, maxRotation: 45, color: _chartTextColor(), callback: _historyXAxisCallback } },
                y: { ticks: { callback: value => _fmtMoneyTick(value), color: _chartTextColor() }, grid: { color: _chartGridColor() } },
            },
        },
    });
}

function _makeMonthlyReturnsChart(canvasId, data, metric = 'gain') {
    if (!data || data.length < 2) {
        _setChartMessage(canvasId, 'Need at least two snapshots to calculate monthly returns.');
        return;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    _clearChartMessage(canvasId);
    _destroyHistoryChart(canvasId);

    const byMonth = {};
    for (const row of data) {
        byMonth[row.date.slice(0, 7)] = { value: row.value, investment: row.investment };
    }

    const months = Object.keys(byMonth).sort();
    const labels = [];
    const values = [];
    const colors = [];
    for (let i = 1; i < months.length; i++) {
        const prev = byMonth[months[i - 1]];
        const curr = byMonth[months[i]];
        const investmentDelta = Number((curr.investment - prev.investment).toFixed(2));
        const netGain = Number(((curr.value - prev.value) - (curr.investment - prev.investment)).toFixed(2));
        const delta = metric === 'deposit' ? investmentDelta : netGain;
        labels.push(months[i]);
        values.push(delta);
        colors.push(delta >= 0 ? _cssVar('--color-success', '#10b981') : _cssVar('--color-danger', '#ef4444'));
    }

    _renderMonthlyStats(labels, values, metric);

    const metricLabel = metric === 'deposit' ? 'Monthly Net Deposits (PLN)' : 'Monthly Net Gain (PLN)';
    const valueLabel = metric === 'deposit' ? 'Net deposits' : 'Net gain';

    _historyCharts[canvasId] = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: metricLabel,
                data: values,
                backgroundColor: colors,
                borderColor: colors,
                borderWidth: 0,
                borderRadius: 3,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: ctx => {
                            const [year, month] = ctx[0].label.split('-');
                            return new Date(year, month - 1).toLocaleString('en-US', { month: 'long', year: 'numeric' });
                        },
                        label: ctx => {
                            const value = Number(ctx.parsed.y || 0);
                            return valueLabel + ': ' + (value >= 0 ? '+' : '') + value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN';
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: {
                        color: _chartTextColor(),
                        maxRotation: 45,
                        callback: function(_value, index) {
                            const [year, month] = labels[index].split('-');
                            return new Date(year, month - 1).toLocaleString('en-US', { month: 'short', year: 'numeric' });
                        },
                    },
                },
                y: {
                    ticks: { callback: value => (value >= 0 ? '+' : '') + _fmtMoneyTick(value), color: _chartTextColor() },
                    grid: { color: _chartGridColor() },
                },
            },
        },
    });
}

function _renderHistoryHero(rows, anchoredRows) {
    const last = rows && rows.length ? rows[rows.length - 1] : null;
    const first = anchoredRows && anchoredRows.length ? anchoredRows[0] : null;
    const rangeFirst = rows && rows.length ? rows[0] : first;
    const total = last ? Number(last.value || 0) : null;
    const invested = last ? Number(last.investment || 0) : null;
    const deposits = last && first ? Number((Number(last.investment || 0) - Number(first.investment || 0)).toFixed(2)) : null;
    const gain = last && first ? Number(((Number(last.value || 0) - Number(first.value || 0)) - (Number(last.investment || 0) - Number(first.investment || 0))).toFixed(2)) : null;
    let gainPct = null;
    if (last && first) {
        const lastTwr = _resolveTwrPct(last);
        const firstTwr = _resolveTwrPct(first);
        if (lastTwr != null && firstTwr != null) {
            const base = 1 + firstTwr / 100;
            if (base > 0) gainPct = ((1 + lastTwr / 100) / base - 1) * 100;
        } else if (Number(rangeFirst?.value || 0) > 0) {
            gainPct = gain / Number(rangeFirst.value) * 100;
        }
    }
    const walletLabel = _historyWalletKey === 'summary' ? 'Total' : _historyWalletKey;
    const rangeLabels = { ALL: 'all time', '5Y': 'in the last 5 years', '3Y': 'in the last 3 years', '1Y': 'in the last year', YTD: 'year to date', '1M': 'this month', '1W': 'this week' };
    const setText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
    setText('history-hero-wallet', walletLabel);
    setText('history-hero-total', _fmtHistoryMoney(total));
    setText('history-hero-gain', _fmtHistoryMoney(gain, true));
    setText('history-hero-gain-pct', _fmtHistoryPct(gainPct, true));
    setText('history-hero-range', rangeLabels[_historyRange] || 'selected range');
    setText('history-hero-invested', _fmtHistoryMoney(invested));
    setText('history-hero-deposits', _fmtHistoryMoney(deposits, true));
    setText('history-hero-market', _fmtHistoryMoney(gain, true));
    ['history-hero-gain-pill', 'history-hero-gain-pct', 'history-hero-market'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.toggle('up', Number(gain) > 0);
        el.classList.toggle('down', Number(gain) < 0);
    });
}

function _renderMonthlyStats(labels, values, metric) {
    const root = document.getElementById('history-monthly-stats');
    if (!root) return;
    const valid = values.map((value, index) => ({ value: Number(value), label: labels[index] })).filter(item => Number.isFinite(item.value));
    if (!valid.length) { root.innerHTML = ''; return; }
    const best = valid.reduce((a, b) => b.value > a.value ? b : a, valid[0]);
    const worst = valid.reduce((a, b) => b.value < a.value ? b : a, valid[0]);
    const positives = valid.filter(item => item.value > 0).length;
    const monthLabel = label => {
        const [year, month] = String(label).split('-').map(Number);
        return Number.isFinite(year) && Number.isFinite(month) ? new Date(year, month - 1).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' }) : label;
    };
    root.innerHTML = [
        ['Best', _fmtHistoryMoney(best.value, true), monthLabel(best.label), _historyTone(best.value)],
        ['Worst', _fmtHistoryMoney(worst.value, true), monthLabel(worst.label), _historyTone(worst.value)],
        [metric === 'deposit' ? 'Positive flows' : 'Positive months', `${positives}/${valid.length}`, '', positives ? 'up' : ''],
    ].map(([label, value, detail, tone]) => `<span class="hx-stat ${tone || ''}"><small>${label}</small><strong>${value}</strong>${detail ? `<em>${detail}</em>` : ''}</span>`).join('');
}

function _renderDailyStats(changes, mode) {
    const root = document.getElementById('history-daily-stats');
    if (!root) return;
    const values = changes.filter(item => Number.isFinite(Number(mode === 'pct' ? item.pct : item.pnl)));
    if (!values.length) { root.innerHTML = ''; return; }
    const valueFor = item => Number(mode === 'pct' ? item.pct : item.pnl);
    const best = values.reduce((a, b) => valueFor(b) > valueFor(a) ? b : a, values[0]);
    const worst = values.reduce((a, b) => valueFor(b) < valueFor(a) ? b : a, values[0]);
    const upDays = values.filter(item => valueFor(item) > 0).length;
    const avg = values.reduce((sum, item) => sum + valueFor(item), 0) / values.length;
    const fmt = value => mode === 'pct' ? _fmtHistoryPct(value, true) : _fmtHistoryMoney(value, true);
    root.innerHTML = [
        ['Best', fmt(valueFor(best)), best.date, 'up'],
        ['Worst', fmt(valueFor(worst)), worst.date, 'down'],
        ['Up days', `${upDays}/${values.length}`, '', 'up'],
        ['Average', fmt(avg), '', _historyTone(avg)],
    ].map(([label, value, detail, tone]) => `<span class="hx-stat ${tone || ''}"><small>${label}</small><strong>${value}</strong>${detail ? `<em>${detail}</em>` : ''}</span>`).join('');
}

async function _loadHistoryBenchmark(id) {
    if (_historyBenchmarkCache.has(id)) return _historyBenchmarkCache.get(id);
    if (!window.PortfolioClient) return { daily: [], name: id };
    try {
        let payload = PortfolioClient.getBenchmarkDaily ? await PortfolioClient.getBenchmarkDaily(id, false) : null;
        let daily = Array.isArray(payload?.daily) ? payload.daily : [];
        if (!daily.length && PortfolioClient.getBenchmarkReturns) {
            const monthly = await PortfolioClient.getBenchmarkReturns(id);
            const rows = Array.isArray(monthly?.returns) ? [...monthly.returns].reverse() : [];
            let close = null;
            daily = rows.map(row => {
                if (Number.isFinite(Number(row.closePrice))) close = Number(row.closePrice);
                return { t: `${row.month}-01`, c: close };
            }).filter(row => row.c != null);
        }
        const entry = { daily, name: payload?.name || _historyBenchmarks.find(item => item.id === id)?.label || id };
        _historyBenchmarkCache.set(id, entry);
        return entry;
    } catch (error) {
        console.warn('[history] Failed to load benchmark series', id, error);
        const entry = { daily: [], name: id };
        _historyBenchmarkCache.set(id, entry);
        return entry;
    }
}

function _alignBenchmarkSeries(points, labels) {
    const sorted = (points || [])
        .map(point => ({ date: String(point.t || point.date || '').slice(0, 10), price: Number(point.c ?? point.close ?? point.value) }))
        .filter(point => /^\d{4}-\d{2}-\d{2}$/.test(point.date) && Number.isFinite(point.price) && point.price > 0)
        .sort((a, b) => a.date.localeCompare(b.date));
    if (!sorted.length) return labels.map(() => null);
    let cursor = 0;
    let lastPrice = null;
    let firstPrice = null;
    return labels.map(label => {
        while (cursor < sorted.length && sorted[cursor].date <= label) {
            lastPrice = sorted[cursor].price;
            cursor += 1;
        }
        if (firstPrice == null && lastPrice != null) firstPrice = lastPrice;
        if (firstPrice == null || lastPrice == null) return null;
        return Number(((lastPrice / firstPrice - 1) * 100).toFixed(2));
    });
}

function _makeDailyChangeChart(canvasId, data, mode) {
    if (!data || data.length < 2) {
        _setChartMessage(canvasId, 'Need at least two snapshots to calculate daily changes.');
        return;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    _clearChartMessage(canvasId);
    _destroyHistoryChart(canvasId);

    const changes = [];
    if (data.length > 0) {
        changes.push({ date: data[0].date, pnl: null, pct: null });
    }

    const twrSeries = data.map(item => _resolveTwrPct(item));
    const hasTwrPath = mode === 'pct' && twrSeries.some(v => v != null);

    for (let i = 1; i < data.length; i++) {
        const prev = data[i - 1];
        const curr = data[i];
        const netPln = Number(((curr.value - prev.value) - (curr.investment - prev.investment)).toFixed(2));

        let netPct = null;
        if (hasTwrPath) {
            const prevCum = twrSeries[i - 1];
            const currCum = twrSeries[i];
            if (prevCum != null && currCum != null) {
                const prevFactor = 1 + (Number(prevCum) / 100);
                const currFactor = 1 + (Number(currCum) / 100);
                if (prevFactor > 0 && currFactor > 0) {
                    netPct = Number((((currFactor / prevFactor) - 1) * 100).toFixed(3));
                }
            }
        }

        if (netPct == null && prev.value > 0) {
            netPct = Number(((netPln / prev.value) * 100).toFixed(3));
        }

        changes.push({ date: curr.date, pnl: netPln, pct: netPct });
    }

    const visibleChanges = changes.slice(-90);
    _renderDailyStats(visibleChanges, mode);
    const labels = visibleChanges.map(item => item.date);
    const values = visibleChanges.map(item => mode === 'pct' ? item.pct : item.pnl);
    const finiteValues = values.filter(value => Number.isFinite(Number(value))).map(Number);
    const best = finiteValues.length ? Math.max(...finiteValues) : null;
    const worst = finiteValues.length ? Math.min(...finiteValues) : null;
    const avg = finiteValues.length ? finiteValues.reduce((sum, value) => sum + value, 0) / finiteValues.length : null;
    const scatterData = values.map((value, index) => value === null ? null : { x: labels[index], y: Number(value) });
    const scatterColors = values.map(value => Number(value) >= 0 ? 'rgba(16, 185, 129, 0.78)' : 'rgba(239, 68, 68, 0.78)');
    const scatterRadius = values.map(value => value === best || value === worst ? 6 : 3.4);
    const scatterBorder = values.map(value => value === best || value === worst ? 8 : 0);
    const avgData = avg == null ? [] : labels.map(label => ({ x: label, y: Number(avg.toFixed(mode === 'pct' ? 3 : 2)) }));

    _historyCharts[canvasId] = new Chart(canvas, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: mode === 'pct' ? 'Daily % Change' : 'Daily PLN Change',
                    data: scatterData,
                    backgroundColor: scatterColors,
                    borderColor: values.map(value => value === best ? 'rgba(16, 185, 129, 0.18)' : value === worst ? 'rgba(239, 68, 68, 0.18)' : 'transparent'),
                    borderWidth: scatterBorder,
                    pointRadius: scatterRadius,
                    pointHoverRadius: values.map(value => value === best || value === worst ? 8 : 5),
                    showLine: false,
                    spanGaps: false,
                },
                {
                    label: 'Average',
                    type: 'line',
                    data: avgData,
                    borderColor: 'rgba(119, 132, 148, 0.9)',
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    borderDash: [6, 3],
                    pointRadius: 0,
                    fill: false,
                    tension: 0,
                    spanGaps: true,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: ctx => 'Date: ' + (ctx[0]?.raw?.x || ctx[0]?.label || ''),
                        label: ctx => {
                            const value = ctx.parsed.y;
                            if (value == null || Number.isNaN(value)) return null;
                            if (mode === 'pct') return ctx.dataset.label + ': ' + (value >= 0 ? '+' : '') + value.toFixed(2) + '%';
                            return ctx.dataset.label + ': ' + (value >= 0 ? '+' : '') + Number(value).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN';
                        },
                    },
                },
            },
            scales: {
                x: { type: 'category', labels, ticks: { maxTicksLimit: 8, maxRotation: 45, color: _chartTextColor(), callback: _historyXAxisCallback }, grid: { color: _chartGridColor() } },
                y: mode === 'pct'
                    ? {
                        suggestedMin: finiteValues.length ? Math.min(...finiteValues) - Math.max(0.2, (Math.max(...finiteValues) - Math.min(...finiteValues)) * 0.12) : undefined,
                        suggestedMax: finiteValues.length ? Math.max(...finiteValues) + Math.max(0.2, (Math.max(...finiteValues) - Math.min(...finiteValues)) * 0.12) : undefined,
                        title: { display: false },
                        ticks: { callback: value => (value >= 0 ? '+' : '') + Number(value).toFixed(1) + '%', color: _chartTextColor() },
                        grid: { color: ctx => ctx.tick.value === 0 ? _chartGridColor(true) : _chartGridColor() },
                    }
                    : {
                        suggestedMin: finiteValues.length ? Math.min(...finiteValues) - Math.max(100, (Math.max(...finiteValues) - Math.min(...finiteValues)) * 0.12) : undefined,
                        suggestedMax: finiteValues.length ? Math.max(...finiteValues) + Math.max(100, (Math.max(...finiteValues) - Math.min(...finiteValues)) * 0.12) : undefined,
                        title: { display: false },
                        ticks: { callback: value => (value >= 0 ? '+' : '') + _fmtMoneyTick(value), color: _chartTextColor() },
                        grid: { color: ctx => ctx.tick.value === 0 ? _chartGridColor(true) : _chartGridColor() },
                    },
            },
        },
    });
}

async function _makeCumulativeReturnChart(canvasId, data, mode) {
    if (!data || !data.length) {
        _setChartMessage(canvasId, 'No snapshot history yet.');
        return;
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    _clearChartMessage(canvasId);
    _destroyHistoryChart(canvasId);

    const labels = data.map(item => item.date);
    let returns = [];

    if (mode === 'pln') {
        returns = data.map(item => Number((item.value - item.investment).toFixed(2)));
    } else {
        const hasAnyTwr = data.some(item => _resolveTwrPct(item) != null);

        if (hasAnyTwr) {
            let lastTwr = null;
            returns = data.map(item => {
                const twr = _resolveTwrPct(item);
                if (twr != null) {
                    lastTwr = twr;
                    return Number(twr.toFixed(2));
                }
                if (lastTwr != null) return Number(lastTwr.toFixed(2));
                return null;
            });
        } else {
            returns = data.map(item => {
                const profit = item.value - item.investment;
                if (!item.investment) return 0;
                return Number(((profit / item.investment) * 100).toFixed(2));
            });
        }
    }

    const datasets = [{
        label: mode === 'pln' ? 'Portfolio return (PLN)' : 'Portfolio return (%)',
        data: returns,
        borderColor: '#7db7d9',
        backgroundColor: 'rgba(125,183,217,0.08)',
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.15,
        fill: true,
    }];

    if (mode === 'pct') {
        const selected = _historyBenchmarks.filter(item => _historySelectedBenchmarks.has(item.id));
        for (const bm of selected) {
            const entry = await _loadHistoryBenchmark(bm.id);
            const series = _alignBenchmarkSeries(entry.daily, labels);
            const chip = document.querySelector(`[data-history-benchmark="${bm.id}"]`);
            const empty = !series.some(value => value != null);
            if (chip) {
                chip.toggleAttribute('data-empty', empty);
                chip.title = empty ? `No ${bm.label} data for this range` : '';
            }
            if (empty) continue;
            datasets.push({
                label: entry.name || bm.label,
                data: series,
                borderColor: bm.color,
                backgroundColor: 'transparent',
                borderWidth: 1.8,
                borderDash: [6, 4],
                pointRadius: 0,
                pointHoverRadius: 3,
                tension: 0.12,
                fill: false,
            });
        }
    }

    _historyCharts[canvasId] = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: ctx => ctx[0].label,
                        label: ctx => mode === 'pln'
                            ? ctx.dataset.label + ': ' + (ctx.parsed.y >= 0 ? '+' : '') + Number(ctx.parsed.y || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN'
                            : ctx.dataset.label + ': ' + (ctx.parsed.y >= 0 ? '+' : '') + Number(ctx.parsed.y || 0).toFixed(2) + '%',
                    },
                },
            },
            scales: {
                x: { ticks: { maxTicksLimit: 10, maxRotation: 45, color: _chartTextColor(), callback: _historyXAxisCallback }, grid: { color: _chartGridColor() } },
                y: mode === 'pln'
                    ? {
                        title: { display: false },
                        ticks: { callback: value => (value >= 0 ? '+' : '') + _fmtMoneyTick(value), color: _chartTextColor() },
                        grid: { color: ctx => ctx.tick.value === 0 ? _chartGridColor(true) : _chartGridColor() },
                    }
                    : {
                        title: { display: false },
                        ticks: { callback: value => (value >= 0 ? '+' : '') + Number(value).toFixed(0) + '%', color: _chartTextColor() },
                        grid: { color: ctx => ctx.tick.value === 0 ? _chartGridColor(true) : _chartGridColor() },
                    },
            },
        },
    });
}

async function renderHistoryTab(force = false) {
    const chartIds = ['investmentChart', 'monthlyReturnsChart', 'returnsChart', 'dailyChangeChart'];
    const startedAt = performance.now();
    chartIds.forEach(_showHistoryChartLoader);

    try {
        const history = await _loadHistorySnapshots(force);
        const walletNames = Object.keys(history.wallets || {}).sort((a, b) => a.localeCompare(b));

        // Ensure selected wallet key is still valid
        if (_historyWalletKey !== 'summary' && !walletNames.includes(_historyWalletKey)) {
            _historyWalletKey = 'summary';
        }

        _renderWalletBtns(walletNames);
        _setHistoryButtonState('[data-history-range]', 'data-history-range', _historyRange);
        _setHistoryButtonState('[data-history-return-mode]', 'data-history-return-mode', _historyReturnMode);
        _setHistoryButtonState('[data-history-monthly-metric]', 'data-history-monthly-metric', _historyMonthlyMetric);
        _setHistoryButtonState('[data-history-daily-mode]', 'data-history-daily-mode', _historyDailyMode);
        document.getElementById('history-return-pln-note')?.toggleAttribute('hidden', _historyReturnMode !== 'pln');
        const series = document.getElementById('history-benchmark-series');
        if (series) series.hidden = _historyReturnMode === 'pln';

        // Pick data source based on selected wallet
        const isTotal = _historyWalletKey === 'summary';
        const activeRows = isTotal ? history.summary : (history.wallets[_historyWalletKey] || []);
        const filteredMain = _filterHistoryRows(activeRows, _historyRange);
        const anchoredMain = _filterHistoryRowsWithAnchor(activeRows, _historyRange);
        const activeAth = isTotal ? (window.PORTFOLIO_ATH || null) : ((window.WALLET_ATHS || {})[_historyWalletKey] || null);

        // Resample line charts to improve rendering on long histories
        const strategy = _getResamplingStrategy(_historyRange, filteredMain.map(r => r.date));
        const resampledMain = _resampleHistoryRows(filteredMain, strategy);

        _renderHistoryHero(filteredMain, anchoredMain);
        _makeLineChart('investmentChart', resampledMain, false, activeAth, activeRows);
        _makeMonthlyReturnsChart('monthlyReturnsChart', anchoredMain, _historyMonthlyMetric);
        await _makeCumulativeReturnChart('returnsChart', resampledMain, _historyReturnMode);
        _makeDailyChangeChart('dailyChangeChart', anchoredMain, _historyDailyMode);
    } catch (error) {
        console.warn('Failed to render history tab from live snapshots:', error);
        chartIds.forEach(id => _setChartMessage(id, error.message || 'Could not load snapshot history.'));
    } finally {
        const elapsed = performance.now() - startedAt;
        const minVisibleMs = 260;
        const remaining = Math.max(0, minVisibleMs - elapsed);
        setTimeout(() => {
            chartIds.forEach(_hideHistoryChartLoader);
        }, remaining);
    }
}

window.renderHistoryTab = renderHistoryTab;
window._loadHistorySnapshots = _loadHistorySnapshots;
window._getHistorySnapshotCache = () => _cachedHistoryData;
window.setHistoryWallet = function setHistoryWallet(key) {
    _historyWalletKey = key || 'summary';
    // Update button active state immediately for snappy feel
    document.querySelectorAll('.history-wallet-btn').forEach(btn => {
        const active = btn.dataset.walletKey === _historyWalletKey;
        btn.classList.toggle('is-active', active);
        btn.setAttribute('aria-selected', String(active));
        btn.tabIndex = active ? 0 : -1;
    });
    renderHistoryTab().catch(error => console.warn('Failed to switch history wallet:', error));
};
window.setHistoryRange = function setHistoryRange(range) {
    _historyRange = range;
    renderHistoryTab().catch(error => console.warn('Failed to update history range:', error));
};
window.setHistoryReturnMode = function setHistoryReturnMode(mode) {
    _historyReturnMode = mode;
    renderHistoryTab().catch(error => console.warn('Failed to update history return mode:', error));
};
window.setHistoryMonthlyMetric = function setHistoryMonthlyMetric(mode) {
    _historyMonthlyMetric = mode === 'deposit' ? 'deposit' : 'gain';
    renderHistoryTab().catch(error => console.warn('Failed to update monthly history metric:', error));
};
window.setHistoryDailyMode = function setHistoryDailyMode(mode) {
    _historyDailyMode = mode === 'pln' ? 'pln' : 'pct';
    renderHistoryTab().catch(error => console.warn('Failed to update daily history metric:', error));
};

document.addEventListener('click', function(event) {
    const button = event.target && event.target.closest ? event.target.closest('[data-history-benchmark]') : null;
    if (!button) return;
    const id = button.getAttribute('data-history-benchmark');
    if (!id) return;
    if (_historySelectedBenchmarks.has(id)) _historySelectedBenchmarks.delete(id);
    else _historySelectedBenchmarks.add(id);
    button.setAttribute('aria-pressed', String(_historySelectedBenchmarks.has(id)));
    renderHistoryTab().catch(error => console.warn('Failed to update benchmark series:', error));
});

document.addEventListener('DOMContentLoaded', function () {
    renderHistoryTab().catch(error => console.warn('Failed to initialize history tab:', error));
});

document.addEventListener('liveDataReady', function () {
    renderHistoryTab(true).catch(error => console.warn('Failed to refresh history tab:', error));
});

// When a historical transaction triggers a backend snapshot recalculation,
// reload the history charts once the new data is ready.
window.addEventListener('portfolioHistoryRecalculated', function () {
    renderHistoryTab(true).catch(error => console.warn('Failed to refresh history tab after recalculation:', error));
});
