(() => {
  function toNumber(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  }

  function isoToday() {
    return new Date().toISOString().slice(0, 10);
  }

  function parseDate(value) {
    if (!value) return null;
    const parsed = new Date(`${String(value).slice(0, 10)}T00:00:00Z`);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function toIsoDate(value) {
    const parsed = value instanceof Date ? value : parseDate(value);
    return parsed ? parsed.toISOString().slice(0, 10) : null;
  }

  function addMonths(isoDate, monthsToAdd) {
    const base = parseDate(isoDate) || parseDate(isoToday());
    const year = base.getUTCFullYear();
    const month = base.getUTCMonth();
    const day = base.getUTCDate();
    const target = new Date(Date.UTC(year, month + monthsToAdd + 1, 0));
    const lastDay = target.getUTCDate();
    return new Date(Date.UTC(year, month + monthsToAdd, Math.min(day, lastDay)))
      .toISOString()
      .slice(0, 10);
  }

  function addYears(isoDate, yearsToAdd) {
    const months = Math.round(toNumber(yearsToAdd, 0) * 12);
    return addMonths(isoDate, months);
  }

  function annualToMonthlyRate(percentRate) {
    const decimalRate = toNumber(percentRate, 0) / 100;
    if (decimalRate <= -1) return -1;
    return Math.pow(1 + decimalRate, 1 / 12) - 1;
  }

  function annualFeeToMonthlyRate(percentRate) {
    const decimalRate = Math.max(0, toNumber(percentRate, 0)) / 100;
    if (decimalRate <= 0) return 0;
    if (decimalRate >= 1) return 1;
    return 1 - Math.pow(1 - decimalRate, 1 / 12);
  }

  function monthsBetween(startIso, endIso) {
    const start = parseDate(startIso);
    const end = parseDate(endIso);
    if (!start || !end || end <= start) return 0;
    let months = (end.getUTCFullYear() - start.getUTCFullYear()) * 12 + (end.getUTCMonth() - start.getUTCMonth());
    while (months > 0 && parseDate(addMonths(startIso, months)) > end) {
      months -= 1;
    }
    while (parseDate(addMonths(startIso, months + 1)) <= end) {
      months += 1;
    }
    return Math.max(0, months);
  }

  function ageOnDate(birthDateIso, asOfIso) {
    const birth = parseDate(birthDateIso);
    const asOf = parseDate(asOfIso);
    if (!birth || !asOf) return NaN;
    return Math.max(0, (asOf.getTime() - birth.getTime()) / (365.2425 * 24 * 60 * 60 * 1000));
  }

  function buildChartReadyOutput(points) {
    return {
      labels: points.map((point) => point.date),
      portfolioValues: points.map((point) => point.portfolioValue),
      contributions: points.map((point) => point.contribution),
      requestedWithdrawals: points.map((point) => point.requestedWithdrawal),
      actualWithdrawals: points.map((point) => point.actualWithdrawal),
      shortfalls: points.map((point) => point.shortfall),
      phases: points.map((point) => point.phase),
      points,
    };
  }

  function resolveDateInputs(input) {
    const today = isoToday();
    const birthDate = toIsoDate(input.dateOfBirth)
      || addYears(today, -toNumber(input.currentAge, 35));
    const investingStartDate = toIsoDate(input.investingStartDate)
      || addYears(birthDate, toNumber(input.ageStartedInvesting, toNumber(input.currentAge, 35)));
    const retirementDate = toIsoDate(input.retirementDate)
      || addYears(birthDate, toNumber(input.retirementAge, 65));
    const targetAge = toNumber(input.targetAge, 88.6);
    const targetDate = toIsoDate(input.targetDate) || addYears(birthDate, targetAge);
    const actualSeries = Array.isArray(input.actualSeries) ? input.actualSeries : [];
    const anchorDate = toIsoDate(input.anchorDate)
      || (actualSeries.length ? String(actualSeries[actualSeries.length - 1].date).slice(0, 10) : today);
    return {
      birthDate,
      investingStartDate,
      retirementDate,
      targetDate,
      targetAge,
      anchorDate,
      currentAge: Number(ageOnDate(birthDate, today).toFixed(2)),
      ageStartedInvesting: Number(ageOnDate(birthDate, investingStartDate).toFixed(2)),
      retirementAge: Number(ageOnDate(birthDate, retirementDate).toFixed(2)),
    };
  }

  function validateRetirementSimulationInputs(input) {
    const errors = [];
    const dates = resolveDateInputs(input || {});
    const normalized = {
      ...dates,
      currentPortfolioValue: Math.max(0, toNumber(input.currentPortfolioValue, 0)),
      monthlyInvestment: Math.max(0, toNumber(input.monthlyInvestment, 0)),
      yearlyReturnBeforeRetirement: toNumber(input.yearlyReturnBeforeRetirement, 0),
      yearlyReturnAfterRetirement: toNumber(input.yearlyReturnAfterRetirement, 0),
      monthlyRetirementWithdrawals: Math.max(0, toNumber(input.monthlyRetirementWithdrawals, 0)),
      monthlyWithdrawalGrowthRate: toNumber(input.monthlyWithdrawalGrowthRate, 0),
      annualFeeRate: Math.max(0, toNumber(input.annualFeeRate, 0)),
      initialInvestmentAmount: Math.max(0, toNumber(input.initialInvestmentAmount, input.monthlyInvestment)),
      simulationYears: Math.min(70, Math.max(1, Math.round(toNumber(input.simulationYears, 40)))),
      actualSeries: Array.isArray(input.actualSeries) ? input.actualSeries : [],
    };

    if (!parseDate(normalized.birthDate)) errors.push('Provide a valid date of birth.');
    if (!parseDate(normalized.investingStartDate)) errors.push('Provide a valid investing start date.');
    if (!parseDate(normalized.retirementDate)) errors.push('Provide a valid retirement date.');
    if (!parseDate(normalized.targetDate)) errors.push('Provide a valid target age date.');
    if (normalized.investingStartDate < normalized.birthDate) errors.push('Investing start date cannot be before date of birth.');
    if (normalized.retirementDate <= normalized.investingStartDate) errors.push('Retirement date must be after investing start date.');
    if (normalized.targetDate <= normalized.retirementDate) errors.push('Target age date must be after retirement date.');
    if (normalized.anchorDate < normalized.investingStartDate) errors.push('Current anchor date must be after investing start date.');
    if (normalized.monthlyInvestment < 0) errors.push('Monthly investment cannot be negative.');
    if (normalized.monthlyRetirementWithdrawals < 0) errors.push('Monthly retirement withdrawals cannot be negative.');

    normalized.monthsUntilRetirement = monthsBetween(normalized.anchorDate, normalized.retirementDate);
    return { isValid: errors.length === 0, errors, normalized };
  }

  function simulateSeries(cfg, startDate, startingValue, endDate) {
    const totalMonths = monthsBetween(startDate, endDate);
    const workingRate = annualToMonthlyRate(cfg.yearlyReturnBeforeRetirement);
    const retirementRate = annualToMonthlyRate(cfg.yearlyReturnAfterRetirement);
    const withdrawalGrowth = annualToMonthlyRate(cfg.monthlyWithdrawalGrowthRate);
    const monthlyFeeRate = annualFeeToMonthlyRate(cfg.annualFeeRate);
    const series = new Array(totalMonths + 1);

    let balance = Math.max(0, startingValue);
    let requestedWithdrawal = cfg.monthlyRetirementWithdrawals;
    let depletionDate = null;

    series[0] = {
      date: startDate,
      monthIndex: 0,
      phase: startDate >= cfg.retirementDate ? 'retirement' : 'accumulation',
      age: Number(ageOnDate(cfg.birthDate, startDate).toFixed(2)),
      contribution: 0,
      requestedWithdrawal: 0,
      actualWithdrawal: 0,
      shortfall: 0,
      portfolioValue: Number(balance.toFixed(2)),
    };

    for (let monthIndex = 1; monthIndex <= totalMonths; monthIndex += 1) {
      const date = addMonths(startDate, monthIndex);
      const inRetirement = date >= cfg.retirementDate;
      const monthlyRate = inRetirement ? retirementRate : workingRate;
      const contribution = inRetirement ? 0 : cfg.monthlyInvestment;
      // Add contribution before applying growth and fee
      const balanceWithContribution = balance + contribution;
      const grossBalance = balanceWithContribution * (1 + monthlyRate);
      const balanceAfterGrowth = Math.max(0, grossBalance * (1 - monthlyFeeRate));
      const requested = inRetirement ? requestedWithdrawal : 0;
      const availableBeforeWithdrawal = balanceAfterGrowth;
      const actualWithdrawal = Math.min(Math.max(0, requested), Math.max(0, availableBeforeWithdrawal));
      const shortfall = Math.max(0, requested - actualWithdrawal);
      balance = Math.max(0, availableBeforeWithdrawal - actualWithdrawal);
      series[monthIndex] = {
        date,
        monthIndex,
        phase: inRetirement ? 'retirement' : 'accumulation',
        age: Number(ageOnDate(cfg.birthDate, date).toFixed(2)),
        contribution: Number(contribution.toFixed(2)),
        requestedWithdrawal: Number(requested.toFixed(2)),
        actualWithdrawal: Number(actualWithdrawal.toFixed(2)),
        shortfall: Number(shortfall.toFixed(2)),
        portfolioValue: Number(balance.toFixed(2)),
      };
      if (inRetirement && !depletionDate && balance <= 0) {
        depletionDate = date;
      }
      if (inRetirement) {
        requestedWithdrawal = Math.max(0, requestedWithdrawal * (1 + withdrawalGrowth));
      }
    }

    return {
      series,
      depletionDate,
      retirementValue: (() => {
        const found = series.find((point) => point.date >= cfg.retirementDate);
        return found ? found.portfolioValue : Number(balance.toFixed(2));
      })(),
    };
  }

  function estimateCurrentPortfolioValue(input) {
    const validation = validateRetirementSimulationInputs(input);
    if (!validation.isValid) {
      return Math.max(0, toNumber(input.currentPortfolioValue, 0));
    }
    const cfg = validation.normalized;
    const historical = simulateSeries(cfg, cfg.investingStartDate, cfg.initialInvestmentAmount, cfg.anchorDate);
    return historical.series[historical.series.length - 1].portfolioValue;
  }

  function simulateRetirementProjection(input) {
    const validation = validateRetirementSimulationInputs(input);
    if (!validation.isValid) {
      throw new Error(validation.errors.join(' '));
    }

    const cfg = validation.normalized;
    const actualSeries = cfg.actualSeries
      .filter((point) => point && point.date)
      .map((point) => ({
        date: String(point.date).slice(0, 10),
        value: Number(toNumber(point.value, 0).toFixed(2)),
        phase: point.phase || 'actual',
      }))
      .sort((a, b) => a.date.localeCompare(b.date));

    const projectedPast = simulateSeries(cfg, cfg.investingStartDate, cfg.initialInvestmentAmount, cfg.anchorDate);
    const projectedCurrentValue = projectedPast.series[projectedPast.series.length - 1].portfolioValue;
    const actualCurrentValue = actualSeries.length
      ? actualSeries[actualSeries.length - 1].value
      : Math.max(0, toNumber(input.currentPortfolioValue, projectedCurrentValue));
    
    // Always use today as the starting point for future simulations
    const today = isoToday();
    const futureFromActual = simulateSeries(cfg, today, actualCurrentValue, cfg.targetDate);
    const futureFromProjected = simulateSeries(cfg, today, projectedCurrentValue, cfg.targetDate);
    const actualRetirementPoint = futureFromActual.series.find((point) => point.date >= cfg.retirementDate) || futureFromActual.series[futureFromActual.series.length - 1];
    const projectedRetirementPoint = futureFromProjected.series.find((point) => point.date >= cfg.retirementDate) || futureFromProjected.series[futureFromProjected.series.length - 1];

    return {
      input: cfg,
      summary: {
        actualStartDate: actualSeries.length ? actualSeries[0].date : null,
        actualEndDate: actualSeries.length ? actualSeries[actualSeries.length - 1].date : cfg.anchorDate,
        historicalProjectedStartDate: projectedPast.series.length ? projectedPast.series[0].date : cfg.investingStartDate,
        forecastEndDate: futureFromActual.series.length ? futureFromActual.series[futureFromActual.series.length - 1].date : cfg.targetDate,
        currentPortfolioValue: actualCurrentValue,
        projectedCurrentPortfolioValue: projectedCurrentValue,
        retirementPortfolioValue: actualRetirementPoint.portfolioValue,
        projectedRetirementPortfolioValue: projectedRetirementPoint.portfolioValue,
        finalPortfolioValue: futureFromActual.series[futureFromActual.series.length - 1].portfolioValue,
        projectedFinalPortfolioValue: futureFromProjected.series[futureFromProjected.series.length - 1].portfolioValue,
        transitionDate: cfg.retirementDate,
        depletionDate: futureFromActual.depletionDate,
        projectedDepletionDate: futureFromProjected.depletionDate,
        monthsAfterRetirement: futureFromActual.depletionDate
          ? Math.max(0, monthsBetween(cfg.retirementDate, futureFromActual.depletionDate))
          : Math.max(0, monthsBetween(cfg.retirementDate, cfg.targetDate)),
        targetAge: cfg.targetAge,
        targetDate: cfg.targetDate,
        portfolioLasts: !futureFromActual.depletionDate,
        lastsToTargetAge: !futureFromActual.depletionDate,
        monteCarloSuccessProbability: null,
        historicalMonths: actualSeries.length,
        projectedHistoricalMonths: projectedPast.series.length,
        forecastMonths: futureFromActual.series.length,
      },
      series: {
        actual: actualSeries,
        projectedPast: projectedPast.series.map((point) => ({ date: point.date, value: point.portfolioValue, phase: point.phase })),
        futureFromActual: futureFromActual.series.map((point) => ({ date: point.date, value: point.portfolioValue, phase: point.phase })),
        futureFromProjected: futureFromProjected.series.map((point) => ({ date: point.date, value: point.portfolioValue, phase: point.phase })),
        transitionMarker: [{ date: cfg.retirementDate, value: actualRetirementPoint.portfolioValue, label: 'Retirement' }],
        todayMarker: [{ date: cfg.anchorDate, value: actualCurrentValue, label: 'Today' }],
      },
      chart: buildChartReadyOutput(futureFromActual.series),
    };
  }

  const RetirementSimulation = {
    annualToMonthlyRate,
    validateRetirementSimulationInputs,
    simulateRetirementProjection,
    buildChartReadyOutput,
    estimateCurrentPortfolioValue,
    addMonths,
    addYears,
    monthsBetween,
    ageOnDate,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = RetirementSimulation;
  }
  if (typeof window !== 'undefined') {
    window.RetirementSimulation = RetirementSimulation;
  }
})();
