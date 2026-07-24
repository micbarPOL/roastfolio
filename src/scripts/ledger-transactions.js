(() => {
    const LEDGER_TX_LIMIT = 1000;
    const BACKFILL_WALLETS = new Set(['IKE', 'IKZE', 'XTB', 'Schwab', 'Binance']);
    const OP_LABELS = {
        BUY: 'Buy',
        SELL: 'Sell',
        DEPOSIT: 'Deposit',
        WITHDRAWAL: 'Withdrawal',
        DIVIDEND: 'Dividend',
        SPINOFF: 'Spin-off',
        EXTRA_COST: 'Extra Cost',
    };

    let _rows = [];
    let _loaded = false;
    let _loadPromise = null;
    let _migrationAttempted = false;

    function normalizeNumber(value, fallback = 0) {
        const num = Number(value);
        return Number.isFinite(num) ? num : fallback;
    }

    function rowSignature(row) {
        return [
            row.date || '',
            row.wallet || '',
            row.operation || '',
            row.asset || '',
            normalizeNumber(row.units).toFixed(6),
            normalizeNumber(row.price).toFixed(6),
            normalizeNumber(row.commission).toFixed(2),
            normalizeNumber(row.tax).toFixed(2),
            normalizeNumber(row.value).toFixed(2),
        ].join('|');
    }

    function assetLabel(tx) {
        const type = String(tx.type || '').toUpperCase();
        if (['DEPOSIT', 'WITHDRAWAL', 'EXTRA_COST'].includes(type)) return 'Cash';
        const ticker = String(tx.ticker || '').replace(/\.WA$/, '').trim();
        const name = String(tx.name || '').trim();
        if (name && ticker && !name.includes(ticker)) return `${name} (${ticker})`;
        return name || ticker || 'Unknown';
    }

    function valueForType(tx) {
        const raw = Math.abs(normalizeNumber(tx.value));
        const type = String(tx.type || '').toUpperCase();
        if (['BUY', 'WITHDRAWAL', 'EXTRA_COST'].includes(type)) return -raw;
        if (type === 'SPINOFF') return 0;
        return raw;
    }

    function unitsForType(tx) {
        const raw = Math.abs(normalizeNumber(tx.quantity));
        const type = String(tx.type || '').toUpperCase();
        if (type === 'SELL') return -raw;
        if (['BUY', 'DIVIDEND', 'SPINOFF'].includes(type)) return raw;
        return 0;
    }

    function mapTransaction(tx, portfolio) {
        const type = String(tx.type || '').toUpperCase();
        const wallet = String(portfolio?.name || portfolio?.portfolioId || '').trim() || 'Wallet';
        const row = {
            transactionId: String(tx.transactionId || ''),
            portfolioId: String(tx.portfolioId || portfolio?.portfolioId || ''),
            holdingId: String(tx.holdingId || ''),
            type,
            date: String(tx.transactionDate || tx.date || '').slice(0, 10),
            wallet,
            operation: OP_LABELS[type] || type || 'Transaction',
            asset: assetLabel(tx),
            name: String(tx.name || '').trim(),
            ticker: String(tx.ticker || '').trim(),
            currency: String(tx.currency || 'PLN'),
            units: unitsForType(tx),
            price: normalizeNumber(tx.price),
            commission: normalizeNumber(tx.commission),
            tax: normalizeNumber(tx.tax),
            value: valueForType(tx),
            automatic: Boolean(tx.automatic),
        };
        return { ...row, _signature: rowSignature(row) };
    }

    async function fetchRows() {
        if (typeof PortfolioClient === 'undefined' || typeof PortfolioClient.listPortfolios !== 'function') {
            return { rows: [], emptyWallets: [] };
        }
        const list = await PortfolioClient.listPortfolios();
        const portfolios = Array.isArray(list?.portfolios) ? list.portfolios : [];
        const realPortfolios = portfolios.filter(portfolio => {
            const id = String(portfolio.portfolioId || '').toLowerCase();
            const name = String(portfolio.name || '').toLowerCase();
            return id && id !== 'summary' && name !== 'summary';
        });
        const emptyWallets = [];
        const nested = await Promise.all(realPortfolios.map(async portfolio => {
            const data = await PortfolioClient.listTransactions(portfolio.portfolioId, LEDGER_TX_LIMIT);
            const rows = Array.isArray(data?.transactions) ? data.transactions : [];
            if (!rows.length) emptyWallets.push(String(portfolio.name || portfolio.portfolioId || 'wallet'));
            return rows.map(tx => mapTransaction(tx, portfolio));
        }));
        const rows = nested.flat().sort((a, b) => {
            const byDate = String(b.date || '').localeCompare(String(a.date || ''));
            if (byDate !== 0) return byDate;
            return normalizeNumber(b.value) - normalizeNumber(a.value);
        });
        return { rows, emptyWallets };
    }

    function publish(rows) {
        _rows = rows;
        window.dispatchEvent(new CustomEvent('ledgerTransactionsUpdated', { detail: { rows } }));
        return rows;
    }

    function shouldAttemptBackfill(rows, emptyWallets) {
        if (!rows.length) return true;
        return emptyWallets.some(wallet => BACKFILL_WALLETS.has(String(wallet || '').trim().toUpperCase()));
    }

    const LedgerTransactions = {
        getRows() {
            return _rows.slice();
        },

        async loadRows({ force = false, attemptMigration = true } = {}) {
            if (_loaded && !force) return _rows;
            if (_loadPromise && !force) return _loadPromise;
            _loadPromise = (async () => {
                let { rows, emptyWallets } = await fetchRows();
                const backfillWallets = emptyWallets.filter(wallet => BACKFILL_WALLETS.has(String(wallet || '').trim().toUpperCase()));
                if (shouldAttemptBackfill(rows, emptyWallets) && attemptMigration && !_migrationAttempted && typeof PortfolioClient?.migrate === 'function') {
                    _migrationAttempted = true;
                    console.log('[LedgerTransactions] Missing history for wallets:', backfillWallets.length ? backfillWallets : emptyWallets);
                    try {
                        await PortfolioClient.migrate();
                        ({ rows } = await fetchRows());
                    } catch (error) {
                        console.warn('[LedgerTransactions] Backfill migration failed; using currently available live rows.', error);
                    }
                }
                _loaded = true;
                return publish(rows);
            })();
            try {
                return await _loadPromise;
            } finally {
                _loadPromise = null;
            }
        },
    };

    window.LedgerTransactions = LedgerTransactions;

    window.addEventListener('portfolioTransactionSaved', () => {
        LedgerTransactions.loadRows({ force: true, attemptMigration: false }).catch(error => {
            console.warn('Failed to refresh live transactions after save:', error);
        });
    });
})();
