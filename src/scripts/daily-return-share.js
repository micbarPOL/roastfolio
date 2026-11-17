(function () {
    'use strict';

    const valid = value => typeof value === 'number' && Number.isFinite(value);
    const signed = value => `${value > 0 ? '+' : ''}${value.toFixed(2)}`;
    const palette = { ink: '#151b26', white: '#f5faf7', muted: '#aebeb6', mint: '#d0f5b0', coral: '#f4bea8', amber: '#ffd36e', grid: '#3c4a42', headline: '#23352a' };
    let activeDialog;

    function timestamp(value) {
        if (typeof value === 'number') return value < 1e12 ? value * 1000 : value;
        return typeof value === 'string' && value.trim() ? Date.parse(value) : NaN;
    }

    function buildModel(source = window, now = Date.now()) {
        const daily = source.PORTFOLIO_DAILY_CHANGE_PCT;
        if (!source._gaugeDataReady || !valid(daily)) throw new Error('Daily return is unavailable. Wait for prices to load.');
        const quoteTime = timestamp(source.PORTFOLIO_UPDATED_AT);
        if (!Number.isFinite(quoteTime)) throw new Error('Quote time is unavailable. Refresh prices before sharing.');
        const timeZone = 'Europe/Warsaw';
        const date = value => new Intl.DateTimeFormat('en-CA', {timeZone, year: 'numeric', month: '2-digit', day: '2-digit'}).format(value);
        const name = String(source.BENCHMARK_NAME || source.BENCHMARK_ID || 'Benchmark');
        const model = {
            daily, nominal: valid(source.PORTFOLIO_DAILY_CHANGE_PLN) ? source.PORTFOLIO_DAILY_CHANGE_PLN : null,
            quoteTime, timeZone, date: date(quoteTime), latestSession: date(quoteTime) !== date(now),
            benchmarkName: name, chart: null, chartMessage: 'Intraday comparison unavailable.',
            comment: typeof source.ROAST_DATA?.message === 'string' ? source.ROAST_DATA.message : '',
        };
        try {
            const comparison = source.IntradayComparison.synthesize({
                holdings: source.PORTFOLIO_DATA, benchmark: source.BENCHMARK_DATA,
                benchmarkId: source.BENCHMARK_ID, mode: 'session', now,
            });
            const points = comparison.points.map(point => ({
                timestamp: point.timestamp,
                portfolioPct: valid(point.portfolioPct) ? point.portfolioPct : null,
                benchmarkPct: valid(point.benchmarkPct) ? point.benchmarkPct : null,
            }));
            const common = points.filter(point => valid(point.portfolioPct) && valid(point.benchmarkPct));
            if (comparison.sessionDate === model.date && common.length >= 2) {
                model.chart = {
                    points, start: comparison.start, end: comparison.end,
                    timeZone: comparison.timeZone, quoteDelay: comparison.quoteDelay,
                    benchmarkCurrency: comparison.benchmarkCurrency,
                    last: {...common[common.length - 1]}, warnings: [...comparison.warnings],
                };
            } else if (comparison.sessionDate !== model.date) {
                model.chartMessage = 'Intraday chart belongs to a different session.';
            } else {
                model.chartMessage = 'Not enough common minute bars yet.';
            }
        } catch (_) {
            model.chartMessage = 'Intraday comparison unavailable.';
        }
        return model;
    }

    function drawPoster(canvas, model, {story = false, showNominal = true} = {}) {
        canvas.width = 1080;
        canvas.height = story ? 1920 : 1350;
        const context = canvas.getContext('2d');
        const colors = palette;
        const offset = story ? 90 : 0;
        const time = (value, zone = model.timeZone) => new Intl.DateTimeFormat('en-GB', {
            timeZone: zone, hour: '2-digit', minute: '2-digit', timeZoneName: 'short', hourCycle: 'h23',
        }).format(value);
        const text = (value, x, y, size, color = colors.white, weight = 500) => {
            context.font = `${weight} ${size}px "Helvetica Neue", sans-serif`;
            context.fillStyle = color;
            context.fillText(value, x, y);
        };
        const fit = (value, x, y, maxWidth, size, color, weight = 500) => {
            while (size > 14) {
                context.font = `${weight} ${size}px "Helvetica Neue", sans-serif`;
                if (context.measureText(value).width <= maxWidth) break;
                size -= 1;
            }
            context.font = `${weight} ${size}px "Helvetica Neue", sans-serif`;
            context.fillStyle = color;
            context.fillText(value, x, y, maxWidth);
        };
        context.fillStyle = colors.ink;
        context.fillRect(0, 0, canvas.width, canvas.height);
        const headerHeight = 540 + offset;
        context.fillStyle = model.daily < 0 ? colors.coral : model.daily > 0 ? colors.mint : '#cec4f5';
        context.fillRect(0, 0, canvas.width, headerHeight);
        const glow = context.createRadialGradient(180, 180, 30, 180, 180, 750);
        glow.addColorStop(0, 'rgba(255,255,255,.35)');
        glow.addColorStop(1, 'rgba(255,255,255,0)');
        context.fillStyle = glow;
        context.fillRect(0, 0, canvas.width, headerHeight);
        context.save();
        context.beginPath(); context.rect(0, 0, canvas.width, headerHeight); context.clip();
        context.strokeStyle = '#192824'; context.lineWidth = 2;
        const curves = [
            [[-100, 720], [250, 340], [680, 820], [1200, 400]],
            [[-100, 580], [300, 220], [640, 680], [1200, 260]],
            [[-100, 440], [350, 100], [600, 540], [1200, 130]],
            [[-100, 300], [400, 20], [560, 400], [1200, 20]],
        ];
        curves.forEach((points, index) => {
            context.globalAlpha = .04 + index * .01;
            context.beginPath(); context.moveTo(...points[0]);
            context.bezierCurveTo(...points[1], ...points[2], ...points[3]); context.stroke();
        });
        context.globalAlpha = .08;
        for (let x = 24; x < canvas.width; x += 36) {
            for (let y = 24; y < headerHeight; y += 36) {
                context.beginPath(); context.arc(x, y, 1, 0, Math.PI * 2); context.stroke();
            }
        }
        context.restore();
        text('roastfolio.', 72, 100 + offset, 40, colors.headline, 750);
        context.textAlign = 'right';
        text(new Intl.DateTimeFormat('en-GB', {timeZone: model.timeZone, day: '2-digit', month: 'short', year: 'numeric'}).format(model.quoteTime).toUpperCase(), 1008, 96 + offset, 24, colors.headline);
        context.textAlign = 'left';
        text(model.latestSession ? 'MY LATEST SESSION RETURN' : 'MY RETURN TODAY', 72, 197 + offset, 25, colors.headline, 650);
        fit(`${signed(model.daily)}%`, 64, 385 + offset, 950, 184, colors.headline, 750);
        if (showNominal && model.nominal !== null) {
            const nominal = new Intl.NumberFormat('en-GB', {minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero'}).format(model.nominal);
            fit(`${nominal} PLN`, 76, 459 + offset, 930, 51, colors.headline);
        } else text(model.nominal === null && showNominal ? 'PLN AMOUNT UNAVAILABLE' : 'PLN AMOUNT PRIVATE', 76, 454 + offset, 22, colors.headline);
        fit(`Since previous close / Quotes ${time(model.quoteTime)}`, 76, 508 + offset, 930, 22, colors.headline);
        const top = 618 + offset;
        const bottom = story ? 1150 : 886;
        fit(`PORTFOLIO vs ${model.benchmarkName}`, 76, top - 48, 930, 24, colors.white, 650);
        if (model.chart) {
            const chart = model.chart;
            const points = chart.points;
            let extent = .25;
            for (const point of points) {
                for (const key of ['portfolioPct', 'benchmarkPct']) if (valid(point[key])) extent = Math.max(extent, Math.abs(point[key]));
            }
            extent *= 1.3;
            const first = points[0].timestamp;
            const last = points[points.length - 1].timestamp;
            const project = (value, stamp) => ({x: 76 + (stamp - first) / Math.max(1, last - first) * 820, y: (top + bottom) / 2 - value / extent * (bottom - top) / 2});
            for (const tick of [-extent, 0, extent]) {
                const position = project(tick, first).y;
                context.beginPath(); context.moveTo(76, position); context.lineTo(896, position);
                context.strokeStyle = tick === 0 ? colors.muted : colors.grid;
                context.lineWidth = 1; context.setLineDash(tick === 0 ? [5, 9] : []); context.stroke(); context.setLineDash([]);
                fit(`${signed(tick)}%`, 918, position + 7, 100, 19, colors.muted);
            }
            for (const [key, color] of [['benchmarkPct', colors.amber], ['portfolioPct', colors.white]]) {
                context.beginPath();
                let connected = false;
                for (const point of points) {
                    if (!valid(point[key])) { connected = false; continue; }
                    const position = project(point[key], point.timestamp);
                    if (connected) context.lineTo(position.x, position.y);
                    else context.moveTo(position.x, position.y);
                    connected = true;
                }
                context.strokeStyle = color; context.lineWidth = 6; context.lineJoin = 'round'; context.stroke();
            }
            text(time(first, chart.timeZone), 76, bottom + 34, 20, colors.muted);
            context.textAlign = 'right'; text(time(last, chart.timeZone), 896, bottom + 34, 20, colors.muted); context.textAlign = 'left';
            fit(`You ${signed(chart.last.portfolioPct)}%`, 76, bottom + 89, 370, 29, colors.white, 650);
            fit(`${model.benchmarkName} ${signed(chart.last.benchmarkPct)}%`, 470, bottom + 89, 535, 29, colors.amber, 650);
            fit(`${signed(chart.last.portfolioPct - chart.last.benchmarkPct)} pp at ${time(chart.last.timestamp, chart.timeZone)}`, 76, bottom + 137, 930, 27, colors.muted);
            fit(`Minute bars / ${Math.round(chart.quoteDelay / 60000)} min delay / Constant FX / ${chart.benchmarkCurrency}`, 76, bottom + 176, 930, 21, colors.muted);
        } else fit(model.chartMessage, 76, top + 100, 930, 34, colors.muted);
        const commentY = story ? 1490 : 1155;
        let line = '';
        let lineNumber = 0;
        context.font = '600 43px "Helvetica Neue", sans-serif';
        const words = model.comment.split(/\s+/).filter(Boolean);
        const lines = [];
        for (const word of words) {
            if (context.measureText(line ? `${line} ${word}` : word).width > 900 && line) { lines.push(line); line = word; }
            else line = line ? `${line} ${word}` : word;
        }
        if (line) lines.push(line);
        for (const value of lines.slice(0, 2)) {
            let displayed = value;
            if (lineNumber === 1 && lines.length > 2) displayed += '...';
            fit(displayed, 76, commentY + lineNumber++ * 55, 900, 43, colors.white, 600);
        }
        text('Since previous close / Returns are not a forecast', 76, canvas.height - 65, 20, colors.muted);
        context.textAlign = 'right'; text('roastfolio', 1008, canvas.height - 65, 22, colors.mint, 650); context.textAlign = 'left';
        canvas.setAttribute('aria-label', `Return ${signed(model.daily)} percent. ${showNominal && model.nominal !== null ? `${model.nominal} PLN.` : 'PLN amount not shown.'} ${model.chart ? `Intraday comparison with ${model.benchmarkName}, delayed minute bars and constant FX.` : model.chartMessage}`);
    }

    function open() {
        if (activeDialog) { activeDialog.focus(); return; }
        const opener = document.activeElement;
        const dialog = document.createElement('dialog');
        dialog.className = 'daily-share-dialog';
        dialog.setAttribute('aria-labelledby', 'daily-share-title');
        dialog.innerHTML = `<header><h2 id="daily-share-title">Share your day.</h2><button type="button" data-close aria-label="Close share preview" title="Close">&times;</button></header>
            <div class="daily-share-layout"><div class="daily-share-preview"><canvas width="1080" height="1350" role="img" aria-label="Daily return poster"></canvas></div>
            <div class="daily-share-options"><fieldset><legend>Format</legend><label><input type="radio" name="daily-share-format" value="post" checked><span>Post 4:5</span></label><label><input type="radio" name="daily-share-format" value="story"><span>Story 9:16</span></label></fieldset>
            <label class="daily-share-privacy"><input type="checkbox" data-amount checked>Show PLN amount</label>
            <button type="button" data-share disabled>Share image</button><button type="button" data-download disabled>Download PNG</button>
            <p role="status" aria-live="polite">Preparing image...</p></div></div>`;
        document.body.appendChild(dialog);
        activeDialog = dialog;
        const canvas = dialog.querySelector('canvas');
        const amount = dialog.querySelector('[data-amount]');
        const share = dialog.querySelector('[data-share]');
        const download = dialog.querySelector('[data-download]');
        const status = dialog.querySelector('[role=status]');
        let model;
        let file;
        let generation = 0;
        let sharing = false;
        try { model = buildModel(); } catch (error) {
            status.textContent = error.message;
            dialog.querySelector('.daily-share-preview').hidden = true;
            dialog.querySelectorAll('input').forEach(input => { input.disabled = true; });
        }
        function prepare() {
            const revision = ++generation;
            file = null; share.disabled = download.disabled = true;
            if (!model) return;
            status.textContent = 'Preparing image...';
            const story = dialog.querySelector('[name=daily-share-format]:checked').value === 'story';
            try {
                drawPoster(canvas, model, {story, showNominal: amount.checked});
                canvas.toBlob(blob => {
                    if (revision !== generation || !dialog.open) return;
                    if (!blob) { status.textContent = 'Image could not be prepared. Change format to retry.'; return; }
                    file = new File([blob], `roastfolio-${model.date}-${story ? 'story' : 'post'}.png`, {type: 'image/png'});
                    let native = false;
                    try { native = !!(navigator.share && navigator.canShare?.({files: [file]})); } catch (_) {}
                    share.hidden = !native; share.disabled = !native; download.disabled = false;
                    status.textContent = native ? 'Image ready.' : 'PNG ready. Attach it in WhatsApp or your social app.';
                }, 'image/png');
            } catch (_) { status.textContent = 'Image could not be prepared. Change format to retry.'; }
        }
        dialog.addEventListener('change', prepare);
        download.addEventListener('click', () => {
            if (!file || sharing) return;
            const url = URL.createObjectURL(file);
            const anchor = document.createElement('a'); anchor.href = url; anchor.download = file.name; anchor.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            status.textContent = 'PNG download requested.';
        });
        share.addEventListener('click', async () => {
            if (!file || sharing) return;
            sharing = true; share.disabled = download.disabled = true;
            dialog.querySelectorAll('input').forEach(input => { input.disabled = true; });
            try {
                await navigator.share({files: [file], title: `Roastfolio / ${model.date}`});
                if (dialog.open) status.textContent = 'Image handed to your sharing app.';
            } catch (error) {
                if (dialog.open) status.textContent = error.name === 'AbortError' ? 'Sharing cancelled. Your image is still ready.' : 'Sharing unavailable. Download the PNG instead.';
            } finally {
                sharing = false; share.disabled = download.disabled = false;
                dialog.querySelectorAll('input').forEach(input => { input.disabled = false; });
            }
        });
        dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
        dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
        dialog.addEventListener('close', () => {
            generation++; file = null; activeDialog = null; dialog.remove();
            if (opener?.isConnected) opener.focus();
        }, {once: true});
        dialog.showModal();
        prepare();
    }

    window.DailyReturnShare = Object.freeze({buildModel, drawPoster, open});
    document.addEventListener('click', event => {
        if (event.target.closest('[data-share-daily-return]')) open();
    });
}());