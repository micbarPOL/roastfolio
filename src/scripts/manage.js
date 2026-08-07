/**
 * manage.js — Portfolio & holding management UI controller.
 *
 * Exposes:
 *   openManageModal()  — open the portfolio manager
 *   closeManageModal() — close it
 *
 * Depends on: config.js, auth-guard.js, portfolios.js
 */

(() => {
  // ── State ────────────────────────────────────────────────────
  let _portfolios   = [];
  let _activePortId = null;
  let _searchTimer  = null;
  let _selectedHolding = null;
  let _searchRequestId = 0;
  let _searchResults = [];
  let _searchActiveIndex = -1;
  let _searchSource = 'yf';   // 'yf' | 'tfi'
  let _currentHoldings = [];
  let _currentTransactions = [];
  let _currentClosedHoldings = [];
  let _currentSnapshots = [];
  let _holdingsView = 'active';
  let _cemeterySort = { key: 'date', dir: 'desc' }; // default: latest close first
  let _transactionsPanelMode = 'trade';
  let _priceInputSource = 'price'; // 'price' | 'total' — last edited price-related field

  let _walletSelectorOpen = false;
  let _createComposerOpen = false;
  let _walletStickyBound = false;
  let _walletStickyLastScrollY = 0;
  let _walletStickyCondensed = false;
  const _companyLogos = {
    'XTB': 'data/logos/xtb.png',
    'RAINBOW (RBW)': 'data/logos/RAINBOW.png',
    'MOBRUK (MBR)': 'data/logos/MOBRUK.png',
    'CREOTECH (CRI)': 'data/logos/CREOTECH.png',
    'CDPROJEKT (CDR)': 'data/logos/CDPROJEKT.png',
    'Meta Platforms, Inc. (META)': 'data/logos/META.png',
    'Bitcoin (BTC)': 'data/logos/Bitcoin.png',
  };

  // ── API base ─────────────────────────────────────────────────
  function _apiBase() {
    const cfg = window.__CONFIG__ || {};
    return (cfg.apiUrl || '').replace(/\/prices$/, '');
  }

  async function _get(path) {
    const token = AuthGuard.getIdToken();
    const res = await fetch(_apiBase() + path, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || `HTTP ${res.status}`);
    }
    return res.json();
  }

  // ── Ticker search ────────────────────────────────────────────
  async function searchTickers(q) {
    const data = await _get(`/search?q=${encodeURIComponent(q || '')}`);
    return data.results || [];
  }

  // ── Render helpers ───────────────────────────────────────────
  function _esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function _portfolioColor(name) {
    const colors = ['#4a9fd4','#27ae60','#e67e22','#9b59b6','#e74c3c','#1abc9c','#f39c12'];
    let h = 0; for (let c of name) h = (h * 31 + c.charCodeAt(0)) & 0xffff;
    return colors[h % colors.length];
  }

  function _isSummaryPortfolio(portfolioId) {
    return String(portfolioId || '').toLowerCase() === 'summary';
  }

  function _activePortfolio() {
    return _portfolios.find(x => x.portfolioId === _activePortId) || null;
  }

  function _walletSummaryFor(portfolio) {
    if (!portfolio || typeof WALLET_SUMMARIES === 'undefined' || !WALLET_SUMMARIES) return null;
    if (_isSummaryPortfolio(portfolio.portfolioId)) return WALLET_SUMMARIES.Summary || null;
    return WALLET_SUMMARIES[portfolio.name] || null;
  }

  function _liveHoldingsFor(portfolio) {
    if (!portfolio) return [];
    if (_isSummaryPortfolio(portfolio.portfolioId)) return (typeof window !== 'undefined' && window.PORTFOLIO_DATA) || [];
    if (typeof WALLET_HOLDINGS === 'undefined' || !WALLET_HOLDINGS) return [];
    return WALLET_HOLDINGS[portfolio.name] || [];
  }

  function _holdingKey(item) {
    const ticker = String(item && item.ticker || '').trim().toUpperCase();
    if (ticker) return `ticker:${ticker}`;
    return `name:${String(item && item.name || '').trim().toLowerCase()}`;
  }

  function _mergeHoldings(rawHoldings, liveHoldings) {
    const rawMap = new Map((rawHoldings || []).map(item => [_holdingKey(item), item]));
    const merged = [];

    (liveHoldings || []).forEach(live => {
      const raw = rawMap.get(_holdingKey(live)) || {};
      merged.push({ ...raw, ...live });
      rawMap.delete(_holdingKey(live));
    });

    rawMap.forEach(raw => {
      merged.push({ ...raw, currentValue: Number(raw.purchaseValue || 0), pct: 0 });
    });

    return merged.sort((a, b) => Number(b.currentValue || b.purchaseValue || 0) - Number(a.currentValue || a.purchaseValue || 0));
  }

  function _logoHtml(name, ticker) {
    const src = _companyLogos[name];
    if (!src) return `<div class="wallet-holding-avatar">${_esc((ticker || name || '?').slice(0, 1))}</div>`;
    return `<img src="${src}" alt="" class="wallet-holding-logo" onerror="this.style.display='none'">`;
  }

  async function _refreshWalletData() {
    if (typeof window.refreshLivePrices === 'function') {
      try {
        await window.refreshLivePrices();
      } catch (_) {}
    }
  }

  function _deepClone(value) {
    return JSON.parse(JSON.stringify(value || []));
  }

  function _fmtMoney(value) {
    return `${Number(value || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN`;
  }

  function _fmtUnits(value) {
    return Number(value || 0).toLocaleString('pl-PL', { maximumFractionDigits: 4 });
  }

  function _fmtMaybeUnits(value) {
    return Number.isFinite(Number(value)) && Number(value) > 0 ? _fmtUnits(value) : '—';
  }

  function _fmtSignedPct(value) {
    const num = Number(value || 0);
    const sign = num > 0 ? '+' : '';
    return `${sign}${num.toFixed(2)}%`;
  }

  function _fmtSignedMoney(value) {
    const num = Number(value || 0);
    const sign = num > 0 ? '+' : '';
    return `${sign}${num.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN`;
  }

  function _holdingMetricValue(holding, snakeCase, camelCase) {
    const value = holding && (holding[snakeCase] ?? holding[camelCase]);
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function _transactionAssetKey(tx, options = {}) {
    const { preferTicker = false } = options;
    if (!preferTicker && tx && tx.holdingId) return `id:${String(tx.holdingId)}`;
    const ticker = String(tx && tx.ticker || '').trim().toUpperCase();
    if (ticker) return `ticker:${ticker}`;
    return `name:${String(tx && tx.name || '').trim().toLowerCase()}`;
  }

  function _isAssetTransaction(tx) {
    return ['BUY', 'SELL', 'DIVIDEND', 'SPINOFF'].includes(String(tx && tx.type || '').toUpperCase());
  }

  function _buildHoldingPerformance(transactions, closedHoldings = [], options = {}) {
    const { aggregateByTicker = false } = options;
    const grouped = new Map();
    (transactions || []).filter(_isAssetTransaction).forEach(tx => {
      const key = _transactionAssetKey(tx, { preferTicker: aggregateByTicker });
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(tx);
    });

    const metrics = new Map();
    grouped.forEach((rows, key) => {
      const sorted = rows.slice().sort((a, b) => String(a.transactionDate || a.date || '').localeCompare(String(b.transactionDate || b.date || '')));
      let units = 0;
      let costBasis = 0;
      let realized = 0;
      let dividends = 0;
      let firstBuyDate = '';
      let lastSellDate = '';
      let name = '';
      let ticker = '';
      let gamification = null;

      sorted.forEach(tx => {
        const type = String(tx.type || '').toUpperCase();
        const quantity = Math.abs(Number(tx.quantity || 0));
        const value = Math.abs(Number(tx.value || 0));
        name = String(tx.name || name || 'Unknown asset');
        ticker = String(tx.ticker || ticker || '');
        gamification = tx.gamification || tx.gamificationPayload || tx.gamification_payload || gamification;

        if (type === 'BUY') {
          units += quantity;
          costBasis += value;
          if (!firstBuyDate) firstBuyDate = String(tx.transactionDate || tx.date || '').slice(0, 10);
        } else if (type === 'SELL' && quantity > 0) {
          const soldCost = units > 0 ? costBasis * Math.min(quantity, units) / units : 0;
          realized += value - soldCost;
          costBasis = Math.max(0, costBasis - soldCost);
          units = Math.max(0, units - quantity);
          lastSellDate = String(tx.transactionDate || tx.date || '').slice(0, 10);
        } else if (type === 'DIVIDEND') {
          dividends += value;
        }
      });

      metrics.set(key, { units, realized, dividends, firstBuyDate, lastSellDate, name, ticker, gamification });
    });
    closedHoldings.forEach(holding => {
      const key = _transactionAssetKey(holding, { preferTicker: aggregateByTicker });
      metrics.set(key, {
        units: Number(holding.units || 0),
        realized: _holdingMetricValue(holding, 'realized_return', 'realizedReturn') || 0,
        unrealized: _holdingMetricValue(holding, 'unrealized_return', 'unrealizedReturn') || 0,
        dividends: _holdingMetricValue(holding, 'dividends_received', 'dividendsReceived') || 0,
        firstBuyDate: holding.first_buy_date || holding.firstBuyDate || '',
        lastSellDate: holding.last_sell_date || holding.lastSellDate || '',
        name: holding.name || holding.ticker || 'Unknown asset',
        ticker: holding.ticker || '',
        gamification: holding.gamification || holding.gamificationPayload || holding.gamification_payload || null,
      });
    });
    return metrics;
  }

  function _holdingPerformanceFor(holding, performance) {
    const fallback = performance.get(_transactionAssetKey(holding)) || {};
    const realized = _holdingMetricValue(holding, 'realized_return', 'realizedReturn');
    const unrealized = _holdingMetricValue(holding, 'unrealized_return', 'unrealizedReturn');
    const dividends = _holdingMetricValue(holding, 'dividends_received', 'dividendsReceived');
    return {
      ...fallback,
      realized: realized ?? fallback.realized ?? 0,
      unrealized: unrealized ?? fallback.unrealized ?? 0,
      dividends: dividends ?? fallback.dividends ?? 0,
      gamification: holding.gamification || holding.gamificationPayload || holding.gamification_payload || fallback.gamification || null,
    };
  }

  function _lifespanLabel(firstBuyDate, lastSellDate) {
    if (!firstBuyDate || !lastSellDate) return 'Dates unavailable';
    const start = new Date(`${firstBuyDate}T00:00:00`);
    const end = new Date(`${lastSellDate}T00:00:00`);
    const days = Math.max(0, Math.round((end - start) / 86400000));
    return `${firstBuyDate} → ${lastSellDate} · ${days === 1 ? '1 day' : `${days} days`}`;
  }

  function _positionLifespanLabel(firstBuyDate, lastSellDate) {
    if (!firstBuyDate) return 'Dates unavailable';
    if (!lastSellDate) {
      const start = new Date(`${firstBuyDate}T00:00:00`);
      const now = new Date();
      const days = Math.max(0, Math.round((now - start) / 86400000));
      return `${firstBuyDate} → Active · ${days === 1 ? '1 day' : `${days} days`}`;
    }
    return _lifespanLabel(firstBuyDate, lastSellDate);
  }

  function _bindCemeterySortHandlers() {
    const dateBtn = document.getElementById('cemetery-sort-date');
    const returnBtn = document.getElementById('cemetery-sort-return');
    if (!dateBtn || !returnBtn || dateBtn.dataset.bound === '1') return;

    dateBtn.dataset.bound = '1';
    const applySort = (key) => {
      if (_cemeterySort.key === key) {
        _cemeterySort.dir = _cemeterySort.dir === 'desc' ? 'asc' : 'desc';
      } else {
        _cemeterySort = { key, dir: key === 'date' ? 'desc' : 'asc' };
      }
      if (_activePortId) {
        _renderHoldings(_activePortId, _currentHoldings, _isSummaryPortfolio(_activePortId));
      }
    };

    dateBtn.addEventListener('click', () => applySort('date'));
    returnBtn.addEventListener('click', () => applySort('return'));
  }

  function _updateCemeterySortLabels() {
    const dateBtn = document.getElementById('cemetery-sort-date');
    const returnBtn = document.getElementById('cemetery-sort-return');
    if (!dateBtn || !returnBtn) return;

    const arrow = (_cemeterySort.dir === 'desc') ? ' ↓' : ' ↑';
    dateBtn.textContent = `Holding lifespan${_cemeterySort.key === 'date' ? arrow : ''}`;
    returnBtn.textContent = `Realized (Unrealized)${_cemeterySort.key === 'return' ? arrow : ''}`;
  }

  function _isCompactWalletSelector() {
    return typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(max-width: 860px)').matches;
  }

  function _walletSelectorMetrics(portfolio) {
    const summary = _walletSummaryFor(portfolio) || { total: 0, dailyPct: 0 };
    return {
      total: Number(summary.total || 0),
      dailyPct: Number(summary.dailyPct || 0),
    };
  }


  function _pageScrollTop() {
    const root = document.scrollingElement || document.documentElement || document.body;
    return Math.max(Number((root && root.scrollTop) || window.pageYOffset || window.scrollY || 0), 0);
  }

  function _isWalletsTabActive() {
    const tab = document.getElementById('tab-wallets');
    return !!(tab && tab.classList.contains('active'));
  }

  function _walletStickyElements() {
    const sentinel = document.getElementById('wallet-sticky-sentinel');
    const sticky = document.querySelector('#tab-wallets .wallet-sticky-top');
    const card = sticky ? sticky.querySelector('.wallet-selector-card') : null;
    return { sentinel, sticky, card };
  }

  // Gesture code removed as transaction form is now an inline card

  function _dailyChangeClass(value) {
    const num = Number(value || 0);
    if (num > 0) return 'is-positive';
    if (num < 0) return 'is-negative';
    return 'is-neutral';
  }

  function _dailyChangeText(value) {
    const num = Number(value || 0);
    const sign = num > 0 ? '+' : '';
    return `${sign}${num.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN`;
  }

  function _summaryCashEffect(txType, value, autoAddCash, availableCash) {
    const amount = Number(value || 0);
    if (!Number.isFinite(amount) || amount <= 0) return '—';
    if (txType === 'BUY') {
      const missing = Math.max(0, amount - Number(availableCash || 0));
      return autoAddCash && missing > 0
        ? `-${_fmtMoney(amount)} · auto top-up ${_fmtMoney(missing)}`
        : `-${_fmtMoney(amount)}`;
    }
    if (txType === 'SELL' || txType === 'DEPOSIT') return `+${_fmtMoney(amount)}`;
    if (txType === 'WITHDRAWAL') return `-${_fmtMoney(amount)}`;
    return '—';
  }

  function _renderHoldingsSkeleton() {
    const tbody = document.getElementById('mgmt-holdings-body');
    if (!tbody) return;
    tbody.innerHTML = Array.from({ length: 5 }).map(() => `
      <tr class="wht-row is-skeleton">
        <td class="wht-td wht-td-company">
          <div class="wht-company">
            <span class="wsk wsk-avatar"></span>
            <div class="wht-company-copy">
              <span class="wsk wsk-line wsk-line-lg"></span>
              <span class="wsk wsk-line wsk-line-sm"></span>
            </div>
          </div>
        </td>
        <td class="wht-td wht-td-r"><span class="wsk wsk-line wsk-line-sm"></span></td>
        <td class="wht-td wht-td-r"><span class="wsk wsk-line wsk-line-md"></span></td>
        <td class="wht-td wht-td-r">
          <div class="wht-daily-stack">
            <span class="wsk wsk-line wsk-line-md"></span>
            <span class="wsk wsk-line wsk-line-sm"></span>
          </div>
        </td>
        <td class="wht-td wht-td-r">
          <div class="wht-alloc">
            <span class="wsk wsk-line wsk-line-sm"></span>
            <div class="wht-alloc-bar"><div class="wsk" style="height:100%;border-radius:2px;width:55%"></div></div>
          </div>
        </td>
        <td class="wht-td wht-td-actions">
          <div class="wht-actions">
            <span class="wsk wsk-btn"></span>
            <span class="wsk wsk-btn"></span>
          </div>
        </td>
      </tr>
    `).join('');
    // Mobile skeleton cards
    const _skelCardsEl = document.getElementById('mgmt-holdings-cards');
    if (_skelCardsEl) {
      _skelCardsEl.innerHTML = Array.from({ length: 4 }).map(() => `
        <div class="whc is-skeleton">
          <div class="whc-main">
            <div class="whc-identity">
              <span class="wsk wsk-avatar"></span>
              <div class="whc-names">
                <span class="wsk wsk-line wsk-line-lg" style="margin-bottom:6px;"></span>
                <span class="wsk wsk-line wsk-line-sm"></span>
              </div>
            </div>
            <div class="whc-financials">
              <span class="wsk wsk-line wsk-line-md" style="margin-bottom:6px;height:15px;"></span>
              <span class="wsk wsk-line wsk-line-sm"></span>
            </div>
          </div>
          <div class="whc-meta-row">
            <div class="whc-meta-line">
              <span class="wsk wsk-line wsk-line-lg"></span>
            </div>
            <div class="whc-alloc-bar"><div class="wsk" style="height:100%;border-radius:2px;width:42%"></div></div>
          </div>
        </div>
      `).join('');
    }
  }

  function _setTradeSyncState(text, mode) {
    const el = document.getElementById('mgmt-trade-sync');
    if (!el) return;
    el.textContent = text || 'Ready';
    el.className = `wallet-settings-pill wallet-settings-pill-muted${mode ? ` is-${mode}` : ''}`;
  }

  function _setPillState(el, text, mode) {
    if (!el) return;
    el.textContent = text || '';
    el.className = `wallet-settings-pill wallet-settings-pill-muted${mode ? ` is-${mode}` : ''}`;
  }

  function _renderTransactionSummary(summary = {}) {
    const summaryEl = document.getElementById('mgmt-transaction-summary');
    if (!summaryEl) return;
    const typeEl = document.getElementById('mgmt-summary-type');
    const tickerEl = document.getElementById('mgmt-summary-ticker');
    const unitsEl = document.getElementById('mgmt-summary-units');
    const valueEl = document.getElementById('mgmt-summary-value');
    const cashEffectEl = document.getElementById('mgmt-summary-cash-effect');
    const { txType = _getTransactionType(), ticker, units, amount, value, autoAddCash = false } = summary;
    const availableCash = _cashBalance();
    const displayTicker = _isCashTransactionType(txType) ? 'CASH' : (ticker || (_selectedHolding && _selectedHolding.ticker) || '—');
    const displayUnits = _isCashTransactionType(txType) ? amount : units;

    if (typeEl) typeEl.textContent = txType || 'Choose a transaction';
    if (tickerEl) tickerEl.textContent = displayTicker || '—';
    if (unitsEl) unitsEl.textContent = _fmtMaybeUnits(displayUnits);
    if (valueEl) valueEl.textContent = Number.isFinite(Number(value)) && Number(value) > 0 ? _fmtMoney(value) : '—';
    if (cashEffectEl) cashEffectEl.textContent = _summaryCashEffect(txType, value, autoAddCash, availableCash);
    summaryEl.classList.toggle('is-ready', Number.isFinite(Number(value)) && Number(value) > 0);
  }

  function handleTransactionDraftChange(changedField) {
    const txType = _getTransactionType();
    const isCashTx = _isCashTransactionType(txType);

    // Cross-calculate price per share ↔ trade value for BUY/SELL
    if (!isCashTx && changedField) {
      const qtyEl   = document.getElementById('mgmt-units-input');
      const priceEl = document.getElementById('mgmt-price-input');
      const totalEl = document.getElementById('mgmt-total-input');
      const qty   = Number(qtyEl   ? qtyEl.value   : 0);
      const price = Number(priceEl ? priceEl.value : 0);
      const total = Number(totalEl ? totalEl.value : 0);

      if (changedField === 'price') {
        _priceInputSource = 'price';
        if (qty > 0 && price > 0 && totalEl) totalEl.value = (qty * price).toFixed(2);
      } else if (changedField === 'total') {
        _priceInputSource = 'total';
        if (qty > 0 && total > 0 && priceEl) priceEl.value = (total / qty).toFixed(txType === 'DIVIDEND' ? 2 : 4);
      } else if (changedField === 'units') {
        if (_priceInputSource === 'price') {
          if (qty > 0 && price > 0 && totalEl) totalEl.value = (qty * price).toFixed(2);
        } else {
          if (qty > 0 && total > 0 && priceEl) priceEl.value = (total / qty).toFixed(txType === 'DIVIDEND' ? 2 : 4);
        }
      }
    }
    const ticker = isCashTx ? 'CASH' : document.getElementById('mgmt-ticker-hidden').value.trim();
    const unitsValue = Number(document.getElementById('mgmt-units-input').value || 0);
    const totalValue = Number(document.getElementById('mgmt-total-input').value || 0);
    const autoAddCash = !!(document.getElementById('mgmt-auto-cash-checkbox') || {}).checked;
    const value = isCashTx ? unitsValue : totalValue;
    const hasDraft = Number.isFinite(value) && value > 0;

    _renderTransactionSummary({
      txType,
      ticker,
      units: isCashTx ? null : unitsValue,
      amount: isCashTx ? unitsValue : null,
      value,
      autoAddCash,
    });

    _setSubmitStatus(hasDraft ? 'Review the summary, then submit' : 'Ready to review');
  }

  function _setSearchStatus(message, type) {
    const el = document.getElementById('mgmt-search-status');
    if (!el) return;
    el.textContent = message || '';
    el.className = `mgmt-search-hint${type ? ` is-${type}` : ''}`;
  }

  function _setSubmitStatus(message, mode) {
    const el = document.getElementById('mgmt-submit-status');
    if (!el) return;
    el.textContent = message || '';
    el.className = `wallet-trade-submit-status${mode ? ` is-${mode}` : ''}`;
  }

  function _syncWalletSelectorChrome() {
    const trigger = document.getElementById('mgmt-wallet-selector-trigger');
    const wrap = document.getElementById('mgmt-portfolio-list-wrap');
    const nameEl = document.getElementById('mgmt-wallet-selector-name');
    const metaEl = document.getElementById('mgmt-wallet-selector-meta');
    const active = _activePortfolio() || _portfolios[0] || { portfolioId: 'summary', name: 'Summary' };
    const metrics = _walletSelectorMetrics(active);
    const compact = _isCompactWalletSelector();

    if (nameEl) nameEl.textContent = active.name || 'Summary';
    if (metaEl) {
      metaEl.textContent = `${_fmtMoney(metrics.total)} · ${_fmtSignedPct(metrics.dailyPct)}`;
      metaEl.className = `wallet-selector-trigger-meta ${_dailyChangeClass(metrics.dailyPct)}`;
    }
    if (trigger) {
      trigger.setAttribute('aria-expanded', _walletSelectorOpen ? 'true' : 'false');
      trigger.classList.toggle('is-open', _walletSelectorOpen);
      trigger.classList.toggle('is-compact', compact);
    }
    if (wrap) {
      wrap.hidden = !_walletSelectorOpen;
      wrap.setAttribute('aria-hidden', _walletSelectorOpen ? 'false' : 'true');
      wrap.classList.toggle('is-open', _walletSelectorOpen);
      wrap.classList.toggle('is-compact', compact);
    }
    // Mobile: update chip strip active state
    const chipsEl = document.getElementById('mgmt-wallet-chips-strip');
    if (chipsEl) {
      const activeId = String(_activePortId || '');
      chipsEl.querySelectorAll('.wallet-chip').forEach(chip => {
        const isActive = chip.dataset.id === activeId;
        chip.classList.toggle('is-active', isActive);
        chip.setAttribute('aria-selected', isActive);
      });
      const activeChip = chipsEl.querySelector('.wallet-chip.is-active');
      if (activeChip) activeChip.scrollIntoView({ block: 'nearest', inline: 'start', behavior: 'smooth' });
    }
    // Mobile: update wallet summary bar
    const mobileName = document.getElementById('mgmt-mobile-wallet-name');
    const mobileTotal = document.getElementById('mgmt-mobile-wallet-total');
    const mobilePct = document.getElementById('mgmt-mobile-wallet-pct');
    if (mobileName) mobileName.textContent = active.name || 'Summary';
    if (mobileTotal) mobileTotal.textContent = _fmtMoney(metrics.total);
    if (mobilePct) {
      mobilePct.textContent = _fmtSignedPct(metrics.dailyPct);
      mobilePct.className = `wallet-mobile-summary-pct ${_dailyChangeClass(metrics.dailyPct)}`;
    }
  }

  function _setWalletSelectorOpen(nextOpen, options = {}) {
    const compact = _isCompactWalletSelector();
    _walletSelectorOpen = compact ? !!nextOpen : (options.force ? !!nextOpen : true);
    _syncWalletSelectorChrome();
    if (_walletSelectorOpen) {
      requestAnimationFrame(() => {
        const active = document.querySelector('#mgmt-portfolio-list .mgmt-portfolio-item.active');
        active?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
      });
    }
  }

  function toggleWalletSelector() {
    _setWalletSelectorOpen(!_walletSelectorOpen, { force: true });
  }

  function toggleWalletOverflow() {
    const menu = document.getElementById('mgmt-wallet-overflow-menu');
    if (!menu) return;
    const wasHidden = menu.hidden;
    menu.hidden = !wasHidden;
    menu.setAttribute('aria-hidden', wasHidden ? 'false' : 'true');
  }

  function _clearDropdown() {
    const dropdown = document.getElementById('mgmt-ticker-dropdown');
    if (!dropdown) return;
    dropdown.style.display = 'none';
    dropdown.innerHTML = '';
    _searchResults = [];
    _searchActiveIndex = -1;
  }

  function _clearValidationState() {
    document.querySelectorAll('#tab-wallets .mgmt-input-invalid').forEach(el => el.classList.remove('mgmt-input-invalid'));
    const errorsEl = document.getElementById('mgmt-form-errors');
    if (errorsEl) {
      errorsEl.style.display = 'none';
      errorsEl.innerHTML = '';
    }
  }

  function _showValidationErrors(errors, invalidIds) {
    _clearValidationState();
    (invalidIds || []).forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.add('mgmt-input-invalid');
    });
    const errorsEl = document.getElementById('mgmt-form-errors');
    if (!errorsEl || !errors || !errors.length) return;
    errorsEl.innerHTML = errors.map(msg => `<div>${_esc(msg)}</div>`).join('');
    errorsEl.style.display = 'block';
  }

  function _findCurrentHolding(ticker, name) {
    return (_currentHoldings || []).find(h => {
      if (ticker && h.ticker && String(h.ticker).toUpperCase() === String(ticker).toUpperCase()) return true;
      return String(h.name || '').trim().toLowerCase() === String(name || '').trim().toLowerCase();
    }) || null;
  }

  function _getLivePricePLN(symbol, name) {
    if (!symbol || String(symbol).toUpperCase() === 'CASH') return null;
    const cleanSym = String(symbol).trim().toUpperCase();
    const cleanName = String(name || '').trim().toLowerCase();

    // 1. Check current portfolio holdings
    const existing = _findCurrentHolding(cleanSym, name);
    if (existing) {
      if (Number.isFinite(Number(existing.pricePLN)) && Number(existing.pricePLN) > 0) {
        return Number(existing.pricePLN);
      }
      if (Number(existing.currentValue) > 0 && Number(existing.units) > 0) {
        return Number(existing.currentValue) / Number(existing.units);
      }
    }

    // 2. Check Summary holdings (PORTFOLIO_DATA)
    if (typeof window !== 'undefined' && Array.isArray(window.PORTFOLIO_DATA)) {
      const h = window.PORTFOLIO_DATA.find(item =>
        (item.ticker && String(item.ticker).toUpperCase() === cleanSym) ||
        (cleanName && item.name && String(item.name).trim().toLowerCase() === cleanName)
      );
      if (h) {
        if (Number.isFinite(Number(h.pricePLN)) && Number(h.pricePLN) > 0) {
          return Number(h.pricePLN);
        }
        if (Number(h.currentValue) > 0 && Number(h.units) > 0) {
          return Number(h.currentValue) / Number(h.units);
        }
      }
    }

    // 3. Check WALLET_HOLDINGS
    if (typeof window !== 'undefined' && window.WALLET_HOLDINGS && typeof window.WALLET_HOLDINGS === 'object') {
      for (const walletName of Object.keys(window.WALLET_HOLDINGS)) {
        const list = window.WALLET_HOLDINGS[walletName] || [];
        const h = list.find(item =>
          (item.ticker && String(item.ticker).toUpperCase() === cleanSym) ||
          (cleanName && item.name && String(item.name).trim().toLowerCase() === cleanName)
        );
        if (h) {
          if (Number.isFinite(Number(h.pricePLN)) && Number(h.pricePLN) > 0) {
            return Number(h.pricePLN);
          }
          if (Number(h.currentValue) > 0 && Number(h.units) > 0) {
            return Number(h.currentValue) / Number(h.units);
          }
        }
      }
    }

    return null;
  }

  async function _fetchStockPricePLN(symbol) {
    if (!symbol || symbol.toUpperCase() === 'CASH' || symbol.startsWith('TFI:')) return null;
    try {
      if (typeof window.PortfolioClient !== 'undefined' && typeof window.PortfolioClient.getBenchmarkDaily === 'function') {
        const res = await window.PortfolioClient.getBenchmarkDaily(symbol, true);
        if (res && Array.isArray(res.daily) && res.daily.length > 0) {
          const lastCandle = res.daily[res.daily.length - 1];
          let price = Number(lastCandle.close || 0);
          if (price > 0) {
            if (!symbol.toUpperCase().endsWith('.WA')) {
              let rate = 4.0;
              try {
                const usdRes = await window.PortfolioClient.getBenchmarkDaily('USDPLN=X', true);
                if (usdRes && Array.isArray(usdRes.daily) && usdRes.daily.length > 0) {
                  const usdCandle = usdRes.daily[usdRes.daily.length - 1];
                  if (Number(usdCandle.close) > 0) rate = Number(usdCandle.close);
                }
              } catch (_) {}
              price = price * rate;
            }
            return price;
          }
        }
      }
    } catch (_) {}
    return null;
  }

  function _isCashTransactionType(txType) {
    return txType === 'DEPOSIT' || txType === 'WITHDRAWAL';
  }

  function _isCashHolding(holding) {
    if (!holding) return false;
    if (String(holding.holdingId || '') === '__cash__') return true;
    if (holding.ticker) return false;
    const name = String(holding.name || '').trim().toLowerCase();
    return name.includes('cash') || name.includes('got') || name.includes('konto');
  }

  function _findCashHolding() {
    return (_currentHoldings || []).find(_isCashHolding) || null;
  }

  function _cashBalance() {
    const cash = _findCashHolding();
    return Number((cash && (cash.currentValue || cash.purchaseValue || cash.units)) || 0);
  }

  function _isTransactionsPanelOpen() {
    const card = document.getElementById('wallet-transaction-card');
    return !!(card && card.style.display !== 'none');
  }

  function _setCreateComposerOpen(open) {
    _createComposerOpen = !!open;
    const wrap = document.getElementById('mgmt-create-row-wrap');
    const btn = document.getElementById('mgmt-toggle-create-btn');
    if (wrap) {
      wrap.hidden = !_createComposerOpen;
      wrap.setAttribute('aria-hidden', _createComposerOpen ? 'false' : 'true');
      wrap.classList.toggle('is-open', _createComposerOpen);
    }
    if (btn) btn.textContent = _createComposerOpen ? 'Done' : '+ Wallet';
    if (_createComposerOpen) {
      setTimeout(() => {
        const input = document.getElementById('mgmt-new-port-name');
        if (input) input.focus();
      }, 20);
    }
  }

  function toggleCreatePortfolioComposer(forceState) {
    _setCreateComposerOpen(typeof forceState === 'boolean' ? forceState : !_createComposerOpen);
  }

  function _setWalletStickyCondensed(condensed) {
    const { sticky, card } = _walletStickyElements();
    const nextCondensed = !!condensed && _isCompactWalletSelector() && _isWalletsTabActive();
    _walletStickyCondensed = nextCondensed;
    if (sticky) sticky.classList.toggle('is-condensed', nextCondensed);
    if (card) card.classList.toggle('is-condensed', nextCondensed);
    if (nextCondensed) {
      if (_walletSelectorOpen) _setWalletSelectorOpen(false, { force: true });
      if (_createComposerOpen) _setCreateComposerOpen(false);
    }
  }

  function _syncWalletStickyCondensed(forceExpand = false) {
    const { sentinel, sticky } = _walletStickyElements();
    if (!_isCompactWalletSelector() || !_isWalletsTabActive() || !sticky || !sentinel) {
      _setWalletStickyCondensed(false);
      _walletStickyLastScrollY = _pageScrollTop();
      return;
    }
    const scrollY = _pageScrollTop();
    const pinned = sentinel.getBoundingClientRect().top <= 10;
    const scrollingDown = scrollY > _walletStickyLastScrollY + 6;
    const scrollingUp = scrollY < _walletStickyLastScrollY - 6;
    const shouldCondense = !forceExpand && pinned && (scrollingDown || (_walletStickyCondensed && !scrollingUp));
    const shouldExpand = forceExpand || !pinned || scrollY <= 24 || scrollingUp;

    if (shouldExpand) {
      _setWalletStickyCondensed(false);
    } else if (shouldCondense) {
      _setWalletStickyCondensed(true);
    }
    _walletStickyLastScrollY = scrollY;
  }

  function _bindWalletStickyBehavior() {
    if (_walletStickyBound) return;
    const onScroll = () => _syncWalletStickyCondensed(false);
    window.addEventListener('scroll', onScroll, { passive: true });
    _walletStickyBound = true;
    _walletStickyLastScrollY = _pageScrollTop();
  }

  function _syncTransactionsPanel() {
    const overlay = document.getElementById('mgmt-transaction-overlay');
    const tradeView = document.getElementById('mgmt-overlay-trade');
    const overlayTitle = document.getElementById('mgmt-overlay-title');
    const openTradeBtn = document.getElementById('mgmt-open-trade-btn');
    const inlineStatus = document.getElementById('mgmt-inline-status');
    const portfolio = _activePortfolio();
    const isSummary = _isSummaryPortfolio(_activePortId);

    if (tradeView) tradeView.hidden = false;
    if (overlayTitle) {
      overlayTitle.textContent = `${portfolio ? portfolio.name : 'Wallet'} transaction`;
    }
    if (openTradeBtn) {
      openTradeBtn.disabled = isSummary;
      openTradeBtn.classList.toggle('is-disabled', isSummary);
      openTradeBtn.textContent = isSummary ? 'Summary is read only' : 'New transaction';
    }
    if (inlineStatus) {
      if (isSummary) {
        _setPillState(inlineStatus, 'Summary stays stable and read only', '');
      } else if (_isTransactionsPanelOpen()) {
        _setPillState(inlineStatus, 'Trading in focused panel', '');
      } else {
        _setPillState(inlineStatus, 'Stable holdings layout', '');
      }
    }
    if (overlay) overlay.dataset.mode = 'trade';
  }

  function openTransactionsPanel(mode = 'trade') {
    const card = document.getElementById('wallet-transaction-card');
    if (!card) return;
    
    _transactionsPanelMode = mode === 'history' ? 'history' : 'trade';
    _syncTransactionsPanel();
    
    // Show card inline
    card.style.display = 'flex';
    
    // Scroll to the card smoothly so user sees it
    requestAnimationFrame(() => {
        card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    if (_transactionsPanelMode === 'trade') {
      setTimeout(() => {
        const target = document.getElementById(_selectedHolding ? 'mgmt-units-input' : 'mgmt-search-input');
        if (target) target.focus();
      }, 180);
    }
  }

  function closeTransactionsPanel() {
    const card = document.getElementById('wallet-transaction-card');
    if (!card) return;
    
    card.style.display = 'none';
    _syncTransactionsPanel();
    _setSubmitStatus('Ready to review');
  }

  function setTransactionsPanelMode(_mode) {
    _transactionsPanelMode = 'trade';
    _syncTransactionsPanel();
    if (document.getElementById('wallet-transaction-card')?.style.display === 'none') {
        openTransactionsPanel('trade');
    }
  }

  function _setSelectedHolding(holding) {
    _selectedHolding = holding;
    _updateTransactionFormState();
  }

  function _resetTransactionForm(options = {}) {
    const keepType = !!options.keepType;
    const txTypeEl = document.getElementById('mgmt-transaction-type');
    if (txTypeEl && !keepType) txTypeEl.value = 'BUY';
    const searchInput = document.getElementById('mgmt-search-input');
    const tickerInput = document.getElementById('mgmt-ticker-hidden');
    const nameInput = document.getElementById('mgmt-holding-name-hidden');
    const qtyInput = document.getElementById('mgmt-units-input');
    const totalInput = document.getElementById('mgmt-total-input');
    const priceInput = document.getElementById('mgmt-price-input');
    const commissionInput = document.getElementById('mgmt-commission-input');
    const commentInput = document.getElementById('mgmt-comment-input');
    const autoCashInput = document.getElementById('mgmt-auto-cash-checkbox');
    const confirm = document.getElementById('mgmt-holding-confirm');
    const dateEl = document.getElementById('mgmt-transaction-date');
    const todayStr = new Date().toISOString().slice(0, 10);
    if (dateEl) {
      dateEl.max = todayStr;
      if (!dateEl.value || dateEl.value > todayStr) {
        dateEl.value = todayStr;
      }
    }
    if (searchInput) searchInput.value = '';
    if (tickerInput) tickerInput.value = '';
    if (nameInput) nameInput.value = '';
    if (qtyInput) qtyInput.value = '';
    if (totalInput) totalInput.value = '';
    if (priceInput) priceInput.value = '';
    _priceInputSource = 'price';
    if (commissionInput) commissionInput.value = '';
    if (commentInput) commentInput.value = '';
    if (autoCashInput) autoCashInput.checked = false;
    if (confirm) confirm.style.display = 'none';
    _selectedHolding = null;
    _clearDropdown();
    _clearValidationState();
    _setSearchStatus('Type to search Yahoo Finance · use arrows and Enter to select');
    // Reset TFI state
    const tfiCodeInput = document.getElementById('mgmt-tfi-code-input');
    if (tfiCodeInput) tfiCodeInput.value = '';
    _searchSource = 'yf';
    _syncSearchSourceView();
    _setTfiStatus('Enter the bankier.pl fund code and press Lookup. <a href="https://www.bankier.pl/fundusze" target="_blank" rel="noopener noreferrer">Browse funds →</a>');
    _setTradeSyncState('Ready');
    _setSubmitStatus('Ready to review');
    _renderTransactionSummary();
    _updateTransactionFormState();
    _syncTransactionsPanel();
  }

  function _renderSettings(portfolio, holdingsCount, txCount) {
    const titleEl = document.getElementById('mgmt-holdings-title');
    const summaryEl = document.getElementById('mgmt-settings-summary');
    const actionsEl = document.getElementById('mgmt-settings-actions');
    const subtitleEl = document.getElementById('mgmt-holdings-subtitle');
    const inlineStatus = document.getElementById('mgmt-inline-status');
    const tradeCard = document.querySelector('.wallet-card-trade');
    const benchmarkSettingEl = document.getElementById('mgmt-benchmark-setting');
    const annualReturnContentEl = document.getElementById('mgmt-annual-return-content');
    const summary = _walletSummaryFor(portfolio) || { total: 0, dailyPLN: 0, dailyPct: 0, annualReturn: 0 };
    const isSummary = _isSummaryPortfolio(portfolio && portfolio.portfolioId);

    if (titleEl) titleEl.textContent = portfolio ? portfolio.name : 'Select a portfolio';
    if (subtitleEl) subtitleEl.textContent = isSummary
      ? 'Aggregated holdings across all wallets. Summary is pinned and read-only.'
      : 'Live value, allocation, and quick trade actions.';
    if (summaryEl) {
      summaryEl.innerHTML = isSummary
        ? `Summary is auto-calculated from all wallets. Current total: <strong>${Number(summary.total || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN</strong>.`
        : `Live total: <strong>${Number(summary.total || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN</strong> · Daily <strong>${Number(summary.dailyPLN || 0) >= 0 ? '+' : ''}${Number(summary.dailyPLN || 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN (${Number(summary.dailyPct || 0) >= 0 ? '+' : ''}${Number(summary.dailyPct || 0).toFixed(2)}%)</strong> · ${holdingsCount} holdings · ${txCount} transactions.`;
    }
    if (actionsEl) {
        actionsEl.innerHTML = isSummary ? `
        <span class="wallet-settings-pill">Summary pinned first</span>
        <button class="mgmt-icon-btn wallet-settings-btn" title="Wallet Settings"
          onclick="window._mgmt.openWalletSettingsModal()">⚙️ Settings</button>
      ` : `
        <button class="mgmt-icon-btn wallet-settings-btn" title="Wallet Settings"
          onclick="window._mgmt.openWalletSettingsModal()">⚙️ Settings</button>
      `;
    }
    if (tradeCard) tradeCard.style.display = isSummary && _transactionsPanelMode === 'trade' ? 'none' : '';
    // Quick Entry is now always visible
    if (inlineStatus && !isSummary && !_isTransactionsPanelOpen()) {
      _setPillState(inlineStatus, `Stable holdings · ${holdingsCount} positions · ${txCount} entries`, '');
    }
    _syncTransactionsPanel();
    // Render ATH section for the selected wallet
    if (typeof window.renderWalletAthSection === 'function') {
      const athKey = portfolio ? (isSummary ? 'Summary' : portfolio.name) : null;
      window.renderWalletAthSection(athKey);
    }

    if (benchmarkSettingEl) {
        benchmarkSettingEl.style.display = isSummary ? '' : 'none';
    }

    if (annualReturnContentEl) {
        if (typeof summary.annualReturn === 'number') {
            annualReturnContentEl.textContent = `${summary.annualReturn > 0 ? '+' : ''}${(summary.annualReturn * 100).toFixed(2)}% / yr`;
            annualReturnContentEl.className = `wob-value-bold ${_dailyChangeClass(summary.annualReturn)}`;
        } else {
            annualReturnContentEl.textContent = '--';
            annualReturnContentEl.className = 'wob-value-bold';
        }
    }
  }

  // ── Load portfolios from DynamoDB ────────────────────────────
  async function _loadPortfolios() {
    const _chipsEl = document.getElementById('mgmt-wallet-chips-strip');
    if (_chipsEl) _chipsEl.innerHTML = '<div class="mgmt-loading" style="padding-left:16px;">Loading…</div>';
    try {
      const data = await PortfolioClient.listPortfolios();
      const realPortfolios = (data.portfolios || []).sort((a,b) => (a.order||99)-(b.order||99));
      _portfolios = [{
        portfolioId: 'summary',
        name: 'Summary',
        type: 'virtual',
        currency: 'PLN',
        order: -1,
      }, ...realPortfolios];
      _setWalletSelectorOpen(!_isCompactWalletSelector(), { force: true });
      _renderPortfolioList();


      const targetId = _portfolios.some(p => p.portfolioId === _activePortId)
        ? _activePortId
        : (_portfolios[0] && _portfolios[0].portfolioId);
      if (targetId) await selectPortfolio(targetId);
    } catch(e) {
      el.innerHTML = `<div class="mgmt-error">Failed to load portfolios: ${_esc(e.message)}</div>`;
    }
  }

  function _renderPortfolioList() {
    const _chipsEl = document.getElementById('mgmt-wallet-chips-strip');
    if (_chipsEl) {
      // Build chip buttons
      _chipsEl.innerHTML = _portfolios.map(p => {
        const isActive = _activePortId === p.portfolioId;
        return `<button type="button"
             class="wallet-chip${isActive ? ' is-active' : ''}"
             data-id="${_esc(p.portfolioId)}"
             role="option"
             aria-selected="${isActive}"
             onclick="window._mgmt.selectPortfolio('${_esc(p.portfolioId)}')">`
          + `<span class="wallet-chip-top">`
            + `<span class="wallet-chip-dot" style="background:${_esc(_portfolioColor(p.name))}"></span>`
            + `<span class="wallet-chip-name">${_esc(p.name)}</span>`
          + `</span>`
          + `<span class="wallet-chip-value">${_fmtMoney(_walletSelectorMetrics(p).total)}</span>`
          + `</button>`;
      }).join('');

      // Build dot indicators
      const dotsEl = document.getElementById('mgmt-wallet-chips-dots');
      if (dotsEl) {
        dotsEl.innerHTML = _portfolios.map((p, i) => {
          const isActive = _activePortId === p.portfolioId;
          return `<button class="wallet-chips-dot${isActive ? ' is-active' : ''}"
                  data-carousel-index="${i}"
                  aria-label="${_esc(p.name)}"
                  onclick="window._mgmt._carouselGoTo(${i})"></button>`;
        }).join('');
      }

      // Attach scroll → dot sync listener once
      if (!_chipsEl._carouselBound) {
        _chipsEl._carouselBound = true;
        _chipsEl.addEventListener('scroll', () => {
          const chips = Array.from(_chipsEl.querySelectorAll('.wallet-chip'));
          if (!chips.length) return;
          const mid = _chipsEl.scrollLeft + _chipsEl.clientWidth / 2;
          let best = 0, minDist = Infinity;
          chips.forEach((c, i) => {
            const dist = Math.abs(c.offsetLeft + c.offsetWidth / 2 - mid);
            if (dist < minDist) { minDist = dist; best = i; }
          });
          document.querySelectorAll('#mgmt-wallet-chips-dots .wallet-chips-dot')
            .forEach((d, i) => d.classList.toggle('is-active', i === best));
        }, { passive: true });
      }
    }
    _syncWalletSelectorChrome();
  }

  // Scroll carousel to the chip at given index and select it
  function _carouselGoTo(index) {
    const strip = document.getElementById('mgmt-wallet-chips-strip');
    if (!strip) return;
    const chips = Array.from(strip.querySelectorAll('.wallet-chip'));
    if (!chips[index]) return;
    chips[index].scrollIntoView({ block: 'nearest', inline: 'start', behavior: 'smooth' });
    const id = chips[index].dataset.id;
    if (id) selectPortfolio(id);
  }


  // ── Select portfolio → show its holdings ─────────────────────
  async function selectPortfolio(portfolioId) {
    _activePortId = portfolioId;
    _renderPortfolioList();
    _syncWalletSelectorChrome();
    if (_isCompactWalletSelector()) _setWalletSelectorOpen(false, { force: true });

    const panel = document.getElementById('mgmt-holdings-panel');
    // Panel is always in-flow (no display:none). Just ensure it's visible.
    if (panel && panel.style.display === 'none') panel.style.display = '';

    const p = _portfolios.find(x => x.portfolioId === portfolioId);
    const tbody = document.getElementById('mgmt-holdings-body');
    const holdingsMeta = document.getElementById('mgmt-holdings-meta');
    const cemeteryBody = document.getElementById('mgmt-cemetery-body');
    const cemeteryMeta = document.getElementById('mgmt-cemetery-meta');
    const valueHistoryBody = document.getElementById('mgmt-value-history-body');
    const valueHistoryMeta = document.getElementById('mgmt-value-history-meta');
    _renderHoldingsSkeleton();
    if (holdingsMeta) _setPillState(holdingsMeta, 'Loading holdings…', 'syncing');
    if (cemeteryBody) cemeteryBody.innerHTML = '<tr><td colspan="3" class="cemetery-empty">Loading closed positions…</td></tr>';
    if (cemeteryMeta) _setPillState(cemeteryMeta, 'Loading archive…', 'syncing');
    const txBody = document.getElementById('mgmt-transactions-body');
    if (txBody) txBody.innerHTML = '<tr><td colspan="7" class="mgmt-loading">Loading…</td></tr>';
    if (valueHistoryBody) valueHistoryBody.innerHTML = '<tr><td colspan="3" class="mgmt-loading" style="text-align:center;padding:20px;">Loading…</td></tr>';
    if (valueHistoryMeta) _setPillState(valueHistoryMeta, 'Loading snapshots…', 'syncing');

    if (!p) return;

    if (_isSummaryPortfolio(portfolioId)) {
      const holdings = _mergeHoldings([], _liveHoldingsFor(p));
      _currentHoldings = holdings;
      const sourcePortfolioIds = (_portfolios || [])
        .filter((port) => !_isSummaryPortfolio(port.portfolioId))
        .map((port) => port.portfolioId);
      const summaryTxResponses = await Promise.all(
        sourcePortfolioIds.map((pid) => PortfolioClient.listTransactions(pid, 5000).catch(() => ({ transactions: [] })))
      );
      _currentTransactions = summaryTxResponses.flatMap((response, idx) => {
        const pid = sourcePortfolioIds[idx];
        const rows = (response && response.transactions) || [];
        return rows.map((tx) => ({ ...tx, portfolioId: tx.portfolioId || pid }));
      });
      _currentClosedHoldings = [];
      try {
        const snapshotData = await PortfolioClient.listSnapshots(portfolioId);
        _currentSnapshots = snapshotData.snapshots || [];
      } catch (_) {
        _currentSnapshots = [];
      }
      _renderSettings(p, holdings.length, _currentTransactions.length);
      _renderHoldings(portfolioId, holdings, true);
      if (txBody) {
        txBody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#888;padding:20px;">Summary is aggregated across wallets. Open an individual wallet to inspect its transactions.</td></tr>';
      }
      _renderValueHistory(_currentSnapshots);
      _resetTransactionForm({ keepType: false });
      _syncTransactionsPanel();
      return;
    }

    try {
      const [data, snapshotData] = await Promise.all([
        PortfolioClient.getPortfolio(portfolioId),
        PortfolioClient.listSnapshots(portfolioId),
      ]);
      const holdings = _mergeHoldings(data.holdings || [], _liveHoldingsFor(p));
      const transactions = data.transactions || [];
      const closedHoldings = data.closedHoldings || [];
      const snapshots = snapshotData.snapshots || [];
      _currentHoldings = holdings;
      _currentTransactions = transactions;
      _currentClosedHoldings = closedHoldings;
      _currentSnapshots = snapshots;
      _renderSettings(p, holdings.length, transactions.length);
      _renderHoldings(portfolioId, holdings, false);
      _renderTransactions(transactions);
      _renderValueHistory(snapshots);
      _resetTransactionForm({ keepType: false });
      _syncTransactionsPanel();
    } catch(e) {
      _currentHoldings = [];
      _currentTransactions = [];
      _currentClosedHoldings = [];
      _currentSnapshots = [];
      _renderSettings(p, 0, 0);
      tbody.innerHTML = `<tr><td colspan="7" class="mgmt-error">Error: ${_esc(e.message)}</td></tr>`;
      if (txBody) txBody.innerHTML = `<tr><td colspan="7" class="mgmt-error">Error: ${_esc(e.message)}</td></tr>`;
      if (valueHistoryBody) valueHistoryBody.innerHTML = `<tr><td colspan="3" class="mgmt-error" style="text-align:center;padding:20px;">Error: ${_esc(e.message)}</td></tr>`;
      if (valueHistoryMeta) _setPillState(valueHistoryMeta, 'Unable to load snapshots', 'error');
      if (holdingsMeta) _setPillState(holdingsMeta, 'Unable to load holdings', 'error');
      _syncTransactionsPanel();
    }
  }

  function _renderHoldings(portfolioId, holdings, isSummary) {
    const tbody = document.getElementById('mgmt-holdings-body');
    const cardsEl = document.getElementById('mgmt-holdings-cards');
    const metaEl = document.getElementById('mgmt-holdings-meta');
    if (!tbody) return;

    const performance = _buildHoldingPerformance(_currentTransactions, _currentClosedHoldings, { aggregateByTicker: isSummary });
    const activeHoldings = holdings.filter(h => _isCashHolding(h) || Number(h.units || 0) > 0.00000001);

    if (activeHoldings.length === 0) {
      const _emptyMsg = isSummary
        ? 'No holdings yet — create a wallet and add transactions to populate Summary.'
        : 'No holdings yet — add one using the trade flow.';
      tbody.innerHTML = `<tr class="wht-row"><td colspan="6" class="wht-td" style="text-align:center;color:#888;padding:36px 20px;">${_emptyMsg}</td></tr>`;
      if (cardsEl) cardsEl.innerHTML = `<div class="whc-empty">${_emptyMsg}</div>`;
      if (metaEl) _setPillState(metaEl, isSummary ? 'Summary waiting for wallets' : 'No holdings yet', '');
      _renderCemetery(holdings, performance, isSummary, portfolioId);
      return;
    }

    if (metaEl) {
      const cashCount = activeHoldings.filter(_isCashHolding).length;
      const liveCount = activeHoldings.length - cashCount;
      _setPillState(metaEl, `${liveCount} holdings${cashCount ? ` · ${cashCount} cash` : ''}`, '');
    }

    // SVG icons for buy (arrow-up) and sell (arrow-down)
    const _svgUp   = `<svg class="wht-btn-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 13V3M3 8l5-5 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    const _svgDown = `<svg class="wht-btn-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 3v10M3 8l5 5 5-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

    // ── Desktop table rows ──────────────────────────────────────
    tbody.innerHTML = activeHoldings.map(h => {
      const _cv      = Number.isFinite(Number(h.currentValue)) ? Number(h.currentValue) : Number(h.purchaseValue || 0);
      const _isCash  = _isCashHolding(h);
      const _isTfi   = !_isCash && String(h.ticker || '').startsWith('TFI:');
      const _dispTicker = _isCash ? 'CASH' : (_isTfi ? h.ticker.replace('TFI:', '') : (h.ticker || '—'));
      const _dailyPct   = Number(h.dailyChangePct || 0);
      const _alloc      = Math.min(100, Number(h.pct || 0));
      const _dClass     = _dailyChangeClass(h.dailyChangePLN);
      const _performance = _holdingPerformanceFor(h, performance);
      const _realized = Number(_performance.realized || 0);
      const _realizedBadge = !_isCash && Math.abs(_realized) >= 0.005
        ? `<span class="wht-realized ${_realized >= 0 ? 'is-positive' : 'is-negative'}">Past Realized: ${_fmtSignedMoney(_realized)} (AVCO)</span>`
        : '';

      let _actionHtml;
      if (isSummary) {
        _actionHtml = '<span class="wht-badge wht-badge-readonly" tabindex="0" title="Select a specific wallet to make transactions for this asset. Summary is an aggregated read-only view." data-tooltip="Select a specific wallet to make transactions for this asset. Summary is an aggregated read-only view.">Read only</span>';
      } else if (_isCash) {
        _actionHtml = '<span class="wht-badge wht-badge-cash">Cash</span>';
      } else {
        _actionHtml = `
          <div class="wht-actions">
            <button class="wht-btn wht-btn-buy" type="button" title="Buy more" aria-label="Buy more ${_esc(h.name)}"
              onclick="window._mgmt.prefillBuy('${_esc(h.holdingId)}','${_esc(h.ticker||'')}','${_esc(h.name)}',${Number(h.units||0)})">${_svgUp}</button>
            <button class="wht-btn wht-btn-sell" type="button" title="Sell" aria-label="Sell ${_esc(h.name)}"
              onclick="window._mgmt.prefillSell('${_esc(h.holdingId)}','${_esc(h.ticker||'')}','${_esc(h.name)}',${Number(h.units||0)})">${_svgDown}</button>
          </div>`;
      }

      return `
        <tr class="wht-row${h.pending ? ' is-pending' : ''}${_isCash ? ' is-cash' : ''}" tabindex="0">
          <td class="wht-td wht-td-company">
            <div class="wht-company${_isCash ? '' : ' wht-company-clickable'}"${_isCash ? '' : ` onclick="window.openAnalysisForTicker('${_esc(h.ticker || h.name)}'); event.stopPropagation();" style="cursor:pointer;"`}>
              ${_logoHtml(h.name, h.ticker)}
              <div class="wht-company-copy">
                <span class="wht-company-name">${_esc(h.name)}</span>
                <span class="wht-company-ticker">${_esc(_dispTicker)}</span>
                ${_realizedBadge}
              </div>
            </div>
          </td>
          <td class="wht-td wht-td-r wht-td-num">${_fmtUnits(h.units)}</td>
          <td class="wht-td wht-td-r wht-td-value">${_fmtMoney(_cv)}</td>
          <td class="wht-td wht-td-r wht-td-today">
            <div class="wht-daily-stack">
              <span class="wht-daily-pln ${_dClass}">${_dailyChangeText(h.dailyChangePLN)}</span>
              <span class="wht-daily-pct ${_dClass}">${_fmtSignedPct(_dailyPct)}</span>
            </div>
          </td>
          <td class="wht-td wht-td-r wht-td-alloc">
            <div class="wht-alloc">
              <span class="wht-alloc-num">${_alloc.toFixed(1)}%</span>
              <div class="wht-alloc-bar"><div class="wht-alloc-fill" style="width:${_alloc}%"></div></div>
            </div>
          </td>
          <td class="wht-td wht-td-actions">${_actionHtml}</td>
        </tr>`;
    }).join('');

    // ── Mobile holding cards ────────────────────────────────────
    if (cardsEl) {
      const _svgUpMobile   = `<svg class="whc-btn-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 13V3M3 8l5-5 5 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      const _svgDownMobile = `<svg class="whc-btn-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 3v10M3 8l5 5 5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

      cardsEl.innerHTML = activeHoldings.map(h => {
        const _cv     = Number.isFinite(Number(h.currentValue)) ? Number(h.currentValue) : Number(h.purchaseValue || 0);
        const _isCash = _isCashHolding(h);
        const _isTfi  = !_isCash && String(h.ticker || '').startsWith('TFI:');
        const _dispTicker = _isCash ? 'Cash' : (_isTfi ? h.ticker.replace('TFI:', '') + ' · TFI' : (h.ticker || '—'));
        const _dailyPct   = Number(h.dailyChangePct || 0);
        const _alloc      = Math.min(100, Number(h.pct || 0));
        const _dClass     = _dailyChangeClass(h.dailyChangePLN);
        const _performance = _holdingPerformanceFor(h, performance);
        const _realized = Number(_performance.realized || 0);
        const _realizedBadge = !_isCash && Math.abs(_realized) >= 0.005
          ? `<span class="wht-realized ${_realized >= 0 ? 'is-positive' : 'is-negative'}">Past Realized: ${_fmtSignedMoney(_realized)} (AVCO)</span>`
          : '';

        return `
          <div class="whc${_isCash ? ' is-cash' : ''}${h.pending ? ' is-pending' : ''}">
            <div class="whc-main">
              <div class="whc-identity${_isCash ? '' : ' whc-identity-clickable'}"${_isCash ? '' : ` onclick="window.openAnalysisForTicker('${_esc(h.ticker || h.name)}'); event.stopPropagation();" style="cursor:pointer;"`}>
                ${_logoHtml(h.name, h.ticker)}
                <div class="whc-names">
                  <span class="whc-name">${_esc(h.name)}</span>
                  <span class="whc-ticker">${_esc(_dispTicker)}</span>
                  ${_realizedBadge}
                </div>
              </div>
              <div class="whc-financials">
                <span class="whc-value">${_fmtMoney(_cv)}</span>
                <span class="whc-daily ${_dClass}">${_dailyChangeText(h.dailyChangePLN)}</span>
              </div>
            </div>
            <div class="whc-meta-row">
              <div class="whc-meta-line">
                <span class="whc-meta">${_fmtUnits(h.units)} ${_isCash ? 'PLN' : 'units'} · ${_alloc.toFixed(1)}%</span>
                <span class="whc-meta whc-meta-pct ${_dClass}">${_fmtSignedPct(_dailyPct)}</span>
              </div>
              <div class="whc-alloc-bar"><div class="whc-alloc-fill" style="width:${_alloc}%"></div></div>
            </div>
            ${isSummary ? `
            <div class="whc-actions whc-actions-readonly">
              <span class="wht-badge wht-badge-readonly" tabindex="0" title="Select a specific wallet to make transactions for this asset. Summary is an aggregated read-only view." data-tooltip="Select a specific wallet to make transactions for this asset. Summary is an aggregated read-only view.">Read only</span>
            </div>` : (_isCash ? '' : `
            <div class="whc-actions">
              <button class="whc-btn whc-btn-buy" type="button" aria-label="Buy ${_esc(h.name)}"
                onclick="window._mgmt.prefillBuy('${_esc(h.holdingId)}','${_esc(h.ticker||'')}','${_esc(h.name)}',${Number(h.units||0)})">${_svgUpMobile} Buy</button>
              <button class="whc-btn whc-btn-sell" type="button" aria-label="Sell ${_esc(h.name)}"
                onclick="window._mgmt.prefillSell('${_esc(h.holdingId)}','${_esc(h.ticker||'')}','${_esc(h.name)}',${Number(h.units||0)})">${_svgDownMobile} Sell</button>
            </div>`)}
          </div>`;
      }).join('');
    }
    _renderCemetery(holdings, performance, isSummary, portfolioId);
  }

  function _renderCemetery(holdings, performance, isSummary, portfolioId) {
    const tbody = document.getElementById('mgmt-cemetery-body');
    const meta = document.getElementById('mgmt-cemetery-meta');
    if (!tbody) return;

    _bindCemeterySortHandlers();
    _updateCemeterySortLabels();

    const activeKeys = new Set(
      (holdings || [])
        .filter(h => Number(h.units || 0) > 0.00000001)
        .map((h) => _transactionAssetKey(h, { preferTicker: isSummary }))
    );
    const direction = _cemeterySort.dir === 'desc' ? -1 : 1;
    const closed = Array.from(performance.entries())
      .filter(([, row]) => row.firstBuyDate)
      .map(([key, row]) => ({
        ...row,
        isActive: activeKeys.has(key) || Number(row.units || 0) > 0.00000001,
        totalReturn: Number(row.realized || 0) + Number(row.unrealized || 0) + Number(row.dividends || 0),
      }))
      .sort((a, b) => {
        if (_cemeterySort.key === 'return') {
          return (Number(a.totalReturn || 0) - Number(b.totalReturn || 0)) * direction;
        }
        const aDate = String(a.lastSellDate || a.firstBuyDate || '');
        const bDate = String(b.lastSellDate || b.firstBuyDate || '');
        return aDate.localeCompare(bDate) * direction;
      });

    const activeCount = closed.filter((row) => row.isActive).length;
    const closedCount = closed.length - activeCount;
    if (meta) {
      const base = `${closed.length} position${closed.length === 1 ? '' : 's'} · ${activeCount} active · ${closedCount} closed`;
      _setPillState(meta, isSummary ? `${base} across all wallets` : base, '');
    }
    if (!closed.length) {
      tbody.innerHTML = `<tr><td colspan="3" class="cemetery-empty">${isSummary ? 'No investment positions across all wallets.' : 'No investment positions in this wallet.'}</td></tr>`;
      return;
    }

    const resolvedPortfolioId = isSummary ? '' : (portfolioId || _activePortId || '');
    tbody.innerHTML = closed.map(row => `<tr class="cemetery-row">
      <td><div class="cemetery-asset"><button type="button" class="cemetery-asset-link" data-ticker="${_esc(row.ticker || row.name || '')}" data-portfolio-id="${_esc(resolvedPortfolioId)}"><span class="cemetery-ticker">${_esc(row.ticker || '—')}</span><span class="cemetery-name">${_esc(row.name)}</span></button></div></td>
      <td class="cemetery-lifespan">${_esc(_positionLifespanLabel(row.firstBuyDate, row.lastSellDate))}</td>
      <td class="cemetery-return ${_dailyChangeClass(row.realized)}">${_fmtSignedMoney(row.realized)} <span class="cemetery-unrealized">(${_fmtSignedMoney(row.unrealized)})</span></td>
    </tr>`).join('');

    tbody.querySelectorAll('.cemetery-asset-link').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault();
        const ticker = String(button.getAttribute('data-ticker') || '').trim();
        const pid = String(button.getAttribute('data-portfolio-id') || '').trim();
        if (ticker && typeof window.openAnalysisForTicker === 'function') {
          window.openAnalysisForTicker(ticker, { portfolioId: pid || null });
        }
      });
    });
  }

  function setHoldingsView(view) {
    _holdingsView = view === 'cemetery' ? 'cemetery' : 'active';
    document.querySelectorAll('[data-holdings-view]').forEach(button => {
      const active = button.dataset.holdingsView === _holdingsView;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', String(active));
    });
    document.querySelectorAll('[data-holdings-view-panel]').forEach(panel => {
      panel.hidden = panel.dataset.holdingsViewPanel !== _holdingsView;
    });
  }

  function _renderTransactions(transactions) {
    const tbody = document.getElementById('mgmt-transactions-body');
    const metaEl = document.getElementById('mgmt-history-meta');
    if (!tbody) return;
    if (!transactions.length) {
      tbody.innerHTML = _isSummaryPortfolio(_activePortId)
        ? '<tr><td colspan=\"7\" style=\"text-align:center;color:#888;padding:20px;\">Summary is a live aggregate. Open a real wallet to inspect transaction history.</td></tr>'
        : '<tr><td colspan=\"7\" style=\"text-align:center;color:#888;padding:20px;\">No transactions yet.</td></tr>';
      if (metaEl) _setPillState(metaEl, _isSummaryPortfolio(_activePortId) ? 'Summary has no direct ledger' : 'No activity yet', '');
      return;
    }
    const typeColors = {
      BUY: '#27ae60',
      SELL: '#c0392b',
      DEPOSIT: '#1abc9c',
      WITHDRAWAL: '#e67e22',
    };
    if (metaEl) _setPillState(metaEl, `${transactions.length} recent ${transactions.length === 1 ? 'entry' : 'entries'}`, '');
    tbody.innerHTML = transactions.map(tx => `
      <tr class="${tx.pending ? 'mgmt-row-pending' : ''}">
        <td>${_esc(tx.transactionDate || '—')}</td>
        <td><strong style="color:${typeColors[tx.type] || '#27ae60'}">${_esc(tx.type || 'BUY')}</strong>${tx.pending ? ' <span class="wallet-settings-pill wallet-settings-pill-muted">Pending</span>' : ''}</td>
        <td>${_esc(tx.ticker || (_isCashTransactionType(tx.type) ? 'CASH' : '—'))}</td>
        <td style="text-align:right;">${tx.quantity != null ? Number(tx.quantity || 0).toLocaleString('pl-PL',{maximumFractionDigits:4}) : '—'}</td>
        <td style="text-align:right;">${tx.price ? Number(tx.price).toLocaleString('pl-PL',{minimumFractionDigits:2}) : '—'}</td>
        <td style="text-align:right;">${tx.value != null ? Number(tx.value).toLocaleString('pl-PL',{minimumFractionDigits:2, maximumFractionDigits:2}) : '—'}</td>
        <td>${_esc(tx.comment || '')}</td>
      </tr>
    `).join('');
  }

  function _renderValueHistory(snapshots) {
    const tbody = document.getElementById('mgmt-value-history-body');
    const metaEl = document.getElementById('mgmt-value-history-meta');
    if (!tbody) return;

    if (!snapshots.length) {
      tbody.innerHTML = _isSummaryPortfolio(_activePortId)
        ? '<tr><td colspan="3" style="text-align:center;color:#888;padding:20px;">No summary snapshots yet.</td></tr>'
        : '<tr><td colspan="3" style="text-align:center;color:#888;padding:20px;">No daily value snapshots yet.</td></tr>';
      if (metaEl) _setPillState(metaEl, _isSummaryPortfolio(_activePortId) ? 'Summary snapshots pending' : 'No snapshots yet', '');
      return;
    }

    if (metaEl) _setPillState(metaEl, `${snapshots.length} close ${snapshots.length === 1 ? 'snapshot' : 'snapshots'}`, '');
    tbody.innerHTML = snapshots.map((snapshot, index) => {
      const value = Number(snapshot.portfolioValue || 0);
      const investment = snapshot.investmentValue == null ? null : Number(snapshot.investmentValue);
      const dailyReturn = snapshot.dailyReturn == null ? null : Number(snapshot.dailyReturn);
      const returnMarkup = dailyReturn == null
        ? ''
        : `<div class="wallet-history-note ${_dailyChangeClass(dailyReturn)}">${_fmtSignedMoney(dailyReturn)}</div>`;
      const investmentMarkup = investment == null ? '—' : _fmtMoney(investment);
      return `
        <tr class="${index === 0 ? 'wallet-value-history-latest' : ''}">
          <td>
            <div class="wallet-history-date-cell">
              <strong>${_esc(snapshot.snapshotDate || '—')}</strong>
              ${index === 0 ? '<span class="wallet-settings-pill">Latest close</span>' : ''}
            </div>
          </td>
          <td style="text-align:right;">
            <div class="wallet-history-value-cell">
              <strong class="wallet-cell-strong">${_fmtMoney(value)}</strong>
              ${returnMarkup}
            </div>
          </td>
          <td style="text-align:right;">
            <strong class="wallet-cell-strong">${investmentMarkup}</strong>
          </td>
        </tr>
      `;
    }).join('');
  }

  // ── Create portfolio ─────────────────────────────────────────
  async function createPortfolio() {
    const input = document.getElementById('mgmt-new-port-name');
    const name = (input.value || '').trim();
    if (!name) { _flash('mgmt-port-flash', 'Enter a portfolio name', 'error'); return; }

    const btn = document.getElementById('mgmt-create-port-btn');
    btn.disabled = true; btn.textContent = 'Creating…';
    try {
      await PortfolioClient.putPortfolio({ name, type: 'real', currency: 'PLN' });
      await _refreshWalletData();
      input.value = '';
      _setCreateComposerOpen(false);
      _flash('mgmt-port-flash', `"${name}" created`, 'ok');
      await _loadPortfolios();
      // Auto-select the new one
      const created = _portfolios.find(p => p.name === name);
      if (created) selectPortfolio(created.portfolioId);
    } catch(e) {
      _flash('mgmt-port-flash', e.message, 'error');
    } finally {
      btn.disabled = false; btn.textContent = 'Create';
    }
  }

  // ── Wallet Settings Modal ──────────────────────────────────────
  function openWalletSettingsModal() {
    const isSummary = _isSummaryPortfolio(_activePortId);
    const portfolio = _portfolios.find(p => p.portfolioId === _activePortId);
    const modal = document.getElementById('wallet-settings-modal');
    if (!modal) return;

    const nameInput = document.getElementById('wallet-settings-name');
    const athDate = document.getElementById('wallet-settings-ath-date');
    const athValue = document.getElementById('wallet-settings-ath-value');
    const delBtn = document.getElementById('wallet-settings-delete-btn');
    const athGroup = document.getElementById('wallet-settings-ath-group');
    const resetAthBtn = document.getElementById('wallet-settings-reset-ath-btn');
    const flash = document.getElementById('wallet-settings-flash');

    if (flash) flash.style.display = 'none';

    if (isSummary) {
      if (nameInput) {
        nameInput.value = 'Summary (All Wallets)';
        nameInput.disabled = true;
      }
      if (delBtn) delBtn.style.display = 'none';
      
      const ath = window.PORTFOLIO_ATH || {};
      if (athDate) athDate.value = ath.athDate || '';
      if (athValue) athValue.value = ath.athValue || '';
    } else {
      if (nameInput) {
        nameInput.value = portfolio ? portfolio.name : '';
        nameInput.disabled = false;
      }
      if (delBtn) delBtn.style.display = '';

      const walletKey = portfolio ? portfolio.name : null;
      const ath = (window.WALLET_ATHS || {})[walletKey] || {};
      if (athDate) athDate.value = ath.athDate || '';
      if (athValue) athValue.value = ath.athValue || '';
    }

    modal.style.display = 'flex';
  }

  function closeWalletSettingsModal() {
    const modal = document.getElementById('wallet-settings-modal');
    if (modal) modal.style.display = 'none';
  }

  async function saveWalletSettings() {
    const flash = document.getElementById('wallet-settings-flash');
    const showFlash = (msg, isError=false) => {
      if (!flash) return;
      flash.textContent = msg;
      flash.className = `user-flash ${isError ? 'mgmt-error' : 'mgmt-success'}`;
      flash.style.display = 'block';
    };

    const isSummary = _isSummaryPortfolio(_activePortId);
    const portfolio = _portfolios.find(p => p.portfolioId === _activePortId);
    const nameInput = document.getElementById('wallet-settings-name');
    const athDateInput = document.getElementById('wallet-settings-ath-date');
    const athValueInput = document.getElementById('wallet-settings-ath-value');

    const newName = nameInput ? nameInput.value.trim() : '';
    const athDate = athDateInput ? athDateInput.value : '';
    const athValue = athValueInput ? parseFloat(athValueInput.value) : NaN;

    let wantsRename = !isSummary && portfolio && newName && newName !== portfolio.name;
    let wantsAth = !!athDate || !Number.isNaN(athValue);

    if (wantsAth && (!athDate || !Number.isFinite(athValue) || athValue <= 0)) {
      showFlash('Please provide both ATH date and a valid ATH value.', true);
      return;
    }

    showFlash('Saving settings...');

    try {
      if (wantsRename) {
        await PortfolioClient.putPortfolio({ portfolioId: _activePortId, name: newName, type: 'real', currency: 'PLN' });
      }

      if (wantsAth) {
        // Resolve portfolioId for ATH (if summary, resolveAthPortfolioId uses 'summary')
        const athPid = isSummary ? 'summary' : _activePortId;
        const athResponse = await PortfolioClient.updateAth(athPid, { athDate, athValue, athSource: 'MANUAL' });
        
        const walletKey = isSummary ? 'Summary' : (wantsRename ? newName : portfolio.name);
        if (walletKey === 'Summary') window.PORTFOLIO_ATH = athResponse.ath || null;
        else {
            window.WALLET_ATHS = window.WALLET_ATHS || {};
            window.WALLET_ATHS[walletKey] = athResponse.ath || null;
        }
      }

      if (wantsRename || wantsAth) {
        await _refreshWalletData();
        await _loadPortfolios();
        await selectPortfolio(_activePortId);
        if (typeof renderDashboard === 'function') renderDashboard();
      }
      
      closeWalletSettingsModal();
    } catch(e) {
      showFlash(e.message || 'Failed to save settings.', true);
    }
  }

  async function deleteSelectedWallet() {
    const portfolio = _portfolios.find(p => p.portfolioId === _activePortId);
    if (!portfolio || _isSummaryPortfolio(_activePortId)) return;

    if (!confirm(`Delete portfolio "${portfolio.name}" and all its holdings? This cannot be undone.`)) return;
    try {
      await PortfolioClient.deletePortfolio(_activePortId);
      await _refreshWalletData();
      _activePortId = 'summary';
      await _loadPortfolios();
      closeWalletSettingsModal();
    } catch(e) {
      alert(`Delete failed: ${e.message}`);
    }
  }

  async function resetSelectedWalletAth() {
    const flash = document.getElementById('wallet-settings-flash');
    if (flash) {
      flash.textContent = 'Recalculating ATH from history...';
      flash.className = 'user-flash';
      flash.style.display = 'block';
    }

    try {
      const isSummary = _isSummaryPortfolio(_activePortId);
      const athPid = isSummary ? 'summary' : _activePortId;
      const response = await PortfolioClient.updateAth(athPid, { athSource: 'AUTO' });
      
      const portfolio = _portfolios.find(p => p.portfolioId === _activePortId);
      const walletKey = isSummary ? 'Summary' : (portfolio ? portfolio.name : null);
      
      if (walletKey === 'Summary') window.PORTFOLIO_ATH = response.ath || null;
      else if (walletKey) {
          window.WALLET_ATHS = window.WALLET_ATHS || {};
          window.WALLET_ATHS[walletKey] = response.ath || null;
      }
      
      closeWalletSettingsModal();
      await _refreshWalletData();
      await selectPortfolio(_activePortId);
      if (typeof renderDashboard === 'function') renderDashboard();
    } catch(e) {
      if (flash) {
        flash.textContent = e.message || 'Could not recalculate ATH.';
        flash.className = 'user-flash mgmt-error';
      }
    }
  }

  // ── Ticker search autocomplete ───────────────────────────────
  function _getTransactionType() {
    const el = document.getElementById('mgmt-transaction-type');
    return ((el && el.value) || 'BUY').toUpperCase();
  }

  function setTransactionType(type) {
    const normalized = String(type || 'BUY').toUpperCase();
    const allowed = ['BUY', 'SELL', 'DEPOSIT', 'WITHDRAWAL', 'DIVIDEND'];
    const value = allowed.includes(normalized) ? normalized : 'BUY';
    const el = document.getElementById('mgmt-transaction-type');
    if (el) el.value = value;
    _updateTransactionFormState();
  }

  function _normalizeSearchValue(symbol, name) {
    return `${symbol} — ${name}`;
  }

  function onSearchInput(e) {
    const q = (e && e.target ? e.target.value : '').trim();
    clearTimeout(_searchTimer);

    const currentDisplay = _selectedHolding
      ? _normalizeSearchValue(_selectedHolding.ticker || '', _selectedHolding.name || '')
      : '';
    if (_selectedHolding && q !== currentDisplay) {
      document.getElementById('mgmt-ticker-hidden').value = '';
      document.getElementById('mgmt-holding-name-hidden').value = '';
      document.getElementById('mgmt-holding-confirm').style.display = 'none';
      _setSelectedHolding(null);
    }

    if (!q) {
      const requestId = ++_searchRequestId;
      _setSearchStatus('Loading holdings...', 'loading');
      _searchTimer = setTimeout(async () => {
        try {
          const results = await searchTickers('');
          if (requestId !== _searchRequestId) return;
          renderDropdown(results);
          _setSearchStatus('Type to search Yahoo Finance · use arrows and Enter to select', 'ok');
        } catch (err) {
          if (requestId !== _searchRequestId) return;
          _clearDropdown();
          _setSearchStatus(err.message || 'Failed to load holdings', 'error');
        }
      }, 50);
      _renderTransactionSummary();
      return;
    }

    if (_selectedHolding && q === currentDisplay) {
      _setSearchStatus(`Selected ${_selectedHolding.ticker} from Yahoo Finance`, 'ok');
      return;
    }

    const requestId = ++_searchRequestId;
    _setSearchStatus('Searching Yahoo Finance…', 'loading');
    _searchTimer = setTimeout(async () => {
      try {
        const results = await searchTickers(q);
        if (requestId !== _searchRequestId) return;
        renderDropdown(results);
      } catch (err) {
        if (requestId !== _searchRequestId) return;
        _clearDropdown();
        _setSearchStatus(err.message || 'Search failed', 'error');
      }
    }, 180);
  }

  function onSearchKeyDown(event) {
    if (!_searchResults.length) {
      if (event.key === 'Escape') _clearDropdown();
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      _searchActiveIndex = (_searchActiveIndex + 1) % _searchResults.length;
      _highlightActiveDropdown();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      _searchActiveIndex = (_searchActiveIndex - 1 + _searchResults.length) % _searchResults.length;
      _highlightActiveDropdown();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const idx = _searchActiveIndex >= 0 ? _searchActiveIndex : 0;
      const result = _searchResults[idx];
      if (result) selectTicker(result.symbol, result.name, result.exchange);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      _clearDropdown();
    }
  }

  function onSearchBlur() {
    setTimeout(() => _clearDropdown(), 140);
    _renderTransactionSummary();
  }

  // ── TFI fund search ───────────────────────────────────────

  function _syncSearchSourceView() {
    const yfInput  = document.getElementById('mgmt-search-input');
    const yfStatus = document.getElementById('mgmt-search-status');
    const tfiWrap  = document.getElementById('mgmt-tfi-wrap');
    const yfBtn    = document.getElementById('mgmt-source-yf');
    const tfiBtn   = document.getElementById('mgmt-source-tfi');
    const isTfi = _searchSource === 'tfi';
    if (yfInput)  yfInput.style.display  = isTfi ? 'none' : '';
    if (yfStatus) yfStatus.style.display = isTfi ? 'none' : '';
    if (tfiWrap)  tfiWrap.style.display  = isTfi ? '' : 'none';
    if (yfBtn)    yfBtn.classList.toggle('is-active', !isTfi);
    if (tfiBtn)   tfiBtn.classList.toggle('is-active',  isTfi);
  }

  function setSearchSource(source) {
    _searchSource = source === 'tfi' ? 'tfi' : 'yf';
    _syncSearchSourceView();
    _clearDropdown();
    const tickerEl = document.getElementById('mgmt-ticker-hidden');
    const nameEl   = document.getElementById('mgmt-holding-name-hidden');
    const confirmEl = document.getElementById('mgmt-holding-confirm');
    if (tickerEl)  tickerEl.value  = '';
    if (nameEl)    nameEl.value    = '';
    if (confirmEl) confirmEl.style.display = 'none';
    _setSelectedHolding(null);
    _clearValidationState();
    if (_searchSource === 'yf') {
      const searchInput = document.getElementById('mgmt-search-input');
      if (searchInput) searchInput.value = '';
      _setSearchStatus('Type to search Yahoo Finance · use arrows and Enter to select');
    } else {
      _setTfiStatus('Enter the bankier.pl fund code and press Lookup. <a href="https://www.bankier.pl/fundusze" target="_blank" rel="noopener noreferrer">Browse funds →</a>');
    }
    _renderTransactionSummary();
  }

  function _setTfiStatus(message, type) {
    const el = document.getElementById('mgmt-tfi-status');
    if (!el) return;
    el.innerHTML = message || '';
    el.className = `mgmt-search-hint${type ? ` is-${type}` : ''}`;
  }

  function onTfiCodeInput(e) {
    if (e && e.target) e.target.value = e.target.value.toUpperCase();
  }

  function onTfiCodeKeyDown(e) {
    if (e.key === 'Enter') { e.preventDefault(); lookupTfi(); }
  }

  async function lookupTfi() {
    const codeInput = document.getElementById('mgmt-tfi-code-input');
    const code = (codeInput ? codeInput.value : '').trim().toUpperCase();
    if (!code) { _setTfiStatus('Enter a bankier.pl fund code first.', 'error'); return; }
    const btn = document.getElementById('mgmt-tfi-lookup-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Looking up…'; }
    _setTfiStatus('Fetching from bankier.pl…', 'loading');
    try {
      const data = await _get(`/tfi/lookup?code=${encodeURIComponent(code)}`);
      selectTfi(data.code, data.name, data.nav, data.navDate);
    } catch (e) {
      _setTfiStatus(e.message || 'Fund not found — check the code on bankier.pl.', 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Lookup'; }
    }
  }

  function selectTfi(code, name, nav, navDate) {
    const symbol = `TFI:${code}`;
    const existing = _findCurrentHolding(symbol, name);
    const displayName = (existing && existing.name) ? existing.name : name;
    document.getElementById('mgmt-ticker-hidden').value = symbol;
    document.getElementById('mgmt-holding-name-hidden').value = displayName;
    const confirmEl = document.getElementById('mgmt-holding-confirm');
    const navFmt = nav != null
      ? nav.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' PLN'
      : '?';
    document.getElementById('mgmt-confirm-symbol').textContent = code;
    document.getElementById('mgmt-confirm-name').textContent = displayName;
    document.getElementById('mgmt-confirm-exchange').textContent =
      `Polish TFI · bankier.pl · last close ${navFmt}${navDate ? ' (' + navDate + ')' : ''}`;
    if (confirmEl) confirmEl.style.display = 'block';
    _setSelectedHolding({
      holdingId: existing ? existing.holdingId : null,
      ticker: symbol,
      name: displayName,
      units: existing ? Number(existing.units || 0) : 0,
      exchange: 'bankier.pl',
      currentValue: existing ? Number(existing.currentValue || 0) : 0,
      purchaseValue: existing ? Number(existing.purchaseValue || 0) : 0,
      dailyChangePLN: 0,
    });
    _setTfiStatus(`${displayName} · Last close: ${navFmt}${navDate ? ' (' + navDate + ')' : ''}`, 'ok');
    _clearValidationState();
    _setSubmitStatus('Review the summary, then submit');

    // Autopopulate price per share in PLN with fund NAV
    const priceEl = document.getElementById('mgmt-price-input');
    if (priceEl && nav != null && Number(nav) > 0) {
      const txType = _getTransactionType();
      priceEl.value = Number(nav).toFixed(txType === 'DIVIDEND' ? 2 : 4);
      handleTransactionDraftChange('price');
    }

    _renderTransactionSummary({
      txType: _getTransactionType(),
      ticker: symbol,
      units: Number(document.getElementById('mgmt-units-input').value || 0),
      value: Number(document.getElementById('mgmt-total-input').value || 0),
      autoAddCash: !!(document.getElementById('mgmt-auto-cash-checkbox') || {}).checked,
    });
    setTimeout(() => {
      confirmEl && confirmEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      const unitsEl = document.getElementById('mgmt-units-input');
      if (unitsEl) unitsEl.focus();
    }, 50);
  }

  function _highlightActiveDropdown() {
    const dropdown = document.getElementById('mgmt-ticker-dropdown');
    if (!dropdown) return;
    dropdown.querySelectorAll('.mgmt-dropdown-item').forEach((el, index) => {
      el.classList.toggle('active', index === _searchActiveIndex);
      if (index === _searchActiveIndex) {
        el.scrollIntoView({ block: 'nearest' });
      }
    });
  }

  function _isPolishTicker(r) {
    const sym = (r.symbol || '').toUpperCase();
    const exch = (r.exchange || '').toUpperCase();
    return sym.endsWith('.WA') || exch.includes('WARSAW') || exch.includes('WSE') || exch.includes('GPW');
  }

  function _findHoldingAcrossAllWallets(symbol) {
    // Check current wallet holdings first
    const inCurrent = _findCurrentHolding(symbol, '');
    if (inCurrent) return { holding: inCurrent, walletName: _activePortfolio()?.name || 'this wallet' };
    // Check all wallets via WALLET_HOLDINGS global
    if (typeof WALLET_HOLDINGS !== 'undefined' && WALLET_HOLDINGS) {
      for (const [walletName, holdings] of Object.entries(WALLET_HOLDINGS)) {
        if (walletName === 'Summary') continue;
        const found = (holdings || []).find(h =>
          h.ticker && String(h.ticker).toUpperCase() === String(symbol).toUpperCase()
        );
        if (found) return { holding: found, walletName };
      }
    }
    return null;
  }

  function renderDropdown(results) {
    const dropdown = document.getElementById('mgmt-ticker-dropdown');
    if (!dropdown) return;
    _searchResults = results || [];
    _searchActiveIndex = _searchResults.length ? 0 : -1;

    if (!_searchResults.length) {
      _clearDropdown();
      _setSearchStatus('No Yahoo Finance matches. Try another ticker or company name.', 'error');
      return;
    }

    dropdown.innerHTML = _searchResults.map((r, i) => {
      const isPolish = _isPolishTicker(r);
      const owned    = _findHoldingAcrossAllWallets(r.symbol);
      const isHistoricalOwned = r.isOwned && !owned;
      const polishBadge = isPolish
        ? `<span class="mgmt-ticker-badge mgmt-ticker-badge-pl" title="Warsaw Stock Exchange">🇵🇱 WSE</span>`
        : '';
      const ownedBadge  = owned
        ? `<span class="mgmt-ticker-badge mgmt-ticker-badge-owned" title="You already hold this in ${_esc(owned.walletName)}">✓ In ${_esc(owned.walletName)}</span>`
        : isHistoricalOwned 
        ? `<span class="mgmt-ticker-badge mgmt-ticker-badge-owned" title="In your portfolio history">✓ Owned</span>`
        : '';
      return `
      <div class="mgmt-dropdown-item${i === _searchActiveIndex ? ' active' : ''}${owned || isHistoricalOwned ? ' is-owned' : ''}" data-idx="${i}">
        <div class="mgmt-dropdown-main">
          <span class="mgmt-ticker-symbol">${_esc(r.symbol)}</span>
          <span class="mgmt-ticker-name">${_esc(r.name)}</span>
        </div>
        <div class="mgmt-ticker-meta">
          ${polishBadge}${ownedBadge}
          <span class="mgmt-ticker-exchange">${_esc(r.exchange)}</span>
        </div>
      </div>`;
    }).join('');

    dropdown.querySelectorAll('.mgmt-dropdown-item').forEach(el => {
      el.addEventListener('mousedown', evt => evt.preventDefault());
      el.addEventListener('click', () => {
        const idx = parseInt(el.dataset.idx, 10);
        const result = _searchResults[idx];
        if (result) selectTicker(result.symbol, result.name, result.exchange);
      });
    });

    dropdown.style.display = 'block';

    const wrap = document.getElementById('mgmt-search-wrap') || dropdown.parentElement;
    const wrapRect = wrap.getBoundingClientRect();
    const modalBody = document.querySelector('.tflow-sheet') || document.querySelector('.wallet-overlay-panel') || document.querySelector('.wallet-holdings-shell') || document.querySelector('.manage-modal-body');
    const modalRect = modalBody ? modalBody.getBoundingClientRect() : null;
    const spaceBelow = modalRect ? modalRect.bottom - wrapRect.bottom : 300;

    if (spaceBelow < 220) {
      dropdown.style.bottom = '100%';
      dropdown.style.top = 'auto';
    } else {
      dropdown.style.top = 'calc(100% + 6px)';
      dropdown.style.bottom = 'auto';
    }

    _setSearchStatus(`${_searchResults.length} Yahoo Finance result${_searchResults.length === 1 ? '' : 's'} ready`);
    setTimeout(() => dropdown.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50);
  }


  function selectTicker(symbol, name, exchange) {
    const existing = _findCurrentHolding(symbol, name);
    const displayName = existing && existing.name ? existing.name : name;
    document.getElementById('mgmt-search-input').value = _normalizeSearchValue(symbol, displayName);
    document.getElementById('mgmt-ticker-hidden').value = symbol;
    document.getElementById('mgmt-holding-name-hidden').value = displayName;
    _clearDropdown();

    const confirmEl = document.getElementById('mgmt-holding-confirm');
    document.getElementById('mgmt-confirm-symbol').textContent = symbol;
    document.getElementById('mgmt-confirm-name').textContent = displayName;
    document.getElementById('mgmt-confirm-exchange').textContent = exchange || 'Yahoo Finance';
    if (confirmEl) confirmEl.style.display = 'block';

    _setSelectedHolding({
      holdingId: existing ? existing.holdingId : null,
      ticker: symbol,
      name: displayName,
      units: existing ? Number(existing.units || 0) : 0,
      exchange: exchange || 'Yahoo Finance',
      currentValue: existing ? Number(existing.currentValue || 0) : 0,
      purchaseValue: existing ? Number(existing.purchaseValue || 0) : 0,
      dailyChangePLN: existing ? Number(existing.dailyChangePLN || 0) : 0,
    });
    _clearValidationState();
    _setSearchStatus(`Selected ${symbol} from Yahoo Finance`, 'ok');
    _setSubmitStatus('Review the summary, then submit');

    // Autopopulate price per share in PLN with current live value
    const priceEl = document.getElementById('mgmt-price-input');
    let pricePLN = _getLivePricePLN(symbol, displayName);
    if (pricePLN && pricePLN > 0) {
      if (priceEl) {
        const txType = _getTransactionType();
        priceEl.value = pricePLN.toFixed(txType === 'DIVIDEND' ? 2 : 4);
        handleTransactionDraftChange('price');
      }
    } else {
      _fetchStockPricePLN(symbol).then(fetchedPrice => {
        if (fetchedPrice && fetchedPrice > 0) {
          const currentSymbol = document.getElementById('mgmt-ticker-hidden')?.value;
          if (currentSymbol === symbol && priceEl) {
            const txType = _getTransactionType();
            priceEl.value = fetchedPrice.toFixed(txType === 'DIVIDEND' ? 2 : 4);
            handleTransactionDraftChange('price');
          }
        }
      });
    }

    _renderTransactionSummary({
      txType: _getTransactionType(),
      ticker: symbol,
      units: Number(document.getElementById('mgmt-units-input').value || 0),
      value: Number(document.getElementById('mgmt-total-input').value || 0),
      autoAddCash: !!(document.getElementById('mgmt-auto-cash-checkbox') || {}).checked,
    });

    setTimeout(() => {
      confirmEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      const unitsEl = document.getElementById('mgmt-units-input');
      if (unitsEl) unitsEl.focus();
    }, 50);
  }

  function _updateTransactionFormState() {
    const txType = _getTransactionType();
    const isCashTx = _isCashTransactionType(txType);
    const unitsEl = document.getElementById('mgmt-units-input');
    const unitsLabel = document.getElementById('mgmt-units-label');
    const btn = document.getElementById('mgmt-add-holding-btn');
    const hintEl = document.getElementById('mgmt-transaction-hint');
    const valueHint = document.getElementById('mgmt-value-hint');
    const totalLabel = document.getElementById('mgmt-total-label');
    const totalInput = document.getElementById('mgmt-total-input');
    const totalWrap = document.getElementById('mgmt-total-wrap');
    const priceWrap = document.getElementById('mgmt-price-wrap');
    const commissionWrap = document.getElementById('mgmt-commission-wrap');
    const confirmMeta = document.getElementById('mgmt-confirm-meta');
    const confirmEl = document.getElementById('mgmt-holding-confirm');
    const confirmSymbol = document.getElementById('mgmt-confirm-symbol');
    const confirmName = document.getElementById('mgmt-confirm-name');
    const confirmExchange = document.getElementById('mgmt-confirm-exchange');
    const searchWrap = document.getElementById('mgmt-search-wrap');
    const maxBtn = document.getElementById('mgmt-max-qty-btn');
    const buyBtn = document.getElementById('mgmt-type-buy');
    const sellBtn = document.getElementById('mgmt-type-sell');
    const depositBtn = document.getElementById('mgmt-type-deposit');
    const withdrawalBtn = document.getElementById('mgmt-type-withdrawal');
    const dividendBtn = document.getElementById('mgmt-type-dividend');
    const autoCashWrap = document.getElementById('mgmt-auto-cash-wrap');
    const availableUnits = _selectedHolding && Number.isFinite(Number(_selectedHolding.units))
      ? Number(_selectedHolding.units)
      : 0;
    const availableCash = _cashBalance();

    if (buyBtn) buyBtn.classList.toggle('is-active', txType === 'BUY');
    if (sellBtn) sellBtn.classList.toggle('is-active', txType === 'SELL');
    if (depositBtn) depositBtn.classList.toggle('is-active', txType === 'DEPOSIT');
    if (withdrawalBtn) withdrawalBtn.classList.toggle('is-active', txType === 'WITHDRAWAL');
    if (dividendBtn) dividendBtn.classList.toggle('is-active', txType === 'DIVIDEND');
    // Theme submit button and type tabs via data-tx-type attribute
    const _txOverlay = document.getElementById('mgmt-transaction-overlay');
    if (_txOverlay) _txOverlay.dataset.txType = txType;

    const unitsWrap = unitsEl ? unitsEl.closest('.tflow-amount-field') : null;

    if (searchWrap) {
      searchWrap.style.display = isCashTx ? 'none' : '';
      if (!isCashTx) _syncSearchSourceView();
    }
    if (confirmEl) confirmEl.style.display = isCashTx || _selectedHolding ? 'block' : 'none';
    
    if (unitsWrap) unitsWrap.style.display = '';
    if (totalWrap) totalWrap.style.display = isCashTx ? 'none' : '';
    if (priceWrap) priceWrap.style.display = isCashTx ? 'none' : '';
    if (commissionWrap) commissionWrap.style.display = isCashTx ? 'none' : '';
    if (autoCashWrap) autoCashWrap.style.display = txType === 'BUY' ? '' : 'none';
    if (isCashTx) {
      if (confirmSymbol) confirmSymbol.textContent = 'CASH';
      if (confirmName) confirmName.textContent = txType === 'DEPOSIT' ? 'Wallet cash deposit' : 'Wallet cash withdrawal';
      if (confirmExchange) confirmExchange.textContent = 'Cash position';
    } else if (!_selectedHolding) {
      if (confirmSymbol) confirmSymbol.textContent = '';
      if (confirmName) confirmName.textContent = '';
      if (confirmExchange) confirmExchange.textContent = '';
    }

    if (unitsLabel) {
      unitsLabel.textContent = isCashTx ? 'Amount' : 'Quantity';
    }
    if (unitsEl) {
      if (txType === 'SELL') {
        unitsEl.placeholder = availableUnits > 0
          ? `Quantity to sell (max ${availableUnits.toLocaleString('pl-PL', { maximumFractionDigits: 4 })})`
          : 'Quantity to sell';
      } else if (txType === 'BUY') {
        unitsEl.placeholder = 'Quantity to buy';
      } else if (txType === 'DEPOSIT') {
        unitsEl.placeholder = 'Amount to deposit';
      } else if (txType === 'WITHDRAWAL') {
        unitsEl.placeholder = 'Amount to withdraw';
      } else if (txType === 'DIVIDEND') {
        unitsEl.placeholder = availableUnits > 0 
          ? `Shares owned (default: ${availableUnits.toLocaleString('pl-PL', { maximumFractionDigits: 4 })})`
          : 'Number of shares owned';
        // Auto-fill available units for dividend if not filled
        if (availableUnits > 0 && !unitsEl.value) {
            unitsEl.value = availableUnits;
        }
      }
    }
    if (totalLabel) {
      if (txType === 'DIVIDEND') totalLabel.textContent = 'Dividend cash received (required)';
      else totalLabel.textContent = 'Trade value (required)';
    }
    if (totalInput) {
      if (txType === 'DIVIDEND') totalInput.placeholder = 'Total cash received';
      else if (txType === 'SELL') totalInput.placeholder = 'Net proceeds incl. fees';
      else totalInput.placeholder = 'Total cash outflow incl. fees';
    }
    const priceInput = document.getElementById('mgmt-price-input');
    if (priceInput) {
      if (txType === 'DIVIDEND') priceInput.placeholder = '0.00';
      else priceInput.placeholder = '0.0000';
    }
    if (hintEl) {
      if (txType === 'SELL') {
        hintEl.textContent = 'Selling validates owned quantity and credits the cash position.';
      } else if (txType === 'BUY') {
        hintEl.textContent = 'Buying debits the cash position. If needed, you can auto-add the missing cash first.';
      } else if (txType === 'DEPOSIT') {
        hintEl.textContent = 'Deposit adds money to the wallet cash position.';
      } else if (txType === 'WITHDRAWAL') {
        hintEl.textContent = 'Withdrawal subtracts money from the wallet cash position.';
      } else if (txType === 'DIVIDEND') {
        hintEl.textContent = 'Dividends add money directly to the wallet cash position and are linked to the selected holding.';
      }
    }
    if (valueHint) {
      if (isCashTx) {
        valueHint.textContent = `Current cash balance: ${availableCash.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN.`;
      } else if (txType === 'DIVIDEND') {
        valueHint.textContent = 'Enter the total net dividend cash received.';
      } else {
        valueHint.textContent = 'Trade value is the full cash impact of the transaction. For buys and sells, include fees in that value.';
      }
    }
    if (confirmMeta) {
      if (txType === 'SELL') {
        confirmMeta.textContent = availableUnits > 0
          ? `Available to sell: ${availableUnits.toLocaleString('pl-PL', { maximumFractionDigits: 4 })} units. Cash balance: ${availableCash.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN.`
          : 'Select an existing holding you own before selling.';
      } else if (txType === 'BUY') {
        confirmMeta.textContent = availableUnits > 0
          ? `You already hold ${availableUnits.toLocaleString('pl-PL', { maximumFractionDigits: 4 })} units. Cash available: ${availableCash.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN.`
          : `New position ready. Cash available: ${availableCash.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN.`;
      } else {
        confirmMeta.textContent = `Cash available: ${availableCash.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN.`;
      }
    }
    if (maxBtn) maxBtn.style.display = txType === 'SELL' && availableUnits > 0 ? '' : 'none';
    if (btn) {
      if (txType === 'SELL') btn.textContent = 'Save Sell';
      else if (txType === 'BUY') btn.textContent = 'Save Buy';
      else if (txType === 'DEPOSIT') btn.textContent = 'Save Deposit';
      else if (txType === 'WITHDRAWAL') btn.textContent = 'Save Withdrawal';
      else if (txType === 'DIVIDEND') btn.textContent = 'Save Dividend';
      else btn.textContent = 'Save';
    }
    handleTransactionDraftChange();
  }

  function onTransactionTypeChange() {
    _updateTransactionFormState();
  }

  function _prefillHolding(type, holdingId, ticker, name, units) {
    setTransactionType(type);
    const isTfi = (ticker || '').startsWith('TFI:');
    const displaySymbol = isTfi ? ticker.replace('TFI:', '') : ticker;
    const confirmEl = document.getElementById('mgmt-holding-confirm');
    document.getElementById('mgmt-search-input').value = _normalizeSearchValue(displaySymbol, name);
    document.getElementById('mgmt-ticker-hidden').value = ticker;
    document.getElementById('mgmt-holding-name-hidden').value = name;
    document.getElementById('mgmt-confirm-symbol').textContent = displaySymbol;
    document.getElementById('mgmt-confirm-name').textContent = name;
    document.getElementById('mgmt-confirm-exchange').textContent = isTfi ? 'Polish TFI · bankier.pl' : 'Existing holding';
    if (confirmEl) confirmEl.style.display = 'block';
    const existing = _findCurrentHolding(ticker, name);
    _setSelectedHolding({
      holdingId,
      ticker,
      name,
      units: Number(units || (existing && existing.units) || 0),
      exchange: 'Existing holding',
      currentValue: Number((existing && existing.currentValue) || 0),
      purchaseValue: Number((existing && existing.purchaseValue) || 0),
      dailyChangePLN: Number((existing && existing.dailyChangePLN) || 0),
    });
    _clearValidationState();
    _setSearchStatus(`Selected existing ${ticker}`, 'ok');
    _setSubmitStatus('Review the summary, then submit');

    // Autopopulate price per share in PLN with current live value
    const priceEl = document.getElementById('mgmt-price-input');
    let pricePLN = _getLivePricePLN(ticker, name);
    if (pricePLN && pricePLN > 0 && priceEl) {
      priceEl.value = pricePLN.toFixed(type === 'DIVIDEND' ? 2 : 4);
      handleTransactionDraftChange('price');
    }

    _renderTransactionSummary({
      txType: type,
      ticker,
      units: Number(units || 0),
      value: Number(document.getElementById('mgmt-total-input').value || 0),
      autoAddCash: !!(document.getElementById('mgmt-auto-cash-checkbox') || {}).checked,
    });
    openTransactionsPanel('trade');
    setTimeout(() => {
      const unitsEl = document.getElementById('mgmt-units-input');
      if (unitsEl) unitsEl.focus();
    }, 20);
  }


  // ── Quick Entry (natural language) ───────────────────────────

  function toggleQuickEntry() {
    // No-op: quick entry is now always visible on the wallet screen.
    // Kept for backward compatibility in case any code calls it.
  }

  function onQuickEntryInput(e) {
    // Auto-grow the single-line textarea up to ~3 rows
    const el = e && e.target;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 90) + 'px';
  }

  const _QE_TEMPLATES = {
    buy:     'Buy {qty} {TICKER} for {price} PLN/share to {Wallet} on {YYYY-MM-DD}',
    sell:    'Sell {qty} {TICKER} for {price} PLN/share to {Wallet} on {YYYY-MM-DD}',
    deposit: 'Deposit {amount} PLN to {Wallet} on {YYYY-MM-DD}',
  };

  function applyQeTemplate(key) {
    const tpl = _QE_TEMPLATES[key];
    if (!tpl) return;
    const today = new Date().toISOString().slice(0, 10);
    const walletName = (_activePortfolio() && !_isSummaryPortfolio(_activePortId))
      ? _activePortfolio().name
      : (_portfolios.find(p => !_isSummaryPortfolio(p.portfolioId)) || { name: 'Wallet' }).name;
    const filled = tpl
      .replace('{Wallet}', walletName)
      .replace('{YYYY-MM-DD}', today)
      .replace('{TICKER}', 'AAPL')
      .replace('{qty}', '10')
      .replace('{price}', '185.50')
      .replace('{amount}', '5000');
    const inp = document.getElementById('mgmt-quick-entry-input');
    if (inp) {
      inp.value = filled;
      inp.style.height = 'auto';
      inp.style.height = Math.min(inp.scrollHeight, 90) + 'px';
      inp.focus();
      inp.select();
    }
  }

  function _setQeStatus(msg, type) {
    const el = document.getElementById('mgmt-qe-status');
    if (!el) return;
    el.textContent = msg || '';
    el.className = `wallet-qe-status${type ? ` is-${type}` : ''}`;
  }

  async function parseQuickEntry() {
    const inp = document.getElementById('mgmt-quick-entry-input');
    if (!inp) return;
    const raw = inp.value.trim();
    if (!raw) { _setQeStatus('Enter a transaction description first.', 'error'); return; }

    // ── Parse ─────────────────────────────────────────────────────
    const text = raw.toLowerCase();

    // Determine type: buy / sell / deposit / withdrawal
    let txType = 'BUY';
    if (/^sell\b/.test(text))        txType = 'SELL';
    else if (/^deposit\b/.test(text)) txType = 'DEPOSIT';
    else if (/^withdraw/.test(text))  txType = 'WITHDRAWAL';

    const isCash = txType === 'DEPOSIT' || txType === 'WITHDRAWAL';

    // Quantity — first number after the action word
    const qtyMatch = raw.match(/(?:buy|sell|deposit|withdraw(?:al)?)\s+([\d,. ]+)/i);
    const qty = qtyMatch ? parseFloat(qtyMatch[1].replace(/,/g, '.').replace(/ /g, '')) : NaN;

    // Ticker — word that is all-caps or looks like a stock symbol (only for buy/sell)
    let ticker = null;
    if (!isCash) {
      // Try explicit ticker: word that is alphanumeric with dots/hyphens
      const afterQty = raw.replace(/^(buy|sell)\s+[\d,. ]+\s*/i, '');
      const tickerMatch = afterQty.match(/^([a-zA-Z0-9]+(?:[.\-][a-zA-Z0-9]+)?)/);
      if (tickerMatch) ticker = tickerMatch[1].toUpperCase();
    }

    // Price per share — after "for|@|at|price" keyword
    const priceMatch = raw.match(/(?:for|@|at|price)\s*([\d,. ]+)/i);
    const pricePerShare = priceMatch ? parseFloat(priceMatch[1].replace(/,/g, '.').replace(/ /g, '')) : NaN;

    // Date — YYYY-MM-DD or DD.MM.YYYY or DD/MM/YYYY
    let txDate = '';
    const isoMatch = raw.match(/\b(\d{4}-\d{2}-\d{2})\b/);
    const euMatch  = raw.match(/\b(\d{2})[./](\d{2})[./](\d{4})\b/);
    if (isoMatch) {
      txDate = isoMatch[1];
    } else if (euMatch) {
      txDate = `${euMatch[3]}-${euMatch[2]}-${euMatch[1]}`;
    } else {
      txDate = new Date().toISOString().slice(0, 10); // default: today
    }

    // Wallet — after "to|into|in" keyword, match known portfolio names
    let targetPortId = null;
    const toMatch = raw.match(/\b(?:to|into|in)\s+([a-z0-9_\-. ]+?)(?:\s+on\b|\s*$)/i);
    if (toMatch) {
      const walletHint = toMatch[1].trim().toLowerCase();
      const found = _portfolios.find(p =>
        !_isSummaryPortfolio(p.portfolioId) &&
        (p.name.toLowerCase().includes(walletHint) || walletHint.includes(p.name.toLowerCase()))
      );
      if (found) targetPortId = found.portfolioId;
    }

    // Fallback to active portfolio if it's not Summary
    if (!targetPortId) {
      if (!_isSummaryPortfolio(_activePortId)) {
        targetPortId = _activePortId;
      }
    }

    if (txDate > new Date().toISOString().slice(0, 10)) {
      _setQeStatus('Transaction date cannot be in the future.', 'error');
      return;
    }

    // ── Validate basics ──────────────────────────────────────────
    if (!isCash && !ticker) {
      _setQeStatus('Could not find a ticker symbol. Example: "Buy 10 AAPL for 185 to XTB"', 'error');
      return;
    }
    if (Number.isNaN(qty) || qty <= 0) {
      _setQeStatus('Could not parse the quantity. Example: "Buy 10 AAPL for 185 to XTB"', 'error');
      return;
    }
    if (!isCash && (Number.isNaN(pricePerShare) || pricePerShare <= 0)) {
      _setQeStatus('Could not parse the price. Add "for 185.50" or "@185.50" after the ticker.', 'error');
      return;
    }

    // ── Switch wallet if needed ──────────────────────────────────
    if (!targetPortId) {
      _setQeStatus('Please select a target wallet or specify "to WalletName" in your text.', 'error');
      return;
    }

    if (targetPortId !== _activePortId && !_isSummaryPortfolio(targetPortId)) {
      _setQeStatus('Switching wallet…', 'loading');
      await selectPortfolio(targetPortId);
    }

    // Open panel & set type first
    openTransactionsPanel('trade');
    setTransactionType(txType);

    // Set date
    const dateEl = document.getElementById('mgmt-transaction-date');
    if (dateEl) dateEl.value = txDate;

    if (isCash) {
      // Deposit / withdrawal: just fill in the amount
      const unitsEl = document.getElementById('mgmt-units-input');
      if (unitsEl) { unitsEl.value = qty.toFixed(2); }
      handleTransactionDraftChange('units');
      _setQeStatus(`✓ ${txType === 'DEPOSIT' ? 'Deposit' : 'Withdrawal'} of ${qty.toLocaleString('pl-PL', {minimumFractionDigits: 2})} PLN on ${txDate} — review and submit.`, 'ok');
      return;
    }

    // ── Stock: search Yahoo Finance then auto-select ─────────────
    _setQeStatus(`Searching for ${ticker}…`, 'loading');
    try {
      // Prioritize current holdings: check if the ticker matches an existing holding in this portfolio
      const activePortObj = _portfolios.find(p => p.portfolioId === _activePortId);
      const holdings = activePortObj ? _liveHoldingsFor(activePortObj) : [];
      let holdingMatch = holdings.find(h => h.ticker && h.ticker.toUpperCase() === ticker.toUpperCase());
      if (!holdingMatch) {
        // Also try matching the base symbol, assuming local exchange if it's already in the portfolio (e.g. "cdr" matching "CDR.WA")
        holdingMatch = holdings.find(h => h.ticker && h.ticker.toUpperCase().startsWith(ticker.toUpperCase() + '.'));
      }
      if (holdingMatch) {
        ticker = holdingMatch.ticker; // Upgrades "cdr" to "CDR.WA" if matched
      }

      const results = await searchTickers(ticker);
      const best = results.find(r => r.symbol.toUpperCase() === ticker.toUpperCase()) || results[0];
      
      if (!best) {
        _setQeStatus(`No exact match for "${ticker}". Please select from the dropdown.`, 'error');
        // Fallback to UI: Open the dropdown
        const searchInput = document.getElementById('mgmt-search-input');
        if (searchInput) {
          searchInput.value = ticker;
          // Trigger the input event to kick off the dropdown search automatically
          searchInput.dispatchEvent(new Event('input', { bubbles: true }));
          searchInput.focus();
        }
        return;
      }
      // Select the ticker (fills search field + shows confirm card)
      selectTicker(best.symbol, best.name, best.exchange);

      // Fill quantity and price
      const unitsEl = document.getElementById('mgmt-units-input');
      const priceEl = document.getElementById('mgmt-price-input');
      const totalEl = document.getElementById('mgmt-total-input');
      if (unitsEl) unitsEl.value = qty;
      if (priceEl) priceEl.value = pricePerShare.toFixed(4);
      if (totalEl) totalEl.value = (qty * pricePerShare).toFixed(2);
      handleTransactionDraftChange('price');

      const totalVal = (qty * pricePerShare).toFixed(2);
      _setQeStatus(`✓ ${txType} ${qty} × ${best.symbol} @ ${pricePerShare.toLocaleString('pl-PL', {minimumFractionDigits: 2})} = ${Number(totalVal).toLocaleString('pl-PL', {minimumFractionDigits: 2})} PLN on ${txDate}. Review and submit.`, 'ok');
    } catch (e) {
      _setQeStatus(`Search failed: ${e.message}`, 'error');
    }
  }

  function prefillBuy(holdingId, ticker, name, units) {
    _prefillHolding('BUY', holdingId, ticker, name, units);
  }

  function prefillSell(holdingId, ticker, name, units) {
    _prefillHolding('SELL', holdingId, ticker, name, units);
  }

  function fillMaxQuantity() {
    if (_getTransactionType() !== 'SELL' || !_selectedHolding) return;
    const unitsEl = document.getElementById('mgmt-units-input');
    const maxUnits = Number(_selectedHolding.units || 0);
    if (unitsEl && maxUnits > 0) {
      unitsEl.value = String(maxUnits);
      _renderTransactionSummary({
        txType: _getTransactionType(),
        ticker: (_selectedHolding && _selectedHolding.ticker) || '',
        units: maxUnits,
        value: Number(document.getElementById('mgmt-total-input').value || 0),
        autoAddCash: !!(document.getElementById('mgmt-auto-cash-checkbox') || {}).checked,
      });
    }
  }

  function validateTransactionForm() {
    const txType = _getTransactionType();
    const isCashTx = _isCashTransactionType(txType);
    const txDate = document.getElementById('mgmt-transaction-date').value;
    const ticker = isCashTx ? '' : document.getElementById('mgmt-ticker-hidden').value.trim();
    const name = isCashTx ? 'Cash' : (document.getElementById('mgmt-holding-name-hidden').value.trim() || ticker);
    const units = parseFloat(document.getElementById('mgmt-units-input').value);
    const totalRaw = document.getElementById('mgmt-total-input').value.trim();
    const commissionRaw = document.getElementById('mgmt-commission-input').value.trim();
    const comment = document.getElementById('mgmt-comment-input').value.trim();
    const totalAmount = totalRaw === '' ? NaN : parseFloat(totalRaw);
    const commission = isCashTx ? 0 : (commissionRaw === '' ? 0 : parseFloat(commissionRaw));
    const value = isCashTx ? units : totalAmount;
    const errors = [];
    const invalidIds = [];
    const availableUnits = Number((_selectedHolding && _selectedHolding.units) || 0);
    const availableCash = _cashBalance();
    const autoAddCash = !!(document.getElementById('mgmt-auto-cash-checkbox') || {}).checked;

    if (!_activePortId || _isSummaryPortfolio(_activePortId)) {
      errors.push('Select a real portfolio first.');
    }
    if (!isCashTx && !ticker) {
      if (_searchSource === 'tfi') {
        errors.push('Enter a TFI code and press Lookup to select a fund.');
        invalidIds.push('mgmt-tfi-code-input');
      } else {
        errors.push('Search Yahoo Finance and select a stock first.');
        invalidIds.push('mgmt-search-input');
      }
    }
    const todayStr = new Date().toISOString().slice(0, 10);
    if (!txDate) {
      errors.push('Pick a transaction date.');
      invalidIds.push('mgmt-transaction-date');
    } else if (txDate > todayStr) {
      errors.push('Transaction date cannot be in the future.');
      invalidIds.push('mgmt-transaction-date');
    }
    if (!Number.isFinite(units) || units <= 0) {
      errors.push(isCashTx ? 'Enter a valid cash amount greater than 0.' : 'Enter a valid quantity greater than 0.');
      invalidIds.push('mgmt-units-input');
    }
    if (!isCashTx && (!Number.isFinite(totalAmount) || totalAmount <= 0)) {
      errors.push('Trade value is required for buys and sells.');
      invalidIds.push('mgmt-total-input');
    } else if (!isCashTx && Number.isFinite(totalAmount) && totalAmount < 0) {
      errors.push('Trade value cannot be negative.');
      invalidIds.push('mgmt-total-input');
    }
    if (!Number.isFinite(commission) || commission < 0) {
      errors.push('Commission cannot be negative.');
      invalidIds.push('mgmt-commission-input');
    }
    if (txType === 'SELL') {
      if (!_selectedHolding || !availableUnits) {
        errors.push('Select an existing holding with owned quantity before selling.');
        invalidIds.push(_searchSource === 'tfi' ? 'mgmt-tfi-code-input' : 'mgmt-search-input');
      } else if (Number.isFinite(units) && units - availableUnits > 0.00000001) {
        errors.push(`Insufficient quantity. You own ${availableUnits.toLocaleString('pl-PL', { maximumFractionDigits: 4 })} units.`);
        invalidIds.push('mgmt-units-input');
      }
    }
    if (txType === 'BUY' && Number.isFinite(value) && value - availableCash > 0.00000001 && !autoAddCash) {
      errors.push(`Insufficient cash. Available ${availableCash.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN.`);
      invalidIds.push('mgmt-total-input');
    }
    if (txType === 'WITHDRAWAL' && Number.isFinite(value) && value - availableCash > 0.00000001) {
      errors.push(`Insufficient cash. Available ${availableCash.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN.`);
      invalidIds.push('mgmt-units-input');
    }

    if (errors.length) {
      _setSubmitStatus('Fix the highlighted fields', 'error');
    } else {
      _setSubmitStatus('Looks good — ready to submit', 'ok');
    }

    _renderTransactionSummary({
      txType,
      ticker,
      units,
      amount: isCashTx ? units : null,
      value,
      autoAddCash,
    });

    const price = !isCashTx && Number.isFinite(value) && Number.isFinite(units) && units > 0
      ? Number((((txType === 'BUY' ? value - commission : value + commission) / units)).toFixed(8))
      : NaN;

    return {
      valid: errors.length === 0,
      errors,
      invalidIds,
      data: {
        txType,
        txDate,
        ticker,
        name,
        units: isCashTx ? null : units,
        amount: isCashTx ? units : null,
        totalAmount: Number.isFinite(totalAmount) ? totalAmount : NaN,
        value,
        commission,
        comment,
        price,
        autoAddCash,
      },
    };
  }

  function _recalculateHoldingPercents(holdings) {
    const total = holdings.reduce((sum, item) => sum + Number(item.currentValue || item.purchaseValue || 0), 0);
    holdings.forEach(item => {
      item.pct = total ? Number((((Number(item.currentValue || item.purchaseValue || 0)) / total) * 100).toFixed(2)) : 0;
      item.profit = Number((Number(item.currentValue || 0) - Number(item.purchaseValue || 0)).toFixed(2));
      item.returnPct = item.purchaseValue ? Number(((item.profit / Number(item.purchaseValue)) * 100).toFixed(2)) : 0;
    });
    holdings.sort((a, b) => Number(b.currentValue || b.purchaseValue || 0) - Number(a.currentValue || a.purchaseValue || 0));
  }

  function _applyOptimisticTransaction(data) {
    const holdings = _deepClone(_currentHoldings);
    const transactions = _deepClone(_currentTransactions);
    const quantity = Number(data.units || 0);
    const value = Number(data.value || 0);
    const commission = Number(data.commission || 0);
    const isCashTx = _isCashTransactionType(data.txType);
    const cashIdx = holdings.findIndex(_isCashHolding);
    const cashHolding = cashIdx >= 0 ? holdings[cashIdx] : null;
    const currentCash = cashHolding ? Number(cashHolding.currentValue || cashHolding.purchaseValue || cashHolding.units || 0) : 0;
    let nextCash = currentCash;

    const optimisticTx = {
      transactionDate: data.txDate,
      type: data.txType,
      ticker: data.ticker,
      name: data.name,
      quantity: data.units,
      price: Number.isFinite(data.price) ? data.price : null,
      value,
      commission,
      comment: data.comment || 'Pending sync…',
      pending: true,
    };

    const idx = holdings.findIndex(h => {
      if (data.ticker && h.ticker && String(h.ticker).toUpperCase() === String(data.ticker).toUpperCase()) return true;
      return String(h.name || '').trim().toLowerCase() === String(data.name || '').trim().toLowerCase();
    });
    const existing = idx >= 0 ? holdings[idx] : null;
    const unitCurrent = existing && Number(existing.units || 0) > 0
      ? Number(existing.currentValue || 0) / Number(existing.units || 1)
      : (Number.isFinite(data.price) && quantity > 0 ? Number(data.price) : 0);
    const unitDaily = existing && Number(existing.units || 0) > 0
      ? Number(existing.dailyChangePLN || 0) / Number(existing.units || 1)
      : 0;

    if (isCashTx) {
      nextCash = data.txType === 'DEPOSIT'
        ? currentCash + value
        : Math.max(0, currentCash - value);
    } else if (data.txType === 'BUY') {
      if (data.autoAddCash && value > currentCash) {
        transactions.unshift({
          transactionDate: data.txDate,
          type: 'DEPOSIT',
          ticker: null,
          name: 'Cash',
          quantity: null,
          price: null,
          value: Number((value - currentCash).toFixed(2)),
          commission: 0,
          comment: `Auto cash top-up before buying ${data.ticker}`,
          pending: true,
        });
        nextCash = value;
      }
      nextCash = Math.max(0, nextCash - value);
      const purchaseDelta = value;
      if (existing) {
        existing.units = Number((Number(existing.units || 0) + quantity).toFixed(6));
        existing.purchaseValue = Number((Number(existing.purchaseValue || 0) + purchaseDelta).toFixed(2));
        existing.currentValue = Number((Number(existing.currentValue || 0) + unitCurrent * quantity).toFixed(2));
        existing.dailyChangePLN = Number((Number(existing.dailyChangePLN || 0) + unitDaily * quantity).toFixed(2));
        existing.pending = true;
      } else {
        holdings.push({
          holdingId: (_selectedHolding && _selectedHolding.holdingId) || String(data.ticker || data.name || '').toLowerCase(),
          ticker: data.ticker,
          name: data.name,
          currency: _currencyForTicker(data.ticker),
          units: Number(quantity.toFixed(6)),
          purchaseValue: Number(purchaseDelta.toFixed(2)),
          currentValue: Number(((unitCurrent * quantity) || value || 0).toFixed(2)),
          dailyChangePLN: Number((unitDaily * quantity).toFixed(2)),
          pricePLN: Number(unitCurrent.toFixed(2)),
          priceOriginal: Number.isFinite(data.price) ? Number(data.price.toFixed(2)) : 0,
          priceOriginalCurrency: _currencyForTicker(data.ticker),
          dailyChangePct: 0,
          ytdChangePct: 0,
          todayBars: [],
          yearBars: [],
          pct: 0,
          pending: true,
        });
      }
    } else if (existing) {
      nextCash = currentCash + value;
      const oldUnits = Number(existing.units || 0);
      const oldPurchaseValue = Number(existing.purchaseValue || 0);
      const nextUnits = Number((oldUnits - quantity).toFixed(6));
      const avgCost = oldUnits > 0 ? oldPurchaseValue / oldUnits : 0;
      const nextPurchaseValue = Math.max(0, oldPurchaseValue - avgCost * quantity);
      const nextCurrentValue = Math.max(0, Number(existing.currentValue || 0) - unitCurrent * quantity);
      const nextDailyPln = Number((Number(existing.dailyChangePLN || 0) - unitDaily * quantity).toFixed(2));
      if (nextUnits <= 0.00000001) {
        holdings.splice(idx, 1);
      } else {
        existing.units = nextUnits;
        existing.purchaseValue = Number(nextPurchaseValue.toFixed(2));
        existing.currentValue = Number(nextCurrentValue.toFixed(2));
        existing.dailyChangePLN = nextDailyPln;
        existing.pending = true;
      }
    }

    if (isCashTx || data.txType === 'BUY' || data.txType === 'SELL') {
      if (nextCash > 0.00000001) {
        const cashPayload = {
          holdingId: (cashHolding && cashHolding.holdingId) || '__cash__',
          ticker: null,
          name: 'Cash',
          currency: 'PLN',
          units: Number(nextCash.toFixed(2)),
          purchaseValue: Number(nextCash.toFixed(2)),
          currentValue: Number(nextCash.toFixed(2)),
          dailyChangePLN: 0,
          pct: 0,
          pending: true,
        };
        if (cashHolding) {
          Object.assign(cashHolding, cashPayload);
        } else {
          holdings.push(cashPayload);
        }
      } else if (cashIdx >= 0) {
        holdings.splice(cashIdx, 1);
      }
    }

    _recalculateHoldingPercents(holdings);
    transactions.unshift(optimisticTx);
    _currentHoldings = holdings;
    _currentTransactions = transactions;
    const portfolio = _activePortfolio();
    if (portfolio) {
      _renderSettings(portfolio, holdings.length, transactions.length);
      _renderHoldings(_activePortId, holdings, false);
      _renderTransactions(transactions);
    }
  }

  // ── Add transaction ──────────────────────────────────────────
  async function addHolding() {
    const validation = validateTransactionForm();
    if (!validation.valid) {
      _showValidationErrors(validation.errors, validation.invalidIds);
      _flash('mgmt-holding-flash', validation.errors[0], 'error');
      return;
    }

    _clearValidationState();
    const { txType, txDate, ticker, name, units, value, commission, comment, price, autoAddCash } = validation.data;
    const btn = document.getElementById('mgmt-add-holding-btn');
    const previousHoldings = _deepClone(_currentHoldings);
    const previousTransactions = _deepClone(_currentTransactions);
    const payload = {
      type: txType,
      transactionDate: txDate,
      holdingId: !_isCashTransactionType(txType) && _selectedHolding && _selectedHolding.holdingId ? _selectedHolding.holdingId : undefined,
      name,
      ticker: ticker || undefined,
      currency: _isCashTransactionType(txType) ? 'PLN' : _currencyForTicker(ticker),
      quantity: units,
      price: Number.isFinite(price) ? price : undefined,
      value,
      commission,
      comment,
      autoAddCash,
    };

    btn.disabled = true;
    btn.textContent = 'Saving…';
    _setTradeSyncState('Syncing…', 'syncing');
    _setSubmitStatus('Submitting transaction…', 'loading');
    _applyOptimisticTransaction(validation.data);

    try {
      await PortfolioClient.addTransaction(_activePortId, payload);
      _flash('mgmt-holding-flash', `${txType} saved for ${ticker || 'cash'}`, 'ok');
      await _refreshWalletData();
      await selectPortfolio(_activePortId);
      window.dispatchEvent(new CustomEvent('portfolioTransactionSaved', {
        detail: { portfolioId: _activePortId, type: txType }
      }));
      _setTradeSyncState('Synced', 'ok');
      _setSubmitStatus('Saved successfully', 'ok');
      _resetTransactionForm({ keepType: false });
      closeTransactionsPanel();

      // Recalculate historical snapshots when the transaction date is in the past.
      // The call is fire-and-forget from the UX perspective; an event is dispatched
      // when done so the History tab can refresh its chart data.
      const today = new Date().toISOString().slice(0, 10);
      if (txDate && txDate < today) {
        const recalcPortId = _activePortId;
        PortfolioClient.recalculateSnapshots(recalcPortId, txDate)
          .then(res => {
            window.dispatchEvent(new CustomEvent('portfolioHistoryRecalculated', {
              detail: { portfolioId: recalcPortId, fromDate: txDate, updated: res.updated || 0 }
            }));
          })
          .catch(err => {
            console.warn('[manage] Snapshot recalculation failed:', err);
          });
      }
    } catch(e) {
      _currentHoldings = previousHoldings;
      _currentTransactions = previousTransactions;
      const portfolio = _activePortfolio();
      if (portfolio) {
        _renderSettings(portfolio, previousHoldings.length, previousTransactions.length);
        _renderHoldings(_activePortId, previousHoldings, false);
        _renderTransactions(previousTransactions);
      }
      _setTradeSyncState('Sync failed', 'error');
      _setSubmitStatus('Sync failed — try again', 'error');
      _flash('mgmt-holding-flash', e.message, 'error');
    } finally {
      btn.disabled = false;
      _updateTransactionFormState();
    }
  }

  function _currencyForTicker(ticker) {
    if (!ticker) return 'PLN';
    if (ticker.startsWith('TFI:')) return 'PLN';
    if (ticker.endsWith('.WA')) return 'PLN';
    if (['BTC-USD','ETH-USD'].some(t => ticker.startsWith(t.split('-')[0]))) return 'USD';
    // Default: USD for US tickers, PLN for Polish
    return ticker.includes('.') ? 'PLN' : 'USD';
  }

  // ── Flash message ────────────────────────────────────────────
  function _flash(elId, msg, type) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = msg;
    el.className = `mgmt-flash mgmt-flash-${type}`;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 3000);
  }

  // ── Wallet screen entry point ─────────────────────────────────
  async function initWalletScreen() {
    const dateEl = document.getElementById('mgmt-transaction-date');
    if (dateEl && !dateEl.value) dateEl.value = new Date().toISOString().slice(0, 10);
    _bindWalletStickyBehavior();
    _setCreateComposerOpen(false);
    _setWalletStickyCondensed(false);
    _resetTransactionForm({ keepType: false });
    await _loadPortfolios();
    _loadBenchmarkSetting();
    _syncTransactionsPanel();
    _syncWalletStickyCondensed(true);
  }

  function openManageModal() {
    const btn = document.querySelector(`.tab-btn[onclick*="'wallets'"]`);
    if (typeof showTab === 'function' && btn) {
      showTab('wallets', btn);
    }
    initWalletScreen();
  }

  function closeManageModal() {
    _activePortId = null;
    closeTransactionsPanel();
    _resetTransactionForm({ keepType: false });
  }

  async function _loadBenchmarkSetting() {
    const sel = document.getElementById('mgmt-benchmark-select');
    if (!sel || !window.UserProfile) return;
    try {
      const saved = await UserProfile.getBenchmark();
      if (saved) sel.value = saved;
    } catch (_) {}
  }

  async function _loadRoastIntensitySetting() {
    const sel = document.getElementById('mgmt-roast-select');
    if (!sel || !window.UserProfile) return;
    try {
      const saved = await UserProfile.getRoastIntensity();
      if (saved) sel.value = saved;
    } catch (_) {}
  }

  async function saveBenchmark(newId) {
    if (!window.UserProfile) return;
    const savedEl = document.getElementById('mgmt-benchmark-saved');
    try {
      await UserProfile.updateBenchmark(newId);
      UserProfile.clearCache();
      try { localStorage.removeItem('lambda_cache'); } catch (_) {}
      window.BENCHMARK_ID   = newId;
      if (typeof window.resetBenchmarkRangeAuto === 'function') window.resetBenchmarkRangeAuto();
      // Find human-readable name from select options
      const sel = document.getElementById('mgmt-benchmark-select');
      window.BENCHMARK_NAME = sel ? sel.options[sel.selectedIndex].text.split(' (')[0] : newId;
      if (typeof updateBenchmarkChartLabels === 'function') updateBenchmarkChartLabels();
      if (typeof window.refreshLivePrices === 'function') {
        await window.refreshLivePrices();
      }
      if (savedEl) {
        savedEl.style.display = 'inline';
        setTimeout(() => { savedEl.style.display = 'none'; }, 2500);
      }
    } catch (e) {
      console.error('[benchmark] save failed', e);
    }
  }

  async function saveRoastIntensity(intensity) {
    if (!window.UserProfile) return;
    const savedEl = document.getElementById('mgmt-roast-saved');
    try {
      await UserProfile.updateRoastIntensity(intensity);
      UserProfile.clearCache();
      window.ROAST_INTENSITY = intensity;
      if (savedEl) {
        savedEl.style.display = 'inline';
        setTimeout(() => { savedEl.style.display = 'none'; }, 2500);
      }
    } catch (e) {
      console.error('[roast] save failed', e);
    }
  }

  // ── Expose globals ───────────────────────────────────────────
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && _isTransactionsPanelOpen()) closeTransactionsPanel();
    if (event.key === 'Escape' && _walletSelectorOpen && _isCompactWalletSelector()) {
      _setWalletSelectorOpen(false, { force: true });
    }
  });
  document.addEventListener('click', (event) => {
    const shell = event.target && event.target.closest ? event.target.closest('.wallet-selector-shell') : null;
    if (!shell && _walletSelectorOpen && _isCompactWalletSelector()) {
      _setWalletSelectorOpen(false, { force: true });
    }
  });
  window.addEventListener('roastfolio:auth', () => {
    _loadBenchmarkSetting();
    _loadRoastIntensitySetting();
  });
  // Also load immediately in case the auth event already fired or is unused
  document.addEventListener('DOMContentLoaded', () => {
    _loadBenchmarkSetting();
    _loadRoastIntensitySetting();
  });
  window.addEventListener('resize', () => {
    _setWalletSelectorOpen(!_isCompactWalletSelector(), { force: true });
    _syncWalletStickyCondensed(true);
  });
  window.openManageModal  = openManageModal;
  window.closeManageModal = closeManageModal;
  window.initWalletScreen = initWalletScreen;
  window._mgmt = {
    selectPortfolio,
    setHoldingsView,
    _carouselGoTo,
    openWalletSettingsModal,
    closeWalletSettingsModal,
    saveWalletSettings,
    deleteSelectedWallet,
    resetSelectedWalletAth,
    prefillBuy,
    prefillSell,
    selectTicker,
    setSearchSource,
    onTfiCodeInput,
    onTfiCodeKeyDown,
    lookupTfi,
    onSearchInput,
    onSearchKeyDown,
    onSearchBlur,
    handleTransactionDraftChange,
    onTransactionTypeChange,
    setTransactionType,
    fillMaxQuantity,
    addHolding,
    createPortfolio,
    toggleCreatePortfolioComposer,
    toggleWalletSelector,
    toggleWalletOverflow,
    openTransactionsPanel,
    closeTransactionsPanel,
    setTransactionsPanelMode,
    saveBenchmark,
    saveRoastIntensity,
    toggleQuickEntry,
    onQuickEntryInput,
    applyQeTemplate,
    parseQuickEntry,
  };
  document.addEventListener('liveDataReady', () => {
    if (document.getElementById('tab-wallets') && document.getElementById('tab-wallets').classList.contains('active')) {
      initWalletScreen();
    }
  });
})();
