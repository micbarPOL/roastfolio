(function () {
    'use strict';

    const NEUTRAL = 0.05;
    const valid = value => typeof value === 'number' && Number.isFinite(value);
    const signed = value => `${value > 0 ? '+' : ''}${value.toFixed(2)}`;

    function classify(portfolio, benchmark) {
        if (!valid(portfolio) || !valid(benchmark)) return { mood: 'unavailable', effect: 'none' };
        const spread = Math.round((portfolio - benchmark) * 10000) / 10000;
        if (Math.abs(portfolio) <= NEUTRAL || Math.abs(benchmark) <= NEUTRAL) return { mood: 'neutral', effect: 'none' };
        if (portfolio > 0 && benchmark < 0) return { mood: 'exceptional', effect: 'fireworks' };
        if (portfolio < 0 && benchmark > 0) return { mood: 'against-market', effect: 'spotlight' };
        if (portfolio < 0) return spread > NEUTRAL
            ? { mood: 'losing-less', effect: 'umbrella' }
            : { mood: 'losing', effect: spread < -NEUTRAL ? 'rain' : 'none' };
        return { mood: spread > NEUTRAL ? 'winning' : 'profitable', effect: 'fireworks' };
    }

    let played = false;
    let observer;
    let timer;
    let narrativeSignature;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');

    function stopEffect() {
        const effect = document.querySelector('#daily-verdict .dv-effect');
        if (effect) effect.dataset.playing = 'false';
        clearTimeout(timer);
    }

    function play(root) {
        if (played || root.dataset.state !== 'ready') return;
        played = true;
        if (motion.matches || root.dataset.effect === 'none') return;
        const effect = root.querySelector('.dv-effect');
        effect.dataset.playing = 'true';
        timer = setTimeout(stopEffect, 1200);
    }

    motion.addEventListener('change', stopEffect);

    function renderNarrative(root, roast, available) {
        const tooltip = root.querySelector('#gauge-benchmark-tooltip');
        const message = available ? roast?.message || 'No fresh commentary available at the moment.' : 'Commentary will return when fresh comparison data is available.';
        const signature = JSON.stringify([message, roast?.templateId, available]);
        if (signature === narrativeSignature) return;
        narrativeSignature = signature;
        tooltip.innerHTML = `<button type="button" class="roast-toggle" aria-expanded="false" aria-controls="roast-reactions"><span class="roast-msg"></span><span class="hero-tap">Tap to react</span></button>
            <div class="roast-reactions" id="roast-reactions" hidden>
                <button type="button" class="chip-btn" onclick="window.submitRoastReaction('good', event)">Good</button>
                <button type="button" class="chip-btn" onclick="window.submitRoastReaction('repetitive', event)">Repetitive</button>
                <button type="button" class="chip-btn" onclick="window.submitRoastReaction('wrong', event)">Wrong</button>
                <button type="button" class="chip-btn" onclick="window.submitRoastReaction('boring', event)">Boring</button>
            </div>`;
        tooltip.querySelector('.roast-msg').textContent = message;
        tooltip.querySelector('.roast-toggle').disabled = !available || !roast?.message;
        tooltip.querySelector('.hero-tap').hidden = !available || !roast?.message;
        tooltip.className = 'bm-modern-roast';
        tooltip.style.display = 'block';
        if (available && roast?.message) window.RoastTracker?.recordEvent({
            eventType: 'roast_displayed', templateId: roast.templateId, scenarioKey: roast.scenarioKey,
            portfolioChange: roast.portfolioChange, benchmarkChange: roast.benchmarkChange,
            bestAsset: roast.bestAsset, worstAsset: roast.worstAsset,
        });
    }

    function render({ portfolio, benchmark, cash, name, ready, roast }) {
        const root = document.getElementById('daily-verdict');
        if (!root) return;
        const available = !!ready && valid(portfolio) && valid(benchmark);
        const state = classify(ready ? portfolio : null, ready ? benchmark : null);
        if (root.dataset.mood !== state.mood || !available) stopEffect();
        root.dataset.state = available ? 'ready' : ready ? 'unavailable' : 'loading';
        root.dataset.mood = state.mood;
        root.dataset.effect = state.effect;
        root.dataset.return = portfolio > 0 ? 'positive' : portfolio < 0 ? 'negative' : 'neutral';
        root.querySelector('#dash-daily-return').textContent = ready && valid(portfolio) ? `${signed(portfolio)}%` : '\u2014';
        root.querySelector('#dash-daily-pln').textContent = ready && valid(cash)
            ? `${new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero' }).format(cash)} PLN today` : '\u2014';
        root.querySelector('.dv-benchmark-name').textContent = name;
        root.querySelector('.dv-unavailable').textContent = ready ? 'Comparison unavailable. Waiting for fresh portfolio and benchmark returns.' : 'Loading today\u2019s returns\u2026';
        root.querySelector('.dv-plot').hidden = !available;
        root.querySelector('#gauge-lead').hidden = !available;
        root.querySelector('.dv-unavailable').hidden = available;
        if (available) {
            const spread = Math.round((portfolio - benchmark) * 10000) / 10000;
            const extent = Math.max(1, Math.ceil(Math.max(Math.abs(portfolio), Math.abs(benchmark))));
            const portfolioPosition = 50 + portfolio / extent * 50;
            const benchmarkPosition = 50 + benchmark / extent * 50;
            root.style.setProperty('--dv-portfolio', `${portfolioPosition}%`);
            root.style.setProperty('--dv-benchmark', `${benchmarkPosition}%`);
            root.style.setProperty('--dv-start', `${Math.min(portfolioPosition, benchmarkPosition)}%`);
            root.style.setProperty('--dv-width', `${Math.abs(portfolioPosition - benchmarkPosition)}%`);
            root.querySelector('.dv-portfolio-value').textContent = `${signed(portfolio)}%`;
            root.querySelector('.dv-benchmark-value').textContent = `${signed(benchmark)}%`;
            root.querySelector('.dv-low').textContent = `-${extent}%`;
            root.querySelector('.dv-high').textContent = `+${extent}%`;
            root.querySelector('.dv-spread').textContent = `${signed(Math.abs(spread) < .005 ? 0 : spread)} pp`;
            root.querySelector('.dv-relation').textContent = Math.abs(spread) < .005 ? `In line with ${name}` : `${spread > 0 ? 'Ahead of' : 'Behind'} ${name}`;
            const say = document.getElementById('dash-player-say');
            if (say) say.textContent = root.querySelector('#gauge-lead').textContent;
            if (!observer && !played) {
                observer = new IntersectionObserver(entries => {
                    if (entries.some(entry => entry.isIntersecting)) play(root);
                });
                observer.observe(root);
            }
            const bounds = root.getBoundingClientRect();
            if (bounds.height && bounds.top < window.innerHeight && bounds.bottom > 0) play(root);
        }
        renderNarrative(root, roast, available);
    }

    window.DailyVerdict = { classify, render };
}());