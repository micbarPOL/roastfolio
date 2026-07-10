/* achievements.js — Roastfolio Engagement Layer v2
 *
 * Tracks behavioral metrics: streaks, milestone progression, badges, and XP.
 * "Gamification" is a reductive term. This is a structured reinforcement
 *  system with measurable behavioral outcomes. The distinction matters.
 *
 * Rendering is data-driven: if xp-engine.js has produced real computed data
 * (window.XPEngine.getResult()), that data is used. The static DATA object
 * below serves as a fallback when no transaction history is loaded yet.
 *
 * For contextual commentary, see roast-engine.js.
 * I want to be clear: the opinions expressed there are data-driven.
 */
(function () {
    'use strict';

    // ═══════════════════════════════════════════════════════════
    // SVG ICON LIBRARY
    // ═══════════════════════════════════════════════════════════
    const IC = {
        arrow_up:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>`,
        calendar:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
        lock:         `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>`,
        target:       `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>`,
        trending:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>`,
        shield:       `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
        dollar:       `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`,
        flame:        `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>`,
        globe:        `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`,
        star:         `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
        eye:          `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
        bars:         `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
        check:        `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
        award:        `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/></svg>`,
        zap:          `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
        percent:      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="5" x2="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></svg>`,
        clock:        `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
        noentry:      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>`,
    };

    // ═══════════════════════════════════════════════════════════
    // MOCK DATA
    // ═══════════════════════════════════════════════════════════
    const DATA = {
        xp: {
            current:   1240,
            level:     'Contributor',
            nextLevel: 'Operator',
            nextAt:    2500,
            prevAt:    1000,
        },

        streaks: [
            {
                id: 'contribution', name: 'Deposit streak',
                value: 7, unit: 'mo', color: '#27ae60',
                best: 7,
                nextMilestone: 12, nextLabel: 'next: 12 mo',
                hint: 'Monthly capital added',
            },
            {
                id: 'checkin', name: 'Check-in streak',
                value: 34, unit: 'days', color: '#2b88cf',
                best: 51,
                nextMilestone: 90, nextLabel: 'next: 90 days',
                hint: 'GPW trading days opened',
            },
            {
                id: 'withdrawal', name: 'Withdrawal-free',
                value: 14, unit: 'mo', color: '#8a4fff',
                best: 14,
                nextMilestone: 36, nextLabel: 'next: 36 mo',
                hint: 'Months without pulling out',
            },
            {
                id: 'goal', name: 'Goal streak',
                value: 4, unit: 'mo', color: '#d4ac2a',
                best: 6,
                nextMilestone: 12, nextLabel: 'goal: 1 000 PLN/mo',
                hint: 'Monthly target hit',
            },
            {
                id: 'green', name: 'Green months',
                value: 3, unit: 'mo', color: '#4caf82',
                best: 5,
                nextMilestone: 6, nextLabel: 'next: 6 mo',
                hint: 'Consecutive positive returns',
            },
            {
                id: 'beat_benchmark', name: 'Beat WIG',
                value: 2, unit: 'mo', color: '#e06b1f',
                best: 4,
                nextMilestone: 3, nextLabel: 'next: 3 mo',
                hint: 'Consecutive months where net return exceeded WIG',
                startMonth: null,
                keepGoingHint: 'Your net portfolio return must beat WIG this month',
            },
        ],

        milestoneHistory: [
            {
                value:   1000, currency: 'PLN',
                date:    'Jan 2024', tier: 'seed', unlocked: true,
                roast:   "It begins. Technically you're an investor now.",
            },
            {
                value:   10000, currency: 'PLN',
                date:    'Mar 2024', tier: 'bronze', unlocked: true,
                roast:   "Five figures. A threshold that matters.",
            },
            {
                value:   50000, currency: 'PLN',
                date:    'Nov 2024', tier: 'silver', unlocked: true,
                roast:   "Halfway to six figures. The market will try to undo this. Don't let it.",
            },
            {
                value:   100000, currency: 'PLN',
                date:    null, tier: 'gold', unlocked: false,
                current: 73500,
                roast:   "Six figures. This is the number that changes behavior. Guard it.",
            },
            {
                value:   250000, currency: 'PLN',
                date:    null, tier: 'gold', unlocked: false,
                current: 73500,
                roast:   "A quarter million. At this point your money has a support group.",
            },
            {
                value:   500000, currency: 'PLN',
                date:    null, tier: 'diamond', unlocked: false,
                current: 73500,
                roast:   "Half a million. The math is doing most of the work now.",
            },
            {
                value:   1000000, currency: 'PLN',
                date:    null, tier: 'diamond', unlocked: false,
                current: 73500,
                roast:   "One million. You either DCA'd for 30 years or got very lucky.",
            },
        ],

        badges: [
            // UNLOCKED
            { id: 'showing_up',     name: 'Showing Up',          tier: 'seed',   icon: 'calendar', unlocked: true, celebrate: false, unlockedOn: 'Jan 2024', desc: 'First deposit recorded.',                                           roast: "The first one is the hardest. Now it's just numbers." },
            { id: 'reliable',       name: 'Reliable',            tier: 'bronze', icon: 'arrow_up', unlocked: true, celebrate: false, unlockedOn: 'Apr 2024', desc: '3-month deposit streak.',                                            roast: "Month 3. You're officially no longer in the experimental phase." },
            { id: 'eyes_open',      name: 'Eyes Open',           tier: 'seed',   icon: 'eye',      unlocked: true, celebrate: false, unlockedOn: 'Feb 2024', desc: '7 consecutive GPW trading-day check-ins.',                           roast: "Seven trading days in a row. Every session, you showed up." },
            { id: 'hands_off',      name: 'Hands Off',           tier: 'bronze', icon: 'lock',     unlocked: true, celebrate: false, unlockedOn: 'Jul 2024', desc: '6 consecutive months without a withdrawal.',                         roast: "Six months of leaving it alone. This is the discipline people talk about but rarely practice." },
            { id: 'four_digits',    name: 'Four Digits',         tier: 'seed',   icon: 'dollar',   unlocked: true, celebrate: false, unlockedOn: 'Jan 2024', desc: 'Portfolio reached 1 000 PLN.',                                       roast: "It begins. Technically you're an investor now." },
            { id: 'getting_serious',name: 'Getting Serious',     tier: 'bronze', icon: 'bars',     unlocked: true, celebrate: false, unlockedOn: 'Mar 2024', desc: 'Portfolio reached 10 000 PLN.',                                      roast: "Five figures. A threshold that matters." },
            { id: 'not_one_basket', name: 'Not One Basket',      tier: 'seed',   icon: 'globe',    unlocked: true, celebrate: false, unlockedOn: 'Feb 2024', desc: '3 different holdings in the portfolio.',                             roast: "Diversified. Kind of." },
            { id: 'diversified',    name: 'Actually Diversified',tier: 'bronze', icon: 'globe',    unlocked: true, celebrate: false, unlockedOn: 'Apr 2024', desc: '5 holdings across 2 asset classes.',                                 roast: "Five assets. You're managing a portfolio now, not a bet." },
            { id: 'baptism',        name: 'Baptism by Fire',     tier: 'bronze', icon: 'flame',    unlocked: true, celebrate: false, unlockedOn: 'Mar 2024', desc: 'Portfolio down 10%+. No withdrawal made.',                           roast: "Down ten percent. You checked the app anyway. You didn't pull out. Badge earned." },
            { id: 'fire_curious',   name: 'FIRE Curious',        tier: 'seed',   icon: 'target',   unlocked: true, celebrate: false, unlockedOn: 'Feb 2024', desc: 'Retirement plan configured.',                                        roast: "The plan exists. That's already more than most." },
            { id: 'red_day',        name: 'Red Day Survivor',    tier: 'seed',   icon: 'zap',      unlocked: true, celebrate: false, unlockedOn: 'Mar 2024', desc: 'Opened the app on a -3%+ portfolio day.',                            roast: "You looked at the numbers when they were bad. Respect." },
            { id: 'sold_something', name: 'Sold Something',      tier: 'seed',   icon: 'check',    unlocked: true, celebrate: false, unlockedOn: 'May 2024', desc: 'First SELL transaction recorded.',                                   roast: "You sold something. It's a rite of passage. Everyone gets this one." },
            { id: 'committed',      name: 'Committed',           tier: 'bronze', icon: 'target',   unlocked: true, celebrate: true,  unlockedOn: 'May 2025', desc: '3-month goal streak — monthly target hit 3 months running.',         roast: "Goal hit three months in a row. The plan is becoming a practice." },
            // LOCKED
            { id: 'long_game',        name: 'The Long Game',       tier: 'silver',  icon: 'arrow_up', unlocked: false, req: '12-month deposit streak',                     progress: 7,     progressMax: 12 },
            { id: 'weekly_habit',     name: 'Weekly Habit',        tier: 'bronze',  icon: 'eye',      unlocked: false, req: '90 trading-day check-in streak',               progress: 34,    progressMax: 90 },
            { id: 'untouched',        name: 'Untouched',           tier: 'silver',  icon: 'lock',     unlocked: false, req: '36-month withdrawal-free streak',              progress: 14,    progressMax: 36 },
            { id: 'on_track',         name: 'On Track',            tier: 'silver',  icon: 'target',   unlocked: false, req: '12-month goal streak',                         progress: 4,     progressMax: 12 },
            { id: 'six_figures',      name: 'Six Figures',         tier: 'gold',    icon: 'award',    unlocked: false, req: 'Portfolio reaches 100 000 PLN',                progress: 73500, progressMax: 100000 },
            { id: 'held_the_line',    name: 'Held the Line',       tier: 'silver',  icon: 'shield',   unlocked: false, req: 'Portfolio down 20%+ — no withdrawal made',    progress: 0,     progressMax: 1 },
            { id: 'world_citizen',    name: 'World Citizen',       tier: 'silver',  icon: 'globe',    unlocked: false, req: 'Holdings in 3+ countries',                     progress: 2,     progressMax: 3 },
            { id: 'tax_efficient',    name: 'Tax Efficient',       tier: 'gold',    icon: 'percent',  unlocked: false, req: 'Both IKE + IKZE accounts active',              progress: 1,     progressMax: 2 },
            { id: 'on_the_map',       name: 'On the Map',          tier: 'bronze',  icon: 'flame',    unlocked: false, req: '10% of FIRE target reached',                   progress: 0,     progressMax: 10 },
            { id: 'institutionalized',name: 'Institutionalized',   tier: 'gold',    icon: 'clock',    unlocked: false, req: '36-month deposit streak',                      progress: 7,     progressMax: 36 },
            { id: 'comma_club',       name: 'Comma Club',          tier: 'diamond', icon: 'star',     unlocked: false, req: 'Portfolio reaches 1 000 000 PLN',              progress: 73500, progressMax: 1000000 },
        ],

        monthly: {
            month:              'May 2026',
            portfolioChangePct: '+3.8%',
            portfolioChangePos: true,
            deposited:          '1 200 PLN',
            depositGoal:        '1 000 PLN',
            depositGoalMet:     true,
            bestHolding:        'VWCE  +6.2%',
            worstHolding:       'CDR  -1.1%',
            activeStreaks:      '7-month deposits',
            badgesUnlocked:     1,
            roast: "Up 3.8%. You deposited 1 200 PLN. The market helped with the rest. "
                 + "Contribution streak: 7 months. Don't ruin it in June.",
        },

        journeyMilestones: [
            { type: 'journey', value: 3,   currency: 'months', label: '3 months invested',  tier: 'seed',    unlocked: true,  date: 'Apr 2024', roast: "Still here. Initial excitement survived." },
            { type: 'journey', value: 6,   currency: 'months', label: '6 months invested',  tier: 'seed',    unlocked: true,  date: 'Jul 2024', roast: "Half a year. One market wobble behind you, probably." },
            { type: 'journey', value: 12,  currency: 'months', label: '1 year invested',    tier: 'bronze',  unlocked: true,  date: 'Jan 2025', roast: "One full year as an investor. All four seasons of market behavior." },
            { type: 'journey', value: 24,  currency: 'months', label: '2 years invested',   tier: 'silver',  unlocked: false, date: null, current: 17, roast: "The 'long term' is no longer hypothetical.", progressSuffix: 'mo invested', remainSuffix: 'mo to go' },
            { type: 'journey', value: 60,  currency: 'months', label: '5 years invested',   tier: 'gold',    unlocked: false, date: null, current: 17, roast: "You're a different investor than when you started.", progressSuffix: 'mo invested', remainSuffix: 'mo to go' },
            { type: 'journey', value: 120, currency: 'months', label: '10 years invested',  tier: 'diamond', unlocked: false, date: null, current: 17, roast: "A decade. Compounding has had time to become your co-pilot.", progressSuffix: 'mo invested', remainSuffix: 'mo to go' },
        ],

        monthlyBestMilestones: [
            { type: 'monthly_best', value: 1000,   currency: 'PLN/mo', label: '1 000 PLN month',   tier: 'seed',    unlocked: true,  date: 'Feb 2024', roast: "1 000 PLN in one month. That is not a coincidence, that is a habit." },
            { type: 'monthly_best', value: 2500,   currency: 'PLN/mo', label: '2 500 PLN month',   tier: 'bronze',  unlocked: false, date: null, current: 1200, roast: "Deposit 2 500 PLN in a single calendar month.", progressSuffix: 'PLN best', remainSuffix: 'PLN to go' },
            { type: 'monthly_best', value: 5000,   currency: 'PLN/mo', label: '5 000 PLN month',   tier: 'bronze',  unlocked: false, date: null, current: 1200, roast: "Deposit 5 000 PLN in a single calendar month.", progressSuffix: 'PLN best', remainSuffix: 'PLN to go' },
            { type: 'monthly_best', value: 10000,  currency: 'PLN/mo', label: '10 000 PLN month',  tier: 'silver',  unlocked: false, date: null, current: 1200, roast: "Deposit 10 000 PLN in a single calendar month.", progressSuffix: 'PLN best', remainSuffix: 'PLN to go' },
            { type: 'monthly_best', value: 25000,  currency: 'PLN/mo', label: '25 000 PLN month',  tier: 'silver',  unlocked: false, date: null, current: 1200, roast: "Deposit 25 000 PLN in a single calendar month.", progressSuffix: 'PLN best', remainSuffix: 'PLN to go' },
            { type: 'monthly_best', value: 50000,  currency: 'PLN/mo', label: '50 000 PLN month',  tier: 'gold',    unlocked: false, date: null, current: 1200, roast: "Deposit 50 000 PLN in a single calendar month.", progressSuffix: 'PLN best', remainSuffix: 'PLN to go' },
            { type: 'monthly_best', value: 100000, currency: 'PLN/mo', label: '100 000 PLN month', tier: 'diamond', unlocked: false, date: null, current: 1200, roast: "Deposit 100 000 PLN in a single calendar month.", progressSuffix: 'PLN best', remainSuffix: 'PLN to go' },
        ],

        fireMilestones: [],
    };

    // ═══════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════
    const CIRCUMFERENCE = 175.93; // 2π × r28

    function fmtNum(n) { return Number(n).toLocaleString('pl-PL'); }

    function tierLabel(t) {
        return { seed: 'Seed', bronze: 'Bronze', silver: 'Silver', gold: 'Gold', diamond: 'Diamond' }[t] || t;
    }

    function tierColor(t) {
        return { seed: '#8aa8c8', bronze: '#c8873a', silver: '#a8c8e8', gold: '#d4ac2a', diamond: '#2bcfcf' }[t] || '#6a8ba8';
    }

    function animateBar(el, pct, delayMs) {
        if (!el) return;
        el.style.width = '0';
        setTimeout(() => { el.style.width = Math.min(pct, 100) + '%'; }, delayMs || 80);
    }

    // ═══════════════════════════════════════════════════════════
    // LIVE DATA RESOLVER
    // ═══════════════════════════════════════════════════════════
    // Returns real computed data from XPEngine when available, else mock DATA.
    function getData() {
        var engineResult = window.XPEngine && window.XPEngine.getResult();
        if (engineResult && engineResult.hasRealData) return engineResult;
        return DATA;
    }

    // ═══════════════════════════════════════════════════════════
    // RENDER: XP CARD
    // ═══════════════════════════════════════════════════════════
    function renderXP() {
        const d    = getData().xp;
        const pct  = ((d.current - d.prevAt) / (d.nextAt - d.prevAt)) * 100;
        const pill = document.getElementById('ach-level-pill');
        const lvEl = document.getElementById('ach-xp-level');
        const sub  = document.getElementById('ach-xp-sub');
        const num  = document.getElementById('ach-xp-number');
        const lvls = document.getElementById('ach-xp-levels');
        const fill = document.getElementById('ach-xp-fill');

        if (pill) pill.textContent = d.level;
        if (lvEl) lvEl.textContent = d.level;
        if (num)  num.textContent  = fmtNum(d.current);
        if (sub)  sub.textContent  = fmtNum(d.current) + ' XP · ' + fmtNum(d.nextAt - d.current) + ' to ' + d.nextLevel;

        if (lvls) {
            lvls.innerHTML =
                '<span class="ach-xp-level-label">' + d.level + '</span>' +
                '<span class="ach-xp-level-label ach-xp-level-current">' + Math.round(pct) + '%</span>' +
                '<span class="ach-xp-level-label">' + d.nextLevel + '</span>';
        }
        if (fill) animateBar(fill, pct, 300);

        // Show breakdown hint when real breakdown data is available
        var hintEl = document.getElementById('ach-xp-breakdown-hint');
        var breakdown = getData().xp && getData().xp.breakdown;
        if (hintEl) {
            if (breakdown && breakdown.length) {
                hintEl.style.display = '';
            } else {
                hintEl.style.display = 'none';
            }
        }
    }

    // ═══════════════════════════════════════════════════════════
    // RENDER: STREAK CARDS
    // ═══════════════════════════════════════════════════════════
    function renderStreaks() {
        const container = document.getElementById('ach-streaks-scroll');
        if (!container) return;

        container.innerHTML = getData().streaks.map(function(s, i) {
            var progress = Math.min(s.value / s.nextMilestone, 1);
            var isBest   = s.value === s.best;
            var bestHTML = isBest
                ? '<span class="ach-streak-pb is-active">PB</span>'
                : '<span class="ach-streak-pb">PB&nbsp;' + s.best + '</span>';

            return '<div class="ach-streak-card" data-streak="' + s.id + '"' +
                   ' style="animation-delay:' + (i * 60) + 'ms" title="' + s.hint + '">' +
                   '<div class="ach-ring-wrap">' +
                   '<svg class="ach-ring-svg" viewBox="0 0 72 72" role="img"' +
                   ' aria-label="' + s.name + ': ' + s.value + ' ' + s.unit + '">' +
                   '<circle class="ach-ring-track" cx="36" cy="36" r="28"/>' +
                   '<circle class="ach-ring-progress" cx="36" cy="36" r="28"' +
                   ' stroke="' + s.color + '" data-progress="' + progress.toFixed(4) + '"' +
                   ' style="stroke-dashoffset:' + CIRCUMFERENCE + '"/>' +
                   '</svg>' +
                   '<div class="ach-ring-center">' +
                   '<span class="ach-ring-val">' + s.value + '</span>' +
                   '<span class="ach-ring-unit">' + s.unit + '</span>' +
                   '</div></div>' +
                   '<div class="ach-streak-name">' + s.name + '</div>' +
                   '<div class="ach-streak-meta-row">' +
                   '<div class="ach-streak-next">' + s.nextLabel + '</div>' +
                   bestHTML +
                   '</div></div>';
        }).join('');

        setTimeout(function() {
            container.querySelectorAll('.ach-ring-progress').forEach(function(el) {
                var p = parseFloat(el.dataset.progress);
                el.style.strokeDashoffset = (CIRCUMFERENCE * (1 - p)).toFixed(2);
            });
        }, 220);
    }

    // ═══════════════════════════════════════════════════════════
    // RENDER: MILESTONE TIMELINE (generic — used for all 4 types)
    // ═══════════════════════════════════════════════════════════

    /**
     * Generic milestone timeline renderer.
     * @param {string} containerId  - id of the timeline container element
     * @param {string} summaryId    - id of the summary count element
     * @param {Array}  milestones   - array of milestone objects from XPEngine
     * @param {string} fillPrefix   - unique prefix for fill element ids
     */
    function renderMilestoneSection(containerId, summaryId, milestones, fillPrefix) {
        var container = document.getElementById(containerId);
        var summary   = document.getElementById(summaryId);
        if (!container) return;

        if (!milestones || !milestones.length) {
            container.innerHTML = '';
            if (summary) summary.textContent = '';
            return;
        }

        var unlocked = milestones.filter(function(m) { return m.unlocked; }).length;
        var nextIdx  = milestones.findIndex(function(m) { return !m.unlocked; });
        if (summary) summary.textContent = unlocked + ' of ' + milestones.length + ' reached';

        var items = milestones.map(function(m, i) {
            var isNext    = (i === nextIdx);
            var isFuture  = !m.unlocked && !isNext;
            var color     = tierColor(m.tier);
            var isLast    = (i === milestones.length - 1);
            var connector = isLast ? '' : '<div class="ach-mh-connector' + (isFuture ? ' is-faded' : '') + '"></div>';
            var lbl       = m.label || (fmtNum(m.value) + ' ' + m.currency);
            var fillId    = fillPrefix + '-fill-' + i;

            if (m.unlocked) {
                return '<div class="ach-mh-item is-unlocked" style="animation-delay:' + (i * 55) + 'ms">' +
                       '<div class="ach-mh-left">' +
                       '<div class="ach-mh-node is-unlocked" style="border-color:' + color + '">' +
                       '<svg viewBox="0 0 16 16" fill="none" stroke="' + color + '" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 8.5 6.5 12 13 5"/></svg>' +
                       '</div>' + connector + '</div>' +
                       '<div class="ach-mh-body">' +
                       '<div class="ach-mh-top-row">' +
                       '<span class="ach-mh-amount">' + lbl + '</span>' +
                       '<span class="ach-mh-tier" style="color:' + color + '">' + tierLabel(m.tier) + '</span>' +
                       '</div>' +
                       (m.date ? '<div class="ach-mh-date">' + m.date + '</div>' : '') +
                       '<div class="ach-mh-roast">&ldquo;' + m.roast + '&rdquo;</div>' +
                       '</div></div>';
            }

            if (isNext) {
                var pct       = m.value > 0 ? Math.min((m.current / m.value) * 100, 100) : 0;
                var remaining = fmtNum(m.value - m.current);
                var sufCurrent  = m.progressSuffix  || m.currency;
                var sufRemain   = m.remainSuffix    || m.currency + ' to go';
                return '<div class="ach-mh-item is-next" style="animation-delay:' + (i * 55) + 'ms">' +
                       '<div class="ach-mh-left">' +
                       '<div class="ach-mh-node is-next" style="border-color:' + color + '">' +
                       '<div class="ach-mh-node-dot" style="background:' + color + '"></div>' +
                       '</div>' + connector + '</div>' +
                       '<div class="ach-mh-body">' +
                       '<div class="ach-mh-top-row">' +
                       '<span class="ach-mh-amount is-next-amount">' + lbl + '</span>' +
                       '<span class="ach-mh-pct-label">' + pct.toFixed(0) + '%</span>' +
                       '</div>' +
                       '<div class="ach-mh-progress-track">' +
                       '<div class="ach-mh-progress-fill" id="' + fillId + '"' +
                       ' style="background:' + color + '; width:0"></div>' +
                       '</div>' +
                       '<div class="ach-mh-progress-meta">' +
                       '<span>' + fmtNum(m.current) + ' ' + sufCurrent + '</span>' +
                       '<span>' + remaining + ' ' + sufRemain + '</span>' +
                       '</div>' +
                       '<div class="ach-mh-roast is-muted">&ldquo;' + m.roast + '&rdquo;</div>' +
                       '</div></div>';
            }

            // Future
            return '<div class="ach-mh-item is-future" style="animation-delay:' + (i * 55) + 'ms">' +
                   '<div class="ach-mh-left"><div class="ach-mh-node is-future"></div>' + connector + '</div>' +
                   '<div class="ach-mh-body">' +
                   '<div class="ach-mh-top-row">' +
                   '<span class="ach-mh-amount is-future-amount">' + lbl + '</span>' +
                   '<span class="ach-mh-tier is-future-tier">' + tierLabel(m.tier) + '</span>' +
                   '</div></div></div>';
        }).join('');

        container.innerHTML = '<div class="ach-mh-list">' + items + '</div>';

        // Animate the "next" progress bar
        if (nextIdx >= 0) {
            var fillEl = document.getElementById(fillPrefix + '-fill-' + nextIdx);
            var mn     = milestones[nextIdx];
            if (fillEl && mn && mn.value > 0) animateBar(fillEl, (mn.current / mn.value) * 100, 420);
        }
    }

    function renderMilestoneTimeline() {
        var d = getData();
        renderMilestoneSection('ach-milestone-timeline', 'ach-mh-summary',        d.milestoneHistory,      'ach-mh');
        renderMilestoneSection('ach-journey-timeline',   'ach-journey-summary',   d.journeyMilestones,     'ach-jn');
        renderMilestoneSection('ach-monthly-best-timeline', 'ach-monthly-best-summary', d.monthlyBestMilestones, 'ach-mb');

        // FIRE section — only show if data available
        var fireSection = document.getElementById('ach-fire-section');
        if (fireSection) {
            var hasFire = d.fireMilestones && d.fireMilestones.length > 0;
            fireSection.style.display = hasFire ? '' : 'none';
            if (hasFire) renderMilestoneSection('ach-fire-timeline', 'ach-fire-summary', d.fireMilestones, 'ach-fi');
        }
    }

    // ═══════════════════════════════════════════════════════════
    // RENDER: BADGES GRID
    // ═══════════════════════════════════════════════════════════
    var activeFilter = 'all';

    function renderBadges(filter) {
        activeFilter = filter || 'all';
        var grid = document.getElementById('ach-badges-grid');
        if (!grid) return;

        var list = getData().badges;
        if (activeFilter === 'unlocked') list = list.filter(function(b) { return b.unlocked; });
        if (activeFilter === 'locked')   list = list.filter(function(b) { return !b.unlocked; });

        if (!list.length) {
            var msg = activeFilter === 'unlocked'
                ? 'Make your first deposit to start earning badges.'
                : "You've unlocked everything. Remarkable.";
            grid.innerHTML = '<div class="ach-empty">' +
                '<div class="ach-empty-icon">' + IC.star + '</div>' +
                '<div class="ach-empty-title">Nothing here</div>' +
                '<div class="ach-empty-sub">' + msg + '</div></div>';
            return;
        }

        grid.innerHTML = list.map(function(b, i) {
            var stateClass = b.unlocked ? 'is-unlocked' : 'is-locked';
            var newClass   = b.celebrate ? ' is-new' : '';
            var icon       = IC[b.icon] || IC.star;
            var delay      = i * 38;
            var color      = tierColor(b.tier);

            var progressHTML = '';
            if (!b.unlocked && b.progress !== undefined && b.progressMax) {
                var pct = Math.min((b.progress / b.progressMax) * 100, 100);
                var labelStr = b.progressMax >= 1000
                    ? fmtNum(b.progress) + ' / ' + fmtNum(b.progressMax)
                    : b.progress + ' / ' + b.progressMax;
                progressHTML = '<div class="ach-badge-prog">' +
                    '<div class="ach-badge-prog-track">' +
                    '<div class="ach-badge-prog-fill" data-pct="' + pct.toFixed(1) + '"' +
                    ' style="background:' + color + '; width:0"></div>' +
                    '</div>' +
                    '<div class="ach-badge-prog-label">' + labelStr + '</div>' +
                    '</div>';
            }

            return '<div class="ach-badge tier-' + b.tier + ' ' + stateClass + newClass + '"' +
                   ' style="animation-delay:' + delay + 'ms; --badge-color:' + color + '"' +
                   ' data-badge-id="' + b.id + '"' +
                   ' role="button" tabindex="0"' +
                   ' aria-label="' + b.name + ', ' + tierLabel(b.tier) + ', ' + (b.unlocked ? 'unlocked' : 'locked') + '">' +
                   '<div class="ach-badge-icon">' + icon + '</div>' +
                   '<div class="ach-badge-name">' + b.name + '</div>' +
                   '<div class="ach-badge-tier-label">' + tierLabel(b.tier) + '</div>' +
                   progressHTML + '</div>';
        }).join('');

        requestAnimationFrame(function() {
            grid.querySelectorAll('.ach-badge-prog-fill').forEach(function(el, idx) {
                var pct = parseFloat(el.dataset.pct);
                if (!isNaN(pct)) {
                    setTimeout(function() { el.style.width = pct + '%'; }, 300 + idx * 40);
                }
            });
        });

        requestAnimationFrame(function() {
            grid.querySelectorAll('.ach-badge.is-new').forEach(function(el) {
                setTimeout(function() { triggerCelebration(el); }, 900);
            });
        });
    }

    // ═══════════════════════════════════════════════════════════
    // RENDER: MONTHLY RECAP
    // ═══════════════════════════════════════════════════════════
    function renderMonthly() {
        var container = document.getElementById('ach-monthly-card');
        var lbl       = document.getElementById('ach-monthly-label');
        if (!container) return;
        var m = getData().monthly;
        if (lbl) lbl.textContent = m.month.toUpperCase() + ' IN REVIEW';

        var goalClass = m.depositGoalMet ? 'is-pos' : 'is-neg';
        var goalLabel = m.depositGoalMet ? 'Goal met' : 'Goal missed';
        var badgePill = m.badgesUnlocked > 0
            ? '<div class="ach-monthly-badge-pill">' + IC.award + '&nbsp;' + m.badgesUnlocked + ' badge' + (m.badgesUnlocked > 1 ? 's' : '') + '</div>'
            : '';

        // Active streaks section — show all streaks with value > 0
        var streaksList = Array.isArray(m.activeStreaks) ? m.activeStreaks : [];
        var streaksHTML = '';
        if (streaksList.length) {
            var rows = streaksList.map(function(s) {
                return '<div class="ach-monthly-streak-row">' +
                    '<div class="ach-monthly-streak-left">' +
                    '<div class="ach-monthly-streak-dot" style="background:' + s.color + '"></div>' +
                    '<span class="ach-monthly-streak-name">' + s.name + '</span>' +
                    '</div>' +
                    '<span class="ach-monthly-streak-val" style="color:' + s.color + '">' + s.value + '\u202f' + s.unit + '</span>' +
                    '</div>' +
                    (s.keepGoingHint ? '<div class="ach-monthly-streak-hint">' + s.keepGoingHint + '</div>' : '');
            }).join('');
            streaksHTML = '<div class="ach-monthly-streaks">' +
                '<div class="ach-monthly-streaks-label">Ongoing streaks</div>' +
                rows + '</div>';
        }

        container.innerHTML =
            '<div class="ach-monthly-card">' +
            '<div class="ach-monthly-head">' +
            '<div><div class="ach-monthly-headline">' + m.month + '</div>' +
            '<div class="ach-monthly-tagline">Your investment journal for the month.</div></div>' +
            badgePill + '</div>' +
            '<div class="ach-monthly-stats">' +
            '<div class="ach-monthly-stat">' +
            '<div class="ach-monthly-stat-label">Portfolio</div>' +
            '<div class="ach-monthly-stat-value ' + (m.portfolioChangePos ? 'is-pos' : 'is-neg') + '">' + m.portfolioChangePct + '</div>' +
            '</div>' +
            '<div class="ach-monthly-stat">' +
            '<div class="ach-monthly-stat-label">Deposited</div>' +
            '<div class="ach-monthly-stat-value">' + m.deposited + '</div>' +
            '<div class="ach-monthly-stat-sub ' + goalClass + '">' + goalLabel + ' · ' + m.depositGoal + '</div>' +
            '</div>' +
            '<div class="ach-monthly-stat">' +
            '<div class="ach-monthly-stat-label">Best holding</div>' +
            '<div class="ach-monthly-stat-value is-pos">' + m.bestHolding + '</div>' +
            '<div class="ach-monthly-stat-sub is-neg">' + m.worstHolding + '</div>' +
            '</div>' +
            '</div>' +
            streaksHTML +
            '<div class="ach-monthly-roast">' +
            '<span class="ach-monthly-roast-label">Roastfolio says</span>' +
            '&ldquo;' + m.roast + '&rdquo;</div>' +
            '</div>';
    }

    // ═══════════════════════════════════════════════════════════
    // STREAK DETAIL OVERLAY
    // ═══════════════════════════════════════════════════════════
    var _activeStreakId = null;

    function openStreakDetail(streakId) {
        var streak = getData().streaks.find(function(s) { return s.id === streakId; });
        if (!streak) return;
        _activeStreakId = streakId;
        _activeBadgeId  = null;

        var overlay = document.getElementById('ach-detail-overlay');
        var body    = document.getElementById('ach-detail-body');
        if (!overlay || !body) return;

        var color = streak.color || '#2b88cf';

        // Streak ring icon (mini svg)
        var ringIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:34px;height:34px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';

        // Start date display
        var startDisplay = streak.startMonth
            ? (function() {
                var p = String(streak.startMonth).split('-');
                if (p.length === 2) {
                    var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
                    return months[parseInt(p[1], 10) - 1] + ' ' + p[0];
                }
                return streak.startMonth;
            }())
            : null;

        var infoRows = '<div class="ach-streak-detail-info">' +
            '<div class="ach-streak-detail-row"><span class="ach-streak-detail-row-label">How</span>' +
            '<span>' + streak.hint + '</span></div>' +
            (startDisplay
                ? '<div class="ach-streak-detail-row"><span class="ach-streak-detail-row-label">Since</span>' +
                  '<span>' + startDisplay + '</span></div>'
                : '') +
            '<div class="ach-streak-detail-row"><span class="ach-streak-detail-row-label">Current</span>' +
            '<span style="font-weight:800;color:' + color + '">' + streak.value + '\u202f' + streak.unit + '</span></div>' +
            '<div class="ach-streak-detail-row"><span class="ach-streak-detail-row-label">Best</span>' +
            '<span>' + streak.best + '\u202f' + streak.unit + '</span></div>' +
            '<div class="ach-streak-detail-row"><span class="ach-streak-detail-row-label">Next goal</span>' +
            '<span>' + streak.nextMilestone + '\u202f' + streak.unit + '</span></div>' +
            '</div>';

        var keepGoingHTML = streak.keepGoingHint
            ? '<div class="ach-streak-keep-going"><strong>Keep it going</strong>' + streak.keepGoingHint + '</div>'
            : '';

        body.innerHTML =
            '<div class="ach-detail-badge-row">' +
            '<div class="ach-detail-icon is-unlocked" style="--badge-color:' + color + '; --badge-bg:rgba(255,255,255,0.04);color:' + color + '">' + ringIcon + '</div>' +
            '<div class="ach-detail-meta">' +
            '<div class="ach-detail-name" id="ach-detail-name">' + streak.name + '</div>' +
            '<div class="ach-detail-tier" style="color:' + color + '">' + streak.value + '\u202f' + streak.unit + ' streak</div>' +
            '</div></div>' +
            infoRows + keepGoingHTML;

        overlay.setAttribute('aria-hidden', 'false');
        overlay.classList.add('is-open');
        document.body.style.overflow = 'hidden';
    }

    // ═══════════════════════════════════════════════════════════
    // BADGE DETAIL OVERLAY
    // ═══════════════════════════════════════════════════════════
    var _activeBadgeId = null;

    function openDetail(badgeId) {
        var badge = getData().badges.find(function(b) { return b.id === badgeId; });
        if (!badge) return;
        _activeBadgeId = badgeId;

        var overlay = document.getElementById('ach-detail-overlay');
        var body    = document.getElementById('ach-detail-body');
        var color   = tierColor(badge.tier);
        var icon    = IC[badge.icon] || IC.star;

        var progressHTML = '';
        if (!badge.unlocked && badge.progress !== undefined) {
            var rawPct = (badge.progress / badge.progressMax) * 100;
            var pct    = Math.min(rawPct, 100);
            var label  = badge.progressMax >= 1000
                ? fmtNum(badge.progress) + ' / ' + fmtNum(badge.progressMax)
                : badge.progress + ' / ' + badge.progressMax;
            progressHTML =
                '<div class="ach-detail-prog-wrap">' +
                '<div class="ach-detail-prog-label">Progress &mdash; <strong>' + Math.round(pct) + '%</strong>' +
                '<span class="ach-detail-prog-count">' + label + '</span></div>' +
                '<div class="ach-detail-prog-track">' +
                '<div class="ach-detail-prog-fill" id="ach-dpfill"' +
                ' style="background:' + color + '; width:0"></div>' +
                '</div></div>';
        }

        var unlockedSection = badge.unlocked
            ? '<div class="ach-detail-row"><span class="ach-detail-row-label">Unlocked</span>' +
              '<span class="ach-detail-row-val">' + (badge.unlockedOn || '—') + '</span></div>'
            : '<div class="ach-detail-row"><span class="ach-detail-row-label">Requires</span>' +
              '<span class="ach-detail-row-val">' + badge.req + '</span></div>' + progressHTML;

        var descHTML = badge.desc || badge.req
            ? '<div class="ach-detail-desc">' + (badge.desc || badge.req) + '</div>'
            : '';
        var roastHTML = badge.roast
            ? '<div class="ach-detail-roast">&ldquo;' + badge.roast + '&rdquo;</div>'
            : '';

        body.innerHTML =
            '<div class="ach-detail-badge-row">' +
            '<div class="ach-detail-icon' + (badge.unlocked ? ' is-unlocked' : '') + '"' +
            ' style="--badge-color:' + color + '; --badge-bg:rgba(255,255,255,0.04)">' + icon + '</div>' +
            '<div class="ach-detail-meta">' +
            '<div class="ach-detail-name" id="ach-detail-name">' + badge.name + '</div>' +
            '<div class="ach-detail-tier" style="color:' + color + '">' + tierLabel(badge.tier) + '</div>' +
            '</div></div>' +
            descHTML + roastHTML +
            unlockedSection;

        overlay.setAttribute('aria-hidden', 'false');
        overlay.classList.add('is-open');
        document.body.style.overflow = 'hidden';

        if (!badge.unlocked && badge.progress !== undefined) {
            var p2 = Math.min((badge.progress / badge.progressMax) * 100, 100);
            animateBar(document.getElementById('ach-dpfill'), p2, 140);
        }
    }

    function closeDetail() {
        var overlay = document.getElementById('ach-detail-overlay');
        if (!overlay) return;
        overlay.classList.remove('is-open');
        overlay.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        _activeBadgeId  = null;
        _activeStreakId = null;
    }

    // ═══════════════════════════════════════════════════════════
    // PREMIUM CELEBRATION  — canvas arc particles
    // ═══════════════════════════════════════════════════════════
    function triggerCelebration(badgeEl) {
        if (!badgeEl) return;
        var canvas = document.getElementById('ach-celebrate-canvas');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');

        var rect = badgeEl.getBoundingClientRect();
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
        canvas.style.display = 'block';

        var cx = rect.left + rect.width  / 2;
        var cy = rect.top  + rect.height / 2;

        var rawColor = (getComputedStyle(badgeEl).getPropertyValue('--badge-color') || '').trim() || '#2b88cf';

        var COUNT     = 18;
        var particles = [];
        for (var i = 0; i < COUNT; i++) {
            var angle = (i / COUNT) * Math.PI * 2;
            var speed = 2.0 + Math.random() * 2.6;
            particles.push({
                x: cx, y: cy,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                size:  2.2 + Math.random() * 2.8,
                color: rawColor,
                alpha: 1,
            });
        }

        badgeEl.classList.add('is-celebrating');
        setTimeout(function() { badgeEl.classList.remove('is-celebrating'); }, 1000);

        var startTime = performance.now();
        var DURATION  = 1000;
        var rafId;

        function draw(now) {
            var elapsed = now - startTime;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            var anyAlive = false;

            particles.forEach(function(p) {
                if (p.alpha <= 0) return;
                anyAlive  = true;
                p.x      += p.vx;
                p.y      += p.vy;
                p.vy     += 0.075;
                p.vx     *= 0.97;
                p.alpha   = Math.max(0, 1 - (elapsed / DURATION) * 1.5);

                ctx.globalAlpha = p.alpha;
                ctx.fillStyle   = p.color;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.size * p.alpha, 0, Math.PI * 2);
                ctx.fill();
            });

            if (anyAlive && elapsed < DURATION) {
                rafId = requestAnimationFrame(draw);
            } else {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                canvas.style.display = 'none';
                cancelAnimationFrame(rafId);
            }
        }

        rafId = requestAnimationFrame(draw);
    }

    // ═══════════════════════════════════════════════════════════
    // XP BREAKDOWN OVERLAY
    // ═══════════════════════════════════════════════════════════
    function openXPBreakdown() {
        var result    = getData();
        var breakdown = result.xp && result.xp.breakdown;
        if (!breakdown || !breakdown.length) return;

        // Aggregate: bucket "Monthly deposit (YYYY-MM)" etc. by stripping trailing date suffix
        var groups = {};
        breakdown.forEach(function(item) {
            var key = item.label.replace(/\s+\(\d{4}-\d{2}\)$/, '');
            if (!groups[key]) groups[key] = { amount: 0, count: 0 };
            groups[key].amount += item.amount;
            groups[key].count++;
        });

        var sorted = Object.keys(groups).map(function(k) {
            return { label: k, amount: groups[k].amount, count: groups[k].count };
        }).sort(function(a, b) { return b.amount - a.amount; });

        var total = result.xp.current;
        var color = '#2b88cf';

        var rows = sorted.map(function(g) {
            var countStr = g.count > 1 ? ' &times;' + g.count : '';
            return '<div class="ach-detail-row">' +
                   '<span class="ach-detail-row-label">' + g.label + countStr + '</span>' +
                   '<span class="ach-detail-row-val">+' + fmtNum(g.amount) + ' XP</span>' +
                   '</div>';
        }).join('');

        var body = document.getElementById('ach-detail-body');
        if (!body) return;

        body.innerHTML =
            '<div class="ach-detail-badge-row">' +
            '<div class="ach-detail-icon is-unlocked" style="--badge-color:' + color + '; --badge-bg:rgba(43,136,207,0.12)">' + IC.zap + '</div>' +
            '<div class="ach-detail-meta">' +
            '<div class="ach-detail-name" id="ach-detail-name">XP Breakdown</div>' +
            '<div class="ach-detail-tier" style="color:' + color + '">' + fmtNum(total) + ' XP total</div>' +
            '</div></div>' +
            '<div class="ach-detail-desc">All sources contributing to your XP score.</div>' +
            rows;

        var overlay = document.getElementById('ach-detail-overlay');
        if (!overlay) return;
        overlay.setAttribute('aria-hidden', 'false');
        overlay.classList.add('is-open');
        document.body.style.overflow = 'hidden';
    }

    // ═══════════════════════════════════════════════════════════
    // BIND INTERACTIONS
    // ═══════════════════════════════════════════════════════════
    function bindInteractions() {
        // XP card → breakdown overlay
        var xpCard = document.getElementById('ach-xp-card');
        if (xpCard) {
            xpCard.addEventListener('click', openXPBreakdown);
            xpCard.style.cursor = 'pointer';
        }

        // Streak cards → streak detail overlay
        var streaksScroll = document.getElementById('ach-streaks-scroll');
        if (streaksScroll) {
            streaksScroll.addEventListener('click', function(e) {
                var card = e.target.closest('.ach-streak-card');
                if (card) openStreakDetail(card.dataset.streak);
            });
            streaksScroll.querySelectorAll('.ach-streak-card').forEach(function(c) {
                c.style.cursor = 'pointer';
            });
        }

        document.querySelectorAll('.ach-filter-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.ach-filter-btn').forEach(function(b) {
                    b.classList.remove('is-active');
                    b.setAttribute('aria-selected', 'false');
                });
                btn.classList.add('is-active');
                btn.setAttribute('aria-selected', 'true');
                renderBadges(btn.dataset.filter);
            });
        });

        var grid = document.getElementById('ach-badges-grid');
        if (grid) {
            grid.addEventListener('click', function(e) {
                var badge = e.target.closest('.ach-badge');
                if (badge) openDetail(badge.dataset.badgeId);
            });
            grid.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    var badge = e.target.closest('.ach-badge');
                    if (badge) { e.preventDefault(); openDetail(badge.dataset.badgeId); }
                }
            });
        }

        var backdrop = document.getElementById('ach-detail-backdrop');
        if (backdrop) backdrop.addEventListener('click', closeDetail);

        var sheet = document.getElementById('ach-detail-sheet');
        if (sheet) {
            var _sy = 0;
            sheet.addEventListener('touchstart', function(e) { _sy = e.touches[0].clientY; }, { passive: true });
            sheet.addEventListener('touchend',   function(e) {
                if (e.changedTouches[0].clientY - _sy > 64) closeDetail();
            }, { passive: true });
        }

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && (_activeBadgeId || _activeStreakId)) closeDetail();
        });

        window.addEventListener('resize', function() {
            var canvas = document.getElementById('ach-celebrate-canvas');
            if (canvas && canvas.style.display !== 'none') {
                canvas.width  = window.innerWidth;
                canvas.height = window.innerHeight;
            }
        }, { passive: true });
    }

    // ═══════════════════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════════════════
    function renderAll() {
        renderXP();
        renderStreaks();
        renderMilestoneTimeline();
        renderBadges(activeFilter);
        renderMonthly();
    }

    function init() {
        renderAll();
        bindInteractions();
    }

    // Re-render whenever XPEngine finishes a computation
    window.addEventListener('xpEngineReady', function() {
        renderAll();
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window._achievements = { triggerCelebration: triggerCelebration, renderBadges: renderBadges, renderAll: renderAll };

}());
