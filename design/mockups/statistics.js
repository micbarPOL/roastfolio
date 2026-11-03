(() => {
  'use strict';
  const DAY = 86400000;
  const END = '2026-10-30';
  const START = '2022-01-01';
  const benchmarks = ['WIG', 'WIG20', 'mWIG40', 'sWIG80', 'S&P 500', 'NASDAQ', 'DAX', 'MSCI World'];
  const wallets = [{id: 'summary', name: 'All wallets'}, {id: 'ike', name: 'Retirement · IKE'}, {id: 'growth', name: 'Global growth'}];
  const state = {underwater: 'summary', heatmap: 'summary', snapshots: 'summary', range: 'ALL', unit: 'pct', frequency: 'monthly', lake: null, benchmarkPage: 0, snapshotPage: 0};
  const byId = id => document.getElementById(id);
  const stamp = date => Date.parse(`${date}T00:00:00Z`);
  const iso = time => new Date(time).toISOString().slice(0, 10);
  const dateLabel = date => new Date(stamp(date)).toLocaleDateString('en-GB', {day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC'});
  const monthLabel = month => new Date(stamp(`${month}-01`)).toLocaleDateString('en-GB', {month: 'short', year: 'numeric', timeZone: 'UTC'});
  const number = value => value.toLocaleString('en-GB', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const money = value => `${number(value)} PLN`;
  const percent = value => value == null ? 'N/A' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
  const direction = value => value > 0 ? 's-positive' : value < 0 ? 's-negative' : '';
  const walletName = id => wallets.find(wallet => wallet.id === id).name;
  const icons = () => window.lucide?.createIcons();
  const query = new URLSearchParams(location.search);

  function annualReturn(flows, terminal, endDate) {
    const first = stamp(flows[0].date);
    const years = (stamp(endDate) - first) / DAY / 365;
    if (years < 30 / 365) return null;
    const npv = rate => flows.filter(flow => flow.date <= endDate).reduce((sum, flow) => sum - flow.amount / (1 + rate) ** ((stamp(flow.date) - first) / DAY / 365), 0) + terminal / (1 + rate) ** years;
    let lower = -0.999, upper = 8;
    if (npv(lower) * npv(upper) > 0) return null;
    for (let iteration = 0; iteration < 72; iteration++) {
      const middle = (lower + upper) / 2;
      if (npv(middle) > 0) lower = middle;
      else upper = middle;
    }
    return (lower + upper) / 2 * 100;
  }

  function buildWallet(kind) {
    const flows = [{date: START, amount: kind === 0 ? 80000 : 50000}];
    const transactions = [];
    const rows = [];
    let value = flows[0].amount, invested = value, unit = 100, hwm = 100;
    for (let time = stamp(START), index = 0; time <= stamp(END); time += DAY, index++) {
      const date = iso(time), month = Number(date.slice(5, 7)), day = Number(date.slice(8, 10));
      let flow = 0;
      if (day === 15) {
        flow = kind === 0 ? 1200 + (month % 3) * 100 : 700 + (month % 4) * 150;
        invested += flow;
        flows.push({date, amount: flow});
      }
      const weekend = [0, 6].includes(new Date(time).getUTCDay());
      const dailyRate = index === 0 || weekend ? 0 : 0.00036 + 0.0027 * Math.sin(index / (19 + kind * 7) + kind) + 0.0018 * Math.cos(index / 5 + kind) - (index > 260 && index < 345 ? 0.003 : 0) - (index > 1160 && index < 1280 ? 0.0015 : 0);
      unit *= 1 + dailyRate;
      value = value * (1 + dailyRate) + flow;
      hwm = Math.max(hwm, unit);
      if (day === 15 || (day % (kind === 0 ? 11 : 8) === 0 && !weekend)) {
        const count = 1 + (index % 3);
        for (let trade = 0; trade < count; trade++) transactions.push({date, turnover: (flow + 600 + (index % 9) * 180) / count, count: 1});
      }
      rows.push({date, value, invested, unit, hwm, drawdown: (unit / hwm - 1) * 100, xirr: null});
    }
    return {rows, flows, transactions};
  }

  const ike = buildWallet(0), growth = buildWallet(1);
  const combinedFlows = [...ike.flows, ...growth.flows].sort((first, second) => first.date.localeCompare(second.date));
  let summaryUnit = 100, summaryHwm = 100;
  const summaryRows = ike.rows.map((row, index) => {
    const other = growth.rows[index];
    const value = row.value + other.value, invested = row.invested + other.invested;
    if (index) {
      const previous = ike.rows[index - 1], otherPrevious = growth.rows[index - 1];
      const flow = invested - previous.invested - otherPrevious.invested;
      summaryUnit *= 1 + (value - previous.value - otherPrevious.value - flow) / (previous.value + otherPrevious.value);
    }
    summaryHwm = Math.max(summaryHwm, summaryUnit);
    return {date: row.date, value, invested, unit: summaryUnit, hwm: summaryHwm, drawdown: (summaryUnit / summaryHwm - 1) * 100, xirr: null};
  });
  const data = {ike, growth, summary: {rows: summaryRows, flows: combinedFlows, transactions: [...ike.transactions, ...growth.transactions]}};
  function xirrAt(wallet, row) {
    if (row.xirr === null) row.xirr = annualReturn(wallet.flows, row.value, row.date);
    return row.xirr;
  }
  function period(start, end) {
    const flow = end.invested - start.invested;
    const gain = end.value - start.value - flow;
    const denominator = start.value + flow * 0.5;
    return {date: end.date, value: end.value, invested: end.invested, gain, pct: denominator > 0 ? gain / denominator * 100 : null, end};
  }
  function monthly(rows) {
    const groups = new Map();
    rows.forEach((row, index) => {
      const month = row.date.slice(0, 7);
      if (!groups.has(month)) groups.set(month, {start: rows[Math.max(0, index - 1)], end: row});
      groups.get(month).end = row;
    });
    return [...groups].filter(([, group]) => group.start.date !== group.end.date).map(([month, group]) => ({...period(group.start, group.end), month}));
  }
  const daily = rows => rows.slice(1).map((row, index) => period(rows[index], row));
  const extreme = (rows, key, maximum = true) => rows.reduce((best, row) => (maximum ? row[key] > best[key] : row[key] < best[key]) ? row : best, rows[0]);
  function record(field, label, value, meta, sign = 0) {
    return `<div data-field="${field}"><dt>${label}</dt><dd><span class="s-record-value num ${direction(sign)}">${value}</span><span class="s-record-meta num">${meta}</span></dd></div>`;
  }
  function turnover(transactions, monthlyMode) {
    const grouped = new Map();
    transactions.forEach(transaction => {
      const key = monthlyMode ? transaction.date.slice(0, 7) : transaction.date;
      grouped.set(key, (grouped.get(key) || 0) + transaction.turnover);
    });
    return [...grouped].reduce((best, item) => item[1] > best[1] ? item : best);
  }
  function renderRecords() {
    const wallet = data.summary, rows = wallet.rows, last = rows.at(-1);
    const ath = extreme(rows, 'value'), profit = extreme(rows.map(row => ({...row, profit: row.value - row.invested})), 'profit');
    const drawdown = (last.value / ath.value - 1) * 100;
    const recentStart = '2026-05-01', priorStart = '2025-11-01';
    const activity = (start, end) => wallet.transactions.filter(transaction => transaction.date >= start && transaction.date < end).reduce((sum, transaction) => sum + transaction.count, 0) / 6;
    const average = activity(recentStart, '2026-11-01'), previous = activity(priorStart, recentStart);
    byId('alltime-records').innerHTML = record('record-ath', 'All-time high', money(ath.value), `${dateLabel(ath.date)} · Nightly snapshot`) + record('record-ath-age', 'Days since ATH', `${(stamp(END) - stamp(ath.date)) / DAY} days`, dateLabel(ath.date)) + record('record-ath-drawdown', 'Drawdown from ATH', percent(drawdown), money(last.value - ath.value), drawdown) + record('record-profit', 'Highest profit', money(profit.profit), `${dateLabel(profit.date)} · Value − invested`, profit.profit) + record('record-transactions', 'Transactions / month · 6mo MA', average.toFixed(1), `${average >= previous ? '+' : ''}${(average - previous).toFixed(1)} vs prior 6 months · avg ${previous.toFixed(1)}/mo`);
    const months = monthly(rows), days = daily(rows).map((row, index) => ({...row, pct: row.gain / rows[index].value * 100}));
    const bestMonth = extreme(months, 'gain'), worstMonth = extreme(months, 'gain', false), monthTurnover = turnover(wallet.transactions, true);
    byId('monthly-records').innerHTML = record('record-best-month', 'Best month · net gain', money(bestMonth.gain), monthLabel(bestMonth.month), bestMonth.gain) + record('record-worst-month', 'Worst month · net gain', money(worstMonth.gain), monthLabel(worstMonth.month), worstMonth.gain) + record('record-month-turnover', 'Highest monthly turnover', money(monthTurnover[1]), monthLabel(monthTurnover[0]));
    const bestPct = extreme(days, 'pct'), worstPct = extreme(days, 'pct', false), bestGain = extreme(days, 'gain'), worstGain = extreme(days, 'gain', false), dayTurnover = turnover(wallet.transactions, false);
    byId('daily-records').innerHTML = record('record-best-day-pct', 'Best day · return', percent(bestPct.pct), dateLabel(bestPct.date), bestPct.pct) + record('record-worst-day-pct', 'Worst day · return', percent(worstPct.pct), dateLabel(worstPct.date), worstPct.pct) + record('record-best-day-pln', 'Best day · net gain', money(bestGain.gain), dateLabel(bestGain.date), bestGain.gain) + record('record-worst-day-pln', 'Worst day · net gain', money(worstGain.gain), dateLabel(worstGain.date), worstGain.gain) + record('record-day-turnover', 'Highest daily turnover', money(dayTurnover[1]), dateLabel(dayTurnover[0]));
    renderBenchmarks();
  }
  function benchmarkReturn(month, benchmarkIndex) {
    const offset = (Number(month.slice(0, 4)) - 2022) * 12 + Number(month.slice(5, 7));
    if ((offset + benchmarkIndex * 3) % 17 === 0 || (benchmarkIndex === 7 && offset < 4)) return null;
    return 1.1 + 3.2 * Math.sin(offset * 1.1 + benchmarkIndex * 0.42) + 1.8 * Math.cos(offset * 0.7 + benchmarkIndex);
  }
  function comparison(row, benchmarkIndex) {
    const value = benchmarkReturn(row.month, benchmarkIndex), delta = value == null || row.pct == null ? null : row.pct - value;
    return value == null ? '<td class="num" title="Benchmark observation unavailable">N/A<span class="s-delta">Unavailable</span></td>' : `<td class="num ${direction(delta)}">${percent(value)}<span class="s-delta">${delta == null ? 'N/A' : `${delta > 0 ? '+' : ''}${delta.toFixed(2)} pp`}</span></td>`;
  }
  function pagination(id, page, total, onChange, size) {
    const pages = Math.ceil(total / size);
    byId(id).innerHTML = `<span class="num">${page * size + 1}–${Math.min(total, (page + 1) * size)} of ${total}</span><button class="s-page-btn" type="button" aria-label="Previous ${id.startsWith('benchmark') ? 'benchmark' : 'snapshot'} page" ${page === 0 ? 'disabled' : ''}><i data-lucide="chevron-left" aria-hidden="true"></i></button><button class="s-page-btn" type="button" aria-label="Next ${id.startsWith('benchmark') ? 'benchmark' : 'snapshot'} page" ${page >= pages - 1 ? 'disabled' : ''}><i data-lucide="chevron-right" aria-hidden="true"></i></button>`;
    const buttons = byId(id).querySelectorAll('button');
    buttons.forEach((button, index) => button.addEventListener('click', () => {
      onChange(page + (index ? 1 : -1));
      byId(id).querySelectorAll('button')[index].focus({preventScroll: true});
    }));
    icons();
  }
  function renderBenchmarks() {
    const months = monthly(data.summary.rows).reverse();
    const visible = months.slice(state.benchmarkPage * 6, state.benchmarkPage * 6 + 6);
    byId('benchmark-period').textContent = `${walletName('summary')} · ${months.length} months · Jan 2022–Oct 2026`;
    byId('benchmark-wins').innerHTML = benchmarks.map((name, index) => {
      const comparable = months.filter(row => benchmarkReturn(row.month, index) != null && row.pct != null);
      const wins = comparable.filter(row => row.pct > benchmarkReturn(row.month, index)).length;
      return `<div class="s-win"><span>${name}</span><strong class="num">${wins} / ${comparable.length}</strong><span>months won</span></div>`;
    }).join('');
    byId('benchmark-table').innerHTML = `<caption>Monthly returns · portfolio minus benchmark in pp</caption><thead><tr><th scope="col">Month</th><th scope="col">Portfolio</th>${benchmarks.map(name => `<th scope="col">${name}</th>`).join('')}</tr></thead><tbody>${visible.map(row => `<tr><th scope="row">${monthLabel(row.month)}</th><td class="num">${percent(row.pct)}</td>${benchmarks.map((name, index) => comparison(row, index)).join('')}</tr>`).join('')}</tbody>`;
    byId('benchmark-mobile').innerHTML = visible.map(row => `<details class="s-month-row"><summary><span>${monthLabel(row.month)}</span><strong class="num">${percent(row.pct)}</strong><i data-lucide="chevron-down" aria-hidden="true"></i></summary><table><caption>${monthLabel(row.month)} · ${walletName('summary')}</caption><thead><tr><th scope="col">Benchmark</th><th scope="col">Return / difference</th></tr></thead><tbody>${benchmarks.map((name, index) => `<tr><th scope="row">${name}</th>${comparison(row, index)}</tr>`).join('')}</tbody></table></details>`).join('');
    pagination('benchmark-pagination', state.benchmarkPage, months.length, page => {state.benchmarkPage = page; renderBenchmarks();}, 6);
  }
  function lakeCatalog(rows) {
    const lakes = [];
    let current = null;
    rows.forEach((row, index) => {
      if (row.drawdown < -0.000001) {
        if (!current) current = {id: `lake-${lakes.length}`, peak: rows[Math.max(0, index - 1)], start: row, trough: row, end: row, recovered: false};
        if (row.drawdown < current.trough.drawdown) current.trough = row;
        current.end = row;
      } else if (current) {
        current.end = row;
        current.recovered = true;
        lakes.push(current);
        current = null;
      }
    });
    if (current) lakes.push(current);
    return lakes.map(lake => ({...lake, duration: (stamp(lake.end.date) - stamp(lake.start.date)) / DAY + 1}));
  }
  function lakeDates(lake) {
    return `Peak ${dateLabel(lake.peak.date)} · Trough ${dateLabel(lake.trough.date)} · ${lake.recovered ? 'Recovered' : 'Ongoing through'} ${dateLabel(lake.end.date)}`;
  }
  function rangeRows(rows) {
    if (state.range === 'ALL') return rows;
    const date = new Date(stamp(END));
    if (state.range === 'YTD') date.setUTCMonth(0, 1);
    else date.setUTCFullYear(date.getUTCFullYear() - (state.range === '3Y' ? 3 : 1));
    return rows.filter(row => stamp(row.date) >= date.getTime());
  }
  function drawChart(container, rows, lake, drawdownMode) {
    const width = Math.max(300, byId(container).clientWidth), height = byId(container).clientHeight;
    const left = 54, right = width - 10, top = 12, bottom = height - 30;
    const minimum = drawdownMode ? Math.min(-5, Math.floor(Math.min(...rows.map(row => row.drawdown)) / 5) * 5) : Math.floor(Math.min(...rows.map(row => row.unit)) / 10) * 10;
    const maximum = drawdownMode ? 0 : Math.ceil(Math.max(...rows.map(row => row.hwm)) / 10) * 10;
    const x = row => left + (stamp(row.date) - stamp(rows[0].date)) / (stamp(rows.at(-1).date) - stamp(rows[0].date)) * (right - left);
    const y = value => bottom - (value - minimum) / (maximum - minimum || 1) * (bottom - top);
    const path = key => rows.map((row, index) => `${index ? 'L' : 'M'}${x(row).toFixed(2)},${y(row[key]).toFixed(2)}`).join(' ');
    const ticks = Array.from({length: 4}, (_, index) => minimum + (maximum - minimum) * index / 3);
    const selectedStart = Math.max(stamp(rows[0].date), stamp(lake.peak.date)), selectedEnd = Math.min(stamp(rows.at(-1).date), stamp(lake.end.date));
    const highlight = selectedEnd >= selectedStart ? `<rect class="s-selected-lake" x="${x({date: iso(selectedStart)})}" y="${top}" width="${Math.max(1, x({date: iso(selectedEnd)}) - x({date: iso(selectedStart)}))}" height="${bottom - top}"/>` : '';
    const lines = drawdownMode ? `<path class="s-area-dd" d="${path('drawdown')} L${right},${y(0)} L${left},${y(0)} Z"/><path class="s-line-dd" d="${path('drawdown')}"/>` : `<path class="s-line-hwm" d="${path('hwm')}"/><path class="s-line-price" d="${path('unit')}"/>`;
    byId(container).innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${drawdownMode ? 'Selected lake drawdown below unit-price HWM' : 'Unit price and high-water mark'} for ${walletName(state.underwater)}, ${dateLabel(rows[0].date)} to ${dateLabel(rows.at(-1).date)}"><title>${drawdownMode ? 'Selected lake drawdown (%)' : 'Unit price / HWM'} · ${drawdownMode ? 'all lake dates' : state.range}</title>${ticks.map(tick => `<line class="s-grid" x1="${left}" x2="${right}" y1="${y(tick)}" y2="${y(tick)}"/><text x="${left - 8}" y="${y(tick) + 4}" text-anchor="end">${tick.toFixed(drawdownMode ? 1 : 0)}${drawdownMode ? '%' : ''}</text>`).join('')}${highlight}${lines}<line class="s-observation" x1="${right}" x2="${right}" y1="${top}" y2="${bottom}"/><text x="${left}" y="${height - 8}">${dateLabel(rows[0].date)}</text><text x="${right}" y="${height - 8}" text-anchor="end">${dateLabel(rows.at(-1).date)}</text></svg>`;
    byId(container).querySelector('svg').addEventListener('pointermove', event => {
      const bounds = event.currentTarget.getBoundingClientRect();
      const fraction = Math.max(0, Math.min(1, (event.clientX - bounds.left - left) / (right - left)));
      byId(drawdownMode ? 'lake-inspect' : 'chart-inspect').value = Math.round(fraction * (rows.length - 1));
      inspectChart(drawdownMode);
    });
    if (!drawdownMode) byId(container).querySelector('svg').addEventListener('click', event => {
      const bounds = event.currentTarget.getBoundingClientRect();
      const fraction = Math.max(0, Math.min(1, (event.clientX - bounds.left - left) / (right - left)));
      const row = rows[Math.round(fraction * (rows.length - 1))];
      const selected = lakeCatalog(data[state.underwater].rows).find(lake => row.date >= lake.start.date && row.date <= lake.end.date);
      if (selected) {state.lake = selected.id; renderUnderwater(); announce(`Lake selected: ${monthLabel(selected.start.date.slice(0, 7))}.`);}
    });
  }
  let chartRows = [], lakeRows = [];
  function inspectChart(drawdownMode = false) {
    const slider = byId(drawdownMode ? 'lake-inspect' : 'chart-inspect');
    const output = byId(drawdownMode ? 'lake-reading' : 'chart-reading');
    const rows = drawdownMode ? lakeRows : chartRows;
    const index = Number(slider.value), row = rows[index];
    if (!row) return;
    output.textContent = `${dateLabel(row.date)} · Unit ${number(row.unit)} · HWM ${number(row.hwm)} · ${percent(row.drawdown)}`;
    slider.setAttribute('aria-valuetext', output.textContent);
    const svg = byId(drawdownMode ? 'drawdown-chart' : 'unit-chart').querySelector('svg'), line = svg.querySelector('.s-observation');
    const width = svg.viewBox.baseVal.width;
    const position = 54 + index / (rows.length - 1) * (width - 64);
    line.setAttribute('x1', position); line.setAttribute('x2', position);
  }
  function renderUnderwater() {
    const rows = data[state.underwater].rows, lakes = lakeCatalog(rows);
    const deepest = lakes.reduce((best, lake) => lake.trough.drawdown < best.trough.drawdown ? lake : best);
    const longest = lakes.reduce((best, lake) => lake.duration > best.duration ? lake : best);
    if (!lakes.some(lake => lake.id === state.lake)) state.lake = deepest.id;
    const selected = lakes.find(lake => lake.id === state.lake);
    byId('deepest-lake').innerHTML = `<h3>Deepest lake · all time</h3><strong class="s-extreme-value num">${percent(deepest.trough.drawdown)}</strong><p class="s-caption num">${deepest.duration} days · ${lakeDates(deepest)}</p>`;
    byId('longest-lake').innerHTML = `<h3>Longest lake · all time</h3><strong class="s-extreme-value num">${longest.duration} days</strong><p class="s-caption num">Depth ${percent(longest.trough.drawdown)} · ${lakeDates(longest)}</p>`;
    byId('lake-select').innerHTML = [...lakes].reverse().map(lake => `<option value="${lake.id}">${monthLabel(lake.start.date.slice(0, 7))} · ${percent(lake.trough.drawdown)} · ${lake.duration} days${lake.recovered ? '' : ' · ongoing'}</option>`).join('');
    byId('lake-select').value = state.lake;
    chartRows = rangeRows(rows);
    const outside = selected.end.date < chartRows[0].date;
    byId('lake-detail').textContent = `${lakeDates(selected)} · ${selected.duration} days · Depth ${percent(selected.trough.drawdown)}${outside ? ' · Outside selected chart range' : ''}`;
    drawChart('unit-chart', chartRows, selected, false);
    lakeRows = rows.filter(row => stamp(row.date) >= stamp(selected.start.date) - 2 * DAY && stamp(row.date) <= stamp(selected.end.date) + 2 * DAY).map(row => row.date < selected.start.date || row.date > selected.end.date ? {...row, drawdown: 0} : row);
    drawChart('drawdown-chart', lakeRows, selected, true);
    byId('chart-inspect').max = chartRows.length - 1;
    byId('chart-inspect').value = chartRows.length - 1;
    inspectChart();
    byId('lake-inspect').max = lakeRows.length - 1;
    byId('lake-inspect').value = lakeRows.findIndex(row => row.date === selected.trough.date);
    inspectChart(true);
  }
  function renderHeatmap() {
    const months = monthly(data[state.heatmap].rows);
    const names = Array.from({length: 12}, (_, index) => new Date(Date.UTC(2026, index, 1)).toLocaleDateString('en-GB', {month: 'short', timeZone: 'UTC'}));
    const metric = row => state.unit === 'pct' ? row.pct : row.gain;
    const cell = (value, label) => value == null ? '<td class="num" title="No snapshot period available">N/A</td>' : `<td class="num ${direction(value)}" title="${label}">${state.unit === 'pct' ? percent(value) : number(value)}</td>`;
    const years = [...new Set(months.map(row => row.month.slice(0, 4)))].reverse();
    const averages = names.map((name, index) => {
      const available = months.filter(row => Number(row.month.slice(5, 7)) === index + 1 && metric(row) != null);
      return available.length ? available.reduce((sum, row) => sum + metric(row), 0) / available.length : null;
    });
    byId('heatmap-table').innerHTML = `<caption>${walletName(state.heatmap)} · Monthly ${state.unit === 'pct' ? 'return (%)' : 'net gain (PLN)'}</caption><thead><tr><th scope="col">Year</th>${names.map(name => `<th scope="col">${name}</th>`).join('')}</tr></thead><tbody>${years.map(year => `<tr><th scope="row" class="num">${year}</th>${names.map((name, index) => {const row = months.find(item => item.month === `${year}-${String(index + 1).padStart(2, '0')}`); return cell(row ? metric(row) : null, `${name} ${year}`);}).join('')}</tr>`).join('')}</tbody><tfoot data-field="statistics-monthly-averages"><tr><th scope="row">Average</th>${averages.map((value, index) => cell(value, `${names[index]} arithmetic average`)).join('')}</tr></tfoot>`;
  }
  function renderSnapshots() {
    const wallet = data[state.snapshots];
    const periods = (state.frequency === 'monthly' ? monthly(wallet.rows) : daily(wallet.rows)).reverse();
    const visible = periods.slice(state.snapshotPage * 12, state.snapshotPage * 12 + 12);
    byId('snapshot-table').innerHTML = `<caption>${walletName(state.snapshots)} · ${state.frequency === 'monthly' ? 'Monthly' : 'Daily'} ending balances and period returns · PLN</caption><thead><tr>${['Period', 'Value', 'Invested', 'Net gain', 'Return', 'XIRR'].map(name => `<th scope="col">${name}</th>`).join('')}</tr></thead><tbody>${visible.map(row => `<tr><th scope="row" class="num">${state.frequency === 'monthly' ? monthLabel(row.month) : dateLabel(row.date)}</th><td class="num">${money(row.value)}</td><td class="num">${money(row.invested)}</td><td class="num ${direction(row.gain)}">${money(row.gain)}</td><td class="num">${percent(row.pct)}</td><td class="num">${percent(xirrAt(wallet, row.end))}</td></tr>`).join('')}</tbody>`;
    pagination('snapshot-pagination', state.snapshotPage, periods.length, page => {state.snapshotPage = page; renderSnapshots();}, 12);
  }
  function announce(message) { byId('filter-status').textContent = message; }
  ['underwater', 'heatmap', 'snapshot'].forEach(section => {
    const select = byId(`${section}-wallet`);
    select.innerHTML = wallets.map(wallet => `<option value="${wallet.id}">${wallet.name}</option>`).join('');
    select.addEventListener('change', () => {
      state[section === 'snapshot' ? 'snapshots' : section] = select.value;
      if (section === 'underwater') {state.lake = null; renderUnderwater();}
      if (section === 'heatmap') renderHeatmap();
      if (section === 'snapshot') {state.snapshotPage = 0; renderSnapshots();}
      announce(`${section === 'snapshot' ? 'Snapshots' : section} updated for ${walletName(select.value)}.`);
    });
  });
  [['range', 'range', renderUnderwater], ['unit', 'unit', renderHeatmap], ['frequency', 'frequency', renderSnapshots]].forEach(([attribute, key, render]) => {
    document.querySelectorAll(`[data-${attribute}]`).forEach(button => button.addEventListener('click', () => {
      state[key] = button.dataset[attribute];
      if (key === 'frequency') state.snapshotPage = 0;
      button.parentElement.querySelectorAll('button').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
      render();
      announce(`${key} changed to ${state[key]}.`);
    }));
  });
  byId('lake-select').addEventListener('change', event => {state.lake = event.target.value; renderUnderwater();});
  byId('chart-inspect').addEventListener('input', () => inspectChart());
  byId('lake-inspect').addEventListener('input', () => inspectChart(true));
  document.querySelectorAll('.s-help').forEach(button => {
    button.addEventListener('click', () => {button.dataset.dismissed = 'false'; button.dataset.open = String(button.dataset.open !== 'true');});
    button.addEventListener('pointerleave', () => {button.dataset.dismissed = 'false';});
    button.addEventListener('focus', () => {button.dataset.dismissed = 'false';});
    button.addEventListener('blur', () => {button.dataset.open = 'false';});
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') document.querySelectorAll('.s-help').forEach(button => {button.dataset.open = 'false'; button.dataset.dismissed = 'true';});
  });
  document.addEventListener('pointerdown', event => {
    document.querySelectorAll('.s-help').forEach(button => {if (!button.contains(event.target)) {button.dataset.open = 'false'; button.dataset.dismissed = 'true';}});
  });
  function theme(value) {
    document.documentElement.dataset.theme = value;
    document.querySelectorAll('[data-theme-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.themeChoice === value)));
  }
  theme(query.get('theme') === 'light' ? 'light' : 'dark');
  document.querySelectorAll('[data-theme-choice]').forEach(button => button.addEventListener('click', () => theme(button.dataset.themeChoice)));
  document.querySelector('.s-mobile-theme').addEventListener('click', () => theme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  document.querySelector('.sidebar-collapse').addEventListener('click', event => {
    const app = document.querySelector('.app'), collapsed = app.dataset.sidebar !== 'collapsed';
    app.dataset.sidebar = collapsed ? 'collapsed' : 'expanded';
    event.currentTarget.setAttribute('aria-pressed', String(collapsed));
    event.currentTarget.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    event.currentTarget.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
  });
  const drawer = byId('statistics-menu'), backdrop = document.querySelector('.drawer-backdrop');
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(link => {
    const clone = link.cloneNode(true);
    clone.removeAttribute('data-field');
    document.querySelector('.s-drawer-links').append(clone);
  });
  function closeDrawer() {
    drawer.hidden = true; backdrop.hidden = true;
    document.querySelector('.app').inert = false;
    document.querySelector('.bottom-tabs').inert = false;
    document.querySelector('.drawer-open').setAttribute('aria-expanded', 'false');
    document.querySelector('.drawer-open').focus();
  }
  document.querySelector('.drawer-open').addEventListener('click', () => {
    drawer.hidden = false; backdrop.hidden = false;
    document.querySelector('.drawer-open').setAttribute('aria-expanded', 'true');
    document.querySelector('.app').inert = true;
    document.querySelector('.bottom-tabs').inert = true;
    document.querySelector('.drawer-close').focus();
  });
  document.querySelector('.drawer-close').addEventListener('click', closeDrawer);
  backdrop.addEventListener('click', closeDrawer);
  drawer.addEventListener('keydown', event => {
    if (event.key === 'Escape') {closeDrawer(); return;}
    if (event.key !== 'Tab') return;
    const targets = [...drawer.querySelectorAll('a,button')], first = targets[0], last = targets.at(-1);
    if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last.focus();}
    else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus();}
  });
  function sampleState(value) {
    document.querySelectorAll('.s-record-section,.s-section').forEach(section => {section.hidden = value !== 'ready';});
    document.querySelector('[data-field="statistics-empty"]').hidden = value !== 'empty';
    document.querySelector('[data-field="statistics-loading"]').hidden = value !== 'loading';
    if (value === 'ready') {renderUnderwater(); announce('Sample history restored.');}
  }
  byId('restore-samples').addEventListener('click', () => {sampleState('ready'); byId('underwater-wallet').focus();});
  let resizeFrame;
  window.addEventListener('resize', () => {cancelAnimationFrame(resizeFrame); resizeFrame = requestAnimationFrame(renderUnderwater);});
  document.querySelector('[data-field="statistics-underwater"]').addEventListener('toggle', event => {if (event.target.open) renderUnderwater();});
  renderRecords(); renderUnderwater(); renderHeatmap(); renderSnapshots(); icons();
  if (['empty', 'loading'].includes(query.get('state'))) sampleState(query.get('state'));
  window.statisticsMockup = {data, state, monthly, daily, benchmarkReturn, annualReturn, lakeCatalog, rangeRows};
})();