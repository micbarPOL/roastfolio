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

    const formatPLN = (value, showSign = false) => {
        const amount = number(value);
        const rounded = Math.round(amount);
        const sign = rounded < 0 ? '-' : showSign && rounded > 0 ? '+' : '';
        const grouped = Math.abs(rounded).toLocaleString('en-GB');
        return `${sign}${grouped} PLN`;
    };

    const formatPct = (value, showSign = false) => {
        const amount = number(value);
        const sign = showSign && amount > 0 ? '+' : '';
        return `${sign}${amount.toLocaleString('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 2 })}%`;
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

    function ingestItems(items) {
        (Array.isArray(items) ? items : []).forEach(item => {
            const period = String(item?.period || item?.SK?.replace('WRAP#MONTH#', '') || '');
            if (/^\d{4}-\d{2}$/.test(period)) state.items.set(period, { ...item, period });
        });
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
        return `
            <div class="monthly-audit-state monthly-audit-empty">
                <span class="monthly-audit-empty-mark" aria-hidden="true">0</span>
                <strong>No audit for ${escapeHtml(period)}</strong>
                <span>This summary appears after month close.</span>
            </div>`;
    }

    function timelineMarkup() {
        const year = state.selectedYear;
        const now = new Date();
        const monthButtons = MONTHS.map((name, index) => {
            const period = `${year}-${String(index + 1).padStart(2, '0')}`;
            const selected = period === state.selectedPeriod;
            const available = state.items.has(period);
            const future = year > now.getFullYear() || (year === now.getFullYear() && index > now.getMonth());
            return `
                <button type="button" class="monthly-audit-month${selected ? ' is-active' : ''}${available ? ' has-report' : ''}"
                    data-period="${period}" aria-pressed="${selected}" ${future ? 'disabled' : ''}
                    onclick="selectMonthlyAuditPeriod('${period}')">${escapeHtml(name)}</button>`;
        }).join('');
        return `
            <div class="monthly-audit-timeline-wrap">
                <div class="monthly-audit-timeline-label">Timeline</div>
                <div class="monthly-audit-timeline" role="navigation" aria-label="Audit months">
                    <div class="monthly-audit-year-control">
                        <button type="button" aria-label="Previous year" onclick="shiftMonthlyAuditYear(-1)">‹</button>
                        <strong>[ ${year} ]</strong>
                        <button type="button" aria-label="Next year" onclick="shiftMonthlyAuditYear(1)">›</button>
                    </div>
                    <div class="monthly-audit-months">${monthButtons}</div>
                </div>
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

    function trajectoryVisual(start, end) {
        const startDepth = Math.abs(number(start));
        const endDepth = Math.abs(number(end));
        const scale = Math.max(startDepth, endDepth, 1);
        const startY = 8 + (startDepth / scale) * 28;
        const endY = 8 + (endDepth / scale) * 28;
        const line = `M4 ${startY} C38 ${startY}, 78 ${endY}, 116 ${endY}`;
        return `
            <svg class="monthly-audit-trajectory" viewBox="0 0 120 44" aria-hidden="true">
                <path class="trajectory-baseline" d="M4 5 H116" />
                <path class="trajectory-lake" d="M4 5 L4 ${startY} C38 ${startY}, 78 ${endY}, 116 ${endY} L116 5 Z" />
                <path class="trajectory-line" d="${line}" />
                <circle cx="4" cy="${startY}" r="2.5"/><circle cx="116" cy="${endY}" r="2.5"/>
            </svg>`;
    }

    function progressRing(percent) {
        const clamped = Math.max(0, Math.min(100, number(percent)));
        const rounded = Math.round(number(percent));
        const circumference = 175.93;
        const offset = circumference * (1 - clamped / 100);
        return `
            <div class="monthly-audit-ring-stack">
                <strong>${escapeHtml(`${rounded.toLocaleString('en-GB')}%`)}</strong>
                <div class="monthly-audit-ring" style="--ring-offset:${offset}">
                    <svg viewBox="0 0 72 72" aria-hidden="true">
                        <circle class="ring-track" cx="36" cy="36" r="28"/>
                        <circle class="ring-progress" cx="36" cy="36" r="28"/>
                    </svg>
                </div>
            </div>`;
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
                ${metric('Nominal change', formatPLN(item.overall_nominal_change_pln, true), tone(item.overall_nominal_change_pln))}
                ${metric('Portfolio TWR', formatPct(item.overall_twr_pct, true), tone(item.overall_twr_pct))}
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
            </div>`;
        return card('Cash Flows and Portfolio Performance', 'Reconciliation', body);
    }

    function extremesCard(item) {
        const athValue = item.is_new_ath ? formatPLN(item.ath_value_pln) : 'No new ATH';
        const athDetail = item.is_new_ath ? `${formatDate(item.ath_date)} · new peak` : 'Peak was not exceeded';
        const delta = number(item.trajectory_delta_pp);
        const body = `
            <div class="monthly-audit-stats-grid">
                ${stat('ATH status', athValue, athDetail, item.is_new_ath ? 'is-ath' : '')}
                ${stat('Days since ATH', item.days_since_ath == null ? 'No data' : `${number(item.days_since_ath)} days`, 'State at month end')}
                ${stat('Max drawdown', formatPct(item.max_drawdown_pct), formatDate(item.max_drawdown_date), 'is-danger')}
                ${stat('Drawdown trajectory', `${formatPct(item.start_drawdown_pct)} → ${formatPct(item.end_drawdown_pct)}`, `${delta > 0 ? '+' : ''}${delta.toLocaleString('en-GB', { maximumFractionDigits: 2 })} pp`, tone(delta), trajectoryVisual(item.start_drawdown_pct, item.end_drawdown_pct))}
                ${stat('Best day', formatPLN(item.best_day?.change_pln, true), formatDate(item.best_day?.date), 'is-positive')}
                ${stat('Worst day', formatPLN(item.worst_day?.change_pln), formatDate(item.worst_day?.date), 'is-negative')}
            </div>`;
        return card('Monthly Statistics and Extremes', 'Turning Points', body);
    }

    function seasonalityCard(item) {
        const count = number(item.historical_years_count);
        const negatives = number(item.negative_years_count);
        const positives = number(item.positive_years_count);
        const monthName = MONTHS[Math.max(0, number(item.month) - 1)];
        const historyText = count
            ? `${monthName} was negative in ${negatives} out of the last ${count} observations (avg ${formatPct(item.avg_negative_pct)}) and positive in ${positives} (avg ${formatPct(item.avg_positive_pct, true)}).`
            : `This is the first fully audited ${monthName.toLowerCase()}. Seasonality starts from this result.`;
        const outperformed = Boolean(item.outperformed_seasonal_history);
        const status = count
            ? (outperformed ? 'Current result beat seasonal history' : 'Current result did not beat seasonal history')
            : 'Not enough data for seasonal comparison';
        const body = `
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
        return card('Historical Context and Seasonality', 'Market Memory', body);
    }

    function retirementCard(item) {
        const target = item.retirement_target || {};
        const gains = item.avco_gains || {};
        const achieved = number(target.pct_achieved);
        const width = Math.max(0, Math.min(100, achieved));
        const body = `
            <div class="monthly-audit-retirement">
                ${progressRing(achieved)}
                <div class="monthly-audit-retirement-copy">
                    <span>Monthly target progress</span>
                    <strong>${escapeHtml(formatPLN(target.actual_nominal_gain_pln, true))} <small>of ${escapeHtml(formatPLN(target.monthly_target_nominal_pln))}</small></strong>
                    <div class="monthly-audit-progress"><span style="width:${width}%"></span></div>
                </div>
            </div>
            <div class="monthly-audit-gains-grid">
                <div><span>Unrealized gains</span><strong class="${tone(gains.unrealized_pln)}">${escapeHtml(formatPLN(gains.unrealized_pln, true))}</strong><small>Open positions</small></div>
                <div><span>Realized gains</span><strong class="${tone(gains.realized_pln)}">${escapeHtml(formatPLN(gains.realized_pln, true))}</strong><small>Monthly sells · AVCO</small></div>
            </div>`;
        return card('Retirement Plan and Gains', 'Target and AVCO', body);
    }

    function contributionPanel(kind, asset) {
        const isCarry = kind === 'carry';
        if (!asset) {
            return `<div class="monthly-audit-contribution ${kind}"><span>${isCarry ? '▲ Leader' : '▼ Anchor'}</span><strong>No data</strong><p>No assets available for comparison.</p></div>`;
        }
        return `
            <div class="monthly-audit-contribution ${kind}">
                <span>${isCarry ? '▲ Leader' : '▼ Anchor'}</span>
                <div><strong>${escapeHtml(asset.ticker || asset.name)}</strong><b class="${tone(asset.net_contribution_pln)}">${escapeHtml(formatPLN(asset.net_contribution_pln, true))}</b></div>
                <p>${escapeHtml(asset.context_note || 'Pure price move, no transactions')}</p>
            </div>`;
    }

    function carryCard(item) {
        const body = `<div class="monthly-audit-contributions">${contributionPanel('carry', item.carry)}${contributionPanel('anchor', item.anchor)}</div>`;
        return card('Monthly Leader and Anchor', 'Net Contribution', body);
    }

    function diaryCard(item) {
        const audit = item.coping_diary_audit || {};
        const body = `
            <div class="monthly-audit-diary-summary">
                ${metric('Entries this month', String(number(audit.current_month_entries)))}
                ${metric('3-month average', number(audit.three_month_avg_entries).toLocaleString('en-GB', { maximumFractionDigits: 1 }))}
            </div>
            ${audit.activity_dropped_warning ? '<div class="monthly-audit-warning">The portfolio will not discipline itself. Your journaling frequency dropped.</div>' : ''}
            <div class="monthly-audit-checkpoints">
                <div class="verified"><strong>${number(audit.checkpoints_true)}</strong><span>TRUE · validated</span></div>
                <div class="falsified"><strong>${number(audit.checkpoints_false)}</strong><span>FALSE · invalidated</span></div>
                <div class="overdue"><strong>${number(audit.checkpoints_overdue)}</strong><span>OVERDUE · pending</span></div>
            </div>`;
        return card('Coping Diary Audit and Activity', 'Process Discipline', body);
    }

    function renderReport() {
        const root = document.getElementById('monthly-audit-root');
        if (!root) return;
        const item = state.items.get(state.selectedPeriod);
        const periodTitle = state.selectedPeriod && /^\d{4}-\d{2}$/.test(state.selectedPeriod)
            ? `${MONTHS[Number(state.selectedPeriod.slice(5)) - 1]} ${state.selectedPeriod.slice(0, 4)}`
            : 'Monthly audit';
        root.innerHTML = `
            ${timelineMarkup()}
            <header class="monthly-audit-hero">
                <div><span>Monthly audit</span><h1>${escapeHtml(periodTitle)}</h1></div>
                ${item ? `<div class="monthly-audit-hero-result ${tone(item.overall_twr_pct)}"><span>TWR result</span><strong>${escapeHtml(formatPct(item.overall_twr_pct, true))}</strong></div>` : ''}
            </header>
            <div class="monthly-audit-content">
                ${item ? [flowsCard(item), extremesCard(item), seasonalityCard(item), retirementCard(item), carryCard(item), diaryCard(item)].join('') : renderEmpty(state.selectedPeriod)}
            </div>`;
        requestAnimationFrame(() => root.querySelector('.monthly-audit-month.is-active')?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' }));
    }

    async function loadPeriod(period) {
        if (state.items.has(period)) return state.items.get(period);
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
            renderReport();
        } catch (error) {
            renderError(error.message);
        }
    };

    window.shiftMonthlyAuditYear = direction => {
        const nextYear = state.selectedYear + Number(direction || 0);
        const currentYear = new Date().getFullYear();
        if (nextYear > currentYear) return;
        state.selectedYear = nextYear;
        renderReport();
    };

    window.initMonthlyAudit = async force => {
        if (state.loading || (state.initialized && !force)) return;
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
            state.selectedPeriod = latest || latestExpectedPeriod();
            state.selectedYear = Number(state.selectedPeriod.slice(0, 4));
            state.initialized = true;
            renderReport();
        } catch (error) {
            renderError(error.message);
        } finally {
            state.loading = false;
        }
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
        if (showRecaps) window.initMonthlyAudit(false);
    };
})();