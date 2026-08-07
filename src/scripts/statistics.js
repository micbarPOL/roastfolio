function fmtPLN(v) {
    return Number(v || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN';
}
function fmtPct(v) {
    const num = Number(v || 0);
    if (num === 0) return '0%';
    return (num > 0 ? '+' : '') + num.toFixed(2) + '%';
}
function fmtDate(d) {
    return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}
function daysBetween(dateStr) {
    const then = new Date(dateStr);
    const now = new Date();
    return Math.floor((now - then) / (1000 * 60 * 60 * 24));
}
function fmtMonth(m) {
    const [y, mo] = m.split('-');
    return new Date(y, mo - 1).toLocaleString('en-US', { month: 'long', year: 'numeric' });
}
function statCard(label, value, sub) {
    return `<div class="stat-card">
        <div class="stat-label">${label}</div>
        <div class="stat-value">${value}</div>
        ${sub ? `<div class="stat-sub">${sub}</div>` : ''}
    </div>`;
}

let _statisticsHistoryCache = {};
let _statisticsHistoryPromise = {};

function _sortSnapshotRows(rows) {
    return [...(rows || [])]
        .map(row => ({
            date: String(row.snapshotDate || '').slice(0, 10),
            value: Number(row.portfolioValue || 0),
            investment: Number(row.investmentValue || 0),
            xirr: row.xirr != null ? Number(row.xirr) : null,
        }))
        .filter(row => row.date)
        .sort((a, b) => a.date.localeCompare(b.date));
}

async function _loadStatisticsHistory(portfolioId = 'summary', force = false) {
    if (!window.PortfolioClient) return [];
    if (_statisticsHistoryCache[portfolioId] && !force) return _statisticsHistoryCache[portfolioId];
    if (_statisticsHistoryPromise[portfolioId] && !force) return _statisticsHistoryPromise[portfolioId];
    _statisticsHistoryPromise[portfolioId] = PortfolioClient.listSnapshots(portfolioId)
        .then(data => {
            const rows = _sortSnapshotRows(data?.snapshots || []);
            _statisticsHistoryCache[portfolioId] = rows;
            _statisticsHistoryPromise[portfolioId] = null;
            return rows;
        });
    return _statisticsHistoryPromise[portfolioId];
}

// ── Benchmark columns registry ────────────────────────────────────────────
const BENCHMARK_COLS = [
    { id: 'WIG',        short: 'WIG' },
    { id: 'WIG20',      short: 'WIG20' },
    { id: 'MWIG40',     short: 'mWIG40' },
    { id: 'SWIG80',     short: 'sWIG80' },
    { id: 'SP500',      short: 'S&P 500' },
    { id: 'NASDAQ',     short: 'NASDAQ' },
    { id: 'DAX',        short: 'DAX' },
    { id: 'MSCI_WORLD', short: 'MSCI W' },
];

// ── Benchmark data cache ──────────────────────────────────────────────────
let _benchmarkAllCache = null;
let _benchmarkAllPromise = null;

async function _loadAllBenchmarkReturns(force = false) {
    if (_benchmarkAllCache && !force) return _benchmarkAllCache;
    if (_benchmarkAllPromise && !force) return _benchmarkAllPromise;

    _benchmarkAllPromise = (async () => {
        const results = [];
        for (const b of BENCHMARK_COLS) {
            try {
                if (window.PortfolioClient && window.PortfolioClient.getBenchmarkReturns) {
                    const data = await window.PortfolioClient.getBenchmarkReturns(b.id, '2010-01');
                    results.push({ id: b.id, returns: data?.returns || [] });
                } else {
                    results.push({ id: b.id, returns: [] });
                }
            } catch (err) {
                console.warn(`Failed to load benchmark ${b.id}`, err);
                results.push({ id: b.id, returns: [] });
            }
        }
        
        const cache = {};
        for (const { id, returns } of results) {
            cache[id] = {};
            for (const r of returns) {
                if (r.month) cache[id][r.month] = Number(r.returnPct);
            }
        }
        _benchmarkAllCache = cache;
        _benchmarkAllPromise = null;
        return cache;
    })();

    return _benchmarkAllPromise;
}

// ── Modified Dietz monthly return ─────────────────────────────────────────
// gain = ΔValue − net_cash_flows
// return = gain / (V0 + net_cash_flows × 0.5)
// Assumes cash flows occur at mid-month (CFA Institute standard).
function _monthReturn(prev, curr) {
    const netFlow = curr.investment - prev.investment;
    const gain = (curr.value - prev.value) - netFlow;
    const denom = prev.value + netFlow * 0.5;
    if (denom <= 0) return null;
    return gain / denom * 100;
}

function _nextMonthString(month) {
    const [year, rawMonth] = month.split('-').map(Number);
    const next = new Date(year, rawMonth, 1);
    return next.getFullYear() + '-' + String(next.getMonth() + 1).padStart(2, '0');
}

function _firstSnapshotOnOrAfter(snapshots, date) {
    return snapshots.find(row => row.date >= date) || null;
}

function _buildPortfolioMonthlyPeriods(snapshots) {
    const sorted = [...(snapshots || [])].sort((a, b) => a.date.localeCompare(b.date));
    const months = [...new Set(sorted.map(row => row.date.slice(0, 7)))].sort();
    
    return months.map(month => {
        const snapsInMonth = sorted.filter(r => r.date.startsWith(month));
        if (snapsInMonth.length === 0) return null;

        const end = snapsInMonth[snapsInMonth.length - 1];

        let start = null;
        const prevMonthSnaps = sorted.filter(r => r.date < `${month}-01`);
        if (prevMonthSnaps.length > 0) {
            start = prevMonthSnaps[prevMonthSnaps.length - 1];
        } else {
            start = snapsInMonth[0];
        }

        if (!start || !end || start.date === end.date) return null;
        const netGain = (end.value - start.value) - (end.investment - start.investment);
        return {
            month,
            start,
            end,
            endValue: end.value,
            invested: end.investment,
            netGain,
            pct: _monthReturn(start, end),
            xirr: end.xirr,
        };
    }).filter(Boolean);
}

function _buildPortfolioDailyPeriods(snapshots) {
    const sorted = [...(snapshots || [])].sort((a, b) => a.date.localeCompare(b.date));
    const result = [];
    for (let i = 1; i < sorted.length; i++) {
        const start = sorted[i - 1];
        const end = sorted[i];
        const netGain = (end.value - start.value) - (end.investment - start.investment);
        result.push({
            month: end.date, // Represents the date, but using 'month' key for compatibility with existing render loop
            start,
            end,
            endValue: end.value,
            invested: end.investment,
            netGain,
            pct: _monthReturn(start, end),
            xirr: end.xirr,
        });
    }
    return result;
}

// ── Accordion toggle ──────────────────────────────────────────────────────
function toggleStatsAccordion(id) {
    const body = document.getElementById('acc-' + id);
    const btn  = body && body.previousElementSibling;
    if (!body) return;
    const isOpen = body.classList.toggle('stats-acc-body--open');
    if (btn) {
        btn.setAttribute('aria-expanded', isOpen);
        const arrow = btn.querySelector('.stats-acc-arrow');
        if (arrow) arrow.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
    }
}

function _openAccordion(id) {
    const body = document.getElementById('acc-' + id);
    const btn  = body && body.previousElementSibling;
    if (!body) return;
    body.classList.add('stats-acc-body--open');
    if (btn) {
        btn.setAttribute('aria-expanded', 'true');
        const arrow = btn.querySelector('.stats-acc-arrow');
        if (arrow) arrow.style.transform = 'rotate(0deg)';
    }
}

function toggleMobileBmRow(rowEl) {
    if (!rowEl) return;
    const isExpanded = rowEl.classList.toggle('bm-mobile-row--expanded');
    const arrow = rowEl.querySelector('.bm-mobile-arrow-icon');
    if (arrow) {
        arrow.style.transform = isExpanded ? 'rotate(180deg)' : 'rotate(0deg)';
    }
}
window.toggleMobileBmRow = toggleMobileBmRow;

// ── Section 1: Monthly Snapshot Summary ──────────────────────────────────
function renderMonthlySnapshotTable(data, granularity = 'monthly') {
    const wrap = document.getElementById('returns-table-wrap');
    if (!wrap) return;

    if (!data.length) {
        wrap.innerHTML = '<div class="stats-empty">No snapshot history yet.</div>';
        return;
    }

    const isDaily = granularity === 'daily';
    const rows = (isDaily ? _buildPortfolioDailyPeriods(data) : _buildPortfolioMonthlyPeriods(data)).reverse();

    if (rows.length < 1) {
        wrap.innerHTML = `<div class="stats-empty">Need at least two ${isDaily ? 'days' : 'months'} of snapshots to build the summary.</div>`;
        return;
    }

    const rowsHTML = rows.map(r => {
        const gainColor  = r.netGain >= 0 ? '#34d399' : '#f87171';
        const pctColor   = r.pct == null ? '#94a3b8' : r.pct >= 0 ? '#34d399' : '#f87171';
        const pctDisplay = r.pct == null ? '—' : (r.pct >= 0 ? '+' : '') + r.pct.toFixed(2) + '%';
        const gainDisplay = (r.netGain >= 0 ? '+' : '') + fmtPLN(r.netGain);
        
        let xirrDisplay = '—';
        let xirrColor = '#94a3b8';
        if (r.xirr != null) {
            const xirrPct = r.xirr * 100;
            xirrColor = xirrPct >= 0 ? '#34d399' : '#f87171';
            xirrDisplay = (xirrPct >= 0 ? '+' : '') + xirrPct.toFixed(2) + '%';
        }
        
        const dateLabel = isDaily ? fmtDate(r.month) : fmtMonth(r.month);

        return `<tr>
            <td style="padding:6px 10px;font-weight:500;white-space:nowrap;">${dateLabel}</td>
            <td style="padding:6px 10px;text-align:right;">${fmtPLN(r.endValue)}</td>
            <td style="padding:6px 10px;text-align:right;">${fmtPLN(r.invested)}</td>
            <td style="padding:6px 10px;text-align:right;color:${gainColor};font-weight:700;">${gainDisplay}</td>
            <td style="padding:6px 10px;text-align:right;color:${pctColor};font-weight:700;">${pctDisplay}</td>
            <td style="padding:6px 10px;text-align:right;color:${xirrColor};font-weight:700;">${xirrDisplay}</td>
        </tr>`;
    }).join('');

    const dateHeader = isDaily ? 'Date' : 'Month';

    wrap.innerHTML = `
        <div style="overflow-x:auto;margin-top:4px;">
            <table class="holdings-table" style="width:100%;font-size:13px;">
                <thead>
                    <tr>
                        <th style="text-align:left;">${dateHeader}</th>
                        <th style="text-align:right;">End Value</th>
                        <th style="text-align:right;">Total Invested</th>
                        <th style="text-align:right;">Net Gain</th>
                        <th style="text-align:right;">Return %</th>
                        <th style="text-align:right;">XIRR</th>
                    </tr>
                </thead>
                <tbody>${rowsHTML}</tbody>
            </table>
        </div>`;
}

// ── Section 2: Benchmark Comparison ──────────────────────────────────────
function renderBenchmarkComparisonTable(snapshotData, benchmarkData) {
    const wrap = document.getElementById('bm-cmp-wrap');
    if (!wrap) return;

    if (!snapshotData.length) {
        wrap.innerHTML = '<div class="stats-empty">No snapshot history available.</div>';
        return;
    }

    const monthlyPeriods = _buildPortfolioMonthlyPeriods(snapshotData);

    if (monthlyPeriods.length < 1) {
        wrap.innerHTML = '<div class="stats-empty">Need at least two months of snapshot data.</div>';
        return;
    }

    // Build portfolio monthly returns map
    const portReturns = {};
    for (const period of monthlyPeriods) {
        portReturns[period.month] = period.pct;
    }

    // Determine which months to show (portfolio month ∩ any benchmark month)
    const allBmMonths = new Set();
    for (const b of BENCHMARK_COLS) {
        Object.keys(benchmarkData[b.id] || {}).forEach(m => allBmMonths.add(m));
    }
    const periodMonths = monthlyPeriods.map(period => period.month);
    const displayMonths = periodMonths
        .filter(m => portReturns[m] != null || allBmMonths.has(m))
        .reverse(); // newest first

    const previewEl = document.getElementById('bm-cmp-header-preview');
    if (previewEl) {
        if (displayMonths.length > 0) {
            const m = displayMonths[0];
            const portPct = portReturns[m];
            const portDisplay = portPct == null ? '—' : (portPct >= 0 ? '+' : '') + portPct.toFixed(2) + '%';
            
            let wins = 0, total = 0;
            BENCHMARK_COLS.forEach(b => {
                const bmRet = benchmarkData[b.id]?.[m];
                if (bmRet != null && bmRet !== undefined) {
                    total++;
                    if (portPct != null && portPct > bmRet) {
                        wins++;
                    }
                }
            });
            const scoreStr = total > 0 ? `Beat ${wins}/${total}` : '';
            const monthStr = fmtMonth(m);
            const scoreStyleClass = total > 0 ? (wins / total >= 0.6 ? 'bm-score-good' : wins / total >= 0.4 ? 'bm-score-mid' : 'bm-score-bad') : '';
            
            previewEl.innerHTML = `<span class="stats-acc-preview-badge ${scoreStyleClass}">${scoreStr}</span> <span class="stats-acc-preview-month">(${monthStr})</span> <span class="stats-acc-preview-pct" style="${portPct != null ? (portPct >= 0 ? 'color:#34d399;' : 'color:#f87171;') : ''}font-weight:700;">${portDisplay}</span>`;
        } else {
            previewEl.innerHTML = '';
        }
    }

    if (!displayMonths.length) {
        wrap.innerHTML = '<div class="stats-empty">No overlapping months between portfolio history and benchmark data. Deploy and seed benchmark data to enable this view.</div>';
        return;
    }

    const headerCells = BENCHMARK_COLS.map(b =>
        `<th class="bm-th">${b.short}</th>`
    ).join('');

    const rowsHTML = displayMonths.map(m => {
        const portPct = portReturns[m];
        const portDisplay = portPct == null ? '—'
            : (portPct >= 0 ? '+' : '') + portPct.toFixed(2) + '%';
        const portStyle = portPct == null ? '' : portPct >= 0
            ? 'color:#34d399;font-weight:700;'
            : 'color:#f87171;font-weight:700;';

        let wins = 0, total = 0;
        const bmCells = BENCHMARK_COLS.map(b => {
            const bmRet = benchmarkData[b.id]?.[m];
            if (bmRet == null || bmRet === undefined) {
                return '<td class="bm-td bm-na">—</td>';
            }
            total++;
            const hasPct = portPct != null;
            const beat   = hasPct && portPct > bmRet;
            const loss   = hasPct && portPct <= bmRet;
            if (beat) wins++;
            const cls  = !hasPct ? '' : beat ? 'bm-win' : 'bm-loss';
            const icon = !hasPct ? '' : beat ? '✓' : '✗';
            const diff = hasPct ? portPct - bmRet : null;
            const diffHtml = diff != null
                ? `<span class="bm-diff">${diff >= 0 ? '+' : ''}${diff.toFixed(1)}</span>`
                : '';
            const bmPctStr = (bmRet >= 0 ? '+' : '') + bmRet.toFixed(2) + '%';
            return `<td class="bm-td ${cls}"><span class="bm-icon">${icon}</span>${bmPctStr}${diffHtml}</td>`;
        }).join('');

        const scoreStr = total > 0 ? `${wins}/${total}` : '—';
        const scoreCls = total > 0 ? (wins / total >= 0.6 ? 'bm-score-good' : wins / total >= 0.4 ? 'bm-score-mid' : 'bm-score-bad') : '';

        return `<tr>
            <td class="bm-td bm-month">${fmtMonth(m)}</td>
            <td class="bm-td bm-port" style="${portStyle}">${portDisplay}</td>
            ${bmCells}
            <td class="bm-td bm-score ${scoreCls}">${scoreStr}</td>
        </tr>`;
    }).join('');

    const mobileRowsHTML = displayMonths.map(m => {
        const portPct = portReturns[m];
        const portDisplay = portPct == null ? '—' : (portPct >= 0 ? '+' : '') + portPct.toFixed(2) + '%';
        const portColor = portPct == null ? '#94a3b8' : portPct >= 0 ? '#34d399' : '#f87171';

        let wins = 0, total = 0;
        const detailsHTML = BENCHMARK_COLS.map(b => {
            const bmRet = benchmarkData[b.id]?.[m];
            if (bmRet == null || bmRet === undefined) {
                return `<div class="bm-mobile-detail-item">
                    <span class="bm-mobile-detail-name">${b.short}</span>
                    <span class="bm-mobile-detail-val bm-na">—</span>
                </div>`;
            }
            total++;
            const beat = portPct != null && portPct > bmRet;
            if (beat) wins++;
            const statusClass = portPct == null ? '' : beat ? 'bm-mobile-win' : 'bm-mobile-loss';
            const icon = portPct == null ? '' : beat ? '✓' : '✗';
            const bmPctStr = (bmRet >= 0 ? '+' : '') + bmRet.toFixed(2) + '%';
            const diff = portPct != null ? portPct - bmRet : null;
            const diffStr = diff != null ? ` (${diff >= 0 ? '+' : ''}${diff.toFixed(1)}%)` : '';
            return `<div class="bm-mobile-detail-item ${statusClass}">
                <span class="bm-mobile-detail-name">${b.short}</span>
                <span class="bm-mobile-detail-val">${icon} ${bmPctStr} <span class="bm-mobile-detail-diff">${diffStr}</span></span>
            </div>`;
        }).join('');

        const scoreStr = total > 0 ? `Beat ${wins}/${total}` : '—';
        const scoreCls = total > 0 ? (wins / total >= 0.6 ? 'bm-score-good' : wins / total >= 0.4 ? 'bm-score-mid' : 'bm-score-bad') : '';

        return `
            <div class="bm-mobile-row" onclick="toggleMobileBmRow(this)">
                <div class="bm-mobile-summary">
                    <div class="bm-mobile-summary-left">
                        <span class="bm-mobile-month">${fmtMonth(m)}</span>
                        <span class="bm-mobile-score ${scoreCls}">${scoreStr}</span>
                    </div>
                    <div class="bm-mobile-summary-right">
                        <span class="bm-mobile-port" style="color:${portColor}">${portDisplay}</span>
                        <svg class="bm-mobile-arrow-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                </div>
                <div class="bm-mobile-details">
                    <div class="bm-mobile-details-grid">${detailsHTML}</div>
                </div>
            </div>
        `;
    }).join('');

    wrap.innerHTML = `
        <div class="bm-scroll bm-desktop-only">
            <table class="bm-table">
                <thead>
                    <tr>
                        <th class="bm-th bm-th-month">Month</th>
                        <th class="bm-th bm-th-port">Portfolio</th>
                        ${headerCells}
                        <th class="bm-th bm-th-score">Score</th>
                    </tr>
                </thead>
                <tbody>${rowsHTML}</tbody>
            </table>
        </div>
        <div class="bm-mobile-only">
            <div class="bm-mobile-list">${mobileRowsHTML}</div>
        </div>`;
}

function _injectLiveSummaryValue(data) {
    if (typeof window === 'undefined' || !window.PORTFOLIO_TOTAL_VALUE) return data;
    const now = new Date();
    const todayStr = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
    const hasToday = data.some(d => d.date === todayStr);
    let latestInvestment = 0;
    let latestXirr = null;
    if (data.length > 0) {
        latestInvestment = data[data.length - 1].investment;
        latestXirr = data[data.length - 1].xirr;
    }
    const liveXirr = (typeof WALLET_SUMMARIES !== 'undefined' && WALLET_SUMMARIES && WALLET_SUMMARIES.Summary)
        ? WALLET_SUMMARIES.Summary.annualReturn
        : null;
    const todayXirr = liveXirr != null ? Number(liveXirr) : latestXirr;
    if (!hasToday) {
        return [...data, {
            date: todayStr,
            value: Number(window.PORTFOLIO_TOTAL_VALUE),
            investment: latestInvestment,
            xirr: todayXirr
        }];
    } else {
        return data.map(d => d.date === todayStr ? {
            ...d,
            value: Number(window.PORTFOLIO_TOTAL_VALUE),
            xirr: todayXirr
        } : d);
    }
}

async function renderStatisticsSummary(force = false) {
    let data = await _loadStatisticsHistory('summary', force);
    data = _injectLiveSummaryValue(data);
    const snapshotAth = window.PORTFOLIO_ATH || null;
    const txRows = window.LedgerTransactions ? await window.LedgerTransactions.loadRows() : [];
    const tradeRows = txRows.filter(r => r.operation !== 'Deposit' && r.operation !== 'Withdrawal');

    if ((!data || data.length === 0) && !snapshotAth) {
        ['stats-alltime', 'stats-monthly', 'stats-daily'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '<div class="stat-card"><div class="stat-label">Waiting for summary snapshots</div><div class="stat-sub">Daily statistics will appear after snapshot history is available.</div></div>';
        });
        renderMonthlySnapshotTable([]);
        return;
    }

    let athValue = snapshotAth && snapshotAth.athValue != null ? Number(snapshotAth.athValue) : -Infinity;
    let athDate = snapshotAth && snapshotAth.athDate ? snapshotAth.athDate : '';
    let maxSpread = -Infinity, maxSpreadDate = '';
    for (const d of data) {
        const spread = d.value - d.investment;
        if (spread > maxSpread) { maxSpread = spread; maxSpreadDate = d.date; }
        if (d.value > athValue) {
            athValue = d.value;
            athDate = d.date;
        }
    }

    const latest = data[data.length - 1] || { value: Number(window.PORTFOLIO_TOTAL_VALUE || 0), investment: 0, date: '' };
    const latestValue = latest.value;
    const hasAth = Number.isFinite(athValue) && athValue > 0 && !!athDate;
    const isAthToday = hasAth && latestValue >= athValue;
    const drawdownPct = hasAth ? Math.min(0, ((latestValue - athValue) / athValue) * 100) : 0;
    const drawdownDiff = hasAth ? Math.min(0, latestValue - athValue) : 0;
    const daysFromATH = hasAth ? (isAthToday ? 0 : daysBetween(athDate)) : 0;
    const athSourceLabel = snapshotAth && snapshotAth.athSource === 'MANUAL' ? 'Manual override' : (hasAth ? 'Daily snapshots' : 'Pending snapshot');

    let avgTxCard = '';
    if (tradeRows.length > 0) {
        const txByMonth = {};
        for (const r of tradeRows) {
            const m = r.date.slice(0, 7);
            txByMonth[m] = (txByMonth[m] || 0) + 1;
        }
        const txMonths = Object.keys(txByMonth).sort();
        const last6 = txMonths.slice(-6);
        const prev6 = txMonths.slice(-12, -6);
        const avg6 = last6.length ? last6.reduce((s, m) => s + txByMonth[m], 0) / last6.length : 0;
        const avgPrev6 = prev6.length ? prev6.reduce((s, m) => s + txByMonth[m], 0) / prev6.length : 0;
        const change = avg6 - avgPrev6;
        const changeSub = avgPrev6 > 0
            ? `${change >= 0 ? '+' : ''}${change.toFixed(1)} vs prev 6 months (avg ${avgPrev6.toFixed(1)}/mo)`
            : 'No prior 6-month comparison available';
        avgTxCard = statCard('Avg Transactions / Month (6mo MA)', avg6.toFixed(1), changeSub);
    }

    document.getElementById('stats-alltime').innerHTML =
        statCard('All-Time High', hasAth ? fmtPLN(athValue) : '—', hasAth ? `${fmtDate(athDate)} · ${athSourceLabel}` : athSourceLabel) +
        statCard('Days Since ATH', hasAth ? (daysFromATH + ' days') : '—', hasAth ? fmtDate(athDate) : 'Nightly snapshot not available yet') +
        statCard('Drawdown from ATH', hasAth ? (drawdownPct === 0 ? '0%' : fmtPct(drawdownPct)) : '—', hasAth ? fmtPLN(drawdownDiff) : 'Waiting for snapshot data') +
        statCard('Highest Profit (Value − Invested)', Number.isFinite(maxSpread) ? fmtPLN(maxSpread) : '—', maxSpreadDate ? fmtDate(maxSpreadDate) : 'Historical snapshot data unavailable') +
        avgTxCard;

    if (data.length < 2) {
        document.getElementById('stats-monthly').innerHTML = '<div class="stat-card"><div class="stat-label">Monthly statistics pending</div><div class="stat-sub">Need at least two daily snapshots.</div></div>';
        document.getElementById('stats-daily').innerHTML = '<div class="stat-card"><div class="stat-label">Daily statistics pending</div><div class="stat-sub">Need at least two daily snapshots.</div></div>';
        renderMonthlySnapshotTable(data);
        return;
    }

    const monthlyPeriods = _buildPortfolioMonthlyPeriods(data);
    let bestMonthGain = -Infinity, bestMonth = '';
    let worstMonthGain = Infinity, worstMonth = '';
    for (const period of monthlyPeriods) {
        const net = period.netGain;
        const month = period.month;
        if (net > bestMonthGain) { bestMonthGain = net; bestMonth = month; }
        if (net < worstMonthGain) { worstMonthGain = net; worstMonth = month; }
    }

    let monthTurnoverCard = '';
    if (tradeRows.length > 0) {
        const turnoverByMonth = {};
        for (const r of tradeRows) {
            const m = r.date.slice(0, 7);
            turnoverByMonth[m] = (turnoverByMonth[m] || 0) + Math.abs(r.value);
        }
        let bestTurnoverMonth = '', bestTurnoverVal = -Infinity;
        for (const [m, v] of Object.entries(turnoverByMonth)) {
            if (v > bestTurnoverVal) { bestTurnoverVal = v; bestTurnoverMonth = m; }
        }
        if (bestTurnoverMonth) monthTurnoverCard = statCard('Highest Monthly Turnover', fmtPLN(bestTurnoverVal), fmtMonth(bestTurnoverMonth));
    }

    document.getElementById('stats-monthly').innerHTML =
        statCard('Best Month (Net Gain)', fmtPLN(bestMonthGain), fmtMonth(bestMonth)) +
        statCard('Worst Month (Net Gain)', fmtPLN(worstMonthGain), fmtMonth(worstMonth)) +
        monthTurnoverCard;

    let bestDayPct = -Infinity, bestDayPctDate = '';
    let worstDayPct = Infinity, worstDayPctDate = '';
    let bestDayPLN = -Infinity, bestDayPLNDate = '';
    let worstDayPLN = Infinity, worstDayPLNDate = '';
    for (let i = 1; i < data.length; i++) {
        const prev = data[i - 1], curr = data[i];
        if (prev.value === 0) continue;
        const netPLN = (curr.value - prev.value) - (curr.investment - prev.investment);
        const netPct = (netPLN / prev.value) * 100;
        if (netPct > bestDayPct) { bestDayPct = netPct; bestDayPctDate = curr.date; }
        if (netPct < worstDayPct) { worstDayPct = netPct; worstDayPctDate = curr.date; }
        if (netPLN > bestDayPLN) { bestDayPLN = netPLN; bestDayPLNDate = curr.date; }
        if (netPLN < worstDayPLN) { worstDayPLN = netPLN; worstDayPLNDate = curr.date; }
    }

    let dailyTurnoverCard = '';
    if (tradeRows.length > 0) {
        const turnoverByDay = {};
        for (const r of tradeRows) {
            turnoverByDay[r.date] = (turnoverByDay[r.date] || 0) + Math.abs(r.value);
        }
        let bestDay = '', bestDayVal = -Infinity;
        for (const [d, v] of Object.entries(turnoverByDay)) {
            if (v > bestDayVal) { bestDayVal = v; bestDay = d; }
        }
        if (bestDay) dailyTurnoverCard = statCard('Highest Daily Turnover', fmtPLN(bestDayVal), fmtDate(bestDay));
    }

    document.getElementById('stats-daily').innerHTML =
        statCard('Best Day (%)', fmtPct(bestDayPct), fmtDate(bestDayPctDate)) +
        statCard('Worst Day (%)', fmtPct(worstDayPct), fmtDate(worstDayPctDate)) +
        statCard('Best Day (PLN)', fmtPLN(bestDayPLN), fmtDate(bestDayPLNDate)) +
        statCard('Worst Day (PLN)', fmtPLN(worstDayPLN), fmtDate(worstDayPLNDate)) +
        dailyTurnoverCard;

    // ── Render both accordions ────────────────────────────────
    refreshSnapshotTable();

    // Benchmark comparison loads async in parallel, renders when ready
    _loadAllBenchmarkReturns(false).then(benchmarkData => {
        renderBenchmarkComparisonTable(data, benchmarkData);
    }).catch(() => {
        const w = document.getElementById('bm-cmp-wrap');
        if (w) w.innerHTML = '<div class="stats-empty">Could not load benchmark data.</div>';
    });
}

let _snapshotGranularity = 'monthly';
let _snapshotPortfolio = 'summary';

window.setSnapshotGranularity = function(gran) {
    _snapshotGranularity = gran;
    const btns = document.querySelectorAll('#stats-snap-granularity-btns .history-wallet-btn');
    btns.forEach(b => {
        if (b.getAttribute('data-val') === gran) b.classList.add('is-active');
        else b.classList.remove('is-active');
    });
    refreshSnapshotTable();
};

window.setSnapshotPortfolio = function(port) {
    _snapshotPortfolio = port;
    const btns = document.querySelectorAll('#stats-snap-portfolio-btns .history-wallet-btn');
    btns.forEach(b => {
        if (b.getAttribute('data-wallet-key') === port) b.classList.add('is-active');
        else b.classList.remove('is-active');
    });
    refreshSnapshotTable();
};

async function refreshSnapshotTable() {
    const wrap = document.getElementById('returns-table-wrap');
    if (wrap && !wrap.innerHTML) {
        wrap.innerHTML = '<div class="stats-loading">Loading snapshots…</div>';
    }
    
    try {
        let rawData = await _loadStatisticsHistory(_snapshotPortfolio, false);
        if (_snapshotPortfolio === 'summary') {
            rawData = _injectLiveSummaryValue(rawData);
        }
        renderMonthlySnapshotTable(rawData, _snapshotGranularity);
    } catch (e) {
        console.error('Error refreshing snapshot table:', e);
        if (wrap) wrap.innerHTML = '<div class="stats-empty">Error loading snapshots.</div>';
    }
}

async function _initSnapshotControls() {
    const strip = document.getElementById('stats-snap-portfolio-btns');
    if (!strip) return;

    try {
        const list = await window.PortfolioClient.listPortfolios();
        const portfolios = Array.isArray(list?.portfolios) ? list.portfolios : [];
        const realPortfolios = portfolios.filter(p => p.portfolioId !== 'summary');
        
        const allKeys = ['summary', ...realPortfolios.map(p => p.portfolioId)];
        const allLabels = ['Total', ...realPortfolios.map(p => p.name || p.portfolioId)];
        
        strip.innerHTML = allKeys.map((key, i) => {
            const label = allLabels[i];
            const active = key === _snapshotPortfolio;
            return `<button class="history-wallet-btn${active ? ' is-active' : ''}" data-wallet-key="${key}" onclick="setSnapshotPortfolio('${key}')">${label}</button>`;
        }).join('');
    } catch (e) {
        console.warn('Failed to load portfolios for snapshot table', e);
    }
}

// ── Monthly Performance Heatmap ─────────────────────────────────────────

let _heatmapMetric = 'pct';
let _heatmapPortfolio = 'summary';

window.setHeatmapMetric = function(metric) {
    _heatmapMetric = metric;
    const btns = document.querySelectorAll('#heatmap-metric-btns .history-wallet-btn');
    btns.forEach(b => {
        if (b.getAttribute('data-metric') === metric) b.classList.add('is-active');
        else b.classList.remove('is-active');
    });
    refreshHeatmapTable();
};

window.setHeatmapPortfolio = function(port) {
    _heatmapPortfolio = port;
    const btns = document.querySelectorAll('#heatmap-portfolio-btns .history-wallet-btn');
    btns.forEach(b => {
        if (b.getAttribute('data-wallet-key') === port) b.classList.add('is-active');
        else b.classList.remove('is-active');
    });
    refreshHeatmapTable();
};

async function refreshHeatmapTable() {
    const wrap = document.getElementById('heatmap-table-wrap');
    if (wrap && !wrap.innerHTML) {
        wrap.innerHTML = '<div class="stats-loading">Loading heatmap…</div>';
    }

    try {
        let rawData = await _loadStatisticsHistory(_heatmapPortfolio, false);
        if (_heatmapPortfolio === 'summary') {
            rawData = _injectLiveSummaryValue(rawData);
        }
        renderHeatmapTable(rawData, _heatmapMetric);
    } catch (e) {
        console.error('Error loading heatmap:', e);
        if (wrap) wrap.innerHTML = '<div class="stats-empty">Error loading monthly heatmap.</div>';
    }
}

async function _initHeatmapControls() {
    const strip = document.getElementById('heatmap-portfolio-btns');
    if (!strip) return;

    try {
        const list = await window.PortfolioClient.listPortfolios();
        const portfolios = Array.isArray(list?.portfolios) ? list.portfolios : [];
        const realPortfolios = portfolios.filter(p => p.portfolioId !== 'summary');
        
        const allKeys = ['summary', ...realPortfolios.map(p => p.portfolioId)];
        const allLabels = ['Total', ...realPortfolios.map(p => p.name || p.portfolioId)];
        
        strip.innerHTML = allKeys.map((key, i) => {
            const label = allLabels[i];
            const active = key === _heatmapPortfolio;
            return `<button class="history-wallet-btn${active ? ' is-active' : ''}" data-wallet-key="${key}" onclick="setHeatmapPortfolio('${key}')">${label}</button>`;
        }).join('');
    } catch (e) {
        console.warn('Failed to load portfolios for heatmap table', e);
    }
}

function renderHeatmapTable(data, metric = 'pct') {
    const container = document.getElementById('heatmap-table-wrap');
    if (!container) return;

    const monthlyPeriods = _buildPortfolioMonthlyPeriods(data);
    if (!monthlyPeriods || monthlyPeriods.length === 0) {
        container.innerHTML = '<div class="stats-empty">No monthly snapshot history available for heatmap.</div>';
        return;
    }

    const dataMap = {};
    const yearSet = new Set();
    
    for (const p of monthlyPeriods) {
        if (!p.month) continue;
        const parts = p.month.split('-');
        if (parts.length < 2) continue;
        const year = parseInt(parts[0], 10);
        const monthIdx = parseInt(parts[1], 10) - 1; // 0..11
        if (isNaN(year) || isNaN(monthIdx)) continue;
        yearSet.add(year);

        const val = metric === 'pln' ? p.netGain : p.pct;
        dataMap[`${year}-${monthIdx}`] = val;
    }

    const years = [...yearSet].sort((a, b) => a - b);
    if (years.length === 0) {
        container.innerHTML = '<div class="stats-empty">No yearly data available for heatmap.</div>';
        return;
    }

    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    // Max absolute value for heatmap opacity scaling
    let maxAbs = 0;
    Object.values(dataMap).forEach(v => {
        if (Number.isFinite(v) && Math.abs(v) > maxAbs) maxAbs = Math.abs(v);
    });
    if (maxAbs === 0) maxAbs = 1;

    let html = `<div class="heatmap-scroll-wrap"><table class="heatmap-table">`;

    // Header row: Month | Avg Return | 2020 | 2021 | 2022 ...
    html += `<thead><tr>`;
    html += `<th class="heatmap-th-month">Month</th>`;
    html += `<th class="heatmap-th-avg">Avg (${metric === 'pln' ? 'PLN' : '%'})</th>`;
    years.forEach(y => {
        html += `<th class="heatmap-th-year">${y}</th>`;
    });
    html += `</tr></thead><tbody>`;

    // 12 Rows for Months
    for (let m = 0; m < 12; m++) {
        html += `<tr>`;
        html += `<td class="heatmap-td-month">${monthNames[m]}</td>`;

        // Compute average return for this month across all years
        let mSum = 0;
        let mCount = 0;
        years.forEach(y => {
            const v = dataMap[`${y}-${m}`];
            if (v !== undefined && Number.isFinite(v)) {
                mSum += v;
                mCount++;
            }
        });

        const mAvg = mCount > 0 ? (mSum / mCount) : null;
        let avgText = '—';
        let avgStyle = '';
        if (mAvg !== null) {
            const sign = mAvg > 0 ? '+' : '';
            if (metric === 'pln') {
                avgText = `${sign}${mAvg.toLocaleString('pl-PL', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} PLN`;
            } else {
                avgText = `${sign}${mAvg.toFixed(2)}%`;
            }
            const color = mAvg > 0 ? '#27ae60' : mAvg < 0 ? '#c0392b' : '#94a3b8';
            avgStyle = `style="color:${color};font-weight:700;"`;
        }

        html += `<td class="heatmap-td-avg" ${avgStyle}>${avgText}</td>`;

        // Year cells
        years.forEach(y => {
            const val = dataMap[`${y}-${m}`];
            if (val === undefined || !Number.isFinite(val)) {
                html += `<td class="heatmap-cell heatmap-empty">—</td>`;
            } else {
                const sign = val > 0 ? '+' : '';
                let text = '';
                if (metric === 'pln') {
                    text = `${sign}${val.toLocaleString('pl-PL', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
                } else {
                    text = `${sign}${val.toFixed(2)}%`;
                }

                const ratio = Math.min(1, Math.abs(val) / maxAbs);
                const alpha = (0.15 + ratio * 0.40).toFixed(2);
                let bg = '', textColor = '', border = '';

                if (val > 0) {
                    bg = `rgba(39, 174, 96, ${alpha})`;
                    textColor = '#2ecc71';
                    border = `rgba(39, 174, 96, ${(0.25 + ratio * 0.45).toFixed(2)})`;
                } else if (val < 0) {
                    bg = `rgba(192, 57, 43, ${alpha})`;
                    textColor = '#e74c3c';
                    border = `rgba(192, 57, 43, ${(0.25 + ratio * 0.45).toFixed(2)})`;
                } else {
                    bg = 'rgba(255, 255, 255, 0.04)';
                    textColor = '#94a3b8';
                    border = 'rgba(255, 255, 255, 0.08)';
                }

                html += `<td class="heatmap-cell" style="background:${bg};color:${textColor};border:1px solid ${border};">${text}</td>`;
            }
        });

        html += `</tr>`;
    }

    html += `</tbody></table></div>`;
    container.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', function () {
    let _statsRendered = false;

    _initSnapshotControls();
    _initHeatmapControls();
    refreshHeatmapTable();

    // Initial render on page load — loads snapshots + transactions + benchmark data once.
    renderStatisticsSummary().then(() => {
        _statsRendered = true;
    }).catch(error => {
        console.warn('Failed to render statistics summary from live snapshots:', error);
    });

    // liveDataReady fires 2-3 times per page (cached, lite, full).
    // Only trigger a render if the initial load hasn't completed yet
    // (e.g. live data arrived before snapshots finished).
    // Never pass force=true — benchmark returns and snapshots only change monthly.
    document.addEventListener('liveDataReady', () => {
        refreshHeatmapTable();
        if (_statsRendered) return; // already rendered, skip
        renderStatisticsSummary(false).then(() => {
            _statsRendered = true;
        }).catch(error => {
            console.warn('Failed to refresh statistics summary after live data load:', error);
        });
    });

    // ledgerTransactionsUpdated fires every time publish() is called, which itself
    // can be triggered by renderStatisticsSummary → loadRows. Do NOT re-render here
    // or we create an infinite loop. Transactions are already cached by _loaded flag.
});
