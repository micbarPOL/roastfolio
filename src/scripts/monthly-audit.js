(() => {
    'use strict';

    const MONTHS = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December',
    ];
    const state = {
        initialized: false,
        loading: false,
        selectedPeriod: '',
        selectedYear: new Date().getFullYear(),
        items: new Map(),
        availableYears: [],
    };

    const escapeHtml = value => String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');

    const number = value => {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    };
    const finite = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
    // ISO dates are labels supplied by the report, never inferred observation dates.
    const storedDate = value => value ? String(value) : 'No data';
    const dateTime = value => /^\d{4}-\d{2}-\d{2}$/.test(value || '') ? Date.parse(`${value}T00:00:00Z`) : NaN;

    const formatPLN = (value, showSign = false) => {
        if (value == null || value === '' || !Number.isFinite(Number(value))) return 'No data';
        const amount = number(value);
        const rounded = Math.round(amount);
        const sign = rounded < 0 ? '-' : showSign && rounded > 0 ? '+' : '';
        const grouped = Math.abs(rounded).toLocaleString('en-GB');
        return `${sign}${grouped} PLN`;
    };

    const formatPct = (value, showSign = false) => {
        if (value == null || value === '' || !Number.isFinite(Number(value))) return 'No data';
        const amount = number(value) || 0;
        const sign = showSign && amount > 0 ? '+' : '';
        return `${sign}${amount.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
    };

    const formatDate = value => {
        if (!value) return 'No data';
        const parsed = new Date(`${String(value).slice(0, 10)}T12:00:00`);
        return Number.isNaN(parsed.getTime())
            ? escapeHtml(value)
            : parsed.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    };

    const tone = value => number(value) > 0 ? 'is-positive' : number(value) < 0 ? 'is-negative' : 'is-neutral';

    function apiBase() {
        const config = window.__CONFIG__ || window.APP_CONFIG || {};
        return String(config.apiUrl || '').replace(/\/prices$/, '');
    }

    async function fetchJson(path) {
        const token = window.AuthGuard && AuthGuard.getIdToken ? AuthGuard.getIdToken() : '';
        const response = await fetch(`${apiBase()}${path}`, {
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(payload.error || `HTTP ${response.status}`);
            error.status = response.status;
            throw error;
        }
        return payload;
    }

    async function postJson(path, body) {
        const token = window.AuthGuard && AuthGuard.getIdToken ? AuthGuard.getIdToken() : '';
        const response = await fetch(`${apiBase()}${path}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify(body),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(payload.error || `HTTP ${response.status}`);
            error.status = response.status;
            throw error;
        }
        return payload;
    }

    async function sendRecapEmail(period, options = {}) {
        const payload = { period };
        if (options && typeof options.hideCash === 'boolean') {
            payload.hideCash = options.hideCash;
        }
        return await postJson('/monthly-wraps/email', payload);
    }
    window.sendMonthlyRecapEmail = sendRecapEmail;

    function isCurrentMonth(period) {
        const now = new Date();
        const currentPeriod = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
        return period === currentPeriod;
    }

    function ingestItems(items) {
        (Array.isArray(items) ? items : []).forEach(item => {
            const period = String(item?.period || item?.SK?.replace('WRAP#MONTH#', '') || '');
            if (/^\d{4}-\d{2}$/.test(period)) {
                if (item.is_live !== undefined || item.overall_twr_pct !== undefined) {
                    item._isLiveStub = false;
                }
                state.items.set(period, { ...item, period });
            }
        });
        const current = new Date();
        const currentPeriod = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}`;
        if (!state.items.has(currentPeriod)) {
            state.items.set(currentPeriod, { period: currentPeriod, _isLiveStub: true });
        }
        state.availableYears = [...new Set([...state.items.keys()].map(period => Number(period.slice(0, 4))))].sort((a, b) => a - b);
    }

    function latestExpectedPeriod() {
        const current = new Date();
        current.setDate(1);
        current.setMonth(current.getMonth() - 1);
        return `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}`;
    }

    function renderLoading() {
        const root = document.getElementById('monthly-audit-root');
        if (!root) return;
        root.innerHTML = `
            <div class="monthly-audit-loading" role="status">
                <div class="monthly-audit-loader" aria-hidden="true"></div>
                <strong>Building monthly audit</strong>
                <span>Calculating returns net of external cash flows.</span>
            </div>`;
    }

    function renderError(message) {
        const root = document.getElementById('monthly-audit-root');
        if (!root) return;
        root.innerHTML = `
            <div class="monthly-audit-state" role="alert">
                <strong>Unable to load summary</strong>
                <span>${escapeHtml(message)}</span>
                <button type="button" onclick="initMonthlyAudit(true)">Try again</button>
            </div>`;
    }

    function renderEmpty(period) {
        const item = state.items.get(period);
        if (item && item._isLiveStub) {
            return `
            <div class="monthly-audit-loading" role="status" style="min-height: 300px; display: flex; flex-direction: column; justify-content: center; background: var(--fintech-surface-raised); border-radius: var(--fintech-radius-lg); margin-top: 16px;">
                <div class="monthly-audit-loader" aria-hidden="true"></div>
                <strong>Generating Live MTD</strong>
                <span>Calculating returns net of external cash flows.</span>
            </div>`;
        }
        return `
            <div class="monthly-audit-state monthly-audit-empty">
                <span class="monthly-audit-empty-mark" aria-hidden="true">0</span>
                <strong>No audit for ${escapeHtml(period)}</strong>
                <span>There are no recorded transactions or history data for this month.</span>
            </div>`;
    }

    function timelineMarkup() {
        const periods = [...new Set([...state.items.keys(), state.selectedPeriod])].filter(Boolean).sort();
        const current = periods.indexOf(state.selectedPeriod);
        const options = [...periods].reverse().map(period => `<option value="${period}" ${period === state.selectedPeriod ? 'selected' : ''}>${escapeHtml(window.MonthlyAuditPresentation.periodTitle(period))}${isCurrentMonth(period) ? ' (Live MTD)' : (state.items.has(period) ? '' : ' · No report')}</option>`).join('');
        return `
            <div class="ma-toolbar">
                <div class="ma-edition">YOUR MONTHLY EDITION <span>Less noise. More perspective.</span></div>
                <nav class="ma-period-control" aria-label="Summary months">
                    <button type="button" aria-label="Previous available month" ${current <= 0 ? 'disabled' : ''} onclick="selectMonthlyAuditPeriod('${periods[current - 1] || state.selectedPeriod}')">‹</button>
                    <select aria-label="Choose summary month" onchange="selectMonthlyAuditPeriod(this.value)">${options}</select>
                    <button type="button" aria-label="Next available month" ${current >= periods.length - 1 ? 'disabled' : ''} onclick="selectMonthlyAuditPeriod('${periods[current + 1] || state.selectedPeriod}')">›</button>
                </nav>
            </div>`;
    }

    function metric(label, value, className = '') {
        return `<div class="monthly-audit-metric"><span>${escapeHtml(label)}</span><strong class="${className}">${escapeHtml(value)}</strong></div>`;
    }

    function stat(label, value, detail, className = '', visual = '') {
        return `
            <div class="monthly-audit-stat ${className}">
                <span class="monthly-audit-stat-label">${escapeHtml(label)}</span>
                <strong>${escapeHtml(value)}</strong>
                <small>${escapeHtml(detail)}</small>
                ${visual}
            </div>`;
    }

    function trajectoryVisual(series) {
        if (!Array.isArray(series) || series.length < 2) return '<p class="ma-muted">Daily history unavailable for this report.</p>';
        const values = series.slice(0, 31).map(value => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Math.min(0, Number(value)));
        if (values.filter(value => value !== null).length < 2) return '<p class="ma-muted">Daily history unavailable for this report.</p>';
        const scale = Math.max(...values.filter(value => value !== null).map(value => Math.abs(value)), 1);
        let segments = [[]];
        values.forEach((value, index) => {
            if (value === null) { segments.push([]); return; }
            segments[segments.length - 1].push({ x: 12 + 616 * index / (values.length - 1), y: 16 + Math.abs(value) / scale * 152 });
        });
        const paths = segments.filter(points => points.length).map(points => {
            const line = points.map((point, index) => `${index ? 'L' : 'M'}${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ');
            const first = points[0];
            const last = points[points.length - 1];
            return `<path class="trajectory-lake" d="${line} L${last.x} 16 L${first.x} 16 Z" /><path class="trajectory-line" d="${line}" />`;
        }).join('');
        const minimum = Math.min(...values.filter(value => value !== null), 0);
        const minimumIndex = values.indexOf(minimum);
        return `
            <svg class="monthly-audit-trajectory" viewBox="0 0 640 190" role="img" aria-label="Drawdown through the month. Lowest observed drawdown ${escapeHtml(formatPct(minimum))}.">
                <path class="trajectory-baseline" d="M12 16 H628" />
                ${paths}
                ${minimumIndex >= 0 ? `<circle cx="${12 + 616 * minimumIndex / (values.length - 1)}" cy="${16 + Math.abs(minimum) / scale * 152}" r="5" />` : ''}
            </svg>`;
    }

    function journeyPoints(item) {
        return window.MonthlyAuditPresentation.buildJourney(item).points;
    }

    function journeyLabel(point, benchmarkName) {
        return `${storedDate(point.date)} · Portfolio ${formatPct(point.portfolio_pct, true)} · ${benchmarkName} ${formatPct(point.benchmark_pct, true)}`;
    }

    function journeyVisual(points) {
        const dates = points.map(point => dateTime(point.date)).filter(Number.isFinite);
        const values = points.flatMap(point => Number.isFinite(dateTime(point.date))
            ? [point.portfolio_pct, point.benchmark_pct].filter(finite).map(Number) : []);
        if (new Set(dates).size < 2 || !values.length) return '<p class="ma-muted">Dated return history unavailable for this report.</p>';
        const first = Math.min(...dates), last = Math.max(...dates);
        const low = Math.min(0, ...values), high = Math.max(0, ...values);
        const span = high - low || 1;
        const x = date => 60 + (dateTime(date) - first) / (last - first) * 560;
        const y = value => 22 + (high - value) / span * 168;
        const series = ['portfolio_pct', 'benchmark_pct'].map((key, index) => {
            const segments = [[]];
            points.forEach(point => {
                if (!finite(point[key]) || !Number.isFinite(dateTime(point.date))) { segments.push([]); return; }
                segments[segments.length - 1].push({ x: x(point.date), y: y(Number(point[key])), date: point.date, value: point[key] });
            });
            return segments.filter(segment => segment.length).map(segment => {
                const path = segment.map((point, i) => `${i ? 'L' : 'M'}${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ');
                return `<g class="ma-return-series ma-return-${index ? 'benchmark' : 'portfolio'}"><path d="${path}"/>${segment.map(point => `<circle cx="${point.x}" cy="${point.y}" r="2.5"><title>${escapeHtml(storedDate(point.date))} · ${escapeHtml(formatPct(point.value, true))}</title></circle>`).join('')}</g>`;
            }).join('');
        }).join('');
        const firstLabel = points.find(point => dateTime(point.date) === first)?.date;
        const lastLabel = points.find(point => dateTime(point.date) === last)?.date;
        return `<div class="ma-chart-interactive">
            <p id="ma-journey-help" class="ma-chart-help">Hover or touch the chart to inspect returns. Keyboard: arrows, Home and End.</p>
            <svg class="ma-return-chart" viewBox="-32 0 672 228" tabindex="0" role="slider" aria-label="Dated cumulative returns" aria-describedby="ma-journey-help" aria-orientation="horizontal" aria-valuemin="0" aria-valuemax="${points.length - 1}" aria-valuenow="0">
            ${[...new Set([high, 0, low])].map(value => `<path class="ma-return-grid ${value === 0 ? 'ma-return-zero' : 'ma-return-extreme'}" d="M60 ${y(value)} H620"/><text class="ma-return-grid-label" x="52" y="${y(value) + 4}" text-anchor="end">${escapeHtml(formatPct(value))}</text>`).join('')}
            ${series}
            <g class="ma-return-cursor" visibility="hidden" aria-hidden="true"><path class="ma-return-crosshair" d="M60 22 V190"/><circle class="ma-cursor-portfolio" r="5"/><circle class="ma-cursor-benchmark" r="5"/></g>
            <text x="60" y="218">${escapeHtml(firstLabel)}</text><text x="620" y="218" text-anchor="end">${escapeHtml(lastLabel)}</text></svg>
            <div id="ma-journey-value" class="ma-chart-tooltip" role="tooltip" hidden></div>
        </div>`;
    }

    function journeyCard(item) {
        const journey = window.MonthlyAuditPresentation.buildJourney(item);
        const points = journeyPoints(item);
        const available = key => points.some(point => Number.isFinite(dateTime(point.date)) && finite(point[key]));
        const delta = finite(item.trajectory_delta_pp) ? `${number(item.trajectory_delta_pp) > 0 ? '+' : ''}${number(item.trajectory_delta_pp).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} pp` : 'No data';
        const body = `
            <div class="ma-return-legend"><span class="ma-legend-portfolio">Portfolio · cumulative TWR</span><span class="ma-legend-benchmark">${escapeHtml(journey.benchmark_name || 'Benchmark')}${journey.benchmark_id === 'MSCI_WORLD' && !/proxy/i.test(journey.benchmark_name || '') ? ' · MSCI World proxy' : ''} · ${escapeHtml(journey.benchmark_currency || 'currency unavailable')}</span></div>
            ${!available('portfolio_pct') ? '<p class="ma-muted">Portfolio return history unavailable.</p>' : ''}
            ${!available('benchmark_pct') ? '<p class="ma-muted">Benchmark return history unavailable.</p>' : ''}
            ${journeyVisual(points)}
            <p class="ma-footnote">Cumulative TWR, not account value: deposits and withdrawals do not create returns. Benchmark returns are in its native currency, not converted to PLN. Weekend and empty benchmark observations are extrapolated from the last available day.</p>
            <div class="ma-journey-endpoints">${metric('Deepest drawdown', formatPct(item.max_drawdown_pct))}${metric('Month-end drawdown', formatPct(item.end_drawdown_pct))}${metric('Drawdown change', delta)}</div>
            <details class="ma-details"><summary>Drawdown details</summary><p class="ma-muted">Deepest on ${escapeHtml(storedDate(item.max_drawdown_date))} · Start ${escapeHtml(formatPct(item.start_drawdown_pct))}. Legacy drawdown observations have no stored dates.</p>${trajectoryVisual(item.drawdown_trajectory_pct)}</details>`;
        return card('Your returns, side by side.', 'The journey', body, 'ma-journey');
    }

    function bindJourney(item) {
        const chart = document.querySelector('#monthly-audit-root .ma-return-chart');
        if (!chart || !item) return;
        const { points, benchmark_name: benchmarkName } = window.MonthlyAuditPresentation.buildJourney(item);
        const dates = points.map(point => dateTime(point.date));
        const first = Math.min(...dates), last = Math.max(...dates);
        const values = points.flatMap(point => [point.portfolio_pct, point.benchmark_pct].filter(finite).map(Number));
        const low = Math.min(0, ...values), high = Math.max(0, ...values);
        const y = value => 22 + (high - value) / (high - low || 1) * 168;
        const cursor = chart.querySelector('.ma-return-cursor');
        const tooltip = document.getElementById('ma-journey-value');
        let index = 0;
        const show = (next, pointerEvent) => {
            index = Math.max(0, Math.min(points.length - 1, next));
            const point = points[index];
            const x = 60 + (dates[index] - first) / (last - first) * 560;
            chart.setAttribute('aria-valuenow', String(index));
            chart.setAttribute('aria-valuetext', journeyLabel(point, benchmarkName));

            const hasP = finite(point.portfolio_pct);
            const pVal = hasP ? Number(point.portfolio_pct) : null;
            const pClass = pVal != null ? (pVal > 0 ? 'is-positive' : (pVal < 0 ? 'is-negative' : 'is-neutral')) : 'is-neutral';
            const pText = hasP ? formatPct(point.portfolio_pct, true) : 'No data';

            const hasB = finite(point.benchmark_pct);
            const bVal = hasB ? Number(point.benchmark_pct) : null;
            const bClass = bVal != null ? (bVal > 0 ? 'is-positive' : (bVal < 0 ? 'is-negative' : 'is-neutral')) : 'is-neutral';
            const bText = hasB ? formatPct(point.benchmark_pct, true) : 'No data';

            tooltip.innerHTML = `
                <div class="ma-tooltip-date">${escapeHtml(storedDate(point.date))}</div>
                <div class="ma-tooltip-body">
                    <div class="ma-tooltip-row">
                        <span class="ma-tooltip-key"><span class="ma-tooltip-dot ma-dot-portfolio"></span>My Portfolio</span>
                        <span class="ma-tooltip-val ${pClass}">${escapeHtml(pText)}</span>
                    </div>
                    <div class="ma-tooltip-row">
                        <span class="ma-tooltip-key"><span class="ma-tooltip-dot ma-dot-benchmark"></span>${escapeHtml(benchmarkName || 'Benchmark')}</span>
                        <span class="ma-tooltip-val ${bClass}">${escapeHtml(bText)}</span>
                    </div>
                </div>`;
            tooltip.hidden = false;

            cursor.setAttribute('visibility', 'visible');
            cursor.querySelector('path').setAttribute('d', `M${x} 22 V190`);
            ['portfolio_pct', 'benchmark_pct'].forEach((key, i) => {
                const dot = cursor.querySelectorAll('circle')[i];
                dot.setAttribute('visibility', finite(point[key]) ? 'visible' : 'hidden');
                dot.setAttribute('cx', String(x));
                if (finite(point[key])) dot.setAttribute('cy', String(y(Number(point[key]))));
            });

            const container = chart.parentElement;
            if (container) {
                const containerRect = container.getBoundingClientRect();
                const matrix = chart.getScreenCTM();
                let pixelX = 0;
                let pixelY = 0;
                const primarySvgY = hasP ? y(pVal) : (hasB ? y(bVal) : 106);

                if (matrix && containerRect) {
                    const screenPt = new DOMPoint(x, primarySvgY).matrixTransform(matrix);
                    pixelX = screenPt.x - containerRect.left;
                    if (pointerEvent && Number.isFinite(pointerEvent.clientY)) {
                        pixelY = pointerEvent.clientY - containerRect.top;
                    } else {
                        pixelY = screenPt.y - containerRect.top;
                    }
                } else if (containerRect) {
                    const chartRect = chart.getBoundingClientRect();
                    pixelX = chartRect.left - containerRect.left + ((x + 32) / 672) * chartRect.width;
                    pixelY = chartRect.top - containerRect.top + (primarySvgY / 228) * chartRect.height;
                }

                const tooltipWidth = tooltip.offsetWidth || 180;
                const tooltipHeight = tooltip.offsetHeight || 64;
                const containerWidth = containerRect ? containerRect.width : 500;
                const containerHeight = containerRect ? containerRect.height : 230;

                let posX = pixelX + 14;
                if (posX + tooltipWidth > containerWidth - 8) {
                    posX = pixelX - 14 - tooltipWidth;
                }
                if (posX < 8) posX = 8;
                if (posX + tooltipWidth > containerWidth - 8) {
                    posX = Math.max(8, containerWidth - tooltipWidth - 8);
                }

                let posY = pixelY - tooltipHeight / 2;
                if (posY < 8) posY = 8;
                if (posY + tooltipHeight > containerHeight - 8) {
                    posY = Math.max(8, containerHeight - tooltipHeight - 8);
                }

                tooltip.style.left = `${Math.round(posX)}px`;
                tooltip.style.top = `${Math.round(posY)}px`;
                tooltip.style.transform = 'none';
            }
        };
        const hide = () => {
            cursor.setAttribute('visibility', 'hidden');
            cursor.querySelectorAll('circle').forEach(dot => dot.setAttribute('visibility', 'hidden'));
            tooltip.hidden = true;
        };
        const inspectPointer = event => {
            const matrix = chart.getScreenCTM();
            if (!matrix) return;
            const local = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
            const date = first + Math.max(0, Math.min(1, (local.x - 60) / 560)) * (last - first);
            show(dates.reduce((best, current, i) => Math.abs(current - date) < Math.abs(dates[best] - date) ? i : best, 0), event);
        };
        chart.setAttribute('aria-valuetext', journeyLabel(points[0], benchmarkName));
        chart.addEventListener('pointermove', inspectPointer);
        chart.addEventListener('pointerdown', event => {
            chart.focus({ preventScroll: true });
            inspectPointer(event);
            if (event.pointerType !== 'mouse') chart.setPointerCapture(event.pointerId);
        });
        chart.addEventListener('pointerleave', () => { if (document.activeElement !== chart) hide(); });
        chart.addEventListener('pointercancel', hide);
        chart.addEventListener('focus', () => show(index));
        chart.addEventListener('blur', hide);
        chart.addEventListener('keydown', event => {
            const next = { ArrowRight: index + 1, ArrowUp: index + 1, ArrowLeft: index - 1, ArrowDown: index - 1, Home: 0, End: points.length - 1 };
            if (Object.hasOwn(next, event.key)) { event.preventDefault(); show(next[event.key]); }
            else if (event.key === 'Escape') { event.preventDefault(); hide(); }
        });
    }

    function card(title, eyebrow, body, className = '') {
        return `
            <article class="monthly-audit-card ${className}">
                <header><span>${escapeHtml(eyebrow)}</span><h2>${escapeHtml(title)}</h2></header>
                ${body}
            </article>`;
    }

    function flowsCard(item) {
        const best = item.best_efficiency_wallet || {};
        const engine = item.primary_profit_engine_wallet || {};
        const body = `
            <div class="monthly-audit-summary-grid">
                ${metric('Deposits', formatPLN(item.deposits_pln), 'is-positive')}
                ${metric('Withdrawals', formatPLN(item.withdrawals_pln), item.withdrawals_pln ? 'is-negative' : 'is-neutral')}
            </div>
            <div class="monthly-audit-highlight-grid">
                <div class="monthly-audit-highlight efficiency">
                    <span>Efficiency leader · % TWR</span>
                    <strong>${escapeHtml(best.name || 'No data')}</strong>
                    <b class="${tone(best.twr_pct)}">${escapeHtml(formatPct(best.twr_pct, true))} TWR</b>
                </div>
                <div class="monthly-audit-highlight engine">
                    <span>Primary profit engine · PLN</span>
                    <strong>${escapeHtml(engine.name || 'No data')}</strong>
                    <b class="${tone(engine.nominal_change_pln)}">${escapeHtml(formatPLN(engine.nominal_change_pln, true))}</b>
                </div>
            </div>
            <details class="ma-details"><summary>View wallet details</summary>
                ${(item.wallet_performance || []).map(wallet => `<div class="ma-wallet-row"><strong>${escapeHtml(wallet.name || 'Wallet')}</strong><span>${escapeHtml(formatPct(wallet.twr_pct, true))} TWR</span><span>${escapeHtml(formatPLN(wallet.nominal_change_pln, true))}</span><small>Net cash flow ${escapeHtml(formatPLN(wallet.cash_flow_pln, true))}</small></div>`).join('') || '<p>No wallet data.</p>'}
            </details>`;
        return card('Your money, in motion.', 'Cash flows & wallets', body, 'ma-flows');
    }

    const formatPLN2 = (value, showSign = false) => {
        if (value == null || value === '' || !Number.isFinite(Number(value))) return 'No data';
        const amount = number(value);
        const sign = amount < -0.005 ? '-' : showSign && amount > 0.005 ? '+' : '';
        const formatted = Math.abs(amount).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return `${sign}${formatted} PLN`;
    };

    function getMonthDaysMap(item) {
        const daysMap = new Map();
        if (!item?.period) return daysMap;

        // 1. Primary source: item.daily_moves from wrap
        if (Array.isArray(item.daily_moves) && item.daily_moves.length > 0) {
            for (const move of item.daily_moves) {
                if (!move?.date) continue;
                daysMap.set(move.date, {
                    date: move.date,
                    change_pln: Number(move.change_pln || 0),
                    change_pct: move.change_pct != null ? Number(move.change_pct) : null,
                    is_ath: Boolean(move.is_ath),
                    has_data: true,
                });
            }
        } else {
            // Fallback: check cached history snapshots if available
            const cachedSnapshots = (typeof window !== 'undefined' && typeof window._getHistorySnapshotCache === 'function')
                ? window._getHistorySnapshotCache()?.summary
                : null;
            if (Array.isArray(cachedSnapshots) && cachedSnapshots.length > 0) {
                const ym = item.period;
                const prior = [...cachedSnapshots].reverse().find(s => s.date && s.date < `${ym}-01`);
                const monthSnaps = cachedSnapshots.filter(s => s.date && s.date.startsWith(ym));
                let prevVal = prior ? Number(prior.value || 0) : null;
                let prevInv = prior ? Number(prior.investment || 0) : null;

                for (const snap of monthSnaps) {
                    const curVal = Number(snap.value || 0);
                    const curInv = Number(snap.investment || 0);
                    let changePln = 0;
                    let changePct = 0;
                    if (prevVal != null && prevVal > 0) {
                        const flow = curInv - (prevInv ?? curInv);
                        changePln = curVal - prevVal - flow;
                        changePct = (changePln / prevVal) * 100;
                    }
                    daysMap.set(snap.date, {
                        date: snap.date,
                        change_pln: changePln,
                        change_pct: changePct,
                        is_ath: Boolean(snap.isAthPeak),
                        has_data: true,
                    });
                    prevVal = curVal;
                    prevInv = curInv;
                }
            }
        }

        // 2. Overlay ath_dates
        const athDates = new Set(Array.isArray(item.ath_dates) ? item.ath_dates : []);
        if (item.is_new_ath && item.ath_date) athDates.add(item.ath_date);
        for (const date of athDates) {
            const existing = daysMap.get(date) || { date, change_pln: 0, change_pct: null, has_data: false };
            existing.is_ath = true;
            daysMap.set(date, existing);
        }

        // 3. Overlay best_day and worst_day
        if (item.best_day?.date) {
            const existing = daysMap.get(item.best_day.date) || { date: item.best_day.date, has_data: true };
            if (item.best_day.change_pln != null) existing.change_pln = Number(item.best_day.change_pln);
            if (item.best_day.change_pct != null) existing.change_pct = Number(item.best_day.change_pct);
            if (item.best_day.is_ath != null) existing.is_ath = Boolean(item.best_day.is_ath);
            existing.is_best = true;
            existing.has_data = true;
            daysMap.set(item.best_day.date, existing);
        }
        if (item.worst_day?.date) {
            const existing = daysMap.get(item.worst_day.date) || { date: item.worst_day.date, has_data: true };
            if (item.worst_day.change_pln != null) existing.change_pln = Number(item.worst_day.change_pln);
            if (item.worst_day.change_pct != null) existing.change_pct = Number(item.worst_day.change_pct);
            existing.is_worst = true;
            existing.has_data = true;
            daysMap.set(item.worst_day.date, existing);
        }

        return daysMap;
    }

    function monthCalendarWidget(item) {
        if (!item?.period) return '';
        const [yearStr, monthStr] = item.period.split('-');
        const year = parseInt(yearStr, 10);
        const month = parseInt(monthStr, 10);
        if (isNaN(year) || isNaN(month)) return '';

        const daysMap = getMonthDaysMap(item);
        const daysInMonth = new Date(year, month, 0).getDate();
        const firstDow = new Date(year, month - 1, 1).getDay();
        const offset = (firstDow + 6) % 7;

        let hasAnyAth = false;
        for (const val of daysMap.values()) {
            if (val.is_ath) { hasAnyAth = true; break; }
        }

        const DOW_LABELS = [
            { short: 'M', full: 'Monday' },
            { short: 'T', full: 'Tuesday' },
            { short: 'W', full: 'Wednesday' },
            { short: 'T', full: 'Thursday' },
            { short: 'F', full: 'Friday' },
            { short: 'S', full: 'Saturday' },
            { short: 'S', full: 'Sunday' },
        ];

        let cellsHtml = '';
        for (let i = 0; i < offset; i++) {
            cellsHtml += '<span class="ma-cal-day is-empty" aria-hidden="true"></span>';
        }

        for (let day = 1; day <= daysInMonth; day++) {
            const dayStr = String(day).padStart(2, '0');
            const dateStr = `${item.period}-${dayStr}`;
            const info = daysMap.get(dateStr);

            const hasData = Boolean(info && (info.has_data || info.change_pln != null));
            const changePln = info?.change_pln != null ? Number(info.change_pln) : null;
            const changePct = info?.change_pct != null ? Number(info.change_pct) : null;
            const isAth = Boolean(info?.is_ath);
            const isBest = Boolean(info?.is_best || (item.best_day?.date === dateStr));
            const isWorst = Boolean(info?.is_worst || (item.worst_day?.date === dateStr));

            let returnClass = 'is-neutral';
            if (hasData && changePln != null) {
                if (changePln > 0.005) returnClass = 'is-positive';
                else if (changePln < -0.005) returnClass = 'is-negative';
                else returnClass = 'is-flat';
            }

            const classes = [
                'ma-cal-day',
                hasData ? 'has-data' : 'no-data',
                returnClass,
                isBest ? 'is-best' : '',
                isWorst ? 'is-worst' : '',
                isAth ? 'is-ath' : '',
            ].filter(Boolean).join(' ');

            const dObj = new Date(year, month - 1, day);
            const dateReadable = dObj.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
            let returnDesc = 'No trading data';
            if (hasData && changePln != null) {
                returnDesc = formatPLN(changePln, true);
                if (changePct != null) returnDesc += ` (${formatPct(changePct, true)})`;
            }
            const badgesDesc = [
                isAth ? 'All-Time High' : '',
                isBest ? 'Best Day' : '',
                isWorst ? 'Worst Day' : '',
            ].filter(Boolean).join(', ');
            const ariaLabel = `${dateReadable}: ${returnDesc}${badgesDesc ? ` · ${badgesDesc}` : ''}`;

            cellsHtml += `
                <button type="button" class="${classes}"
                    data-cal-date="${dateStr}"
                    data-cal-day="${day}"
                    data-cal-pln="${changePln != null ? changePln : ''}"
                    data-cal-pct="${changePct != null ? changePct : ''}"
                    data-cal-ath="${isAth ? '1' : '0'}"
                    data-cal-best="${isBest ? '1' : '0'}"
                    data-cal-worst="${isWorst ? '1' : '0'}"
                    data-cal-hasdata="${hasData ? '1' : '0'}"
                    aria-label="${escapeHtml(ariaLabel)}">
                    <span class="ma-cal-num">${day}</span>
                    ${isAth ? '<span class="ma-cal-ath-trophy" aria-hidden="true" title="All-Time High">🏆</span>' : ''}
                    ${isBest ? '<span class="ma-cal-tag is-best" aria-hidden="true" title="Best day">★</span>' : ''}
                    ${isWorst && !isBest ? '<span class="ma-cal-tag is-worst" aria-hidden="true" title="Worst day">▼</span>' : ''}
                </button>`;
        }

        return `
            <div class="ma-calendar-section" id="ma-milestones-calendar">
                <div class="ma-calendar-header">
                    <span class="ma-calendar-title">Daily returns</span>
                    <div class="ma-calendar-legend">
                        <span class="ma-cal-legend-item"><span class="ma-cal-swatch is-positive"></span>Gain</span>
                        <span class="ma-cal-legend-item"><span class="ma-cal-swatch is-negative"></span>Loss</span>
                        ${hasAnyAth ? '<span class="ma-cal-legend-item"><span class="ma-cal-ath-legend">🏆</span>ATH</span>' : ''}
                    </div>
                </div>
                <div class="ma-cal-grid" role="region" aria-label="Monthly daily performance calendar">
                    <div class="ma-cal-dow-row" role="row">
                        ${DOW_LABELS.map(dow => `<span class="ma-cal-dow" role="columnheader" aria-label="${dow.full}">${dow.short}</span>`).join('')}
                    </div>
                    <div class="ma-cal-days">
                        ${cellsHtml}
                    </div>
                </div>
                <div class="ma-chart-tooltip ma-cal-tooltip" id="ma-cal-tooltip" hidden></div>
            </div>`;
    }

    function bindMilestones(item) {
        const root = document.getElementById('ma-milestones-calendar');
        if (!root) return;
        const tooltip = root.querySelector('#ma-cal-tooltip');
        if (!tooltip) return;

        const show = (btn) => {
            const dateStr = btn.dataset.calDate;
            if (!dateStr) return;
            const hasData = btn.dataset.calHasdata === '1';
            const plnStr = btn.dataset.calPln;
            const pctStr = btn.dataset.calPct;
            const isAth = btn.dataset.calAth === '1';
            const isBest = btn.dataset.calBest === '1';
            const isWorst = btn.dataset.calWorst === '1';

            const [y, m, d] = dateStr.split('-').map(Number);
            const dateObj = new Date(y, m - 1, d);
            const formattedDate = dateObj.toLocaleDateString('en-GB', {
                weekday: 'short',
                day: 'numeric',
                month: 'short',
                year: 'numeric',
            });

            let returnHtml = '';
            if (hasData && plnStr !== '') {
                const pln = Number(plnStr);
                const pct = pctStr !== '' ? Number(pctStr) : null;
                const pctFormatted = pct != null ? ` (${formatPct(pct, true)})` : '';
                const valTone = pln > 0.005 ? 'is-positive' : (pln < -0.005 ? 'is-negative' : 'is-neutral');

                returnHtml = `
                    <div class="ma-tooltip-row">
                        <span class="ma-tooltip-key">Daily return</span>
                        <strong class="ma-tooltip-val ${valTone}">${formatPLN2(pln, true)}${pctFormatted}</strong>
                    </div>`;
            } else {
                returnHtml = `
                    <div class="ma-tooltip-row">
                        <span class="ma-tooltip-key" style="color:var(--ma-muted); font-style:italic;">No trading activity</span>
                    </div>`;
            }

            let badgesHtml = '';
            if (isAth) {
                badgesHtml += `<div class="ma-cal-tooltip-badge is-ath">🏆 All-Time High</div>`;
            }
            if (isBest) {
                badgesHtml += `<div class="ma-cal-tooltip-badge is-best">🌟 Best Day of Month</div>`;
            }
            if (isWorst) {
                badgesHtml += `<div class="ma-cal-tooltip-badge is-worst">🔻 Worst Day of Month</div>`;
            }

            tooltip.innerHTML = `
                <div class="ma-tooltip-date">${escapeHtml(formattedDate)}</div>
                <div class="ma-tooltip-body">
                    ${returnHtml}
                    ${badgesHtml ? `<div class="ma-cal-tooltip-badges">${badgesHtml}</div>` : ''}
                </div>`;

            tooltip.hidden = false;

            const rootRect = root.getBoundingClientRect();
            const btnRect = btn.getBoundingClientRect();
            const tipWidth = tooltip.offsetWidth || 190;
            const tipHeight = tooltip.offsetHeight || 64;

            let left = (btnRect.left + btnRect.width / 2) - rootRect.left - (tipWidth / 2);
            if (left < 4) left = 4;
            if (left + tipWidth > rootRect.width - 4) {
                left = Math.max(4, rootRect.width - tipWidth - 4);
            }

            let top = (btnRect.top - rootRect.top) - tipHeight - 8;
            if (top < 0) {
                top = (btnRect.bottom - rootRect.top) + 8;
            }

            tooltip.style.left = `${Math.round(left)}px`;
            tooltip.style.top = `${Math.round(top)}px`;
            tooltip.style.transform = 'none';
        };

        const hide = () => {
            tooltip.hidden = true;
        };

        root.querySelectorAll('.ma-cal-day:not(.is-empty)').forEach(btn => {
            btn.addEventListener('mouseenter', () => show(btn));
            btn.addEventListener('focus', () => show(btn));
            btn.addEventListener('mouseleave', hide);
            btn.addEventListener('blur', hide);
            btn.addEventListener('touchstart', () => {
                show(btn);
            }, { passive: true });
        });

        root.addEventListener('mouseleave', hide);
    }

    function extremesCard(item) {
        const athValue = item.is_new_ath ? formatPLN(item.ath_value_pln) : 'No new ATH';
        const athDetail = item.is_new_ath ? `${formatDate(item.ath_date)} · new peak` : 'Peak was not exceeded';
        const body = `
            <div class="monthly-audit-stats-grid">
                ${stat('ATH status', athValue, athDetail, item.is_new_ath ? 'is-ath' : '')}
                ${stat('Days since ATH', item.days_since_ath == null ? 'No data' : `${number(item.days_since_ath)} days`, 'State at month end')}
                ${stat('Best day', formatPLN(item.best_day?.change_pln, true), formatDate(item.best_day?.date), 'is-positive')}
                ${stat('Worst day', formatPLN(item.worst_day?.change_pln), formatDate(item.worst_day?.date), 'is-negative')}
            </div>
            ${monthCalendarWidget(item)}`;
        return card('Moments that mattered.', 'The milestones', body, 'ma-milestones');
    }

    const MARKET_BENCHMARK_IDS = ['WIG', 'DAX', 'FTSE100', 'SP500', 'NASDAQ', 'MSCI_WORLD'];
    const _benchmarkReturns = {};
    let _benchmarkReturnsLoading = false;
    let _benchmarkReturnsLoaded = false;
    let _benchmarkReturnsPromise = null;

    function resolveMarketReturn(item, marketId) {
        const markets = Array.isArray(item?.market_context) ? item.market_context : [];
        const market = markets.find(entry => entry?.id === marketId);
        if (finite(market?.return_pct)) {
            return number(market.return_pct);
        }
        const ym = item?.period;
        if (ym && _benchmarkReturns[marketId] && finite(_benchmarkReturns[marketId][ym])) {
            return _benchmarkReturns[marketId][ym];
        }
        return null;
    }

    function globalMarketVerdict(item) {
        if (!item || !finite(item.overall_twr_pct)) return null;
        const userReturn = number(item.overall_twr_pct);
        const msciReturn = resolveMarketReturn(item, 'MSCI_WORLD');
        if (!finite(msciReturn)) return null;

        const msci = number(msciReturn);
        const delta = userReturn - msci;
        const absDiff = Math.abs(delta);
        const diffStr = `${absDiff.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} pp`;

        if (absDiff < 0.05) {
            return {
                status: 'Matched global market',
                tone: 'is-neutral',
                text: 'You matched the global market — pacing neck and neck with the MSCI World benchmark.',
            };
        }

        if (delta > 0) {
            const detail = userReturn >= 0 && msci < 0
                ? `You were better than the global market — staying positive while the MSCI World slipped (+${diffStr} alpha).`
                : userReturn < 0
                ? `You were better than the global market — weathering the drop better than the MSCI World (+${diffStr} cushion).`
                : `You were better than the global market — beating the MSCI World by +${diffStr} this month.`;
            return {
                status: 'Better than global market',
                tone: 'is-positive',
                text: detail,
            };
        }

        const detail = userReturn < 0 && msci >= 0
            ? `You were behind the global market — the MSCI World held positive territory by ${diffStr}.`
            : userReturn >= 0
            ? `You were behind the global market — a positive run, but the MSCI World set a faster pace by ${diffStr}.`
            : `You were behind the global market — the market pullback weighed on you more than the MSCI World by ${diffStr}.`;
        return {
            status: 'Behind global market',
            tone: 'is-caution',
            text: detail,
        };
    }

    function updateMarketContextDom() {
        const item = state.items.get(state.selectedPeriod);
        if (!item) return;
        const rows = document.querySelectorAll('.ma-ticker-item[data-market-id], .ma-market-row[data-market-id]');
        rows.forEach(row => {
            const id = row.getAttribute('data-market-id');
            const valEl = row.querySelector('.ma-ticker-val') || row.querySelector('div > b') || row.querySelector('b, strong');
            if (!valEl) return;
            const currentVal = resolveMarketReturn(item, id);
            valEl.className = valEl.classList.contains('ma-ticker-val') ? `ma-ticker-val ${tone(currentVal)}` : tone(currentVal);
            valEl.textContent = formatPct(currentVal, true);
        });
        const verdictEl = document.getElementById('ma-global-market-verdict');
        if (verdictEl) {
            const verdict = globalMarketVerdict(item);
            if (verdict) {
                verdictEl.className = `ma-market-verdict ${verdict.tone}`;
                verdictEl.hidden = false;
                verdictEl.innerHTML = `<span class="ma-verdict-badge">${escapeHtml(verdict.status)}</span><span class="ma-verdict-copy">${escapeHtml(verdict.text)}</span>`;
            } else {
                verdictEl.hidden = true;
            }
        }
        const heroWig = document.getElementById('ma-hero-benchmark-wig');
        if (heroWig) {
            const wigVal = resolveMarketReturn(item, 'WIG');
            heroWig.className = `ma-hero-benchmark-val ${tone(wigVal)}`;
            heroWig.textContent = formatPct(wigVal, true);
        }
        const heroMsci = document.getElementById('ma-hero-benchmark-msci');
        if (heroMsci) {
            const msciVal = resolveMarketReturn(item, 'MSCI_WORLD');
            heroMsci.className = `ma-hero-benchmark-val ${tone(msciVal)}`;
            heroMsci.textContent = formatPct(msciVal, true);
        }
    }

    async function loadAllBenchmarkMonthlyReturns(force = false) {
        if (_benchmarkReturnsLoaded && !force) return _benchmarkReturns;
        if (_benchmarkReturnsPromise && !force) return _benchmarkReturnsPromise;
        if (!window.PortfolioClient || !window.PortfolioClient.getBenchmarkReturns) return _benchmarkReturns;

        _benchmarkReturnsLoading = true;
        _benchmarkReturnsPromise = Promise.all(
            MARKET_BENCHMARK_IDS.map(async bid => {
                try {
                    const data = await window.PortfolioClient.getBenchmarkReturns(bid, '2010-01');
                    const returns = Array.isArray(data?.returns) ? data.returns : [];
                    const map = _benchmarkReturns[bid] || {};
                    for (const r of returns) {
                        const m = String(r?.month || '');
                        const val = Number(r?.returnPct);
                        if (m && Number.isFinite(val)) {
                            map[m] = val;
                        }
                    }
                    _benchmarkReturns[bid] = map;
                } catch (err) {
                    console.warn(`[monthly-audit] Failed to fetch benchmark returns for ${bid}:`, err);
                }
            })
        ).then(() => {
            _benchmarkReturnsLoaded = true;
            _benchmarkReturnsLoading = false;
            _benchmarkReturnsPromise = null;
            updateMarketContextDom();
            return _benchmarkReturns;
        }).catch(() => {
            _benchmarkReturnsLoading = false;
            _benchmarkReturnsPromise = null;
            return _benchmarkReturns;
        });

        return _benchmarkReturnsPromise;
    }

    function marketContext(item) {
        const tickers = [
            ['WIG', 'WIG'], ['DAX', 'DAX'], ['FTSE100', 'FTSE 100'],
            ['SP500', 'S&P 500'], ['NASDAQ', 'NASDAQ'], ['MSCI_WORLD', 'MSCI World'],
        ];
        const verdict = globalMarketVerdict(item);
        const verdictHtml = verdict ? `
            <div class="ma-market-verdict ${verdict.tone}" id="ma-global-market-verdict" role="status">
                <span class="ma-verdict-badge">${escapeHtml(verdict.status)}</span>
                <span class="ma-verdict-copy">${escapeHtml(verdict.text)}</span>
            </div>` : '<div class="ma-market-verdict is-pending" id="ma-global-market-verdict" hidden></div>';

        return `<div class="ma-market-portfolio">
                ${metric('Your portfolio · monthly TWR', formatPct(item.overall_twr_pct, true), tone(item.overall_twr_pct))}
                ${verdictHtml}
            </div>
            <div class="ma-ticker-strip">${tickers.map(([id, label]) => {
                const returnVal = resolveMarketReturn(item, id);
                return `<div class="ma-ticker-item ma-market-row" data-market-id="${id}"><span class="ma-ticker-label">${label}</span><b class="ma-ticker-val ${tone(returnVal)}">${escapeHtml(formatPct(returnVal, true))}</b></div>`;
            }).join('')}</div><p class="ma-footnote">Calendar close-to-close, native currencies (not PLN-adjusted); dates may differ from portfolio TWR. MSCI World uses a proxy.</p>`;
    }

    function seasonalityCard(item) {
        const count = number(item.historical_years_count);
        const negatives = number(item.negative_years_count);
        const positives = number(item.positive_years_count);
        const monthName = MONTHS[Number(item.period.slice(5)) - 1] || 'This month';
        const historyText = count
            ? `${monthName} was negative in ${negatives} out of the last ${count} observations (avg ${formatPct(item.avg_negative_pct)}) and positive in ${positives} (avg ${formatPct(item.avg_positive_pct, true)}).`
            : `This is the first fully audited ${monthName.toLowerCase()}. Seasonality starts from this result.`;
        const outperformed = Boolean(item.outperformed_seasonal_history);
        const status = count
            ? (outperformed ? 'Current result beat seasonal history' : 'Current result did not beat seasonal history')
            : 'Not enough data for seasonal comparison';
        const body = `${marketContext(item)}
            <h3 class="ma-section-title">Seasonality · ${escapeHtml(monthName)}</h3>
            <div class="monthly-audit-seasonality">
                <div class="monthly-audit-season-bars" aria-hidden="true">
                    <span class="negative" style="--share:${count ? (negatives / count) * 100 : 0}%"></span>
                    <span class="positive" style="--share:${count ? (positives / count) * 100 : 0}%"></span>
                </div>
                <p>${escapeHtml(historyText)}</p>
                <div class="monthly-audit-status ${outperformed ? 'is-positive' : 'is-caution'}">
                    <span>${outperformed ? 'Trend broken' : 'Seasonality test'}</span>
                    <strong>${escapeHtml(status)}</strong>
                </div>
            </div>`;
        return card('A little perspective.', 'The bigger picture', body, 'ma-seasonality');
    }

    function retirementCard(item) {
        const target = item.retirement_target || {};
        const gains = item.avco_gains || {};
        const goal = target.monthly_target_nominal_pln;
        const actual = target.actual_nominal_gain_pln;
        const hasGoal = finite(goal) && number(goal) > 0;
        const hasActual = finite(actual);
        const achieved = hasGoal && hasActual ? number(actual) / number(goal) * 100 : null;
        const scale = Math.max(number(goal), Math.abs(number(actual)), 1);
        // Positive outcomes use 0..scale; losses use -scale..+scale on ONE track.
        const minimum = number(actual) < 0 ? -scale : 0;
        const position = value => (number(value) - minimum) / (scale - minimum) * 100;
        const zero = position(0), actualPosition = position(actual);
        const body = `
            <div class="monthly-audit-retirement">
                <strong class="ma-target-percent">${achieved === null ? 'No data' : `${Math.round(achieved).toLocaleString('en-GB')}%`}</strong>
                <div class="monthly-audit-retirement-copy">
                    <span>Monthly target progress</span>
                    <strong>${escapeHtml(formatPLN(target.actual_nominal_gain_pln, true))} <small>of ${escapeHtml(formatPLN(target.monthly_target_nominal_pln))}</small></strong>
                    ${hasGoal && hasActual ? `<div class="ma-target-track" role="img" aria-label="Actual ${escapeHtml(formatPLN(actual, true))}; target ${escapeHtml(formatPLN(goal))}. Shared scale ${escapeHtml(formatPLN(minimum))} to ${escapeHtml(formatPLN(scale))}.">
                        <span class="ma-target-fill ${tone(actual)}" style="left:${Math.min(zero, actualPosition)}%;width:${Math.abs(actualPosition - zero)}%"></span><i class="ma-track-zero" style="left:${zero}%"></i><i class="ma-target-marker" style="left:${position(goal)}%" title="Target ${escapeHtml(formatPLN(goal))}"></i></div>
                        <div class="ma-scale-labels"><span>${escapeHtml(formatPLN(minimum))}</span><span>${escapeHtml(formatPLN(scale, true))}</span></div><p class="ma-footnote">│ Target ${escapeHtml(formatPLN(goal))} · one shared PLN scale; losses extend left of zero.</p>` : '<p class="ma-muted">Target progress unavailable without both target and actual gain.</p>'}
                </div>
            </div>
            <details class="ma-details"><summary>View gains · AVCO</summary><div class="monthly-audit-gains-grid">
                <div><span>Unrealized gains</span><strong class="${tone(gains.unrealized_pln)}">${escapeHtml(formatPLN(gains.unrealized_pln, true))}</strong><small>Open positions</small></div>
                <div><span>Realized gains</span><strong class="${tone(gains.realized_pln)}">${escapeHtml(formatPLN(gains.realized_pln, true))}</strong><small>Monthly sells · AVCO</small></div>
            </div></details>`;
        return card('The bigger goal.', 'Target & AVCO', target.plan_id == null && !hasGoal
            ? `<p class="ma-muted">No monthly target configured.</p>${body.slice(body.indexOf('<details'))}` : body, 'ma-goal');
    }

    function contributionPanel(kind, asset, scale, monthTotal) {
        const isCarry = kind === 'carry';
        const available = finite(asset?.net_contribution_pln);
        const value = number(asset?.net_contribution_pln);
        const endpoint = 50 + value / scale * 50;
        return `
            <div class="monthly-audit-contribution ${kind}">
                <span>${isCarry ? '▲ Leader' : '▼ Anchor'}</span>
                <div><strong>${escapeHtml(asset?.ticker || asset?.name || 'No data')}</strong><b class="${tone(value)}">${escapeHtml(formatPLN(asset?.net_contribution_pln, true))}</b></div>
                <div class="ma-contribution-track" role="img" aria-label="${escapeHtml(isCarry ? 'Leader' : 'Anchor')}: ${escapeHtml(formatPLN(asset?.net_contribution_pln, true))}. Shared axis minus ${scale} to plus ${scale} PLN; zero in the centre.">
                    ${available ? `<span class="ma-contribution-fill ${tone(value)}" style="left:${Math.min(50, endpoint)}%;width:${Math.abs(value) / scale * 50}%"></span>` : ''}<i class="ma-track-zero" style="left:50%"></i>
                    ${finite(monthTotal) ? `<i class="ma-month-marker" style="left:${50 + number(monthTotal) / scale * 50}%" title="Month total ${escapeHtml(formatPLN(monthTotal, true))}"></i>` : ''}</div>
                <p>${escapeHtml(asset?.context_note || (available ? 'Net contribution in PLN.' : 'Contribution unavailable.'))}</p>
            </div>`;
    }

    function carryCard(item) {
        const monthTotal = item.overall_nominal_change_pln;
        const scale = Math.max(Math.abs(number(monthTotal)), Math.abs(number(item.carry?.net_contribution_pln)), Math.abs(number(item.anchor?.net_contribution_pln)), 1);
        const body = `<p class="ma-month-reference">┆ Month total · ${escapeHtml(formatPLN(monthTotal, true))}</p><div class="monthly-audit-contributions">${contributionPanel('carry', item.carry, scale, monthTotal)}${contributionPanel('anchor', item.anchor, scale, monthTotal)}</div>
            <div class="ma-scale-labels"><span>${escapeHtml(formatPLN(-scale))}</span><span>0 PLN</span><span>${escapeHtml(formatPLN(scale, true))}</span></div>
            <p class="ma-footnote">Common symmetric PLN scale · same zero and scale in both rows. Dashed marker = month total, net of cash flows. Full extent is the larger of the absolute month total and either contribution (minimum 1 PLN), not necessarily the month total. Contributions can exceed the net month when other positions offset them.</p>`;
        return card('Who moved your month?', 'The movers', body, 'ma-movers');
    }

    function tradingCard(item) {
        const activity = item.trading_activity || {};
        const transactions = Array.isArray(activity.largest_transactions) ? activity.largest_transactions : [];
        const body = `
            <div class="ma-trading-metrics">
                ${metric('Turnover · BUY + SELL', formatPLN(activity.turnover_pln))}
                ${metric('BUY total', formatPLN(activity.buy_total_pln))}
                ${metric('SELL total', formatPLN(activity.sell_total_pln))}
                ${metric('BUY / SELL transactions', finite(activity.transaction_count) ? number(activity.transaction_count).toLocaleString('en-GB') : 'No data')}
                ${finite(activity.dividend_total_pln) && number(activity.dividend_total_pln) !== 0 ? metric('Dividends received', formatPLN(activity.dividend_total_pln, true)) : ''}
            </div>
            ${!finite(activity.dividend_total_pln) ? '<p class="ma-muted">Dividend data unavailable.</p>' : ''}
            <h3 class="ma-section-title">Largest transactions</h3>
            ${transactions.length ? `<ol class="ma-transactions">${transactions.map(transaction => `<li><time>${escapeHtml(storedDate(transaction.date))}</time><span class="ma-trade-type">${escapeHtml(['BUY', 'SELL'].includes(transaction.type) ? transaction.type : 'No data')}</span><strong>${escapeHtml(transaction.ticker || 'No data')}</strong><b>${escapeHtml(formatPLN(transaction.value_pln))}</b></li>`).join('')}</ol>` : `<p class="ma-muted">${finite(activity.transaction_count) && number(activity.transaction_count) === 0 ? 'No BUY or SELL transactions this month.' : 'Transaction details unavailable.'}</p>`}
            <p class="ma-footnote">Settled transaction values in PLN. Turnover is trading volume, not investment return; dividends are separate.</p>`;
        return card('What changed hands.', 'Trading activity', body, 'ma-trading');
    }

    function renderReport() {
        const root = document.getElementById('monthly-audit-root');
        if (!root) return;
        const item = state.items.get(state.selectedPeriod);
        const periodTitle = window.MonthlyAuditPresentation.periodTitle(state.selectedPeriod);
        const isReady = item && !item._isLiveStub;
        const wigReturn = isReady ? resolveMarketReturn(item, 'WIG') : null;
        const msciReturn = isReady ? resolveMarketReturn(item, 'MSCI_WORLD') : null;
        root.innerHTML = `
            ${timelineMarkup()}
            ${isReady ? `<header class="monthly-audit-hero ${tone(item.overall_twr_pct)}">
                <div class="ma-cover-top"><div class="ma-cover-brand"><span class="ma-wordmark">roastfolio</span><span class="ma-cover-edition">MONTHLY AUDIT</span></div><button type="button" class="ma-share-button" onclick="shareMonthlyAudit()"><span aria-hidden="true">↗</span> Share recap</button></div>
                <h1>${escapeHtml(periodTitle)}<br><em>${item.is_live ? 'Live MTD.' : 'Wrapped.'}</em></h1>
                <p class="ma-cover-story">${escapeHtml(window.MonthlyAuditPresentation.headline(item))}</p>
                <div class="monthly-audit-hero-bottom">
                    <div class="monthly-audit-hero-metrics">
                        <div class="monthly-audit-hero-result ma-twr"><strong>${escapeHtml(formatPct(item.overall_twr_pct, true))}</strong><span>TWR result</span></div>
                        <div class="monthly-audit-hero-result ma-nominal"><strong>${escapeHtml(formatPLN(item.overall_nominal_change_pln, true))}</strong><span>Nominal change · net of cash flows</span></div>
                    </div>
                    <div class="ma-hero-benchmarks" id="ma-hero-benchmarks" aria-label="Key monthly benchmarks">
                        <span class="ma-hero-benchmarks-title">BENCHMARKS</span>
                        <div class="ma-hero-benchmarks-grid">
                            <div class="ma-hero-benchmark-row">
                                <span class="ma-hero-benchmark-label">Poland (WIG)</span>
                                <strong class="ma-hero-benchmark-val ${tone(wigReturn)}" id="ma-hero-benchmark-wig">${escapeHtml(formatPct(wigReturn, true))}</strong>
                            </div>
                            <div class="ma-hero-benchmark-row">
                                <span class="ma-hero-benchmark-label">World (MSCI ACWI)</span>
                                <strong class="ma-hero-benchmark-val ${tone(msciReturn)}" id="ma-hero-benchmark-msci">${escapeHtml(formatPct(msciReturn, true))}</strong>
                            </div>
                        </div>
                    </div>
                </div>
            </header>` : ''}
            <div class="monthly-audit-content">
                ${isReady ? [journeyCard(item), extremesCard(item), carryCard(item), retirementCard(item), seasonalityCard(item), flowsCard(item), tradingCard(item)].join('') : renderEmpty(state.selectedPeriod)}
            </div><p class="ma-footer">${item?.is_live ? 'Month to date (Live). Not investment advice.' : 'A month in perspective. Not investment advice.'}</p>`;
        if (isReady) {
            bindJourney(item);
            bindMilestones(item);
        }
    }

    window.shareMonthlyAudit = () => {
        const item = state.items.get(state.selectedPeriod);
        if (item) {
            item._heroBenchmarks = {
                wig: resolveMarketReturn(item, 'WIG'),
                msci: resolveMarketReturn(item, 'MSCI_WORLD'),
            };
            window.MonthlyAuditShare.open(item, {
                onEmail: (emailOpts) => sendRecapEmail(item.period, emailOpts),
            });
        }
    };

    async function loadPeriod(period) {
        const item = state.items.get(period);
        if (item && !item._isLiveStub && !isCurrentMonth(period)) return item;
        try {
            const payload = await fetchJson(`/monthly-wraps?period=${encodeURIComponent(period)}`);
            if (payload.item) ingestItems([payload.item]);
        } catch (error) {
            if (error.status !== 404) throw error;
        }
        return state.items.get(period) || null;
    }

    window.selectMonthlyAuditPeriod = async period => {
        if (!/^\d{4}-\d{2}$/.test(period)) return;
        state.selectedPeriod = period;
        state.selectedYear = Number(period.slice(0, 4));
        renderReport();
        try {
            await loadPeriod(period);
            if (state.selectedPeriod === period) renderReport();
        } catch (error) {
            if (state.selectedPeriod === period) renderError(error.message);
        }
        document.querySelector('#monthly-audit-root select')?.focus({ preventScroll: true });
    };

    window.shiftMonthlyAuditYear = direction => {
        const nextYear = state.selectedYear + Number(direction || 0);
        const currentYear = new Date().getFullYear();
        if (nextYear > currentYear) return;
        state.selectedYear = nextYear;
        renderReport();
    };

    window.initMonthlyAudit = async force => {
        if (state.loading || (state.initialized && !force)) {
            loadAllBenchmarkMonthlyReturns();
            return;
        }
        state.loading = true;
        renderLoading();
        try {
            const localItems = window.MONTHLY_WRAP_DATA;
            if (Array.isArray(localItems) && localItems.length) {
                ingestItems(localItems);
            } else {
                const payload = await fetchJson('/monthly-wraps');
                ingestItems(payload.items || []);
            }
            const latest = [...state.items.keys()].sort().pop();
            state.initialized = true;
            await window.selectMonthlyAuditPeriod(latest || latestExpectedPeriod());
        } catch (error) {
            renderError(error.message);
        } finally {
            state.loading = false;
        }
        loadAllBenchmarkMonthlyReturns();
    };

    window.setHistorySection = section => {
        const showRecaps = section === 'recaps';
        const overview = document.getElementById('history-overview-view');
        const recaps = document.getElementById('history-recaps-view');
        if (overview) overview.hidden = showRecaps;
        if (recaps) recaps.hidden = !showRecaps;
        document.querySelectorAll('[data-history-section]').forEach(button => {
            const active = button.dataset.historySection === section;
            button.classList.toggle('is-active', active);
            button.setAttribute('aria-selected', String(active));
        });
        if (showRecaps) {
            window.initMonthlyAudit(false);
            loadAllBenchmarkMonthlyReturns();
        }
    };

    window.loadMonthlyAuditBenchmarkReturns = loadAllBenchmarkMonthlyReturns;
    window._monthlyAuditBenchmarkReturns = _benchmarkReturns;
    window.globalMarketVerdict = globalMarketVerdict;
})();