(() => {
  function _toNumber(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  }

  function _normalizeSeries(points, phase) {
    return (points || [])
      .filter((point) => point && point.date)
      .map((point) => ({
        date: String(point.date).slice(0, 10),
        value: _toNumber(point.value, 0),
        phase: point.phase || phase,
      }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }

  function _dedupeByDate(points) {
    const map = new Map();
    (points || []).forEach((point) => {
      map.set(point.date, point);
    });
    return [...map.values()].sort((a, b) => a.date.localeCompare(b.date));
  }

  function _subtractYears(isoDate, years) {
    const parsed = new Date(`${String(isoDate).slice(0, 10)}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime())) return null;
    parsed.setUTCFullYear(parsed.getUTCFullYear() - years);
    return parsed.toISOString().slice(0, 10);
  }

  function filterHistoricalRange(actualPoints, range) {
    const actual = _normalizeSeries(actualPoints, 'actual');
    if (!actual.length || !range || range === 'ALL') {
      return actual;
    }
    const years = Number(String(range).replace(/[^0-9]/g, ''));
    if (!Number.isFinite(years) || years <= 0) {
      return actual;
    }
    const anchorDate = actual[actual.length - 1].date;
    const cutoff = _subtractYears(anchorDate, years);
    if (!cutoff) {
      return actual;
    }
    return actual.filter((point) => point.date >= cutoff);
  }

  function buildProjectionBridge(actualPoints, projectedPoints) {
    const actual = _normalizeSeries(actualPoints, 'actual');
    const projected = _normalizeSeries(projectedPoints, 'projected');
    if (!actual.length || !projected.length) {
      return projected;
    }
    const lastActual = actual[actual.length - 1];
    const firstProjected = projected[0];
    const bridge = {
      date: lastActual.date,
      value: lastActual.value,
      phase: 'transition',
      synthetic: true,
    };
    if (firstProjected.date === lastActual.date) {
      return [bridge, ...projected.slice(1)];
    }
    return [bridge, ...projected];
  }

  function compressLongTimeline(points, maxPoints = 220) {
    const source = _normalizeSeries(points, 'series');
    if (source.length <= maxPoints) {
      return source;
    }
    const compressed = [];
    const lastIndex = source.length - 1;
    for (let index = 0; index < maxPoints; index += 1) {
      const sourceIndex = Math.round((index / (maxPoints - 1)) * lastIndex);
      compressed.push(source[sourceIndex]);
    }
    return _dedupeByDate(compressed);
  }

  function _clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function _collectFiniteValues(datasets) {
    return (datasets || [])
      .flatMap((dataset) => dataset.data || [])
      .filter((value) => Number.isFinite(value));
  }

  function _formatAxisCurrency(value) {
    const numeric = Math.abs(_toNumber(value, 0));
    if (numeric >= 1000000) {
      return `${(value / 1000000).toLocaleString('pl-PL', { maximumFractionDigits: 1 })}M PLN`;
    }
    if (numeric >= 1000) {
      return `${(value / 1000).toLocaleString('pl-PL', { maximumFractionDigits: 0 })}k PLN`;
    }
    return `${Number(value).toLocaleString('pl-PL', { maximumFractionDigits: 0 })} PLN`;
  }

  function resolveYScaleState(datasets, chartState = {}) {
    const scaleMode = chartState.scaleMode === 'log' ? 'log' : 'linear';
    const values = _collectFiniteValues(datasets).filter((value) => (scaleMode === 'log' ? value > 0 : true));
    const fallback = {
      type: scaleMode === 'log' ? 'logarithmic' : 'linear',
      ticks: {
        color: '#9cb9d1',
        callback(value) {
          return _formatAxisCurrency(value);
        },
      },
      grid: {
        color: 'rgba(156, 185, 209, 0.08)',
      },
    };
    if (!values.length) {
      return fallback;
    }

    if (scaleMode === 'log') {
      const min = Math.min(...values);
      const max = Math.max(...values);
      return {
        ...fallback,
        min: Math.max(min * 0.82, 1),
        max: Math.max(max * 1.08, min * 1.25),
      };
    }

    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);
    const span = Math.max(1, rawMax - rawMin);
    const paddedMin = rawMin <= 0 ? 0 : Math.max(0, rawMin - span * 0.08);
    const paddedMax = rawMax + span * 0.08;
    const paddedSpan = Math.max(1, paddedMax - paddedMin);
    const zoomPercent = _clamp(_toNumber(chartState.yZoomPercent, 100), 10, 100);
    const panPercent = _clamp(_toNumber(chartState.yPanPercent, 0), 0, 100);
    const visibleSpan = Math.max(1, paddedSpan * (zoomPercent / 100));
    const maxOffset = Math.max(0, paddedSpan - visibleSpan);
    const min = paddedMin + (maxOffset * (panPercent / 100));
    return {
      ...fallback,
      min,
      max: min + visibleSpan,
    };
  }

  function generateLinearLabels(startDate, endDate, maxLabels = 420) {
    if (!startDate || !endDate || endDate <= startDate) {
      return [];
    }
    const start = new Date(`${startDate}T00:00:00Z`);
    const end = new Date(`${endDate}T00:00:00Z`);
    const totalDays = Math.floor((end - start) / (24 * 60 * 60 * 1000));
    const step = Math.max(1, Math.ceil(totalDays / maxLabels));
    const labels = [];
    for (let day = 0; day <= totalDays; day += step) {
      const date = new Date(start);
      date.setUTCDate(date.getUTCDate() + day);
      labels.push(date.toISOString().slice(0, 10));
    }
    // Ensure end date is included
    const lastLabel = labels[labels.length - 1];
    if (lastLabel !== endDate) {
      labels.push(endDate);
    }
    return labels;
  }

  function buildRetirementChartModel({
    actual = [],
    projectedPast = [],
    futureFromActual = [],
    futureFromProjected = [],
    transitionMarker = [],
    todayMarker = [],
    monteCarloP10 = [],
    monteCarloP50 = [],
    monteCarloP90 = [],
    mobile = false,
    range = 'ALL',
  } = {}) {
    const normalizedActual = filterHistoricalRange(actual, range);
    const normalizedProjectedPast = filterHistoricalRange(projectedPast, range);
    const maxPoints = mobile ? 180 : 420;
    
    // Normalize all series first (without compressing)
    const historicalNorm = _normalizeSeries(normalizedActual, 'actual');
    const projectedHistoryNorm = _normalizeSeries(normalizedProjectedPast, 'projected');
    const actualFutureNorm = _normalizeSeries(futureFromActual, 'future-actual');
    const projectedFutureNorm = _normalizeSeries(futureFromProjected, 'future-projected');
    const lowerNorm = mobile ? [] : _normalizeSeries(monteCarloP10, 'confidence-low');
    const middleNorm = mobile ? [] : _normalizeSeries(monteCarloP50, 'confidence-mid');
    const upperNorm = mobile ? [] : _normalizeSeries(monteCarloP90, 'confidence-high');
    
    // Collect all dates to find the overall date range
    const marker = (transitionMarker || [])[0] || null;
    const today = (todayMarker || [])[0] || null;
    
    const allDates = [
      ...historicalNorm.map((p) => p.date),
      ...projectedHistoryNorm.map((p) => p.date),
      ...actualFutureNorm.map((p) => p.date),
      ...projectedFutureNorm.map((p) => p.date),
      ...lowerNorm.map((p) => p.date),
      ...upperNorm.map((p) => p.date),
    ].sort();
    
    if (allDates.length === 0) {
      return { labels: [], series: {}, datasetLabels: {} };
    }
    
    const startDate = allDates[0];
    const endDate = allDates[allDates.length - 1];
    
    // Generate linear labels from start to end date
    let linearLabels = generateLinearLabels(startDate, endDate, maxPoints);
    
    // Ensure all critical dates are included (to avoid gaps)
    const criticalDates = [
      startDate,
      endDate,
      ...historicalNorm.map((p) => p.date),
      ...projectedHistoryNorm.map((p) => p.date),
      ...actualFutureNorm.map((p) => p.date),
      ...projectedFutureNorm.map((p) => p.date),
      marker?.date,
      today?.date,
    ].filter((d) => d);
    
    linearLabels = [...new Set([...linearLabels, ...criticalDates])].sort();
    
    // Helper to resample series to linear labels (use nearest neighbor)
    function resampleToLinearLabels(series, labels) {
      if (!series || series.length === 0) return [];
      
      return labels.map((label) => {
        const found = series.find((p) => p.date === label);
        if (found) return found;
        // Find nearest point if exact date not found
        let nearest = series[0];
        let minDiff = Math.abs(new Date(series[0].date) - new Date(label));
        for (const point of series) {
          const diff = Math.abs(new Date(point.date) - new Date(label));
          if (diff < minDiff) {
            minDiff = diff;
            nearest = point;
          }
        }
        return nearest;
      });
    }
    
    // Resample all series to linear labels
    const historical = resampleToLinearLabels(historicalNorm, linearLabels);
    const projectedHistory = resampleToLinearLabels(projectedHistoryNorm, linearLabels);
    const actualFuture = resampleToLinearLabels(actualFutureNorm, linearLabels);
    const projectedFuture = resampleToLinearLabels(projectedFutureNorm, linearLabels);
    const lower = mobile ? [] : resampleToLinearLabels(lowerNorm, linearLabels);
    const middle = mobile ? [] : resampleToLinearLabels(middleNorm, linearLabels);
    const upper = mobile ? [] : resampleToLinearLabels(upperNorm, linearLabels);

    return {
      labels: linearLabels,
      series: {
        historical,
        projectedHistory,
        actualFuture,
        projectedFuture,
        lower,
        middle,
        upper,
        marker,
        today,
      },
      datasetLabels: {
        historical: 'Actual portfolio history',
        projectedHistory: 'Projected history',
        actualFuture: 'Future from actual value',
        projectedFuture: 'Future from projected value',
        lower: 'Lower range (P10)',
        middle: 'Middle range (P50)',
        upper: 'Upper range (P90)',
        marker: 'Retirement start',
        today: 'Today',
      },
    };
  }

  function createRetirementChart(canvas, model, formatCurrency, chartState = {}) {
    if (!canvas || typeof Chart === 'undefined') return null;
    const currencyFormatter = typeof formatCurrency === 'function' ? formatCurrency : ((value) => `${value}`);
    const labels = model.labels || [];
    const scaleMode = chartState.scaleMode === 'log' ? 'log' : 'linear';

    function toValueMap(points) {
      return new Map((points || []).filter((point) => point && point.date).map((point) => [point.date, point.value]));
    }

    function chartValue(value) {
      const numeric = _toNumber(value, 0);
      if (scaleMode === 'log' && numeric <= 0) {
        return null;
      }
      return numeric;
    }

    const historicalMap = toValueMap(model.series.historical);
    const projectedHistoryMap = toValueMap(model.series.projectedHistory);
    const actualFutureMap = toValueMap(model.series.actualFuture);
    const projectedFutureMap = toValueMap(model.series.projectedFuture);
    const lowerMap = toValueMap(model.series.lower);
    const middleMap = toValueMap(model.series.middle);
    const upperMap = toValueMap(model.series.upper);
    const marker = model.series.marker;
    const today = model.series.today;
    const mobile = window.matchMedia('(max-width: 640px)').matches;

    const datasets = [
      {
        label: model.datasetLabels.historical,
        data: labels.map((label) => (historicalMap.has(label) ? chartValue(historicalMap.get(label)) : null)),
        borderColor: '#2b88cf',
        backgroundColor: 'rgba(43, 136, 207, 0.14)',
        borderWidth: 2.2,
        tension: 0.28,
        pointRadius: 0,
        pointHitRadius: 10,
        spanGaps: true,
      },
      {
        label: model.datasetLabels.projectedHistory,
        data: labels.map((label) => (projectedHistoryMap.has(label) ? chartValue(projectedHistoryMap.get(label)) : null)),
        borderColor: '#9bc8ff',
        backgroundColor: 'rgba(155, 200, 255, 0.18)',
        borderWidth: 2.4,
        borderDash: [7, 4],
        tension: 0.28,
        pointRadius: 0,
        pointHitRadius: 10,
        spanGaps: true,
      },
      {
        label: model.datasetLabels.actualFuture,
        data: labels.map((label) => (actualFutureMap.has(label) ? chartValue(actualFutureMap.get(label)) : null)),
        borderColor: '#36c78b',
        backgroundColor: 'rgba(54, 199, 139, 0.18)',
        borderWidth: 2.5,
        tension: 0.24,
        pointRadius: 0,
        pointHitRadius: 10,
        spanGaps: true,
      },
      {
        label: model.datasetLabels.projectedFuture,
        data: labels.map((label) => (projectedFutureMap.has(label) ? chartValue(projectedFutureMap.get(label)) : null)),
        borderColor: '#c27bff',
        backgroundColor: 'rgba(194, 123, 255, 0.14)',
        borderWidth: 2,
        borderDash: [7, 4],
        tension: 0.24,
        pointRadius: 0,
        pointHitRadius: 10,
        spanGaps: true,
      },
    ];

    if (!mobile && model.series.lower && model.series.lower.some((p) => p) && model.series.upper && model.series.upper.some((p) => p)) {
      datasets.push(
        {
            label: model.datasetLabels.lower,
            data: labels.map((label) => (lowerMap.has(label) ? chartValue(lowerMap.get(label)) : null)),
          borderColor: 'rgba(255, 155, 144, 0.6)',
          borderDash: [6, 6],
          borderWidth: 1.5,
          pointRadius: 0,
          spanGaps: true,
          hidden: true,
        },
        {
            label: model.datasetLabels.middle,
            data: labels.map((label) => (middleMap.has(label) ? chartValue(middleMap.get(label)) : null)),
          borderColor: 'rgba(255, 208, 110, 0.9)',
          borderDash: [4, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          spanGaps: true,
          hidden: true,
        },
        {
            label: model.datasetLabels.upper,
            data: labels.map((label) => (upperMap.has(label) ? chartValue(upperMap.get(label)) : null)),
          borderColor: 'rgba(126, 226, 168, 0.8)',
          borderDash: [6, 6],
          borderWidth: 1.5,
          pointRadius: 0,
          spanGaps: true,
          hidden: true,
        },
      );
    }

    if (marker && marker.date) {
      datasets.push({
        label: model.datasetLabels.marker,
        data: labels.map((label) => (label === marker.date ? chartValue(marker.value) : null)),
        borderColor: '#f4b942',
        backgroundColor: '#f4b942',
        pointRadius: 5,
        pointHoverRadius: 6,
        showLine: false,
      });
    }

    if (today && today.date) {
      datasets.push({
        label: model.datasetLabels.today,
        data: labels.map((label) => (label === today.date ? chartValue(today.value) : null)),
        borderColor: '#ffffff',
        backgroundColor: '#ffffff',
        pointRadius: 4,
        pointHoverRadius: 5,
        showLine: false,
      });
    }

    const yScale = resolveYScaleState(datasets, chartState);

    return new Chart(canvas, {
      type: 'line',
      data: { labels, datasets },
      options: {
        maintainAspectRatio: false,
        animation: {
          duration: 380,
          easing: 'easeOutQuart',
        },
        interaction: {
          intersect: false,
          mode: 'index',
        },
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              color: '#d8ebfb',
              boxWidth: 10,
              boxHeight: 10,
              usePointStyle: true,
              padding: mobile ? 12 : 16,
            },
          },
          tooltip: {
            backgroundColor: 'rgba(8, 18, 28, 0.94)',
            borderColor: 'rgba(74, 159, 212, 0.18)',
            borderWidth: 1,
            callbacks: {
              title(items) {
                return items && items[0] ? items[0].label : '';
              },
              label(context) {
                return `${context.dataset.label}: ${currencyFormatter(context.parsed.y || 0)}`;
              },
              footer(items) {
                if (!items || !items.length) return '';
                const label = items[0].dataset.label || '';
                if (label === 'Retirement start') {
                  return 'Retirement starts here';
                }
                if (label === 'Today') {
                  return 'This is the split point for both future projections';
                }
                if (label === 'Actual portfolio history') {
                  return 'Actual value from stored snapshots';
                }
                if (label === 'Projected history') {
                  return 'A monthly-compounded backtest using your investing start date, monthly contribution, and pre-retirement yearly return';
                }
                if (label === 'Future from actual value') {
                  return 'Projection starting from the real portfolio value today';
                }
                if (label === 'Future from projected value') {
                  return 'Projection starting from the theoretical portfolio value today';
                }
                if (label === 'Lower range (P10)') {
                  return '10th percentile: only 10% of simulated paths finished lower than this line';
                }
                if (label === 'Middle range (P50)') {
                  return '50th percentile: the median simulated path';
                }
                if (label === 'Upper range (P90)') {
                  return '90th percentile: only 10% of simulated paths finished higher than this line';
                }
                return 'Scenario range';
              },
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color: '#9cb9d1',
              maxTicksLimit: mobile ? 6 : 10,
            },
            grid: {
              color: 'rgba(156, 185, 209, 0.08)',
            },
          },
          y: {
            ...yScale,
          },
        },
      },
    });
  }

  const RetirementChart = {
    buildProjectionBridge,
    filterHistoricalRange,
    compressLongTimeline,
    buildRetirementChartModel,
    resolveYScaleState,
    createRetirementChart,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = RetirementChart;
  }
  if (typeof window !== 'undefined') {
    window.RetirementChart = RetirementChart;
  }
})();
