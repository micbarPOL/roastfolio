(() => {
  function _apiBase() {
    const cfg = window.__CONFIG__ || window.APP_CONFIG || {};
    return (cfg.apiUrl || '').replace(/\/prices$/, '');
  }

  async function _authHeaders() {
    const token = AuthGuard.getIdToken();
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    };
  }

  async function _fetch(path, options = {}) {
    const headers = await _authHeaders();
    const res = await fetch(`${_apiBase()}${path}`, {
      ...options,
      headers: { ...headers, ...(options.headers || {}) },
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || `HTTP ${res.status}`);
    }
    return res.json();
  }

  const RetirementPlansClient = {
    listPlans() {
      return _fetch('/retirement-plans');
    },

    getPlan(planId) {
      return _fetch(`/retirement-plans/${encodeURIComponent(planId)}`);
    },

    savePlan(body) {
      return _fetch('/retirement-plans', {
        method: 'PUT',
        body: JSON.stringify(body),
      });
    },

    simulatePlan(planId, body) {
      return _fetch(`/retirement-plans/${encodeURIComponent(planId)}/simulate`, {
        method: 'POST',
        body: JSON.stringify(body || {}),
      });
    },

    deletePlan(planId) {
      return _fetch(`/retirement-plans/${encodeURIComponent(planId)}`, {
        method: 'DELETE',
      });
    },
  };

  const state = {
    initialized: false,
    plans: [],
    activePlanId: null,
    activePlan: null,
    activeResult: null,
    actualSeries: [],
    previewResult: null,
    chart: null,
    chartRange: 'ALL',
    chartScaleMode: 'linear',
    chartYZoom: 100,
    chartYPan: 0,
    draftTimer: null,
    busyAction: null,
  };

  const _buttonLabels = {
    create: '+ New plan',
    preview: 'Preview',
    save: 'Save plan',
    delete: 'Delete',
  };

  function _el(id) {
    return document.getElementById(id);
  }

  function _safeNumber(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  }

  function _clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function _todayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  function _parseDate(value) {
    if (!value) return null;
    const parsed = new Date(`${String(value).slice(0, 10)}T00:00:00Z`);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function _addYears(isoDate, years) {
    if (!window.RetirementSimulation || typeof window.RetirementSimulation.addYears !== 'function') {
      return isoDate;
    }
    return window.RetirementSimulation.addYears(isoDate, years);
  }

  function _yearsBetween(startIso, endIso) {
    const start = _parseDate(startIso);
    const end = _parseDate(endIso);
    if (!start || !end) return 0;
    return Math.max(0, (end.getTime() - start.getTime()) / (365.2425 * 24 * 60 * 60 * 1000));
  }

  function _retirementDateFromPayload(payload) {
    const birthDate = payload.dateOfBirth || _todayIso();
    return _addYears(birthDate, _safeNumber(payload.retirementAge, 0));
  }

  function _formatCurrency(value) {
    const numeric = Number(value || 0);
    return `${numeric.toLocaleString('pl-PL', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })} PLN`;
  }

  function _formatPercent(value) {
    if (value === null || value === undefined || value === '') return '—';
    return `${Number(value).toLocaleString('pl-PL', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}%`;
  }

  function _formatMonthYear(isoDate) {
    if (!isoDate) return '—';
    const parsed = new Date(`${isoDate}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime())) return isoDate;
    return parsed.toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' });
  }

  function _formatDuration(months) {
    const safeMonths = Math.max(0, Math.round(Number(months || 0)));
    const years = Math.floor(safeMonths / 12);
    const remainder = safeMonths % 12;
    if (!years) return `${remainder} mo`;
    if (!remainder) return `${years} yr`;
    return `${years} yr ${remainder} mo`;
  }

  function _isFiniteNumber(value) {
    return Number.isFinite(Number(value));
  }

  function _summaryCurrency(value, fallback = '—') {
    return _isFiniteNumber(value) ? _formatCurrency(Number(value)) : fallback;
  }

  function _summaryHistoryText(summary, activePayload) {
    const start = summary.historicalProjectedStartDate || activePayload.investingStartDate;
    const end = summary.actualEndDate || _todayIso();
    return start ? `${start} → ${end}` : 'Projection starts from investing date';
  }

  function _summaryMonteCarloText(summary, result, activePayload) {
    if (_isFiniteNumber(summary.monteCarloSuccessProbability)) {
      return `${_formatPercent(summary.monteCarloSuccessProbability)} success`;
    }
    const series = (result && result.series) || {};
    if ((series.monteCarloP10 || []).length && (series.monteCarloP50 || []).length && (series.monteCarloP90 || []).length) {
      return 'P10 / P50 / P90 bands';
    }
    return activePayload.monteCarloEnabled ? 'Enable + save to calculate bands' : 'Off';
  }

  function _ageFromMonths(startAge, months) {
    if (!Number.isFinite(Number(startAge))) return null;
    return Number((Number(startAge) + (Number(months || 0) / 12)).toFixed(1));
  }

  function _setStatus(message, tone = 'muted') {
    const el = _el('retirement-plan-status');
    if (!el) return;
    el.textContent = message || 'Ready';
    el.dataset.tone = tone;
  }

  function _setChartBadge(message, tone = 'preview') {
    const el = _el('retirement-chart-badge');
    if (!el) return;
    el.textContent = message || 'Live preview';
    el.dataset.tone = tone;
  }

  function _setBusy(action, isBusy) {
    const createBtn = _el('retirement-create-btn');
    const previewBtn = _el('retirement-rerun-btn');
    const saveBtn = _el('retirement-save-btn');
    const deleteBtn = _el('retirement-delete-btn');
    const screen = _el('retirement-screen');
    state.busyAction = isBusy ? action : null;
    screen?.classList.toggle('is-busy', !!isBusy);

    const map = {
      create: createBtn,
      preview: previewBtn,
      save: saveBtn,
      delete: deleteBtn,
    };

    Object.entries(map).forEach(([key, button]) => {
      if (!button) return;
      const active = isBusy && key === action;
      button.disabled = !!isBusy;
      button.classList.toggle('is-loading', active);
      button.textContent = active
        ? (key === 'save' ? 'Saving…' : key === 'preview' ? 'Refreshing…' : key === 'delete' ? 'Deleting…' : 'Preparing…')
        : _buttonLabels[key];
    });
  }

  function _defaultPlan() {
    const today = _todayIso();
    const birthDate = _addYears(today, -37);
    const investingStartDate = _addYears(birthDate, 30);
    return {
      name: 'Base retirement plan',
      dateOfBirth: birthDate,
      investingStartDate,
      retirementAge: 50,
      targetAge: 88.6,
      monthlyInvestment: 2000,
      expectedYearlyReturnWorking: 7,
      expectedYearlyReturnAfterRetirement: 4,
      monthlyRetirementSpending: 6000,
      initialInvestmentAmount: 2000,
      inflationRate: 2.5,
      annualFeeRate: 0.35,
      monteCarloEnabled: true,
      monteCarloRuns: 250,
      annualVolatilityWorking: 15,
      annualVolatilityRetired: 8,
      notes: '',
      retirementIncomeStreams: [],
      oneTimeCashflows: [],
      spendingPhases: [],
      returnPhases: [],
    };
  }

  function _stringifyArray(value) {
    return value && value.length ? JSON.stringify(value, null, 2) : '';
  }

  function _parseArrayField(id, label) {
    const raw = (_el(id)?.value || '').trim();
    if (!raw) return [];
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (error) {
      throw new Error(`${label} must be a valid JSON array`);
    }
    if (!Array.isArray(parsed)) {
      throw new Error(`${label} must be a JSON array`);
    }
    return parsed;
  }

  function _activeActualSeries() {
    return ((state.activeResult && state.activeResult.series && state.activeResult.series.actual) || state.actualSeries || []);
  }

  function _currentPortfolioValue() {
    return Number(
      (state.previewResult && state.previewResult.summary && state.previewResult.summary.currentPortfolioValue)
      || (state.activeResult && state.activeResult.summary && state.activeResult.summary.currentPortfolioValue)
      || (state.activePlan && state.activePlan.latestSummary && state.activePlan.latestSummary.currentPortfolioValue)
      || 0
    );
  }

  function _derivedCurrentPortfolioValue(payload) {
    const actual = _activeActualSeries();
    if (actual.length) {
      return Number(actual[actual.length - 1].value || 0);
    }

    const knownCurrentValue = _currentPortfolioValue();
    if (knownCurrentValue > 0) {
      return knownCurrentValue;
    }

    if (!window.RetirementSimulation || typeof window.RetirementSimulation.estimateCurrentPortfolioValue !== 'function') {
      return Number(payload.initialInvestmentAmount || payload.monthlyInvestment || 0);
    }

    return window.RetirementSimulation.estimateCurrentPortfolioValue({
      dateOfBirth: payload.dateOfBirth,
      investingStartDate: payload.investingStartDate,
      retirementAge: payload.retirementAge,
      monthlyInvestment: payload.monthlyInvestment,
      yearlyReturnBeforeRetirement: payload.expectedYearlyReturnWorking,
      initialInvestmentAmount: payload.initialInvestmentAmount,
    });
  }

  function _readPlanForm() {
    const activePlanId = state.activePlanId || (state.activePlan && state.activePlan.planId) || '';
    const monthlyInvestment = Number(_el('retirement-monthly-investment')?.value || 0);
    const initialInvestmentAmount = _el('retirement-initial-investment')?.value === ''
      ? monthlyInvestment
      : Number(_el('retirement-initial-investment')?.value || 0);
    return {
      ...(activePlanId ? { planId: activePlanId } : {}),
      name: (_el('retirement-plan-name')?.value || '').trim() || 'Retirement Plan',
      dateOfBirth: (_el('retirement-birth-date')?.value || '').trim(),
      investingStartDate: (_el('retirement-started-date')?.value || '').trim(),
      retirementAge: Number(_el('retirement-retirement-age')?.value || 0),
      targetAge: 88.6,
      monthlyInvestment,
      expectedYearlyReturnWorking: Number(_el('retirement-working-return')?.value || 0),
      expectedYearlyReturnAfterRetirement: Number(_el('retirement-retired-return')?.value || 0),
      monthlyRetirementSpending: Number(_el('retirement-monthly-spending')?.value || 0),
      initialInvestmentAmount,
      inflationRate: Number(_el('retirement-inflation-rate')?.value || 0),
      annualFeeRate: Number(_el('retirement-annual-fee-rate')?.value || 0),
      monteCarloEnabled: !!_el('retirement-monte-carlo-enabled')?.checked,
      monteCarloRuns: Number(_el('retirement-monte-carlo-runs')?.value || 250),
      annualVolatilityWorking: Number(_el('retirement-working-volatility')?.value || 15),
      annualVolatilityRetired: Number(_el('retirement-retired-volatility')?.value || 8),
      notes: (_el('retirement-notes')?.value || '').trim(),
      retirementIncomeStreams: _parseArrayField('retirement-income-streams', 'Income streams'),
      oneTimeCashflows: _parseArrayField('retirement-one-time-events', 'One-time events'),
      spendingPhases: _parseArrayField('retirement-spending-phases', 'Spending phases'),
      returnPhases: _parseArrayField('retirement-return-phases', 'Return phases'),
    };
  }

  function _fillPlanForm(plan) {
    const source = { ..._defaultPlan(), ...(plan || {}) };
    _el('retirement-plan-name').value = source.name || '';
    _el('retirement-birth-date').value = source.dateOfBirth || '';
    _el('retirement-started-date').value = source.investingStartDate || '';
    _el('retirement-retirement-age').value = source.retirementAge ?? (_yearsBetween(source.dateOfBirth, source.retirementDate || '') || '');
    _el('retirement-monthly-investment').value = source.monthlyInvestment ?? '';
    _el('retirement-working-return').value = source.expectedYearlyReturnWorking ?? '';
    _el('retirement-retired-return').value = source.expectedYearlyReturnAfterRetirement ?? '';
    _el('retirement-monthly-spending').value = source.monthlyRetirementSpending ?? '';
    _el('retirement-initial-investment').value = source.initialInvestmentAmount ?? '';
    _el('retirement-inflation-rate').value = source.inflationRate ?? '';
    _el('retirement-annual-fee-rate').value = source.annualFeeRate ?? '';
    _el('retirement-monte-carlo-enabled').checked = !!source.monteCarloEnabled;
    _el('retirement-monte-carlo-runs').value = source.monteCarloRuns ?? 250;
    _el('retirement-working-volatility').value = source.annualVolatilityWorking ?? 15;
    _el('retirement-retired-volatility').value = source.annualVolatilityRetired ?? 8;
    _el('retirement-notes').value = source.notes || '';
    if (_el('retirement-target-age-display')) _el('retirement-target-age-display').value = `${source.targetAge || 88.6} years old`;
    _el('retirement-income-streams').value = _stringifyArray(source.retirementIncomeStreams);
    _el('retirement-one-time-events').value = _stringifyArray(source.oneTimeCashflows);
    _el('retirement-spending-phases').value = _stringifyArray(source.spendingPhases);
    _el('retirement-return-phases').value = _stringifyArray(source.returnPhases);
    _el('retirement-plan-title').textContent = source.name || 'Retirement plan';
    _updateHeroInputs(source);
  }

  function _updateHeroInputs(payload) {
    const today = _todayIso();
    const retirementDate = _retirementDateFromPayload(payload);
    const yearsLeft = _yearsBetween(today, retirementDate);
    const accumulationYears = _yearsBetween(payload.investingStartDate, retirementDate);
    const label = `${yearsLeft ? `${yearsLeft.toFixed(1)} years to retirement` : 'Already at retirement'} · ${accumulationYears.toFixed(1)} years invested by retirement`;
    const yearsEl = _el('retirement-years-left');
    if (yearsEl) yearsEl.textContent = label;
    const spendingHero = _el('retirement-spending-hero');
    if (spendingHero) spendingHero.textContent = `${_formatCurrency(payload.monthlyRetirementSpending || 0)}/mo`;
  }

  function _renderPlanList() {
    const wrap = _el('retirement-plan-list');
    if (!wrap) return;
    if (!state.plans.length) {
      wrap.innerHTML = '<div class="retirement-empty-state">No saved plans yet. Start with the default template and tap save when the preview looks right.</div>';
      return;
    }
    wrap.innerHTML = state.plans.map((plan) => {
      const summary = plan.latestSummary || {};
      const active = plan.planId === state.activePlanId ? ' is-active' : '';
      const status = summary.lastsToTargetAge === false ? 'Below 88.6y' : (summary.finalPortfolioValue ? 'Covers 88.6y' : 'No forecast yet');
      return `
        <button type="button" class="retirement-plan-chip${active}" onclick="window.RetirementForecast.selectPlan('${plan.planId}')">
          <span class="retirement-plan-chip-top">
            <strong>${plan.name || 'Retirement plan'}</strong>
            <span class="retirement-plan-chip-status">${status}</span>
          </span>
          <span>${summary.finalPortfolioValue ? _formatCurrency(summary.finalPortfolioValue) : 'Tap to load this scenario'}</span>
        </button>
      `;
    }).join('');
  }

  function _warningState(summary) {
    if (!summary) return null;
    if (summary.lastsToTargetAge === false) {
      return {
        tone: 'danger',
      title: `Your actual portfolio may not make it to age ${summary.targetAge || 88.6}`,
        copy: `Using the real portfolio value today, the projection may run out around ${summary.depletionDate || 'the depletion date'}. Consider retiring later, investing more, or lowering retirement spending.`,
      };
    }
    return {
      tone: 'success',
      title: `Your actual portfolio reaches age ${summary.targetAge || 88.6}`,
      copy: `With the real portfolio value today, this plan stays funded through ${summary.targetDate || `age ${summary.targetAge || 88.6}`}.`,
    };
  }

  function _renderWarning(summary) {
    const banner = _el('retirement-warning-banner');
    if (!banner) return;
    const warning = _warningState(summary);
    if (!warning) {
      banner.hidden = true;
      banner.dataset.tone = '';
      return;
    }
    banner.hidden = false;
    banner.dataset.tone = warning.tone;
    _el('retirement-warning-title').textContent = warning.title;
    _el('retirement-warning-copy').textContent = warning.copy;
  }

  function _renderSummary(result, mode = 'saved') {
    const summary = (result && result.summary) || {};
    const activePayload = state.activePlan || {};
    _el('retirement-summary-current').textContent = _summaryCurrency(summary.currentPortfolioValue, _summaryCurrency(summary.projectedCurrentPortfolioValue));
    _el('retirement-summary-transition').textContent = _summaryCurrency(summary.retirementPortfolioValue, _summaryCurrency(summary.projectedRetirementPortfolioValue));
    _el('retirement-summary-final').textContent = _summaryCurrency(summary.finalPortfolioValue, _summaryCurrency(summary.projectedFinalPortfolioValue));
    _el('retirement-summary-duration').textContent = _isFiniteNumber(summary.monthsAfterRetirement) ? _formatDuration(summary.monthsAfterRetirement) : '—';
    _el('retirement-summary-spending').textContent = _isFiniteNumber(activePayload.monthlyRetirementSpending) ? `${_formatCurrency(activePayload.monthlyRetirementSpending)}/mo` : '—';
    _el('retirement-summary-lasts').textContent = summary.lastsToTargetAge
      ? `Covers age ${summary.targetAge || 88.6}`
      : `Runs out before ${summary.targetAge || 88.6}`;
    _el('retirement-summary-monte-carlo').textContent = _summaryMonteCarloText(summary, result, activePayload);
    _el('retirement-summary-history').textContent = _summaryHistoryText(summary, activePayload);

    const transition = _el('retirement-transition-date');
    if (transition) {
      transition.textContent = summary.transitionDate ? _formatMonthYear(summary.transitionDate) : '—';
    }
    const heroDuration = _el('retirement-duration-hero');
    if (heroDuration) {
      heroDuration.textContent = summary.lastsToTargetAge
        ? `To age ${summary.targetAge || 88.6}`
        : (summary.depletionDate ? `Until ${_formatMonthYear(summary.depletionDate)}` : '—');
    }

    _setChartBadge(mode === 'preview' ? 'Instant preview' : 'Saved scenario', mode === 'preview' ? 'preview' : 'saved');
    _renderWarning(summary);
  }

  function _syncRangeButtons() {
    document.querySelectorAll('[data-retirement-range]').forEach((button) => {
      button.classList.toggle('is-active', button.dataset.retirementRange === state.chartRange);
    });
  }

  function _chartPrefsKey(suffix) {
    return `retirementChart:${suffix}`;
  }

  function _restoreChartPrefs() {
    try {
      state.chartScaleMode = window.localStorage.getItem(_chartPrefsKey('scaleMode')) || 'linear';
      state.chartYZoom = _clamp(_safeNumber(window.localStorage.getItem(_chartPrefsKey('yZoom')), 100), 10, 100);
      state.chartYPan = _clamp(_safeNumber(window.localStorage.getItem(_chartPrefsKey('yPan')), 0), 0, 100);
    } catch (_error) {
      state.chartScaleMode = 'linear';
      state.chartYZoom = 100;
      state.chartYPan = 0;
    }
  }

  function _persistChartPrefs() {
    try {
      window.localStorage.setItem(_chartPrefsKey('scaleMode'), state.chartScaleMode);
      window.localStorage.setItem(_chartPrefsKey('yZoom'), String(state.chartYZoom));
      window.localStorage.setItem(_chartPrefsKey('yPan'), String(state.chartYPan));
    } catch (_error) {
      // ignore storage failures
    }
  }

  function _syncChartControls() {
    const scale = _el('retirement-chart-scale-mode');
    const zoom = _el('retirement-chart-y-zoom');
    const pan = _el('retirement-chart-y-pan');
    const zoomValue = _el('retirement-chart-y-zoom-value');
    const panValue = _el('retirement-chart-y-pan-value');
    const panRow = _el('retirement-chart-y-pan-row');
    const helper = _el('retirement-chart-scale-helper');

    if (scale) scale.value = state.chartScaleMode;
    if (zoom) zoom.value = String(state.chartYZoom);
    if (pan) pan.value = String(state.chartYPan);
    if (zoomValue) zoomValue.textContent = `${state.chartYZoom}% of full height`;
    if (panValue) {
      if (state.chartScaleMode === 'log') {
        panValue.textContent = 'Handled by log scale';
      } else if (state.chartYZoom >= 100) {
        panValue.textContent = 'Not needed at full height';
      } else if (state.chartYPan <= 10) {
        panValue.textContent = 'Focused on lower values';
      } else if (state.chartYPan >= 90) {
        panValue.textContent = 'Focused on upper values';
      } else {
        panValue.textContent = 'Mid-range focus';
      }
    }
    if (zoom) zoom.disabled = state.chartScaleMode === 'log';
    if (pan) pan.disabled = state.chartScaleMode === 'log' || state.chartYZoom >= 100;
    if (panRow) panRow.hidden = state.chartScaleMode === 'log';
    if (helper) {
      helper.textContent = state.chartScaleMode === 'log'
        ? 'Log scale keeps small real balances visible next to very large future values.'
        : 'Use Y zoom + Y scroll to inspect the lower part of the chart when the forecast shoots much higher than today.';
    }
  }

  function _renderChart(result) {
    const canvas = _el('retirement-forecast-chart');
    if (!canvas || !window.RetirementChart) return;
    const model = window.RetirementChart.buildRetirementChartModel({
      ...(result && result.series ? result.series : {}),
      mobile: window.matchMedia('(max-width: 640px)').matches,
      range: state.chartRange,
    });

    if (state.chart) {
      state.chart.destroy();
    }

    state.chart = window.RetirementChart.createRetirementChart(canvas, model, _formatCurrency, {
      scaleMode: state.chartScaleMode,
      yZoomPercent: state.chartYZoom,
      yPanPercent: state.chartYPan,
    });
    _syncRangeButtons();
    _syncChartControls();
  }

  function _buildPreviewFromPayload(payload) {
    if (!window.RetirementSimulation) return null;
    const actual = _activeActualSeries();
    const projection = window.RetirementSimulation.simulateRetirementProjection({
      dateOfBirth: payload.dateOfBirth,
      investingStartDate: payload.investingStartDate,
      retirementAge: payload.retirementAge,
      targetAge: 88.6,
      monthlyInvestment: payload.monthlyInvestment,
      yearlyReturnBeforeRetirement: payload.expectedYearlyReturnWorking,
      yearlyReturnAfterRetirement: payload.expectedYearlyReturnAfterRetirement,
      monthlyRetirementWithdrawals: payload.monthlyRetirementSpending,
      monthlyWithdrawalGrowthRate: payload.inflationRate,
      annualFeeRate: payload.annualFeeRate,
      initialInvestmentAmount: payload.initialInvestmentAmount,
      simulationYears: 40,
      currentPortfolioValue: _currentPortfolioValue(),
      actualSeries: actual,
      anchorDate: (actual.slice(-1)[0] || {}).date || _todayIso(),
    });
    return {
      summary: {
        ...projection.summary,
        monteCarloSuccessProbability: payload.monteCarloEnabled
          ? ((state.activeResult && state.activeResult.summary && state.activeResult.summary.monteCarloSuccessProbability) ?? null)
          : null,
      },
      series: {
        ...projection.series,
        monteCarloP10: [],
        monteCarloP50: [],
        monteCarloP90: [],
      },
    };
  }

  function _applyPreview(payload, options = {}) {
    const preview = _buildPreviewFromPayload(payload);
    state.previewResult = preview;
    state.activePlan = { ...(state.activePlan || {}), ...payload };
    _updateHeroInputs(payload);
    _renderSummary(preview, 'preview');
    _renderChart(preview);
    if (!options.quiet) {
      _setStatus('Preview updated', 'preview');
    }
    return preview;
  }

  function _validateDraftSimulation(payload) {
    _buildPreviewFromPayload(payload);
  }

  function _bindDraftInputs() {
    const ids = [
      'retirement-plan-name',
      'retirement-birth-date',
      'retirement-started-date',
      'retirement-retirement-age',
      'retirement-monthly-investment',
      'retirement-working-return',
      'retirement-retired-return',
      'retirement-monthly-spending',
      'retirement-initial-investment',
      'retirement-inflation-rate',
      'retirement-annual-fee-rate',
      'retirement-monte-carlo-runs',
      'retirement-working-volatility',
      'retirement-retired-volatility',
      'retirement-notes',
      'retirement-income-streams',
      'retirement-one-time-events',
      'retirement-spending-phases',
      'retirement-return-phases',
      'retirement-monte-carlo-enabled',
    ];
    ids.forEach((id) => {
      const node = _el(id);
      if (!node || node.dataset.retirementBound === 'true') return;
      const eventName = node.tagName === 'INPUT' && node.type === 'checkbox' ? 'change' : 'input';
      node.addEventListener(eventName, () => {
        clearTimeout(state.draftTimer);
        state.draftTimer = window.setTimeout(() => {
          try {
            const payload = _readPlanForm();
            _applyPreview(payload, { quiet: true });
          } catch (_error) {
            _setStatus('Editing… complete the inputs for a fresh preview.', 'muted');
            _setChartBadge('Draft in progress', 'muted');
          }
        }, 160);
      });
      node.dataset.retirementBound = 'true';
    });
  }

  async function _loadActualSeries() {
    if (!window.PortfolioClient || typeof window.PortfolioClient.listSnapshots !== 'function') {
      state.actualSeries = [];
      return;
    }
    const payload = await window.PortfolioClient.listSnapshots('summary').catch(() => ({ snapshots: [] }));
    state.actualSeries = (payload.snapshots || [])
      .filter((row) => row && row.snapshotDate)
      .map((row) => ({
        date: String(row.snapshotDate).slice(0, 10),
        value: Number(row.portfolioValue || 0),
        phase: 'actual',
      }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }

  async function _loadPlan(planId) {
    _setBusy('preview', true);
    _setStatus('Loading saved plan…');
    try {
      const payload = await RetirementPlansClient.getPlan(planId);
      state.activePlanId = payload.plan.planId;
      state.activePlan = payload.plan;
      state.activeResult = payload.result;
      state.previewResult = null;
      _fillPlanForm(payload.plan);
      _renderPlanList();
      _renderSummary(payload.result, 'saved');
      _renderChart(payload.result);
      _setStatus(`Loaded ${payload.plan.name}`, 'success');
    } finally {
      _setBusy('preview', false);
    }
  }

  async function _refreshPlans(preferredPlanId) {
    const response = await RetirementPlansClient.listPlans();
    state.plans = response.plans || [];
    _renderPlanList();

    const selectedPlanId = preferredPlanId
      || state.activePlanId
      || (state.plans[0] && state.plans[0].planId);

    if (selectedPlanId) {
      await _loadPlan(selectedPlanId);
      return;
    }

    state.activePlanId = null;
    state.activePlan = _defaultPlan();
    state.activeResult = null;
    state.previewResult = null;
    _fillPlanForm(state.activePlan);
    _applyPreview(state.activePlan, { quiet: true });
    _setStatus('Start with the default template, then save your favorite scenario.');
  }

  async function createNewPlan() {
    _setBusy('create', true);
    try {
      state.activePlanId = null;
      state.activePlan = _defaultPlan();
      state.activeResult = null;
      state.previewResult = null;
      _fillPlanForm(state.activePlan);
      _renderPlanList();
      _applyPreview(state.activePlan, { quiet: true });
      _setStatus('Fresh plan ready', 'success');
    } finally {
      _setBusy('create', false);
    }
  }

  async function saveCurrentPlan() {
    _setBusy('save', true);
    try {
      _setStatus('Saving plan and forecast…');
      const payload = _readPlanForm();
      _applyPreview(payload, { quiet: true });
      const saved = await RetirementPlansClient.savePlan(payload);
      state.activePlanId = saved.plan.planId;
      state.activePlan = saved.plan;
      state.activeResult = saved.result;
      state.previewResult = null;
      _fillPlanForm(saved.plan);
      _renderSummary(saved.result, 'saved');
      _renderChart(saved.result);
      await _refreshPlans(saved.plan.planId);
      _setStatus('Plan saved', 'success');
    } catch (error) {
      console.error('[RetirementForecast] save failed', error);
      _setStatus(error.message || 'Save failed', 'danger');
    } finally {
      _setBusy('save', false);
    }
  }

  async function rerunCurrentPlan() {
    _setBusy('preview', true);
    try {
      const payload = _readPlanForm();
      _applyPreview(payload, { quiet: true });
      if (!state.activePlanId) {
        _setStatus('Preview refreshed locally', 'success');
        return;
      }
      _setStatus('Refreshing saved forecast…');
      const saved = await RetirementPlansClient.simulatePlan(state.activePlanId, payload);
      state.activePlan = saved.plan;
      state.activeResult = saved.result;
      state.previewResult = null;
      _fillPlanForm(saved.plan);
      _renderSummary(saved.result, 'saved');
      _renderChart(saved.result);
      await _refreshPlans(saved.plan.planId);
      _setStatus('Forecast refreshed', 'success');
    } catch (error) {
      console.error('[RetirementForecast] simulate failed', error);
      _setStatus(error.message || 'Preview failed', 'danger');
    } finally {
      _setBusy('preview', false);
    }
  }

  async function deleteCurrentPlan() {
    if (!state.activePlanId) {
      await createNewPlan();
      return;
    }
    if (!window.confirm('Delete this retirement plan? This also removes its saved forecast snapshots.')) {
      return;
    }
    _setBusy('delete', true);
    try {
      _setStatus('Deleting plan…');
      await RetirementPlansClient.deletePlan(state.activePlanId);
      state.activePlanId = null;
      await _refreshPlans(null);
      _setStatus('Plan deleted', 'success');
    } catch (error) {
      console.error('[RetirementForecast] delete failed', error);
      _setStatus(error.message || 'Delete failed', 'danger');
    } finally {
      _setBusy('delete', false);
    }
  }

  async function initRetirementTab() {
    if (!_el('tab-retirement')) return;
    if (!state.initialized) {
      state.initialized = true;
      _restoreChartPrefs();
      _el('retirement-create-btn')?.addEventListener('click', createNewPlan);
      _el('retirement-save-btn')?.addEventListener('click', saveCurrentPlan);
      _el('retirement-rerun-btn')?.addEventListener('click', rerunCurrentPlan);
      _el('retirement-delete-btn')?.addEventListener('click', deleteCurrentPlan);
      _el('retirement-chart-scale-mode')?.addEventListener('change', (event) => {
        state.chartScaleMode = event.target.value === 'log' ? 'log' : 'linear';
        if (state.chartScaleMode === 'log') {
          state.chartYPan = 0;
        }
        _persistChartPrefs();
        if (state.previewResult || state.activeResult) {
          _renderChart(state.previewResult || state.activeResult);
        } else {
          _syncChartControls();
        }
      });
      _el('retirement-chart-y-zoom')?.addEventListener('input', (event) => {
        state.chartYZoom = _clamp(_safeNumber(event.target.value, 100), 10, 100);
        if (state.chartYZoom >= 100) {
          state.chartYPan = 0;
        }
        _persistChartPrefs();
        if (state.previewResult || state.activeResult) {
          _renderChart(state.previewResult || state.activeResult);
        } else {
          _syncChartControls();
        }
      });
      _el('retirement-chart-y-pan')?.addEventListener('input', (event) => {
        state.chartYPan = _clamp(_safeNumber(event.target.value, 0), 0, 100);
        _persistChartPrefs();
        if (state.previewResult || state.activeResult) {
          _renderChart(state.previewResult || state.activeResult);
        } else {
          _syncChartControls();
        }
      });
      _el('retirement-chart-focus-lower-btn')?.addEventListener('click', () => {
        state.chartScaleMode = 'linear';
        state.chartYZoom = 22;
        state.chartYPan = 0;
        _persistChartPrefs();
        if (state.previewResult || state.activeResult) {
          _renderChart(state.previewResult || state.activeResult);
        } else {
          _syncChartControls();
        }
      });
      _el('retirement-chart-fit-all-btn')?.addEventListener('click', () => {
        state.chartScaleMode = 'linear';
        state.chartYZoom = 100;
        state.chartYPan = 0;
        _persistChartPrefs();
        if (state.previewResult || state.activeResult) {
          _renderChart(state.previewResult || state.activeResult);
        } else {
          _syncChartControls();
        }
      });
      _el('retirement-chart-log-btn')?.addEventListener('click', () => {
        state.chartScaleMode = 'log';
        state.chartYPan = 0;
        _persistChartPrefs();
        if (state.previewResult || state.activeResult) {
          _renderChart(state.previewResult || state.activeResult);
        } else {
          _syncChartControls();
        }
      });
      _el('retirement-chart-scroll-surface')?.addEventListener('wheel', (event) => {
        if (state.chartScaleMode === 'log' || state.chartYZoom >= 100) {
          return;
        }
        event.preventDefault();
        state.chartYPan = _clamp(state.chartYPan + (Math.sign(event.deltaY) * 4), 0, 100);
        _persistChartPrefs();
        if (state.previewResult || state.activeResult) {
          _renderChart(state.previewResult || state.activeResult);
        } else {
          _syncChartControls();
        }
      }, { passive: false });
      _bindDraftInputs();
      window.addEventListener('resize', () => {
        if (state.previewResult || state.activeResult) {
          _renderChart(state.previewResult || state.activeResult);
        }
      });
    }
    try {
      await _loadActualSeries();
      await _refreshPlans(state.activePlanId);
    } catch (error) {
      console.error('[RetirementForecast] init failed', error);
      _setStatus(error.message || 'Failed to load retirement plans', 'danger');
    }
  }

  window.RetirementPlansClient = RetirementPlansClient;
  window.RetirementForecast = {
    initRetirementTab,
    createNewPlan,
    saveCurrentPlan,
    rerunCurrentPlan,
    deleteCurrentPlan,
    async selectPlan(planId) {
      try {
        await _loadPlan(planId);
      } catch (error) {
        console.error('[RetirementForecast] plan load failed', error);
        _setStatus(error.message || 'Failed to load plan', 'danger');
      }
    },
  };
  window.setRetirementChartRange = function setRetirementChartRange(range) {
    state.chartRange = range || 'ALL';
    if (state.previewResult || state.activeResult) {
      _renderChart(state.previewResult || state.activeResult);
    } else {
      _syncRangeButtons();
    }
  };
  window.setRetirementChartScaleMode = function setRetirementChartScaleMode(mode) {
    state.chartScaleMode = mode === 'log' ? 'log' : 'linear';
    if (state.chartScaleMode === 'log') {
      state.chartYPan = 0;
    }
    _persistChartPrefs();
    if (state.previewResult || state.activeResult) {
      _renderChart(state.previewResult || state.activeResult);
    } else {
      _syncChartControls();
    }
  };
  window.initRetirementTab = initRetirementTab;
})();
