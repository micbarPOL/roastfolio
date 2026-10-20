(function (root) {
    'use strict';

    const MINUTE = 60000;
    const MAX_OPEN_DELAY = 15 * MINUTE;
    // Yahoo exchange quotes (benchmark and holdings) arrive 15 minutes late, so the portfolio line
    // stops at the same delayed minute instead of running flat into "now".
    const QUOTE_DELAY = 15 * MINUTE;
    const SESSIONS = {
        WIG: ['Europe/Warsaw', '09:00', '17:00', 'PLN'],
        WIG20: ['Europe/Warsaw', '09:00', '17:00', 'PLN'],
        MWIG40: ['Europe/Warsaw', '09:00', '17:00', 'PLN'],
        SWIG80: ['Europe/Warsaw', '09:00', '17:00', 'PLN'],
        SP500: ['America/New_York', '09:30', '16:00', 'USD'],
        NASDAQ: ['America/New_York', '09:30', '16:00', 'USD'],
        DAX: ['Europe/Berlin', '09:00', '17:30', 'EUR'],
        MSCI_WORLD: ['Europe/Amsterdam', '09:00', '17:30', 'EUR'],
        FTSE100: ['Europe/London', '08:00', '16:30', 'GBP'],
    };

    function localParts(timestamp, timeZone) {
        return Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
            timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
        }).formatToParts(timestamp).map(part => [part.type, part.value]));
    }

    function localDate(timestamp, timeZone) {
        const p = localParts(timestamp, timeZone);
        return `${p.year}-${p.month}-${p.day}`;
    }

    function localTime(date, clock, timeZone) {
        const target = Date.parse(`${date}T${clock}:00Z`);
        let result = target;
        for (let i = 0; i < 3; i++) {
            const p = localParts(result, timeZone);
            const represented = Date.parse(`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:00Z`);
            result += target - represented;
        }
        return result;
    }

    function validPrice(value) {
        return typeof value === 'number' && Number.isFinite(value) && value > 0;
    }

    function benchmarkBars(data) {
        return (data.intraday || []).filter(bar =>
            Number.isFinite(bar.t) && validPrice(bar.c)
        ).map(bar => ({ timestamp: bar.t < 1e12 ? bar.t * 1000 : bar.t, price: bar.c, open: bar.o }))
            .sort((a, b) => a.timestamp - b.timestamp);
    }

    function synthesize({ holdings, benchmark, benchmarkId, mode = 'session', now = Date.now(), quoteDelay = QUOTE_DELAY }) {
        const config = SESSIONS[benchmarkId];
        if (!config) throw new Error(`No intraday session configured for ${benchmarkId}.`);
        if (!['session', 'day'].includes(mode)) throw new Error('Invalid intraday chart window.');
        if (benchmark.benchmarkId && benchmark.benchmarkId !== benchmarkId) {
            throw new Error(`Waiting for ${benchmarkId} minute bars. Refresh prices.`);
        }
        const [timeZone, openClock, closeClock, benchmarkCurrency] = config;
        const allBenchmarkBars = benchmarkBars(benchmark);
        if (!allBenchmarkBars.length) throw new Error('Benchmark minute bars are unavailable. Refresh prices.');
        const date = localDate(allBenchmarkBars.at(-1).timestamp, timeZone);
        const start = localTime(date, openClock, timeZone);
        const scheduledEnd = localTime(date, closeClock, timeZone);
        const provided = benchmark.session;
        const providedStart = Number(provided?.start) * 1000;
        const providedEnd = Number(provided?.end) * 1000;
        const hasSession = Number.isFinite(providedStart) && Number.isFinite(providedEnd) &&
            localDate(providedStart, timeZone) === date && providedEnd > start;
        const end = hasSession ? Math.min(scheduledEnd, providedEnd) : scheduledEnd;
        const bars = allBenchmarkBars.filter(bar => bar.timestamp >= start && bar.timestamp < end);
        // Index feeds (e.g. WIG on Yahoo) often publish the first print a minute or two after the open.
        if (!bars.length || bars[0].timestamp - start > MAX_OPEN_DELAY || !validPrice(bars[0].open)) {
            throw new Error('Benchmark opening candle is missing; a since-open comparison is unavailable.');
        }
        const warnings = ['Current holdings and cash; constant FX. Benchmark return is in its native currency.'];
        const benchmarkStart = bars[0].timestamp;
        if (!hasSession) warnings.push('Scheduled closing time; exchange closure metadata unavailable.');
        if (benchmarkStart > start) {
            warnings.push(`Benchmark first print ${new Intl.DateTimeFormat('en-GB', {
                timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
            }).format(benchmarkStart)} is used as its opening value.`);
        }
        if (date !== localDate(now, timeZone)) warnings.push(`Showing the latest available session (${date}), not today.`);
        const dayStart = localTime(date, '00:00', timeZone);
        const nextDate = new Date(Date.parse(`${date}T12:00:00Z`) + 86400000).toISOString().slice(0, 10);
        const dayEnd = localTime(nextDate, '00:00', timeZone);
        const delayedNow = now - quoteDelay;
        const until = Math.floor(Math.min(delayedNow, mode === 'session' ? end : dayEnd - MINUTE) / MINUTE) * MINUTE;
        if (until < start) {
            throw new Error(now < start ? 'Waiting for the benchmark session to open.'
                : `Quotes are delayed ${Math.round(quoteDelay / MINUTE)} minutes; the chart starts at ${new Intl.DateTimeFormat('en-GB', {
                    timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
                }).format(start + quoteDelay)}.`);
        }
        if (!Array.isArray(holdings) || !holdings.length) throw new Error('Portfolio holdings are unavailable.');
        let cash = 0;
        const stocks = [];
        for (const holding of holdings) {
            const name = holding.name || holding.ticker || 'Holding';
            if (holding.ticker == null) {
                if (!Number.isFinite(holding.currentValue)) throw new Error(`Cash value unavailable: ${name}.`);
                cash += holding.currentValue;
                continue;
            }
            if (!Number.isFinite(holding.units) || holding.units < 0 || !validPrice(holding.intradayFxRate)) {
                throw new Error(`Units or FX rate unavailable: ${name}.`);
            }
            if (holding.units === 0) continue;
            const prices = (holding.comparisonBars?.length ? holding.comparisonBars : holding.todayBars || []).filter(pair =>
                Array.isArray(pair) && Number.isFinite(pair[0]) && validPrice(pair[1])
            ).map(pair => ({ timestamp: pair[0] + MINUTE, price: pair[1] }))
                .sort((a, b) => a.timestamp - b.timestamp);
            const baseline = holding.intradayBaseline;
            let price = null;
            for (const bar of prices) {
                if (bar.timestamp <= start) price = bar.price;
                else break;
            }
            if (baseline?.openTime === start && validPrice(baseline.openPrice)) {
                price = baseline.openPrice;
            } else if (!validPrice(price) && baseline?.sessionStart > start && baseline.sessionStart < dayEnd &&
                baseline.openTime >= baseline.sessionStart && baseline.openTime < dayEnd &&
                validPrice(baseline.previousClose)) {
                price = baseline.previousClose;
            }
            if (!prices.length || !validPrice(price)) {
                throw new Error(`Session-start price unavailable: ${name}. No holdings were excluded.`);
            }
            const last = prices.at(-1).timestamp;
            if (last < until - 5 * MINUTE) {
                warnings.push(`${name}: last minute bar ${new Intl.DateTimeFormat('en-GB', {
                    timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
                }).format(last)}; prices carried forward.`);
            }
            let index = 0;
            while (index < prices.length && prices[index].timestamp <= start) index++;
            stocks.push({ prices, price, index, units: holding.units, fx: holding.intradayFxRate });
        }
        const openValue = cash + stocks.reduce((sum, stock) => sum + stock.units * stock.price * stock.fx, 0);
        if (!validPrice(openValue)) throw new Error('Portfolio session-start value must be positive.');
        const points = [];
        let benchmarkIndex = 0;
        let benchmarkPrice = bars[0].open;
        const benchmarkAsOf = Math.min(until, end, bars.at(-1).timestamp + MINUTE);
        const portfolioAsOf = stocks.length
            ? Math.min(until, Math.max(start, ...stocks.map(stock => stock.prices.at(-1).timestamp)))
            : until;
        for (let timestamp = start; timestamp <= until; timestamp += MINUTE) {
            for (const stock of stocks) {
                while (stock.index < stock.prices.length && stock.prices[stock.index].timestamp <= timestamp) {
                    stock.price = stock.prices[stock.index++].price;
                }
            }
            while (benchmarkIndex < bars.length && bars[benchmarkIndex].timestamp + MINUTE <= timestamp) {
                benchmarkPrice = bars[benchmarkIndex++].price;
            }
            const value = cash + stocks.reduce((sum, stock) => sum + stock.units * stock.price * stock.fx, 0);
            const portfolioPct = (value / openValue - 1) * 100;
            const benchmarkPct = timestamp >= benchmarkStart && timestamp <= benchmarkAsOf && timestamp <= end
                ? (benchmarkPrice / bars[0].open - 1) * 100 : null;
            points.push({
                timestamp, portfolioPct, benchmarkPct,
                spreadPp: portfolioPct == null || benchmarkPct == null ? null : portfolioPct - benchmarkPct,
            });
        }
        return {
            points, sessionDate: date, baseline: 'benchmark-session-open',
            start, end, timeZone, benchmarkCurrency, openValue,
            axisStart: mode === 'day' ? dayStart : start,
            axisEnd: mode === 'day' ? dayEnd : end,
            portfolioAsOf, benchmarkAsOf, quoteDelay, warnings,
        };
    }

    root.IntradayComparison = { synthesize, localTime };
    if (typeof module !== 'undefined') module.exports = root.IntradayComparison;
    if (typeof document === 'undefined') return;

    let chart = null;
    let mode = 'session';
    function preferenceKey() {
        const user = root.AuthGuard?.getUserId?.();
        return `intraday-comparison-window:${user || 'local'}`;
    }
    function render() {
        const canvas = document.getElementById('intraday-comparison-chart');
        const status = document.getElementById('intraday-comparison-status');
        if (!canvas || !status) return;
        const renderStarted = performance.now();
        try {
            if (typeof root.Chart !== 'function') throw new Error('Chart library unavailable. Reload to retry.');
            const synthesisStarted = performance.now();
            const data = synthesize({
                holdings: root.PORTFOLIO_DATA, benchmark: root.BENCHMARK_DATA || {},
                benchmarkId: root.BENCHMARK_ID || 'WIG', mode,
            });
            root.DashboardPerformance?.record('intraday-synthesis', performance.now() - synthesisStarted, {
                pointCount: data.points.length, holdingCount: root.PORTFOLIO_DATA?.length,
            });
            const style = getComputedStyle(canvas);
            const text = style.getPropertyValue('--text-secondary').trim() || '#94a3b8';
            const portfolioColor = style.getPropertyValue('--accent-primary').trim() || '#7db7d9';
            const benchmarkColor = style.getPropertyValue('--color-warning').trim() || '#f4a261';
            const time = timestamp => new Intl.DateTimeFormat('en-GB', {
                timeZone: data.timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
            }).format(timestamp);
            const datasets = [
                { label: 'Portfolio (PLN, constant FX)', key: 'portfolioPct', borderColor: portfolioColor },
                { label: `${root.BENCHMARK_NAME || root.BENCHMARK_ID || 'WIG'} (${data.benchmarkCurrency})`,
                    key: 'benchmarkPct', borderColor: benchmarkColor, borderDash: [5, 4] },
            ].map(series => ({
                ...series, data: data.points.map(point => ({ x: point.timestamp, y: point[series.key] })),
                pointRadius: 0, pointHitRadius: 12, borderWidth: 2, spanGaps: false,
            }));
            if (chart) chart.destroy();
            chart = new root.Chart(canvas, {
                type: 'line', data: { datasets },
                plugins: [{
                    id: 'benchmarkSessionClose',
                    afterDraw(instance) {
                        if (mode !== 'day') return;
                        const { ctx, chartArea, scales } = instance;
                        const x = scales.x.getPixelForValue(data.end);
                        ctx.save();
                        ctx.strokeStyle = benchmarkColor;
                        ctx.setLineDash([3, 4]);
                        ctx.beginPath();
                        ctx.moveTo(x, chartArea.top);
                        ctx.lineTo(x, chartArea.bottom);
                        ctx.stroke();
                        ctx.setLineDash([]);
                        ctx.fillStyle = text;
                        ctx.font = '11px sans-serif';
                        ctx.textAlign = x > (chartArea.left + chartArea.right) / 2 ? 'right' : 'left';
                        ctx.fillText(`Benchmark close ${time(data.end)}`, x - 4, chartArea.top + 12);
                        ctx.restore();
                    },
                }],
                options: {
                    responsive: true, maintainAspectRatio: false, animation: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { labels: { color: text } },
                        tooltip: { callbacks: {
                            title: items => items.length ? `${data.sessionDate} ${time(items[0].parsed.x)}` : '',
                            label: item => `${item.dataset.label}: ${Number.isFinite(item.parsed.y) ? `${item.parsed.y.toFixed(2)}%` : 'n/a'}`,
                            afterBody: items => {
                                const point = data.points[items[0]?.dataIndex];
                                const spread = point?.spreadPp == null ? 'Comparison unavailable at this minute'
                                    : `Spread: ${point.spreadPp.toFixed(2)} pp`;
                                return point?.timestamp > data.portfolioAsOf
                                    ? `${spread}\nPortfolio carries forward last available prices`
                                    : spread;
                            },
                        } },
                    },
                    scales: {
                        x: { type: 'linear', min: data.axisStart, max: data.axisEnd,
                            ticks: { color: text, maxTicksLimit: 7,
                                callback: value => mode === 'day' && value === data.axisEnd ? '24:00' : time(value) },
                            grid: { display: false } },
                        y: { ticks: { color: text, callback: value => `${value.toFixed(1)}%` },
                            grid: { color: style.getPropertyValue('--border-subtle').trim() || 'rgba(128,128,128,.15)' } },
                    },
                },
            });
            status.textContent = `${data.sessionDate} · ${data.timeZone} · Since ${time(data.start)} · ` +
                `Benchmark ${Date.now() >= data.end ? 'closed' : 'closes'} ${time(data.end)} · ` +
                `Benchmark bars through ${time(data.benchmarkAsOf)} · ` +
                `Portfolio bars through ${time(data.portfolioAsOf)} · ` +
                `Both lines delayed ${Math.round(data.quoteDelay / MINUTE)} min. ${data.warnings.join(' ')}`;
            root.DashboardPerformance?.record('intraday-render', performance.now() - renderStarted, { status: 'ok' });
            requestAnimationFrame(() => requestAnimationFrame(() => root.DashboardPerformance?.mark('intraday-ready')));
        } catch (error) {
            root.DashboardPerformance?.record('intraday-render', performance.now() - renderStarted, { status: 'unavailable' });
            if (chart) { chart.destroy(); chart = null; }
            status.textContent = error.message;
        }
    }
    function init() {
        const select = document.getElementById('intraday-comparison-window');
        if (!select) return;
        try {
            const saved = localStorage.getItem(preferenceKey());
            if (saved === 'session' || saved === 'day') mode = saved;
        } catch (error) {
            console.warn('Unable to read intraday chart preference', error);
        }
        select.value = mode;
        const info = document.querySelector('#tab-dashboard .intraday-info');
        if (info) {
            // Tap toggles it because iOS Safari never focuses a tapped button.
            info.querySelector('button').addEventListener('click', () => {
                const open = !info.classList.contains('is-open');
                info.classList.toggle('is-open', open);
                info.classList.toggle('is-dismissed', !open);
            });
            document.addEventListener('click', (event) => {
                if (!info.contains(event.target)) info.classList.remove('is-open');
            });
            info.addEventListener('keydown', (event) => {
                if (event.key !== 'Escape') return;
                info.classList.remove('is-open');
                info.classList.add('is-dismissed');
            });
            info.addEventListener('mouseleave', () => info.classList.remove('is-dismissed'));
            info.addEventListener('focusout', () => info.classList.remove('is-dismissed'));
        }
        select.addEventListener('change', () => {
            mode = select.value;
            try { localStorage.setItem(preferenceKey(), mode); }
            catch (error) { console.warn('Unable to save intraday chart preference', error); }
            render();
        });
        render();
    }
    document.addEventListener('liveDataReady', render);
    root.addEventListener('roastfolio:themechange', render);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})(typeof window === 'undefined' ? globalThis : window);
