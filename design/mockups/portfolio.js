(() => {
  'use strict';
  const assets = [
    { name: 'Vanguard FTSE All-World', ticker: 'VWCE', wallet: 'IKE', type: 'ETFs', currency: 'EUR', quantity: 180, price: 530, cost: 85000, daily: 0.28, ytd: 14.62 },
    { name: 'iShares Core S&P 500', ticker: 'CSPX', wallet: 'Brokerage', type: 'ETFs', currency: 'USD', quantity: 25, price: 2300, cost: 47200, daily: -0.18, ytd: 18.34 },
    { name: 'PKO Bank Polski', ticker: 'PKO', wallet: 'IKE', type: 'Stocks', currency: 'PLN', quantity: 600, price: 63.8, cost: 32520, daily: 1.24, ytd: 22.15 },
    { name: 'Microsoft', ticker: 'MSFT', wallet: 'Brokerage', type: 'Stocks', currency: 'USD', quantity: 18, price: 1690, cost: 26730, daily: -0.42, ytd: 11.28 },
    { name: 'CD Projekt', ticker: 'CDR', wallet: 'IKE', type: 'Stocks', currency: 'PLN', quantity: 90, price: 192, cost: 18630, daily: 0.84, ytd: -4.22 },
    { name: 'Bitcoin', ticker: 'BTC', wallet: 'Crypto', type: 'Crypto', currency: 'USD', quantity: 0.06, price: 272000, cost: 12800, daily: -1.12, ytd: 32.64 },
    { name: 'Treasury bonds', ticker: 'EDO', wallet: 'IKE', type: 'Bonds', currency: 'PLN', quantity: 140, price: 108.5, cost: 14000, daily: 0.02, ytd: 6.84 },
    { name: 'Ethereum', ticker: 'ETH', wallet: 'Crypto', type: 'Crypto', currency: 'USD', quantity: 1.2, price: 10400, cost: 14900, daily: -1.76, ytd: -12.46 },
    { name: 'Available cash', ticker: 'PLN', wallet: 'Brokerage', type: 'Cash', currency: 'PLN', quantity: 8150, price: 1, cost: 8150, daily: 0, ytd: 0 }
  ];
  const state = { wallet: 'All wallets', group: 'type', search: '', sort: 'value' };
  const number = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const money = value => number.format(value);
  const signed = value => `${value >= 0 ? '+' : ''}${money(value)}`;
  const tone = value => value >= 0 ? 'up' : 'down';
  const valueOf = asset => asset.quantity * asset.price;
  const sum = (items, getter) => items.reduce((total, item) => total + getter(item), 0);
  const scoped = () => assets.filter(asset => state.wallet === 'All wallets' || asset.wallet === state.wallet);
  const visible = () => scoped().filter(asset => `${asset.name} ${asset.ticker} ${asset.wallet}`.toLowerCase().includes(state.search.toLowerCase())).sort((first, second) => {
    if (state.sort === 'name') return first.name.localeCompare(second.name);
    if (state.sort === 'daily') return second.daily - first.daily;
    if (state.sort === 'return') return valueOf(second) / second.cost - valueOf(first) / first.cost;
    return valueOf(second) - valueOf(first);
  });
  const icons = () => window.lucide?.createIcons();
  const setResult = (id, value, suffix = '') => {
    const element = document.getElementById(id);
    element.textContent = `${signed(value)}${suffix}`;
    element.classList.remove('up', 'down');
    element.classList.add(tone(value));
  };
  function render() {
    const selected = scoped();
    const total = sum(selected, valueOf);
    const cost = sum(selected, asset => asset.cost);
    const previous = sum(selected, asset => valueOf(asset) / (1 + asset.daily / 100));
    document.getElementById('scope-label').textContent = state.wallet === 'All wallets' ? 'Total portfolio' : state.wallet;
    document.getElementById('total-value').textContent = money(total);
    document.getElementById('scope-meta').textContent = `${selected.length} positions · ${state.wallet === 'All wallets' ? '3 wallets' : '1 wallet'} · Base currency PLN`;
    setResult('daily-result', (total / previous - 1) * 100, '%');
    setResult('daily-money', total - previous, ' PLN');
    setResult('total-result', (total / cost - 1) * 100, '%');
    setResult('total-money', total - cost, ' PLN');
    document.getElementById('cost-value').textContent = money(cost);
    document.getElementById('wallets').innerHTML = ['All wallets', 'IKE', 'Brokerage', 'Crypto'].map(wallet => {
      const items = assets.filter(asset => wallet === 'All wallets' || asset.wallet === wallet);
      const value = sum(items, valueOf);
      const basis = sum(items, asset => asset.cost);
      const profit = (value / basis - 1) * 100;
      return `<button class="p-wallet" data-wallet="${wallet}" aria-pressed="${wallet === state.wallet}"><span class="p-wallet-top">${wallet}<i data-lucide="${wallet === 'All wallets' ? 'layers' : 'wallet'}" aria-hidden="true"></i></span><strong class="num">${money(value)}</strong><small><span class="num ${tone(profit)}">${signed(profit)}%</span><span>${items.length} positions</span></small></button>`;
    }).join('');
    const groups = new Map();
    for (const asset of selected) groups.set(asset[state.group], (groups.get(asset[state.group]) || 0) + valueOf(asset));
    const allocations = [...groups].sort((first, second) => second[1] - first[1]);
    const bar = document.getElementById('allocation-bar');
    bar.replaceChildren();
    for (const [index, [label, value]] of allocations.entries()) {
      const segment = document.createElement('span');
      segment.className = `p-segment p-tone-${index}`;
      segment.style.flex = String(value);
      segment.title = `${label}: ${money(value / total * 100)}%`;
      bar.append(segment);
    }
    bar.setAttribute('aria-label', allocations.map(([label, value]) => `${label} ${money(value / total * 100)}%`).join(', '));
    document.getElementById('allocation-legend').innerHTML = allocations.map(([label, value], index) => `<span class="p-legend-item"><span class="p-swatch p-tone-${index}"></span>${label}<strong class="num">${money(value / total * 100)}%</strong></span>`).join('');
    const items = visible();
    document.getElementById('holdings-count').textContent = `${items.length} / ${selected.length}`;
    document.getElementById('holdings').innerHTML = items.map(asset => {
      const value = valueOf(asset);
      const profit = value - asset.cost;
      const weight = value / total * 100;
      return `<tr><td><div class="p-asset"><span class="p-monogram" aria-hidden="true">${asset.ticker.slice(0, 2)}</span><div><span class="p-asset-name">${asset.name}</span><span class="p-asset-meta">${asset.ticker} · ${asset.wallet}</span></div></div></td><td class="num">${money(asset.price)}<span class="p-subvalue">${asset.currency}</span></td><td class="num ${tone(asset.daily)}">${signed(asset.daily)}%</td><td class="num ${tone(asset.ytd)}">${signed(asset.ytd)}%</td><td class="num">${money(value)}<span class="p-subvalue">${asset.quantity} units</span></td><td class="num ${tone(profit)}"><span class="p-pnl-money">${signed(profit)}</span><span class="p-subvalue ${tone(profit)}">${signed(profit / asset.cost * 100)}%</span></td><td class="num">${money(weight)}%<progress class="p-weight" value="${weight}" max="100" aria-label="Portfolio weight"></progress></td><td><button class="icon-btn" data-asset="${asset.ticker}" title="View ${asset.name}" aria-label="View ${asset.name}"><i data-lucide="chevron-right"></i></button></td></tr>`;
    }).join('');
    document.getElementById('empty').hidden = items.length > 0;
    document.getElementById('visible-total').textContent = `${money(sum(items, valueOf))} PLN`;
    icons();
  }
  document.getElementById('wallets').addEventListener('click', event => {
    const button = event.target.closest('[data-wallet]');
    if (!button) return;
    state.wallet = button.dataset.wallet;
    render();
    document.querySelector(`[data-wallet="${state.wallet}"]`).focus();
  });
  document.querySelectorAll('[data-group]').forEach(button => button.addEventListener('click', () => {
    state.group = button.dataset.group;
    document.querySelectorAll('[data-group]').forEach(option => {
      option.setAttribute('aria-pressed', String(option === button));
      option.classList.toggle('is-active', option === button);
    });
    render();
  }));
  document.getElementById('search').addEventListener('input', event => { state.search = event.target.value; render(); });
  document.getElementById('sort').addEventListener('change', event => { state.sort = event.target.value; render(); });
  document.getElementById('clear-search').addEventListener('click', () => {
    state.search = '';
    document.getElementById('search').value = '';
    render();
    document.getElementById('search').focus();
  });
  const dialog = document.getElementById('asset-dialog');
  document.getElementById('holdings').addEventListener('click', event => {
    const button = event.target.closest('[data-asset]');
    if (!button) return;
    const asset = assets.find(item => item.ticker === button.dataset.asset);
    const value = valueOf(asset);
    const details = [['Current value', `${money(value)} PLN`], ['Purchase value', `${money(asset.cost)} PLN`], ['Profit / loss', `${signed(value - asset.cost)} PLN`], ['Total return', `${signed((value / asset.cost - 1) * 100)}%`], ['Price in PLN', money(asset.price)], ['Quantity', String(asset.quantity)], ['Today / previous close', `${signed(asset.daily)}%`], ['YTD', `${signed(asset.ytd)}%`], ['Portfolio weight', `${money(value / sum(scoped(), valueOf) * 100)}%`], ['Quote currency', asset.currency]];
    document.getElementById('detail-content').innerHTML = `<h2 id="detail-name">${asset.name}</h2><p class="p-note">${asset.ticker} · ${asset.wallet} · ${asset.type}</p><dl class="p-detail-grid">${details.map(([label, content]) => `<div><dt>${label}</dt><dd class="num">${content}</dd></div>`).join('')}</dl>`;
    dialog.showModal();
  });
  document.getElementById('close-detail').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog && (event.clientX < dialog.getBoundingClientRect().left || event.clientX > dialog.getBoundingClientRect().right || event.clientY < dialog.getBoundingClientRect().top || event.clientY > dialog.getBoundingClientRect().bottom)) dialog.close(); });
  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('[data-theme-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.themeChoice === theme)));
  }
  document.querySelectorAll('[data-theme-choice]').forEach(button => button.addEventListener('click', () => setTheme(button.dataset.themeChoice)));
  document.querySelector('.p-mobile-theme').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  document.querySelector('.sidebar-collapse').addEventListener('click', event => {
    const collapsed = document.querySelector('.app').dataset.sidebar !== 'collapsed';
    document.querySelector('.app').dataset.sidebar = collapsed ? 'collapsed' : 'expanded';
    event.currentTarget.setAttribute('aria-pressed', String(collapsed));
    event.currentTarget.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    event.currentTarget.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
  });
  document.getElementById('export').addEventListener('click', () => {
    const rows = [['Asset', 'Ticker', 'Wallet', 'Quantity', 'Price PLN', 'Current value PLN', 'Purchase value PLN', 'Profit PLN', 'Total return %', 'Today %', 'YTD %'], ...visible().map(asset => [asset.name, asset.ticker, asset.wallet, asset.quantity, asset.price, valueOf(asset).toFixed(2), asset.cost, (valueOf(asset) - asset.cost).toFixed(2), ((valueOf(asset) / asset.cost - 1) * 100).toFixed(2), asset.daily, asset.ytd])];
    const csv = rows.map(row => row.map(cell => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'portfolio-sample.csv';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  render();
})();