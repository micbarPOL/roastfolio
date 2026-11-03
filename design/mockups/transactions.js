(() => {
  const byId = id => document.getElementById(id);
  const icons = () => window.lucide?.createIcons();
  const TODAY = '2026-11-03';
  const operations = ['Buy', 'Sell', 'Dividend', 'Deposit', 'Withdrawal', 'Extra Cost', 'Spin-off'];
  const assets = [['Apple', 'AAPL'], ['Microsoft', 'MSFT'], ['iShares Core MSCI World', 'IWDA'], ['PKO Bank Polski', 'PKO'], ['PZU', 'PZU']];
  const rows = Array.from({length: 80}, (_, index) => {
    const operation = operations[index % operations.length];
    const [name, ticker] = assets[index % assets.length];
    const date = new Date(Date.UTC(2026, 10, 3 - index * 5)).toISOString().slice(0, 10);
    const cash = ['Deposit', 'Withdrawal', 'Extra Cost'].includes(operation);
    const quantity = cash ? 0 : 5 + index % 19;
    const price = cash ? 0 : 110 + index * 7.25;
    const commission = ['Buy', 'Sell'].includes(operation) ? 9 + index % 8 : 0;
    const base = cash ? 500 + index * 47 : operation === 'Dividend' ? 20 + index * 3 : quantity * price;
    const value = ['Buy', 'Withdrawal', 'Extra Cost'].includes(operation) ? -base : base;
    return {id: `sample-${index}`, date, operation, asset: cash ? 'Cash' : name, ticker: cash ? 'PLN' : ticker, wallet: index % 2 ? 'Brokerage' : 'Retirement', quantity, price, commission, value, automatic: index > 0 && operation === 'Deposit' && index % 2 === 0};
  });
  const state = {page: 0, year: 2026, operations: new Set(), editing: null, day: null};
  const money = value => `${Number(value).toLocaleString('en-GB', {minimumFractionDigits: 2, maximumFractionDigits: 2})} PLN`;
  const number = value => Number(value).toLocaleString('en-GB', {maximumFractionDigits: 6});
  const escape = value => String(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const turnover = data => data.filter(row => ['Buy', 'Sell'].includes(row.operation)).reduce((total, row) => total + Math.abs(row.value), 0);
  function filters() {
    const from = byId('t-from').value, to = byId('t-to').value;
    const min = byId('t-min').value === '' ? null : Number(byId('t-min').value);
    const max = byId('t-max').value === '' ? null : Number(byId('t-max').value);
    const invalid = (from && to && from > to) || (min !== null && max !== null && min > max);
    byId('t-filter-error').hidden = !invalid;
    byId('t-filter-error').textContent = invalid ? 'The beginning of a range must not exceed its end.' : '';
    if (invalid) return [];
    const asset = byId('t-asset').value.trim().toLowerCase(), wallet = byId('t-wallet').value;
    return rows.filter(row => (!from || row.date >= from) && (!to || row.date <= to) && (!asset || `${row.asset} ${row.ticker}`.toLowerCase().includes(asset)) && (!wallet || row.wallet === wallet) && (!state.operations.size || state.operations.has(row.operation)) && (min === null || row.value >= min) && (max === null || row.value <= max)).sort((left, right) => right.date.localeCompare(left.date));
  }
  function renderLedger() {
    const result = filters(), pages = Math.max(1, Math.ceil(result.length / 12));
    state.page = Math.min(state.page, pages - 1);
    byId('t-result-count').textContent = `${result.length} transactions · ${money(result.reduce((total, row) => total + row.value, 0))} net value`;
    byId('t-rows').innerHTML = result.slice(state.page * 12, state.page * 12 + 12).map(row => `<tr><td>${row.date}</td><td><span class="t-operation t-operation-${row.operation.toLowerCase().replaceAll(' ', '-')}">${row.operation}</span></td><td><span class="t-asset-name">${escape(row.asset)}</span><span class="t-asset-ticker">${escape(row.ticker)} · ${row.date} · ${escape(row.wallet)}</span></td><td>${escape(row.wallet)}</td><td>${row.quantity ? number(row.quantity) : '—'}</td><td>${row.price ? number(row.price) : '—'}</td><td>${number(row.commission)}</td><td class="t-value">${number(row.value)}</td><td>${row.automatic ? '<span class="t-auto" title="Automatic cash entry follows its source transaction">Auto</span>' : `<button type="button" class="t-icon" data-edit="${row.id}" aria-label="Edit ${escape(row.asset)} transaction from ${row.date}" title="Edit transaction"><i data-lucide="pencil" aria-hidden="true"></i></button>`}</td></tr>`).join('');
    byId('t-page').textContent = `${state.page + 1} / ${pages}`;
    byId('t-prev').disabled = state.page === 0;
    byId('t-next').disabled = state.page >= pages - 1;
    document.querySelector('.t-empty').hidden = result.length !== 0;
    document.querySelector('.t-table-scroll').hidden = result.length === 0;
    document.querySelector('.t-pagination').hidden = result.length === 0;
    icons();
  }
  function renderSummary() {
    for (const [scope, data] of [['month', rows.filter(row => row.date.startsWith(TODAY.slice(0, 7)))], ['ytd', rows.filter(row => row.date.startsWith(TODAY.slice(0, 4)))], ['total', rows]]) {
      byId(`t-${scope}-value`).textContent = money(turnover(data));
      byId(`t-${scope}-count`).textContent = `${data.length} transactions`;
    }
  }
  function renderCalendar() {
    const years = [...new Set(rows.map(row => Number(row.date.slice(0, 4))))].sort((left, right) => right - left);
    byId('t-years').innerHTML = years.map(year => `<button type="button" data-year="${year}" aria-pressed="${year === state.year}">${year}</button>`).join('');
    const allTurnovers = rows.map(row => Math.abs(row.value));
    const maximum = Math.max(1, ...allTurnovers);
    byId('t-calendar').innerHTML = Array.from({length: 12}, (_, month) => {
      const count = new Date(Date.UTC(state.year, month + 1, 0)).getUTCDate();
      const offset = (new Date(Date.UTC(state.year, month, 1)).getUTCDay() + 6) % 7;
      const monthName = new Date(Date.UTC(state.year, month, 1)).toLocaleString('en-GB', {month:'short', timeZone:'UTC'});
      return `<div><div class="t-month-name">${monthName}</div><div class="t-month-days">${'<span></span>'.repeat(offset)}${Array.from({length:count}, (_, day) => {
        const date = `${state.year}-${String(month+1).padStart(2,'0')}-${String(day+1).padStart(2,'0')}`;
        const items = rows.filter(row => row.date === date);
        const value = turnover(items), level = value ? Math.max(1, Math.min(4, Math.ceil(value / maximum * 4))) : 0;
        return `<button type="button" class="t-level-${level}${items.some(row => row.operation === 'Deposit') ? ' t-deposit' : ''}${items.some(row => row.operation === 'Withdrawal') ? ' t-withdrawal' : ''}" data-day="${date}" data-count="${items.length}" aria-label="${date}: ${items.length} transactions, ${money(value)} turnover" title="${date} · ${items.length} transactions · ${money(value)}" ${items.length ? '' : 'disabled'}></button>`;
      }).join('')}</div></div>`;
    }).join('');
  }
  function renderChart() {
    const months = [...new Set(rows.map(row => row.date.slice(0, 7)))].sort().slice(-12);
    const values = months.map(month => turnover(rows.filter(row => row.date.startsWith(month))));
    const max = Math.max(1, ...values), width = Math.max(320, byId('t-chart').clientWidth), height = 220, left = 64, right = width - 12, top = 16, bottom = 180;
    const track = (right-left)/months.length;
    const labelStep = Math.max(1, Math.ceil(48 / track));
    byId('t-chart').innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Monthly turnover for the last twelve sample months"><title>Monthly Buy and Sell turnover in PLN</title>${[0,.5,1].map(ratio => `<line class="t-grid" x1="${left}" x2="${right}" y1="${bottom-ratio*(bottom-top)}" y2="${bottom-ratio*(bottom-top)}"/><text x="${left-8}" y="${bottom-ratio*(bottom-top)+4}" text-anchor="end">${number(max*ratio/1000)}k</text>`).join('')}${months.map((month,index) => `<rect class="t-bar" x="${left+index*track+track*.22}" y="${bottom-values[index]/max*(bottom-top)}" width="${track*.55}" height="${values[index]/max*(bottom-top)}"><title>${month}: ${money(values[index])}</title></rect>${index % labelStep === 0 ? `<text x="${left+index*track+track*.5}" y="208" text-anchor="middle">${month.slice(5)}/${month.slice(2,4)}</text>` : ''}`).join('')}</svg>`;
  }
  function openEdit(id) {
    const row = rows.find(item => item.id === id);
    if (!row || row.automatic) return;
    state.editing = id;
    const form = byId('t-edit-form');
    const cash = ['Deposit','Withdrawal','Extra Cost'].includes(row.operation);
    for (const field of ['date','asset','quantity','price','commission','value']) {
      form.elements[field].value = row[field];
      form.elements[field].disabled = cash && ['asset','quantity','price','commission'].includes(field);
    }
    byId('t-edit-meta').textContent = `${row.operation} · ${row.wallet}`;
    byId('t-edit-error').hidden = true;
    byId('t-edit').showModal();
  }
  function openDay(date) {
    state.day = date;
    const data = rows.filter(row => row.date === date);
    byId('t-day-title').textContent = date;
    byId('t-day-summary').textContent = `${data.length} transactions · ${money(turnover(data))} turnover`;
    byId('t-day-rows').innerHTML = data.map(row => `<div class="t-day-row"><div><span>${row.operation} · ${escape(row.asset)}</span><span class="t-caption">${escape(row.wallet)} · ${number(row.quantity)} units · ${number(row.price)} PLN · ${number(row.commission)} commission</span></div><strong class="num">${money(row.value)}</strong></div>`).join('');
    byId('t-day').showModal();
  }
  function clearFilters() {
    byId('t-filters').reset(); state.operations.clear(); state.page=0;
    document.querySelectorAll('#t-operations input').forEach(input => {input.checked=false;});
    byId('t-operation-label').textContent='All operations';
    renderLedger();
  }
  byId('t-wallet').replaceChildren(new Option('All wallets',''), ...[...new Set(rows.map(row=>row.wallet))].map(wallet=>new Option(wallet,wallet)));
  byId('t-operations').innerHTML=operations.map(operation=>`<label><input type="checkbox" value="${operation}">${operation}</label>`).join('');
  byId('t-filters').addEventListener('submit', event=>event.preventDefault());
  byId('t-filters').addEventListener('input', event=>{
    if(event.target.type==='checkbox') {if(event.target.checked)state.operations.add(event.target.value);else state.operations.delete(event.target.value);}
    byId('t-operation-label').textContent=state.operations.size ? `${state.operations.size} operations` : 'All operations';
    state.page=0; renderLedger();
  });
  byId('t-clear').addEventListener('click',clearFilters);
  byId('t-empty-clear').addEventListener('click',clearFilters);
  byId('t-prev').addEventListener('click',()=>{state.page--;renderLedger();});
  byId('t-next').addEventListener('click',()=>{state.page++;renderLedger();});
  byId('t-rows').addEventListener('click',event=>{const button=event.target.closest('[data-edit]');if(button)openEdit(button.dataset.edit);});
  byId('t-calendar').addEventListener('click',event=>{const button=event.target.closest('[data-day]');if(button&&!button.disabled)openDay(button.dataset.day);});
  byId('t-years').addEventListener('click',event=>{const button=event.target.closest('[data-year]');if(button){state.year=Number(button.dataset.year);renderCalendar();}});
  document.querySelectorAll('[data-preset]').forEach(button=>button.addEventListener('click',()=>{
    const start=new Date(`${TODAY}T00:00:00Z`);
    if(button.dataset.preset==='week')start.setUTCDate(start.getUTCDate()-((start.getUTCDay()+6)%7));
    if(button.dataset.preset==='month')start.setUTCDate(1);
    byId('t-from').value=start.toISOString().slice(0,10);byId('t-to').value=TODAY;state.page=0;renderLedger();
  }));
  byId('t-day-filter').addEventListener('click',()=>{byId('t-from').value=state.day;byId('t-to').value=state.day;state.page=0;renderLedger();byId('t-day').close();byId('t-asset').focus();});
  byId('t-edit-form').addEventListener('submit',event=>{
    event.preventDefault();const form=event.currentTarget,row=rows.find(item=>item.id===state.editing);
    if(!form.reportValidity()||!row)return;
    const update={date:form.elements.date.value,asset:form.elements.asset.value.trim(),quantity:Number(form.elements.quantity.value),price:Number(form.elements.price.value),commission:Number(form.elements.commission.value),value:Number(form.elements.value.value)};
    if(!update.asset||update.date>TODAY||!Number.isFinite(update.value)){byId('t-edit-error').textContent='Enter a valid asset, date no later than the sample date, and numeric value.';byId('t-edit-error').hidden=false;return;}
    Object.assign(row,update);renderSummary();renderCalendar();renderChart();renderLedger();byId('t-edit').close();byId('t-announcement').textContent='Sample transaction saved.';
  });
  document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>byId(button.dataset.close).close()));
  document.querySelectorAll('.t-help').forEach(button=>button.addEventListener('click',()=>{button.dataset.open=String(button.dataset.open!=='true');}));
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){document.querySelectorAll('.t-help').forEach(button=>{button.dataset.open='false';});document.querySelectorAll('.t-filter-popover').forEach(details=>details.removeAttribute('open'));}});
  document.addEventListener('pointerdown',event=>{document.querySelectorAll('.t-help').forEach(button=>{if(!button.contains(event.target))button.dataset.open='false';});document.querySelectorAll('.t-filter-popover[open]').forEach(details=>{if(!details.contains(event.target))details.removeAttribute('open');});});
  const setTheme=theme=>{document.documentElement.dataset.theme=theme;document.querySelectorAll('[data-theme-choice]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.themeChoice===theme)));};
  document.querySelectorAll('[data-theme-choice]').forEach(button=>button.addEventListener('click',()=>setTheme(button.dataset.themeChoice)));
  document.querySelector('.t-mobile-theme').addEventListener('click',()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark'));
  document.querySelector('.sidebar-collapse').addEventListener('click',event=>{const collapsed=document.querySelector('.app').dataset.sidebar!=='collapsed';document.querySelector('.app').dataset.sidebar=collapsed?'collapsed':'expanded';event.currentTarget.setAttribute('aria-pressed',String(collapsed));event.currentTarget.setAttribute('aria-label',collapsed?'Expand sidebar':'Collapse sidebar');});
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(link=>{const clone=link.cloneNode(true);clone.removeAttribute('data-field');byId('t-menu-links').append(clone);});
  document.querySelector('.t-mobile-menu').addEventListener('click',()=>{byId('transactions-menu').showModal();document.querySelector('.t-mobile-menu').setAttribute('aria-expanded','true');});
  byId('transactions-menu').addEventListener('close',()=>document.querySelector('.t-mobile-menu').setAttribute('aria-expanded','false'));
  const query=new URLSearchParams(location.search);setTheme(query.get('theme')==='light'?'light':'dark');
  renderSummary();renderCalendar();renderChart();renderLedger();icons();
  let chartResizeFrame;
  window.addEventListener('resize',()=>{cancelAnimationFrame(chartResizeFrame);chartResizeFrame=requestAnimationFrame(renderChart);});
  if(query.get('state')==='loading'){document.querySelector('.t-table-scroll').hidden=true;document.querySelector('.t-pagination').hidden=true;document.querySelector('.card-cl-overlay').hidden=false;}
  window.transactionsMockup={rows,state,turnover,filters,renderLedger};
})();