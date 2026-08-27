(function() {
    let searchTimeout = null;
    let currentChart = null;
    let currentTicker = null;
    let currentPeriod = '5y';
    let currentFinancialData = { cashflow: {}, financials: {}, earnings: [] };
    let currentStatementType = 'income'; // 'income' or 'cashflow'
    let currentFinPeriod = 'annual'; // 'annual' or 'quarterly'
    let sparklineCache = {}; // Cache for sparkline data (localStorage)
    let favoritesData = []; // In-memory favorites from API
    let showVolume = true; // Volume histogram (on by default)
    let showMA = { ma10: false, ma20: false, ma50: false }; // Moving averages
    let showMACD = false; // MACD indicator
    let currentPortfolioFilter = 'all'; // 'all' or specific portfolioId

    // ── Indicator helpers ──────────────────────────────────────────────────

    // Simple Moving Average over `period` data points
    function calcSMA(values, period) {
        const result = [];
        for (let i = 0; i < values.length; i++) {
            if (i < period - 1) { result.push(null); continue; }
            let sum = 0;
            for (let j = i - period + 1; j <= i; j++) sum += values[j];
            result.push(sum / period);
        }
        return result;
    }

    // Exponential Moving Average
    function calcEMA(values, period) {
        const k = 2 / (period + 1);
        const result = [];
        let ema = null;
        for (let i = 0; i < values.length; i++) {
            if (values[i] == null) { result.push(null); continue; }
            if (ema === null) {
                // seed with first non-null value; wait for enough points
                if (i < period - 1) { result.push(null); continue; }
                // seed: SMA of first `period` values
                let sum = 0;
                for (let j = i - period + 1; j <= i; j++) sum += values[j];
                ema = sum / period;
            } else {
                ema = values[i] * k + ema * (1 - k);
            }
            result.push(ema);
        }
        return result;
    }

    // MACD = EMA12 - EMA26, Signal = EMA9(MACD), Hist = MACD - Signal
    function calcMACD(values) {
        const ema12 = calcEMA(values, 12);
        const ema26 = calcEMA(values, 26);
        const macdLine = ema12.map((v, i) => (v != null && ema26[i] != null) ? v - ema26[i] : null);
        const signal = calcEMA(macdLine.map(v => v ?? 0), 9);
        // Only emit signal where macd is valid
        const signalClean = signal.map((v, i) => (macdLine[i] != null ? v : null));
        const hist = macdLine.map((v, i) => (v != null && signalClean[i] != null) ? v - signalClean[i] : null);
        return { macdLine, signal: signalClean, hist };
    }

    const SPARKLINE_CACHE_KEY = 'roastfolio_sparkline_cache';
    const CACHE_EXPIRY_DAYS = 1; // Cache sparklines for 1 day

    const inputEl = document.getElementById('analysis-search-input');
    const dropdownEl = document.getElementById('analysis-ticker-dropdown');
    const contentArea = document.getElementById('analysis-content-area');
    
    // Sparkline cache management
    function getSparklineCache() {
        try {
            const stored = localStorage.getItem(SPARKLINE_CACHE_KEY);
            if (!stored) return {};
            const cache = JSON.parse(stored);
            // Clean expired entries
            const now = Date.now();
            Object.keys(cache).forEach(ticker => {
                if (cache[ticker].expiresAt < now) {
                    delete cache[ticker];
                }
            });
            return cache;
        } catch (e) {
            console.error('Failed to load sparkline cache:', e);
            return {};
        }
    }

    function saveSparklineCache(ticker, data) {
        try {
            const cache = getSparklineCache();
            cache[ticker] = {
                ...data,
                expiresAt: Date.now() + (CACHE_EXPIRY_DAYS * 24 * 60 * 60 * 1000)
            };
            localStorage.setItem(SPARKLINE_CACHE_KEY, JSON.stringify(cache));
        } catch (e) {
            console.error('Failed to save sparkline cache:', e);
        }
    }

    // Favorites management (API-based)
    async function getFavorites() {
        // Mock data for localhost testing
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            if (favoritesData.length === 0) {
                favoritesData = [
                    { ticker: 'AAPL', name: 'Apple Inc.', addedAt: new Date().toISOString() },
                    { ticker: 'MSFT', name: 'Microsoft Corporation', addedAt: new Date().toISOString() },
                    { ticker: 'CDR.WA', name: 'CD Projekt S.A.', addedAt: new Date().toISOString() }
                ];
            }
            return favoritesData;
        }

        try {
            const res = await fetch(`${_apiBase()}/favorites`, {
                headers: getAuthHeaders()
            });
            if (!res.ok) throw new Error('Failed to fetch favorites');
            const data = await res.json();
            favoritesData = data.favorites || [];
            return favoritesData;
        } catch (e) {
            console.error('Failed to load favorites:', e);
            return favoritesData; // Return cached data
        }
    }

    async function saveFavorites(favorites) {
        // Mock save for localhost testing
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            favoritesData = favorites;
            return true;
        }

        try {
            const res = await fetch(`${_apiBase()}/favorites`, {
                method: 'PUT',
                headers: {
                    ...getAuthHeaders(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ favorites })
            });
            if (!res.ok) throw new Error('Failed to save favorites');
            favoritesData = favorites;
            return true;
        } catch (e) {
            console.error('Failed to save favorites:', e);
            return false;
        }
    }

    function isFavorite(ticker) {
        return favoritesData.some(f => f.ticker === ticker);
    }

    async function addToFavorites(ticker, name) {
        if (!favoritesData.some(f => f.ticker === ticker)) {
            const newFavorites = [...favoritesData, {
                ticker: ticker,
                name: name,
                addedAt: new Date().toISOString()
            }];
            const success = await saveFavorites(newFavorites);
            if (success) {
                updateFavoriteButton();
                return true;
            }
        }
        return false;
    }

    async function removeFromFavorites(ticker) {
        const newFavorites = favoritesData.filter(f => f.ticker !== ticker);
        const success = await saveFavorites(newFavorites);
        if (success) {
            updateFavoriteButton();
            renderFavoritesList();
        }
    }

    function _apiBase() {
        const cfg = window.__CONFIG__ || window.APP_CONFIG || {};
        return (cfg.apiUrl || '').replace(/\/prices$/, '');
    }

    // Formatting utilities
    function formatCurrency(val) {
        if (val === null || val === undefined) return '—';
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
    }
    
    function formatLargeNumber(num) {
        if (num === null || num === undefined) return '—';
        if (num >= 1e12) return (num / 1e12).toFixed(2) + 'T';
        if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
        if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
        return num.toLocaleString();
    }

    function formatPercent(val) {
        if (val === null || val === undefined) return '—';
        return (val * 100).toFixed(2) + '%';
    }

    function renderChart(historyData, transactions = []) {
        const container = document.getElementById('analysisChartContainer');
        container.innerHTML = ''; // clear existing
        
        if (!historyData || historyData.length === 0) {
            container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#888;">No history available.</div>';
            return;
        }

        container.style.position = 'relative';

        const isDark = typeof window.isRoastfolioDark === 'function'
            ? window.isRoastfolioDark()
            : window.matchMedia('(prefers-color-scheme: dark)').matches;
        const textColor = isDark ? '#c8e3f5' : '#142640';
        const gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)';

        let tooltip = document.getElementById('analysis-chart-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'analysis-chart-tooltip';
            tooltip.style.position = 'absolute';
            tooltip.style.display = 'none';
            tooltip.style.padding = '8px 12px';
            tooltip.style.boxSizing = 'border-box';
            tooltip.style.fontSize = '12px';
            tooltip.style.textAlign = 'left';
            tooltip.style.zIndex = '1000';
            tooltip.style.pointerEvents = 'none';
            tooltip.style.border = '1px solid rgba(0, 229, 255, 0.2)';
            tooltip.style.boxShadow = '0 4px 12px rgba(0,0,0,0.4)';
            tooltip.style.borderRadius = '8px';
            tooltip.style.background = isDark ? '#0e1e30' : '#ffffff';
            tooltip.style.color = isDark ? '#c8e3f5' : '#142640';
            container.appendChild(tooltip);
        } else {
            tooltip.style.display = 'none';
        }

        // Calculate chart height: base + extra panes
        const hasAnyIndicator = showVolume || showMACD;
        const macdPaneHeight = showMACD ? 100 : 0;
        const volPaneHeight = showVolume ? 80 : 0;
        const chartHeight = 300 + macdPaneHeight + volPaneHeight;

        currentChart = LightweightCharts.createChart(container, {
            width: container.clientWidth,
            height: chartHeight,
            layout: {
                background: { type: 'solid', color: 'transparent' },
                textColor: textColor,
            },
            grid: {
                vertLines: { color: gridColor },
                horzLines: { color: gridColor },
            },
            rightPriceScale: {
                borderVisible: false,
            },
            timeScale: {
                borderVisible: false,
                fixLeftEdge: true,
                fixRightEdge: true,
                timeVisible: currentPeriod === '1d' || currentPeriod === '1w',
            },
        });

        // Shrink parent wrapper height to match
        const wrapper = document.getElementById('analysis-chart-wrapper') || container.parentElement;
        if (wrapper) wrapper.style.height = chartHeight + 'px';

        // Calculate price scale margins to accommodate panes below
        const totalExtra = macdPaneHeight + volPaneHeight;
        const priceBottom = totalExtra > 0 ? totalExtra / chartHeight : 0;
        // Slightly above zero baseline
        const priceBottomMargin = Math.max(0, priceBottom + 0.02);

        const lineSeries = currentChart.addLineSeries({
            color: '#00e5ff',
            lineWidth: 2,
            crosshairMarkerRadius: 4,
            priceScaleId: 'right',
        });

        const chartData = historyData.map(d => ({
            time: (d.t.includes('T')) ? new Date(d.t).getTime() / 1000 : d.t,
            value: d.c
        }));

        lineSeries.setData(chartData);

        if (hasAnyIndicator) {
            currentChart.priceScale('right').applyOptions({
                scaleMargins: { top: 0.02, bottom: priceBottomMargin },
            });
        }

        // ── Moving averages ──────────────────────────────────────────────
        const closes = historyData.map(d => d.c);
        const MA_CONFIGS = [
            { key: 'ma10', period: 10, color: '#f59e0b', label: 'MA10W' },
            { key: 'ma20', period: 20, color: '#a78bfa', label: 'MA20W' },
            { key: 'ma50', period: 50, color: '#34d399', label: 'MA50W' },
        ];
        MA_CONFIGS.forEach(({ key, period, color }) => {
            if (!showMA[key]) return;
            const smaValues = calcSMA(closes, period);
            const maSeries = currentChart.addLineSeries({
                color,
                lineWidth: 1,
                crosshairMarkerVisible: false,
                lastValueVisible: true,
                priceLineVisible: false,
                priceScaleId: 'right',
            });
            const maData = historyData
                .map((d, i) => smaValues[i] != null ? {
                    time: (d.t.includes('T')) ? new Date(d.t).getTime() / 1000 : d.t,
                    value: smaValues[i]
                } : null)
                .filter(Boolean);
            maSeries.setData(maData);
        });

        // ── Volume histogram ─────────────────────────────────────────────
        if (showVolume) {
            const hasVolume = historyData.some(d => d.v != null);
            if (hasVolume) {
                // vol sits in bottom portion; if MACD also visible, vol is above MACD
                const volBottom = showMACD ? macdPaneHeight / chartHeight : 0;
                const volTop = 1 - volPaneHeight / chartHeight;

                const volSeries = currentChart.addHistogramSeries({
                    color: 'rgba(14,165,233,0.3)',
                    priceFormat: { type: 'volume' },
                    priceScaleId: 'vol',
                    lastValueVisible: false,
                    priceLineVisible: false,
                });
                currentChart.priceScale('vol').applyOptions({
                    scaleMargins: { top: volTop, bottom: volBottom },
                    borderVisible: false,
                });

                const volData = historyData
                    .filter(d => d.v != null)
                    .map(d => ({
                        time: (d.t.includes('T')) ? new Date(d.t).getTime() / 1000 : d.t,
                        value: d.v,
                        color: 'rgba(14,165,233,0.25)',
                    }));
                volSeries.setData(volData);
            }
        }

        // ── MACD ─────────────────────────────────────────────────────────
        if (showMACD) {
            const { macdLine, signal, hist } = calcMACD(closes);
            const macdBottom = 0;
            const macdTop = 1 - macdPaneHeight / chartHeight;

            // MACD histogram (divergence bars)
            const macdHistSeries = currentChart.addHistogramSeries({
                priceScaleId: 'macd',
                lastValueVisible: false,
                priceLineVisible: false,
            });
            currentChart.priceScale('macd').applyOptions({
                scaleMargins: { top: macdTop, bottom: macdBottom },
                borderVisible: false,
            });

            const macdHistData = historyData
                .map((d, i) => hist[i] != null ? {
                    time: (d.t.includes('T')) ? new Date(d.t).getTime() / 1000 : d.t,
                    value: hist[i],
                    color: hist[i] >= 0 ? 'rgba(52,211,153,0.6)' : 'rgba(248,113,113,0.6)',
                } : null)
                .filter(Boolean);
            macdHistSeries.setData(macdHistData);

            // MACD line
            const macdLineSeries = currentChart.addLineSeries({
                color: '#00e5ff',
                lineWidth: 1,
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
                priceScaleId: 'macd',
            });
            const macdLineData = historyData
                .map((d, i) => macdLine[i] != null ? {
                    time: (d.t.includes('T')) ? new Date(d.t).getTime() / 1000 : d.t,
                    value: macdLine[i]
                } : null)
                .filter(Boolean);
            macdLineSeries.setData(macdLineData);

            // Signal line
            const signalSeries = currentChart.addLineSeries({
                color: '#f59e0b',
                lineWidth: 1,
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
                priceScaleId: 'macd',
            });
            const signalData = historyData
                .map((d, i) => signal[i] != null ? {
                    time: (d.t.includes('T')) ? new Date(d.t).getTime() / 1000 : d.t,
                    value: signal[i]
                } : null)
                .filter(Boolean);
            signalSeries.setData(signalData);
        }

        const txByTime = {};

        // Plot transactions as markers
        if (transactions && transactions.length > 0) {
            const availableTimes = chartData.map(d => d.time);
            
            transactions.forEach(tx => {
                let txTime = tx.date;
                // tx.date is usually YYYY-MM-DD. 
                // If the chart is using UNIX timestamps (e.g., 1D or 1W), we must map it.
                if (typeof availableTimes[0] === 'number') {
                    // Convert tx string to timestamp
                    txTime = new Date(txTime).getTime() / 1000;
                }
                
                let matchedTime = null;
                if (typeof txTime === 'string') {
                    // Exact or next available date
                    matchedTime = availableTimes.find(t => t >= txTime);
                } else {
                    // Nearest timestamp
                    matchedTime = availableTimes.reduce((prev, curr) => Math.abs(curr - txTime) < Math.abs(prev - txTime) ? curr : prev, availableTimes[0]);
                }
                
                if (matchedTime) {
                    if (!txByTime[matchedTime]) {
                        txByTime[matchedTime] = [];
                    }
                    txByTime[matchedTime].push(tx);
                }
            });
            
            const markers = [];
            for (const [timeStr, txs] of Object.entries(txByTime)) {
                const t = isNaN(Number(timeStr)) ? timeStr : Number(timeStr);
                const hasBuy = txs.some(tx => tx.type === 'BUY');
                const hasSell = txs.some(tx => tx.type === 'SELL');
                
                let color, shape, position;
                if (hasBuy && !hasSell) {
                    color = '#2ebd85'; shape = 'arrowUp'; position = 'belowBar';
                } else if (hasSell && !hasBuy) {
                    color = '#e0294a'; shape = 'arrowDown'; position = 'aboveBar';
                } else {
                    color = '#f39c12'; shape = 'circle'; position = 'inBar';
                }

                markers.push({
                    time: t,
                    position: position,
                    color: color,
                    shape: shape
                });
            }
            
            markers.sort((a, b) => {
                const ta = typeof a.time === 'string' ? new Date(a.time).getTime() : a.time;
                const tb = typeof b.time === 'string' ? new Date(b.time).getTime() : b.time;
                return ta - tb;
            });
            
            lineSeries.setMarkers(markers);
        }

        currentChart.subscribeCrosshairMove(param => {
            if (
                param.point === undefined ||
                !param.time ||
                param.point.x < 0 ||
                param.point.x > container.clientWidth ||
                param.point.y < 0 ||
                param.point.y > container.clientHeight
            ) {
                tooltip.style.display = 'none';
                return;
            }

            const matchedTxs = txByTime[param.time];
            if (matchedTxs && matchedTxs.length > 0) {
                let html = `<div style="font-weight:bold;margin-bottom:4px;border-bottom:1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'};padding-bottom:4px;">Transactions</div>`;
                matchedTxs.forEach(tx => {
                    const isBuy = tx.type === 'BUY';
                    const c = isBuy ? '#2ebd85' : '#e0294a';
                    const tName = isBuy ? 'Buy' : 'Sell';
                    html += `<div style="margin-top:4px;">
                        <span style="color:${c};font-weight:bold;">${tName}</span> 
                        ${tx.units} @ ${tx.price}
                    </div>`;
                });
                tooltip.innerHTML = html;
                tooltip.style.display = 'block';
                
                const y = param.point.y;
                let x = param.point.x + 15;
                if (x > container.clientWidth - 120) {
                    x = param.point.x - 130;
                }
                tooltip.style.left = x + 'px';
                tooltip.style.top = Math.max(10, y - 30) + 'px';
            } else {
                tooltip.style.display = 'none';
            }
        });

        currentChart.timeScale().fitContent();

        // Handle resize
        window.addEventListener('resize', () => {
            if (currentChart && container) {
                currentChart.applyOptions({ width: container.clientWidth });
            }
        });
    }

    async function loadAssetData(ticker, period = '1y') {
        currentTicker = ticker;
        currentPeriod = period;
        inputEl.value = ticker;
        dropdownEl.style.display = 'none';
        document.querySelectorAll('.analysis-range-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.range === period);
        });
        
        const originalPlaceholder = inputEl.placeholder;
        inputEl.placeholder = 'Loading data...';
        inputEl.disabled = true;

        // Hide favorites section and show content area first (so loader is visible)
        const favSection = document.getElementById('analysis-favorites-section');
        if (favSection) favSection.style.display = 'none';
        if (contentArea) contentArea.style.display = 'block';

        // Show loader
        const loader = document.getElementById('analysis-loader');
        if (loader) loader.style.display = 'flex';

        try {
            const params = new URLSearchParams({ ticker, period });
            if (currentPortfolioFilter && currentPortfolioFilter !== 'all') {
                params.set('portfolioId', currentPortfolioFilter);
            }
            const res = await fetch(`${_apiBase()}/asset-analysis?${params.toString()}`, {
                headers: getAuthHeaders()
            });
            
            if (!res.ok) throw new Error('Failed to fetch data');
            const data = await res.json();
            
            // Populate Fundamentals
            const f = data.fundamentals || {};
            document.getElementById('analysis-fund-sector').textContent = f.sector || '—';
            document.getElementById('analysis-fund-industry').textContent = f.industry || '—';
            document.getElementById('analysis-fund-mcap').textContent = formatLargeNumber(f.marketCap);
            document.getElementById('analysis-fund-pe').textContent = f.trailingPE ? f.trailingPE.toFixed(2) : '—';
            document.getElementById('analysis-fund-fwd-pe').textContent = f.forwardPE ? f.forwardPE.toFixed(2) : '—';
            document.getElementById('analysis-fund-div').textContent = formatPercent(f.dividendYield);
            document.getElementById('analysis-fund-high').textContent = formatCurrency(f.fiftyTwoWeekHigh);
            document.getElementById('analysis-fund-low').textContent = formatCurrency(f.fiftyTwoWeekLow);

            // Set Title
            const periodLabel = period.toUpperCase();
            document.getElementById('analysis-chart-title').textContent = `${f.longName || ticker} - Price History (${periodLabel})`;

            // Show and update favorite button
            updateFavoriteButton();
            
            renderChart(data.history || [], data.transactions || []);
            
            // Store and render financial data
            currentFinancialData = {
                cashflow: data.cashflow || {},
                financials: data.financials || {},
                earnings: data.earnings || []
            };
            
            renderFinancialTables();
            
            // Hide loader after chart is rendered
            if (loader) loader.style.display = 'none';
            
        } catch (e) {
            console.error('Asset analysis error:', e);
            
            // Hide loader on error
            if (loader) loader.style.display = 'none';
            
            alert('Failed to load asset data. Please try again.');
        } finally {
            inputEl.placeholder = originalPlaceholder;
            inputEl.disabled = false;
        }
    }

    function renderFinancialTables() {
        const { cashflow, financials } = currentFinancialData;
        
        // Show section if either dataset has data
        const section = document.getElementById('analysis-financials-section');
        const hasIncomeData = financials && (financials.annual || financials.quarterly);
        const hasCashflowData = cashflow && (cashflow.annual || cashflow.quarterly);
        
        if (hasIncomeData || hasCashflowData) {
            section.style.display = 'block';
            
            // If current type has no data, switch to the one that does
            if (currentStatementType === 'income' && !hasIncomeData && hasCashflowData) {
                currentStatementType = 'cashflow';
            } else if (currentStatementType === 'cashflow' && !hasCashflowData && hasIncomeData) {
                currentStatementType = 'income';
            }
            
            // Update tab states
            section.querySelectorAll('.analysis-statement-tab').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.type === currentStatementType);
            });
            
            renderFinancialTable();
        } else {
            section.style.display = 'none';
        }
    }

    function renderFinancialTable() {
        const table = document.getElementById('analysis-financials-table');
        if (!table) return;
        
        // Get data based on current statement type
        const data = currentStatementType === 'income' 
            ? currentFinancialData.financials 
            : currentFinancialData.cashflow;
        
        if (!data) {
            table.querySelector('tbody').innerHTML = '<tr><td colspan="100%" style="text-align:center;color:#888;">No data available</td></tr>';
            return;
        }
        
        const periodData = data[currentFinPeriod] || [];
        if (!periodData || periodData.length === 0) {
            table.querySelector('tbody').innerHTML = '<tr><td colspan="100%" style="text-align:center;color:#888;">No data available for this period</td></tr>';
            return;
        }
        
        // Get all unique metric names
        const metricNames = new Set();
        periodData.forEach(pd => {
            Object.keys(pd).forEach(key => {
                if (key !== 'date') metricNames.add(key);
            });
        });
        
        // Build table header with bar chart column
        const thead = table.querySelector('thead tr');
        thead.innerHTML = '<th>Metric</th>' + 
            periodData.map(pd => `<th>${pd.date}</th>`).join('') + 
            '<th style="min-width:150px;">Trend</th>';
        
        // Build table body with bar charts
        const tbody = table.querySelector('tbody');
        const rows = Array.from(metricNames).map(metric => {
            // Collect values for this metric
            const values = periodData.map(pd => pd[metric]);
            
            // Generate cells
            const cells = periodData.map(pd => {
                const val = pd[metric];
                if (val === null || val === undefined) return '<td style="color:#888;">—</td>';
                const formatted = formatLargeNumber(val);
                return `<td style="font-family:monospace;">${formatted}</td>`;
            });
            
            // Generate bar chart
            const chartCell = generateMetricBarChart(values);
            
            return `<tr>
                <td style="font-weight:600;color:var(--text);">${formatMetricName(metric)}</td>
                ${cells.join('')}
                ${chartCell}
            </tr>`;
        });
        
        tbody.innerHTML = rows.join('');
    }

    function generateMetricBarChart(values) {
        // Filter out null/undefined values for charting
        const numericValues = values.map(v => {
            const num = parseFloat(v);
            return isNaN(num) ? null : num;
        });
        
        // If all values are null, show empty
        if (numericValues.every(v => v === null)) {
            return '<td style="text-align:center;color:#888;">—</td>';
        }
        
        // Find min and max for scaling
        const validValues = numericValues.filter(v => v !== null);
        const min = Math.min(...validValues, 0); // Include 0 in range
        const max = Math.max(...validValues, 0);
        const range = max - min || 1;
        
        // Determine if we have negative values
        const hasNegative = min < 0;
        const zeroLinePercent = hasNegative ? Math.abs(min) / range * 100 : 0;
        
        // Generate bars
        const bars = numericValues.map((val, idx) => {
            if (val === null) {
                return '<div class="metric-bar-empty"></div>';
            }
            
            const isPositive = val >= 0;
            const absHeight = Math.abs(val - (hasNegative ? 0 : min)) / range * 100;
            const color = isPositive ? '#34d399' : '#f87171';
            
            // Position bar relative to zero line
            const bottom = hasNegative 
                ? (isPositive ? zeroLinePercent : zeroLinePercent - absHeight)
                : 0;
            
            return `<div class="metric-bar" style="height:${absHeight}%;bottom:${bottom}%;background:${color};\" title="${formatLargeNumber(val)}"></div>`;
        }).join('');
        
        return `<td><div class="metric-bar-chart" style="${hasNegative ? 'border-bottom: 1px solid rgba(100,116,139,0.3);' : ''}">${bars}</div></td>`;
    }

    const FIN_TOOLTIPS = {
        // Income Statement
        'Total Revenue': 'Revenue is the money a company brings in before costs. <strong class="metric-good">Good:</strong> it grows steadily over time. <strong class="metric-bad">Watch:</strong> if revenue climbs but profit does not, margins are weakening or costs are rising faster than sales.',
        'Operating Revenue': 'Revenue generated from the company\'s core operations, excluding unusual or one-off items. This is the clearest view of the core business engine.',
        'Net Income': 'Net income is the bottom line: revenue minus all costs, taxes, and interest. <strong class="metric-good">Good:</strong> positive and growing. <strong class="metric-bad">Important:</strong> if revenue is healthy but net income is weak or negative, the company may be spending too much relative to what it earns. This is the metric to watch when revenue looks fine but the business is not translating sales into profit.',
        'Gross Profit': 'Gross profit is revenue minus the direct cost of producing the product or service. It shows how much value remains before overhead costs. A stable or improving gross margin usually means stronger pricing power or lower production costs.',
        'Operating Income': 'Operating income is profit from normal business operations before interest and taxes. It connects revenue and costs: if revenue is rising but operating income is flat or falling, expenses are likely expanding faster than the business can absorb them.',
        'Ebitda': 'EBITDA is operating profit before interest, taxes, depreciation, and amortization. It is useful for comparing businesses across different capital structures and accounting methods, but it is not the same as true cash profit.',
        'Diluted Eps': 'Diluted earnings per share tells you how much profit belongs to each share after accounting for all potential shares. It helps you compare profit growth with the share count. If net income rises but diluted EPS is flat, dilution may be offsetting the benefit.',
        'Basic Eps': 'Basic EPS is net income divided by the current shares outstanding. It is easier to read than total profit, but it misses dilution from stock options or converts.',
        'Total Operating Expenses': 'This is the full cost of running the business, including COGS, SG&A, and R&D. If operating expenses rise faster than revenue, profit pressure appears in operating income and then net income.',
        'Selling General And Administration': 'SG&A covers overhead like sales, marketing, admin, and office costs. <strong class="metric-bad">Watch:</strong> if SG&A rises faster than revenue for several periods, margins can deteriorate even when sales stay strong.',
        'Research And Development': 'R&D is investment in future products and innovation. <strong class="metric-good">Good:</strong> consistent R&D can support long-term growth, but it is a cost today and should be judged against future returns and profit growth.',
        'Interest Expense': 'The cost of debt. High interest expense can eat into profit even when operating performance is solid. Compare this with operating income to see if leverage is becoming a risk.',
        'Interest Income': 'Income earned from cash deposits and short-term investments. It is a smaller signal for most companies than revenue, margin, or free cash flow.',
        'Tax Provision': 'Taxes owed during the period. It matters because lower taxes can lift earnings, but unusually low tax rates may not be sustainable or comparable across companies.',
        'Reconciled Depreciation': 'Depreciation is a non-cash accounting charge for ageing assets. It reduces reported earnings but not actual cash flow. This is why cash flow often looks healthier than net income.',
        'Reconciled Cost Of Revenue': 'This is the direct cost of providing the product or service. It is the first major bridge between revenue and gross profit: lower direct costs relative to revenue usually means a healthier margin.',
        'Total Expenses': 'All costs incurred in the period. Used together with revenue to see whether the business is generating a real profit or just growing sales while costs absorb most of it.',
        'Net Income Common Stockholders': 'Profit left for ordinary shareholders after preferred dividends. This is one of the cleanest ways to judge whether earnings are creating value for owners.',
        'Net Income Including Noncontrolling Interests': 'Profit after minority-interest ownership is accounted for. It helps you see the full earnings power of a company, not just the parent-company slice.',
        'Net Income Continuous Operations': 'Profit from continuing businesses, excluding discontinued or sold segments. This is useful when a company is restructuring or exiting a line of business.',
        // Cash Flow Statement
        'Operating Cash Flow': 'Cash generated from everyday business activity. This is often more trustworthy than net income because it strips out non-cash accounting effects. <strong class="metric-good">Good:</strong> it should be positive and ideally stronger than reported profit.',
        'Investing Cash Flow': 'Cash spent on or received from investments such as equipment, acquisitions, or asset sales. Negative numbers often reflect reinvestment; the key question is whether this is productive growth or unproductive spending.',
        'Financing Cash Flow': 'Cash raised from or returned to capital providers, including debt, share issuance, buybacks, and dividends. It helps explain how the company is funding itself and returning capital to owners.',
        'Free Cash Flow': 'Free cash flow is operating cash flow minus capital expenditure. This is the cash available after funding the business. <strong class="metric-good">Good:</strong> strong FCF helps support dividends, buybacks, debt paydown, and investment without needing more debt.',
        'Capital Expenditure': 'Cash spent on equipment, facilities, and other long-term assets. It is a sign of reinvestment, but excessive capex can strain cash flow if revenue does not keep pace.',
        'Cash Dividends Paid': 'Cash returned to shareholders as dividends. It is a sign of cash generation, but repeated large dividends with weak free cash flow can be a warning sign.',
        'Repurchase Of Capital Stock': 'Cash used to buy back shares. This can improve per-share metrics, but should be judged alongside free cash flow and debt. Buybacks are positive only when the business can afford them without taking on excess risk.',
        'Issuance Of Debt': 'New debt added during the period. It can fund expansion, but if it is large while free cash flow is weak, leverage is rising and risk is building.',
        'Repayment Of Debt': 'Debt paid down in the period. This strengthens the balance sheet, especially when done from strong cash generation instead of asset sales.',
        'Issuance Of Capital Stock': 'New shares issued to raise cash. This adds capital, but it dilutes existing shareholders and can pressure EPS if not offset by earnings growth.',
        'Stock Based Compensation': 'Compensation paid in equity rather than cash. It is a real cost, even though it is non-cash in accounting terms. It can dilute shareholders over time if issued at scale.',
        'Depreciation And Amortization': 'A non-cash charge that spreads the cost of assets over time. It reduces reported earnings but not cash, so it is often added back when looking at cash generation.',
        'Change In Working Capital': 'The change in short-term assets and liabilities. Negative values can mean the business is consuming cash as it grows, while positive values often release cash from operations.',
        'Changes In Account Receivables': 'Receivables grow when customers owe money but have not yet paid. Rising receivables can be healthy for growth, but if too high it can signal slowing collections or weak demand.',
        'Net Income From Continuing Operations': 'Profit from the business that is expected to continue. It helps separate sustainable earnings from one-off or discontinued operations.',
        'End Cash Position': 'Cash and equivalents held at the end of the period. This is the war chest for acquisitions, debt reduction, dividends, and resilience during downturns.',
        'Income Tax Paid Supplemental Data': 'Actual cash taxes paid. This helps reconcile book profit with true cash outflows and is useful when net income and operating cash flow are far apart.',
        'Interest Paid Supplemental Data': 'Actual cash interest paid. This matters because debt cost is not always obvious from accrual accounting and can become a real pressure point in downturns.',
        // Balance Sheet
        'Total Assets': 'Everything the company owns that has value: cash, inventory, property, brands, intellectual property, and investments. A growing asset base can be healthy if it is earning returns, but it should not be inflated by low-quality investments.',
        'Total Liabilities Net Minority Interest': 'All obligations owed to creditors, providers, and other stakeholders. <strong class="metric-good">Good:</strong> liabilities are manageable when the company generates enough cash and earnings to service them.',
        'Total Equity Gross Minority Interest': 'Equity is the value left for shareholders after liabilities are paid. Growing equity usually means retained earnings and a stronger capital base over time.',
        'Total Debt': 'Total debt includes both short-term and long-term borrowings. Use it with EBITDA and cash flow: a company can carry debt if it generates enough cash, but too much debt creates financial risk.',
        'Net Debt': 'Net debt is debt minus cash. <strong class="metric-good">Good:</strong> strong companies often have moderate or negative net debt. <strong class="metric-bad">Bad:</strong> high net debt can force the company to prioritize debt repayment over reinvestment or dividends.',
        'Working Capital': 'Working capital is current assets minus current liabilities. It shows whether the company can cover near-term obligations without stress. Strong positive working capital usually supports resilience.',
    };

    function formatMetricName(name) {
        // Convert camelCase to readable format
        const readable = name
            .replace(/([A-Z])/g, ' $1')
            .replace(/^./, str => str.toUpperCase())
            .trim();
            
        const tooltip = FIN_TOOLTIPS[readable] || FIN_TOOLTIPS[name];
        if (tooltip) {
            const escapedTooltip = tooltip.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
            return `<span class="metric-tooltip-container" style="color:inherit; font-weight:inherit;" onmouseenter="showFinTooltip(event, '${escapedTooltip}')" onmouseleave="hideFinTooltip()">${readable}</span>`;
        }
        // Generic fallback tooltip for any unrecognised metric
        const fallback = `Financial metric: <strong>${readable}</strong>. Values in billions (B), millions (M), or trillions (T). Positive values shown in green, negative in red in the Trend column.`;
        return `<span class="metric-tooltip-container" style="color:inherit; font-weight:inherit;" onmouseenter="showFinTooltip(event, '${fallback}')" onmouseleave="hideFinTooltip()">${readable}</span>`;
    }

    window.showFinTooltip = function(e, html) {
        let tt = document.getElementById('global-metric-tooltip');
        if (!tt) {
            tt = document.createElement('div');
            tt.id = 'global-metric-tooltip';
            tt.className = 'metric-tooltip global-metric-tooltip';
            document.body.appendChild(tt);
        }
        tt.innerHTML = html;
        tt.classList.add('show');
        
        const rect = e.target.getBoundingClientRect();
        let top = rect.top + window.scrollY - tt.offsetHeight - 8;
        let left = rect.left + window.scrollX;
        
        if (top < window.scrollY) top = rect.bottom + window.scrollY + 8;
        if (left + tt.offsetWidth > window.innerWidth + window.scrollX) left = window.innerWidth + window.scrollX - tt.offsetWidth - 8;
        if (left < window.scrollX) left = window.scrollX + 8;
        
        tt.style.top = top + 'px';
        tt.style.left = left + 'px';
    };

    window.hideFinTooltip = function() {
        const tt = document.getElementById('global-metric-tooltip');
        if (tt) tt.classList.remove('show');
    };

    function switchStatementType(type) {
        currentStatementType = type;
        
        // Update tab button states
        const section = document.getElementById('analysis-financials-section');
        if (section) {
            section.querySelectorAll('.analysis-statement-tab').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.type === type);
            });
        }
        
        // Re-render the table
        renderFinancialTable();
    }

    function switchFinPeriod(period) {
        currentFinPeriod = period;
        
        // Update tab button states
        const section = document.getElementById('analysis-financials-section');
        if (section) {
            section.querySelectorAll('.analysis-fin-tab').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.period === period);
            });
        }
        
        // Re-render the table
        renderFinancialTable();
    }

    function setRange(range) {
        if (!currentTicker) return;
        
        // Update active button state
        document.querySelectorAll('.analysis-range-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.range === range);
        });

        // Load data with new range
        loadAssetData(currentTicker, range);
    }

    function getAuthHeaders() {
        const token = window.AuthGuard ? window.AuthGuard.getIdToken() : null;
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    let _cachedOwnedAssets = null;

    function _updatePortfolioHint() {
        const hintEl = document.getElementById('analysis-portfolio-hint');
        const selectEl = document.getElementById('analysis-portfolio-filter');
        if (!hintEl || !selectEl) return;
        if (currentPortfolioFilter === 'all') {
            hintEl.textContent = 'Markers show transactions from all wallets.';
            return;
        }
        const selected = selectEl.options[selectEl.selectedIndex];
        const label = selected ? selected.textContent : 'selected wallet';
        hintEl.textContent = `Markers show transactions only from: ${label}.`;
    }

    async function _populatePortfolioFilter() {
        const selectEl = document.getElementById('analysis-portfolio-filter');
        if (!selectEl || selectEl.dataset.loaded === '1') return;

        selectEl.innerHTML = '<option value="all">All wallets</option>';
        try {
            if (window.PortfolioClient && typeof window.PortfolioClient.listPortfolios === 'function') {
                const data = await window.PortfolioClient.listPortfolios();
                const portfolios = (data && data.portfolios) || [];
                portfolios
                    .filter((p) => p && p.portfolioId && p.portfolioId !== 'summary')
                    .forEach((p) => {
                        const option = document.createElement('option');
                        option.value = p.portfolioId;
                        option.textContent = p.name || p.portfolioId;
                        selectEl.appendChild(option);
                    });
            }
        } catch (e) {
            console.warn('Analysis portfolio filter: failed to load portfolios', e);
        }
        selectEl.dataset.loaded = '1';
        if (![...selectEl.options].some((o) => o.value === currentPortfolioFilter)) {
            currentPortfolioFilter = 'all';
        }
        selectEl.value = currentPortfolioFilter;
        _updatePortfolioHint();
    }

    async function setPortfolioFilter(portfolioId, options = {}) {
        const { reload = true } = options;
        await _populatePortfolioFilter();
        const selectEl = document.getElementById('analysis-portfolio-filter');
        const normalized = portfolioId && portfolioId !== 'all' ? String(portfolioId) : 'all';
        if (selectEl && [...selectEl.options].some((o) => o.value === normalized)) {
            currentPortfolioFilter = normalized;
            selectEl.value = normalized;
        } else {
            currentPortfolioFilter = 'all';
            if (selectEl) selectEl.value = 'all';
        }
        _updatePortfolioHint();
        if (reload && currentTicker) {
            await loadAssetData(currentTicker, currentPeriod);
        }
    }

    function _renderSearchResults(results) {
        if (!results || results.length === 0) {
            dropdownEl.innerHTML = '<div class="mgmt-dropdown-item"><div class="mgmt-ticker-symbol">No results found</div></div>';
            dropdownEl.style.display = 'block';
            if (typeof selectedIndex !== 'undefined') selectedIndex = -1;
            return;
        }

        dropdownEl.innerHTML = '';
        if (typeof selectedIndex !== 'undefined') selectedIndex = -1;
        results.forEach((r, i) => {
            const item = document.createElement('div');
            item.className = 'mgmt-dropdown-item';
            if (r.isOwned) {
                item.className += ' is-owned';
            }
            item.onclick = () => loadAssetData(r.symbol, currentPeriod);
            
            const ownedBadge = r.isOwned 
                ? `<span class="mgmt-ticker-badge mgmt-ticker-badge-owned" style="margin-right:8px;" title="In your portfolio">✓ Owned</span>`
                : '';
            
            item.innerHTML = `
                <div class="mgmt-dropdown-main">
                    <span class="mgmt-ticker-symbol">${r.symbol}</span>
                    <span class="mgmt-ticker-name">${r.name || r.symbol}</span>
                </div>
                <div class="mgmt-ticker-meta">
                    ${ownedBadge}
                    <span class="mgmt-ticker-exchange">${r.exchange || ''}</span>
                </div>
            `;
            dropdownEl.appendChild(item);
        });
        dropdownEl.style.display = 'block';
    }

    async function performSearch(query) {
        const q = String(query || '').trim();

        // If query is empty and we have cached owned assets, display them instantly
        if (!q && _cachedOwnedAssets) {
            _renderSearchResults(_cachedOwnedAssets);
        }

        try {
            const res = await fetch(`${_apiBase()}/search?q=${encodeURIComponent(q)}`, {
                headers: getAuthHeaders()
            });
            const data = await res.json();
            const results = data.results || [];
            if (!q) {
                _cachedOwnedAssets = results;
            }
            _renderSearchResults(results);
        } catch (e) {
            console.error('Search failed', e);
        }
    }

    if (inputEl) {
        inputEl.addEventListener('input', (e) => {
            const val = e.target.value.trim();
            clearTimeout(searchTimeout);
            if (!val) {
                performSearch('');
            } else {
                searchTimeout = setTimeout(() => {
                    performSearch(val);
                }, 300);
            }
        });

        const showOwnedAssetsOnFocus = (e) => {
            if (e.target && typeof e.target.select === 'function') {
                e.target.select();
            }
            performSearch('');
        };

        inputEl.addEventListener('focus', showOwnedAssetsOnFocus);
        inputEl.addEventListener('click', showOwnedAssetsOnFocus);

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!inputEl.contains(e.target) && !dropdownEl.contains(e.target)) {
                dropdownEl.style.display = 'none';
            }
        });

        let selectedIndex = -1;
        inputEl.addEventListener('keydown', (e) => {
            const items = dropdownEl.querySelectorAll('.mgmt-dropdown-item');
            if (!items.length || dropdownEl.style.display === 'none') return;
            
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectedIndex = (selectedIndex + 1) % items.length;
                items.forEach((item, i) => item.classList.toggle('selected', i === selectedIndex));
                items[selectedIndex].scrollIntoView({ block: 'nearest' });
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIndex = (selectedIndex - 1 + items.length) % items.length;
                items.forEach((item, i) => item.classList.toggle('selected', i === selectedIndex));
                items[selectedIndex].scrollIntoView({ block: 'nearest' });
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (selectedIndex >= 0 && selectedIndex < items.length) {
                    items[selectedIndex].click();
                } else {
                    // if they press enter without selecting, pick the first one
                    items[0].click();
                }
            }
        });
    }

    const portfolioFilterEl = document.getElementById('analysis-portfolio-filter');
    if (portfolioFilterEl) {
        portfolioFilterEl.addEventListener('change', async (event) => {
            const nextPortfolioId = String(event.target.value || 'all');
            await setPortfolioFilter(nextPortfolioId, { reload: true });
        });
        _populatePortfolioFilter();
    }

    // Update favorite button state
    function updateFavoriteButton() {
        const btn = document.getElementById('analysis-favorite-btn');
        if (!btn || !currentTicker) return;
        
        const isFav = isFavorite(currentTicker);
        btn.style.display = 'flex';
        btn.classList.toggle('is-favorite', isFav);
        btn.title = isFav ? 'Remove from favorites' : 'Add to favorites';
    }

    // Toggle favorite
    async function toggleFavorite() {
        if (!currentTicker) return;
        
        const name = document.getElementById('analysis-chart-title').textContent.split(' - ')[0];
        
        if (isFavorite(currentTicker)) {
            await removeFromFavorites(currentTicker);
        } else {
            await addToFavorites(currentTicker, name);
        }
    }

    // Generate sparkline SVG
    function generateSparkline(bars, width = 120, height = 30, forceUp = null) {
        if (!bars || bars.length === 0) return '';
        
        const values = bars.map(b => Array.isArray(b) ? b[1] : b);
        const min = Math.min(...values);
        const max = Math.max(...values);
        const range = max - min || 1;
        
        const isUp = forceUp !== null ? forceUp : (values[values.length - 1] >= values[0]);
        const color = isUp ? '#34d399' : '#f87171';
        
        const points = values.map((val, i) => {
            const x = (i / (values.length - 1)) * width;
            const y = height - ((val - min) / range) * height;
            return `${x},${y}`;
        }).join(' ');
        
        return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" style="display:block;">
            <polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>`;
    }

    // Fetch sparkline data for a ticker
    async function fetchSparklineData(ticker) {
        // Check localStorage cache first
        const cache = getSparklineCache();
        if (cache[ticker] && cache[ticker].expiresAt > Date.now()) {
            return cache[ticker];
        }
        
        try {
            const res = await fetch(`${_apiBase()}/asset-analysis?ticker=${encodeURIComponent(ticker)}&period=1y`, {
                headers: getAuthHeaders()
            });
            
            if (!res.ok) throw new Error('Failed to fetch');
            const data = await res.json();
            
            const history = data.history || [];
            const bars = history.map(h => h.c);
            
            // Calculate returns
            const latestPrice = bars[bars.length - 1] || 0;
            const dayAgo = bars[bars.length - 2] || latestPrice;
            const weekAgo = bars[bars.length - 6] || latestPrice;
            const monthAgo = bars[bars.length - 22] || latestPrice;
            const yearAgo = bars[0] || latestPrice;
            
            const result = {
                bars: bars,
                returns: {
                    '1d': ((latestPrice - dayAgo) / dayAgo * 100).toFixed(2),
                    '1w': ((latestPrice - weekAgo) / weekAgo * 100).toFixed(2),
                    '1m': ((latestPrice - monthAgo) / monthAgo * 100).toFixed(2),
                    '1y': ((latestPrice - yearAgo) / yearAgo * 100).toFixed(2)
                }
            };
            
            // Save to localStorage cache
            saveSparklineCache(ticker, result);
            return result;
            return result;
        } catch (e) {
            console.error(`Failed to fetch sparkline for ${ticker}:`, e);
            return null;
        }
    }

    // Render favorites list
    async function renderFavoritesList() {
        const favorites = await getFavorites();
        const listEl = document.getElementById('analysis-favorites-list');
        const emptyEl = document.getElementById('analysis-favorites-empty');
        const countEl = document.getElementById('analysis-favorites-count');
        
        if (!listEl) return;
        
        // Update count
        if (countEl) {
            countEl.textContent = favorites.length > 0 ? `(${favorites.length})` : '';
        }
        
        if (favorites.length === 0) {
            listEl.innerHTML = '';
            if (emptyEl) emptyEl.style.display = 'flex';
            return;
        }
        
        if (emptyEl) emptyEl.style.display = 'none';
        
        // Render loading state - compact one-liner design like today's movers
        listEl.innerHTML = favorites.map(fav => `
            <article class="analysis-fav-row" data-ticker="${fav.ticker}">
                <div class="analysis-fav-info">
                    <div class="analysis-fav-name-block">
                        <span class="analysis-fav-name">${fav.name}</span>
                        <span class="analysis-fav-ticker">${fav.ticker}</span>
                    </div>
                    <div class="analysis-fav-sparkline">
                        <span class="analysis-fav-sparkline-loader">⟳</span>
                    </div>
                </div>
                <div class="analysis-fav-metrics">
                    <div class="analysis-fav-returns">
                        <span class="analysis-fav-return-badge"><span class="label">1D</span><span class="value">—</span></span>
                        <span class="analysis-fav-return-badge"><span class="label">1W</span><span class="value">—</span></span>
                        <span class="analysis-fav-return-badge"><span class="label">1M</span><span class="value">—</span></span>
                        <span class="analysis-fav-return-badge"><span class="label">1Y</span><span class="value">—</span></span>
                    </div>
                    <button class="analysis-fav-remove" onclick="event.stopPropagation(); window._analysis.removeFromFavorites('${fav.ticker}')" title="Remove">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>
            </article>
        `).join('');
        
        // Make rows clickable
        listEl.querySelectorAll('.analysis-fav-row').forEach(row => {
            const ticker = row.dataset.ticker;
            row.addEventListener('click', (e) => {
                if (!e.target.closest('.analysis-fav-remove')) {
                    loadAssetData(ticker, '1y');
                }
            });
        });
        
        // Fetch sparkline data for each favorite
        for (const fav of favorites) {
            const data = await fetchSparklineData(fav.ticker);
            if (!data) continue;
            
            const rowEl = listEl.querySelector(`[data-ticker="${fav.ticker}"]`);
            if (!rowEl) continue;
            
            // Determine if price is up or down for sparkline color
            const returns1Y = parseFloat(data.returns['1y'] || '0');
            const isUp = returns1Y >= 0;
            
            // Update sparkline
            const sparklineContainer = rowEl.querySelector('.analysis-fav-sparkline');
            if (sparklineContainer && data.bars.length > 0) {
                sparklineContainer.innerHTML = generateSparkline(data.bars, 150, 40, isUp);
            }
            
            // Update returns
            const returnsEl = rowEl.querySelector('.analysis-fav-returns');
            if (returnsEl && data.returns) {
                returnsEl.innerHTML = Object.entries(data.returns).map(([period, value]) => {
                    const num = parseFloat(value);
                    const sign = num >= 0 ? '+' : '';
                    const color = num >= 0 ? '#34d399' : '#f87171';
                    return `<span class="analysis-fav-return-badge">
                        <span class="label">${period.toUpperCase()}</span>
                        <span class="value" style="color:${color};text-shadow:0 0 8px currentColor;">${sign}${value}%</span>
                    </span>`;
                }).join('');
            }
        }
    }

    // Initialize display state
    if (contentArea) {
        contentArea.style.display = 'none';
    }

    // Initialize favorites list on load
    function toggleVolume() {
        showVolume = !showVolume;
        const btn = document.getElementById('analysis-volume-toggle');
        if (btn) btn.classList.toggle('active', showVolume);
        if (currentTicker) loadAssetData(currentTicker, currentPeriod);
    }

    function toggleMA(key) {
        showMA[key] = !showMA[key];
        const btn = document.getElementById(`analysis-${key}-toggle`);
        if (btn) btn.classList.toggle('active', showMA[key]);
        if (currentTicker) loadAssetData(currentTicker, currentPeriod);
    }

    function toggleMACD() {
        showMACD = !showMACD;
        const btn = document.getElementById('analysis-macd-toggle');
        if (btn) btn.classList.toggle('active', showMACD);
        if (currentTicker) loadAssetData(currentTicker, currentPeriod);
    }

    window.addEventListener('roastfolio:themechange', () => {
        if (currentTicker) loadAssetData(currentTicker, currentPeriod);
    });

    renderFavoritesList();

    window._analysis = {
        loadAssetData,
        setRange,
        setPortfolioFilter,
        switchStatementType,
        switchFinPeriod,
        toggleFavorite,
        toggleVolume,
        toggleMA,
        toggleMACD,
        removeFromFavorites,
        showFavorites: () => {
            const favSection = document.getElementById('analysis-favorites-section');
            if (favSection) favSection.style.display = 'block';
            if (contentArea) contentArea.style.display = 'none';
            const btn = document.getElementById('analysis-favorite-btn');
            if (btn) btn.style.display = 'none';
            renderFavoritesList();
        }
    };

    // Global helper to switch to analysis tab and load a ticker
    window.openAnalysisForTicker = function(ticker, options = {}) {
        if (!ticker) return;
        const portfolioId = options && options.portfolioId ? String(options.portfolioId) : 'all';
        // Switch to analysis tab
        if (typeof showTab === 'function') {
            showTab('analysis');
        }
        // Wait a moment for tab to render, then load the ticker
        setTimeout(async () => {
            if (window._analysis && window._analysis.loadAssetData) {
                if (window._analysis.setPortfolioFilter) {
                    await window._analysis.setPortfolioFilter(portfolioId, { reload: false });
                }
                window._analysis.loadAssetData(ticker, '5y');
            }
        }, 100);
    };
})();
