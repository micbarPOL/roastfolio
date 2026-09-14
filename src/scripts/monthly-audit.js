(() => {
    'use strict';

    const MONTHS = [
        'Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec',
        'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień',
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
        const grouped = String(Math.abs(rounded)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
        return `${sign}${grouped} PLN`;
    };

    const formatPct = (value, showSign = false) => {
        const amount = number(value);
        const sign = showSign && amount > 0 ? '+' : '';
        return `${sign}${amount.toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 2 })}%`;
    };

    const formatDate = value => {
        if (!value) return 'Brak danych';
        const parsed = new Date(`${String(value).slice(0, 10)}T12:00:00`);
        return Number.isNaN(parsed.getTime())
            ? escapeHtml(value)
            : parsed.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
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
                <strong>Składamy miesięczny audyt</strong>
                <span>Liczymy wynik bez wpływu przepływów pieniężnych.</span>
            </div>`;
    }

    function renderError(message) {
        const root = document.getElementById('monthly-audit-root');
        if (!root) return;
        root.innerHTML = `
            <div class="monthly-audit-state" role="alert">
                <strong>Nie udało się pobrać podsumowania</strong>
                <span>${escapeHtml(message)}</span>
                <button type="button" onclick="initMonthlyAudit(true)">Spróbuj ponownie</button>
            </div>`;
    }

    function renderEmpty(period) {
        return `
            <div class="monthly-audit-state monthly-audit-empty">
                <span class="monthly-audit-empty-mark" aria-hidden="true">0</span>
                <strong>Brak audytu za ${escapeHtml(period)}</strong>
                <span>Podsumowanie pojawi się po zamknięciu miesiąca.</span>
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
                <div class="monthly-audit-timeline-label">Oś czasu</div>
                <div class="monthly-audit-timeline" role="navigation" aria-label="Miesiące audytu">
                    <div class="monthly-audit-year-control">
                        <button type="button" aria-label="Poprzedni rok" onclick="shiftMonthlyAuditYear(-1)">‹</button>
                        <strong>[ ${year} ]</strong>
                        <button type="button" aria-label="Następny rok" onclick="shiftMonthlyAuditYear(1)">›</button>
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
        const startY = 8 + Math.min(28, Math.abs(number(start)) * 1.2);
        const endY = 8 + Math.min(28, Math.abs(number(end)) * 1.2);
        return `
            <svg class="monthly-audit-trajectory" viewBox="0 0 120 44" aria-hidden="true">
                <path d="M4 ${startY} C38 ${startY}, 78 ${endY}, 116 ${endY}" />
                <circle cx="4" cy="${startY}" r="3"/><circle cx="116" cy="${endY}" r="3"/>
            </svg>`;
    }

    function progressRing(percent) {
        const clamped = Math.max(0, Math.min(100, number(percent)));
        const circumference = 175.93;
        const offset = circumference * (1 - clamped / 100);
        return `
            <div class="monthly-audit-ring" style="--ring-offset:${offset}">
                <svg viewBox="0 0 72 72" aria-hidden="true">
                    <circle class="ring-track" cx="36" cy="36" r="28"/>
                    <circle class="ring-progress" cx="36" cy="36" r="28"/>
                </svg>
                <strong>${escapeHtml(formatPct(percent))}</strong>
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
                ${metric('Wpłaty', formatPLN(item.deposits_pln), 'is-positive')}
                ${metric('Wypłaty', formatPLN(item.withdrawals_pln), item.withdrawals_pln ? 'is-negative' : 'is-neutral')}
                ${metric('Zmiana nominalna', formatPLN(item.overall_nominal_change_pln, true), tone(item.overall_nominal_change_pln))}
                ${metric('TWR portfela', formatPct(item.overall_twr_pct, true), tone(item.overall_twr_pct))}
            </div>
            <div class="monthly-audit-highlight-grid">
                <div class="monthly-audit-highlight efficiency">
                    <span>Lider efektywności · % TWR</span>
                    <strong>${escapeHtml(best.name || 'Brak danych')}</strong>
                    <b class="${tone(best.twr_pct)}">${escapeHtml(formatPct(best.twr_pct, true))} TWR</b>
                </div>
                <div class="monthly-audit-highlight engine">
                    <span>Główny motor zysku · PLN</span>
                    <strong>${escapeHtml(engine.name || 'Brak danych')}</strong>
                    <b class="${tone(engine.nominal_change_pln)}">${escapeHtml(formatPLN(engine.nominal_change_pln, true))}</b>
                </div>
            </div>`;
        return card('Przepływy i wynik portfeli', '01 · Rozliczenie', body);
    }

    function extremesCard(item) {
        const athValue = item.is_new_ath ? formatPLN(item.ath_value_pln) : 'Bez nowego ATH';
        const athDetail = item.is_new_ath ? `${formatDate(item.ath_date)} · nowy szczyt` : 'Szczyt nie został poprawiony';
        const delta = number(item.trajectory_delta_pp);
        const body = `
            <div class="monthly-audit-stats-grid">
                ${stat('Status ATH', athValue, athDetail, item.is_new_ath ? 'is-ath' : '')}
                ${stat('Dni od ostatniego ATH', item.days_since_ath == null ? 'Brak danych' : `${number(item.days_since_ath)} dni`, 'Stan na koniec miesiąca')}
                ${stat('Max drawdown', formatPct(item.max_drawdown_pct), formatDate(item.max_drawdown_date), 'is-danger')}
                ${stat('Trajektoria obsunięcia', `${formatPct(item.start_drawdown_pct)} → ${formatPct(item.end_drawdown_pct)}`, `${delta > 0 ? '+' : ''}${delta.toLocaleString('pl-PL', { maximumFractionDigits: 2 })} p.p.`, tone(delta), trajectoryVisual(item.start_drawdown_pct, item.end_drawdown_pct))}
                ${stat('Najlepszy dzień', formatPLN(item.best_day?.change_pln, true), formatDate(item.best_day?.date), 'is-positive')}
                ${stat('Najgorszy dzień', formatPLN(item.worst_day?.change_pln), formatDate(item.worst_day?.date), 'is-negative')}
            </div>`;
        return card('Statystyki i ekstrema miesiąca', '02 · Punkty zwrotne', body);
    }

    function seasonalityCard(item) {
        const count = number(item.historical_years_count);
        const negatives = number(item.negative_years_count);
        const positives = number(item.positive_years_count);
        const monthName = MONTHS[Math.max(0, number(item.month) - 1)];
        const historyText = count
            ? `${monthName} był w ostatnich ${count} obserwacjach ${negatives}× spadkowy (średnio ${formatPct(item.avg_negative_pct)}) i ${positives}× wzrostowy (średnio ${formatPct(item.avg_positive_pct, true)}).`
            : `To pierwszy ${monthName.toLowerCase()} z pełnym audytem. Sezonowość zaczynamy budować od tego wyniku.`;
        const outperformed = Boolean(item.outperformed_seasonal_history);
        const status = count
            ? (outperformed ? 'Bieżący wynik przebił sezonową historię' : 'Bieżący wynik nie przebił sezonowej historii')
            : 'Za mało danych do porównania sezonowego';
        const body = `
            <div class="monthly-audit-seasonality">
                <div class="monthly-audit-season-bars" aria-hidden="true">
                    <span class="negative" style="--share:${count ? (negatives / count) * 100 : 0}%"></span>
                    <span class="positive" style="--share:${count ? (positives / count) * 100 : 0}%"></span>
                </div>
                <p>${escapeHtml(historyText)}</p>
                <div class="monthly-audit-status ${outperformed ? 'is-positive' : 'is-caution'}">
                    <span>${outperformed ? 'Trend przełamany' : 'Test sezonowości'}</span>
                    <strong>${escapeHtml(status)}</strong>
                </div>
            </div>`;
        return card('Kontekst historyczny i sezonowość', '03 · Pamięć rynku', body);
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
                    <span>Realizacja celu miesięcznego</span>
                    <strong>${escapeHtml(formatPLN(target.actual_nominal_gain_pln, true))} <small>z ${escapeHtml(formatPLN(target.monthly_target_nominal_pln))}</small></strong>
                    <div class="monthly-audit-progress"><span style="width:${width}%"></span></div>
                </div>
            </div>
            <div class="monthly-audit-gains-grid">
                <div><span>Zyski papierowe</span><strong class="${tone(gains.unrealized_pln)}">${escapeHtml(formatPLN(gains.unrealized_pln, true))}</strong><small>Otwarte pozycje</small></div>
                <div><span>Zyski zrealizowane</span><strong class="${tone(gains.realized_pln)}">${escapeHtml(formatPLN(gains.realized_pln, true))}</strong><small>Sprzedaże w miesiącu · AVCO</small></div>
            </div>`;
        return card('Plan emerytalny i zyski', '04 · Cel i AVCO', body);
    }

    function contributionPanel(kind, asset) {
        const isCarry = kind === 'carry';
        if (!asset) {
            return `<div class="monthly-audit-contribution ${kind}"><span>${isCarry ? '▲ Lider' : '▼ Kotwica'}</span><strong>Brak danych</strong><p>Brak aktywów do porównania.</p></div>`;
        }
        return `
            <div class="monthly-audit-contribution ${kind}">
                <span>${isCarry ? '▲ Lider' : '▼ Kotwica'}</span>
                <div><strong>${escapeHtml(asset.ticker || asset.name)}</strong><b class="${tone(asset.net_contribution_pln)}">${escapeHtml(formatPLN(asset.net_contribution_pln, true))}</b></div>
                <p>${escapeHtml(asset.context_note || 'Czysta zmiana kursu, brak transakcji')}</p>
            </div>`;
    }

    function carryCard(item) {
        const body = `<div class="monthly-audit-contributions">${contributionPanel('carry', item.carry)}${contributionPanel('anchor', item.anchor)}</div>`;
        return card('Lider i kotwica miesiąca', '05 · Kontrybucja netto', body);
    }

    function diaryCard(item) {
        const audit = item.coping_diary_audit || {};
        const body = `
            <div class="monthly-audit-diary-summary">
                ${metric('Wpisy w miesiącu', String(number(audit.current_month_entries)))}
                ${metric('Średnia z 3 miesięcy', number(audit.three_month_avg_entries).toLocaleString('pl-PL', { maximumFractionDigits: 1 }))}
            </div>
            ${audit.activity_dropped_warning ? '<div class="monthly-audit-warning">Portfolio samo się nie przypilnuje. Zmniejszyłeś częstotliwość wpisów.</div>' : ''}
            <div class="monthly-audit-checkpoints">
                <div class="verified"><strong>${number(audit.checkpoints_true)}</strong><span>TRUE · potwierdzone</span></div>
                <div class="falsified"><strong>${number(audit.checkpoints_false)}</strong><span>FALSE · obalone</span></div>
                <div class="overdue"><strong>${number(audit.checkpoints_overdue)}</strong><span>OVERDUE · zaległe</span></div>
            </div>`;
        return card('Audyt Coping Diary i aktywność', '06 · Dyscyplina procesu', body);
    }

    function renderReport() {
        const root = document.getElementById('monthly-audit-root');
        if (!root) return;
        const item = state.items.get(state.selectedPeriod);
        const periodTitle = state.selectedPeriod && /^\d{4}-\d{2}$/.test(state.selectedPeriod)
            ? `${MONTHS[Number(state.selectedPeriod.slice(5)) - 1]} ${state.selectedPeriod.slice(0, 4)}`
            : 'Miesięczny audyt';
        root.innerHTML = `
            ${timelineMarkup()}
            <header class="monthly-audit-hero">
                <div><span>Miesięczny audyt</span><h1>${escapeHtml(periodTitle)}</h1></div>
                ${item ? `<div class="monthly-audit-hero-result ${tone(item.overall_twr_pct)}"><span>Wynik TWR</span><strong>${escapeHtml(formatPct(item.overall_twr_pct, true))}</strong></div>` : ''}
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