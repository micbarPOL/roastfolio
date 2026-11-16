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

  async function _fetch(path, options = {}, retries = 2) {
    const isGet = (!options.method || options.method === 'GET');
    
    if (isGet && _fetchPromises[path]) {
      return _fetchPromises[path];
    }

    const promise = (async () => {
      const headers = await _authHeaders();
      const url = `${_apiBase()}${path}`;
      let lastErr;
      for (let attempt = 0; attempt <= (isGet ? retries : 0); attempt++) {
        try {
          const res = await fetch(url, { ...options, headers: { ...headers, ...(options.headers || {}) } });
          if (!res.ok) {
            // On transient 5xx server errors for GET requests, retry with exponential backoff
            if (isGet && res.status >= 500 && res.status <= 504 && attempt < retries) {
              await new Promise(r => setTimeout(r, 200 * Math.pow(2, attempt)));
              continue;
            }
            const body = await res.json().catch(() => ({}));
            const err = new Error(body.error || `HTTP ${res.status}`);
            err.status = res.status;
            throw err;
          }
          return await res.json();
        } catch (err) {
          lastErr = err;
          if (isGet && attempt < retries && (!err.status || (err.status >= 500 && err.status <= 504))) {
            await new Promise(r => setTimeout(r, 200 * Math.pow(2, attempt)));
            continue;
          }
          throw err;
        }
      }
      throw lastErr;
    })();

    if (isGet) {
      _fetchPromises[path] = promise;
      // Clean up cache shortly after it settles to allow fresh fetches later
      promise.finally(() => {
        setTimeout(() => { delete _fetchPromises[path]; }, 100);
      }).catch(() => {});
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

    /**
     * Get daily underwater-lakes metrics for a portfolio.
     * Expected payload shape from API:
     * [{ date, value, hwm, drawdown, lake_id }, ...]
     */
    getDrawdownLakes(portfolioId) {
      return _fetch(`/portfolios/${encodeURIComponent(portfolioId)}/drawdown-lakes`);
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

    _benchmarkReturnsCache: new Map(),

    /**
     * Get stored monthly returns for a benchmark.
     * benchmarkId: e.g. 'WIG' (defaults to user's primary benchmark on server)
     * from: 'YYYY-MM' earliest month to include (default '2020-01')
     */
    getBenchmarkReturns(benchmarkId, from) {
      const bid = String(benchmarkId || '').trim().toUpperCase() || 'WIG';
      const key = `${bid}::${from || ''}`;
      if (this._benchmarkReturnsCache && this._benchmarkReturnsCache.has(key)) {
        return this._benchmarkReturnsCache.get(key);
      }
      const params = new URLSearchParams();
      if (bid) params.set('benchmarkId', bid);
      if (from) params.set('from', from);
      const qs = params.toString();
      const promise = _fetch(`/benchmark-returns${qs ? '?' + qs : ''}`).catch(err => {
        console.warn(`[portfolios] getBenchmarkReturns fallback for ${bid}:`, err.message || err);
        return { benchmarkId: bid, returns: [] };
      });
      if (!this._benchmarkReturnsCache) this._benchmarkReturnsCache = new Map();
      this._benchmarkReturnsCache.set(key, promise);
      return promise;
    },

    /**
     * Get up to 10 years of daily close data for a benchmark or custom ticker.
     * Pass either benchmarkId (e.g. 'SP500') or ticker (e.g. 'AAPL').
     * Response: { id, name, daily: [{t: "YYYY-MM-DD", c: number}] }
     */
    getBenchmarkDaily(benchmarkIdOrTicker, isCustomTicker = false) {
      const params = new URLSearchParams();
      if (isCustomTicker) {
        params.set('ticker', benchmarkIdOrTicker);
      } else {
        params.set('benchmarkId', benchmarkIdOrTicker);
      }
      return _fetch(`/benchmark-daily?${params.toString()}`);
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

  // ── Shared ISIN ↔ Ticker Lookup & Normalization Helper ───────────────
  const _ISIN_DIRECTORY = {
    PLOPTTC00011: { symbol: 'CDR.WA',  name: 'CD Projekt S.A.',                    exchange: 'WSE',    type: 'Equity' },
    PLXTRDM00011: { symbol: 'XTB.WA',  name: 'XTB S.A.',                           exchange: 'WSE',    type: 'Equity' },
    PLKGHM000017: { symbol: 'KGH.WA',  name: 'KGHM Polska Miedź S.A.',             exchange: 'WSE',    type: 'Equity' },
    PLPKN0000018: { symbol: 'PKN.WA',  name: 'ORLEN S.A.',                         exchange: 'WSE',    type: 'Equity' },
    PLPKO0000016: { symbol: 'PKO.WA',  name: 'PKO Bank Polski S.A.',               exchange: 'WSE',    type: 'Equity' },
    PLPZU0000011: { symbol: 'PZU.WA',  name: 'PZU S.A.',                           exchange: 'WSE',    type: 'Equity' },
    PLPEKAO00016: { symbol: 'PEO.WA',  name: 'Bank Pekao S.A.',                    exchange: 'WSE',    type: 'Equity' },
    PLDINPL00011: { symbol: 'DNP.WA',  name: 'Dino Polska S.A.',                   exchange: 'WSE',    type: 'Equity' },
    PLLPP0000011: { symbol: 'LPP.WA',  name: 'LPP S.A.',                           exchange: 'WSE',    type: 'Equity' },
    LU2237380790: { symbol: 'ALE.WA',  name: 'Allegro.eu S.A.',                    exchange: 'WSE',    type: 'Equity' },
    NL0015000AU7: { symbol: 'PCO.WA',  name: 'Pepco Group N.V.',                   exchange: 'WSE',    type: 'Equity' },
    PLALIOR00045: { symbol: 'ALR.WA',  name: 'Alior Bank S.A.',                    exchange: 'WSE',    type: 'Equity' },
    PLKRK0000010: { symbol: 'KRU.WA',  name: 'KRUK S.A.',                          exchange: 'WSE',    type: 'Equity' },
    PLBZ00000044: { symbol: 'SPL.WA',  name: 'Santander Bank Polska S.A.',         exchange: 'WSE',    type: 'Equity' },
    PLMBANK00012: { symbol: 'MBK.WA',  name: 'mBank S.A.',                         exchange: 'WSE',    type: 'Equity' },
    PLBUDMX00013: { symbol: 'BDX.WA',  name: 'Budimex S.A.',                       exchange: 'WSE',    type: 'Equity' },
    PLSOFTB00016: { symbol: 'ACP.WA',  name: 'Asseco Poland S.A.',                 exchange: 'WSE',    type: 'Equity' },
    PLPGER000010: { symbol: 'PGE.WA',  name: 'PGE S.A.',                           exchange: 'WSE',    type: 'Equity' },
    PLTLKPL00017: { symbol: 'OPL.WA',  name: 'Orange Polska S.A.',                 exchange: 'WSE',    type: 'Equity' },
    PLCYFR000011: { symbol: 'CPS.WA',  name: 'Cyfrowy Polsat S.A.',                exchange: 'WSE',    type: 'Equity' },
    PLJSW0000015: { symbol: 'JSW.WA',  name: 'Jastrzębska Spółka Węglowa S.A.',    exchange: 'WSE',    type: 'Equity' },
    PLTAURN00011: { symbol: 'TPE.WA',  name: 'TAURON Polska Energia S.A.',         exchange: 'WSE',    type: 'Equity' },
    PLENEA000013: { symbol: 'ENA.WA',  name: 'Enea S.A.',                          exchange: 'WSE',    type: 'Equity' },
    PLENERG00022: { symbol: 'ENG.WA',  name: 'Energa S.A.',                        exchange: 'WSE',    type: 'Equity' },
    PLKETY000011: { symbol: 'KTY.WA',  name: 'Grupa Kęty S.A.',                    exchange: 'WSE',    type: 'Equity' },
    PLINTCS00010: { symbol: 'CAR.WA',  name: 'Inter Cars S.A.',                    exchange: 'WSE',    type: 'Equity' },
    PLBENEF00018: { symbol: 'BFT.WA',  name: 'Benefit Systems S.A.',               exchange: 'WSE',    type: 'Equity' },
    PLCCC0000016: { symbol: 'CCC.WA',  name: 'CCC S.A.',                           exchange: 'WSE',    type: 'Equity' },
    PL11BTS00015: { symbol: '11B.WA',  name: '11 bit studios S.A.',                exchange: 'WSE',    type: 'Equity' },
    PLMOBRK00013: { symbol: 'MBR.WA',  name: 'Mo-BRUK S.A.',                       exchange: 'WSE',    type: 'Equity' },
    PLRNBWT00031: { symbol: 'RBW.WA',  name: 'Rainbow Tours S.A.',                 exchange: 'WSE',    type: 'Equity' },
    PLCRTCH00018: { symbol: 'CRI.WA',  name: 'Creotech Instruments S.A.',          exchange: 'WSE',    type: 'Equity' },
    PLARTFX00018: { symbol: 'ART.WA',  name: 'Artifex Mundi S.A.',                 exchange: 'WSE',    type: 'Equity' },
    PLCNTSL00014: { symbol: 'COG.WA',  name: 'Cognor Holding S.A.',                exchange: 'WSE',    type: 'Equity' },
    PLMSTSD00019: { symbol: 'PXM.WA',  name: 'Polimex Mostostal S.A.',             exchange: 'WSE',    type: 'Equity' },
    PLGPW0000017: { symbol: 'GPW.WA',  name: 'GPW S.A.',                           exchange: 'WSE',    type: 'Equity' },
    PLBSK0000017: { symbol: 'ING.WA',  name: 'ING Bank Śląski S.A.',               exchange: 'WSE',    type: 'Equity' },
    PLBIG0000016: { symbol: 'MIL.WA',  name: 'Bank Millennium S.A.',               exchange: 'WSE',    type: 'Equity' },
    PLBGZ0000010: { symbol: 'BNP.WA',  name: 'BNP Paribas Bank Polska S.A.',       exchange: 'WSE',    type: 'Equity' },
    PLBH00000012: { symbol: 'BHW.WA',  name: 'Bank Handlowy w Warszawie S.A.',     exchange: 'WSE',    type: 'Equity' },
    PLDOMDV00010: { symbol: 'DOM.WA',  name: 'Dom Development S.A.',               exchange: 'WSE',    type: 'Equity' },
    PLLCCRP00017: { symbol: 'DVL.WA',  name: 'Develia S.A.',                       exchange: 'WSE',    type: 'Equity' },
    PLATAL000046: { symbol: '1AT.WA',  name: 'Atal S.A.',                          exchange: 'WSE',    type: 'Equity' },
    PLLVTSF00010: { symbol: 'TXT.WA',  name: 'Text S.A.',                          exchange: 'WSE',    type: 'Equity' },
    PLWRTPL00027: { symbol: 'WPL.WA',  name: 'Wirtualna Polska Holding S.A.',      exchange: 'WSE',    type: 'Equity' },
    PLSNKTK00019: { symbol: 'SNT.WA',  name: 'Synektik S.A.',                      exchange: 'WSE',    type: 'Equity' },
    PLSLVCR00029: { symbol: 'SLV.WA',  name: 'Selvita S.A.',                       exchange: 'WSE',    type: 'Equity' },
    PLSELVA00018: { symbol: 'RVU.WA',  name: 'Ryvu Therapeutics S.A.',             exchange: 'WSE',    type: 'Equity' },
    PLCLNPH00015: { symbol: 'CLN.WA',  name: 'Celon Pharma S.A.',                  exchange: 'WSE',    type: 'Equity' },
    PLTSQGM00016: { symbol: 'TEN.WA',  name: 'Ten Square Games S.A.',              exchange: 'WSE',    type: 'Equity' },
    PLPLAYW00015: { symbol: 'PLW.WA',  name: 'PlayWay S.A.',                       exchange: 'WSE',    type: 'Equity' },
    PLCTINT00018: { symbol: 'CIG.WA',  name: 'CI Games S.E.',                      exchange: 'WSE',    type: 'Equity' },
    US44853H1086: { symbol: 'HUG.WA',  name: 'Huuuge, Inc.',                       exchange: 'WSE',    type: 'Equity' },
    LU2910446546: { symbol: 'ZAB.WA',  name: 'Żabka Group S.A.',                   exchange: 'WSE',    type: 'Equity' },
    PLDIAG000014: { symbol: 'DIA.WA',  name: 'Diagnostyka S.A.',                   exchange: 'WSE',    type: 'Equity' },
    US0378331005: { symbol: 'AAPL',    name: 'Apple Inc.',                         exchange: 'NASDAQ', type: 'Equity' },
    US5949181045: { symbol: 'MSFT',    name: 'Microsoft Corp.',                    exchange: 'NASDAQ', type: 'Equity' },
    US67066G1040: { symbol: 'NVDA',    name: 'NVIDIA Corp.',                       exchange: 'NASDAQ', type: 'Equity' },
    US02079K3059: { symbol: 'GOOGL',   name: 'Alphabet Inc.',                      exchange: 'NASDAQ', type: 'Equity' },
    US0231351067: { symbol: 'AMZN',    name: 'Amazon.com, Inc.',                   exchange: 'NASDAQ', type: 'Equity' },
    US30303M1027: { symbol: 'META',    name: 'Meta Platforms, Inc.',               exchange: 'NASDAQ', type: 'Equity' },
    US88160R1014: { symbol: 'TSLA',    name: 'Tesla, Inc.',                        exchange: 'NASDAQ', type: 'Equity' },
    US0846707026: { symbol: 'BRK-B',   name: 'Berkshire Hathaway Inc.',            exchange: 'NYSE',   type: 'Equity' },
    IE00B4L5Y983: { symbol: 'IWDA.AS', name: 'iShares Core MSCI World UCITS ETF',  exchange: 'AMS',    type: 'ETF'    },
    IE00BK5BQT80: { symbol: 'VWCE.DE', name: 'Vanguard FTSE All-World UCITS ETF',  exchange: 'XETRA',  type: 'ETF'    },
    IE00B5BMR087: { symbol: 'CSPX.L',  name: 'iShares Core S&P 500 UCITS ETF',     exchange: 'LSE',    type: 'ETF'    },
  };

  const _SYMBOL_TO_ISIN = {};
  Object.entries(_ISIN_DIRECTORY).forEach(([isin, entry]) => {
    const sym = entry.symbol.toUpperCase();
    _SYMBOL_TO_ISIN[sym] = isin;
    if (sym.endsWith('.WA')) {
      const base = sym.slice(0, -3);
      if (!_SYMBOL_TO_ISIN[base]) _SYMBOL_TO_ISIN[base] = isin;
    }
  });

  function normalizeIsin(raw) {
    const cleaned = String(raw || '')
      .trim()
      .replace(/^(?:ISIN[:\s\-]*)/i, '')
      .replace(/[\s\-]+/g, '')
      .toUpperCase();
    return /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(cleaned) ? cleaned : '';
  }

  function compactQuery(raw) {
    return String(raw || '')
      .trim()
      .replace(/^(?:ISIN[:\s\-]*)/i, '')
      .replace(/[\s\-]+/g, '')
      .toUpperCase();
  }

  function getIsinForSymbol(symbol) {
    const sym = String(symbol || '').trim().toUpperCase();
    if (!sym) return '';
    return _SYMBOL_TO_ISIN[sym] || (sym.endsWith('.WA') ? (_SYMBOL_TO_ISIN[sym.slice(0, -3)] || '') : '');
  }

  function getEntryByIsin(raw) {
    const isin = normalizeIsin(raw);
    if (!isin || !_ISIN_DIRECTORY[isin]) return null;
    return { ..._ISIN_DIRECTORY[isin], isin };
  }

  function searchDirectoryByIsin(raw) {
    const compact = compactQuery(raw);
    if (compact.length < 4 || !/^[A-Z]{2}[A-Z0-9]{2,10}$/.test(compact)) return [];
    const exact = _ISIN_DIRECTORY[compact];
    if (exact) return [{ ...exact, isin: compact }];
    const matches = [];
    Object.entries(_ISIN_DIRECTORY).forEach(([isin, entry]) => {
      if (isin.includes(compact)) {
        matches.push({ ...entry, isin });
      }
    });
    return matches;
  }

  function enrichResults(results, rawQuery) {
    const isinQuery = normalizeIsin(rawQuery);
    const list = Array.isArray(results) ? results.map(r => {
      const isin = r.isin || getIsinForSymbol(r.symbol) || (isinQuery || '');
      const dirEntry = isin && _ISIN_DIRECTORY[isin];
      const isSyntheticName = /^[A-Z0-9.\-]+\s+C\.XWAR\s+[A-Z]{3}$/i.test(String(r.name || '').trim());
      return {
        ...r,
        name: (isSyntheticName && dirEntry ? dirEntry.name : r.name) || r.symbol,
        ...(isin ? { isin } : {}),
      };
    }) : [];

    // Ensure directory ISIN matches appear even if backend omitted them
    const dirMatches = searchDirectoryByIsin(rawQuery);
    const seen = new Set(list.map(r => String(r.symbol || '').toUpperCase()));
    dirMatches.forEach(m => {
      if (!seen.has(m.symbol.toUpperCase())) {
        list.push(m);
        seen.add(m.symbol.toUpperCase());
      }
    });
    return list;
  }

  window.RoastfolioIsin = {
    directory: _ISIN_DIRECTORY,
    normalizeIsin,
    compactQuery,
    getIsinForSymbol,
    getEntryByIsin,
    searchDirectoryByIsin,
    enrichResults,
  };
})();
