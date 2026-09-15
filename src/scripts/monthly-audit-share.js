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
        return {
            benchmark_id: id, benchmark_name: name, benchmark_currency: currency,
            points: (Array.isArray(journey.points) ? journey.points : [])
                .filter(point => point && validDate(point.date))
                .map(point => ({ date: point.date,
                    portfolio_pct: finite(point.portfolio_pct) ? Number(point.portfolio_pct) : null,
                    benchmark_pct: finite(point.benchmark_pct) ? Number(point.benchmark_pct) : null }))
                .sort((a, b) => a.date.localeCompare(b.date)),
        };
    }
    const percent = value => finite(value)
        ? `${Number(value) > 0 ? '+' : ''}${(Number(value) || 0).toLocaleString('en-GB', { maximumFractionDigits: 2 })}%` : 'No data';
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
        ctx.strokeStyle = '#192824';
        ctx.globalAlpha = 0.1;
        ctx.lineWidth = 2;
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
        text('CUMULATIVE RETURNS', 72, 826, 21, '#aab7c5');
        const { points, benchmark_name: benchmarkName, benchmark_currency: currency } = model.journey;
        const legend = (label, y, color, dashed = false) => {
            ctx.strokeStyle = color; ctx.lineWidth = 4; ctx.setLineDash(dashed ? [9, 7] : []);
            ctx.beginPath(); ctx.moveTo(72, y - 7); ctx.lineTo(108, y - 7); ctx.stroke(); ctx.setLineDash([]);
            text(label, 122, y, 23, color, 886);
        };
        legend('Portfolio · cumulative TWR', 862, '#b8e4ca');
        legend(`${benchmarkName} · ${currency || 'currency unavailable'}`, 896, '#d0c5f4', true);
        const values = points.flatMap(point => [point.portfolio_pct, point.benchmark_pct].filter(finite));
        const dates = points.map(point => Date.parse(`${point.date}T00:00:00Z`));
        if (new Set(dates).size >= 2 && values.length) {
            const first = Math.min(...dates), last = Math.max(...dates);
            const low = Math.min(0, ...values), high = Math.max(0, ...values);
            const x = date => 150 + (Date.parse(`${date}T00:00:00Z`) - first) / (last - first) * 858;
            const y = value => 930 + (high - value) / (high - low || 1) * 145;
            [...new Set([high, 0, low])].forEach(value => {
                ctx.strokeStyle = value === 0 ? '#aab7c5' : '#46515f';
                ctx.lineWidth = value === 0 ? 2 : 1; ctx.setLineDash(value === 0 ? [] : [5, 6]);
                ctx.beginPath(); ctx.moveTo(150, y(value)); ctx.lineTo(1008, y(value)); ctx.stroke();
                text(percent(value), 72, y(value) + 6, 18, '#aab7c5', 70);
            });
            ['portfolio_pct', 'benchmark_pct'].forEach((key, index) => {
                ctx.strokeStyle = ctx.fillStyle = index ? '#d0c5f4' : '#b8e4ca';
                ctx.lineWidth = 4; ctx.setLineDash(index ? [9, 7] : []);
                ctx.beginPath();
                let connected = false;
                points.forEach(point => {
                    if (!finite(point[key])) { connected = false; return; }
                    if (connected) ctx.lineTo(x(point.date), y(point[key]));
                    else ctx.moveTo(x(point.date), y(point[key]));
                    connected = true;
                });
                ctx.stroke(); ctx.setLineDash([]);
                // Isolated observations remain visible, without joining across gaps.
                points.filter(point => finite(point[key])).forEach(point => {
                    ctx.beginPath(); ctx.arc(x(point.date), y(point[key]), 3, 0, Math.PI * 2); ctx.fill();
                });
            });
            text(points[0].date, 150, 1105, 19, '#aab7c5');
            ctx.textAlign = 'right'; text(points[points.length - 1].date, 1008, 1105, 19, '#aab7c5'); ctx.textAlign = 'left';
        } else {
            text('Dated return history unavailable', 72, 1005, 28, '#aab7c5');
        }
        ctx.setLineDash([]);
        const missing = ['portfolio_pct', 'benchmark_pct'].map((key, i) => points.some(point => finite(point[key])) ? '' : `${i ? 'Benchmark' : 'Portfolio'} unavailable`).filter(Boolean);
        text(missing.length ? missing.join(' · ') : 'Native-currency benchmark · not PLN-adjusted. Gaps = no data.', 72, 1137, 18, '#aab7c5');
        text(`Max drawdown  ${model.maxDrawdown}`, 72, 1170, 28, '#f4f5f7');
        ctx.fillStyle = '#384250'; ctx.fillRect(72, 1220, 936, 1);
        text('A month in perspective. Not investment advice.', 72, 1282, 22, '#aab7c5');
        return canvas;
    }

    let activeDialog = null;
    function open(item) {
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
                    <p class="monthly-share-status" role="status" aria-live="polite">Preparing your image…</p>
                </div></div>`;
        document.body.appendChild(dialog);
        const canvas = dialog.querySelector('canvas');
        const privacy = dialog.querySelector('[data-private]');
        const share = dialog.querySelector('[data-share]');
        const download = dialog.querySelector('[data-download]');
        const status = dialog.querySelector('[role="status"]');
        let file = null;
        let generation = 0;
        let sharing = false;
        const prepare = () => {
            const version = ++generation;
            file = null; share.disabled = download.disabled = true;
            status.textContent = 'Preparing your image…';
            try {
                const model = buildModel(item, { hideAmounts: privacy.checked });
                drawPoster(canvas, model);
                canvas.setAttribute('aria-label', `${model.title}. TWR ${model.twr}. ${model.hideAmounts ? 'PLN amounts hidden.' : `Nominal change ${model.nominalChange}.`} Dated cumulative portfolio TWR versus ${model.journey.benchmark_name}. Missing observations are gaps. Max drawdown ${model.maxDrawdown}.`);
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