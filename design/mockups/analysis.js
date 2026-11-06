(function () {
    'use strict';

    const assets = [
        { ticker: 'XTB.WA', name: 'XTB', exchange: 'GPW', currency: 'PLN', price: 72.48, day: 1.34, sector: 'Financial services', industry: 'Capital markets', cap: '8.52B', pe: '10.8', forward: '9.6', dividend: '7.21%', high: 84.20, low: 48.36, revenue: 1873, margin: 0.46 },
        { ticker: 'DNP.WA', name: 'Dino Polska', exchange: 'GPW', currency: 'PLN', price: 41.26, day: -0.82, sector: 'Consumer defensive', industry: 'Grocery stores', cap: '40.45B', pe: '27.2', forward: '23.4', dividend: '0.00%', high: 49.32, low: 31.08, revenue: 29274, margin: 0.05 },
        { ticker: 'PKO.WA', name: 'PKO Bank Polski', exchange: 'GPW', currency: 'PLN', price: 78.92, day: 0.68, sector: 'Financial services', industry: 'Banks', cap: '98.65B', pe: '9.4', forward: '8.9', dividend: '6.84%', high: 86.70, low: 55.80, revenue: 28620, margin: 0.31 },
        { ticker: 'AAPL', name: 'Apple', exchange: 'NASDAQ', currency: 'USD', price: 248.50, day: -0.42, sector: 'Technology', industry: 'Consumer electronics', cap: '3.69T', pe: '33.1', forward: '29.7', dividend: '0.42%', high: 271.40, low: 169.21, revenue: 391035, margin: 0.24 },
        { ticker: 'MSFT', name: 'Microsoft', exchange: 'NASDAQ', currency: 'USD', price: 512.64, day: 0.91, sector: 'Technology', industry: 'Software infrastructure', cap: '3.81T', pe: '36.7', forward: '31.5', dividend: '0.65%', high: 558.40, low: 344.79, revenue: 245122, margin: 0.36 },
    ];
    const storageKey = 'roastfolio.mockup.analysis.favorites';
    let favorites = assets.slice(0, 4).map(asset => asset.ticker);
    try {
        const saved = JSON.parse(localStorage.getItem(storageKey));
        if (Array.isArray(saved)) favorites = saved.filter(ticker => assets.some(asset => asset.ticker === ticker));
    } catch (_) {}
    let selected = assets[0];
    let range = '1y';
    let list = 'favorites';
    let statement = 'income';
    let period = 'annual';
    let priceChart;
    let macdChart;
    const enabled = { volume: true, ma10: false, ma20: false, ma50: false, macd: false };
    const byId = id => document.getElementById(id);
    const number = value => value.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const signed = value => `${value >= 0 ? '+' : ''}${number(value)}`;
    const color = token => getComputedStyle(document.documentElement).getPropertyValue(token).trim();
    const icons = () => window.lucide?.createIcons();
    const setPressed = (selector, attribute, value) => document.querySelectorAll(selector).forEach(button => button.setAttribute('aria-pressed', String(button.dataset[attribute] === value)));

    function renderList() {
        const query = byId('asset-search').value.trim().toLowerCase();
        const matches = assets.filter(asset => (list === 'all' || favorites.includes(asset.ticker)) && `${asset.ticker} ${asset.name}`.toLowerCase().includes(query));
        byId('asset-count').textContent = `${matches.length} companies`;
        byId('asset-list').replaceChildren();
        matches.forEach(asset => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'a-asset';
            button.dataset.ticker = asset.ticker;
            button.setAttribute('aria-current', String(asset === selected));
            button.innerHTML = `<strong>${asset.ticker}</strong><span class="num">${number(asset.price)}</span><span class="a-caption">${asset.name}</span><span class="num ${asset.day >= 0 ? 'up' : 'down'}">${signed(asset.day)}%</span>`;
            button.addEventListener('click', () => {
                selected = asset;
                byId('company-picker').close();
                renderAsset();
                byId('asset-name').focus({ preventScroll: true });
            });
            byId('asset-list').append(button);
        });
        byId('asset-empty').hidden = matches.length > 0;
    }

    function renderAsset() {
        byId('asset-name').textContent = selected.name;
        byId('asset-monogram').textContent = selected.name[0];
        byId('asset-meta').textContent = `${selected.ticker} · ${selected.exchange} · ${selected.currency}`;
        byId('asset-price').textContent = number(selected.price);
        byId('asset-currency').textContent = selected.currency;
        const dailyAmount = selected.price - selected.price / (1 + selected.day / 100);
        byId('asset-day').textContent = `${signed(dailyAmount)} (${signed(selected.day)}%) today`;
        byId('asset-day').className = `num ${selected.day >= 0 ? 'up' : 'down'}`;
        const favorite = favorites.includes(selected.ticker);
        const favoriteButton = byId('favorite-toggle');
        favoriteButton.setAttribute('aria-pressed', String(favorite));
        favoriteButton.title = favorite ? 'Remove from favorites' : 'Add to favorites';
        favoriteButton.setAttribute('aria-label', favoriteButton.title);
        const metrics = [
            ['Sector', selected.sector, selected.industry],
            ['Market cap', selected.cap, selected.currency],
            ['P/E ratio', selected.pe, `Forward ${selected.forward}`],
            ['Dividend yield', selected.dividend, 'Trailing 12 months'],
            ['52-week high', number(selected.high), selected.currency],
            ['52-week low', number(selected.low), selected.currency],
        ];
        byId('fundamental-grid').innerHTML = metrics.map(([label, value, detail]) => `<div><dt>${label}</dt><dd class="num">${value}<small>${detail}</small></dd></div>`).join('');
        renderList();
        renderCharts();
        renderStatement();
    }

    function dailyBars() {
        const bars = [];
        const end = Date.UTC(2026, 9, 30);
        const seed = assets.indexOf(selected) + 1;
        for (let offset = 2190; offset >= 0; offset--) {
            const timestamp = end - offset * 86400000;
            const weekday = new Date(timestamp).getUTCDay();
            if (weekday === 0 || weekday === 6) continue;
            const progress = (2190 - offset) / 2190;
            const price = selected.price * (0.35 + 0.65 * progress + 0.04 * Math.sin(offset / 19 + seed) + 0.016 * Math.sin(offset / 3));
            bars.push({ timestamp, price, volume: Math.round(80000 + 160000 * Math.abs(Math.sin(offset * seed / 7))) });
        }
        const scale = selected.price / bars.at(-1).price;
        return bars.map(bar => ({ ...bar, price: bar.price * scale }));
    }

    function movingAverage(values, count) {
        let sum = 0;
        return values.map((value, index) => {
            sum += value;
            if (index >= count) sum -= values[index - count];
            return index < count - 1 ? null : sum / count;
        });
    }

    function exponentialAverage(values, count) {
        let average = values[0];
        return values.map(value => (average += (value - average) * 2 / (count + 1)));
    }

    function renderCharts() {
        byId('chart-loader').hidden = false;
        byId('chart-error').hidden = true;
        priceChart?.destroy();
        macdChart?.destroy();
        priceChart = null;
        macdChart = null;
        const history = dailyBars();
        const end = history.at(-1).timestamp;
        const days = { '1w': 7, '1m': 31, '1y': 365, '5y': 1826, all: 2191 };
        const start = range === 'ytd' ? Date.UTC(2026, 0, 1) : end - (days[range] || 1) * 86400000;
        const filtered = history.filter(bar => bar.timestamp >= start);
        const bars = range === '1d' ? Array.from({ length: 79 }, (_, index) => {
            const progress = index / 78;
            return { timestamp: end + (9 * 60 + index * 5) * 60000, price: selected.price / (1 + selected.day / 100) * (1 + selected.day / 100 * progress) + Math.sin(index / 4) * selected.price * 0.001 * Math.sin(Math.PI * progress), volume: 2000 + Math.abs(Math.cos(index)) * 8000 };
        }) : filtered;
        const change = (bars.at(-1).price / bars[0].price - 1) * 100;
        byId('range-return').textContent = `${signed(change)}% · ${range.toUpperCase()}`;
        byId('range-return').className = `num ${change >= 0 ? 'up' : 'down'}`;
        const scope = byId('wallet-scope').value;
        const transactionFixtures = assets.indexOf(selected) < 3 ? [
            { timestamp: Date.UTC(2026, 2, 16), wallet: 'xtb', side: 'Buy', units: 40 },
            { timestamp: Date.UTC(2026, 6, 8), wallet: 'ike', side: 'Buy', units: 25 },
            { timestamp: Date.UTC(2026, 9, 29), wallet: 'xtb', side: 'Sell', units: 10 },
        ] : [];
        const transactions = transactionFixtures.filter(transaction => range !== '1d' && transaction.timestamp >= bars[0].timestamp && transaction.timestamp <= bars.at(-1).timestamp && (scope === 'all' || scope === transaction.wallet));
        byId('transaction-summary').textContent = scope === 'none' ? 'Transaction markers hidden' : transactions.length ? transactions.map(transaction => `${transaction.side} ${transaction.units} · ${transaction.wallet.toUpperCase()} · ${new Date(transaction.timestamp).toLocaleDateString('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short' })}`).join('   /   ') : 'No transactions in this range';
        byId('macd-wrap').hidden = !enabled.macd;
        try {
            if (typeof window.Chart !== 'function') throw new Error('Chart library unavailable');
            const labels = bars.map(bar => new Date(bar.timestamp).toLocaleDateString('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: '2-digit' }));
            if (range === '1d') labels.splice(0, labels.length, ...bars.map(bar => new Date(bar.timestamp).toISOString().slice(11, 16)));
            const text = color('--text-secondary');
            const grid = color('--border-subtle');
            const datasets = [{ label: `${selected.ticker} (${selected.currency})`, data: bars.map(bar => bar.price), borderColor: color('--accent-primary'), backgroundColor: color('--accent-glow'), fill: true, borderWidth: 2, pointRadius: 0, pointHitRadius: 8, yAxisID: 'price' }];
            if (enabled.volume) datasets.push({ type: 'bar', label: 'Volume', data: bars.map(bar => bar.volume), backgroundColor: color('--border-strong'), yAxisID: 'volume', order: 2 });
            const prices = history.map(bar => bar.price);
            for (const [key, weeks, token] of [['ma10', 10, '--color-warning'], ['ma20', 20, '--color-purple'], ['ma50', 50, '--color-success']]) {
                const input = document.querySelector(`[data-indicator="${key}"]`);
                input.disabled = range === '1d';
                input.closest('label').title = range === '1d' ? 'Weekly averages available on daily history' : `${weeks}-week moving average`;
                if (!enabled[key] || range === '1d') continue;
                const averages = movingAverage(prices, weeks * 5).slice(-bars.length);
                datasets.push({ label: `MA${weeks}`, data: averages, borderColor: color(token), pointRadius: 0, borderWidth: 1.5, yAxisID: 'price' });
            }
            for (const side of ['Buy', 'Sell']) {
                const matching = transactions.filter(transaction => transaction.side === side);
                if (matching.length) datasets.push({ label: `${side} transaction`, data: bars.map(bar => matching.some(transaction => transaction.timestamp === bar.timestamp) ? bar.price : null), showLine: false, pointStyle: 'triangle', pointRotation: side === 'Sell' ? 180 : 0, pointRadius: 7, backgroundColor: color(side === 'Buy' ? '--color-success' : '--color-danger'), yAxisID: 'price' });
            }
            priceChart = new Chart(byId('price-chart'), {
                type: 'line', data: { labels, datasets },
                options: { responsive: true, maintainAspectRatio: false, animation: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: item => `${item.dataset.label}: ${number(item.parsed.y)}` } } }, scales: { x: { grid: { display: false }, ticks: { color: text, maxTicksLimit: 6, maxRotation: 0 } }, price: { position: 'right', grid: { color: grid }, ticks: { color: text, maxTicksLimit: 6 } }, volume: { display: false, min: 0, max: Math.max(...bars.map(bar => bar.volume)) * 6 } } },
            });
            if (enabled.macd) {
                const source = range === '1d' ? bars.map(bar => bar.price) : prices;
                const fast = exponentialAverage(source, 12);
                const slow = exponentialAverage(source, 26);
                const macd = fast.map((value, index) => value - slow[index]);
                const signal = exponentialAverage(macd, 9);
                macdChart = new Chart(byId('macd-chart'), { type: 'line', data: { labels, datasets: [{ label: 'MACD', data: macd.slice(-bars.length), borderColor: color('--accent-primary'), borderWidth: 1.5, pointRadius: 0 }, { label: 'Signal', data: signal.slice(-bars.length), borderColor: color('--color-warning'), borderWidth: 1.5, pointRadius: 0 }] }, options: { responsive: true, maintainAspectRatio: false, animation: false, plugins: { legend: { labels: { color: text, boxWidth: 12 } } }, scales: { x: { display: false }, y: { position: 'right', ticks: { color: text, maxTicksLimit: 3 }, grid: { color: grid } } } } });
            }
        } catch (error) {
            byId('chart-error').hidden = false;
            console.warn('Analysis mockup chart:', error.message);
        } finally {
            byId('chart-loader').hidden = true;
        }
    }

    function renderStatement() {
        const headers = period === 'annual' ? ['2025', '2024', '2023', '2022'] : ['Q3 2026', 'Q2 2026', 'Q1 2026', 'Q4 2025'];
        const revenue = selected.revenue / (period === 'annual' ? 1 : 4);
        const rows = statement === 'income' ? [['Revenue', 1], ['Operating income', selected.margin + 0.06], ['Net income', selected.margin], ['Diluted EPS', selected.margin / 118]] : [['Operating cash flow', selected.margin + 0.08], ['Capital expenditure', -0.06], ['Investing cash flow', -0.09], ['Financing cash flow', -0.12], ['Free cash flow', selected.margin + 0.02]];
        byId('statement-unit').textContent = `${selected.currency} million${statement === 'income' ? ' · except EPS' : ''}`;
        byId('statement-table').innerHTML = `<thead><tr><th scope="col">Metric</th>${headers.map(header => `<th scope="col">${header}</th>`).join('')}</tr></thead><tbody>${rows.map(([label, ratio]) => `<tr><th scope="row">${label}</th>${headers.map((_, index) => `<td>${number(revenue * ratio * (1 - index * 0.13))}</td>`).join('')}</tr>`).join('')}</tbody>`;
    }

    function setTheme(theme) {
        document.documentElement.dataset.theme = theme;
        setPressed('[data-theme-choice]', 'themeChoice', theme);
        renderCharts();
    }

    const help = {
        price: { title: 'Price history', entries: [
            ['Range return', 'Price change from the first to the last visible quote, in the asset currency. Excludes dividends, fees and currency conversion; this is not your portfolio return.'],
            ['Transactions', 'Triangles mark sample buys and sells for the selected wallet and date range. They do not change the price return.'],
            ['Volume', 'Number of shares traded per bar, shown on a separate scale.'],
            ['MA10 / MA20 / MA50', 'Simple averages over 50, 100 and 250 trading-day samples, approximating 10, 20 and 50 weeks. Not available for the intraday range.'],
            ['MACD', 'The difference between 12- and 26-bar exponential averages; the signal is a 9-bar exponential average. Bar duration depends on the selected range.'],
        ] },
        fundamentals: { title: 'Fundamental metrics', entries: [
            ['Market cap', 'Share price multiplied by shares outstanding. B means billion; T means trillion.'],
            ['P/E ratio', 'Price divided by earnings per share over the trailing 12 months. Forward P/E uses estimated future earnings, not reported results.'],
            ['Dividend yield', 'Trailing annual dividends per share divided by share price. Historical yield does not guarantee a future payout.'],
            ['52-week high / low', 'The highest and lowest quoted prices over the last year, in the asset currency.'],
        ] },
        statements: { title: 'Financial statements', entries: [
            ['Units', 'Amounts are in millions of the asset currency, except diluted EPS, which is currency per share. All values in this mockup are illustrative.'],
            ['Annual / quarterly', 'Annual columns cover a full fiscal year; quarterly columns cover individual quarters, not cumulative year-to-date totals. Most recent period first.'],
            ['Income statement', 'Revenue and earnings follow accounting recognition, which may differ from when cash changes hands.'],
            ['Cash flow', 'Operating, investing and financing cash movements. Capital expenditure is negative here; free cash flow equals operating cash flow plus capital expenditure.'],
        ] },
    };
    let helpTrigger = null;
    document.querySelectorAll('[data-help]').forEach(button => button.addEventListener('click', () => {
        helpTrigger = button;
        const topic = help[button.dataset.help];
        byId('help-title').textContent = topic.title;
        byId('help-content').replaceChildren();
        topic.entries.forEach(([term, description]) => {
            const title = document.createElement('dt');
            title.textContent = term;
            const definition = document.createElement('dd');
            definition.textContent = description;
            byId('help-content').append(title, definition);
        });
        const bounds = button.getBoundingClientRect();
        const popover = byId('analysis-help');
        const width = Math.min(380, innerWidth - 32);
        popover.style.left = `${Math.max(16, Math.min(bounds.left, innerWidth - width - 16))}px`;
        popover.style.top = '16px';
        requestAnimationFrame(() => {
            const height = popover.getBoundingClientRect().height;
            popover.style.top = `${Math.max(16, Math.min(bounds.bottom + 8, innerHeight - height - 80))}px`;
        });
    }));
    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        if (byId('analysis-help').matches(':popover-open')) {
            event.preventDefault();
            byId('analysis-help').hidePopover();
            helpTrigger?.focus({ preventScroll: true });
        } else if (byId('company-picker').open) {
            event.preventDefault();
            byId('company-picker').close();
        }
    });

    document.querySelectorAll('[data-theme-choice]').forEach(button => button.addEventListener('click', () => setTheme(button.dataset.themeChoice)));
    document.querySelector('.a-mobile-theme').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
    document.querySelector('.sidebar-collapse').addEventListener('click', event => {
        const app = document.querySelector('.app');
        const collapsed = app.dataset.sidebar !== 'collapsed';
        app.dataset.sidebar = collapsed ? 'collapsed' : 'expanded';
        event.currentTarget.setAttribute('aria-pressed', String(collapsed));
        event.currentTarget.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
        event.currentTarget.setAttribute('aria-label', event.currentTarget.title);
    });
    byId('asset-search').addEventListener('input', renderList);
    byId('reset-search').addEventListener('click', () => {
        byId('asset-search').value = '';
        list = 'all';
        setPressed('[data-list]', 'list', list);
        renderList();
        byId('asset-search').focus();
    });
    document.querySelectorAll('[data-list]').forEach(button => button.addEventListener('click', () => {
        list = button.dataset.list;
        setPressed('[data-list]', 'list', list);
        renderList();
    }));
    byId('favorite-toggle').addEventListener('click', () => {
        favorites = favorites.includes(selected.ticker) ? favorites.filter(ticker => ticker !== selected.ticker) : [...favorites, selected.ticker];
        try { localStorage.setItem(storageKey, JSON.stringify(favorites)); } catch (_) {}
        renderAsset();
    });
    byId('show-companies').addEventListener('click', () => {
        byId('company-picker').showModal();
        byId('asset-search').focus();
    });
    byId('close-companies').addEventListener('click', () => byId('company-picker').close());
    byId('company-picker').addEventListener('click', event => {
        if (event.target !== byId('company-picker')) return;
        const bounds = event.target.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) byId('company-picker').close();
    });
    document.querySelectorAll('[data-range]').forEach(button => button.addEventListener('click', () => {
        range = button.dataset.range;
        setPressed('[data-range]', 'range', range);
        renderCharts();
    }));
    document.querySelectorAll('[data-indicator]').forEach(input => input.addEventListener('change', () => {
        enabled[input.dataset.indicator] = input.checked;
        renderCharts();
    }));
    byId('wallet-scope').addEventListener('change', renderCharts);
    byId('retry-chart').addEventListener('click', () => location.reload());
    document.querySelectorAll('[data-statement]').forEach(button => button.addEventListener('click', () => {
        statement = button.dataset.statement;
        setPressed('[data-statement]', 'statement', statement);
        renderStatement();
    }));
    document.querySelectorAll('[data-period]').forEach(button => button.addEventListener('click', () => {
        period = button.dataset.period;
        setPressed('[data-period]', 'period', period);
        renderStatement();
    }));
    icons();
    renderAsset();
})();