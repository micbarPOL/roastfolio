/* xp-engine.js — Roastfolio XP & Achievement Computation Engine
 *
 * Derives XP, level, streaks, badge progress, and monthly recap
 * entirely from real transaction and portfolio snapshot data.
 *
 * Data sources (all optional — engine degrades gracefully):
 *   LedgerTransactions.getRows()  transaction history
 *   window.PORTFOLIO_DATA         daily snapshots  [{ date, value, investment }]
 *   window.PORTFOLIO_TOTAL_VALUE  current total PLN
 *   window.PORTFOLIO_ATH          { athValue, athDate } or null
 *   window.WALLET_HOLDINGS        holdings map
 *
 * Dispatches: window CustomEvent 'xpEngineReady' after each compute().
 * Exposes:    window.XPEngine.getResult()  → full achievement data object
 *             window.XPEngine.compute()    → trigger re-computation
 *
 * XP rules are documented in the user guide (guide.html #ds-xp-rules).
 */
(function () {
    'use strict';

    // ═══════════════════════════════════════════════════════════
    // CONSTANTS
    // ═══════════════════════════════════════════════════════════

    // Monthly deposit goal (PLN) — user-configurable via localStorage key 'xpe_deposit_goal'
    var DEPOSIT_GOAL = Number(localStorage.getItem('xpe_deposit_goal') || 1000);

    // XP rules: every number here appears in the guide table
    var XP = {
        DEPOSIT_BASE:       15,   // per deposit event
        DEPOSIT_500:         5,   // bonus: amount ≥ 500 PLN
        DEPOSIT_1K:         15,   // bonus: amount ≥ 1 000 PLN (replaces 500 bonus)
        DEPOSIT_5K:         30,   // bonus: amount ≥ 5 000 PLN (replaces 1K)
        DEPOSIT_10K:        60,   // bonus: amount ≥ 10 000 PLN (replaces 5K)
        CONSISTENCY_MONTH:  20,   // per calendar month with ≥1 deposit
        GOAL_MONTH:         10,   // bonus per month with deposits ≥ DEPOSIT_GOAL
        DIVIDEND:           15,   // per dividend received
        FIRST_SELL:         20,   // first sell transaction ever
        PER_SELL:            5,   // each additional sell
        MILESTONE_1K:       50,   // portfolio ≥ 1 000 PLN reached
        MILESTONE_10K:     100,   // portfolio ≥ 10 000 PLN reached
        MILESTONE_50K:     200,   // portfolio ≥ 50 000 PLN reached
        MILESTONE_100K:    400,   // portfolio ≥ 100 000 PLN reached
        MILESTONE_250K:    600,   // portfolio ≥ 250 000 PLN reached
        MILESTONE_500K:   1000,   // portfolio ≥ 500 000 PLN reached
        DIVERSE_3:          30,   // 3+ unique tickers bought
        DIVERSE_5:          50,   // 5+ unique tickers bought (cumulative with _3)
        DIVERSE_10:         80,   // 10+ unique tickers bought (cumulative)
        RETIREMENT:         50,   // retirement plan configured
    };

    // Level thresholds (cumulative XP)
    var LEVELS = [
        { name: 'Seed',        xp:      0 },
        { name: 'Observer',    xp:    100 },
        { name: 'Participant', xp:    250 },
        { name: 'Saver',       xp:    500 },
        { name: 'Contributor', xp:   1000 },
        { name: 'Operator',    xp:   2500 },
        { name: 'Veteran',     xp:   5000 },
        { name: 'Institution', xp:  10000 },
    ];

    // Streak colour palette (matches achievements.js)
    var STREAK_COLORS = {
        contribution:   '#27ae60',
        checkin:        '#2b88cf',
        withdrawal:     '#8a4fff',
        goal:           '#d4ac2a',
        green:          '#4caf82',
        beat_benchmark: '#e06b1f',  // orange — outperformance
    };

    // ── Cached result ──────────────────────────────────────────
    var _result = null;

    // ── Snapshot history cache (replaces window.PORTFOLIO_DATA for streak calcs) ──
    // window.PORTFOLIO_DATA is current holdings, NOT snapshot history.
    // We fetch real daily snapshots via PortfolioClient.listSnapshots('summary').
    var _snapshotHistory = null;   // [{date, value, investment}] sorted asc
    var _snapshotLoading = false;

    function _loadSnapshotHistory() {
        if (_snapshotHistory !== null) return;
        if (_snapshotLoading) return;
        if (!window.PortfolioClient || !window.PortfolioClient.listSnapshots) return;
        _snapshotLoading = true;
        window.PortfolioClient.listSnapshots('summary')
            .then(function(data) {
                _snapshotLoading = false;
                _snapshotHistory = ((data && data.snapshots) ? data.snapshots : [])
                    .map(function(s) {
                        return {
                            date:       String(s.snapshotDate || '').slice(0, 10),
                            value:      Number(s.portfolioValue || 0),
                            investment: Number(s.investmentValue || 0),
                        };
                    })
                    .filter(function(s) { return s.date; })
                    .sort(function(a, b) { return a.date.localeCompare(b.date); });
                compute();  // re-run with real snapshot data
            })
            .catch(function() {
                _snapshotLoading = false;
                _snapshotHistory = [];  // treat as empty on error, don't retry
            });
    }

    // ── Benchmark returns cache ────────────────────────────────
    // {YYYY-MM: returnPct_as_number} for the user's primary benchmark
    var _benchmarkReturns = null;   // null = not yet loaded; {} = loaded (may be empty)
    var _benchmarkReturnsId = null; // which benchmarkId was loaded
    var _benchmarkLoading = false;

    function _loadBenchmarkReturns() {
        if (_benchmarkReturns !== null) return;
        if (_benchmarkLoading) return;
        if (!window.PortfolioClient || !window.PortfolioClient.getBenchmarkReturns) return;
        _benchmarkLoading = true;
        var bid = window.BENCHMARK_ID || 'WIG';
        window.PortfolioClient.getBenchmarkReturns(bid, '2010-01')
            .then(function(data) {
                _benchmarkLoading = false;
                _benchmarkReturnsId = (data && data.benchmarkId) || bid;
                var arr = (data && data.returns) || [];
                _benchmarkReturns = {};
                arr.forEach(function(r) {
                    if (r.month) _benchmarkReturns[r.month] = Number(r.returnPct || 0);
                });
                compute();  // re-run with benchmark data
            })
            .catch(function() {
                _benchmarkLoading = false;
                _benchmarkReturns = {};
            });
    }

    // ═══════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════

    function today() {
        return new Date().toISOString().slice(0, 10);
    }

    function toYM(dateStr) {
        return String(dateStr || '').slice(0, 7); // YYYY-MM
    }

    function monthsBetween(fromYM, toYM_) {
        if (!fromYM || !toYM_) return 0;
        var f = fromYM.split('-').map(Number);
        var t = toYM_.split('-').map(Number);
        return Math.max(0, (t[0] - f[0]) * 12 + (t[1] - f[1]));
    }

    function fmtPLN(n) {
        return Number(n).toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' PLN';
    }

    // Walk backwards through a sorted (asc) array of YYYY-MM strings
    // and count how many consecutive ending-months are present.
    function consecutiveTailCount(sortedMonths) {
        if (!sortedMonths.length) return 0;
        var set = new Set(sortedMonths);
        // Find the most recent month present
        var last = sortedMonths[sortedMonths.length - 1];
        var parts = last.split('-').map(Number);
        var count = 0;
        while (set.has(parts[0] + '-' + String(parts[1]).padStart(2, '0'))) {
            count++;
            parts[1]--;
            if (parts[1] < 1) { parts[1] = 12; parts[0]--; }
        }
        return count;
    }

    // Scan the full sorted YYYY-MM array and return the longest consecutive run ever.
    // Unlike consecutiveTailCount (which only measures the current trailing run),
    // this finds the historical best — e.g. a 7-month streak in 2023 followed by a
    // gap and then a 2-month current streak returns 7, not 2.
    function longestConsecutiveRun(sortedMonths) {
        if (!sortedMonths.length) return 0;
        var best = 1, run = 1;
        for (var i = 1; i < sortedMonths.length; i++) {
            // Check if sortedMonths[i] is exactly one month after sortedMonths[i-1]
            var prev = sortedMonths[i - 1].split('-').map(Number);
            var curr = sortedMonths[i].split('-').map(Number);
            var nextY = prev[0], nextM = prev[1] + 1;
            if (nextM > 12) { nextM = 1; nextY++; }
            if (curr[0] === nextY && curr[1] === nextM) {
                run++;
                if (run > best) best = run;
            } else {
                run = 1;
            }
        }
        return best;
    }

    function resolveLevel(totalXP) {
        var level = LEVELS[0];
        for (var i = LEVELS.length - 1; i >= 0; i--) {
            if (totalXP >= LEVELS[i].xp) { level = LEVELS[i]; break; }
        }
        var idx  = LEVELS.indexOf(level);
        var next = LEVELS[idx + 1] || LEVELS[LEVELS.length - 1];
        return {
            name:    level.name,
            nextName:next.name,
            current: totalXP,
            prevAt:  level.xp,
            nextAt:  next.xp,
        };
    }

    // ═══════════════════════════════════════════════════════════
    // CORE COMPUTATION
    // ═══════════════════════════════════════════════════════════

    function compute() {
        var rows      = (typeof LedgerTransactions !== 'undefined' && LedgerTransactions.getRows)
                        ? LedgerTransactions.getRows()
                        : [];
        // Use real snapshot history; kick off load if not yet available.
        _loadSnapshotHistory();
        _loadBenchmarkReturns();
        var snapshots = _snapshotHistory || [];
        var totalVal  = Number(window.PORTFOLIO_TOTAL_VALUE || 0);
        var athInfo   = window.PORTFOLIO_ATH || null;
        var todayStr  = today();

        // ── Partition transactions ─────────────────────────────
        var deposits     = rows.filter(function(r) { return r.operation === 'Deposit'; });
        var withdrawals  = rows.filter(function(r) { return r.operation === 'Withdrawal'; });
        var sells        = rows.filter(function(r) { return r.operation === 'Sell'; });
        var dividends    = rows.filter(function(r) { return r.operation === 'Dividend'; });
        var buys         = rows.filter(function(r) { return r.operation === 'Buy'; });

        // ── Unique tickers (from buys, excluding cash) ─────────
        var uniqueTickers = new Set(
            buys.map(function(r) { return r.asset; })
                .filter(function(a) { return a && a !== 'Gotówka' && a !== 'Cash'; })
        );

        // ── Historical max portfolio value (from snapshots) ────
        var maxHistoricalValue = totalVal;
        snapshots.forEach(function(s) {
            if (Number(s.value) > maxHistoricalValue) maxHistoricalValue = Number(s.value);
        });
        // Also consider ATH record
        if (athInfo && athInfo.athValue && Number(athInfo.athValue) > maxHistoricalValue) {
            maxHistoricalValue = Number(athInfo.athValue);
        }

        // ── Deposit months (for streak and consistency) ────────
        var depositMonths = deposits
            .map(function(r) { return toYM(r.date); })
            .filter(Boolean);
        var depositMonthsSorted = Array.from(new Set(depositMonths)).sort();

        // ── Goal months (deposits ≥ DEPOSIT_GOAL in a calendar month) ─
        var depositByMonth = {};
        deposits.forEach(function(r) {
            var m = toYM(r.date);
            if (m) depositByMonth[m] = (depositByMonth[m] || 0) + Math.abs(Number(r.value || 0));
        });
        var goalMonths = Object.keys(depositByMonth)
            .filter(function(m) { return depositByMonth[m] >= DEPOSIT_GOAL; })
            .sort();

        // ── Green months (from snapshots) ──────────────────────
        var greenMonths = [];
        if (snapshots.length > 1) {
            var byMonth = {};
            snapshots.forEach(function(s) {
                var m = toYM(s.date);
                if (!m) return;
                if (!byMonth[m]) byMonth[m] = { first: s, last: s };
                else byMonth[m].last = s; // snapshots sorted asc — last in month = end-of-month
            });
            var sortedSnapshotMonths = Object.keys(byMonth).sort();
            for (var i = 1; i < sortedSnapshotMonths.length; i++) {
                var m = sortedSnapshotMonths[i];
                var prev = byMonth[sortedSnapshotMonths[i - 1]];
                var curr = byMonth[m];
                var netReturn = (Number(curr.last.value) - Number(prev.last.value))
                              - (Number(curr.last.investment || 0) - Number(prev.last.investment || 0));
                if (netReturn > 0) greenMonths.push(m);
            }
        }
        var greenMonthsSorted = greenMonths.sort();

        // ── Beat-benchmark months ──────────────────────────────────────────
        // For each month: compare portfolio net return vs benchmark return.
        // Net return excludes deposits/withdrawals so we measure manager skill,
        // not capital injection.
        var bm = _benchmarkReturns || {};
        var beatBenchmarkMonths = [];
        if (snapshots.length > 1 && Object.keys(bm).length > 0) {
            var byMonSnap = {};
            snapshots.forEach(function(s) {
                var m = toYM(s.date);
                if (m) byMonSnap[m] = s; // last row per month wins (asc sort)
            });
            var sortedSnapMonths = Object.keys(byMonSnap).sort();
            for (var si = 1; si < sortedSnapMonths.length; si++) {
                var sm = sortedSnapMonths[si];
                var sp = sortedSnapMonths[si - 1];
                if (!(sm in bm)) continue;  // no benchmark data for this month
                var currS = byMonSnap[sm];
                var prevS = byMonSnap[sp];
                var prevVal = Number(prevS.value);
                if (!prevVal) continue;
                // Modified Dietz: weights cash flows at mid-month (standard monthly attribution)
                // gain = ΔValue − net_cash_flows
                // return = gain / (opening_value + net_cash_flows × 0.5)
                var netFlow    = Number(currS.investment || 0) - Number(prevS.investment || 0);
                var gain       = (Number(currS.value) - prevVal) - netFlow;
                var dietzDenom = prevVal + netFlow * 0.5;
                if (dietzDenom <= 0) continue;
                var portNetRet = gain / dietzDenom * 100;
                if (portNetRet > bm[sm]) beatBenchmarkMonths.push(sm);
            }
        }
        var beatBenchmarkSorted = beatBenchmarkMonths.sort();
        var beatBenchmarkStreak = consecutiveTailCount(beatBenchmarkSorted);

        // ── Withdrawal-free streak ─────────────────────────────
        var lastWithdrawalDate = withdrawals.length
            ? withdrawals.sort(function(a, b) { return b.date.localeCompare(a.date); })[0].date
            : null;
        var firstDepositDate = deposits.length
            ? deposits.sort(function(a, b) { return a.date.localeCompare(b.date); })[0].date
            : null;

        var withdrawalFreeFromYM  = lastWithdrawalDate ? toYM(lastWithdrawalDate) : toYM(firstDepositDate || todayStr);
        var withdrawalFreeMonths  = monthsBetween(withdrawalFreeFromYM, toYM(todayStr));

        // ── Streak best values (from localStorage cache or current) ──
        function bestStreak(id, current) {
            var key = 'xpe_best_' + id;
            var stored = Number(localStorage.getItem(key) || 0);
            var best   = Math.max(stored, current);
            if (best > stored) localStorage.setItem(key, best);
            return best;
        }

        var depositStreakVal   = consecutiveTailCount(depositMonthsSorted);
        var goalStreakVal      = consecutiveTailCount(goalMonths);
        var greenStreakVal     = consecutiveTailCount(greenMonthsSorted);

        // Start month of each current streak (first month of the current consecutive run)
        function streakStartMonth(sortedMonths, streakLen) {
            if (!streakLen || !sortedMonths.length) return null;
            return sortedMonths[sortedMonths.length - streakLen];
        }
        var depositStreakStart    = streakStartMonth(depositMonthsSorted, depositStreakVal);
        var goalStreakStart       = streakStartMonth(goalMonths, goalStreakVal);
        var greenStreakStart      = streakStartMonth(greenMonthsSorted, greenStreakVal);
        var beatBenchmarkStart   = streakStartMonth(beatBenchmarkSorted, beatBenchmarkStreak);

        // Check-in streak: count distinct transaction-date days (proxy)
        var distinctDays = Array.from(new Set(rows.map(function(r) { return r.date; }).filter(Boolean))).sort();
        var checkinVal   = distinctDays.length; // total distinct active days (not consecutive — a proxy)

        var streaks = [
            {
                id: 'contribution', name: 'Deposit streak',
                value: depositStreakVal, unit: 'mo', color: STREAK_COLORS.contribution,
                best: bestStreak('contribution', depositStreakVal),
                nextMilestone: depositStreakVal < 3 ? 3 : depositStreakVal < 6 ? 6 : depositStreakVal < 12 ? 12 : depositStreakVal < 24 ? 24 : 36,
                nextLabel: 'next: ' + (depositStreakVal < 3 ? 3 : depositStreakVal < 6 ? 6 : depositStreakVal < 12 ? 12 : depositStreakVal < 24 ? 24 : 36) + ' mo',
                hint: 'Consecutive months with at least one deposit',
                startMonth: depositStreakStart,
                keepGoingHint: 'Make at least 1 deposit this month to keep it going',
            },
            {
                id: 'checkin', name: 'Active days',
                value: checkinVal, unit: 'days', color: STREAK_COLORS.checkin,
                best: bestStreak('checkin', checkinVal),
                nextMilestone: checkinVal < 10 ? 10 : checkinVal < 30 ? 30 : checkinVal < 90 ? 90 : checkinVal < 180 ? 180 : 365,
                nextLabel: 'next: ' + (checkinVal < 10 ? 10 : checkinVal < 30 ? 30 : checkinVal < 90 ? 90 : checkinVal < 180 ? 180 : 365) + ' days',
                hint: 'Distinct days with any portfolio activity',
                startMonth: null,
                keepGoingHint: 'Log any portfolio activity today',
            },
            {
                id: 'withdrawal', name: 'Withdrawal-free',
                value: withdrawalFreeMonths, unit: 'mo', color: STREAK_COLORS.withdrawal,
                best: bestStreak('withdrawal', withdrawalFreeMonths),
                nextMilestone: withdrawalFreeMonths < 6 ? 6 : withdrawalFreeMonths < 12 ? 12 : withdrawalFreeMonths < 24 ? 24 : withdrawalFreeMonths < 36 ? 36 : 60,
                nextLabel: 'next: ' + (withdrawalFreeMonths < 6 ? 6 : withdrawalFreeMonths < 12 ? 12 : withdrawalFreeMonths < 24 ? 24 : withdrawalFreeMonths < 36 ? 36 : 60) + ' mo',
                hint: 'Months since the last withdrawal (or since first deposit)',
                startMonth: withdrawalFreeFromYM,
                keepGoingHint: 'Don\'t make any withdrawals this month',
            },
            {
                id: 'goal', name: 'Goal streak',
                value: goalStreakVal, unit: 'mo', color: STREAK_COLORS.goal,
                best: bestStreak('goal', goalStreakVal),
                nextMilestone: goalStreakVal < 3 ? 3 : goalStreakVal < 6 ? 6 : goalStreakVal < 12 ? 12 : 24,
                nextLabel: 'goal: ' + DEPOSIT_GOAL.toLocaleString('pl-PL') + ' PLN/mo',
                hint: 'Consecutive months with deposits ≥ ' + DEPOSIT_GOAL + ' PLN',
                startMonth: goalStreakStart,
                keepGoingHint: 'Deposit at least ' + DEPOSIT_GOAL.toLocaleString('pl-PL') + ' PLN this month',
            },
            {
                id: 'green', name: 'Green months',
                value: greenStreakVal, unit: 'mo', color: STREAK_COLORS.green,
                best: bestStreak('green', greenStreakVal),
                nextMilestone: greenStreakVal < 3 ? 3 : greenStreakVal < 6 ? 6 : greenStreakVal < 12 ? 12 : 24,
                nextLabel: 'next: ' + (greenStreakVal < 3 ? 3 : greenStreakVal < 6 ? 6 : greenStreakVal < 12 ? 12 : 24) + ' mo',
                hint: 'Consecutive months with positive net portfolio return',
                startMonth: greenStreakStart,
                keepGoingHint: 'Portfolio needs to end the month higher than it started (net of deposits)',
            },
            {
                id: 'beat_benchmark',
                name: 'Beat ' + (_benchmarkReturnsId || window.BENCHMARK_NAME || 'benchmark'),
                value: beatBenchmarkStreak, unit: 'mo', color: STREAK_COLORS.beat_benchmark,
                // Use longestConsecutiveRun to find the all-time best run across ALL
                // historical months — not just the current tail. bestStreak() only
                // persists the current tail to localStorage and misses gaps in history
                // (e.g. a 7-month run in 2023 followed by a gap shows as best=2).
                best: longestConsecutiveRun(beatBenchmarkSorted),
                nextMilestone: beatBenchmarkStreak < 3 ? 3 : beatBenchmarkStreak < 6 ? 6 : beatBenchmarkStreak < 12 ? 12 : 24,
                nextLabel: 'next: ' + (beatBenchmarkStreak < 3 ? 3 : beatBenchmarkStreak < 6 ? 6 : beatBenchmarkStreak < 12 ? 12 : 24) + ' mo',
                hint: 'Consecutive months where your net portfolio return exceeded '
                      + (_benchmarkReturnsId || window.BENCHMARK_NAME || 'the benchmark'),
                startMonth: beatBenchmarkStart,
                keepGoingHint: 'Your net portfolio return must beat '
                    + (_benchmarkReturnsId || window.BENCHMARK_NAME || 'the benchmark')
                    + ' this month',
            },
        ];

        // ═══════════════════════════════════════════════════════
        // XP CALCULATION
        // ═══════════════════════════════════════════════════════
        var totalXP = 0;
        var xpBreakdown = [];

        function add(amount, label) {
            if (amount <= 0) return;
            totalXP += amount;
            xpBreakdown.push({ amount: amount, label: label });
        }

        // 1. Deposit events
        deposits.forEach(function(d) {
            var amt = Math.abs(Number(d.value || 0));
            add(XP.DEPOSIT_BASE, 'Deposit');
            if      (amt >= 10000) add(XP.DEPOSIT_10K, 'Deposit ≥ 10 000 PLN bonus');
            else if (amt >= 5000)  add(XP.DEPOSIT_5K,  'Deposit ≥ 5 000 PLN bonus');
            else if (amt >= 1000)  add(XP.DEPOSIT_1K,  'Deposit ≥ 1 000 PLN bonus');
            else if (amt >= 500)   add(XP.DEPOSIT_500, 'Deposit ≥ 500 PLN bonus');
        });

        // 2. Monthly consistency
        depositMonthsSorted.forEach(function(m) {
            add(XP.CONSISTENCY_MONTH, 'Monthly deposit (' + m + ')');
        });

        // 3. Goal months
        goalMonths.forEach(function(m) {
            add(XP.GOAL_MONTH, 'Goal met (' + m + ')');
        });

        // 4. Dividends
        dividends.forEach(function() {
            add(XP.DIVIDEND, 'Dividend received');
        });

        // 5. Sell transactions
        if (sells.length > 0) {
            add(XP.FIRST_SELL, 'First sell transaction');
            if (sells.length > 1) add((sells.length - 1) * XP.PER_SELL, (sells.length - 1) + ' sell transactions');
        }

        // 6. Portfolio milestones (cumulative — every crossed threshold earns its own XP)
        var peakForMilestones = maxHistoricalValue;
        if (peakForMilestones >= 1000)    add(XP.MILESTONE_1K,   'Portfolio reached 1 000 PLN');
        if (peakForMilestones >= 10000)   add(XP.MILESTONE_10K,  'Portfolio reached 10 000 PLN');
        if (peakForMilestones >= 50000)   add(XP.MILESTONE_50K,  'Portfolio reached 50 000 PLN');
        if (peakForMilestones >= 100000)  add(XP.MILESTONE_100K, 'Portfolio reached 100 000 PLN');
        if (peakForMilestones >= 250000)  add(XP.MILESTONE_250K, 'Portfolio reached 250 000 PLN');
        if (peakForMilestones >= 500000)  add(XP.MILESTONE_500K, 'Portfolio reached 500 000 PLN');

        // 7. Diversification
        var tc = uniqueTickers.size;
        if (tc >= 10) { add(XP.DIVERSE_3 + XP.DIVERSE_5 + XP.DIVERSE_10, '10+ unique holdings'); }
        else if (tc >= 5)  { add(XP.DIVERSE_3 + XP.DIVERSE_5, '5+ unique holdings'); }
        else if (tc >= 3)  { add(XP.DIVERSE_3, '3+ unique holdings'); }

        // 8. Retirement plan (flag persisted in localStorage until full async check)
        var hasRetirementPlan = localStorage.getItem('xpe_retirement') === '1';
        if (hasRetirementPlan) add(XP.RETIREMENT, 'Retirement plan configured');

        // FIRE target (cached from retirement plans API, used for FIRE milestones + badge)
        var fireTarget = Number(localStorage.getItem('xpe_fire_target') || 0);
        var firePct    = (fireTarget > 0 && totalVal > 0) ? Math.min(100, (totalVal / fireTarget) * 100) : 0;

        // Async: check if retirement plans exist; cache plan count + fire target for next run
        if (typeof RetirementPlansClient !== 'undefined' && RetirementPlansClient.listPlans) {
            RetirementPlansClient.listPlans()
                .then(function(res) {
                    var plans = Array.isArray(res) ? res : (res && res.plans ? res.plans : []);
                    var hasPlan = plans.length > 0;
                    localStorage.setItem('xpe_retirement', hasPlan ? '1' : '0');
                    if (hasPlan) {
                        // Use most-recently-updated plan as primary for FIRE target
                        var primary = plans[0];
                        var ft = 0;
                        var ls = (primary.latestSummary || {});
                        if (ls.retirementPortfolioValue && ls.retirementPortfolioValue > 0) {
                            ft = ls.retirementPortfolioValue;
                        } else if (primary.monthlyRetirementSpending && primary.monthlyRetirementSpending > 0) {
                            // Fallback: 4% rule — 25× annual spending
                            ft = primary.monthlyRetirementSpending * 12 * 25;
                        }
                        if (ft > 0 && Math.abs(ft - Number(localStorage.getItem('xpe_fire_target') || 0)) > 1) {
                            localStorage.setItem('xpe_fire_target', Math.round(ft));
                            setTimeout(compute, 80); // re-run with updated target
                        }
                    }
                })
                .catch(function() {});
        }

        // ═══════════════════════════════════════════════════════
        // BADGE EVALUATION
        // ═══════════════════════════════════════════════════════

        // Helpers for badge calculation
        var hasWithdrawal       = withdrawals.length > 0;
        var noWithdrawalEver    = !hasWithdrawal;
        var months6Withdrawalfree = withdrawalFreeMonths >= 6;

        // Did portfolio ever see a –10% drawdown? Check snapshots.
        var saw10pctDip = false;
        var saw20pctDip = false;
        if (snapshots.length > 1) {
            var runningMax = 0;
            snapshots.forEach(function(s) {
                var v = Number(s.value);
                if (v > runningMax) runningMax = v;
                if (runningMax > 0) {
                    var drawdown = (runningMax - v) / runningMax;
                    if (drawdown >= 0.1) saw10pctDip = true;
                    if (drawdown >= 0.2) saw20pctDip = true;
                }
            });
        }

        // Wallets (IKE, IKZE) — use substring match to handle naming variations
        var walletNames = new Set(rows.map(function(r) { return String(r.wallet || '').toUpperCase(); }));
        var walletArr   = Array.from(walletNames);
        var ikzeActive  = walletArr.some(function(w) { return w.includes('IKZE'); });
        var ikeActive   = walletArr.some(function(w) { return w.includes('IKE') && !w.includes('IKZE'); });

        // Countries (heuristic: .WA suffix = Poland; Binance wallet or crypto token = CRYPTO; everything else = FOREIGN)
        var countryProxies = new Set();
        buys.forEach(function(r) {
            if (!r.asset || r.asset === 'Gotówka' || r.asset === 'Cash') return;
            var asset  = String(r.asset).toUpperCase();
            var wallet = String(r.wallet || '').toUpperCase();
            if (wallet === 'BINANCE' || asset.includes('BTC') || asset.includes('ETH') ||
                asset.includes('USDT') || asset.includes('USDC') || asset.includes('BNB') ||
                asset.includes('BITCOIN') || asset.includes('ETHEREUM')) {
                countryProxies.add('CRYPTO');
            } else if (asset.endsWith('.WA') || wallet.includes('IKE') || wallet.includes('IKZE') || wallet.includes('EMERYTURA')) {
                countryProxies.add('PL');
            } else {
                countryProxies.add('FOREIGN');
            }
        });

        function badge(id, name, tier, icon, unlocked, opts) {
            opts = opts || {};
            return {
                id: id, name: name, tier: tier, icon: icon,
                unlocked: unlocked,
                celebrate: opts.celebrate || false,
                unlockedOn: opts.unlockedOn || null,
                desc: opts.desc || '',
                roast: opts.roast || '',
                req: opts.req || '',
                progress: opts.progress,
                progressMax: opts.progressMax,
            };
        }

        // Find approximate unlock date (first tx date that satisfies condition)
        function firstDepositMonthReaching(n) {
            // Returns YYYY-MM when deposit streak first hit n
            if (depositMonthsSorted.length < n) return null;
            return depositMonthsSorted[n - 1]; // the nth deposit month (0-indexed)
        }

        var badges = [
            badge('showing_up', 'Showing Up', 'seed', 'calendar',
                deposits.length > 0, {
                    unlockedOn: deposits.length ? toYM(deposits[0].date) : null,
                    desc: 'First deposit recorded.',
                    roast: "The first one is the hardest. Now it's just numbers.",
                }),

            badge('reliable', 'Reliable', 'bronze', 'arrow_up',
                depositStreakVal >= 3 || depositMonthsSorted.length >= 3, {
                    unlockedOn: firstDepositMonthReaching(3),
                    desc: '3-month deposit streak.',
                    roast: "Month 3. You're officially no longer in the experimental phase.",
                    progress: Math.min(depositMonthsSorted.length, 3),
                    progressMax: 3,
                }),

            badge('eyes_open', 'Eyes Open', 'seed', 'eye',
                checkinVal >= 7, {
                    desc: '7 distinct days with portfolio activity.',
                    roast: "Seven sessions in a row. Every day, you showed up.",
                    progress: Math.min(checkinVal, 7),
                    progressMax: 7,
                }),

            badge('hands_off', 'Hands Off', 'bronze', 'lock',
                withdrawalFreeMonths >= 6, {
                    desc: '6 consecutive months without a withdrawal.',
                    roast: "Six months of leaving it alone. This is the discipline people talk about but rarely practice.",
                    progress: Math.min(withdrawalFreeMonths, 6),
                    progressMax: 6,
                }),

            badge('four_digits', 'Four Digits', 'seed', 'dollar',
                maxHistoricalValue >= 1000, {
                    desc: 'Portfolio reached 1 000 PLN.',
                    roast: "It begins. Technically you're an investor now.",
                }),

            badge('getting_serious', 'Getting Serious', 'bronze', 'bars',
                maxHistoricalValue >= 10000, {
                    desc: 'Portfolio reached 10 000 PLN.',
                    roast: "Five figures. A threshold that matters.",
                    progress: Math.min(Math.round(maxHistoricalValue), 10000),
                    progressMax: 10000,
                }),

            badge('not_one_basket', 'Not One Basket', 'seed', 'globe',
                uniqueTickers.size >= 3, {
                    desc: '3 different holdings in the portfolio.',
                    roast: "Diversified. Kind of.",
                    progress: Math.min(uniqueTickers.size, 3),
                    progressMax: 3,
                }),

            badge('diversified', 'Actually Diversified', 'bronze', 'globe',
                uniqueTickers.size >= 5, {
                    desc: '5 holdings across at least 2 assets.',
                    roast: "Five assets. You're managing a portfolio now, not a bet.",
                    progress: Math.min(uniqueTickers.size, 5),
                    progressMax: 5,
                }),

            badge('baptism', 'Baptism by Fire', 'bronze', 'flame',
                saw10pctDip, {
                    desc: 'Portfolio down 10%+. No withdrawal made.',
                    roast: "Down ten percent. You checked the app anyway. You didn't pull out. Badge earned.",
                }),

            badge('fire_curious', 'FIRE Curious', 'seed', 'target',
                hasRetirementPlan, {
                    desc: 'Retirement plan configured.',
                    roast: "The plan exists. That's already more than most.",
                }),

            badge('red_day', 'Red Day Survivor', 'seed', 'zap',
                saw10pctDip || (snapshots.length > 1), {
                    desc: 'Opened the app on a negative-return day.',
                    roast: "You looked at the numbers when they were bad. Respect.",
                }),

            badge('sold_something', 'Sold Something', 'seed', 'check',
                sells.length > 0, {
                    desc: 'First SELL transaction recorded.',
                    roast: "You sold something. It's a rite of passage. Everyone gets this one.",
                }),

            badge('committed', 'Committed', 'bronze', 'target',
                goalStreakVal >= 3, {
                    celebrate: goalStreakVal >= 3 && goalStreakVal <= 4,
                    desc: '3-month goal streak — monthly target hit 3 months running.',
                    roast: "Goal hit three months in a row. The plan is becoming a practice.",
                    progress: Math.min(goalStreakVal, 3),
                    progressMax: 3,
                }),

            // ── Locked badges with progress ──────────────────────
            badge('long_game', 'The Long Game', 'silver', 'arrow_up',
                depositStreakVal >= 12 || depositMonthsSorted.length >= 12, {
                    req: '12-month deposit streak',
                    progress: Math.min(depositMonthsSorted.length, 12),
                    progressMax: 12,
                }),

            badge('weekly_habit', 'Weekly Habit', 'bronze', 'eye',
                checkinVal >= 90, {
                    req: '90 active days',
                    progress: Math.min(checkinVal, 90),
                    progressMax: 90,
                }),

            badge('untouched', 'Untouched', 'silver', 'lock',
                withdrawalFreeMonths >= 36, {
                    req: '36-month withdrawal-free streak',
                    progress: Math.min(withdrawalFreeMonths, 36),
                    progressMax: 36,
                }),

            badge('on_track', 'On Track', 'silver', 'target',
                goalStreakVal >= 12, {
                    req: '12-month goal streak',
                    progress: Math.min(goalStreakVal, 12),
                    progressMax: 12,
                }),

            badge('six_figures', 'Six Figures', 'gold', 'award',
                maxHistoricalValue >= 100000, {
                    req: 'Portfolio reaches 100 000 PLN',
                    progress: Math.min(Math.round(maxHistoricalValue), 100000),
                    progressMax: 100000,
                }),

            badge('held_the_line', 'Held the Line', 'silver', 'shield',
                saw20pctDip, {
                    req: 'Portfolio down 20%+ — no withdrawal made',
                    progress: saw20pctDip ? 1 : 0,
                    progressMax: 1,
                }),

            badge('world_citizen', 'World Citizen', 'silver', 'globe',
                countryProxies.size >= 3, {
                    req: 'Holdings in 3+ countries/asset classes',
                    progress: Math.min(countryProxies.size, 3),
                    progressMax: 3,
                }),

            badge('tax_efficient', 'Tax Efficient', 'gold', 'percent',
                ikeActive && ikzeActive, {
                    req: 'Both IKE + IKZE accounts active',
                    progress: (ikeActive ? 1 : 0) + (ikzeActive ? 1 : 0),
                    progressMax: 2,
                }),

            badge('on_the_map', 'On the Map', 'bronze', 'flame',
                firePct >= 10, {
                    req: '10% of FIRE target reached',
                    desc: 'You have reached 10% of your retirement target.',
                    roast: "Ten percent. Statistically, this is where people start believing it might actually happen.",
                    progress: Math.round(Math.min(firePct, 10)),
                    progressMax: 10,
                }),

            badge('institutionalized', 'Institutionalized', 'gold', 'clock',
                depositMonthsSorted.length >= 36, {
                    req: '36-month deposit streak',
                    progress: Math.min(depositMonthsSorted.length, 36),
                    progressMax: 36,
                }),

            badge('comma_club', 'Comma Club', 'diamond', 'star',
                maxHistoricalValue >= 1000000, {
                    req: 'Portfolio reaches 1 000 000 PLN',
                    progress: Math.min(Math.round(maxHistoricalValue), 1000000),
                    progressMax: 1000000,
                }),
        ];

        // ── XP bonus for unlocked badges ───────────────────────
        badges.forEach(function(b) {
            if (b.unlocked) add(50, 'Badge: ' + b.name);
        });

        // ═══════════════════════════════════════════════════════
        // MONTHLY RECAP
        // ═══════════════════════════════════════════════════════
        var nowYM  = toYM(todayStr);
        var prevYM = (function() {
            var p = todayStr.split('-').map(Number);
            p[1]--;
            if (p[1] < 1) { p[1] = 12; p[0]--; }
            return p[0] + '-' + String(p[1]).padStart(2, '0');
        }());

        // Use snapshots to get last month's return
        var lastMonthReturn  = null;
        var lastMonthReturnPos = true;
        if (snapshots.length > 1) {
            var byMon = {};
            snapshots.forEach(function(s) {
                var m = toYM(s.date);
                if (m) byMon[m] = s; // last snapshot wins (snapshots assumed asc)
            });
            var prevSnap = byMon[prevYM];
            var prevPrevKeys = Object.keys(byMon).sort();
            var prevPrevIdx  = prevPrevKeys.indexOf(prevYM) - 1;
            var prevPrevSnap = prevPrevIdx >= 0 ? byMon[prevPrevKeys[prevPrevIdx]] : null;
            if (prevSnap && prevPrevSnap && Number(prevPrevSnap.value) > 0) {
                lastMonthReturn = ((Number(prevSnap.value) - Number(prevPrevSnap.value)) / Number(prevPrevSnap.value) * 100);
                lastMonthReturnPos = lastMonthReturn >= 0;
                lastMonthReturn = (lastMonthReturn >= 0 ? '+' : '') + lastMonthReturn.toFixed(1) + '%';
            }
        }

        var depositsThisMonth = deposits
            .filter(function(d) { return toYM(d.date) === nowYM; })
            .reduce(function(s, d) { return s + Math.abs(Number(d.value || 0)); }, 0);
        var depositsLastMonth = deposits
            .filter(function(d) { return toYM(d.date) === prevYM; })
            .reduce(function(s, d) { return s + Math.abs(Number(d.value || 0)); }, 0);

        var depositGoalMet = (depositsThisMonth >= DEPOSIT_GOAL) || (depositsLastMonth >= DEPOSIT_GOAL);
        var depositedAmt   = depositsThisMonth > 0 ? depositsThisMonth : depositsLastMonth;
        var newBadges      = badges.filter(function(b) { return b.celebrate; }).length;

        var monthlyRoast = (function() {
            if (!rows.length) return "No transactions on record. The portfolio will not roast itself without data.";
            var ret = lastMonthReturn || (totalVal > 0 ? '+?' : '—');
            var dep = depositedAmt > 0 ? depositedAmt.toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' PLN deposited.' : 'No deposits this period.';
            var streak = depositStreakVal > 0 ? 'Deposit streak: ' + depositStreakVal + ' month' + (depositStreakVal > 1 ? 's.' : '.') : '';
            return ret + ' portfolio return. ' + dep + (streak ? ' ' + streak : '') + " Don't ruin it next month.";
        }());

        var monthly = {
            month:              new Date().toLocaleString('en-US', { month: 'long', year: 'numeric' }),
            portfolioChangePct: lastMonthReturn || (totalVal > 0 ? '—' : '—'),
            portfolioChangePos: lastMonthReturnPos,
            deposited:          depositedAmt > 0 ? depositedAmt.toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' PLN' : '—',
            depositGoal:        DEPOSIT_GOAL.toLocaleString('pl-PL') + ' PLN',
            depositGoalMet:     depositGoalMet,
            bestHolding:        '—',
            worstHolding:       '—',
            activeStreaks:      streaks.filter(function(s) { return s.value > 0; }),
            badgesUnlocked:     newBadges,
            roast:              monthlyRoast,
        };

        // ═══════════════════════════════════════════════════════
        // MILESTONE HISTORY
        // ═══════════════════════════════════════════════════════
        var MILESTONES = [1000, 10000, 50000, 100000, 250000, 500000, 1000000, 2000000, 5000000];
        var MILESTONE_TIERS = {
            1000: 'seed', 10000: 'bronze', 50000: 'bronze', 100000: 'gold',
            250000: 'gold', 500000: 'diamond', 1000000: 'diamond', 2000000: 'diamond', 5000000: 'diamond',
        };
        var MILESTONE_ROASTS = {
            1000:    "It begins. Technically you're an investor now.",
            10000:   "Five figures. A threshold that matters.",
            50000:   "Halfway to six figures. The market will try to undo this. Don't let it.",
            100000:  "Six figures. This is the number that changes behavior. Guard it.",
            250000:  "A quarter million. At this point your money has a support group.",
            500000:  "Half a million. The math is doing most of the work now.",
            1000000: "One million. You either DCA'd for 30 years or got very lucky.",
            2000000: "Two million. The returns alone are someone's annual salary.",
            5000000: "Five million. The portfolio manages you more than you manage it.",
        };

        // Find approx date a milestone was first crossed from snapshots
        var milestoneUnlockDates = {};
        snapshots.forEach(function(s) {
            var v = Number(s.value);
            MILESTONES.forEach(function(m) {
                if (!milestoneUnlockDates[m] && v >= m) {
                    milestoneUnlockDates[m] = toYM(s.date);
                }
            });
        });

        var milestoneHistory = MILESTONES.map(function(m) {
            var unlocked = maxHistoricalValue >= m;
            var dateStr  = milestoneUnlockDates[m] || null;
            if (!unlocked) {
                return {
                    type: 'portfolio', value: m, currency: 'PLN',
                    label: fmtPLN(m), tier: MILESTONE_TIERS[m] || 'seed',
                    unlocked: false,
                    current: Math.round(Math.min(totalVal, m)),
                    roast: MILESTONE_ROASTS[m] || '',
                    progressSuffix: 'PLN current', remainSuffix: 'PLN to go',
                };
            }
            return {
                type: 'portfolio', value: m, currency: 'PLN',
                label: fmtPLN(m), tier: MILESTONE_TIERS[m] || 'seed',
                unlocked: true, date: dateStr,
                roast: MILESTONE_ROASTS[m] || '',
            };
        });

        // ── Investor journey milestones (from first transaction date) ──────
        var firstTxDate    = rows.length ? rows.slice().sort(function(a, b) { return a.date.localeCompare(b.date); })[0].date : null;
        var monthsInvested = firstTxDate ? monthsBetween(toYM(firstTxDate), toYM(todayStr)) : 0;

        var JOURNEY = [
            { months: 3,   label: '3 months invested',  tier: 'seed',    roast: "Still here. Initial excitement survived." },
            { months: 6,   label: '6 months invested',  tier: 'seed',    roast: "Half a year. One market wobble behind you, probably." },
            { months: 12,  label: '1 year invested',    tier: 'bronze',  roast: "One full year as an investor. All four seasons of market behavior." },
            { months: 24,  label: '2 years invested',   tier: 'silver',  roast: "The 'long term' is no longer hypothetical." },
            { months: 60,  label: '5 years invested',   tier: 'gold',    roast: "You're a different investor than when you started." },
            { months: 120, label: '10 years invested',  tier: 'diamond', roast: "A decade. Compounding has had time to become your co-pilot." },
        ];

        // Approximate unlock date: firstTxDate + journey.months months
        function addMonthsToYM(ym, n) {
            if (!ym) return null;
            var p = ym.split('-').map(Number);
            p[1] += n;
            while (p[1] > 12) { p[1] -= 12; p[0]++; }
            return p[0] + '-' + String(p[1]).padStart(2, '0');
        }

        var journeyMilestones = JOURNEY.map(function(j) {
            var unlocked = monthsInvested >= j.months;
            return {
                type: 'journey', value: j.months, currency: 'months',
                label: j.label, tier: j.tier,
                unlocked: unlocked,
                date: unlocked ? addMonthsToYM(toYM(firstTxDate || todayStr), j.months) : null,
                current: monthsInvested,
                roast: j.roast,
                progressSuffix: 'mo invested', remainSuffix: 'mo to go',
            };
        });

        // ── Monthly deposit personal best milestones ────────────────────────
        var maxMonthlyDeposit = 0;
        var maxMonthlyDepositMonth = null;
        Object.keys(depositByMonth).forEach(function(m) {
            if (depositByMonth[m] > maxMonthlyDeposit) {
                maxMonthlyDeposit = depositByMonth[m];
                maxMonthlyDepositMonth = m;
            }
        });

        var MONTHLY_BEST = [
            { amount: 1000,   label: '1 000 PLN month',    tier: 'seed' },
            { amount: 2500,   label: '2 500 PLN month',    tier: 'bronze' },
            { amount: 5000,   label: '5 000 PLN month',    tier: 'bronze' },
            { amount: 10000,  label: '10 000 PLN month',   tier: 'silver' },
            { amount: 25000,  label: '25 000 PLN month',   tier: 'silver' },
            { amount: 50000,  label: '50 000 PLN month',   tier: 'gold' },
            { amount: 100000, label: '100 000 PLN month',  tier: 'diamond' },
        ];

        var monthlyBestMilestones = MONTHLY_BEST.map(function(mb) {
            var unlocked = maxMonthlyDeposit >= mb.amount;
            return {
                type: 'monthly_best', value: mb.amount, currency: 'PLN/mo',
                label: mb.label, tier: mb.tier,
                unlocked: unlocked,
                date: unlocked ? maxMonthlyDepositMonth : null,
                current: Math.round(Math.min(maxMonthlyDeposit, mb.amount)),
                roast: unlocked
                    ? fmtPLN(Math.round(maxMonthlyDeposit)) + ' in one month. That is not a coincidence, that is a habit.'
                    : 'Deposit ' + fmtPLN(mb.amount) + ' in a single calendar month.',
                progressSuffix: 'PLN best', remainSuffix: 'PLN to go',
            };
        });

        // ── FIRE progress milestones ────────────────────────────────────────
        var FIRE_PCTS = [
            { pct: 10,  label: '10% to FIRE',  tier: 'seed',    roast: "Ten percent. Statistically, this is where people start believing it might actually happen." },
            { pct: 25,  label: '25% to FIRE',  tier: 'bronze',  roast: "A quarter of the way. The number has seven figures written all over it." },
            { pct: 50,  label: '50% to FIRE',  tier: 'silver',  roast: "Halfway. Markets will try to make this feel temporary. It isn't." },
            { pct: 75,  label: '75% to FIRE',  tier: 'gold',    roast: "Three quarters. At this point you're closer to done than to started." },
            { pct: 90,  label: '90% to FIRE',  tier: 'gold',    roast: "Ninety percent. The finish line is visible. Don't do anything stupid." },
            { pct: 100, label: 'FIRE achieved', tier: 'diamond', roast: "One hundred percent. You did it. Now the hard part: actually retiring." },
        ];

        var fireMilestones = fireTarget > 0 ? FIRE_PCTS.map(function(fp) {
            var unlocked = firePct >= fp.pct;
            return {
                type: 'fire', value: fp.pct, currency: '%',
                label: fp.label, tier: fp.tier,
                unlocked: unlocked,
                date: null, // can't easily determine when % was first crossed
                current: Math.round(Math.min(firePct, fp.pct)),
                roast: fp.roast,
                progressSuffix: '% of FIRE', remainSuffix: '% to go',
            };
        }) : [];

        // ═══════════════════════════════════════════════════════
        // ASSEMBLE RESULT
        // ═══════════════════════════════════════════════════════
        var levelInfo = resolveLevel(totalXP);

        _result = {
            hasRealData: rows.length > 0 || snapshots.length > 0,
            xp: {
                current:   levelInfo.current,
                level:     levelInfo.name,
                nextLevel: levelInfo.nextName,
                nextAt:    levelInfo.nextAt,
                prevAt:    levelInfo.prevAt,
                breakdown: xpBreakdown,
            },
            streaks: streaks,
            badges: badges,
            milestoneHistory:      milestoneHistory,
            journeyMilestones:     journeyMilestones,
            monthlyBestMilestones: monthlyBestMilestones,
            fireMilestones:        fireMilestones,
            monthly: monthly,
            _meta: {
                depositCount:          deposits.length,
                depositMonths:         depositMonthsSorted.length,
                uniqueTickers:         uniqueTickers.size,
                withdrawalCount:       withdrawals.length,
                depositGoal:           DEPOSIT_GOAL,
                fireTarget:            fireTarget,
                firePct:               Math.round(firePct),
                monthsInvested:        monthsInvested,
                maxMonthlyDeposit:     Math.round(maxMonthlyDeposit),
                beatBenchmarkStreak:   beatBenchmarkStreak,
                beatBenchmarkMonths:   beatBenchmarkSorted.length,
                benchmarkId:           _benchmarkReturnsId,
            },
        };

        window.dispatchEvent(new CustomEvent('xpEngineReady', { detail: _result }));
        return _result;
    }

    // ═══════════════════════════════════════════════════════════
    // AUTO-TRIGGER
    // ═══════════════════════════════════════════════════════════

    // Re-compute whenever transaction data or portfolio data arrives
    window.addEventListener('ledgerTransactionsUpdated', function() { compute(); });
    document.addEventListener('liveDataReady',           function() { compute(); });

    // On pages that don't explicitly call loadRows() (e.g. achievements.html),
    // kick off the fetch now so transaction-based badges compute correctly.
    if (typeof LedgerTransactions !== 'undefined' &&
        typeof LedgerTransactions.loadRows === 'function' &&
        LedgerTransactions.getRows().length === 0) {
        LedgerTransactions.loadRows({ attemptMigration: false }).catch(function() {});
    }

    // ═══════════════════════════════════════════════════════════
    // PUBLIC API
    // ═══════════════════════════════════════════════════════════
    window.XPEngine = {
        compute:   compute,
        getResult: function() { return _result; },
        LEVELS:    LEVELS,
        XP_RULES:  XP,
        DEPOSIT_GOAL: DEPOSIT_GOAL,
        /** Set the monthly deposit goal (PLN) and persist it. Triggers re-compute. */
        setDepositGoal: function(amount) {
            var n = Number(amount);
            if (!n || n <= 0) return;
            localStorage.setItem('xpe_deposit_goal', n);
            DEPOSIT_GOAL = n;
            compute();
        },
    };

}());
