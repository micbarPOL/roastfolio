window.submitRoastReaction = function(reaction, event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    if (!window.ROAST_DATA || !window.RoastTracker) return;
    
    // Prevent double submission spam
    if (window._roastFeedbackSubmitting) return;
    window._roastFeedbackSubmitting = true;

    const rd = window.ROAST_DATA;
    let eventType = 'roast_reacted_negative';
    if (reaction === 'good') eventType = 'roast_reacted_positive';
    
    window.RoastTracker.recordEvent({
        eventType: eventType,
        reaction: reaction,
        templateId: rd.templateId,
        scenarioKey: rd.scenarioKey,
        portfolioChange: rd.portfolioChange,
        benchmarkChange: rd.benchmarkChange,
        bestAsset: rd.bestAsset,
        worstAsset: rd.worstAsset
    }).then(res => {
        window._roastFeedbackSubmitting = false;
        if (res && res.ok) {
            const containers = document.querySelectorAll('.roast-reactions');
            containers.forEach(btnContainer => {
                const prevHtml = btnContainer.innerHTML;
                btnContainer.innerHTML = '<span style="font-size:12px; color:#27ae60; font-weight:600;">Feedback saved! Thanks.</span>';
                setTimeout(() => {
                    if (btnContainer) btnContainer.innerHTML = prevHtml;
                }, 3000);
            });
        }
    }).catch(err => {
        window._roastFeedbackSubmitting = false;
    });
};

// Local logo files (place PNG/SVG in src/data/logos/ with these exact names)
const COMPANY_LOCAL_LOGOS = {
    'XTB':                         'data/logos/xtb.png',
    'RAINBOW (RBW)':               'data/logos/RAINBOW.png',
    'MOBRUK (MBR)':                'data/logos/MOBRUK.png',
    'CREOTECH (CRI)':              'data/logos/CREOTECH.png',
    'CDPROJEKT (CDR)':             'data/logos/CDPROJEKT.png',
    'Meta Platforms, Inc. (META)': 'data/logos/META.png',
    'Bitcoin (BTC)':               'data/logos/Bitcoin.png',
};

const COMPANY_COLORS = {
    'XTB':                         '#e74c3c',
    'RAINBOW (RBW)':               '#e67e22',
    'MOBRUK (MBR)':                '#27ae60',
    'CREOTECH (CRI)':              '#2980b9',
    'CDPROJEKT (CDR)':             '#8e44ad',
    'Meta Platforms, Inc. (META)': '#1877f2',
    'Bitcoin (BTC)':               '#f7931a',
    'Gotówka (konto)':             '#95a5a6',
    'Cash (konto)':                '#95a5a6',
    'Cash':                        '#95a5a6',
};

function companyLogoHtml(name) {
    const ticker = (name.match(/\(([^)]+)\)$/) || [])[1] || name.slice(0, 3).toUpperCase();
    const color = COMPANY_COLORS[name] || '#35424a';
    const logoPath = COMPANY_LOCAL_LOGOS[name];

    if (logoPath) {
        return `<img src="${logoPath}" alt="${ticker}"
            style="width:28px;height:28px;object-fit:contain;border-radius:4px;margin-right:8px;flex-shrink:0;"
            onerror="this.outerHTML=\`<span style='display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:${color};color:white;font-size:9px;font-weight:bold;margin-right:8px;flex-shrink:0;'>${ticker.slice(0,3)}</span>\`">`;
    }
    // No logo file — always show badge
    return `<span style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:${color};color:white;font-size:9px;font-weight:bold;margin-right:8px;flex-shrink:0;">${ticker.slice(0,3)}</span>`;
}

function getStableGaugeComment(signature, pool) {
    if (!pool || !pool.length) return '';
    const state = window._gaugeCommentState || {};
    if (state[signature]) {
        return state[signature];
    }
    const message = pool[Math.floor(Math.random() * pool.length)];
    state[signature] = message;
    window._gaugeCommentState = state;
    return message;
}

const ATH_CELEBRATION_NOTES = [
    "New ATH unlocked. Wall Street would like a word with your portfolio manager.",
    "Fresh all-time high. Somewhere a benchmark just muttered, 'well, that's rude.'",
    "ATH achieved. Please accept this totally serious institutional confetti.",
    "Another record high. The portfolio has entered its main-character era.",
    "New All-Time High. Don't get overly excited — even a blind squirrel occasionally stumbles across a golden acorn.",
    "Fresh record high. Now brace yourself for the inevitable 40% plummet that always follows your unearned confidence.",
    "You've hit an all-time high. Do try not to celebrate by immediately buying something speculative and utterly stupid.",
    "Record portfolio value achieved. Enjoy the view from the top before gravity remembers you're the one steering this ship.",
    "An all-time high! Astonishing what market inflation and sheer dumb luck can accomplish when left unattended.",
    "Portfolio at record peak. Please resist the urge to quit your day job; this was pure market momentum, not financial genius.",
    "New ATH reached. A triumph of passive waiting over active incompetence.",
    "You're officially richer than ever. Statistically speaking, your downfall begins precisely now.",
    "Peak portfolio value. Somewhere, a hedge fund manager is weeping into their silk handkerchief at your fluke success.",
    "All-Time High unlocked. Try not to brag at dinner — nobody likes a smug amateur whose luck is about to run out.",
    "Record portfolio level. It’s magnificent, really — like a house of cards built on a bouncy castle.",
    "New ATH. Nature is beautiful: even a portfolio managed with zero strategy eventually accidentally hits the ceiling.",
    "You've reached the summit. Do hold onto something solid — the drop back to reality is usually quite steep.",
    "All-time high confirmed. Enjoy the champagne today, because tomorrow the taxman and mean-reversion are coming for you.",
    "Peak net worth recorded. Take a screenshot now so you have something to cry over during the next bear market.",
    "New ATH achieved. The market gave you a gift today — try not to return it tomorrow with interest."
];

// Cached ATH derived from actual daily snapshots (set by loadSnapshotAth)
window._SNAPSHOT_ATH = null;
window._WALLET_SNAPSHOT_ATHS = {};

async function loadSnapshotAth() {
    try {
        if (typeof PortfolioClient === 'undefined' || !PortfolioClient.listSnapshots) return;

        const portfoliosResp = await PortfolioClient.listPortfolios().catch(() => ({ portfolios: [] }));
        const portfolios = Array.isArray(portfoliosResp?.portfolios) ? portfoliosResp.portfolios : [];
        const pids = ['summary', ...portfolios.map(p => p.portfolioId).filter(id => id && id.toLowerCase() !== 'summary')];

        const snapshotCalls = await Promise.all(
            pids.map(pid => PortfolioClient.listSnapshots(pid).catch(() => ({ snapshots: [] })))
        );

        snapshotCalls.forEach((snapshotData, idx) => {
            const pid = pids[idx];
            const snapshots = snapshotData?.snapshots || [];
            if (!snapshots.length) return;

            let peakVal = 0, peakDate = '';
            for (const s of snapshots) {
                const v = Number(s.portfolioValue || 0);
                if (v > peakVal) {
                    peakVal = v;
                    peakDate = String(s.snapshotDate || '').slice(0, 10);
                }
            }
            if (peakVal > 0) {
                const athObj = { athValue: peakVal, athDate: peakDate, athSource: 'AUTO' };
                if (pid === 'summary') {
                    window._SNAPSHOT_ATH = athObj;
                } else {
                    window._WALLET_SNAPSHOT_ATHS[pid] = athObj;
                    window._WALLET_SNAPSHOT_ATHS[pid.toUpperCase()] = athObj;
                    window._WALLET_SNAPSHOT_ATHS[pid.toLowerCase()] = athObj;
                }
            }
        });

        if (typeof updateDashboard === 'function') updateDashboard();
        if (typeof renderAthCelebration === 'function') renderAthCelebration('ath-celebration');
        if (typeof renderWalletCards === 'function') renderWalletCards();
    } catch (e) {
        console.warn('loadSnapshotAth failed:', e);
    }
}

function getRecordedSnapshotAth(baseAthInfo) {
    // Use snapshot-derived ATH if available (most accurate)
    const snapshotAth = window._SNAPSHOT_ATH;

    // Start with the base ATH from backend
    let recAth = baseAthInfo && baseAthInfo.athValue != null ? Number(baseAthInfo.athValue) : 0;
    let recDate = baseAthInfo && baseAthInfo.athDate ? baseAthInfo.athDate : '';
    let athSource = baseAthInfo && baseAthInfo.athSource ? baseAthInfo.athSource : 'AUTO';

    // Override with snapshot-derived peak if it's higher
    if (snapshotAth && Number(snapshotAth.athValue) > recAth) {
        recAth = Number(snapshotAth.athValue);
        recDate = snapshotAth.athDate || recDate;
        athSource = 'AUTO';
    }

    if (!recAth) return baseAthInfo || null;
    return { athValue: recAth, athDate: recDate, athSource: athSource };
}

function isPortfolioAtNewAth() {
    const recordedInfo = getRecordedSnapshotAth(window.PORTFOLIO_ATH);
    const current = Number(window.PORTFOLIO_TOTAL_VALUE || 0);
    const dailyPct = Number(window.PORTFOLIO_DAILY_CHANGE_PCT || 0);

    if (!current || dailyPct < 0 || !recordedInfo || !recordedInfo.athValue) return false;

    const baseAthVal = Number(recordedInfo.athValue);
    // Portfolio is at new ATH only if current live value meets/exceeds recorded ATH peak
    return current >= baseAthVal - 0.05;
}

function fireworkBurstMarkup(prefix, burstIndex) {
    const directions = [
        { x: 0, y: -26 }, { x: 18, y: -18 }, { x: 26, y: 0 }, { x: 18, y: 18 },
        { x: 0, y: 26 }, { x: -18, y: 18 }, { x: -26, y: 0 }, { x: -18, y: -18 },
    ];
    return `
        <span class="ath-firework-burst ath-firework-burst-${burstIndex}">
            ${directions.map((direction, particleIndex) => `
                <span class="ath-firework-particle ath-firework-particle-${particleIndex + 1}"
                    style="--spark-x:${direction.x}px;--spark-y:${direction.y}px;"></span>
            `).join('')}
        </span>
    `;
}

function athCelebrationMarkup(title, note, gain) {
    const metaText = (gain && gain > 10)
        ? `Up ${gain.toLocaleString('pl-PL', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} PLN above previous recorded peak.`
        : `Portfolio is currently trading at its peak all-time value today.`;

    return `
        <div class="ath-celebration-inner">
            <div class="ath-hologram" aria-hidden="true">
                <span class="ath-orbit ath-orbit-1"></span>
                <span class="ath-orbit ath-orbit-2"></span>
                <span class="ath-orbit ath-orbit-3"></span>
                <span class="ath-record-core">ATH</span>
                <span class="ath-scanline"></span>
            </div>
            <div class="ath-fireworks" aria-hidden="true">
                ${fireworkBurstMarkup('ath', 1)}
                ${fireworkBurstMarkup('ath', 2)}
                ${fireworkBurstMarkup('ath', 3)}
            </div>
            <div class="ath-celebration-copy">
                <div class="ath-celebration-badge">New All-Time High</div>
                <div class="ath-celebration-title">${title}</div>
                <div class="ath-celebration-note">${note}</div>
                <div class="ath-celebration-meta">${metaText}</div>
            </div>
        </div>
    `;
}

function renderAthCelebration(targetId) {
    const el = document.getElementById(targetId);
    if (!el) return;
    if (!isPortfolioAtNewAth()) {
        el.hidden = true;
        el.innerHTML = '';
        return;
    }

    const athInfo = window.PORTFOLIO_ATH || {};
    const current = Number(window.PORTFOLIO_TOTAL_VALUE || 0);
    const athValue = Number(athInfo.athValue || 0);
    const note = getStableGaugeComment(
        `ath:${current.toFixed(2)}:${athValue.toFixed(2)}:${athInfo.athDate || ''}`,
        ATH_CELEBRATION_NOTES,
    );
    const gain = current - athValue;

    el.hidden = false;
    el.innerHTML = athCelebrationMarkup('Portfolio broke its own ceiling.', note, gain);
}

// Parameterized ATH renderer for arbitrary wallet slides
function renderAthCelebrationFor(targetId, athInfo, currentValue, dailyPct) {
    const el = document.getElementById(targetId);
    if (!el) return;
    if (dailyPct < 0) {
        el.hidden = true;
        el.innerHTML = '';
        return;
    }
    const current = Number(currentValue || 0);
    const athValue = Number(athInfo && athInfo.athValue ? athInfo.athValue : 0);

    let todayDate = '';
    try {
        todayDate = new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Warsaw' });
    } catch (e) {
        todayDate = new Date().toISOString().slice(0, 10);
    }

    const isTodayAth = (athInfo && athInfo.athDate === todayDate) || (athValue > 0 && current >= athValue - 10);
    if (!isTodayAth) {
        el.hidden = true;
        el.innerHTML = '';
        return;
    }

    const note = getStableGaugeComment(
        `ath:${current.toFixed(2)}:${athValue.toFixed(2)}:${athInfo && athInfo.athDate || ''}`,
        ATH_CELEBRATION_NOTES,
    );
    const gain = current - athValue;

    el.hidden = false;
    el.innerHTML = athCelebrationMarkup('Wallet broke its own ceiling.', note, gain);
}

function initializeDashboard() {
    renderSummaryCards();
    if (window._gaugeDataReady) {
        renderGauge('gaugeChart', PORTFOLIO_DAILY_CHANGE_PCT, null, null,
            window.BENCHMARK_DAILY_PCT ?? (typeof WIG_DAILY_PCT !== 'undefined' ? WIG_DAILY_PCT : null));
    } else {
        const canvas = document.getElementById('gaugeChart');
        if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width || 0, canvas.height || 0);
    }
    renderAthCelebration('dash-ath-celebration');
    renderWalletCards();
    renderDailyBreakdown();
    renderMarketIndexCarousel();
    // Load snapshot-derived ATH asynchronously; re-renders drawdown + banner when ready
    loadSnapshotAth();
}

// Exposed for live-data.js to re-render after fresh prices arrive
function renderDashboard() {
    _renderEmptyState();
    renderSummaryCards();
    // Re-render main gauge.
    // If _gaugeAnimationPending is set (animation is about to take over) just clear the canvas
    // so the animation starts from blank — this prevents a one-frame flash of the final value.
    const gCanvas = document.getElementById('gaugeChart');
    if (gCanvas) { gCanvas.getContext('2d').clearRect(0, 0, gCanvas.width, gCanvas.height); }
    if (window._gaugeAnimationPending) {
        window._gaugeAnimationPending = false; // consumed — animation will draw on next rAF
    } else if (window._gaugeDataReady) {
        renderGauge('gaugeChart', PORTFOLIO_DAILY_CHANGE_PCT, null, null,
            window.BENCHMARK_DAILY_PCT ?? (typeof WIG_DAILY_PCT !== 'undefined' ? WIG_DAILY_PCT : null));
    }
    renderAthCelebration('dash-ath-celebration');
    // Rebuild carousel and wallet cards from dynamic wallet list
    rebuildCarousel();
    renderWalletCards();
    renderDailyBreakdown();
    renderMarketIndexCarousel();
}

function _renderEmptyState() {
    if (window.__walletBootstrapState !== 'empty') {
        const existing = document.getElementById('dash-empty-state');
        if (existing) existing.style.display = 'none';
        return;
    }

    const isEmpty = (
        (!window.PORTFOLIO_DATA || window.PORTFOLIO_DATA.length === 0) &&
        (!window.PORTFOLIO_TOTAL_VALUE || window.PORTFOLIO_TOTAL_VALUE === 0)
    );

    let el = document.getElementById('dash-empty-state');

    if (!isEmpty) {
        if (el) el.style.display = 'none';
        return;
    }

    if (!el) {
        el = document.createElement('div');
        el.id = 'dash-empty-state';
        const dashTab = document.getElementById('tab-dashboard');
        if (dashTab) dashTab.prepend(el);
    }

    el.style.display = 'flex';
    el.innerHTML = `
        <div class="empty-state-card">
            <div class="empty-state-icon">📊</div>
            <h2 class="empty-state-title">Your portfolio is empty</h2>
            <p class="empty-state-desc">
                Add your first portfolio and holdings to start tracking your investments,
                see live prices, daily performance, and sarcastic commentary.
            </p>
            <button class="empty-state-btn" onclick="openManageModal()">
                ⚙️ Set up your portfolio
            </button>
        </div>
    `;
}

function renderSummaryCards() {
    const totalEl    = document.getElementById('dash-total-value');
    const dailyPlnEl = document.getElementById('dash-daily-pln');
    const drawdownEl = document.getElementById('dash-drawdown');

    if (typeof PORTFOLIO_DAILY_CHANGE_PLN === 'undefined') return;
    const pln   = PORTFOLIO_DAILY_CHANGE_PLN;
    const pct   = Number(PORTFOLIO_DAILY_CHANGE_PCT || 0);
    const color = pln >= 0 ? '#27ae60' : '#c0392b';
    const sign  = pln >= 0 ? '+' : '';

    if (totalEl && typeof PORTFOLIO_TOTAL_VALUE !== 'undefined') {
        totalEl.textContent = PORTFOLIO_TOTAL_VALUE.toLocaleString('pl-PL', { minimumFractionDigits: 2 }) + ' PLN';
    }
    if (dailyPlnEl) {
        dailyPlnEl.innerHTML =
            `<span class="dash-daily-main" style="color:${color};">${sign}${pln.toLocaleString('pl-PL', { minimumFractionDigits: 2 })} PLN</span>` +
            `<span class="dash-daily-pct" style="color:${color};">(${sign}${pct.toFixed(2)}%)</span>`;
    }

    if (drawdownEl) {
        const athInfo = getRecordedSnapshotAth(window.PORTFOLIO_ATH);
        if (!athInfo || !athInfo.athValue) {
            drawdownEl.innerHTML =
                `<div class="ath-title">From All-Time High</div>` +
                `<span style="color:#64748b;font-size:0.95rem;font-family:monospace;">ATH pending nightly snapshot</span>`;
        } else {
            const recordedAth = Number(athInfo.athValue || 0);
            const athDate = athInfo.athDate || '';
            const current = Number(PORTFOLIO_TOTAL_VALUE || 0);
            const diffPLN = current - recordedAth;
            const diffPct = recordedAth ? ((diffPLN / recordedAth) * 100).toFixed(2) : '0.00';
            const athFormatted = recordedAth.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            const dateStr = athDate ? ` (${athDate})` : '';

            if (diffPLN > 0.01) {
                const gainSign = diffPLN > 0 ? '+' : '';
                drawdownEl.innerHTML =
                    `<div class="ath-title">From All-Time High</div>` +
                    `<span class="ath-pct" style="color:#27ae60;">+${diffPct}%</span>` +
                    `<span class="ath-pln" style="color:#27ae60;">(${gainSign}${diffPLN.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN above ATH)</span>` +
                    `<div class="ath-date">Last recorded ATH: ${athFormatted} PLN${dateStr}</div>`;
            } else if (diffPLN >= -0.01) {
                drawdownEl.innerHTML =
                    `<div class="ath-title">From All-Time High</div>` +
                    `<span class="ath-pct" style="color:#27ae60;">At All-Time High!</span>` +
                    `<span class="ath-pln" style="color:#27ae60;">(0 PLN drawdown)</span>` +
                    `<div class="ath-date">Last recorded ATH: ${athFormatted} PLN${dateStr}</div>`;
            } else {
                let color = '#c0392b';
                drawdownEl.innerHTML =
                    `<div class="ath-title">From All-Time High</div>` +
                    `<span class="ath-pct" style="color:${color};">${diffPct}%</span>` +
                    `<span class="ath-pln" style="color:${color};">(${diffPLN.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN)</span>` +
                    `<div class="ath-date">Last recorded ATH: ${athFormatted} PLN${dateStr}</div>`;
            }
        }
    }

    if (typeof renderDashSparkline === 'function') {
        renderDashSparkline();
    }
}

function renderGauge(canvasId, value, width, height, benchmarkValue, _animProgress) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // Remove fetching state from the parent card to hide the loader and reveal the gauge wrapper
    const cardEl = canvas.closest('.dash-gauge-card, .dash-gauge-carousel-card');
    if (cardEl && cardEl.classList.contains('is-fetching-data')) {
        cardEl.classList.remove('is-fetching-data');
    }

    const clamped = Math.max(-2, Math.min(2, value));

    // Animation progress for each needle (0→1); default 1 = final position for normal renders
    const _CENTER = Math.PI * 1.5; // 0% position (straight up)
    const _portP = (_animProgress && _animProgress.portfolio != null) ? _animProgress.portfolio : 1;
    const _bmP   = (_animProgress && _animProgress.benchmark  != null) ? _animProgress.benchmark  : 1;
    const _pulseP = (_animProgress && _animProgress.pulse != null) ? _animProgress.pulse : 1;

    function _animateBenchmarkTooltip(tooltipEl) {
        if (!tooltipEl) return;
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        // Force replay so it animates on each meaningful update.
        tooltipEl.classList.remove('bm-reveal');
        void tooltipEl.offsetWidth;
        tooltipEl.classList.add('bm-reveal');
    }

    // Use explicit dimensions or fallback to 400x220 to prevent small sizes
    // if the parent element is hidden during rendering.
    canvas.width  = width  || (canvas.parentElement.clientWidth > 0 ? canvas.parentElement.clientWidth : 400);
    canvas.height = height || 220;

    const ctx = canvas.getContext('2d');
    const cx = canvas.width / 2;
    const isCompact = canvas.height < 180 || canvas.width < 340;
    const bottomPad = isCompact ? 22 : 30;
    const sidePad = isCompact ? 22 : 30;
    const labelOffset = isCompact ? 12 : 18;
    const topPad = isCompact ? 22 : 12;
    const cy = canvas.height - bottomPad;
    const r = Math.min(cx - sidePad, cy - topPad);
    const arcWidth = Math.max(isCompact ? 10 : 12, canvas.height * (isCompact ? 0.11 : 0.12));
    const trackRadius = r - arcWidth * 0.22;
    const trackWidth = Math.max(5, Math.min(8, arcWidth * 0.42));
    const signalRadius = trackRadius - trackWidth * 1.7;
    const isDarkTheme = typeof window.isRoastfolioDark === 'function'
        ? window.isRoastfolioDark()
        : document.documentElement.getAttribute('data-theme') === 'dark';
    const isLightTheme = !isDarkTheme;
    const trackColor = isLightTheme ? 'rgba(15, 23, 42, 0.18)' : 'rgba(148, 163, 184, 0.30)';
    const tickColor = isLightTheme ? 'rgba(15, 23, 42, 0.30)' : 'rgba(226, 232, 240, 0.48)';
    const labelColor = isLightTheme ? 'rgba(51, 65, 85, 0.64)' : 'rgba(148, 163, 184, 0.72)';
    const hubFill = isLightTheme ? '#f8fafc' : '#0f172a';
    const diffGreen = '#22c55e';
    const diffRed = '#ff3b6b';
    const benchmarkMarkerColor = isLightTheme ? 'rgba(15, 23, 42, 0.82)' : 'rgba(248, 250, 252, 0.92)';
    const valueTextColor = isLightTheme ? 'rgba(15, 23, 42, 0.94)' : '#a7f3ff';
    const valueTextGlow = isLightTheme ? 'rgba(15, 23, 42, 0.18)' : 'rgba(34, 211, 238, 0.72)';
    const needleColor = isLightTheme ? 'rgba(15, 23, 42, 0.92)' : '#ecfeff';
    const needleOutline = isLightTheme ? 'rgba(248, 250, 252, 0.9)' : 'rgba(8, 47, 73, 0.95)';
    const needleGlow = isLightTheme ? 'rgba(14, 165, 233, 0.28)' : 'rgba(34, 211, 238, 0.78)';
    const labelFont = canvas.height < 180
        ? "500 9px 'SF Mono', 'Fira Code', 'Consolas', monospace"
        : "500 11px 'SF Mono', 'Fira Code', 'Consolas', monospace";
    const valueFont = canvas.height < 180
        ? "600 14px 'SF Mono', 'Fira Code', 'Consolas', monospace"
        : "600 22px 'SF Mono', 'Fira Code', 'Consolas', monospace";
    function valueToGaugeAngle(rawValue, progress) {
        const pct = Math.max(-2, Math.min(2, rawValue));
        const boundedProgress = Math.max(0, Math.min(1, progress == null ? 1 : progress));
        const targetAngle = Math.PI + ((pct + 2) / 4) * Math.PI;
        return _CENTER + (targetAngle - _CENTER) * boundedProgress;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, trackRadius, Math.PI, Math.PI * 2);
    ctx.strokeStyle = trackColor;
    ctx.lineWidth = trackWidth;
    ctx.lineCap = 'round';
    ctx.stroke();
    ctx.restore();

    const neonScaleSegments = [
        '#ff3b6b',
        '#ff5d4d',
        '#ff8a3d',
        '#facc15',
        '#bef264',
        '#86efac',
        '#4ade80',
        '#22c55e',
    ];
    neonScaleSegments.forEach((color, i) => {
        const startAngle = Math.PI + (i / neonScaleSegments.length) * Math.PI;
        const endAngle = Math.PI + ((i + 1) / neonScaleSegments.length) * Math.PI;

        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, trackRadius, startAngle + 0.018, endAngle - 0.018);
        ctx.strokeStyle = color;
        ctx.lineWidth = Math.max(isCompact ? 5 : 6, trackWidth * 1.05);
        ctx.lineCap = 'round';
        ctx.globalAlpha = isLightTheme ? 0.86 : 0.96;
        ctx.shadowColor = color;
        ctx.shadowBlur = isLightTheme ? 9 : 15;
        ctx.stroke();
        ctx.restore();
    });

    const total = 8;
    for (let i = 1; i < total; i++) {
        const angle = Math.PI + (i / total) * Math.PI;
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(angle) * (trackRadius - trackWidth * 0.82), cy + Math.sin(angle) * (trackRadius - trackWidth * 0.82));
        ctx.lineTo(cx + Math.cos(angle) * (trackRadius + trackWidth * 0.82), cy + Math.sin(angle) * (trackRadius + trackWidth * 0.82));
        ctx.strokeStyle = tickColor;
        ctx.lineWidth = isCompact ? 1.2 : 1.6;
        ctx.stroke();
    }

    ctx.save();
    ctx.font = labelFont;
    ctx.fillStyle = labelColor;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const scaleLabels = ['-2%', '0%', '+2%'];
    const scaleAngles = [Math.PI, Math.PI * 1.5, Math.PI * 2];
    scaleAngles.forEach((angle, i) => {
        const lx = cx + Math.cos(angle) * (trackRadius + labelOffset);
        const labelLift = i === 1 ? (isCompact ? -8 : -10) : 0;
        const ly = cy + Math.sin(angle) * (trackRadius + labelOffset) + (isCompact ? 3 : 4) + labelLift;
        ctx.fillText(scaleLabels[i], lx, ly);
    });
    ctx.restore();

    // Benchmark needle (WIG) — drawn first so main needle renders on top
    if (benchmarkValue != null) {
        const bmClamped    = Math.max(-2, Math.min(2, benchmarkValue));
        const bmAngle      = valueToGaugeAngle(bmClamped, _bmP);
        const portfolioAngleForDiff = valueToGaugeAngle(clamped, _portP);

        const diff = value - benchmarkValue;
        const isAhead = diff >= 0;
        const diffArcColor = isAhead ? diffGreen : diffRed;

        if (Math.abs(diff) > 0.01) {
            const arcStart = Math.min(bmAngle, portfolioAngleForDiff);
            const arcEnd = Math.max(bmAngle, portfolioAngleForDiff);

            ctx.save();
            ctx.beginPath();
            ctx.arc(cx, cy, signalRadius, arcStart, arcEnd);
            ctx.strokeStyle = diffArcColor;
            ctx.lineWidth = isCompact ? 2.5 : 3.5;
            ctx.lineCap = 'round';
            ctx.shadowColor = diffArcColor;
            ctx.shadowBlur = isLightTheme ? 8 : 12;
            ctx.stroke();
            ctx.restore();
        }

        // Draw WIG needle
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(bmAngle) * (trackRadius - trackWidth * 1.35), cy + Math.sin(bmAngle) * (trackRadius - trackWidth * 1.35));
        ctx.lineTo(cx + Math.cos(bmAngle) * (trackRadius + trackWidth * 0.7), cy + Math.sin(bmAngle) * (trackRadius + trackWidth * 0.7));
        ctx.strokeStyle = benchmarkMarkerColor;
        ctx.lineWidth = isCompact ? 2 : 2.5;
        ctx.lineCap = 'round';
        ctx.shadowColor = benchmarkMarkerColor;
        ctx.shadowBlur = isLightTheme ? 5 : 8;
        ctx.stroke();
        ctx.restore();

        // ── Benchmark banner (main gauge + mobile carousel slide) ─
        const tooltipId = canvas.id === 'gaugeChart-mobile'
            ? 'gauge-benchmark-tooltip-mobile'
            : 'gauge-benchmark-tooltip';
        const tooltip = document.getElementById(tooltipId);
        if (!_animProgress && tooltip && (canvas.id === 'gaugeChart' || canvas.id === 'gaugeChart-mobile')) {
            const d = Math.abs(diff).toFixed(2);
            const absDiff = Math.abs(diff);
            const signatureBase = [
                Number(value).toFixed(2),
                Number(benchmarkValue).toFixed(2)
            ].join('|');

            // Use the roast data generated by the backend (roast_engine.py)
            const roastData = window.ROAST_DATA || null;
            
            let msg = "No fresh commentary available at the moment.";
            let stateClass = 'bm-neutral';
            
            if (roastData && roastData.message) {
                msg = roastData.message;
                const tone = roastData.tone || "neutral";
                if (tone === "praise") {
                    stateClass = "bm-winning";
                } else if (tone === "roast" || tone === "mixed") {
                    stateClass = "bm-losing";
                }
            } else {
                stateClass = absDiff < 0.2 ? 'bm-neutral' : (isAhead ? 'bm-winning' : 'bm-losing');
            }
            tooltip.innerHTML = `<span class="bm-msg">"${msg}"</span>
<div class="roast-reactions" style="margin-top: 8px; display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; position: relative; z-index: 50; pointer-events: auto;">
    <button onclick="window.submitRoastReaction('good', event)" ontouchend="window.submitRoastReaction('good', event)" style="font-size:11px; padding:2px 6px; border-radius:12px; background:rgba(255,255,255,0.1); border:none; cursor:pointer; color:inherit; -webkit-appearance:none;">👍 Good</button>
    <button onclick="window.submitRoastReaction('repetitive', event)" ontouchend="window.submitRoastReaction('repetitive', event)" style="font-size:11px; padding:2px 6px; border-radius:12px; background:rgba(255,255,255,0.1); border:none; cursor:pointer; color:inherit; -webkit-appearance:none;">🔁 Repetitive</button>
    <button onclick="window.submitRoastReaction('wrong', event)" ontouchend="window.submitRoastReaction('wrong', event)" style="font-size:11px; padding:2px 6px; border-radius:12px; background:rgba(255,255,255,0.1); border:none; cursor:pointer; color:inherit; -webkit-appearance:none;">❌ Wrong</button>
    <button onclick="window.submitRoastReaction('boring', event)" ontouchend="window.submitRoastReaction('boring', event)" style="font-size:11px; padding:2px 6px; border-radius:12px; background:rgba(255,255,255,0.1); border:none; cursor:pointer; color:inherit; -webkit-appearance:none;">🥱 Boring</button>
</div>`;
            tooltip.className   = stateClass + ' bm-modern-roast';
            tooltip.style.display = 'block';
            if (window.RoastTracker) {
                window.RoastTracker.recordEvent({
                    eventType: 'roast_displayed',
                    templateId: roastData ? roastData.templateId : undefined,
                    scenarioKey: roastData ? roastData.scenarioKey : undefined,
                    portfolioChange: roastData ? roastData.portfolioChange : undefined,
                    benchmarkChange: roastData ? roastData.benchmarkChange : undefined,
                    bestAsset: roastData ? roastData.bestAsset : undefined,
                    worstAsset: roastData ? roastData.worstAsset : undefined
                });
            }
            _animateBenchmarkTooltip(tooltip);
        }
    } else if (canvas.id === 'gaugeChart') {
        // No benchmark data — ensure stale message is hidden
        const tooltipId2 = 'gauge-benchmark-tooltip';
        const tooltip = document.getElementById(tooltipId2);
        if (tooltip) tooltip.style.display = 'none';
    }

    // Main needle (portfolio)
    const needleAngle = valueToGaugeAngle(clamped, _portP);
    const needleLen = signalRadius - 10;
    const needleDx = Math.cos(needleAngle);
    const needleDy = Math.sin(needleAngle);
    const needleNx = -needleDy;
    const needleNy = needleDx;
    const needleX = cx + needleDx * needleLen;
    const needleY = cy + needleDy * needleLen;
    const needleTail = isCompact ? 7 : 10;
    const needleBaseWidth = isCompact ? 8 : 11;
    const needleTipWidth = isCompact ? 2.4 : 3.2;
    const needleTipReach = isCompact ? 3 : 5;
    const needleShoulder = needleLen * 0.24;
    const needleBladeGradient = ctx.createLinearGradient(
        cx - needleDx * needleTail,
        cy - needleDy * needleTail,
        needleX + needleDx * needleTipReach,
        needleY + needleDy * needleTipReach,
    );
    if (isLightTheme) {
        needleBladeGradient.addColorStop(0, 'rgba(15, 23, 42, 0.92)');
        needleBladeGradient.addColorStop(0.55, 'rgba(2, 132, 199, 0.96)');
        needleBladeGradient.addColorStop(1, 'rgba(14, 165, 233, 0.98)');
    } else {
        needleBladeGradient.addColorStop(0, 'rgba(8, 145, 178, 0.92)');
        needleBladeGradient.addColorStop(0.56, 'rgba(103, 232, 249, 0.98)');
        needleBladeGradient.addColorStop(1, 'rgba(255, 255, 255, 1)');
    }

    function drawNeedleBlade(offset) {
        ctx.moveTo(cx - needleDx * needleTail + needleNx * (needleBaseWidth * 0.42 + offset), cy - needleDy * needleTail + needleNy * (needleBaseWidth * 0.42 + offset));
        ctx.lineTo(cx + needleDx * needleShoulder + needleNx * (needleBaseWidth * 0.54 + offset), cy + needleDy * needleShoulder + needleNy * (needleBaseWidth * 0.54 + offset));
        ctx.lineTo(needleX + needleDx * needleTipReach + needleNx * (needleTipWidth + offset), needleY + needleDy * needleTipReach + needleNy * (needleTipWidth + offset));
        ctx.lineTo(needleX + needleDx * (needleTipReach + 4), needleY + needleDy * (needleTipReach + 4));
        ctx.lineTo(needleX + needleDx * needleTipReach - needleNx * (needleTipWidth + offset), needleY + needleDy * needleTipReach - needleNy * (needleTipWidth + offset));
        ctx.lineTo(cx + needleDx * needleShoulder - needleNx * (needleBaseWidth * 0.54 + offset), cy + needleDy * needleShoulder - needleNy * (needleBaseWidth * 0.54 + offset));
        ctx.lineTo(cx - needleDx * needleTail - needleNx * (needleBaseWidth * 0.42 + offset), cy - needleDy * needleTail - needleNy * (needleBaseWidth * 0.42 + offset));
        ctx.closePath();
    }

    ctx.save();
    ctx.beginPath();
    drawNeedleBlade(isCompact ? 2.2 : 3);
    ctx.fillStyle = needleOutline;
    ctx.shadowColor = needleOutline;
    ctx.shadowBlur = 3;
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.beginPath();
    drawNeedleBlade(0);
    ctx.fillStyle = needleBladeGradient;
    ctx.shadowColor = needleGlow;
    ctx.shadowBlur = 12 + 5 * _pulseP;
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(cx + needleDx * (isCompact ? 7 : 10), cy + needleDy * (isCompact ? 7 : 10));
    ctx.lineTo(needleX - needleDx * 4, needleY - needleDy * 4);
    ctx.strokeStyle = isLightTheme ? 'rgba(255, 255, 255, 0.64)' : 'rgba(255, 255, 255, 0.78)';
    ctx.lineWidth = isCompact ? 1 : 1.4;
    ctx.lineCap = 'round';
    ctx.shadowColor = needleGlow;
    ctx.shadowBlur = 6;
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.beginPath();
    ctx.arc(needleX, needleY, isCompact ? 3 : 4, 0, Math.PI * 2);
    ctx.fillStyle = needleColor;
    ctx.shadowColor = needleGlow;
    ctx.shadowBlur = 11;
    ctx.fill();
    ctx.lineWidth = isCompact ? 1.8 : 2.4;
    ctx.strokeStyle = needleOutline;
    ctx.stroke();
    ctx.restore();

    // Center hub
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, isCompact ? 4 : 5, 0, Math.PI * 2);
    ctx.fillStyle = hubFill;
    ctx.strokeStyle = needleColor;
    ctx.lineWidth = 1.5;
    ctx.shadowColor = needleGlow;
    ctx.shadowBlur = 5;
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    // Value text
    const displayValue = Number(value).toFixed(2);
    const sign = value >= 0 ? '+' : '';
    const color = valueTextColor;
    ctx.font = valueFont;
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.shadowColor = valueTextGlow;
    ctx.shadowBlur = isLightTheme ? 3 : 10;
    ctx.fillText(`${sign}${displayValue}%`, cx, cy - r * 0.45);
    ctx.shadowBlur = 0;

    // Benchmark label (small, below value) — render on mobile too
    if (benchmarkValue != null) {
        const bmSign  = benchmarkValue >= 0 ? '+' : '';
        const bmDisplay = Number(benchmarkValue).toFixed(2);
        const benchmarkLabel = window.BENCHMARK_NAME || window.BENCHMARK_ID || 'Benchmark';
        const smallFont = isCompact
            ? `500 ${Math.max(9, canvas.height * 0.055)}px 'SF Mono', 'Fira Code', 'Consolas', monospace`
            : `500 ${Math.max(10, canvas.height * 0.05)}px 'SF Mono', 'Fira Code', 'Consolas', monospace`;
        ctx.font = smallFont;
        ctx.fillStyle = 'rgba(125, 169, 255, 0.78)';
        const bmYOffset = isCompact ? 18 : 22;
        ctx.fillText(`${benchmarkLabel} ${bmSign}${bmDisplay}%`, cx, cy - r * 0.45 + bmYOffset);
    }
}

// Animated gauge entry: needle sweeps from centre (0%) to target, then fires onComplete
function animateGaugeEntry(canvasId, value, benchmarkValue, onComplete) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    // Preserve existing dimensions if previously set by initial renderGauge
    const w = canvas.width !== 300 ? canvas.width : null;
    const h = canvas.height !== 150 ? canvas.height : null;

    // Respect user's reduced-motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        renderGauge(canvasId, value, w, h, benchmarkValue);
        if (typeof onComplete === 'function') onComplete();
        return;
    }
    function easeOutQuint(t) { return 1 - Math.pow(1 - t, 5); }
    function easeInOutSine(t) { return -(Math.cos(Math.PI * t) - 1) / 2; }
    const PORT_END = 2400;
    const BM_START = 420;
    const BM_END   = 2100;
    const TOTAL_END = Math.max(PORT_END, BM_END);
    const startTime = performance.now();
    const cardEl = canvas.closest('.dash-gauge-card, .dash-gauge-carousel-card');
    if (cardEl) {
        cardEl.classList.add('gauge-booting');
        cardEl.classList.remove('gauge-booted');
    }
    function frame(now) {
        const elapsed = now - startTime;
        const portP = easeOutQuint(Math.min(elapsed / PORT_END, 1));
        const bmRaw = benchmarkValue != null
            ? Math.min(Math.max(0, elapsed - BM_START) / (BM_END - BM_START), 1)
            : 1;
        const bmP = easeOutQuint(bmRaw);
        const pulseP = Math.sin(easeInOutSine(Math.min(elapsed / TOTAL_END, 1)) * Math.PI);
        renderGauge(canvasId, value, w, h, benchmarkValue, { portfolio: portP, benchmark: bmP, pulse: pulseP });
        if (elapsed < TOTAL_END) {
            requestAnimationFrame(frame);
        } else {
            renderGauge(canvasId, value, w, h, benchmarkValue); // final render — also updates tooltip
            if (cardEl) {
                cardEl.classList.remove('gauge-booting');
                cardEl.classList.add('gauge-booted');
            }
            if (typeof onComplete === 'function') onComplete();
        }
    }
    requestAnimationFrame(frame);
}
window.animateGaugeEntry = animateGaugeEntry;

const WALLET_HISTORY = {
    'XTB':  typeof HISTORY_XTB  !== 'undefined' ? HISTORY_XTB  : [],
    'IKE':  typeof HISTORY_IKE  !== 'undefined' ? HISTORY_IKE  : [],
    'IKZE': typeof HISTORY_IKZE !== 'undefined' ? HISTORY_IKZE : [],
};

function drawdownHtml(athInfo, currentValue) {
    if (!athInfo || !athInfo.athValue) return '';
    const ath = Number(athInfo.athValue || 0);
    const athDate = athInfo.athDate || '';
    const diffPLN = currentValue - ath;
    const diffPct = ath ? ((diffPLN / ath) * 100).toFixed(2) : '0.00';
    let color = '#64748b';
    if (diffPLN > 0) color = '#27ae60';
    else if (diffPLN < 0) color = '#c0392b';
    const sign = diffPLN > 0 ? '+' : '';
    const sourceLabel = athInfo.athSource === 'MANUAL' ? 'Manual ATH' : 'ATH';
    return `<div style="margin-top:8px;padding:6px 10px;background:#f8f9fa;border-radius:6px;border-left:3px solid #bdc3c7;font-size:12px;">
        <div style="color:#888;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">From ATH</div>
        <span style="color:${color};font-weight:bold;">${sign}${diffPct}%</span>
        <span style="color:${color};margin-left:6px;">(${sign}${diffPLN.toLocaleString('pl-PL', { minimumFractionDigits: 0 })} PLN)</span>
        <div style="color:#aaa;font-size:10px;margin-top:1px;">${sourceLabel}: ${ath.toLocaleString('pl-PL', { minimumFractionDigits: 0 })} PLN · ${athDate}</div>
    </div>`;
}

function renderControlDial(canvasId, value) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    
    canvas.style.width = '100px';
    canvas.style.height = '100px';
    canvas.width = 100 * dpr;
    canvas.height = 100 * dpr;
    ctx.scale(dpr, dpr);

    const cx = 50;
    const cy = 52;
    const r = 38;

    ctx.clearRect(0, 0, 100, 100);

    // Draw background outer rim
    ctx.beginPath();
    ctx.arc(cx, cy, r + 2, 0.75 * Math.PI, 2.25 * Math.PI);
    const isDark = typeof window.isRoastfolioDark === 'function'
        ? window.isRoastfolioDark()
        : window.matchMedia('(prefers-color-scheme: dark)').matches;
    ctx.strokeStyle = isDark ? '#1a2f4a' : '#e2e8f0';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Draw sectors
    ctx.beginPath();
    ctx.arc(cx, cy, r - 3, 0.75 * Math.PI, 1.5 * Math.PI);
    ctx.strokeStyle = isDark ? 'rgba(239, 68, 68, 0.15)' : 'rgba(239, 68, 68, 0.1)';
    ctx.lineWidth = 6;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(cx, cy, r - 3, 1.5 * Math.PI, 2.25 * Math.PI);
    ctx.strokeStyle = isDark ? 'rgba(34, 197, 94, 0.15)' : 'rgba(34, 197, 94, 0.1)';
    ctx.lineWidth = 6;
    ctx.stroke();

    // Draw tick marks
    const ticks = [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2];
    ticks.forEach(t => {
        const angle = 1.5 * Math.PI + (t / 2) * (0.75 * Math.PI);
        const isMajor = t % 1 === 0;
        const tickLength = isMajor ? 6 : 4;
        
        const startX = cx + Math.cos(angle) * (r - tickLength);
        const startY = cy + Math.sin(angle) * (r - tickLength);
        const endX = cx + Math.cos(angle) * r;
        const endY = cy + Math.sin(angle) * r;
        
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.strokeStyle = isMajor 
            ? (isDark ? '#7eb3d2' : '#475569') 
            : (isDark ? '#475569' : '#cbd5e1');
        ctx.lineWidth = isMajor ? 1.5 : 1;
        ctx.stroke();
    });

    // Draw center pin
    ctx.beginPath();
    ctx.arc(cx, cy, 4, 0, 2 * Math.PI);
    ctx.fillStyle = isDark ? '#eef7ff' : '#0f172a';
    ctx.fill();

    // Draw needle
    const clamped = Math.max(-2, Math.min(2, value));
    const needleAngle = 1.5 * Math.PI + (clamped / 2) * (0.75 * Math.PI);
    const needleLength = r - 5;
    const needleEndX = cx + Math.cos(needleAngle) * needleLength;
    const needleEndY = cy + Math.sin(needleAngle) * needleLength;

    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(needleEndX, needleEndY);
    ctx.strokeStyle = clamped >= 0 ? '#22c55e' : '#ef4444';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.stroke();

    // Draw needle cap center dot
    ctx.beginPath();
    ctx.arc(cx, cy, 2, 0, 2 * Math.PI);
    ctx.fillStyle = '#ff7a00';
    ctx.fill();
}

function renderWalletCards() {
    const container = document.getElementById('dash-mini-wallets');
    if (!container || typeof WALLET_SUMMARIES === 'undefined') return;

    // Derive wallet list from API response — excludes 'Summary' (shown in main gauge)
    const wallets = (window.PORTFOLIO_WALLETS || Object.keys(WALLET_SUMMARIES)).filter(k => k !== 'Summary');
    if (wallets.length === 0) {
        container.innerHTML = '';
        return;
    }

    const metersHTML = wallets.map(name => {
        const w = WALLET_SUMMARIES[name];
        if (!w) return '';
        const color = w.dailyPLN >= 0 ? '#27ae60' : '#c0392b';
        const sign = w.dailyPLN >= 0 ? '+' : '';
        return `
        <div class="control-panel-meter" onclick="showTab('history'); if(window.setHistoryWallet) window.setHistoryWallet('${name}');" style="cursor:pointer;" title="View history for ${name}">
            <div class="control-panel-dial-wrap">
                <canvas id="controlDial-${name}" style="width:100px; height:100px;"></canvas>
            </div>
            <div class="control-panel-info">
                <div class="control-panel-nameplate">${name}</div>
                <div class="control-panel-val">${w.total.toLocaleString('pl-PL', {minimumFractionDigits: 0})} PLN</div>
                <div class="control-panel-pct" style="color:${color};">
                    ${sign}${Number(w.dailyPct || 0).toFixed(2)}% 
                    <span style="font-size:11px; font-weight:normal; opacity:0.85; margin-left:4px;">(${sign}${w.dailyPLN.toLocaleString('pl-PL', {minimumFractionDigits: 0})} PLN)</span>
                </div>
                <div id="wallet-ath-${name}" class="control-panel-ath">ATH pending</div>
            </div>
        </div>`;
    }).join('');

    container.innerHTML = `
    <div class="dash-card dash-control-panel-card">
        <div class="control-panel-header">
            <div class="dash-label" style="margin:0;"><span class="control-panel-status-light"></span> Portfolios Control Room</div>
            <div class="control-panel-title-sub">Instrument Panel</div>
        </div>
        <div class="control-panel-grid">
            ${metersHTML}
        </div>
    </div>`;

    // Render mini dial gauges after layout
    requestAnimationFrame(() => {
        wallets.forEach(name => {
            const w = WALLET_SUMMARIES[name];
            if (!w) return;
            renderControlDial(`controlDial-${name}`, w.dailyPct);
            
            // Render wallet ATH summary/drawdown
            try {
                const baseAth = (window.WALLET_ATHS || {})[name];
                const snapAth = (window._WALLET_SNAPSHOT_ATHS || {})[name] ||
                                (window._WALLET_SNAPSHOT_ATHS || {})[String(name).toLowerCase()] ||
                                (window._WALLET_SNAPSHOT_ATHS || {})[String(name).toUpperCase()];
                const athEl = document.getElementById('wallet-ath-' + name);
                if (athEl) {
                    let aVal = baseAth && baseAth.athValue != null ? Number(baseAth.athValue || 0) : 0;
                    if (snapAth && Number(snapAth.athValue || 0) > aVal) {
                        aVal = Number(snapAth.athValue);
                    }
                    if (!aVal) {
                        athEl.textContent = 'ATH pending';
                    } else {
                        const curr = Number(w.total || 0);
                        const effectiveAth = Math.max(aVal, curr);
                        const diff = curr - effectiveAth;
                        const pct = effectiveAth ? ((diff / effectiveAth) * 100).toFixed(2) : '0.00';
                        if (diff >= -0.01) {
                            athEl.innerHTML = `Status: <strong style="color:#22c55e;">At ATH (0.00%)</strong>`;
                        } else {
                            athEl.innerHTML = `ATH Drawdown: <strong style="color:#ef4444;">${pct}%</strong>`;
                        }
                    }
                }
            } catch (e) {
                console.warn('wallet ATH render error', name, e);
            }
        });
    });
}

window._sparkMode = 'today'; // 'today' | 'year'

function setSparkMode(mode) {
    window._sparkMode = mode;
    document.querySelectorAll('.spark-mode-btn').forEach(b => {
        b.style.background = b.dataset.mode === mode ? '#35424a' : '#e8edf0';
        b.style.color      = b.dataset.mode === mode ? '#fff'     : '#555';
    });
    if (typeof renderDailyBreakdown === 'function') renderDailyBreakdown();
}

function makeSparkline(barPairs, isUp, width, height) {
    if (!barPairs || barPairs.length < 2) return '';
    const vals = barPairs.map(p => p[1]);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const range = max - min || 1;
    const pad = 2;
    const w = width - pad * 2;
    const h = height - pad * 2;

    const color = isUp ? '#34d399' : '#f87171'; // Neon green / Neon red
    const fillId = `sf${Math.random().toString(36).slice(2,7)}`;

    const coords = barPairs.map((p, i) => ({
        x: pad + (i / (barPairs.length - 1)) * w,
        y: pad + h - ((p[1] - min) / range) * h,
        ts: p[0], v: p[1]
    }));
    const pts = coords.map(c => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
    const last = coords[coords.length - 1];

    // Tooltip labels per point
    const labels = barPairs.map((p, i) => {
        if (i === barPairs.length - 1) return 'Live';
        const d = new Date(p[0]);
        if (window._sparkMode === 'today') {
            return d.toLocaleTimeString('pl-PL', { timeZone: 'Europe/Warsaw', hour: '2-digit', minute: '2-digit' });
        }
        return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
    });

    // Sample points — max 30 for smooth hover tracking
    const step = Math.max(1, Math.floor(coords.length / 30));
    const hits = coords.filter((_, i) => i % step === 0 || i === coords.length - 1);
    const hitLabels = hits.map(c => labels[coords.indexOf(c)]);

    const dots = hits.map(c =>
        `<circle class="sp-dot" cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="2.5"
            fill="${color}" opacity="0"/>`
    ).join('');

    // Full-width transparent overlay — tracks mouse X to find nearest point
    const coordsJson = JSON.stringify(hits.map((c, i) => ({ x: c.x, v: c.v, label: hitLabels[i] })));

    return `<svg class="sparkline-svg" width="${width}" height="${height}"
            style="display:block;overflow:visible;flex-shrink:0;min-width:${width}px;" data-coords='${coordsJson}'>
        <defs>
            <linearGradient id="${fillId}" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="${color}" stop-opacity="0.35"/>
                <stop offset="100%" stop-color="${color}" stop-opacity="0.02"/>
            </linearGradient>
            <filter id="glow-${fillId}" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="2" result="blur"/>
                <feMerge>
                    <feMergeNode in="blur"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
        </defs>
        <polygon points="${pts} ${last.x.toFixed(1)},${pad + h} ${pad},${pad + h}" fill="url(#${fillId})"/>
        <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" filter="url(#glow-${fillId})" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${last.x.toFixed(1)}" cy="${last.y.toFixed(1)}" r="2.5" fill="${color}" filter="url(#glow-${fillId})"/>
        ${dots}
        <rect x="0" y="0" width="${width}" height="${height}" fill="transparent" style="cursor:crosshair;" data-color="${color}"/>
    </svg>`;
}

// Shared tooltip element for sparklines
function getSparkTooltip() {
    let el = document.getElementById('spark-tooltip');
    if (!el) {
        el = document.createElement('div');
        el.id = 'spark-tooltip';
        el.style.cssText = `position:fixed;background:#1a2530;color:#fff;padding:5px 10px;border-radius:6px;
            font-size:11px;font-weight:600;pointer-events:none;display:none;z-index:9999;
            white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,0.3);`;
        document.body.appendChild(el);
    }
    return el;
}

function renderDailyBreakdown() {
    const container = document.getElementById('dash-breakdown');
    if (!container) return;
    if (typeof PORTFOLIO_DATA === 'undefined' || !PORTFOLIO_DATA) return;

    const mode = window._sparkMode || 'today';
    const isMobile = typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches;

    function isCashHoldingItem(item) {
        if (!item) return false;
        if (item.isCash === true) return true;
        const name = String(item.name || '').trim().toLowerCase();
        const holdingId = String(item.holdingId || '').trim().toLowerCase();
        const ticker = String(item.ticker || '').trim().toUpperCase();

        if (holdingId === '__cash__' || holdingId === 'cash' || holdingId.includes('cash') || holdingId.includes('gotowk') || holdingId.includes('gotowka')) return true;
        if (ticker === 'CASH' || ticker === '__CASH__') return true;

        if (name === 'cash' || name.includes('cash') || name.includes('gotówk') || name.includes('gotowk') || name.includes('środki') || name.includes('srodki') || name.includes('konto') || name.includes('depozyt') || name.includes('saldo') || name.includes('salda')) {
            return true;
        }

        if (!ticker && (name.length === 0 || name.includes('cash') || name.includes('got') || name.includes('pln') || name.includes('usd') || name.includes('eur'))) {
            return true;
        }

        return false;
    }

    // Filter out cash holdings and sort by absolute daily PLN change descending
    const sorted = [...PORTFOLIO_DATA]
        .filter(d => !isCashHoldingItem(d))
        .map(d => ({
            ...d,
            dailyChangePLNSafe: Number.isFinite(Number(d.dailyChangePLN)) ? Number(d.dailyChangePLN) : 0,
            dailyChangePctSafe: Number.isFinite(Number(d.dailyChangePct)) ? Number(d.dailyChangePct) : 0,
            ytdChangePctSafe: Number.isFinite(Number(d.ytdChangePct)) ? Number(d.ytdChangePct) : null,
            pricePLNSafe: Number.isFinite(Number(d.pricePLN)) ? Number(d.pricePLN) : 0,
        }))
        .sort((a, b) => Math.abs(b.dailyChangePLNSafe) - Math.abs(a.dailyChangePLNSafe));

    const entries = sorted.map(d => {
        // Always use daily change for text, regardless of sparkline mode
        const changePct  = d.dailyChangePctSafe;
        const pctColor = changePct >= 0 ? '#27ae60' : '#c0392b';
        const pctSign  = changePct > 0 ? '+' : '';
        const logoHtml = companyLogoHtml(d.name);
        const isUp = changePct >= 0;

        // Daily PLN should always use its own color/sign regardless of sparkline mode
        const dailyColor = d.dailyChangePLNSafe >= 0 ? '#27ae60' : '#c0392b';
        const dailySign  = d.dailyChangePLNSafe < 0 ? '-' : '';
        
        // Ensure no double signs by using Math.abs for PLN
        const plnFormatted = Math.abs(d.dailyChangePLNSafe).toLocaleString('pl-PL', { minimumFractionDigits: 2 });
        const pctFormatted = Math.abs(changePct).toFixed(2);

        const priceStr = d.pricePLNSafe > 0
            ? d.pricePLNSafe.toLocaleString('pl-PL', { minimumFractionDigits: 2 }) + ' PLN'
            + (d.priceOriginalCurrency !== 'PLN' ? ` <small style="color:#888">${d.priceOriginal} ${d.priceOriginalCurrency}</small>` : '')
            : '—';

        const isCash = isCashHoldingItem(d);
        const ticker = d.ticker || d.name;

        // Normalise bar data — support both [[ts,close],...] (new) and [close,...] (old recentBars)
        let rawBars = mode === 'year' ? (d.yearBars || []) : (d.todayBars || d.recentBars || []);
        let barPairs;
        if (rawBars.length && Array.isArray(rawBars[0])) {
            barPairs = rawBars; // already [[ts, close], ...]
        } else {
            // old flat array — assign synthetic timestamps spaced 1min apart ending now
            const now = Date.now();
            barPairs = rawBars.map((v, i) => [now - (rawBars.length - 1 - i) * 60000, v]);
        }
        const spark = makeSparkline(barPairs, isUp, isMobile ? 150 : 135, isMobile ? 40 : 36);

        if (isMobile) {
            const clickHandler = isCash ? '' : `onclick="window.openAnalysisForTicker('${ticker}')"`;
            const clickableClass = isCash ? '' : ' dash-mover-clickable';
            return `
                <article class="dash-mover-card${clickableClass}" ${clickHandler}>
                    <div class="dash-mover-head">
                        <div class="dash-mover-company">
                            ${logoHtml}
                            <span class="dash-mover-name">${d.name}</span>
                        </div>
                        <div class="dash-mover-pln" style="color:${dailyColor};font-family:monospace;text-shadow:0 0 8px currentColor;">
                            ${dailySign}${plnFormatted} PLN
                        </div>
                    </div>
                    <div class="dash-mover-body">
                        <div class="dash-mover-spark">${spark}</div>
                        <div class="dash-mover-meta">
                            <div class="dash-mover-price" style="color:#94a3b8;font-family:monospace;">${priceStr}</div>
                            <div class="dash-mover-pct" style="color:${pctColor};font-family:monospace;text-shadow:0 0 5px currentColor;">${pctSign}${pctFormatted}%</div>
                        </div>
                    </div>
                </article>`;
        }

        const clickHandler = isCash ? '' : `onclick="window.openAnalysisForTicker('${ticker}')" style="cursor:pointer;"`;
        const clickableClass = isCash ? '' : ' holding-row-clickable';
        return `<tr class="${clickableClass}" ${clickHandler}>
            <td><div style="display:flex;align-items:center;">${logoHtml}<span class="dash-mover-name">${d.name}</span></div></td>
            <td>
                <div style="display:flex;align-items:center;gap:8px;">
                    ${spark}
                    <div>
                        <div style="font-size:12px;color:#94a3b8;font-family:monospace;">${priceStr}</div>
                        <div style="font-size:12px;font-weight:700;color:${pctColor};font-family:monospace;text-shadow:0 0 5px currentColor;">${pctSign}${pctFormatted}%</div>
                    </div>
                </div>
            </td>
            <td><div style="color:${dailyColor}; font-weight:bold; font-family:monospace; text-shadow:0 0 8px currentColor;">${dailySign}${plnFormatted} PLN</div></td>
        </tr>`;
    }).join('');

    if (isMobile) {
        container.innerHTML = `
            <div class="dash-movers-mobile-controls">
                <span class="dash-movers-mobile-hint">Sorted by biggest daily impact</span>
                <div class="dash-movers-toggle">
                    <button class="spark-mode-btn" data-mode="today" onclick="setSparkMode('today')"
                        style="border:none;border-radius:6px;padding:4px 10px;font-size:11px;font-weight:700;cursor:pointer;
                        background:${mode==='today'?'#35424a':'#e8edf0'};color:${mode==='today'?'#fff':'#888'};">1D</button>
                    <button class="spark-mode-btn" data-mode="year" onclick="setSparkMode('year')"
                        style="border:none;border-radius:6px;padding:4px 10px;font-size:11px;font-weight:700;cursor:pointer;
                        background:${mode==='year'?'#35424a':'#e8edf0'};color:${mode==='year'?'#fff':'#888'};">1Y</button>
                </div>
            </div>
            <div class="dash-movers-mobile-list">${entries}</div>`;
    } else {
        container.innerHTML = `
            <table class="holdings-table" style="width:100%; font-size:13px;">
                <thead>
                    <tr>
                        <th>Company</th>
                        <th>
                            <div style="display:flex;align-items:center;gap:8px;">
                                <span>Chart</span>
                                <div style="display:flex;gap:4px;background:rgba(255,255,255,0.15);border-radius:6px;padding:3px;">
                                    <button class="spark-mode-btn" data-mode="today" onclick="setSparkMode('today')"
                                        style="border:none;border-radius:4px;padding:3px 8px;font-size:11px;font-weight:600;cursor:pointer;
                                        background:${mode==='today'?'#fff':'transparent'};color:${mode==='today'?'#35424a':'#fff'};">1D</button>
                                    <button class="spark-mode-btn" data-mode="year" onclick="setSparkMode('year')"
                                        style="border:none;border-radius:4px;padding:3px 8px;font-size:11px;font-weight:600;cursor:pointer;
                                        background:${mode==='year'?'#fff':'transparent'};color:${mode==='year'?'#35424a':'#fff'};">1Y</button>
                                </div>
                            </div>
                        </th>
                        <th>Daily PLN</th>
                    </tr>
                </thead>
                <tbody>${entries}</tbody>
            </table>`;
    }

    // Sparkline hover — use overlay rect + nearest-point by X position
    const tip = getSparkTooltip();
    container.querySelectorAll('.sparkline-svg').forEach(svg => {
        const rect = svg.querySelector('rect[data-color]');
        if (!rect) return;
        const rawCoords = svg.dataset.coords;
        if (!rawCoords) return;
        const coords = JSON.parse(rawCoords);
        const dots = [...svg.querySelectorAll('.sp-dot')];

        rect.addEventListener('mousemove', e => {
            const svgRect = svg.getBoundingClientRect();
            const mouseX = e.clientX - svgRect.left;
            // Find nearest coord by X
            let best = coords[0], bestDist = Infinity, bestIdx = 0;
            coords.forEach((c, i) => {
                const d = Math.abs(c.x - mouseX);
                if (d < bestDist) { bestDist = d; best = c; bestIdx = i; }
            });
            dots.forEach((d, i) => d.setAttribute('opacity', i === bestIdx ? '1' : '0'));
            tip.textContent = `${best.label}: ${best.v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
            tip.style.display = 'block';
            tip.style.left = (e.clientX + 14) + 'px';
            tip.style.top  = (e.clientY - 32) + 'px';
        });
        rect.addEventListener('mouseleave', () => {
            dots.forEach(d => d.setAttribute('opacity', '0'));
            tip.style.display = 'none';
        });
    });
}

function getMarketCarouselShells() {
    return Array.from(document.querySelectorAll('[data-market-carousel]'))
        .map(wrap => ({
            wrap,
            track: wrap.querySelector('.market-index-carousel-track'),
        }))
        .filter(shell => shell.track);
}

function renderMarketIndexCarousel() {
    const shells = getMarketCarouselShells();
    const items = Array.isArray(window.MARKET_CAROUSEL) ? window.MARKET_CAROUSEL : [];
    if (!shells.length) return;

    if (!items.length) {
        shells.forEach(({ wrap, track }) => {
            wrap.hidden = true;
            track.innerHTML = '';
        });
        return;
    }

    const tickerItems = items.map(item => {
        const dailyPct = Number(item.dailyPct || 0);
        const isUp = dailyPct >= 0;
        const sign = isUp ? '+' : '';
        const arrow = isUp ? '▲' : '▼';
        return `
            <span class="market-ticker-item" data-index-id="${item.id}">
                <span class="market-ticker-symbol">${item.name}</span>
                <span class="market-ticker-direction ${isUp ? 'is-up' : 'is-down'}" aria-hidden="true">${arrow}</span>
                <span class="market-ticker-change ${isUp ? 'is-up' : 'is-down'}">${sign}${dailyPct.toFixed(2)}%</span>
            </span>
        `;
    }).join('');

    shells.forEach(({ wrap, track }) => {
        wrap.hidden = false;
        track.innerHTML = `<div class="market-ticker-lane">${tickerItems}${tickerItems}</div>`;
    });
}

let dashboardResizeTimer = null;
window.addEventListener('resize', () => {
    clearTimeout(dashboardResizeTimer);
    dashboardResizeTimer = setTimeout(() => {
        const dashTab = document.getElementById('tab-dashboard');
        if (dashTab && dashTab.classList.contains('active')) renderDashboard();
    }, 160);
});

document.addEventListener('DOMContentLoaded', initializeDashboard);

/* ── Mobile Gauge Carousel ──────────────────────────────────────────────────
 * Shows Portfolio (Summary) gauge by default; swipe left/right cycles through
 * user wallet gauges. Rebuilds slides dynamically from PORTFOLIO_WALLETS.
 * Only active when viewport ≤ 768 px.
 */
(function () {
    var _wallets  = ['Summary'];  // updated by rebuildCarousel()
    var currentSlide = 0;
    var touchStartX = 0;
    var touchStartY = 0;
    var dragging = false;
    var _carouselInitialized = false;

    function isMobileCarouselActive() {
        return window.matchMedia('(max-width: 768px)').matches;
    }

    function _slideOffsetPx(idx, track) {
        if (!track) return 0;
        var slides = track.querySelectorAll('.gauge-slide');
        var activeSlide = slides && slides[idx] ? slides[idx] : null;
        return activeSlide ? Math.round(activeSlide.offsetLeft) : 0;
    }

    function goToSlide(idx) {
        var track = document.getElementById('gauge-carousel-track');
        if (!track) return;
        idx = Math.max(0, Math.min(_wallets.length - 1, idx));
        currentSlide = idx;
        track.style.transform = 'translate3d(-' + _slideOffsetPx(idx, track) + 'px, 0, 0)';
        Array.from(track.querySelectorAll('.gauge-slide')).forEach(function (slide, slideIdx) {
            slide.classList.toggle('is-active', slideIdx === idx);
            slide.setAttribute('aria-hidden', slideIdx === idx ? 'false' : 'true');
        });

        // Update dots
        document.querySelectorAll('.gauge-dot').forEach(function (dot, i) {
            dot.classList.toggle('active', i === idx);
        });

        renderCarouselSlide(idx);
    }

    function renderCarouselSlide(idx) {
        var name = _wallets[idx];
        if (idx === 0) {
            renderMobileMainGauge();
            return;
        }
        if (typeof WALLET_SUMMARIES === 'undefined' || !WALLET_SUMMARIES[name]) return;
        var w = WALLET_SUMMARIES[name];
        var canvasId = 'gaugeChart-mobile-' + name;
        var canvas = document.getElementById(canvasId);
        if (!canvas) return;

        var containerW = canvas.parentElement.clientWidth || 280;
        renderGauge(canvasId, w.dailyPct, containerW, 160);

        var meta = document.getElementById('gauge-mobile-meta-' + name);
        if (meta) {
            var color = w.dailyPLN >= 0 ? '#27ae60' : '#c0392b';
            var sign  = w.dailyPLN >= 0 ? '+' : '';
            meta.innerHTML =
                '<span style="font-weight:700;font-size:1.1rem;">' +
                    w.total.toLocaleString('pl-PL', { minimumFractionDigits: 0 }) + ' PLN' +
                '</span><br>' +
                '<span style="color:' + color + ';font-weight:600;">' +
                    sign + w.dailyPLN.toLocaleString('pl-PL', { minimumFractionDigits: 2 }) + ' PLN' +
                    ' (' + sign + Number(w.dailyPct || 0).toFixed(2) + '%)' +
                '</span>';
        }
        // Render per-wallet ATH banner if present
        try {
            var athInfo = (window.WALLET_ATHS || {})[name] || null;
            renderAthCelebrationFor('gauge-ath-celebration-' + name, athInfo, w.total, w.dailyPct);
        } catch (e) {
            console.warn('Failed to render wallet ATH banner for', name, e);
        }
    }

    function renderMobileMainGauge() {
        var canvas = document.getElementById('gaugeChart-mobile');
        if (!canvas) return;
        var w = canvas.parentElement.clientWidth || 280;
        if (!window._gaugeDataReady) {
            canvas.getContext('2d').clearRect(0, 0, canvas.width || 0, canvas.height || 0);
            return;
        }
        var bench = window.BENCHMARK_DAILY_PCT ?? ((typeof WIG_DAILY_PCT !== 'undefined') ? WIG_DAILY_PCT : null);
        renderGauge('gaugeChart-mobile', PORTFOLIO_DAILY_CHANGE_PCT, w, 160, bench);
        var meta = document.getElementById('gauge-mobile-meta-summary');
        if (meta && typeof PORTFOLIO_TOTAL_VALUE !== 'undefined' && typeof PORTFOLIO_DAILY_CHANGE_PLN !== 'undefined') {
            var color = PORTFOLIO_DAILY_CHANGE_PLN >= 0 ? '#27ae60' : '#c0392b';
            var sign  = PORTFOLIO_DAILY_CHANGE_PLN >= 0 ? '+' : '';
            meta.innerHTML =
                '<span style="font-weight:700;font-size:1.1rem;">' +
                    PORTFOLIO_TOTAL_VALUE.toLocaleString('pl-PL', { minimumFractionDigits: 0 }) + ' PLN' +
                '</span><br>' +
                '<span style="color:' + color + ';font-weight:600;">' +
                    sign + PORTFOLIO_DAILY_CHANGE_PLN.toLocaleString('pl-PL', { minimumFractionDigits: 2 }) + ' PLN' +
                    ' (' + sign + Number(PORTFOLIO_DAILY_CHANGE_PCT || 0).toFixed(2) + '%)' +
                '</span>';
        }
    }

    function _bindTouchAndDots(card) {
        document.querySelectorAll('.gauge-dot').forEach(function (dot) {
            dot.addEventListener('click', function () {
                goToSlide(parseInt(dot.dataset.slide, 10));
            });
        });
        if (!card) return;
        card.addEventListener('touchstart', function (e) {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            dragging = false;
        }, { passive: true });
        card.addEventListener('touchmove', function (e) {
            var dx = e.touches[0].clientX - touchStartX;
            var dy = e.touches[0].clientY - touchStartY;
            if (!dragging && Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 8) dragging = true;
        }, { passive: true });
        card.addEventListener('touchend', function (e) {
            if (!dragging) return;
            var dx = e.changedTouches[0].clientX - touchStartX;
            if (dx < -40) goToSlide(currentSlide + 1);
            else if (dx > 40) goToSlide(currentSlide - 1);
            dragging = false;
        }, { passive: true });
    }

    // Public: rebuild carousel slides + dots from current PORTFOLIO_WALLETS
    window.rebuildCarousel = function () {
        if (!isMobileCarouselActive()) return;

        var walletList = window.PORTFOLIO_WALLETS ||
            (typeof WALLET_SUMMARIES !== 'undefined'
                ? ['Summary', ...Object.keys(WALLET_SUMMARIES).filter(k => k !== 'Summary')]
                : ['Summary']);
        _wallets = walletList;

        var track = document.getElementById('gauge-carousel-track');
        var dotsEl = document.getElementById('gauge-carousel-dots');
        if (!track || !dotsEl) return;

        // Keep the Summary slide (slot 0), rebuild wallet slides
        // Remove old wallet slides (data-wallet != Summary)
        Array.from(track.querySelectorAll('.gauge-slide[data-wallet]')).forEach(function (el) {
            if (el.dataset.wallet !== 'Summary') el.remove();
        });

        // Inject new slides for each wallet
        _wallets.slice(1).forEach(function (name) {
            var slide = document.createElement('div');
            slide.className = 'gauge-slide';
            slide.dataset.wallet = name;
            slide.innerHTML =
                '<div class="gauge-slide-inner">' +
                    '<div class="dash-label gauge-slide-title">' + name + '</div>' +
                    '<div class="gauge-wrapper-mini"><canvas id="gaugeChart-mobile-' + name + '"></canvas></div>' +
                    '<div id="gauge-ath-celebration-' + name + '" class="gauge-ath-celebration" hidden></div>' +
                    '<div id="gauge-mobile-meta-' + name + '" class="gauge-mobile-meta"></div>' +
                '</div>';
            track.appendChild(slide);
        });

        // Update track width so each slide is exactly (100/N)%
        var n = _wallets.length;
        track.style.width = (n * 100) + '%';
        Array.from(track.querySelectorAll('.gauge-slide')).forEach(function (s) {
            s.style.width = (100 / n) + '%';
        });

        // Rebuild dots
        dotsEl.innerHTML = _wallets.map(function (_, i) {
            return '<span class="gauge-dot' + (i === 0 ? ' active' : '') + '" data-slide="' + i + '"></span>';
        }).join('');

        // Clamp current slide if wallet list shrank
        currentSlide = Math.min(currentSlide, n - 1);
        goToSlide(currentSlide);

        // Re-bind touch + dot handlers (new DOM nodes)
        _bindTouchAndDots(document.querySelector('.dash-gauge-carousel-card'));
    };

    function initCarousel() {
        if (!isMobileCarouselActive()) return;
        _bindTouchAndDots(document.querySelector('.dash-gauge-carousel-card'));
        _carouselInitialized = true;
        goToSlide(0);
    }

    // Re-render carousel slide when dashboard data updates
    var origRender = window.renderDashboard;
    window.renderDashboard = function () {
        if (origRender) origRender.apply(this, arguments);
        if (isMobileCarouselActive()) {
            requestAnimationFrame(function () {
                renderCarouselSlide(currentSlide);
            });
        }
    };

    document.addEventListener('DOMContentLoaded', function () {
        setTimeout(initCarousel, 100);
    });

    window.addEventListener('resize', function () {
        setTimeout(function () {
            if (isMobileCarouselActive() && !_carouselInitialized) initCarousel();
            if (isMobileCarouselActive() && _carouselInitialized) goToSlide(currentSlide);
        }, 200);
    });

    window.renderGaugeCarousel = function (slideIdx) {
        if (!isMobileCarouselActive()) return;
        if (slideIdx !== undefined) goToSlide(slideIdx);
        else renderCarouselSlide(currentSlide);
    };

    // ── Monthly Summary Logic ──────────────────────────────────────────────────
    const DASHBOARD_BENCHMARK_COLS = [
        { id: 'WIG',        short: 'WIG' },
        { id: 'WIG20',      short: 'WIG20' },
        { id: 'MWIG40',     short: 'mWIG40' },
        { id: 'SWIG80',     short: 'sWIG80' },
        { id: 'SP500',      short: 'S&P 500' },
        { id: 'NASDAQ',     short: 'NASDAQ' },
        { id: 'DAX',        short: 'DAX' },
        { id: 'MSCI_WORLD', short: 'MSCI W' },
    ];

    window.toggleMonthlyBenchmarksList = function () {
        const dropdown = document.getElementById('monthly-benchmarks-dropdown');
        const btn = document.getElementById('monthly-benchmarks-btn');
        if (!dropdown) return;
        if (dropdown.style.display === 'none') {
            dropdown.style.display = 'block';
            btn.classList.add('is-expanded');
        } else {
            dropdown.style.display = 'none';
            btn.classList.remove('is-expanded');
        }
    };

    let _cachedMonthlyBenchmarks = null;
    let _cachedYearlyBenchmarks  = null;

    function getCurrentMonthString() {
        const d = new Date();
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
    }

    function getPreviousMonthString() {
        const d = new Date();
        let y = d.getFullYear();
        let m = d.getMonth(); // 0-indexed
        if (m === 0) {
            m = 12;
            y -= 1;
        }
        return y + '-' + String(m).padStart(2, '0');
    }

    function getMonthlySummaryPeriod(now = new Date()) {
        const reportDate = new Date(now);
        const isFirstDayOfMonth = reportDate.getDate() === 1;
        if (reportDate.getDate() === 1) {
            reportDate.setMonth(reportDate.getMonth() - 1);
        }
        const year = reportDate.getFullYear();
        const month = String(reportDate.getMonth() + 1).padStart(2, '0');
        const monthStr = `${year}-${month}`;
        return {
            monthStr,
            startDate: `${monthStr}-01`,
            completedMonth: isFirstDayOfMonth,
        };
    }

    function firstSnapshotOnOrAfter(snapshots, date) {
        return snapshots.find(snapshot => snapshot.date >= date) || null;
    }

    function previousMonthString(monthStr) {
        const [yearPart, monthPart] = String(monthStr || '').split('-');
        let year = Number(yearPart);
        let month = Number(monthPart);
        if (!Number.isFinite(year) || !Number.isFinite(month)) return '';
        month -= 1;
        if (month < 1) {
            month = 12;
            year -= 1;
        }
        return `${year}-${String(month).padStart(2, '0')}`;
    }

    function benchmarkReturnForPeriod(returns, monthStr, livePrice, completedMonth) {
        const monthReturn = returns.find(row => row.month === monthStr);
        if (monthReturn && completedMonth && Number.isFinite(Number(monthReturn.returnPct))) {
            return Number(monthReturn.returnPct);
        }
        const prevMonthReturn = monthReturn ? null : returns.find(row => row.month === previousMonthString(monthStr));
        const openPrice = Number(monthReturn?.openPrice || prevMonthReturn?.closePrice || 0);
        if (openPrice > 0 && livePrice > 0) {
            return (livePrice - openPrice) / openPrice * 100;
        }
        if (monthReturn && Number.isFinite(Number(monthReturn.returnPct))) {
            return Number(monthReturn.returnPct);
        }
        return null;
    }

    async function refreshMonthlySummary() {
        try {
            if (typeof PortfolioClient === 'undefined') return;

            const monthlyPeriod = getMonthlySummaryPeriod();
            const currentMonthStr = monthlyPeriod.monthStr;

            // 1. Fetch snapshots
            const snapshotData = await PortfolioClient.listSnapshots('summary');
            const snapshots = (snapshotData?.snapshots || [])
                .map(s => ({
                    date: String(s.snapshotDate || '').slice(0, 10),
                    value: Number(s.portfolioValue || 0),
                    investment: Number(s.investmentValue || 0)
                }))
                .sort((a, b) => a.date.localeCompare(b.date));

            // Start snapshot is ideally the last snapshot strictly before this month
            let monthStartSnap = null;
            const prevSnaps = snapshots.filter(r => r.date < monthlyPeriod.startDate);
            if (prevSnaps.length > 0) {
                monthStartSnap = prevSnaps[prevSnaps.length - 1];
            } else {
                // Fallback: first snapshot of this month (only happens for the very first month)
                monthStartSnap = snapshots.find(r => r.date >= monthlyPeriod.startDate) || snapshots[0] || null;
            }

            const prevMonthValue = monthStartSnap ? monthStartSnap.value : 0;
            const prevMonthInvestment = monthStartSnap ? monthStartSnap.investment : 0;
            const currentTotalValue = window.PORTFOLIO_TOTAL_VALUE || 0;

            let latestInvestment = 0;
            if (snapshots.length > 0) {
                latestInvestment = snapshots[snapshots.length - 1].investment;
            }
            const currentInvestment = latestInvestment;

            const monthlyReturnVal = (currentTotalValue - prevMonthValue) - (currentInvestment - prevMonthInvestment);
            
            const netFlow = currentInvestment - prevMonthInvestment;
            const denom = prevMonthValue + netFlow * 0.5;
            const monthlyReturnPct = denom > 0 ? (monthlyReturnVal / denom * 100) : 0;

            const returnValEl = document.getElementById('monthly-return-val');
            const returnPctEl = document.getElementById('monthly-return-pct');
            if (returnValEl) {
                const sign = monthlyReturnVal >= 0 ? '+' : '';
                const color = monthlyReturnVal >= 0 ? '#27ae60' : '#c0392b';
                returnValEl.textContent = sign + monthlyReturnVal.toLocaleString('pl-PL', { minimumFractionDigits: 2 }) + ' PLN';
                returnValEl.style.color = color;
            }
            if (returnPctEl) {
                const sign = monthlyReturnPct >= 0 ? '+' : '';
                const color = monthlyReturnPct >= 0 ? '#27ae60' : '#c0392b';
                returnPctEl.textContent = sign + monthlyReturnPct.toFixed(2) + '%';
                returnPctEl.style.color = color;
            }

            // 2. Fetch Retirement config
            let monthlyDepositGoal = 0;
            let expectedYearlyReturnWorking = 0;
            if (typeof RetirementPlansClient !== 'undefined' && RetirementPlansClient.listPlans) {
                try {
                    const res = await RetirementPlansClient.listPlans();
                    const plans = Array.isArray(res) ? res : (res && res.plans ? res.plans : []);
                    if (plans && plans.length > 0) {
                        const primary = plans[0];
                        monthlyDepositGoal = Number(primary.monthlyInvestment || 0);
                        expectedYearlyReturnWorking = Number(primary.expectedYearlyReturnWorking || 0);
                    }
                } catch (_) {}
            }

            const monthlyPctGoal = expectedYearlyReturnWorking / 12;
            const monthlyReturnGoal = prevMonthValue * (monthlyPctGoal / 100);

            // 3. Fetch current month's deposits
            let actualMonthlyDeposit = 0;
            if (typeof LedgerTransactions !== 'undefined' && LedgerTransactions.loadRows) {
                try {
                    const txs = await LedgerTransactions.loadRows();
                    for (const tx of txs) {
                        if (tx.date && tx.date.startsWith(currentMonthStr)) {
                            if (tx.operation === 'Deposit') {
                                actualMonthlyDeposit += Math.abs(Number(tx.value || 0));
                            }
                        }
                    }
                } catch (_) {}
            }

            // Update Goals DOM
            const depositStatusEl = document.getElementById('monthly-deposit-status');
            const depositBarEl = document.getElementById('monthly-deposit-bar');
            const depositPctEl = document.getElementById('monthly-deposit-pct');

            if (depositStatusEl) {
                depositStatusEl.textContent = actualMonthlyDeposit.toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' / ' + monthlyDepositGoal.toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' PLN';
            }
            if (depositBarEl && depositPctEl) {
                const depPct = monthlyDepositGoal > 0 ? (actualMonthlyDeposit / monthlyDepositGoal * 100) : 0;
                depositBarEl.style.width = Math.min(100, depPct) + '%';
                depositPctEl.textContent = Math.round(depPct) + '%';
            }

            const returnGoalStatusEl = document.getElementById('monthly-return-goal-status');
            const returnBarEl = document.getElementById('monthly-return-bar');
            const returnPctGoalEl = document.getElementById('monthly-return-pct-goal');

            if (returnGoalStatusEl) {
                returnGoalStatusEl.textContent = monthlyReturnVal.toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' / ' + monthlyReturnGoal.toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' PLN';
            }
            if (returnBarEl && returnPctGoalEl) {
                let retPctGoal = 0;
                if (monthlyReturnVal < 0) {
                    retPctGoal = 0;
                    returnBarEl.classList.add('negative-bar');
                } else {
                    returnBarEl.classList.remove('negative-bar');
                    retPctGoal = monthlyReturnGoal > 0 ? (monthlyReturnVal / monthlyReturnGoal * 100) : 100;
                }
                returnBarEl.style.width = Math.min(100, retPctGoal) + '%';
                returnPctGoalEl.textContent = Math.round(retPctGoal) + '%';
            }

            // 4. Benchmarks Comparison
            const livePrices = window.BENCHMARK_LIVE_PRICES;
            if (livePrices && Object.keys(livePrices).length > 0) {
                if (!_cachedMonthlyBenchmarks) {
                    _cachedMonthlyBenchmarks = {};
                    await Promise.all(
                        DASHBOARD_BENCHMARK_COLS.map(async b => {
                            try {
                                const data = await PortfolioClient.getBenchmarkReturns(b.id, '2010-01');
                                _cachedMonthlyBenchmarks[b.id] = data?.returns || [];
                            } catch (_) {
                                _cachedMonthlyBenchmarks[b.id] = [];
                            }
                        })
                    );
                }

                let wins = 0;
                let losses = 0;
                let listHTML = '';

                for (const b of DASHBOARD_BENCHMARK_COLS) {
                    const returns = _cachedMonthlyBenchmarks[b.id] || [];
                    const livePrice = Number(livePrices[b.id] || 0);
                    const bmReturnPct = benchmarkReturnForPeriod(returns, currentMonthStr, livePrice, monthlyPeriod.completedMonth);
                    if (bmReturnPct !== null) {
                        const didBeat = monthlyReturnPct > bmReturnPct;
                        if (didBeat) {
                            wins++;
                        } else {
                            losses++;
                        }
                        const sign = bmReturnPct >= 0 ? '+' : '';
                        listHTML += `
                            <div class="monthly-bench-item ${didBeat ? 'win' : 'loss'}">
                                <span class="monthly-bench-name">${b.short}</span>
                                <span class="monthly-bench-val">${sign}${bmReturnPct.toFixed(2)}%</span>
                            </div>
                        `;
                    }
                }

                const scoreEl = document.getElementById('monthly-benchmarks-score');
                const dropdownEl = document.getElementById('monthly-benchmarks-dropdown');

                if (scoreEl) {
                    scoreEl.textContent = `Beat ${wins} / Lost ${losses}`;
                    if (wins > losses) {
                        scoreEl.style.color = '#27ae60';
                    } else if (wins < losses) {
                        scoreEl.style.color = '#c0392b';
                    } else {
                        scoreEl.style.color = '';
                    }
                }
                if (dropdownEl) {
                    dropdownEl.innerHTML = listHTML || '<div class="stats-empty">No benchmark price data available.</div>';
                }
            }

        } catch (e) {
            console.error('refreshMonthlySummary failed:', e);
        }
    }

    window.toggleYearlyBenchmarksList = function () {
        const dropdown = document.getElementById('yearly-benchmarks-dropdown');
        const btn = document.getElementById('yearly-benchmarks-btn');
        if (!dropdown) return;
        if (dropdown.style.display === 'none') {
            dropdown.style.display = 'block';
            btn.classList.add('is-expanded');
        } else {
            dropdown.style.display = 'none';
            btn.classList.remove('is-expanded');
        }
    };

    function getPreviousYearEndString() {
        const d = new Date();
        const prevYear = d.getFullYear() - 1;
        return prevYear + '-12';
    }

    async function refreshYearlySummary() {
        try {
            if (typeof PortfolioClient === 'undefined') return;

            const currentYearStr = String(new Date().getFullYear()) + '-';
            const prevYearEndStr = getPreviousYearEndString();

            // 1. Fetch snapshots
            const snapshotData = await PortfolioClient.listSnapshots('summary');
            const snapshots = (snapshotData?.snapshots || [])
                .map(s => ({
                    date: String(s.snapshotDate || '').slice(0, 10),
                    value: Number(s.portfolioValue || 0),
                    investment: Number(s.investmentValue || 0)
                }))
                .sort((a, b) => a.date.localeCompare(b.date));

            let prevYearSnap = null;
            for (const s of snapshots) {
                if (s.date.startsWith(prevYearEndStr)) {
                    prevYearSnap = s;
                }
            }
            if (!prevYearSnap && snapshots.length > 0) {
                prevYearSnap = snapshots[0];
            }

            const prevYearValue = prevYearSnap ? prevYearSnap.value : 0;
            const prevYearInvestment = prevYearSnap ? prevYearSnap.investment : 0;
            const currentTotalValue = window.PORTFOLIO_TOTAL_VALUE || 0;

            let latestInvestment = 0;
            if (snapshots.length > 0) {
                latestInvestment = snapshots[snapshots.length - 1].investment;
            }
            const currentInvestment = latestInvestment;

            const yearlyReturnVal = (currentTotalValue - prevYearValue) - (currentInvestment - prevYearInvestment);
            
            const netFlow = currentInvestment - prevYearInvestment;
            const denom = prevYearValue + netFlow * 0.5;
            const yearlyReturnPct = denom > 0 ? (yearlyReturnVal / denom * 100) : 0;

            const returnValEl = document.getElementById('yearly-return-val');
            const returnPctEl = document.getElementById('yearly-return-pct');
            if (returnValEl) {
                const sign = yearlyReturnVal >= 0 ? '+' : '';
                const color = yearlyReturnVal >= 0 ? '#27ae60' : '#c0392b';
                returnValEl.textContent = sign + yearlyReturnVal.toLocaleString('pl-PL', { minimumFractionDigits: 2 }) + ' PLN';
                returnValEl.style.color = color;
            }
            if (returnPctEl) {
                const sign = yearlyReturnPct >= 0 ? '+' : '';
                const color = yearlyReturnPct >= 0 ? '#27ae60' : '#c0392b';
                returnPctEl.textContent = sign + yearlyReturnPct.toFixed(2) + '%';
                returnPctEl.style.color = color;
            }

            // 2. Fetch Retirement config
            let monthlyDepositGoal = 0;
            let expectedYearlyReturnWorking = 0;
            if (typeof RetirementPlansClient !== 'undefined' && RetirementPlansClient.listPlans) {
                try {
                    const res = await RetirementPlansClient.listPlans();
                    const plans = Array.isArray(res) ? res : (res && res.plans ? res.plans : []);
                    if (plans && plans.length > 0) {
                        const primary = plans[0];
                        monthlyDepositGoal = Number(primary.monthlyInvestment || 0);
                        expectedYearlyReturnWorking = Number(primary.expectedYearlyReturnWorking || 0);
                    }
                } catch (_) {}
            }

            const yearlyDepositGoal = monthlyDepositGoal * 12;
            const yearlyReturnGoal = prevYearValue * (expectedYearlyReturnWorking / 100);

            // 3. Fetch current year's deposits
            let actualYearlyDeposit = 0;
            if (typeof LedgerTransactions !== 'undefined' && LedgerTransactions.loadRows) {
                try {
                    const txs = await LedgerTransactions.loadRows();
                    for (const tx of txs) {
                        if (tx.date && tx.date.startsWith(currentYearStr)) {
                            if (tx.operation === 'Deposit') {
                                actualYearlyDeposit += Math.abs(Number(tx.value || 0));
                            }
                        }
                    }
                } catch (_) {}
            }

            // Update Goals DOM
            const depositStatusEl = document.getElementById('yearly-deposit-status');
            const depositBarEl = document.getElementById('yearly-deposit-bar');
            const depositPctEl = document.getElementById('yearly-deposit-pct');

            if (depositStatusEl) {
                depositStatusEl.textContent = actualYearlyDeposit.toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' / ' + yearlyDepositGoal.toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' PLN';
            }
            if (depositBarEl && depositPctEl) {
                const depPct = yearlyDepositGoal > 0 ? (actualYearlyDeposit / yearlyDepositGoal * 100) : 0;
                depositBarEl.style.width = Math.min(100, depPct) + '%';
                depositPctEl.textContent = Math.round(depPct) + '%';
            }

            const returnGoalStatusEl = document.getElementById('yearly-return-goal-status');
            const returnBarEl = document.getElementById('yearly-return-bar');
            const returnPctGoalEl = document.getElementById('yearly-return-pct-goal');

            if (returnGoalStatusEl) {
                returnGoalStatusEl.textContent = yearlyReturnVal.toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' / ' + yearlyReturnGoal.toLocaleString('pl-PL', { maximumFractionDigits: 0 }) + ' PLN';
            }
            if (returnBarEl && returnPctGoalEl) {
                let retPctGoal = 0;
                if (yearlyReturnVal < 0) {
                    retPctGoal = 0;
                    returnBarEl.classList.add('negative-bar');
                } else {
                    returnBarEl.classList.remove('negative-bar');
                    retPctGoal = yearlyReturnGoal > 0 ? (yearlyReturnVal / yearlyReturnGoal * 100) : 100;
                }
                returnBarEl.style.width = Math.min(100, retPctGoal) + '%';
                returnPctGoalEl.textContent = Math.round(retPctGoal) + '%';
            }

            // 4. Benchmarks Comparison
            const livePrices = window.BENCHMARK_LIVE_PRICES;
            if (livePrices && Object.keys(livePrices).length > 0) {
                if (!_cachedYearlyBenchmarks) {
                    _cachedYearlyBenchmarks = {};
                }
                // Fetch any benchmark not yet successfully cached
                await Promise.all(
                    DASHBOARD_BENCHMARK_COLS.map(async b => {
                        if (_cachedYearlyBenchmarks[b.id] && _cachedYearlyBenchmarks[b.id].length > 0) return;
                        try {
                            const data = await PortfolioClient.getBenchmarkReturns(b.id, '2010-01');
                            const returns = data?.returns || [];
                            if (returns.length > 0) {
                                _cachedYearlyBenchmarks[b.id] = returns;
                            }
                        } catch (_) {
                            // leave uncached so next call retries
                        }
                    })
                );

                let wins = 0;
                let losses = 0;
                let listHTML = '';

                for (const b of DASHBOARD_BENCHMARK_COLS) {
                    const returns = (_cachedYearlyBenchmarks && _cachedYearlyBenchmarks[b.id]) || (_cachedMonthlyBenchmarks && _cachedMonthlyBenchmarks[b.id]) || [];
                    let prevYearClosePrice = null;
                    for (const r of returns) {
                        if (r.month === prevYearEndStr) {
                            prevYearClosePrice = Number(r.closePrice || 0);
                            break;
                        }
                    }
                    if (!prevYearClosePrice && returns.length > 0) {
                        prevYearClosePrice = Number(returns[returns.length - 1].closePrice || 0);
                    }

                    const livePrice = Number(livePrices[b.id] || 0);
                    if (prevYearClosePrice && livePrice) {
                        const bmReturnPct = (livePrice - prevYearClosePrice) / prevYearClosePrice * 100;
                        const didBeat = yearlyReturnPct > bmReturnPct;
                        if (didBeat) {
                            wins++;
                        } else {
                            losses++;
                        }
                        const sign = bmReturnPct >= 0 ? '+' : '';
                        listHTML += `
                            <div class="yearly-bench-item ${didBeat ? 'win' : 'loss'}">
                                <span class="yearly-bench-name">${b.short}</span>
                                <span class="yearly-bench-val">${sign}${bmReturnPct.toFixed(2)}%</span>
                            </div>
                        `;
                    }
                }

                const scoreEl = document.getElementById('yearly-benchmarks-score');
                const dropdownEl = document.getElementById('yearly-benchmarks-dropdown');

                if (scoreEl) {
                    scoreEl.textContent = `Beat ${wins} / Lost ${losses}`;
                    if (wins > losses) {
                        scoreEl.style.color = '#27ae60';
                    } else if (wins < losses) {
                        scoreEl.style.color = '#c0392b';
                    } else {
                        scoreEl.style.color = '';
                    }
                }
                if (dropdownEl) {
                    dropdownEl.innerHTML = listHTML || '<div class="stats-empty">No benchmark price data available.</div>';
                }
            }

        } catch (e) {
            console.error('refreshYearlySummary failed:', e);
        }
    }

    document.addEventListener('liveDataReady', function (e) {
        const data = e?.detail || {};
        
        let cachedPrices = {};
        try {
            const cachedStr = localStorage.getItem('benchmark_live_prices_cache');
            if (cachedStr) cachedPrices = JSON.parse(cachedStr);
        } catch (err) {}

        if (data.benchmarkLivePrices && Object.keys(data.benchmarkLivePrices).length > 0) {
            window.BENCHMARK_LIVE_PRICES = { ...cachedPrices, ...data.benchmarkLivePrices };
            try {
                localStorage.setItem('benchmark_live_prices_cache', JSON.stringify(window.BENCHMARK_LIVE_PRICES));
            } catch (err) {}
        } else if (Object.keys(cachedPrices).length > 0) {
            window.BENCHMARK_LIVE_PRICES = cachedPrices;
        } else if (data.benchmarkLivePrices) {
            window.BENCHMARK_LIVE_PRICES = data.benchmarkLivePrices;
        }

        refreshMonthlySummary();
        refreshYearlySummary();
    });
}());

async function renderDashSparkline() {
    const canvas = document.getElementById('dashSparklineChart');
    if (!canvas) return;

    if (typeof Chart === 'undefined') return;

    try {
        if (typeof _loadHistorySnapshots !== 'function') return;
        
        const history = await _loadHistorySnapshots();
        if (!history || !history.summary || history.summary.length < 2) return;

        const data = history.summary;
        const byMonth = {};
        for (const row of data) {
            byMonth[row.date.slice(0, 7)] = { value: row.value, investment: row.investment };
        }

        const months = Object.keys(byMonth).sort();
        const recentMonths = months.slice(-7);
        if (recentMonths.length < 2) return;

        const labels = [];
        const values = [];
        const colors = [];
        for (let i = 1; i < recentMonths.length; i++) {
            const prev = byMonth[recentMonths[i - 1]];
            const curr = byMonth[recentMonths[i]];
            const netGain = Number(((curr.value - prev.value) - (curr.investment - prev.investment)).toFixed(2));
            
            const [year, month] = recentMonths[i].split('-');
            const monthDate = new Date(year, month - 1);
            // Just the short month name, like "Jan" or "Feb" (or "Sty", "Lut" in Polish)
            const monthName = monthDate.toLocaleString('en-US', { month: 'short' });
            
            labels.push(monthName);
            values.push(netGain);
            colors.push(netGain >= 0 ? 'rgba(46, 204, 113, 0.8)' : 'rgba(231, 76, 60, 0.8)');
        }

        if (window._dashSparkline) {
            window._dashSparkline.destroy();
        }

        window._dashSparkline = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderRadius: 3,
                    barPercentage: 0.95,
                    categoryPercentage: 0.9
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        displayColors: false,
                        callbacks: {
                            label: ctx => {
                                const val = Number(ctx.parsed.y);
                                return (val >= 0 ? '+' : '') + val.toLocaleString('pl-PL', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' PLN';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        grid: { display: false, drawBorder: false },
                        ticks: { color: '#94a3b8', font: { size: 10, family: 'monospace' } }
                    },
                    y: {
                        display: false,
                        min: Math.min(...values, 0) * 1.02,
                        max: Math.max(...values, 0) * 1.02,
                    }
                },
                layout: {
                    padding: 0
                }
            }
        });
    } catch (e) {
        console.error('Failed to render dashboard sparkline:', e);
    }
}

window.addEventListener('roastfolio:themechange', function() {
    if (typeof renderDashboard === 'function') {
        renderDashboard();
    }
});

