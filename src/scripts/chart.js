const _historyCharts = {};
let _historyLoadPromise = null;
let _historyRange = 'ALL';
let _historyReturnMode = 'pct';
let _historyWalletKey = 'summary'; // 'summary' | wallet name
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

function _getResamplingStrategy(range, dates) {
    if (range === 'ALL' || range === '10Y' || range === '5Y') return 'monthly';
    if (range === '3Y') return 'weekly';
    
    return 'daily'; // 1Y, YTD, 6M, 3M, 1M, 1W
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
        return `<button class="history-wallet-btn${active ? ' is-active' : ''}" data-wallet-key="${key}" onclick="setHistoryWallet('${key}')">${label}</button>`;
    }).join('');
}

async function _loadHistorySnapshots(force = false) {
    if (!window.PortfolioClient) return { summary: [], wallets: {} };
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
        if (typeof window !== 'undefined' && window.PORTFOLIO_TOTAL_VALUE) {
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
            if (typeof window !== 'undefined' && liveWalletVal != null) {
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

        return {
            summary: summaryRows,
            wallets,
        };
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
        button.classList.toggle('active', button.getAttribute(attrName) === value);
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
            label: 'Portfolio Value',
            data: data.map(d => d.value),
            borderColor: '#7db7d9',
            backgroundColor: 'rgba(125,183,217,0.08)',
            borderWidth: compact ? 1.5 : 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.15,
        },
        {
            label: 'Investment',
            data: data.map(d => d.investment),
            borderColor: '#d8b4d8',
            backgroundColor: 'rgba(216,180,216,0.08)',
            borderWidth: compact ? 1.5 : 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.15,
        },
    ];

    // Add all historical ATH peaks as points
    const athPeaksData = data.map(d => d.isAthPeak ? d.value : null);
    const hasPeaks = athPeaksData.some(v => v !== null);

    if (hasPeaks) {
        datasets.push({
            label: 'ATH Peaks',
            data: athPeaksData,
            backgroundColor: context => {
                const index = context.dataIndex;
                if (index === undefined || !data[index]) return 'rgba(255, 200, 50, 0.5)';
                return data[index].date === starDate ? 'rgba(255, 200, 50, 0.95)' : 'rgba(255, 200, 50, 0.5)';
            },
            borderColor: context => {
                const index = context.dataIndex;
                if (index === undefined || !data[index]) return 'rgba(220, 140, 0, 0.7)';
                return data[index].date === starDate ? 'rgba(220, 140, 0, 1)' : 'rgba(220, 140, 0, 0.7)';
            },
            borderWidth: compact ? 1.5 : 2,
            pointRadius: context => {
                const index = context.dataIndex;
                if (index === undefined || !data[index] || !data[index].isAthPeak) return 0;
                return data[index].date === starDate ? (compact ? 6 : 9) : (compact ? 3.5 : 5.5);
            },
            pointHoverRadius: context => {
                const index = context.dataIndex;
                if (index === undefined || !data[index] || !data[index].isAthPeak) return 0;
                return data[index].date === starDate ? (compact ? 8 : 11) : (compact ? 5.5 : 7.5);
            },
            pointStyle: context => {
                const index = context.dataIndex;
                if (index === undefined || !data[index]) return 'circle';
                return data[index].date === starDate ? 'star' : 'circle';
            },
            showLine: false,
            spanGaps: false,
            order: 9,
        });
    }

    if (absoluteLastAthValue != null) {
        // Horizontal dashed ATH reference line
        datasets.push({
            label: 'ATH',
            data: data.map(() => absoluteLastAthValue),
            borderColor: 'rgba(255, 200, 50, 0.7)',
            backgroundColor: 'transparent',
            borderWidth: compact ? 1 : 1.5,
            borderDash: [5, 4],
            pointRadius: 0,
            pointHoverRadius: 0,
            tension: 0,
            fill: false,
            order: 10,
        });
    }

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
                legend: {
                    display: !compact,
                    position: 'top',
                    labels: { filter: item => item.text !== 'ATH Peaks', color: _chartTextColor() },
                },
                tooltip: {
                    filter: item => item.dataset.label !== 'ATH Peaks',
                    callbacks: {
                        title: ctx => 'Date: ' + ctx[0].label,
                        label: ctx => {
                            if (ctx.dataset.label === 'ATH') {
                                return 'Current ATH: ' + Number(ctx.parsed.y || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN';
                            }
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

function _makeMonthlyReturnsChart(canvasId, data) {
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
        const netGain = Number(((curr.value - prev.value) - (curr.investment - prev.investment)).toFixed(2));
        labels.push(months[i]);
        values.push(netGain);
        colors.push(netGain >= 0 ? 'rgba(190, 229, 207, 0.95)' : 'rgba(244, 199, 194, 0.95)');
    }

    _historyCharts[canvasId] = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Monthly Net Gain (PLN)',
                data: values,
                backgroundColor: colors,
                borderColor: colors.map(c => c.includes('190, 229, 207') ? 'rgba(147, 196, 169, 1)' : 'rgba(225, 160, 152, 1)'),
                borderWidth: 1,
                borderRadius: 3,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false, labels: { color: _chartTextColor() } },
                tooltip: {
                    callbacks: {
                        title: ctx => {
                            const [year, month] = ctx[0].label.split('-');
                            return new Date(year, month - 1).toLocaleString('en-US', { month: 'long', year: 'numeric' });
                        },
                        label: ctx => {
                            const value = Number(ctx.parsed.y || 0);
                            return 'Net gain: ' + (value >= 0 ? '+' : '') + value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN';
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

    const labels = changes.map(item => item.date);
    const values = changes.map(item => mode === 'pct' ? item.pct : item.pnl);
    const scatterData = values.map(value => {
        if (value === null) return null;
        const threshold = mode === 'pct' ? 0.1 : 200;
        return Math.abs(value) < threshold ? null : value;
    });
    const scatterColors = values.map(value => {
        if (value === null) return 'transparent';
        const threshold = mode === 'pct' ? 0.1 : 200;
        return Math.abs(value) < threshold ? 'transparent' : _chartDotColor();
    });
    const maWindow = 14;
    const maData = values.map((_, index) => {
        if (index < maWindow - 1) return null;
        const slice = values.slice(index - maWindow + 1, index + 1).filter(v => v !== null);
        if (slice.length === 0) return null;
        const avg = slice.reduce((sum, value) => sum + value, 0) / slice.length;
        return Number(avg.toFixed(mode === 'pct' ? 3 : 2));
    });

    _historyCharts[canvasId] = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: mode === 'pct' ? 'Daily % Change' : 'Daily PLN Change',
                    data: scatterData,
                    backgroundColor: scatterColors,
                    borderColor: 'transparent',
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    showLine: false,
                    spanGaps: false,
                },
                {
                    label: '14-day MA',
                    data: maData,
                    borderColor: 'rgba(119, 132, 148, 0.9)',
                    backgroundColor: 'transparent',
                    borderWidth: mode === 'pct' ? 2 : 1,
                    borderDash: [6, 3],
                    pointRadius: 0,
                    fill: false,
                    tension: 0.3,
                    spanGaps: true,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: true, labels: { filter: item => item.text === '14-day MA', color: _chartTextColor() } },
                tooltip: {
                    callbacks: {
                        title: ctx => 'Date: ' + ctx[0].label,
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
                x: { type: 'category', ticks: { maxTicksLimit: 10, maxRotation: 45, color: _chartTextColor(), callback: _historyXAxisCallback }, grid: { color: _chartGridColor() } },
                y: mode === 'pct'
                    ? {
                        title: { display: true, text: 'Daily % Change', color: _chartTextColor() },
                        ticks: { callback: value => (value >= 0 ? '+' : '') + Number(value).toFixed(1) + '%', color: _chartTextColor() },
                        grid: { color: ctx => ctx.tick.value === 0 ? _chartGridColor(true) : _chartGridColor() },
                    }
                    : {
                        title: { display: true, text: 'Daily PLN Change', color: _chartTextColor() },
                        ticks: { callback: value => (value >= 0 ? '+' : '') + _fmtMoneyTick(value), color: _chartTextColor() },
                        grid: { color: ctx => ctx.tick.value === 0 ? _chartGridColor(true) : _chartGridColor() },
                    },
            },
        },
    });
}

function _makeCumulativeReturnChart(canvasId, data, mode) {
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

    _historyCharts[canvasId] = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: mode === 'pln' ? 'Cumulative Return (PLN)' : 'Cumulative Return (%)',
                data: returns,
                borderColor: '#7db7d9',
                backgroundColor: 'rgba(125,183,217,0.08)',
                borderWidth: 2.5,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.15,
                fill: true,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: true, position: 'top', labels: { color: _chartTextColor() } },
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
                        title: { display: true, text: 'Return (PLN)', color: _chartTextColor() },
                        ticks: { callback: value => (value >= 0 ? '+' : '') + _fmtMoneyTick(value), color: _chartTextColor() },
                        grid: { color: ctx => ctx.tick.value === 0 ? _chartGridColor(true) : _chartGridColor() },
                    }
                    : {
                        title: { display: true, text: 'Return (%)', color: _chartTextColor() },
                        ticks: { callback: value => (value >= 0 ? '+' : '') + Number(value).toFixed(0) + '%', color: _chartTextColor() },
                        grid: { color: ctx => ctx.tick.value === 0 ? _chartGridColor(true) : _chartGridColor() },
                    },
            },
        },
    });
}

async function renderHistoryTab(force = false) {
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

        // Pick data source based on selected wallet
        const isTotal = _historyWalletKey === 'summary';
        const activeRows = isTotal ? history.summary : (history.wallets[_historyWalletKey] || []);
        const filteredMain = _filterHistoryRows(activeRows, _historyRange);
        const anchoredMain = _filterHistoryRowsWithAnchor(activeRows, _historyRange);
        const activeAth = isTotal ? (window.PORTFOLIO_ATH || null) : ((window.WALLET_ATHS || {})[_historyWalletKey] || null);

        // Resample line charts to improve rendering on long histories
        const strategy = _getResamplingStrategy(_historyRange, filteredMain.map(r => r.date));
        const resampledMain = _resampleHistoryRows(filteredMain, strategy);

        _makeLineChart('investmentChart', resampledMain, false, activeAth, activeRows);
        _makeMonthlyReturnsChart('monthlyReturnsChart', anchoredMain);
        _makeCumulativeReturnChart('returnsChart', resampledMain, _historyReturnMode);
        _makeDailyChangeChart('dailyChangeChart', anchoredMain, 'pct');
        _makeDailyChangeChart('dailyPLNChart', anchoredMain, 'pln');
    } catch (error) {
        console.warn('Failed to render history tab from live snapshots:', error);
        ['investmentChart', 'monthlyReturnsChart', 'returnsChart', 'dailyChangeChart', 'dailyPLNChart']
            .forEach(id => _setChartMessage(id, error.message || 'Could not load snapshot history.'));
    }
}

window.renderHistoryTab = renderHistoryTab;
window.setHistoryWallet = function setHistoryWallet(key) {
    _historyWalletKey = key || 'summary';
    // Update button active state immediately for snappy feel
    document.querySelectorAll('.history-wallet-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.walletKey === _historyWalletKey);
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
