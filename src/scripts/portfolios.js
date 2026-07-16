/**
 * portfolios.js — Browser client for the /portfolios and /migrate API.
 *
 * Requires:
 *   - config.js loaded first (window.APP_CONFIG.apiUrl)
 *   - auth-guard.js loaded first (AuthGuard.getIdToken)
 *
 * Exposes: window.PortfolioClient
 */

(() => {
  function _apiBase() {
    const cfg = window.__CONFIG__ || window.APP_CONFIG || {};
    return (cfg.apiUrl || '').replace(/\/prices$/, '');
  }

  async function _authHeaders() {
    const token = AuthGuard.getIdToken();
    return {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${token}`,
    };
  }

  const _fetchPromises = {};

  async function _fetch(path, options = {}) {
    const isGet = (!options.method || options.method === 'GET');
    
    if (isGet && _fetchPromises[path]) {
      return _fetchPromises[path];
    }

    const promise = (async () => {
      const headers = await _authHeaders();
      const url = `${_apiBase()}${path}`;
      const res = await fetch(url, { ...options, headers: { ...headers, ...(options.headers || {}) } });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const err = new Error(body.error || `HTTP ${res.status}`);
        err.status = res.status;
        throw err;
      }
      return res.json();
    })();

    if (isGet) {
      _fetchPromises[path] = promise;
      // Clean up cache shortly after it settles to allow fresh fetches later
      promise.finally(() => {
        setTimeout(() => { delete _fetchPromises[path]; }, 100);
      });
    }

    return promise;
  }

  const PortfolioClient = {

    /** List all portfolios for the current user. */
    listPortfolios() {
      return _fetch('/portfolios');
    },

    /** Get a single portfolio with its holdings. */
    getPortfolio(portfolioId) {
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}`);
    },

    /** Create or update a portfolio. body: { name, type?, currency?, order? } */
    putPortfolio(body) {
      return _fetch('/portfolios', {
        method: 'PUT',
        body:   JSON.stringify(body),
      });
    },

    /** Delete a portfolio and all its holdings. */
    deletePortfolio(portfolioId) {
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}`, { method: 'DELETE' });
    },

    /** List holdings for a portfolio. */
    listHoldings(portfolioId) {
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}/holdings`);
    },

    /** List transactions for a portfolio. */
    listTransactions(portfolioId, limit) {
      const qs = Number.isFinite(Number(limit)) ? `?limit=${encodeURIComponent(limit)}` : '';
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}/transactions${qs}`);
    },

    /** List daily snapshots for a portfolio. */
    listSnapshots(portfolioId) {
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}/snapshots`);
    },

    /** Get the current ATH state for a portfolio. */
    getAth(portfolioId) {
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}/ath`);
    },

    /** Set manual ATH or switch back to AUTO with { athSource: 'AUTO' }. */
    updateAth(portfolioId, body) {
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}/ath`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
    },

    /**
     * Create or update a holding.
     * body: { name, ticker, currency, units, purchaseValue }
     */
    putHolding(portfolioId, body) {
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}/holdings`, {
        method: 'PUT',
        body:   JSON.stringify(body),
      });
    },

    /** Record a BUY/SELL transaction. */
    addTransaction(portfolioId, body) {
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}/transactions`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
    },

    /** Update a ledger transaction and trigger server-side history recalculation. */
    updateTransaction(portfolioId, transactionId, body) {
      return _fetch(
        `/portfolios/${encodeURIComponent(portfolioId)}/transactions/${encodeURIComponent(transactionId)}`,
        {
          method: 'PUT',
          body: JSON.stringify(body),
        }
      );
    },

    /**
     * Recalculate historical snapshots from a given date.
     * Call after inserting a transaction with a historical transactionDate.
     * fromDate: 'YYYY-MM-DD'
     */
    recalculateSnapshots(portfolioId, fromDate) {
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}/snapshots/recalculate`, {
        method: 'POST',
        body: JSON.stringify({ fromDate }),
      });
    },

    /**
     * Get stored monthly returns for a benchmark.
     * benchmarkId: e.g. 'WIG' (defaults to user's primary benchmark on server)
     * from: 'YYYY-MM' earliest month to include (default '2020-01')
     */
    getBenchmarkReturns(benchmarkId, from) {
      const params = new URLSearchParams();
      if (benchmarkId) params.set('benchmarkId', benchmarkId);
      if (from) params.set('from', from);
      const qs = params.toString();
      return _fetch(`/benchmark-returns${qs ? '?' + qs : ''}`);
    },

    /** Delete a holding by holdingId (URL-safe name slug). */
    deleteHolding(portfolioId, holdingId) {
      return _fetch(
        `/portfolios/${encodeURIComponent(portfolioId)}/holdings/${encodeURIComponent(holdingId)}`,
        { method: 'DELETE' }
      );
    },

    /**
     * Trigger the one-shot CSV → DynamoDB migration.
     * Safe to call multiple times (idempotent).
     */
    migrate() {
      return _fetch('/migrate', { method: 'POST' });
    },

    /**
     * Ensure the user's portfolios are seeded.
     * Calls /migrate if no portfolios exist yet.
     * Returns true if migration was triggered, false if already seeded.
     */
    async ensureSeeded() {
      try {
        const { portfolios } = await PortfolioClient.listPortfolios();
        if (portfolios && portfolios.length > 0) {
          return false; // already seeded
        }
        console.log('[PortfolioClient] No portfolios found — running migration...');
        const result = await PortfolioClient.migrate();
        console.log('[PortfolioClient] Migration complete', result);
        return true;
      } catch (e) {
        // 403 = migration disabled in this environment (dev) — not an error
        if (e.status === 403) {
          console.log('[PortfolioClient] Migration disabled in this environment — skipping seed');
          return false;
        }
        console.warn('[PortfolioClient] ensureSeeded error (non-fatal):', e);
        return false;
      }
    },
  };

  window.PortfolioClient = PortfolioClient;
})();
