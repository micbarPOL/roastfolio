const OP_COLORS = {
    'Buy': '#0ea5e9',
    'Sell': '#34d399',
    'Dividend': '#fbbf24',
    'Deposit': '#a855f7',
    'Withdrawal': '#f87171',
    'Extra Cost': '#94a3b8',
    'Spin-off': '#2dd4bf',
};

let _fDateFrom = '';
let _fDateTo = '';
let _fOps = new Set();
let _fAsset = '';
let _fWallet = '';
let _fValueMin = null;
let _fValueMax = null;
let _allRows = [];

let _sliderMin = 0;
let _sliderMax = 1;
let _sliderMinPct = 0;
let _sliderMaxPct = 1;
let _sliderDrag = null;
let _txChart = null;
let _txUiBound = false;
let _txModalBound = false;
let _txLoadingPromise = null;
let _editingTxId = null;

function fmtNum(v, decimals = 2) {
    if (v === 0) return '—';
    return v.toLocaleString('pl-PL', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtK(v) {
    if (Math.abs(v) >= 1000) return (v / 1000).toFixed(1) + 'k';
    return Math.round(v).toString();
}

function fmtPLN(v) {
    return v.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN';
}

function isTurnoverOperation(operation) {
    return operation === 'Buy' || operation === 'Sell';
}

function opBadge(op) {
    const color = OP_COLORS[op] || '#94a3b8';
    const shortLabels = {
        'Buy': 'B',
        'Sell': 'S',
        'Dividend': 'D',
        'Deposit': '+',
        'Withdrawal': '-',
        'Extra Cost': 'C',
        'Spin-off': 'SO',
    };
    return `<span class="tx-op-badge" style="--tx-op-color:${color}" title="${escapeHtml(op)}"><span class="tx-op-full">${escapeHtml(op)}</span><span class="tx-op-short">${escapeHtml(shortLabels[op] || op.slice(0, 2).toUpperCase())}</span></span>`;
}

function normalizeNumber(value, fallback = 0) {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    }[ch]));
}

function formatInputNumber(value) {
    const num = Number(value);
    if (!Number.isFinite(num) || num === 0) return '';
    return String(num);
}

function normalizeAssetText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
}

function isCashTransactionRow(row) {
    return ['DEPOSIT', 'WITHDRAWAL', 'EXTRA_COST'].includes(String(row.type || '').toUpperCase());
}

function requiresQuantity(row) {
    return ['BUY', 'SELL', 'DIVIDEND', 'SPINOFF'].includes(String(row.type || '').toUpperCase());
}

function requiresPrice(row) {
    return ['BUY', 'SELL'].includes(String(row.type || '').toUpperCase());
}

function editableNumber(value, label, { required = false, allowZero = true } = {}) {
    const raw = String(value || '').replace(',', '.').trim();
    if (!raw) {
        if (required) throw new Error(`${label} is required.`);
        return null;
    }
    const num = Number(raw);
    if (!Number.isFinite(num)) throw new Error(`${label} must be a number.`);
    if (num < 0 || (!allowZero && num === 0)) throw new Error(`${label} must be greater than ${allowZero ? 'or equal to ' : ''}0.`);
    return num;
}

function holdingIdFromAsset(name, ticker) {
    return String(ticker || name || '')
        .trim()
        .replace(/[^a-zA-Z0-9_-]/g, '-')
        .toLowerCase()
        .slice(0, 64);
}

function parseAssetEdit(value, row) {
    const asset = normalizeAssetText(value);
    if (!asset) throw new Error('Asset is required.');
    const match = asset.match(/^(.*?)\s*\(([^()]+)\)\s*$/);
    let name = asset;
    let ticker = '';
    if (match) {
        name = normalizeAssetText(match[1]) || normalizeAssetText(match[2]);
        ticker = normalizeAssetText(match[2]);
    } else if (/^[A-Za-z0-9._=-]{1,16}$/.test(asset)) {
        ticker = asset.toUpperCase();
    }
    const unchanged = normalizeAssetText(row.asset).toLowerCase() === asset.toLowerCase();
    return {
        name,
        ticker,
        holdingId: unchanged && row.holdingId ? row.holdingId : holdingIdFromAsset(name, ticker),
    };
}

function editableField(row, field, value, attrs = '') {
    return `<input class="tx-edit-input" data-tx-field="${field}" value="${escapeHtml(value)}" ${attrs}>`;
}

function renderAssetText(row) {
    return `<span class="tx-asset-text" title="${escapeHtml(row.asset)}">${escapeHtml(row.asset)}</span>`;
}

function renderMobileEditPanel(row, actionHtml) {
    const stockDisabled = !isCashTransactionRow(row) ? '' : 'disabled';
    const quantityDisabled = requiresQuantity(row) ? '' : 'disabled';
    const numericDisabled = !isCashTransactionRow(row) ? '' : 'disabled';
    return `<tr class="tx-mobile-edit-row" data-tx-id="${escapeHtml(row.transactionId || '')}" data-portfolio-id="${escapeHtml(row.portfolioId || '')}">
        <td colspan="9">
            <div class="tx-mobile-edit-panel">
                <label>Date ${editableField(row, 'date', row.date, 'type="date"')}</label>
                <label>Stock ${editableField(row, 'asset', row.asset, stockDisabled)}</label>
                <label>Quantity ${editableField(row, 'quantity', formatInputNumber(Math.abs(row.units)), `type="number" step="any" inputmode="decimal" ${quantityDisabled}`)}</label>
                <label>Price ${editableField(row, 'price', formatInputNumber(row.price), `type="number" step="any" inputmode="decimal" ${numericDisabled}`)}</label>
                <label>Commission ${editableField(row, 'commission', formatInputNumber(row.commission), 'type="number" step="any" inputmode="decimal"')}</label>
                <div class="tx-mobile-edit-actions">${actionHtml}</div>
            </div>
        </td>
    </tr>`;
}

function currentTabIsTransactions() {
    return document.getElementById('tab-transactions')?.classList.contains('active');
}

function setSummaryMessage(message) {
    const summary = document.getElementById('tx-summary');
    if (summary) summary.textContent = message;
}

function applyFilters() {
    return _allRows.filter(r => {
        if (_fDateFrom && r.date < _fDateFrom) return false;
        if (_fDateTo && r.date > _fDateTo) return false;
        if (_fOps.size > 0 && !_fOps.has(r.operation)) return false;
        if (_fAsset && !r.asset.toLowerCase().includes(_fAsset)) return false;
        if (_fWallet && !(r.wallet || '').toLowerCase().includes(_fWallet)) return false;
        if (_fValueMin !== null && r.value < _fValueMin) return false;
        if (_fValueMax !== null && r.value > _fValueMax) return false;
        return true;
    });
}

function renderTable() {
    const tbody = document.getElementById('tx-body');
    if (!tbody) return;
    const filtered = applyFilters();
    if (!filtered.length) {
        tbody.innerHTML = `<tr><td colspan="9" style="padding:18px;text-align:center;color:#94a3b8">No transactions match the current filters.</td></tr>`;
    } else {
        tbody.innerHTML = filtered.map((r, i) => {
            const valueColor = r.value >= 0 ? '#34d399' : '#f87171';
            const editable = Boolean(r.transactionId && r.portfolioId && !r.automatic);
            const isEditing = editable && r.transactionId === _editingTxId;
            
            const stockDisabled = isEditing && !isCashTransactionRow(r) ? '' : 'disabled';
            const quantityDisabled = isEditing && requiresQuantity(r) ? '' : 'disabled';
            const numericDisabled = isEditing && !isCashTransactionRow(r) ? '' : 'disabled';
            
            let actionHtml = '';
            if (editable) {
                if (isEditing) {
                    actionHtml = `
                        <button class="tx-save-btn" data-tx-save title="Save transaction changes">Save</button>
                        <button class="tx-cancel-btn" data-tx-cancel title="Cancel editing">Cancel</button>
                        <div class="tx-row-status" data-tx-status></div>
                    `;
                } else {
                    actionHtml = `
                        <button class="tx-edit-btn" data-tx-edit title="Edit transaction">Edit</button>
                    `;
                }
            } else if (r.automatic) {
                actionHtml = `<span title="Automatic cash rows follow their source transaction." style="color:#94a3b8;font-size:11px;">Auto</span>`;
            }

            const renderCell = (field, textValue, inputHtml) => isEditing ? inputHtml : escapeHtml(textValue);
            const assetHtml = isEditing
                ? `<span class="tx-mobile-static-asset">${renderAssetText(r)}</span><span class="tx-desktop-edit-field">${editableField(r, 'asset', r.asset, stockDisabled)}</span>`
                : renderAssetText(r);

            const rowHtml = `<tr data-tx-id="${escapeHtml(r.transactionId || '')}" data-portfolio-id="${escapeHtml(r.portfolioId || '')}" style="${i % 2 === 0 ? '' : 'background:rgba(255,255,255,0.02)'}">
                <td class="hide-on-mobile">${isEditing ? editableField(r, 'date', r.date, 'type="date"') : escapeHtml(r.date)}</td>
                <td>${opBadge(r.operation)}</td>
                <td>${assetHtml}</td>
                <td class="hide-on-mobile">${escapeHtml(r.wallet || '—')}</td>
                <td class="hide-on-mobile" style="text-align:right">${renderCell('quantity', r.units !== 0 ? fmtNum(Math.abs(r.units), r.units % 1 === 0 ? 0 : 4) : '—', editableField(r, 'quantity', formatInputNumber(Math.abs(r.units)), `type="number" step="any" inputmode="decimal" ${quantityDisabled}`))}</td>
                <td class="hide-on-mobile" style="text-align:right">${renderCell('price', r.price ? fmtNum(r.price) : '—', editableField(r, 'price', formatInputNumber(r.price), `type="number" step="any" inputmode="decimal" ${numericDisabled}`))}</td>
                <td class="hide-on-mobile" style="text-align:right;color:#94a3b8">${renderCell('commission', r.commission ? fmtNum(r.commission) : '—', editableField(r, 'commission', formatInputNumber(r.commission), 'type="number" step="any" inputmode="decimal"'))}</td>
                <td class="tx-value-cell" style="text-align:right;font-weight:600;color:${valueColor}">${fmtNum(r.value)}</td>
                <td class="tx-save-cell">
                    ${actionHtml}
                </td>
            </tr>`;
            return rowHtml + (isEditing ? renderMobileEditPanel(r, actionHtml) : '');
        }).join('');
    }
    setSummaryMessage(`Showing ${filtered.length} of ${_allRows.length} transactions`);
}

function readTransactionUpdatePayload(row, tr) {
    const field = name => tr.querySelector(`[data-tx-field="${name}"]`)?.value;
    const transactionDate = String(field('date') || '').trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(transactionDate)) throw new Error('Date must be YYYY-MM-DD.');

    const payload = {
        transactionDate,
        commission: editableNumber(field('commission'), 'Commission') ?? 0,
    };
    if (requiresQuantity(row)) {
        payload.quantity = Math.abs(editableNumber(field('quantity'), 'Quantity', { required: true, allowZero: false }));
    }
    if (!isCashTransactionRow(row)) {
        const price = editableNumber(field('price'), 'Price', { required: requiresPrice(row), allowZero: !requiresPrice(row) });
        if (price !== null) payload.price = price;
        const asset = parseAssetEdit(field('asset'), row);
        payload.name = asset.name;
        payload.ticker = asset.ticker || null;
        payload.holdingId = asset.holdingId;
        payload.currency = row.currency || 'PLN';
    }
    return payload;
}

async function handleTransactionSave(button) {
    const tr = button.closest('tr[data-tx-id]');
    if (!tr) return;
    const row = _allRows.find(item => item.transactionId === tr.dataset.txId && item.portfolioId === tr.dataset.portfolioId);
    const status = tr.querySelector('[data-tx-status]');
    const setStatus = (message, error = false) => {
        if (status) status.textContent = message;
        tr.classList.toggle('tx-row-error', error);
    };
    if (!row) {
        setStatus('Row not found.', true);
        return;
    }
    if (typeof PortfolioClient?.updateTransaction !== 'function') {
        setStatus('Update API unavailable.', true);
        return;
    }

    let payload;
    try {
        payload = readTransactionUpdatePayload(row, tr);
    } catch (error) {
        setStatus(error.message || 'Invalid row data.', true);
        return;
    }

    button.disabled = true;
    button.textContent = 'Saving…';
    tr.classList.add('tx-row-saving');
    setStatus('Saving…');
    try {
        const result = await PortfolioClient.updateTransaction(row.portfolioId, row.transactionId, payload);
        _editingTxId = null;
        if (window.LedgerTransactions?.loadRows) {
            await window.LedgerTransactions.loadRows({ force: true, attemptMigration: false });
        } else {
            await refreshTransactionsTabData(true);
        }
        window.dispatchEvent(new CustomEvent('portfolioHistoryRecalculated', {
            detail: {
                portfolioId: row.portfolioId,
                fromDate: result?.recalculateFrom || payload.transactionDate,
                updated: result?.recalculated?.updated || 0,
            },
        }));
    } catch (error) {
        console.warn('Transaction update failed:', error);
        button.disabled = false;
        button.textContent = 'Save';
        tr.classList.remove('tx-row-saving');
        setStatus(error.message || 'Save failed.', true);
    }
}

function closeAllPopups(except) {
    ['pop-date', 'pop-op', 'pop-value'].forEach(id => {
        if (id !== except) document.getElementById(id)?.classList.remove('open');
    });
}

function togglePopup(popId) {
    closeAllPopups(popId);
    document.getElementById(popId)?.classList.toggle('open');
}

function buildOpToggles(ops) {
    const container = document.getElementById('op-checkboxes');
    if (!container) return;
    const activeOps = _fOps.size ? [..._fOps].filter(op => ops.includes(op)) : ops.slice();
    _fOps = activeOps.length === ops.length ? new Set() : new Set(activeOps);
    container.innerHTML = ops.map(op => {
        const color = OP_COLORS[op] || '#94a3b8';
        const activeClass = _fOps.size === 0 || _fOps.has(op) ? ' active' : '';
        return `<button class="op-pill${activeClass}" data-op="${op}" style="--op-color:${color}">${op}</button>`;
    }).join('');
    container.querySelectorAll('.op-pill').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            btn.classList.toggle('active');
            const selected = [...container.querySelectorAll('.op-pill.active')].map(b => b.dataset.op);
            _fOps = selected.length === ops.length ? new Set() : new Set(selected);
            updateOpBtn(ops, selected);
            renderTable();
        });
    });
    updateOpBtn(ops, _fOps.size ? [..._fOps] : ops);
}

function updateOpBtn(allOps, activeOps) {
    const btn = document.getElementById('btn-op');
    if (!btn) return;
    const allSelected = activeOps.length === allOps.length;
    btn.textContent = allSelected ? '≡ All' : `≡ ${activeOps.length} selected`;
    btn.classList.toggle('filter-active', !allSelected);
}

function pctFromValue(v) {
    return _sliderMax === _sliderMin ? 0 : (v - _sliderMin) / (_sliderMax - _sliderMin);
}

function valueFromPct(p) {
    return _sliderMin + p * (_sliderMax - _sliderMin);
}

function updateSliderUI(minPct, maxPct) {
    const fill = document.getElementById('range-fill');
    const tMin = document.getElementById('thumb-min');
    const tMax = document.getElementById('thumb-max');
    const labels = document.getElementById('value-range-labels');
    if (!fill || !tMin || !tMax || !labels) return;
    fill.style.left = (minPct * 100) + '%';
    fill.style.width = ((maxPct - minPct) * 100) + '%';
    tMin.style.left = (minPct * 100) + '%';
    tMax.style.left = (maxPct * 100) + '%';
    const vMin = valueFromPct(minPct);
    const vMax = valueFromPct(maxPct);
    labels.innerHTML = `<span>${fmtK(vMin)} PLN</span><span>${fmtK(vMax)} PLN</span>`;
    _fValueMin = minPct === 0 ? null : vMin;
    _fValueMax = maxPct === 1 ? null : vMax;
    const btn = document.getElementById('btn-value');
    const active = _fValueMin !== null || _fValueMax !== null;
    if (btn) {
        btn.textContent = active ? `↔ ${fmtK(vMin)}…${fmtK(vMax)}` : '↔ Any value';
        btn.classList.toggle('filter-active', active);
    }
}

function resetSlider(minVal, maxVal) {
    _sliderMin = Number.isFinite(minVal) ? minVal : 0;
    _sliderMax = Number.isFinite(maxVal) ? maxVal : 1;
    if (_sliderMax <= _sliderMin) _sliderMax = _sliderMin + 1;
    _sliderMinPct = 0;
    _sliderMaxPct = 1;
    updateSliderUI(_sliderMinPct, _sliderMaxPct);
}

function bindSliderEvents() {
    ['thumb-min', 'thumb-max'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('mousedown', e => {
            _sliderDrag = el.dataset.thumb;
            e.preventDefault();
        });
        el.addEventListener('touchstart', () => {
            _sliderDrag = el.dataset.thumb;
        }, { passive: true });
    });
    document.addEventListener('mousemove', e => {
        if (!_sliderDrag) return;
        onSliderMove(e.clientX);
    });
    document.addEventListener('touchmove', e => {
        if (!_sliderDrag) return;
        onSliderMove(e.touches[0].clientX);
    }, { passive: true });
    document.addEventListener('mouseup', () => {
        _sliderDrag = null;
    });
    document.addEventListener('touchend', () => {
        _sliderDrag = null;
    });
    document.getElementById('clear-value')?.addEventListener('click', () => {
        _sliderMinPct = 0;
        _sliderMaxPct = 1;
        updateSliderUI(_sliderMinPct, _sliderMaxPct);
        renderTable();
    });
}

function onSliderMove(clientX) {
    const slider = document.getElementById('value-slider');
    if (!slider) return;
    const rect = slider.getBoundingClientRect();
    let p = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    if (_sliderDrag === 'min') _sliderMinPct = Math.min(p, _sliderMaxPct - 0.01);
    if (_sliderDrag === 'max') _sliderMaxPct = Math.max(p, _sliderMinPct + 0.01);
    updateSliderUI(_sliderMinPct, _sliderMaxPct);
    renderTable();
}

function updateDateBtn() {
    const btn = document.getElementById('btn-date');
    if (!btn) return;
    const active = _fDateFrom || _fDateTo;
    btn.textContent = active ? `📅 ${_fDateFrom || '…'} – ${_fDateTo || '…'}` : '📅 Any date';
    btn.classList.toggle('filter-active', Boolean(active));
}

function bindFilterEvents() {
    document.addEventListener('click', e => {
        if (!e.target.closest('.tx-th')) closeAllPopups(null);
    });
    document.getElementById('btn-date')?.addEventListener('click', e => {
        togglePopup('pop-date');
        e.stopPropagation();
    });
    document.getElementById('f-date-from')?.addEventListener('change', function() {
        _fDateFrom = this.value;
        updateDateBtn();
        renderTable();
    });
    document.getElementById('f-date-to')?.addEventListener('change', function() {
        _fDateTo = this.value;
        updateDateBtn();
        renderTable();
    });
    document.getElementById('date-quick-today')?.addEventListener('click', () => {
        const today = new Date();
        const tzOffset = today.getTimezoneOffset() * 60000;
        const localISOTime = (new Date(today.getTime() - tzOffset)).toISOString().split('T')[0];
        _fDateFrom = localISOTime;
        _fDateTo = localISOTime;
        const from = document.getElementById('f-date-from');
        const to = document.getElementById('f-date-to');
        if (from) from.value = localISOTime;
        if (to) to.value = localISOTime;
        updateDateBtn();
        renderTable();
    });
    document.getElementById('date-quick-week')?.addEventListener('click', () => {
        const now = new Date();
        const day = now.getDay();
        const diff = now.getDate() - day + (day === 0 ? -6 : 1);
        const startOfWeek = new Date(now.setDate(diff));
        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setDate(startOfWeek.getDate() + 6);
        
        const tzOffset = startOfWeek.getTimezoneOffset() * 60000;
        const startStr = (new Date(startOfWeek.getTime() - tzOffset)).toISOString().split('T')[0];
        const endStr = (new Date(endOfWeek.getTime() - tzOffset)).toISOString().split('T')[0];
        
        _fDateFrom = startStr;
        _fDateTo = endStr;
        const from = document.getElementById('f-date-from');
        const to = document.getElementById('f-date-to');
        if (from) from.value = startStr;
        if (to) to.value = endStr;
        updateDateBtn();
        renderTable();
    });
    document.getElementById('clear-date')?.addEventListener('click', () => {
        _fDateFrom = '';
        _fDateTo = '';
        const from = document.getElementById('f-date-from');
        const to = document.getElementById('f-date-to');
        if (from) from.value = '';
        if (to) to.value = '';
        updateDateBtn();
        renderTable();
    });
    document.getElementById('btn-op')?.addEventListener('click', e => {
        togglePopup('pop-op');
        e.stopPropagation();
    });
    document.getElementById('f-asset')?.addEventListener('input', function() {
        _fAsset = this.value.toLowerCase();
        renderTable();
    });
    document.getElementById('f-asset')?.addEventListener('click', e => e.stopPropagation());
    
    document.getElementById('f-wallet')?.addEventListener('input', function() {
        _fWallet = this.value.toLowerCase();
        renderTable();
    });
    document.getElementById('f-wallet')?.addEventListener('click', e => e.stopPropagation());
    document.getElementById('btn-value')?.addEventListener('click', e => {
        togglePopup('pop-value');
        e.stopPropagation();
    });
    bindSliderEvents();
}

function initDayModalHandlers() {
    if (_txModalBound) return;
    _txModalBound = true;
    const overlay = document.getElementById('cal-modal-overlay');
    document.getElementById('cal-modal-close')?.addEventListener('click', () => {
        if (overlay) overlay.style.display = 'none';
    });
    overlay?.addEventListener('click', e => {
        if (e.target === overlay) overlay.style.display = 'none';
    });
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && overlay) overlay.style.display = 'none';
    });
}

function ensureTransactionsUi() {
    if (_txUiBound) return;
    _txUiBound = true;
    bindFilterEvents();
    initDayModalHandlers();
    document.getElementById('tx-body')?.addEventListener('click', event => {
        const saveBtn = event.target.closest('[data-tx-save]');
        if (saveBtn) {
            handleTransactionSave(saveBtn);
            return;
        }
        const editBtn = event.target.closest('[data-tx-edit]');
        if (editBtn) {
            const tr = editBtn.closest('tr[data-tx-id]');
            if (tr) {
                _editingTxId = tr.dataset.txId;
                renderTable();
            }
            return;
        }
        const cancelBtn = event.target.closest('[data-tx-cancel]');
        if (cancelBtn) {
            _editingTxId = null;
            renderTable();
            return;
        }
    });

    document.getElementById('tx-body')?.addEventListener('input', event => {
        if (!event.target.classList.contains('tx-edit-input')) return;
        const tr = event.target.closest('tr[data-tx-id]');
        if (!tr) return;
        const row = _allRows.find(item => item.transactionId === tr.dataset.txId && item.portfolioId === tr.dataset.portfolioId);
        if (!row || isCashTransactionRow(row)) return;

        const qtyInput = tr.querySelector('[data-tx-field="quantity"]');
        const priceInput = tr.querySelector('[data-tx-field="price"]');
        const commInput = tr.querySelector('[data-tx-field="commission"]');

        if (qtyInput && priceInput && commInput) {
            const qtyStr = String(qtyInput.value).replace(',', '.');
            const priceStr = String(priceInput.value).replace(',', '.');
            const commStr = String(commInput.value).replace(',', '.');

            const qty = Math.abs(Number(qtyStr) || 0);
            const price = Number(priceStr) || 0;
            const comm = Number(commStr) || 0;

            let rawValue = qty * price;
            const op = (row.operation || '').toUpperCase();
            if (op === 'BUY') {
                rawValue = -(rawValue + comm);
            } else if (op === 'SELL') {
                rawValue = rawValue - comm;
            } else if (op === 'DIVIDEND') {
                const tax = row.tax || 0;
                rawValue = rawValue - comm - tax;
            } else if (op === 'SPIN-OFF') {
                rawValue = 0;
            }

            const valCell = tr.querySelector('.tx-value-cell');
            if (valCell) {
                valCell.textContent = fmtNum(rawValue);
                valCell.style.color = rawValue >= 0 ? '#34d399' : '#f87171';
            }
        }
    });
}

function turnoverOf(rows) {
    return rows
        .filter(row => isTurnoverOperation(row.operation))
        .reduce((sum, row) => sum + Math.abs(row.value), 0);
}

function renderSummary(rows) {
    const now = new Date();
    const currentMonth = now.toISOString().slice(0, 7);
    const currentYear = now.toISOString().slice(0, 4);
    const monthRows = rows.filter(r => r.date.startsWith(currentMonth));
    const ytdRows = rows.filter(r => r.date.startsWith(currentYear));
    const set = (id, value, sub) => {
        const el = document.getElementById(id);
        const subEl = document.getElementById(id.replace('value', 'sub'));
        if (el) el.textContent = value;
        if (subEl) subEl.textContent = sub;
    };
    set('tx-month-value', fmtPLN(turnoverOf(monthRows)), `${monthRows.length} transactions`);
    set('tx-ytd-value', fmtPLN(turnoverOf(ytdRows)), `${ytdRows.length} transactions`);
    set('tx-total-value', fmtPLN(turnoverOf(rows)), `${rows.length} transactions total`);
}

function renderTurnoverChart(rows) {
    const canvas = document.getElementById('txTurnoverChart');
    if (!canvas || typeof Chart === 'undefined') return;
    if (_txChart) {
        _txChart.destroy();
        _txChart = null;
    }
    const byMonth = {};
    for (const row of rows) {
        if (!isTurnoverOperation(row.operation)) continue;
        const month = row.date.slice(0, 7);
        if (!month) continue;
        byMonth[month] = (byMonth[month] || 0) + Math.abs(row.value);
    }
    const months = Object.keys(byMonth).sort();
    const labels = months.map(month => {
        const [year, numMonth] = month.split('-');
        return new Date(year, Number(numMonth) - 1).toLocaleString('en-US', { month: 'short' }) + ' ' + year.slice(2);
    });
    const values = months.map(month => parseFloat(byMonth[month].toFixed(2)));
    _txChart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Monthly Turnover (PLN)',
                data: values,
                backgroundColor: 'rgba(0, 240, 255, 0.75)',
                borderColor: 'rgba(0, 240, 255, 1)',
                borderWidth: 1,
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
                        title: ctx => ctx[0]?.label || '',
                        label: ctx => 'Turnover: ' + ctx.parsed.y.toLocaleString('pl-PL', { minimumFractionDigits: 2 }) + ' PLN',
                    },
                },
            },
            scales: {
                x: { ticks: { maxRotation: 45 } },
                y: { ticks: { callback: v => fmtK(v) + ' PLN' } },
            },
        },
    });
}

function initCalendar(rows) {
    const tabContainer = document.getElementById('cal-year-tabs');
    const calContainer = document.getElementById('tx-calendar');
    if (!tabContainer || !calContainer) return;

    const byYear = {};
    const turnoverByDate = {};
    const depositDates = new Set();
    const withdrawalDates = new Set();

    for (const row of rows) {
        const year = row.date.slice(0, 4);
        if (!year) continue;
        if (!byYear[year]) byYear[year] = new Set();
        byYear[year].add(row.date);
        if (isTurnoverOperation(row.operation)) {
            turnoverByDate[row.date] = (turnoverByDate[row.date] || 0) + Math.abs(row.value);
        }
        if (row.operation === 'Deposit') depositDates.add(row.date);
        if (row.operation === 'Withdrawal') withdrawalDates.add(row.date);
    }

    const years = Object.keys(byYear).sort().reverse();
    if (!years.length) {
        tabContainer.innerHTML = '';
        calContainer.innerHTML = '<div style="padding:18px;color:#94a3b8">No transaction activity yet.</div>';
        return;
    }

    let activeYear = years[0];
    tabContainer.innerHTML = years.map(year =>
        `<button class="cal-year-btn${year === activeYear ? ' active' : ''}" data-year="${year}">${year}</button>`
    ).join('');
    tabContainer.querySelectorAll('.cal-year-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            activeYear = this.dataset.year;
            tabContainer.querySelectorAll('.cal-year-btn').forEach(node => node.classList.remove('active'));
            this.classList.add('active');
            renderCalendar(calContainer, activeYear, byYear[activeYear] || new Set(), turnoverByDate, depositDates, withdrawalDates);
        });
    });
    renderCalendar(calContainer, activeYear, byYear[activeYear] || new Set(), turnoverByDate, depositDates, withdrawalDates);
}

function renderCalendar(container, year, activeDates, turnoverByDate, depositDates, withdrawalDates) {
    const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const DOW = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
    const maxTurnover = Math.max(1, ...[...activeDates].map(date => turnoverByDate[date] || 0));
    const intensity = dateStr => {
        const turnover = turnoverByDate[dateStr] || 0;
        if (!turnover) return 0;
        const pct = turnover / maxTurnover;
        if (pct <= 0.10) return 1;
        if (pct <= 0.25) return 2;
        if (pct <= 0.50) return 3;
        if (pct <= 0.80) return 4;
        return 5;
    };

    let html = '<div class="cal-grid">';
    for (let month = 0; month < 12; month++) {
        html += `<div class="cal-month">
            <div class="cal-month-name">${MONTHS[month]}</div>
            <div class="cal-dow-row">${DOW.map(day => `<span class="cal-dow">${day}</span>`).join('')}</div>
            <div class="cal-days">`;
        const firstDow = new Date(year, month, 1).getDay();
        const offset = (firstDow + 6) % 7;
        for (let i = 0; i < offset; i++) html += '<span class="cal-day empty"></span>';
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        for (let day = 1; day <= daysInMonth; day++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const active = activeDates.has(dateStr);
            const level = active ? intensity(dateStr) : 0;
            const turnover = turnoverByDate[dateStr] || 0;
            const title = active
                ? `${dateStr}\n${turnover.toLocaleString('pl-PL', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} PLN turnover`
                : '';
            const frameClass = depositDates.has(dateStr)
                ? ' cal-frame-deposit'
                : withdrawalDates.has(dateStr)
                    ? ' cal-frame-withdrawal'
                    : '';
            html += `<span class="cal-day${active ? ` cal-active cal-i${level}` : ''}${frameClass}" title="${title}"${active ? ` data-date="${dateStr}"` : ''}>${day}</span>`;
        }
        html += '</div></div>';
    }
    html += '</div>';
    container.innerHTML = html;
    container.querySelectorAll('.cal-day.cal-active').forEach(el => {
        el.addEventListener('click', () => openDayModal(el.dataset.date, _allRows));
    });
}

function openDayModal(dateStr, rows) {
    const dayRows = rows.filter(row => row.date === dateStr);
    if (!dayRows.length) return;
    const title = document.getElementById('cal-modal-title');
    const body = document.getElementById('cal-modal-body');
    const overlay = document.getElementById('cal-modal-overlay');
    const date = new Date(dateStr);
    if (title) {
        title.textContent = date.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }
    const totalTurnover = dayRows
        .filter(row => isTurnoverOperation(row.operation))
        .reduce((sum, row) => sum + Math.abs(row.value), 0);
    if (body) {
        body.innerHTML = `
            <div style="display:flex;gap:16px;margin-bottom:14px;flex-wrap:wrap;">
                <div class="stat-card" style="flex:1;min-width:160px;padding:10px 14px;">
                    <div class="stat-label">Total Turnover</div>
                    <div class="stat-value" style="font-size:1.1rem">${fmtPLN(totalTurnover)}</div>
                </div>
                <div class="stat-card" style="flex:1;min-width:160px;padding:10px 14px;">
                    <div class="stat-label">Transactions</div>
                    <div class="stat-value" style="font-size:1.1rem">${dayRows.length}</div>
                </div>
            </div>
            <table class="holdings-table" style="width:100%;font-size:13px;">
                <thead><tr>
                    <th>Operation</th><th>Asset</th><th>Wallet</th><th>Units</th><th>Price</th><th>Commission</th><th style="text-align:right">Value</th>
                </tr></thead>
                <tbody>
                    ${dayRows.map((row, i) => {
                        const valueColor = row.value >= 0 ? '#34d399' : '#f87171';
                        return `<tr style="background:${i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)'}">
                            <td>${opBadge(row.operation)}</td>
                            <td>${row.asset}</td>
                            <td>${row.wallet || '—'}</td>
                            <td style="text-align:right">${row.units !== 0 ? fmtNum(Math.abs(row.units), row.units % 1 === 0 ? 0 : 4) : '—'}</td>
                            <td style="text-align:right">${row.price ? fmtNum(row.price) : '—'}</td>
                            <td style="text-align:right;color:#94a3b8">${row.commission ? fmtNum(row.commission) : '—'}</td>
                            <td style="text-align:right;font-weight:600;color:${valueColor}">${fmtNum(row.value)}</td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>`;
    }
    if (overlay) overlay.style.display = 'flex';
}

function renderTransactionsView(rows) {
    _allRows = rows;
    const ops = [...new Set(_allRows.map(row => row.operation))].sort();
    buildOpToggles(ops);
    const values = _allRows.map(row => row.value);
    resetSlider(
        values.length ? Math.floor(Math.min(...values)) : 0,
        values.length ? Math.ceil(Math.max(...values)) : 1
    );
    updateDateBtn();
    renderSummary(_allRows);
    renderTurnoverChart(_allRows);
    initCalendar(_allRows);
    renderTable();
}

async function refreshTransactionsTabData(force = false) {
    ensureTransactionsUi();
    if (_txLoadingPromise && !force) return _txLoadingPromise;
    const tbody = document.getElementById('tx-body');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="9" style="padding:18px;text-align:center;color:#94a3b8">Loading transactions…</td></tr>';
    }
    setSummaryMessage('Loading transactions…');
    _txLoadingPromise = (async () => {
        try {
            const rows = await window.LedgerTransactions.loadRows({ force });
            renderTransactionsView(rows);
        } catch (error) {
            console.warn('Transactions tab failed to load live history:', error);
            renderTransactionsView([]);
        } finally {
            _txLoadingPromise = null;
        }
    })();
    return _txLoadingPromise;
}

window.refreshTransactionsTabData = refreshTransactionsTabData;

window.addEventListener('portfolioTransactionSaved', () => {
    if (currentTabIsTransactions() || _allRows.length) refreshTransactionsTabData(true);
});

window.addEventListener('ledgerTransactionsUpdated', event => {
    if (!currentTabIsTransactions() && !_allRows.length) return;
    renderTransactionsView(Array.isArray(event.detail?.rows) ? event.detail.rows : []);
});

document.addEventListener('DOMContentLoaded', () => {
    ensureTransactionsUi();
    if (currentTabIsTransactions()) refreshTransactionsTabData();
});
