/* Monthly recap presentation contract. No API requests or email delivery here. */
(() => {
    'use strict';

    const finite = value => (typeof value === 'number' || typeof value === 'string' && value.trim() !== '') && Number.isFinite(Number(value));
    const validDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
        && Number.isFinite(Date.parse(`${value}T00:00:00Z`)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
    // Never trust report-supplied names/currencies in a public image.
    const benchmarks = Object.freeze({
        WIG: ['WIG', 'PLN'], DAX: ['DAX', 'EUR'], FTSE100: ['FTSE 100', 'GBP'],
        WIG20: ['WIG20', 'PLN'], MWIG40: ['mWIG40', 'PLN'], SWIG80: ['sWIG80', 'PLN'],
        SP500: ['S&P 500', 'USD'], NASDAQ: ['NASDAQ Composite', 'USD'],
        MSCI_WORLD: ['MSCI World · IWDA proxy', 'EUR'],
    });
    function buildJourney(item) {
        const journey = item.journey || {};
        const id = typeof journey.benchmark_id === 'string' && Object.hasOwn(benchmarks, journey.benchmark_id) ? journey.benchmark_id : null;
        const [name, currency] = id ? benchmarks[id] : ['Benchmark', null];
        const rawPoints = (Array.isArray(journey.points) ? journey.points : [])
            .filter(point => point && validDate(point.date))
            .map(point => ({ date: point.date,
                portfolio_pct: finite(point.portfolio_pct) ? Number(point.portfolio_pct) : null,
                benchmark_pct: finite(point.benchmark_pct) ? Number(point.benchmark_pct) : null }))
            .sort((a, b) => a.date.localeCompare(b.date));
        const hasAnyBenchmark = rawPoints.some(point => point.benchmark_pct !== null);
        let lastBenchmark = hasAnyBenchmark ? 0 : null;
        const points = rawPoints.map(point => {
            let bm = point.benchmark_pct;
            if (bm !== null) {
                lastBenchmark = bm;
            } else if (lastBenchmark !== null) {
                bm = lastBenchmark;
            }
            return {
                date: point.date,
                portfolio_pct: point.portfolio_pct,
                benchmark_pct: bm,
            };
        });
        return {
            benchmark_id: id, benchmark_name: name, benchmark_currency: currency,
            points,
        };
    }
    const percent = value => finite(value)
        ? `${Number(value) > 0 ? '+' : ''}${(Number(value) || 0).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%` : 'No data';
    const money = value => finite(value)
        ? `${Number(value) > 0 ? '+' : ''}${Math.round(Number(value)).toLocaleString('en-GB')} PLN` : 'No data';
    const periodTitle = period => {
        if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(period || '')) return 'Monthly recap';
        return new Date(`${period}-01T12:00:00Z`).toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' });
    };
    const headline = item => !finite(item.overall_twr_pct) ? 'Your month, in perspective.'
        : Number(item.overall_twr_pct) > 0 ? 'A little more momentum.'
        : Number(item.overall_twr_pct) < 0 ? 'A step back. The story continues.'
        : 'Holding your ground.';

    // Allowlist, not a copy of the wrap: never include identity, wallet names,
    // holdings, diary entries, balances or private amounts when privacy is on.
    function buildModel(item, { hideAmounts = true } = {}) {
        const heroBenchmarks = item._heroBenchmarks || {};
        let wigVal = heroBenchmarks.wig;
        let msciVal = heroBenchmarks.msci;
        if (!finite(wigVal) && Array.isArray(item.market_context)) {
            const w = item.market_context.find(e => e?.id === 'WIG');
            if (finite(w?.return_pct)) wigVal = Number(w.return_pct);
        }
        if (!finite(msciVal) && Array.isArray(item.market_context)) {
            const m = item.market_context.find(e => e?.id === 'MSCI_WORLD');
            if (finite(m?.return_pct)) msciVal = Number(m.return_pct);
        }
        return {
            schemaVersion: 2,
            period: /^\d{4}-(0[1-9]|1[0-2])$/.test(item.period || '') ? item.period : '',
            title: periodTitle(item.period),
            headline: headline(item),
            twr: percent(item.overall_twr_pct),
            direction: !finite(item.overall_twr_pct) || Number(item.overall_twr_pct) === 0 ? 'neutral' : Number(item.overall_twr_pct) > 0 ? 'positive' : 'negative',
            hideAmounts: Boolean(hideAmounts),
            nominalChange: hideAmounts ? null : money(item.overall_nominal_change_pln),
            maxDrawdown: percent(item.max_drawdown_pct),
            journey: buildJourney(item),
            benchmarks: {
                wig: finite(wigVal) ? percent(wigVal) : null,
                msci: finite(msciVal) ? percent(msciVal) : null,
            },
        };
    }

    function drawPoster(canvas, model) {
        canvas.width = 1080;
        canvas.height = 1350;
        const ctx = canvas.getContext('2d');
        if (!ctx) throw new Error('Image export is not supported in this browser.');
        ctx.fillStyle = '#151b26';
        ctx.fillRect(0, 0, 1080, 1350);
        const accent = model.direction === 'negative' ? '#f4bea8' : model.direction === 'positive' ? '#d0f5b0' : '#cec4f5';
        ctx.fillStyle = accent;
        ctx.fillRect(0, 0, 1080, 780);

        // Subtle ambient lighting glow
        const glow = ctx.createRadialGradient(180, 180, 30, 180, 180, 750);
        glow.addColorStop(0, 'rgba(255, 255, 255, 0.35)');
        glow.addColorStop(1, 'rgba(255, 255, 255, 0)');
        ctx.fillStyle = glow;
        ctx.fillRect(0, 0, 1080, 780);

        // Subtle topographic contour curves
        ctx.strokeStyle = '#192824';
        ctx.lineWidth = 2;
        const curves = [
            [[-100, 720], [250, 340], [680, 820], [1200, 400]],
            [[-100, 580], [300, 220], [640, 680], [1200, 260]],
            [[-100, 440], [350, 100], [600, 540], [1200, 130]],
            [[-100, 300], [400, 20],  [560, 400], [1200, 20]]
        ];
        curves.forEach((pts, idx) => {
            ctx.globalAlpha = 0.04 + idx * 0.01;
            ctx.beginPath();
            ctx.moveTo(pts[0][0], pts[0][1]);
            ctx.bezierCurveTo(pts[1][0], pts[1][1], pts[2][0], pts[2][1], pts[3][0], pts[3][1]);
            ctx.stroke();
        });

        // Architectural dot matrix
        ctx.globalAlpha = 0.08;
        for (let x = 24; x < 1080; x += 36) {
            for (let y = 24; y < 780; y += 36) {
                ctx.beginPath(); ctx.arc(x, y, 1, 0, Math.PI * 2); ctx.stroke();
            }
        }
        ctx.globalAlpha = 1;
        const text = (value, x, y, size, color, maxWidth = 936, weight = 600) => {
            ctx.fillStyle = color;
            let fitted = size;
            do { ctx.font = `${weight} ${fitted}px system-ui, sans-serif`; fitted -= 1; }
            while (ctx.measureText(value).width > maxWidth && fitted > 12);
            ctx.fillText(value, x, y);
        };
        text('roastfolio', 72, 96, 38, '#23352a', 400, 500);
        text('MONTHLY EDITION', 740, 96, 20, '#23352a', 268);
        text(model.title, 72, 225, 66, '#17281e');
        text('Wrapped.', 72, 310, 84, '#17281e');
        text(model.twr, 64, 495, 158, '#17281e');
        text('TIME-WEIGHTED RETURN', 76, 543, 23, '#314735');
        text(model.nominalChange ?? 'Amounts kept private.', 76, 625, 43, '#17281e');
        text(model.hideAmounts ? 'Your story. Your numbers to keep.' : 'Nominal change · net of deposits and withdrawals', 76, 668, 22, '#314735');
        text(model.headline, 76, 731, 29, '#17281e');
        if (model.benchmarks && (model.benchmarks.wig || model.benchmarks.msci)) {
            text('BENCHMARKS', 672, 578, 17, '#344634', 312, 600);
            text('Poland (WIG)', 672, 618, 21, '#344634', 200, 500);
            const wigVal = model.benchmarks.wig ?? 'No data';
            ctx.textAlign = 'right';
            text(wigVal, 984, 618, 21, '#17281e', 100, 700);
            ctx.textAlign = 'left';

            text('World (MSCI ACWI)', 672, 656, 21, '#344634', 200, 500);
            const msciVal = model.benchmarks.msci ?? 'No data';
            ctx.textAlign = 'right';
            text(msciVal, 984, 656, 21, '#17281e', 100, 700);
            ctx.textAlign = 'left';
        }
        // — Minimalist chart section —
        const { points, benchmark_name: benchmarkName } = model.journey;
        const chartL = 72, chartR = 1008, chartT = 840, chartB = 1070;
        const chartW = chartR - chartL, chartH = chartB - chartT;

        text('CUMULATIVE RETURNS', 72, 826, 21, '#aab7c5');

        // Compact inline legend: colored dots + labels, right-aligned at top
        const dot = (cx, cy, r, color) => { ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill(); };
        ctx.font = '500 18px system-ui, sans-serif';
        const bmLabel = benchmarkName || 'Benchmark';
        const bmW = ctx.measureText(bmLabel).width;
        const pLabel = 'Portfolio';
        const pW = ctx.measureText(pLabel).width;
        // Legend: Portfolio ● ... Benchmark ●  (right-aligned)
        const legendY = 826;
        const legendGap = 28;
        const totalLegendW = 10 + 8 + pW + legendGap + 10 + 8 + bmW;
        const legendX = chartR - totalLegendW;
        dot(legendX + 5, legendY - 5, 5, '#b8e4ca');
        ctx.fillStyle = '#aab7c5'; ctx.font = '500 18px system-ui, sans-serif';
        ctx.fillText(pLabel, legendX + 18, legendY);
        dot(legendX + 18 + pW + legendGap + 5, legendY - 5, 5, '#d0c5f4');
        ctx.fillText(bmLabel, legendX + 18 + pW + legendGap + 18, legendY);

        const values = points.flatMap(point => [point.portfolio_pct, point.benchmark_pct].filter(finite));
        const dates = points.map(point => Date.parse(`${point.date}T00:00:00Z`));
        if (new Set(dates).size >= 2 && values.length) {
            const first = Math.min(...dates), last = Math.max(...dates);
            const low = Math.min(0, ...values), high = Math.max(0, ...values);
            const range = high - low || 1;
            // Add 8% vertical padding so lines don't touch edges
            const padFrac = 0.08;
            const x = date => chartL + (Date.parse(`${date}T00:00:00Z`) - first) / (last - first) * chartW;
            const y = value => chartT + padFrac * chartH + (high - value) / range * (chartH * (1 - 2 * padFrac));

            // Faint zero baseline only (no grid, no Y-axis labels)
            if (low < 0 && high > 0) {
                ctx.save();
                ctx.strokeStyle = 'rgba(170, 183, 197, 0.25)';
                ctx.lineWidth = 1;
                ctx.setLineDash([6, 8]);
                ctx.beginPath(); ctx.moveTo(chartL, y(0)); ctx.lineTo(chartR, y(0)); ctx.stroke();
                ctx.setLineDash([]);
                ctx.restore();
            }

            // Draw portfolio line + gradient fill
            const pfPoints = points.filter(p => finite(p.portfolio_pct));
            if (pfPoints.length >= 2) {
                // Build segments of continuous finite points
                const segments = [];
                let currentSegment = [];
                points.forEach(p => {
                    if (finite(p.portfolio_pct)) {
                        currentSegment.push({ x: x(p.date), y: y(p.portfolio_pct), date: p.date });
                    } else if (currentSegment.length) {
                        segments.push(currentSegment);
                        currentSegment = [];
                    }
                });
                if (currentSegment.length) segments.push(currentSegment);

                // Gradient fill under each continuous portfolio segment
                ctx.save();
                const grad = ctx.createLinearGradient(0, chartT, 0, chartB);
                grad.addColorStop(0, 'rgba(184, 228, 202, 0.35)');
                grad.addColorStop(0.6, 'rgba(184, 228, 202, 0.08)');
                grad.addColorStop(1, 'rgba(184, 228, 202, 0)');
                ctx.fillStyle = grad;
                segments.forEach(seg => {
                    if (seg.length < 2) return;
                    ctx.beginPath();
                    seg.forEach((c, i) => { if (i === 0) ctx.moveTo(c.x, c.y); else ctx.lineTo(c.x, c.y); });
                    ctx.lineTo(seg[seg.length - 1].x, chartB);
                    ctx.lineTo(seg[0].x, chartB);
                    ctx.closePath();
                    ctx.fill();
                });
                ctx.restore();

                // Portfolio line (retains gaps with moveTo)
                ctx.save();
                ctx.strokeStyle = '#b8e4ca';
                ctx.lineWidth = 3;
                ctx.lineJoin = 'round'; ctx.lineCap = 'round';
                ctx.beginPath();
                let connected = false;
                points.forEach(point => {
                    if (!finite(point.portfolio_pct)) { connected = false; return; }
                    if (connected) ctx.lineTo(x(point.date), y(point.portfolio_pct));
                    else ctx.moveTo(x(point.date), y(point.portfolio_pct));
                    connected = true;
                });
                ctx.stroke();

                // Terminal dot with subtle glow
                const lastPf = pfPoints[pfPoints.length - 1];
                ctx.shadowColor = '#b8e4ca'; ctx.shadowBlur = 12;
                dot(x(lastPf.date), y(lastPf.portfolio_pct), 5, '#b8e4ca');
                ctx.shadowBlur = 0;
                ctx.restore();
            }

            // Draw benchmark line
            const bmPoints = points.filter(p => finite(p.benchmark_pct));
            if (bmPoints.length >= 2) {
                ctx.save();
                ctx.strokeStyle = '#d0c5f4';
                ctx.lineWidth = 2;
                ctx.lineJoin = 'round'; ctx.lineCap = 'round';
                ctx.setLineDash([8, 6]);
                ctx.beginPath();
                let started = false;
                points.forEach(p => {
                    if (!finite(p.benchmark_pct)) { started = false; return; }
                    if (started) ctx.lineTo(x(p.date), y(p.benchmark_pct));
                    else ctx.moveTo(x(p.date), y(p.benchmark_pct));
                    started = true;
                });
                ctx.stroke();
                ctx.setLineDash([]);
                // Terminal dot
                const lastBm = bmPoints[bmPoints.length - 1];
                dot(x(lastBm.date), y(lastBm.benchmark_pct), 4, '#d0c5f4');
                ctx.restore();
            }

            // Single centered x-axis label: "August 2026" derived from the period
            const monthLabel = model.period && /^\d{4}-(0[1-9]|1[0-2])$/.test(model.period)
                ? new Date(`${model.period}-15T12:00:00Z`).toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })
                : model.title || '';
            ctx.textAlign = 'center';
            text(monthLabel, (chartL + chartR) / 2, chartB + 36, 20, '#aab7c5', chartW, 500);
            ctx.textAlign = 'left';
        } else {
            text('Dated return history unavailable', 72, 1005, 28, '#aab7c5');
        }
        ctx.setLineDash([]);
        const missing = ['portfolio_pct', 'benchmark_pct'].map((key, i) => points.some(point => finite(point[key])) ? '' : `${i ? 'Benchmark' : 'Portfolio'} unavailable`).filter(Boolean);
        text(missing.length ? missing.join(' · ') : 'Not PLN-adjusted · weekends extrapolated', 72, 1137, 18, '#aab7c5');
        text(`Max drawdown  ${model.maxDrawdown}`, 72, 1170, 28, '#f4f5f7');
        ctx.fillStyle = '#384250'; ctx.fillRect(72, 1220, 936, 1);
        text('A month in perspective. Not investment advice.', 72, 1282, 22, '#aab7c5');
        return canvas;
    }

    let activeDialog = null;
    function open(item, options = {}) {
        if (activeDialog) return;
        const opener = document.activeElement;
        const dialog = document.createElement('dialog');
        activeDialog = dialog;
        dialog.className = 'monthly-share-dialog';
        dialog.setAttribute('aria-labelledby', 'monthly-share-title');
        dialog.innerHTML = `
            <div class="monthly-share-top"><div><span>Your month, ready to go</span><h2 id="monthly-share-title">Share your recap.</h2></div>
                <button type="button" data-close aria-label="Close share preview">×</button></div>
            <div class="monthly-share-layout"><div class="monthly-share-preview"><canvas role="img" aria-label="Monthly recap image preview"></canvas></div>
                <div class="monthly-share-options"><h3>Make it yours.</h3>
                    <label><input type="checkbox" data-private checked> Hide PLN amounts</label>
                    <p>Returns and drawdowns are visible. Your identity, balances, holdings and diary are never included.</p>
                    <p>Only this image is shared. Nothing is uploaded automatically.</p>
                    <button type="button" data-share disabled>Share image</button>
                    <button type="button" data-download disabled>Download PNG</button>
                    <button type="button" data-email>Email recap</button>
                    <div class="ma-recipient-prompt" style="display:none;" aria-live="polite"></div>
                    <p class="monthly-share-status" role="status" aria-live="polite">Preparing your image…</p>
                </div></div>`;
        document.body.appendChild(dialog);
        const canvas = dialog.querySelector('canvas');
        const privacy = dialog.querySelector('[data-private]');
        const share = dialog.querySelector('[data-share]');
        const download = dialog.querySelector('[data-download]');
        const emailBtn = dialog.querySelector('[data-email]');
        const status = dialog.querySelector('[role="status"]');
        let file = null;
        let generation = 0;
        let sharing = false;
        let emailing = false;
        let recipientPromptOpen = false;

        const executeEmailSend = async (scope = 'all') => {
            if (emailing) return;
            emailing = true;
            emailBtn.disabled = true;
            status.textContent = 'Sending recap email…';
            try {
                let res = null;
                const emailOpts = {
                    hideCash: Boolean(privacy && privacy.checked),
                    recipientScope: scope,
                };
                if (options && typeof options.onEmail === 'function') {
                    res = await options.onEmail(emailOpts);
                } else if (typeof window.sendMonthlyRecapEmail === 'function') {
                    res = await window.sendMonthlyRecapEmail(item.period, emailOpts);
                } else {
                    throw new Error('Email notification handler unavailable.');
                }
                const msg = (res && res.message) || (scope === 'me'
                    ? 'Recap email sent to you.'
                    : 'Recap email sent to configured recipient(s).');
                status.textContent = `✓ ${msg}`;
            } catch (error) {
                status.textContent = error.message || 'Failed to send recap email.';
            } finally {
                emailing = false;
                emailBtn.disabled = false;
            }
        };

        if (emailBtn) {
            emailBtn.addEventListener('click', async () => {
                if (emailing) return;

                let profile = null;
                try {
                    if (window.UserProfile && typeof window.UserProfile.get === 'function') {
                        profile = await window.UserProfile.get();
                    }
                } catch (_) {}

                const primaryEmail = (profile && profile.email) || '';
                const additional = (profile && profile.settings && Array.isArray(profile.settings.notificationEmails))
                    ? profile.settings.notificationEmails.filter(e => e && e !== primaryEmail)
                    : [];

                // If more than one email address on share list, prompt user to choose recipient scope
                if (primaryEmail && additional.length > 0) {
                    const promptEl = dialog.querySelector('.ma-recipient-prompt');
                    if (!promptEl) {
                        return executeEmailSend('all');
                    }
                    if (recipientPromptOpen) {
                        promptEl.style.display = 'none';
                        recipientPromptOpen = false;
                        return;
                    }
                    recipientPromptOpen = true;
                    promptEl.style.display = 'block';
                    const allCount = additional.length + 1;
                    const allEmails = [primaryEmail, ...additional];
                    const escapeText = s => String(s || '').replace(/[&<>"']/g, c => ({
                        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
                    }[c]));

                    promptEl.innerHTML = `
                        <div class="ma-recipient-prompt-card">
                            <h4 class="ma-recipient-prompt-title">Share recap with:</h4>
                            <div class="ma-recipient-choices">
                                <label class="ma-recipient-choice">
                                    <input type="radio" name="ma-recipient-scope" value="me" checked>
                                    <div class="ma-recipient-choice-body">
                                        <strong>Just me</strong>
                                        <span class="ma-recipient-subtext">${escapeText(primaryEmail)}</span>
                                    </div>
                                </label>
                                <label class="ma-recipient-choice">
                                    <input type="radio" name="ma-recipient-scope" value="all">
                                    <div class="ma-recipient-choice-body">
                                        <strong>All emails on list (${allCount})</strong>
                                        <span class="ma-recipient-subtext" title="${escapeText(allEmails.join(', '))}">${escapeText(allEmails.join(', '))}</span>
                                    </div>
                                </label>
                            </div>
                            <div class="ma-recipient-actions">
                                <button type="button" class="ma-recipient-btn-send" data-send-choice>Send recap email</button>
                                <button type="button" class="ma-recipient-btn-cancel" data-cancel-choice>Cancel</button>
                            </div>
                        </div>
                    `;

                    const sendChoiceBtn = promptEl.querySelector('[data-send-choice]');
                    const cancelChoiceBtn = promptEl.querySelector('[data-cancel-choice]');

                    sendChoiceBtn.addEventListener('click', () => {
                        const selectedRadio = promptEl.querySelector('input[name="ma-recipient-scope"]:checked');
                        const scope = selectedRadio ? selectedRadio.value : 'all';
                        promptEl.style.display = 'none';
                        recipientPromptOpen = false;
                        executeEmailSend(scope);
                    });

                    cancelChoiceBtn.addEventListener('click', () => {
                        promptEl.style.display = 'none';
                        recipientPromptOpen = false;
                        status.textContent = 'Email sharing cancelled.';
                    });
                    return;
                }

                executeEmailSend('me');
            });
        }
        const prepare = () => {
            const version = ++generation;
            file = null; share.disabled = download.disabled = true;
            status.textContent = 'Preparing your image…';
            try {
                const model = buildModel(item, { hideAmounts: privacy.checked });
                drawPoster(canvas, model);
                canvas.setAttribute('aria-label', `${model.title}. TWR ${model.twr}. ${model.hideAmounts ? 'PLN amounts hidden.' : `Nominal change ${model.nominalChange}.`} Dated cumulative portfolio TWR versus ${model.journey.benchmark_name}. Weekends extrapolated. Max drawdown ${model.maxDrawdown}.`);
                canvas.toBlob(blob => {
                    if (version !== generation || !dialog.open) return;
                    if (!blob) { status.textContent = 'Could not create image. Toggle privacy to retry.'; return; }
                    file = new File([blob], `roastfolio-${model.period || 'monthly'}${model.hideAmounts ? '-private' : ''}.png`, { type: 'image/png' });
                    download.disabled = false;
                    let nativeShare = false;
                    try { nativeShare = Boolean(navigator.share && navigator.canShare?.({ files: [file] })); } catch (_) { /* Download remains available. */ }
                    share.hidden = !nativeShare;
                    share.disabled = !nativeShare;
                    status.textContent = nativeShare ? 'Ready to share.' : 'Save the PNG and attach it in your favourite app.';
                }, 'image/png');
            } catch (_) { status.textContent = 'Could not create image. Please close and try again.'; }
        };
        privacy.addEventListener('change', prepare);
        download.addEventListener('click', () => {
            if (!file) return;
            const url = URL.createObjectURL(file);
            const link = document.createElement('a');
            link.href = url; link.download = file.name;
            document.body.appendChild(link); link.click(); link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 30000);
            status.textContent = 'PNG download requested.';
        });
        share.addEventListener('click', async () => {
            if (!file || sharing) return;
            sharing = true; share.disabled = true; privacy.disabled = true;
            try {
                // File is already prepared: call share within the user activation.
                await navigator.share({ files: [file], title: `Roastfolio · ${periodTitle(item.period)}` });
                status.textContent = 'Image handed to your sharing app.';
            } catch (error) {
                status.textContent = error.name === 'AbortError' ? 'Sharing cancelled. Your image is still ready.' : 'Sharing unavailable. Download the PNG instead.';
            } finally { sharing = false; share.disabled = false; privacy.disabled = false; }
        });
        dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
        dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
        dialog.addEventListener('close', () => {
            generation++; file = null; activeDialog = null; dialog.remove();
            if (opener?.isConnected) opener.focus();
        }, { once: true });
        dialog.showModal();
        prepare();
    }

    window.MonthlyAuditPresentation = Object.freeze({ buildModel, buildJourney, drawPoster, headline, periodTitle });
    window.MonthlyAuditShare = Object.freeze({ open });
})();