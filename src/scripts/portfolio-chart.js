// Uses live Lambda/DynamoDB-backed PORTFOLIO_DATA + WALLET_HOLDINGS state.

const COMPANY_PIE_COLORS = {
    'XTB':                         '#00f0ff', // Neon Cyan
    'RAINBOW (RBW)':               '#ffea00', // Neon Yellow
    'MOBRUK (MBR)':                '#39ff14', // Neon Green
    'CREOTECH (CRI)':              '#bc13fe', // Neon Purple
    'CDPROJEKT (CDR)':             '#ff003c', // Neon Red
    'Meta Platforms, Inc. (META)': '#005eff', // Neon Blue
    'Bitcoin (BTC)':               '#ff8a00', // Neon Orange
    'Gotówka (konto)':             '#4b5563', // Sleek Gray
    'Cash':                        '#4b5563',
};

const COMPANY_LOGO_MAP = {
    'XTB':                         'data/logos/xtb.png',
    'RAINBOW (RBW)':               'data/logos/RAINBOW.png',
    'MOBRUK (MBR)':                'data/logos/MOBRUK.png',
    'CREOTECH (CRI)':              'data/logos/CREOTECH.png',
    'CDPROJEKT (CDR)':             'data/logos/CDPROJEKT.png',
    'Meta Platforms, Inc. (META)': 'data/logos/META.png',
    'Bitcoin (BTC)':               'data/logos/Bitcoin.png',
};

const FALLBACK_COLORS = ['#00f0ff', '#ffea00', '#39ff14', '#bc13fe', '#ff003c', '#005eff', '#ff8a00', '#ff007f'];
let _athPortfolioLookup = null;
let _athPortfolioLookupPromise = null;
const _athEditorOpen = new Set();

const _assignedColors = {};
let _colorIndex = 0;

function getColor(name, index) {
    if (COMPANY_PIE_COLORS[name]) return COMPANY_PIE_COLORS[name];
    if (_assignedColors[name]) return _assignedColors[name];
    
    _assignedColors[name] = FALLBACK_COLORS[_colorIndex % FALLBACK_COLORS.length];
    _colorIndex++;
    return _assignedColors[name];
}

function fmtAthMoney(value) {
    const num = Number(value || 0);
    return num.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN';
}

function formatAbbreviatedMoney(value) {
    const num = Number(value || 0);
    const abs = Math.abs(num);
    const sign = num < 0 ? '-' : '';
    
    if (window.innerWidth <= 768) {
        if (abs >= 1000000) {
            return sign + (abs / 1000000).toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + 'M';
        }
        if (abs >= 1000) {
            return sign + (abs / 1000).toLocaleString('pl-PL', { minimumFractionDigits: 0, maximumFractionDigits: 1 }) + 'k';
        }
        return num.toLocaleString('pl-PL', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }
    return num.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatAthSource(source) {
    return source === 'MANUAL' ? 'Manual' : 'Auto';
}

function fmtPortfolioEditorAction(row) {
    return row.key === 'Summary' ? 'Manage ATH' : 'Edit wallet';
}

function isAthEditorOpen(walletKey) {
    return _athEditorOpen.has(walletKey);
}

function toggleAthEditor(walletKey) {
    if (_athEditorOpen.has(walletKey)) _athEditorOpen.delete(walletKey);
    else _athEditorOpen.add(walletKey);
    renderAthEditor();
}

async function loadAthPortfolioLookup(force) {
    if (_athPortfolioLookup && !force) return _athPortfolioLookup;
    if (_athPortfolioLookupPromise && !force) return _athPortfolioLookupPromise;

    const baseMap = { ...(window.WALLET_PORTFOLIO_IDS || {}) };
    _athPortfolioLookupPromise = (async () => {
        try {
            if (window.PortfolioClient && typeof PortfolioClient.listPortfolios === 'function') {
                const data = await PortfolioClient.listPortfolios();
                for (const p of (data.portfolios || [])) {
                    if (p && p.name && p.portfolioId) baseMap[p.name] = p.portfolioId;
                }
            }
        } catch (e) {
            console.warn('[portfolio-ath] portfolio lookup fetch failed', e);
        }
        _athPortfolioLookup = baseMap;
        _athPortfolioLookupPromise = null;
        return _athPortfolioLookup;
    })();
    return _athPortfolioLookupPromise;
}

function getAthRows() {
    const walletNames = (window.PORTFOLIO_WALLETS || Object.keys(window.WALLET_SUMMARIES || {})).filter(Boolean);
    const rows = [{
        key: 'Summary',
        label: 'Total Portfolio',
        portfolioId: 'summary',
        summary: window.WALLET_SUMMARIES ? window.WALLET_SUMMARIES.Summary : null,
        ath: window.PORTFOLIO_ATH || null,
    }];

    walletNames.filter(name => name !== 'Summary').forEach(name => {
        rows.push({
            key: name,
            label: name,
            portfolioId: (window.WALLET_PORTFOLIO_IDS || {})[name] || null,
            summary: window.WALLET_SUMMARIES ? window.WALLET_SUMMARIES[name] : null,
            ath: (window.WALLET_ATHS || {})[name] || null,
        });
    });
    return rows;
}

function getAthStatusEl() {
    return document.getElementById('portfolio-ath-status');
}

function setAthStatus(message, type) {
    const el = getAthStatusEl();
    if (!el) return;
    el.textContent = message || '';
    el.className = `portfolio-ath-status${type ? ` is-${type}` : ''}`;
}

function renderAthEditor() {
    const container = document.getElementById('portfolio-ath-grid');
    if (!container) return;

    const rows = getAthRows();
    container.innerHTML = rows.map(row => {
        const summary = row.summary || { total: 0, dailyPLN: 0, dailyPct: 0 };
        const ath = row.ath || {};
        const dailyColor = Number(summary.dailyPLN || 0) >= 0 ? '#27ae60' : '#c0392b';
        const sign = Number(summary.dailyPLN || 0) >= 0 ? '+' : '';
        const value = ath.athValue != null ? Number(ath.athValue) : '';
        const date = ath.athDate || '';
        const source = formatAthSource(ath.athSource);
        const isOpen = isAthEditorOpen(row.key);
        const canRename = row.key !== 'Summary';
        return `
        <div class="portfolio-ath-card${isOpen ? ' is-open' : ''}" data-ath-key="${row.key}">
            <div class="portfolio-ath-card-head">
                <div>
                    <div class="portfolio-ath-label">${row.label}</div>
                    <div class="portfolio-ath-current-value">${fmtAthMoney(summary.total || 0)}</div>
                </div>
                <div class="portfolio-ath-card-tools">
                    <div class="portfolio-ath-source">${source}</div>
                    <button
                        type="button"
                        class="portfolio-ath-icon-btn"
                        onclick="toggleAthEditor('${row.key}')"
                        aria-expanded="${isOpen ? 'true' : 'false'}"
                        aria-label="${isOpen ? 'Hide' : 'Show'} wallet editor for ${row.label}"
                        title="${isOpen ? 'Hide editor' : fmtPortfolioEditorAction(row)}"
                    >✏️</button>
                </div>
            </div>
            <div class="portfolio-ath-metrics">
                <div class="portfolio-ath-metric">
                    <span class="portfolio-ath-metric-label">Daily</span>
                    <strong style="color:${dailyColor}">${sign}${Number(summary.dailyPLN || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN</strong>
                    <span style="color:${dailyColor}">(${sign}${Number(summary.dailyPct || 0).toFixed(2)}%)</span>
                </div>
                <div class="portfolio-ath-metric">
                    <span class="portfolio-ath-metric-label">Current ATH</span>
                    <strong>${ath.athValue != null ? fmtAthMoney(ath.athValue) : '—'}</strong>
                    <span>${date || '—'}</span>
                </div>
            </div>
            <div class="portfolio-ath-meta-note">Daily close snapshots always keep checking for a new ATH. Manual ATH sets the current ATH but does not disable automatic updates.</div>
            <div class="portfolio-ath-form${isOpen ? ' is-open' : ''}" ${isOpen ? '' : 'hidden aria-hidden="true" style="display:none;"'}>
                ${canRename ? `
                <div class="portfolio-ath-editor-title">Wallet name</div>
                <input type="text" class="portfolio-ath-input" data-role="name" placeholder="Wallet name" maxlength="80" value="${row.label}">
                ` : ''}
                <div class="portfolio-ath-editor-title">Manual ATH</div>
                <input type="date" class="portfolio-ath-input" data-role="date" value="${date}">
                <input type="number" class="portfolio-ath-input" data-role="value" placeholder="ATH value (PLN)" min="0" step="0.01" value="${value}">
                <div class="portfolio-ath-actions">
                    <button type="button" class="portfolio-ath-btn portfolio-ath-btn-primary" onclick="savePortfolioEditor('${row.key}')">Save changes</button>
                    <button type="button" class="portfolio-ath-btn" onclick="resetPortfolioAth('${row.key}')">Reset from history</button>
                </div>
            </div>
        </div>`;
    }).join('');
}

async function resolveAthPortfolioId(walletKey) {
    if (walletKey === 'Summary') return 'summary';
    const lookup = await loadAthPortfolioLookup();
    return lookup[walletKey] || null;
}

async function savePortfolioEditor(walletKey) {
    const card = document.querySelector(`[data-ath-key="${walletKey}"]`);
    if (!card || !window.PortfolioClient) return;
    const row = getAthRows().find(item => item.key === walletKey);
    const nameEl = card.querySelector('[data-role="name"]');
    const dateEl = card.querySelector('[data-role="date"]');
    const valueEl = card.querySelector('[data-role="value"]');
    const nextName = nameEl ? nameEl.value.trim() : '';
    const athDate = dateEl ? dateEl.value : '';
    const athValue = valueEl ? parseFloat(valueEl.value) : NaN;
    const hasAthDate = !!athDate;
    const hasAthValue = valueEl ? String(valueEl.value).trim() !== '' : false;

    const portfolioId = await resolveAthPortfolioId(walletKey);
    if (!portfolioId) {
        setAthStatus(`Could not find portfolio ID for ${walletKey}.`, 'error');
        return;
    }

    const canRename = walletKey !== 'Summary';
    const nameChanged = !!(canRename && row && nextName && nextName !== row.label);
    const wantsAthUpdate = hasAthDate || hasAthValue;

    if (canRename && nameEl && !nextName) {
        setAthStatus('Enter a wallet name.', 'error');
        return;
    }
    if (wantsAthUpdate && !athDate) {
        setAthStatus('Pick an ATH date first.', 'error');
        return;
    }
    if (wantsAthUpdate && (!Number.isFinite(athValue) || athValue <= 0)) {
        setAthStatus('Enter a valid ATH value.', 'error');
        return;
    }
    if (!nameChanged && !wantsAthUpdate) {
        setAthStatus('No changes to save.', 'error');
        return;
    }

    setAthStatus(`Saving ${walletKey} changes…`, 'saving');
    try {
        let athResponse = null;
        if (nameChanged) {
            await PortfolioClient.putPortfolio({
                portfolioId,
                name: nextName,
                type: 'real',
                currency: 'PLN',
            });
        }
        if (wantsAthUpdate) {
            athResponse = await PortfolioClient.updateAth(portfolioId, {
                athDate,
                athValue,
                athSource: 'MANUAL',
            });
        }
        _athEditorOpen.clear();
        _athPortfolioLookup = null;
        if (!nameChanged && athResponse) {
            if (walletKey === 'Summary') window.PORTFOLIO_ATH = athResponse.ath || null;
            else {
                window.WALLET_ATHS = window.WALLET_ATHS || {};
                window.WALLET_ATHS[walletKey] = athResponse.ath || null;
            }
        }
        if (typeof refreshLivePrices === 'function') await refreshLivePrices();
        await loadAthPortfolioLookup(true);
        renderAthEditor();
        if (typeof renderDashboard === 'function') renderDashboard();
        const messageParts = [];
        if (nameChanged) messageParts.push('wallet renamed');
        if (wantsAthUpdate) messageParts.push('manual ATH saved');
        setAthStatus(`${walletKey}: ${messageParts.join(' and ')}.`, 'ok');
    } catch (e) {
        setAthStatus(e.message || 'Could not save wallet changes.', 'error');
    }
}

async function resetPortfolioAth(walletKey) {
    if (!window.PortfolioClient) return;
    const portfolioId = await resolveAthPortfolioId(walletKey);
    if (!portfolioId) {
        setAthStatus(`Could not find portfolio ID for ${walletKey}.`, 'error');
        return;
    }
    setAthStatus(`Recalculating ${walletKey} ATH from snapshot history…`, 'saving');
    try {
        const response = await PortfolioClient.updateAth(portfolioId, { athSource: 'AUTO' });
        _athEditorOpen.delete(walletKey);
        if (walletKey === 'Summary') window.PORTFOLIO_ATH = response.ath || null;
        else {
            window.WALLET_ATHS = window.WALLET_ATHS || {};
            window.WALLET_ATHS[walletKey] = response.ath || null;
        }
        renderAthEditor();
        if (typeof renderDashboard === 'function') renderDashboard();
        if (typeof refreshLivePrices === 'function') await refreshLivePrices();
        setAthStatus(`${walletKey} ATH reset from historical snapshots.`, 'ok');
    } catch (e) {
        setAthStatus(e.message || 'Could not recalculate ATH from history.', 'error');
    }
}

// Plugin: draw logos at the midpoint of each pie slice — disabled, logos shown in legend only

function normalizeHoldings(data) {
    if (!data) return [];
    // Rename 'Gotówka (konto)' → 'Cash' to match the synthetic cash holding name
    const renamed = [...data]
        .map(d => (d.name === 'Gotówka (konto)' || d.name === 'Gotówka') ? { ...d, name: 'Cash' } : d);
    // Merge duplicate names (e.g. two Cash positions) by summing their values
    const merged = {};
    for (const d of renamed) {
        if (merged[d.name]) {
            merged[d.name] = {
                ...merged[d.name],
                currentValue:  (merged[d.name].currentValue  || 0) + (d.currentValue  || 0),
                purchaseValue: (merged[d.name].purchaseValue || 0) + (d.purchaseValue || 0),
                units:         (merged[d.name].units         || 0) + (d.units         || 0),
            };
        } else {
            merged[d.name] = { ...d };
        }
    }
    // Recalculate pct after merging
    const values = Object.values(merged);
    const total  = values.reduce((s, d) => s + (d.currentValue || 0), 0);
    if (total > 0) {
        values.forEach(d => { d.pct = +((d.currentValue / total) * 100).toFixed(1); });
    }
    return values.sort((a, b) => (b.currentValue || 0) - (a.currentValue || 0));
}

function buildHtmlLegend(containerId, data) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = data.map((d, i) => {
        const color = getColor(d.name, i);
        const logoSrc = COMPANY_LOGO_MAP[d.name];
        const logoHtml = logoSrc
            ? `<img src="${logoSrc}" class="legend-logo" onerror="this.style.display='none'">`
            : '';
        const isCash = d.name === 'Cash' || d.name.toLowerCase().includes('cash');
        const clickHandler = isCash ? '' : `onclick="window.openAnalysisForTicker('${d.ticker || d.name}')" style="cursor:pointer;"`;
        const clickableClass = isCash ? '' : ' legend-item-clickable';
        return `<div class="legend-item${clickableClass}" ${clickHandler}>
            <span class="legend-color-bar" style="background:${color}"></span>
            ${logoHtml ? `<span class="legend-logo-wrap">${logoHtml}</span>` : ''}
            <span class="legend-text">${d.name}</span>
            <span class="legend-pct">${d.pct}%</span>
        </div>`;
    }).join('');
}

function getPieTooltip() {
    let el = document.getElementById('pie-chart-tooltip');
    if (!el) {
        el = document.createElement('div');
        el.id = 'pie-chart-tooltip';
        el.className = 'pie-chart-tooltip';
        document.body.appendChild(el);
    }
    return el;
}

function externalPieTooltip(context, data) {
    const { chart, tooltip } = context;
    const el = getPieTooltip();

    if (!tooltip || tooltip.opacity === 0 || !tooltip.dataPoints || !tooltip.dataPoints.length) {
        el.style.opacity = '0';
        el.style.pointerEvents = 'none';
        return;
    }

    const point = tooltip.dataPoints[0];
    const item = data[point.dataIndex];
    const logoSrc = COMPANY_LOGO_MAP[item.name];
    const value = item.currentValue.toLocaleString('pl-PL', { minimumFractionDigits: 2 });
    const ret = `${item.returnPct >= 0 ? '+' : ''}${item.returnPct}%`;

    el.innerHTML = `
        <div class="pie-tooltip-head">
            ${logoSrc ? `<img src="${logoSrc}" alt="${item.name}" class="pie-tooltip-logo" onerror="this.style.display='none'">` : ''}
            <div class="pie-tooltip-title-wrap">
                <div class="pie-tooltip-title">${item.name}</div>
                <div class="pie-tooltip-share">Share: ${item.pct}%</div>
            </div>
        </div>
        <div class="pie-tooltip-metric">Value: <strong>${value} PLN</strong></div>
        <div class="pie-tooltip-metric">Return: <strong>${ret}</strong></div>
    `;

    const rect = chart.canvas.getBoundingClientRect();
    el.style.opacity = '1';
    el.style.pointerEvents = 'none';
    el.style.left = `${rect.left + window.scrollX + tooltip.caretX + 16}px`;
    el.style.top = `${rect.top + window.scrollY + tooltip.caretY - 20}px`;
}

function makePieChart(canvasId, data, legendId) {
    const canvas = document.getElementById(canvasId);
    data = normalizeHoldings(data);
    if (!canvas || !data || data.length === 0) return;

    // Destroy existing Chart.js instance if any
    const existing = Chart.getChart(canvas);
    if (existing) existing.destroy();

    // If canvas has no layout dimensions (hidden tab), set explicit size so Chart.js can render.
    // Chart.js will resize correctly when the tab becomes visible.
    if (!canvas.offsetWidth || !canvas.offsetHeight) {
        canvas.style.width  = '220px';
        canvas.style.height = '220px';
    }
    
    // Add glowing bloom effect to the pie slices
    canvas.style.filter = 'drop-shadow(0 0 10px rgba(255, 255, 255, 0.35))';

    if (legendId) buildHtmlLegend(legendId, data);

        new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: data.map(d => d.name),
            datasets: [{
                data: data.map(d => d.currentValue),
                backgroundColor: data.map((d, i) => getColor(d.name, i)),
                borderColor: 'transparent',
                borderWidth: 0,
                borderRadius: 20,
                spacing: 8,
                hoverOffset: 12
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '82%',
            layout: {
                padding: 12
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: false,
                    external: (context) => externalPieTooltip(context, data)
                }
            }
        }
    });
}

function makeSimpleTable(tbodySelector, data) {
    const tbody = document.querySelector(tbodySelector);
    data = normalizeHoldings(data);
    if (!tbody || !data) return;
    tbody.innerHTML = ''; // clear for re-render
    for (const d of data) {
        const currentValue  = Number.isFinite(Number(d.currentValue))  ? Number(d.currentValue)  : 0;
        const purchaseValue = Number.isFinite(Number(d.purchaseValue)) ? Number(d.purchaseValue) : 0;
        const profit        = Number.isFinite(Number(d.profit))        ? Number(d.profit)        : 0;
        const returnPct     = Number.isFinite(Number(d.returnPct))     ? Number(d.returnPct)     : 0;
        const pct           = Number.isFinite(Number(d.pct))           ? Number(d.pct)           : 0;
        const isCash = d.name === 'Cash';
        const profitColor = isCash ? '#94a3b8' : (profit >= 0 ? '#34d399' : '#f87171');
        
        const tr = tbody.insertRow();
        tr.style.fontFamily = 'monospace';
        tr.style.color = '#e2e8f0';
        if (isCash) tr.style.color = '#94a3b8';
        
        const expandedTr = tbody.insertRow();
        expandedTr.className = 'expanded-details-row';
        expandedTr.style.display = 'none';

        if (!isCash) {
            tr.style.cursor = 'pointer';
            tr.className = 'holding-row-clickable';
            tr.onclick = () => {
                if (window.innerWidth <= 768) {
                    expandedTr.style.display = expandedTr.style.display === 'none' ? 'table-row' : 'none';
                } else {
                    window.openAnalysisForTicker(d.ticker || d.name);
                }
            };
        }

        tr.insertCell().textContent = d.name;
        tr.insertCell().textContent = formatAbbreviatedMoney(currentValue);
        
        const purchCell = tr.insertCell();
        purchCell.className = 'hide-on-mobile';
        purchCell.textContent = formatAbbreviatedMoney(purchaseValue);
        
        const pc = tr.insertCell();
        pc.textContent = (profit >= 0 ? '+' : '') + formatAbbreviatedMoney(profit);
        pc.style.cssText = `color:${profitColor};font-weight:bold;text-shadow:0 0 5px currentColor;`;
        
        const rc = tr.insertCell();
        rc.className = 'hide-on-mobile';
        rc.textContent = (returnPct >= 0 ? '+' : '') + returnPct + '%';
        rc.style.cssText = `color:${profitColor};font-weight:bold;text-shadow:0 0 5px currentColor;`;
        
        const pctCell = tr.insertCell();
        pctCell.className = 'hide-on-mobile';
        pctCell.textContent = pct + '%';

        const detailsTd = expandedTr.insertCell();
        detailsTd.colSpan = 6;
        detailsTd.innerHTML = `
            <div class="mobile-expanded-details">
                <div class="mobile-detail-item">
                    <span>Purchase Value:</span>
                    <span>${formatAbbreviatedMoney(purchaseValue)} PLN</span>
                </div>
                <div class="mobile-detail-item">
                    <span>Total Return:</span>
                    <span style="color:${profitColor}">${(returnPct >= 0 ? '+' : '') + returnPct}%</span>
                </div>
                <div class="mobile-detail-item">
                    <span>Portfolio %:</span>
                    <span>${pct}%</span>
                </div>
                ${!isCash ? `<button class="mobile-analyze-btn" onclick="window.openAnalysisForTicker('${d.ticker || d.name}')">Analyze Asset</button>` : ''}
            </div>
        `;
    }
}

function renderPortfolio() {
    if (typeof PORTFOLIO_DATA === 'undefined' || !PORTFOLIO_DATA) return;

    const el = document.getElementById('portfolio-updated');
    if (el && typeof PORTFOLIO_UPDATED_AT !== 'undefined') {
        const formatted = typeof formatPortfolioUpdatedAtCET === 'function'
            ? formatPortfolioUpdatedAtCET(PORTFOLIO_UPDATED_AT)
            : PORTFOLIO_UPDATED_AT;
        el.textContent = '— last updated: ' + formatted;
    }

    makePieChart('portfolioChart', PORTFOLIO_DATA, 'legendPortfolio');

    // Portfolio full table (with price/today/ytd columns)
    const tbody = document.querySelector('#portfolio-table tbody');
    if (tbody) {
        tbody.innerHTML = ''; // clear for re-render
        for (const d of normalizeHoldings(PORTFOLIO_DATA)) {
            const pricePLN = Number.isFinite(Number(d.pricePLN)) ? Number(d.pricePLN) : 0;
            const currentValue = Number.isFinite(Number(d.currentValue)) ? Number(d.currentValue) : 0;
            const purchaseValue = Number.isFinite(Number(d.purchaseValue)) ? Number(d.purchaseValue) : 0;
            const profit = Number.isFinite(Number(d.profit)) ? Number(d.profit) : 0;
            const dailyChangePct = Number.isFinite(Number(d.dailyChangePct)) ? Number(d.dailyChangePct) : 0;
            const ytdChangePct = Number.isFinite(Number(d.ytdChangePct)) ? Number(d.ytdChangePct) : 0;
            const returnPct = Number.isFinite(Number(d.returnPct)) ? Number(d.returnPct) : 0;
            const pct = Number.isFinite(Number(d.pct)) ? Number(d.pct) : 0;
            const isCash = d.name === 'Cash';
            const profitColor = isCash ? '#94a3b8' : (profit >= 0 ? '#34d399' : '#f87171');
            const dailyColor  = dailyChangePct >= 0 ? '#34d399' : '#f87171';
            const ytdColor    = ytdChangePct >= 0 ? '#34d399' : '#f87171';
            
            const tr = tbody.insertRow();
            tr.style.fontFamily = 'monospace';
            tr.style.color = '#e2e8f0';
            if (isCash) tr.style.color = '#94a3b8';
            
            const expandedTr = tbody.insertRow();
            expandedTr.className = 'expanded-details-row';
            expandedTr.style.display = 'none';

            if (!isCash) {
                tr.style.cursor = 'pointer';
                tr.className = 'holding-row-clickable';
                tr.onclick = () => {
                    if (window.innerWidth <= 768) {
                        expandedTr.style.display = expandedTr.style.display === 'none' ? 'table-row' : 'none';
                    } else {
                        window.openAnalysisForTicker(d.ticker || d.name);
                    }
                };
            }

            tr.insertCell().textContent = d.name;

            const priceCell = tr.insertCell();
            priceCell.className = 'hide-on-mobile';
            if (d.priceOriginalCurrency && d.priceOriginalCurrency !== 'PLN') {
                priceCell.innerHTML = `${pricePLN.toLocaleString('pl-PL', { minimumFractionDigits: 2 })}<br><small style="color:#94a3b8">${d.priceOriginal} ${d.priceOriginalCurrency}</small>`;
            } else {
                priceCell.textContent = pricePLN > 0 ? pricePLN.toLocaleString('pl-PL', { minimumFractionDigits: 2 }) : '—';
            }

            const tc = tr.insertCell();
            tc.className = 'hide-on-mobile';
            if (dailyChangePct !== 0) { tc.textContent = (dailyChangePct >= 0 ? '+' : '') + dailyChangePct + '%'; tc.style.cssText = `color:${dailyColor};font-weight:bold;text-shadow:0 0 5px currentColor;`; }
            else tc.textContent = '—';

            const yc = tr.insertCell();
            yc.className = 'hide-on-mobile';
            if (ytdChangePct !== 0) { yc.textContent = (ytdChangePct >= 0 ? '+' : '') + ytdChangePct + '%'; yc.style.cssText = `color:${ytdColor};font-weight:bold;text-shadow:0 0 5px currentColor;`; }
            else yc.textContent = '—';

            tr.insertCell().textContent = formatAbbreviatedMoney(currentValue);
            
            const purchCell = tr.insertCell();
            purchCell.className = 'hide-on-mobile';
            purchCell.textContent = formatAbbreviatedMoney(purchaseValue);
            
            const p = tr.insertCell(); 
            p.textContent = (profit >= 0 ? '+' : '') + formatAbbreviatedMoney(profit); 
            p.style.cssText = `color:${profitColor};font-weight:bold;text-shadow:0 0 5px currentColor;`;
            
            const r = tr.insertCell(); 
            r.className = 'hide-on-mobile';
            r.textContent = (returnPct >= 0 ? '+' : '') + returnPct + '%'; 
            r.style.cssText = `color:${profitColor};font-weight:bold;text-shadow:0 0 5px currentColor;`;            
            
            const pctCell = tr.insertCell();
            pctCell.className = 'hide-on-mobile';
            pctCell.textContent = pct + '%';
            
            const detailsTd = expandedTr.insertCell();
            detailsTd.colSpan = 9;
            detailsTd.innerHTML = `
                <div class="mobile-expanded-details">
                    <div class="mobile-detail-item">
                        <span>Price:</span>
                        <span>${pricePLN > 0 ? pricePLN.toLocaleString('pl-PL', { minimumFractionDigits: 2 }) : '—'} PLN</span>
                    </div>
                    <div class="mobile-detail-item">
                        <span>Today:</span>
                        <span style="color:${dailyColor}">${(dailyChangePct >= 0 ? '+' : '') + dailyChangePct}%</span>
                    </div>
                    <div class="mobile-detail-item">
                        <span>YTD:</span>
                        <span style="color:${ytdColor}">${(ytdChangePct >= 0 ? '+' : '') + ytdChangePct}%</span>
                    </div>
                    <div class="mobile-detail-item">
                        <span>Purchase Value:</span>
                        <span>${formatAbbreviatedMoney(purchaseValue)} PLN</span>
                    </div>
                    <div class="mobile-detail-item">
                        <span>Total Return:</span>
                        <span style="color:${profitColor}">${(returnPct >= 0 ? '+' : '') + returnPct}%</span>
                    </div>
                    <div class="mobile-detail-item">
                        <span>Portfolio %:</span>
                        <span>${pct}%</span>
                    </div>
                    ${!isCash ? `<button class="mobile-analyze-btn" onclick="window.openAnalysisForTicker('${d.ticker || d.name}')">Analyze Asset</button>` : ''}
                </div>
            `;
        }
    }
}

window._portfolioInitialized = false;

function _walletNames() {
    return (window.PORTFOLIO_WALLETS || Object.keys(window.WALLET_SUMMARIES || {}))
        .filter(name => name && name !== 'Summary');
}

function _walletDomId(name) {
    return String(name || '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '') || 'wallet';
}

function _walletHoldings(name) {
    const holdings = (window.WALLET_HOLDINGS || {})[name];
    return Array.isArray(holdings) ? holdings : [];
}

function renderWalletBreakdowns() {
    const walletNames = _walletNames();
    const miniCharts = document.getElementById('portfolio-wallet-mini-charts');
    const holdingsTabs = document.getElementById('holdings-wallet-tabs');
    const holdingsSections = document.getElementById('holdings-wallet-sections');
    if (!miniCharts || !holdingsTabs || !holdingsSections) return;

    // Clear only dynamically added wallets, keeping the static Portfolio Summary chart
    miniCharts.querySelectorAll('.dynamic-wallet-section').forEach(el => el.remove());

    miniCharts.insertAdjacentHTML('beforeend', walletNames.map(name => {
        const domId = _walletDomId(name);
        return `
            <section class="chart-container mini-chart-section dynamic-wallet-section" data-dom-id="${domId}">
                <h3 style="font-size: 14px; margin-top: 0;">${name}</h3>
                <div class="pie-with-legend">
                    <div class="pie-wrapper-mini"><canvas id="portfolioChartWallet-${domId}"></canvas></div>
                    <div class="pie-legend pie-legend-mini" id="legendWallet-${domId}"></div>
                </div>
            </section>`;
    }).join(''));

    holdingsTabs.innerHTML = walletNames.map(name => {
        const domId = _walletDomId(name);
        return `<button class="holdings-tab-btn" data-dom-id="${domId}" onclick="showHoldingsTab('holdings-wallet-${domId}', this)">${name}</button>`;
    }).join('');

    holdingsSections.innerHTML = walletNames.map(name => {
        const domId = _walletDomId(name);
        return `
            <div id="holdings-wallet-${domId}" class="holdings-content">
                <table id="portfolio-table-wallet-${domId}" class="holdings-table">
                    <thead><tr><th>Company</th><th>Current Value (PLN)</th><th class="hide-on-mobile">Purchase Value (PLN)</th><th>Profit / Loss (PLN)</th><th class="hide-on-mobile">Total Return</th><th class="hide-on-mobile">Portfolio %</th></tr></thead>
                    <tbody></tbody>
                </table>
            </div>`;
    }).join('');

    walletNames.forEach(name => {
        const domId = _walletDomId(name);
        const holdings = _walletHoldings(name);
        makePieChart(`portfolioChartWallet-${domId}`, holdings, `legendWallet-${domId}`);
        makeSimpleTable(`#portfolio-table-wallet-${domId} tbody`, holdings);
    });

    // Removed IntersectionObserver as per user request (prevents table filtering on swipe)
}

// Called when the Portfolio tab becomes visible (ensures canvas has proper dimensions)
function initPortfolioCharts() {
    if (window._portfolioInitialized) return;
    window._portfolioInitialized = true;

    renderPortfolio();
    renderWalletBreakdowns();
}
window.initPortfolioCharts = initPortfolioCharts;
window.toggleAthEditor = toggleAthEditor;
window.savePortfolioEditor = savePortfolioEditor;
window.savePortfolioAth = savePortfolioEditor;
window.resetPortfolioAth = resetPortfolioAth;


// On DOMContentLoaded, pre-render portfolio charts while tab is hidden.
// We use two nested rAFs so the browser completes layout before Chart.js measures canvases.
document.addEventListener('DOMContentLoaded', function () {
    requestAnimationFrame(() => requestAnimationFrame(() => initPortfolioCharts()));
});
document.addEventListener('liveDataReady', function () {
    _athPortfolioLookup = null;
    renderPortfolio();
    try { renderWalletBreakdowns(); } catch (e) { console.error('[portfolio-chart] renderWalletBreakdowns failed:', e); }
});
