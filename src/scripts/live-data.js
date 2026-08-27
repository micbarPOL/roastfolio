/**
 * live-data.js — fetches live portfolio prices from the Lambda API on page load.
 * The API URL comes from config.js (written by deploy.sh → uploaded to S3).
 * Locally, config.js is absent so the WIG chart renders from data-wig.js only.
 */

function _benchmarkDailyPctCacheKey(benchmarkId) {
    const normalized = String(benchmarkId || 'WIG').trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    return `benchmark_daily_pct_${normalized}`;
}

function _cacheBenchmarkDailyPct(benchmarkId, pct) {
    try {
        localStorage.setItem(_benchmarkDailyPctCacheKey(benchmarkId), pct);
        if (String(benchmarkId || '').trim().toUpperCase() === 'WIG') {
            localStorage.setItem('wig_daily_pct', pct);
        }
    } catch(_) {}
}

function _readCachedBenchmarkDailyPct(benchmarkId) {
    try {
        const keyed = parseFloat(localStorage.getItem(_benchmarkDailyPctCacheKey(benchmarkId)));
        if (!isNaN(keyed)) return keyed;
        if (String(benchmarkId || '').trim().toUpperCase() === 'WIG') {
            const legacy = parseFloat(localStorage.getItem('wig_daily_pct'));
            if (!isNaN(legacy)) return legacy;
        }
    } catch(_) {}
    return null;
}

/** Compute benchmark daily % change — always returns a number, never null.
 *  Priority: last two daily candles (prev-close → current) → intraday fallback → localStorage → 0
 *  Note: server-provided benchmarkDailyPct always takes precedence; this is only a local fallback.
 */
function computeBenchmarkDailyPct(benchmarkData, benchmarkId) {
    // Primary: yesterday close → latest daily bar close (market-standard daily change)
    const daily = benchmarkData.daily || [];
    if (daily.length >= 2) {
        const prev = daily[daily.length - 2].c;
        const last = daily[daily.length - 1].c;
        if (prev) {
            const pct = Math.round((last - prev) / prev * 10000) / 100;
            _cacheBenchmarkDailyPct(benchmarkId, pct);
            return pct;
        }
    }
    // Fallback: intraday open → latest close (when only intraday bars are present)
    const intra = benchmarkData.intraday || [];
    if (intra.length >= 2) {
        const open  = intra[0].o;
        const close = intra[intra.length - 1].c;
        if (open) {
            const pct = Math.round((close - open) / open * 10000) / 100;
            _cacheBenchmarkDailyPct(benchmarkId, pct);
            return pct;
        }
    }
    // Last resort: cached value from previous session
    const cached = _readCachedBenchmarkDailyPct(benchmarkId);
    if (cached != null) return cached;
    return 0;
}
window.computeBenchmarkDailyPct = computeBenchmarkDailyPct;
window.computeWigDailyPct = computeBenchmarkDailyPct;

function _parseAsUtcDate(value) {
    if (value == null || value === '') return null;
    if (value instanceof Date) return value;
    if (typeof value === 'number') {
        return new Date(value < 1e12 ? value * 1000 : value);
    }
    if (typeof value === 'string') {
        if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value)) {
            return new Date(value.replace(' ', 'T') + 'Z');
        }
        return new Date(value);
    }
    return new Date(value);
}

function formatWarsawTime(updatedAt) {
    const date = _parseAsUtcDate(updatedAt);
    if (!date || Number.isNaN(date.getTime())) {
        return String(updatedAt ?? '—');
    }
    return new Intl.DateTimeFormat('pl-PL', {
        timeZone: 'Europe/Warsaw',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hourCycle: 'h23',
    }).format(date);
}
window.formatWarsawTime = formatWarsawTime;

function formatPortfolioUpdatedAtCET(updatedAt) {
    if (updatedAt == null || updatedAt === '') return '—';

    if (typeof updatedAt === 'string') {
        if (updatedAt.endsWith(' Warsaw')) return updatedAt;
        if (updatedAt.endsWith(' CET') || updatedAt.endsWith(' CEST') || updatedAt.endsWith(' ECT')) {
            updatedAt = updatedAt.replace(/\s+(CET|CEST|ECT)$/, '');
        }
    }

    const date = _parseAsUtcDate(updatedAt);

    if (Number.isNaN(date.getTime())) {
        return String(updatedAt);
    }

    const parts = new Intl.DateTimeFormat('sv-SE', {
        timeZone: 'Europe/Warsaw',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hourCycle: 'h23',
    }).formatToParts(date).reduce((acc, part) => {
        if (part.type !== 'literal') acc[part.type] = part.value;
        return acc;
    }, {});

    return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} Warsaw`;
}
window.formatPortfolioUpdatedAtCET = formatPortfolioUpdatedAtCET;

/** Render a sarcastic Sheldon-style market commentary in the header. */
function renderMarketCommentary(pct, benchmarkName) {
    const targets = Array.from(document.querySelectorAll('[data-market-commentary]'));
    if (!targets.length || pct == null) return;

    const bm  = benchmarkName || window.BENCHMARK_NAME || 'WIG';
    const abs  = Math.abs(pct);
    const sign = pct >= 0 ? '+' : '';

    let pool;

    if (abs <= 0.2) {
        pool = [
            `${bm} ${sign}${pct}%. You'd genuinely get more volatility from watching paint dry. At least paint has a direction.`,
            `${bm} ${sign}${pct}%. I ran a simulation. The most exciting thing that happened today was the lunch break.`,
            `${bm} ${sign}${pct}%. This market action has the emotional depth of plain oatmeal.`,
            `${bm} ${sign}${pct}%. The index has committed itself to the rigorous scientific study of doing absolutely nothing.`,
            `${bm} ${sign}${pct}%. Congratulations. You are witnessing the financial equivalent of waiting for a microwave.`,
            `${bm} ${sign}${pct}%. The market appears to be buffering. I assume even capitalism needs a moment.`,
            `${bm} ${sign}${pct}%. If this session were any flatter, it would qualify as a calibration tool.`,
            `${bm} ${sign}${pct}%. Traders have collectively produced a masterpiece of statistical irrelevance.`,
            `${bm} ${sign}${pct}%. I could explain today's move, but then I'd need to explain why nothing deserves explanation.`,
            `${bm} ${sign}${pct}%. The chart has all the dramatic tension of a tax seminar with bad coffee.`,
            `${bm} ${sign}${pct}%. The market is technically conscious, which is more than I can say for the decision-making behind some portfolios.`,
            `${bm} ${sign}${pct}%. Everyone showed up to exchange capital for the privilege of remaining exactly where they started. Efficient.`,
            `${bm} ${sign}${pct}%. Today's volatility is so small it should be measured with lab equipment and lowered expectations.`,
            `${bm} ${sign}${pct}%. Somewhere, an analyst is writing a three-page note about why absolutely nothing happened.`,
            `${bm} ${sign}${pct}%. This is less a trading session and more a prolonged shrug in graph form.`,
        ];
    } else if (pct > 0.2 && pct <= 1.0) {
        pool = [
            `${bm} ${sign}${pct}%. The economy is technically growing. At the pace of a very motivated snail.`,
            `${bm} ${sign}${pct}%. A modest rise. Please enjoy it quietly before someone on LinkedIn calls it a paradigm shift.`,
            `${bm} ${sign}${pct}%. The market is green enough for optimism and not nearly green enough for your confidence.`,
            `${bm} ${sign}${pct}%. Investors saw a little upside and immediately resumed confusing luck with expertise.`,
            `${bm} ${sign}${pct}%. This is what cautious optimism looks like after being filtered through spreadsheets and denial.`,
            `${bm} ${sign}${pct}%. The bulls have entered the room, though clearly not with a sense of urgency.`,
            `${bm} ${sign}${pct}%. It's a decent day, which means somewhere an average investor is becoming intolerable.`,
            `${bm} ${sign}${pct}%. The market rose just enough for everyone to rediscover their 'long-term thesis.' Convenient.`,
            `${bm} ${sign}${pct}%. Mild green. The sort of gain that inspires confidence far beyond its credentials.`,
            `${bm} ${sign}${pct}%. Traders are acting like macroeconomics makes sense again. Adorable.`,
            `${bm} ${sign}${pct}%. The index is positive. Not brilliant, not historic, just sufficiently competent. Unlike some holdings.`,
            `${bm} ${sign}${pct}%. Today's rally is powered by caffeine, selective memory, and a touching disregard for risk.`,
            `${bm} ${sign}${pct}%. A small gain. Financially useful, intellectually overcelebrated.`,
            `${bm} ${sign}${pct}%. This is the kind of session where people make money and immediately mistake it for wisdom.`,
            `${bm} ${sign}${pct}%. The market advanced politely. Please do not interpret that as permission to be smug.`,
        ];
    } else if (pct > 1.0 && pct <= 2.0) {
        pool = [
            `${bm} ${sign}${pct}%. The market is rallying like someone leaked cheat codes for capitalism.`,
            `${bm} ${sign}${pct}%. A move this strong causes ordinary investors to become philosophers of momentum.`,
            `${bm} ${sign}${pct}%. The bulls are feeling invincible, which in finance is usually the beginning of a lesson.`,
            `${bm} ${sign}${pct}%. This is what euphoria looks like when it has a Bloomberg terminal and no adult supervision.`,
            `${bm} ${sign}${pct}%. Everyone is suddenly a genius again. Statistically, most of them are still not.`,
            `${bm} ${sign}${pct}%. A rally of this size turns cautious people into motivational speakers.`,
            `${bm} ${sign}${pct}%. The chart is very green. I remain very suspicious. Both positions are correct.`,
            `${bm} ${sign}${pct}%. Investors are celebrating as if recessions were canceled by committee.`,
            `${bm} ${sign}${pct}%. Strong up day. Somewhere, a cousin who bought one stock is now giving strategic advice.`,
            `${bm} ${sign}${pct}%. This much optimism usually ends with either a correction or an embarrassing podcast clip.`,
            `${bm} ${sign}${pct}%. The index is sprinting and valuations are pretending not to notice.`,
            `${bm} ${sign}${pct}%. A proper rally. Please keep your seatbelt fastened and your ego in a locked compartment.`,
            `${bm} ${sign}${pct}%. Markets surged and confidence has exceeded medically recommended levels.`,
            `${bm} ${sign}${pct}%. The bulls are now speaking in rocket emojis and deeply flawed probability assumptions.`,
            `${bm} ${sign}${pct}%. Impressive session. I hate how much humans learn the wrong lesson from these.`,
        ];
    } else if (pct > 2.0) {
        pool = [
            `${bm} ${sign}${pct}%. The market is up over 2%, meaning logic has officially left the building.`,
            `${bm} ${sign}${pct}%. Full market mania. The adults are gone and momentum is driving the bus.`,
            `${bm} ${sign}${pct}%. Investors are buying with the strategic discipline of toddlers in a candy store.`,
            `${bm} ${sign}${pct}%. This rally is so aggressive it should come with protective eyewear and a waiver.`,
            `${bm} ${sign}${pct}%. Today's gains are powered almost entirely by dopamine and the refusal to remember history.`,
            `${bm} ${sign}${pct}%. The chart looks less like finance and more like an engineering test gone wrong.`,
            `${bm} ${sign}${pct}%. Bulls are now operating at confidence levels previously reserved for science fiction villains.`,
            `${bm} ${sign}${pct}%. A move like this causes people to say 'obviously' about things they did not obviously predict.`,
            `${bm} ${sign}${pct}%. The market is vertically enthusiastic. I find that medically concerning.`,
            `${bm} ${sign}${pct}%. Even pessimists are accidentally making money. It must be exhausting for them.`,
            `${bm} ${sign}${pct}%. This is the sort of day that convinces average traders they should quit their jobs and start a newsletter.`,
            `${bm} ${sign}${pct}%. Capitalism is currently speedrunning overconfidence.`,
            `${bm} ${sign}${pct}%. The exchange appears to be having a sugar rush and absolutely no one is asking sensible questions.`,
            `${bm} ${sign}${pct}%. If exuberance were taxable, the budget would be balanced by lunch.`,
            `${bm} ${sign}${pct}%. Bears are reviewing career alternatives. The bulls, naturally, are being unbearable.`,
        ];
    } else if (pct < -0.2 && pct >= -1.0) {
        pool = [
            `${bm} ${sign}${pct}%. This decline is financially minor but emotionally theatrical.`,
            `${bm} ${sign}${pct}%. A small dip. Or as retail investors call it: 'the end.'`,
            `${bm} ${sign}${pct}%. The market slipped and financial media is already warming up the apocalypse graphics.`,
            `${bm} ${sign}${pct}%. Mild red day. Enough to hurt feelings, not enough to justify your dramatic internal monologue.`,
            `${bm} ${sign}${pct}%. Investors reacted to uncertainty the way toddlers react to vegetables.`,
            `${bm} ${sign}${pct}%. This is the sort of pullback that makes people rediscover gold and misuse Warren Buffett quotes.`,
            `${bm} ${sign}${pct}%. Wall Street saw one red candle and immediately lost emotional stability.`,
            `${bm} ${sign}${pct}%. The market is down, which means finance influencers are now achieving spiritual enlightenment on schedule.`,
            `${bm} ${sign}${pct}%. A polite decline. The index is underperforming, but at least it's being civil about it.`,
            `${bm} ${sign}${pct}%. Small losses. Just enough for people to check their apps with unnecessary intensity.`,
            `${bm} ${sign}${pct}%. The market fell modestly and suddenly everyone has a macro thesis. None of them improved the chart.`,
            `${bm} ${sign}${pct}%. Bears are celebrating like they survived an era, when in fact they survived a Tuesday.`,
            `${bm} ${sign}${pct}%. It's red, but not catastrophe-red. More like 'annoying email' red.`,
            `${bm} ${sign}${pct}%. Your correct emotional response here is mild annoyance, not a documentary voice-over.`,
            `${bm} ${sign}${pct}%. The index declined just enough to remind you markets contain risk and people contain melodrama.`,
        ];
    } else if (pct < -1.0 && pct >= -2.0) {
        pool = [
            `${bm} ${sign}${pct}%. Blood in the streets. Metaphorically. Financially, extremely literally.`,
            `${bm} ${sign}${pct}%. The market saw uncertainty and immediately chose violence.`,
            `${bm} ${sign}${pct}%. Down over 1%. Humanity has entered its annual ritual of loud, spreadsheet-based panic.`,
            `${bm} ${sign}${pct}%. This is what panic looks like after being professionally formatted.`,
            `${bm} ${sign}${pct}%. Investors are fleeing risk as though the word 'recession' just coughed in the room.`,
            `${bm} ${sign}${pct}%. The chart resembles a ski slope designed by pessimists and approved by lawyers.`,
            `${bm} ${sign}${pct}%. A drop of this size produces three things: fear, podcasts, and terrible hot takes.`,
            `${bm} ${sign}${pct}%. The algorithm says 'sell.' For once, the algorithm sounds less emotional than the humans.`,
            `${bm} ${sign}${pct}%. Financial Twitter has entered the bargaining stage of grief.`,
            `${bm} ${sign}${pct}%. This decline is no longer cute. It has become organized.`,
            `${bm} ${sign}${pct}%. Somewhere, a hedge fund manager just aged enough to need a new skincare routine.`,
            `${bm} ${sign}${pct}%. The efficient market is efficiently distributing discomfort to everyone at once.`,
            `${bm} ${sign}${pct}%. A proper down day. The kind that turns 'buy the dip' into a sentence people whisper.`,
            `${bm} ${sign}${pct}%. Analysts are now using words like 'headwinds' because 'we don't know' sounds unprofessional.`,
            `${bm} ${sign}${pct}%. Capitalism appears to be experiencing temporary dizziness and permanent overreaction.`,
        ];
    } else {
        pool = [
            `${bm} ${sign}${pct}%. This is no longer a dip. This is an organized evacuation.`,
            `${bm} ${sign}${pct}%. The market is down so much even economists have temporarily stopped pretending.`,
            `${bm} ${sign}${pct}%. Absolute chaos. The professional term is 'heightened volatility.' The useful term is 'oh no.'`,
            `${bm} ${sign}${pct}%. Today's chart resembles a piano falling off a building, which at least has narrative clarity.`,
            `${bm} ${sign}${pct}%. Investors are refreshing portfolios with the emotional stability of raccoons in a thunderstorm.`,
            `${bm} ${sign}${pct}%. The market just performed a live demonstration of gravity for anyone who still had questions.`,
            `${bm} ${sign}${pct}%. A crash of this size turns diversification from a concept into a prayer.`,
            `${bm} ${sign}${pct}%. Bears are insufferable right now, which is irritating because they are also, regrettably, correct.`,
            `${bm} ${sign}${pct}%. This will absolutely appear on a future chart with a neat label. Today, unfortunately, you are inside the label.`,
            `${bm} ${sign}${pct}%. The phrase 'long-term investing' is being repeated defensively by people who sound unconvinced even to themselves.`,
            `${bm} ${sign}${pct}%. Circuit breakers are warming up like Olympic athletes. That's not a sentence you want in a calm market.`,
            `${bm} ${sign}${pct}%. Somewhere, an intern opened the red chart template and did not need to change a single thing.`,
            `${bm} ${sign}${pct}%. If panic had an annual report, today would be the cover image.`,
            `${bm} ${sign}${pct}%. The exchange appears to be reenacting a disaster film with fewer heroes and more spreadsheets.`,
            `${bm} ${sign}${pct}%. On the bright side, this is an excellent day to discover who was lying about their risk tolerance.`,
        ];
    }

    const msg = pool[Math.floor(Math.random() * pool.length)];

    // Skip animation if user prefers reduced motion
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        targets.forEach(el => { el.textContent = msg; });
        return;
    }

    // Typewriter effect — comedian's pace: listen → reflect → deliver
    targets.forEach(el => {
        el.textContent = '';
        el.classList.add('commentary-typing');
    });
    window._commentaryGen = (window._commentaryGen || 0) + 1;
    const _myGen = window._commentaryGen;
    let _i = 0;
    function _type() {
        if (window._commentaryGen !== _myGen) return; // cancelled by restore/reset
        if (_i >= msg.length) {
            targets.forEach(el => el.classList.remove('commentary-typing'));
            return;
        }
        const ch = msg[_i++];
        targets.forEach(el => { el.textContent += ch; });
        // Dramatic pacing: punctuation = beat after punchline, spaces = quick between words
        const delay = (ch === '.' || ch === '!' || ch === '?') ? 160
                    : ch === ','                                ? 75
                    : ch === ' '                               ? 20
                    : 9 + Math.random() * 7;
        setTimeout(_type, delay);
    }
    _type();
}
window.renderMarketCommentary = renderMarketCommentary;
window._marketCommentaryRendered = false;  // Flag to render commentary only once on initial load

(function () {
    const API_URL = window.__CONFIG__ && window.__CONFIG__.apiUrl;

    window.__walletBootstrapState = 'checking';

    async function checkWalletBootstrapState() {
        if (!window.PortfolioClient || typeof PortfolioClient.listPortfolios !== 'function') {
            window.__walletBootstrapState = 'unknown';
            document.dispatchEvent(new CustomEvent('walletBootstrapReady', { detail: { state: 'unknown' } }));
            return false;
        }

        try {
            const data = await PortfolioClient.listPortfolios();
            const hasWallets = Array.isArray(data && data.portfolios) && data.portfolios.length > 0;
            window.__walletBootstrapState = hasWallets ? 'ready' : 'empty';
            document.dispatchEvent(new CustomEvent('walletBootstrapReady', {
                detail: { state: window.__walletBootstrapState, portfolios: data.portfolios || [] },
            }));
            if (!hasWallets && typeof renderDashboard === 'function') renderDashboard();
            return hasWallets;
        } catch (e) {
            console.warn('[live-data] Wallet bootstrap check failed:', e);
            window.__walletBootstrapState = 'unknown';
            document.dispatchEvent(new CustomEvent('walletBootstrapReady', { detail: { state: 'unknown', error: e } }));
            return false;
        }
    }

    // On DOMContentLoaded: seed WIG + portfolio values, then render dashboard
    document.addEventListener('DOMContentLoaded', () => {
        // WIG chart from static file
        if (typeof BENCHMARK_DATA !== 'undefined' && typeof renderBenchmarkChart === 'function') {
            renderBenchmarkChart(BENCHMARK_DATA, null, null);
        }
        // Seed WIG_DAILY_PCT — prefer the pre-computed static value written by update-wig.py,
        // then fall back to computing from intraday bars, then localStorage cache.
        if (typeof WIG_DAILY_PCT_STATIC !== 'undefined' && WIG_DAILY_PCT_STATIC !== 0) {
            window.WIG_DAILY_PCT = WIG_DAILY_PCT_STATIC;
            _cacheBenchmarkDailyPct(window.BENCHMARK_ID || 'WIG', WIG_DAILY_PCT_STATIC);
        } else if (typeof BENCHMARK_DATA !== 'undefined') {
            window.WIG_DAILY_PCT = computeBenchmarkDailyPct(BENCHMARK_DATA, window.BENCHMARK_ID || 'WIG');
        } else {
            const cached = _readCachedBenchmarkDailyPct(window.BENCHMARK_ID || 'WIG');
            if (cached != null) window.WIG_DAILY_PCT = cached;
        }
        // Seed PORTFOLIO_DAILY_CHANGE_PCT from localStorage if static value is absent/zero
        try {
            const cachedEmt = parseFloat(localStorage.getItem('emerytura_daily_pct'));
            if (!isNaN(cachedEmt) && (typeof PORTFOLIO_DAILY_CHANGE_PCT === 'undefined' || PORTFOLIO_DAILY_CHANGE_PCT === 0)) {
                window.PORTFOLIO_DAILY_CHANGE_PCT = cachedEmt;
            }
        } catch(_) {}

        // Re-render dashboard now that WIG_DAILY_PCT is available (benchmark needle)
        if (typeof renderDashboard === 'function') renderDashboard();
        // Market commentary is rendered after the first live Lambda fetch, not here
    });

    // Show a subtle loading indicator in the header
    function _shortStatus(msg) {
        if (!msg) return msg;
        if (/^\u2713 Live prices/.test(msg)) return '\u2713 Live prices';
        if (/^\u2713 Live \u2014/.test(msg)) return msg.replace(' Warsaw', '').replace(' \u2014 ', ' ');
        if (/^\u27f3 Fetching/.test(msg))   return '\u27f3 Fetching\u2026';
        const cm = msg.match(/^\u27f3 Cached \((\d+m ago)\)/);
        if (cm) return `\u27f3 Cached ${cm[1]}`;
        if (/^\u27f3 Refreshing/.test(msg)) return '\u27f3 Refreshing\u2026';
        if (/^\u27f3 Lambda/.test(msg))     return '\u27f3 Retrying\u2026';
        if (/^\u26a0/.test(msg))            return '\u26a0 Cached';
        return msg;
    }

    function showStatus(msg, color) {
        let el = document.getElementById('live-data-status');
        if (!el) {
            el = document.createElement('div');
            el.id = 'live-data-status';
            el.className = 'live-data-status';
            const header = document.querySelector('.brand-copy') || document.querySelector('header');
            if (header) header.appendChild(el);
        }
        const textColor = color === 'loading' ? '#666' : color === 'ok' ? '#155724' : '#721c24';
        el.textContent = msg;
        el.dataset.short = _shortStatus(msg);
        el.style.setProperty('--live-status-color', textColor);
        el.style.background = color === 'loading' ? '#f0f0f0' : color === 'ok' ? '#d4edda' : '#f8d7da';
        el.style.color = textColor;
    }

    if (!API_URL) {
        // ── Local dev: poll server.py for a fresh update, then rerender from live globals ──────
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            document.addEventListener('DOMContentLoaded', () => {
                showStatus('⟳ Fetching live prices…', 'loading');
                const pageStartedAt = Date.now() / 1000;
                let startVersion = null;

                const applyLocalRefresh = async (updatedAt) => {
                    clearInterval(poll);
                    await reloadScript('scripts/data-wig.js');
                    window._gaugeDataReady = true;
                    if (typeof renderDashboard === 'function') renderDashboard();
                    if (typeof BENCHMARK_DATA !== 'undefined' && typeof renderBenchmarkChart === 'function') {
                        renderBenchmarkChart(BENCHMARK_DATA, null, null);
                    }
                    if (typeof WIG_DAILY_PCT_STATIC !== 'undefined') {
                        window.WIG_DAILY_PCT = WIG_DAILY_PCT_STATIC;
                    }
                    // Market commentary only on initial load, not on refreshes
                    if (typeof initPortfolioCharts === 'function') {
                        window._portfolioInitialized = false;
                        initPortfolioCharts();
                    }
                    const age = formatWarsawTime(updatedAt);
                    showStatus(`✓ Live — ${age} Warsaw`, 'ok');
                    // Signal splash screen to hide (same event the production path uses)
                    document.dispatchEvent(new CustomEvent('liveDataReady'));
                };

                const poll = setInterval(async () => {
                    try {
                        const res = await fetch('http://localhost:8080/status', { cache: 'no-cache' });
                        const { version, updatedAt } = await res.json();
                        if (startVersion === null) {
                            startVersion = version;
                            // If the update completed before our first successful poll, still apply it.
                            if (version > 0 && updatedAt && updatedAt >= pageStartedAt - 2) {
                                await applyLocalRefresh(updatedAt);
                            }
                        } else if (version > startVersion) {
                            await applyLocalRefresh(updatedAt);
                        }
                    } catch (_) { /* server not running */ }
                }, 2000);
                // Stop polling after 3 minutes regardless
                setTimeout(() => {
                    clearInterval(poll);
                    showStatus('', 'ok');
                }, 180000);
            });
        }
        return;
    }

    function reloadScript(src) {
        return new Promise(resolve => {
            const old = document.querySelector(`script[src="${src}"], script[src*="${src.split('/').pop()}"]`);
            const s = document.createElement('script');
            s.src = src + '?v=' + Date.now();
            s.onload = resolve;
            s.onerror = resolve;
            document.head.appendChild(s);
        });
    }

    const TIMEOUT_MS = 25000;
    const RETRY_TIMEOUT_MS = 45000;

    function _holdingKey(row) {
        return `${row && row.ticker ? row.ticker : ''}::${row && row.name ? row.name : ''}`;
    }

    function _mergeHoldingBars(nextRows, previousRows) {
        const prevMap = new Map((previousRows || []).map(row => [_holdingKey(row), row]));
        return (nextRows || []).map(row => {
            const prev = prevMap.get(_holdingKey(row));
            if (!prev) return row;
            const merged = { ...row };
            if ((!Array.isArray(merged.todayBars) || !merged.todayBars.length) && Array.isArray(prev.todayBars) && prev.todayBars.length) {
                merged.todayBars = prev.todayBars;
            }
            if ((!Array.isArray(merged.yearBars) || !merged.yearBars.length) && Array.isArray(prev.yearBars) && prev.yearBars.length) {
                merged.yearBars = prev.yearBars;
            }
            return merged;
        });
    }

    function _mergeWalletHoldings(nextHoldings, previousHoldings) {
        const merged = {};
        Object.keys(nextHoldings || {}).forEach(wallet => {
            merged[wallet] = _mergeHoldingBars(nextHoldings[wallet] || [], (previousHoldings || {})[wallet] || []);
        });
        return merged;
    }

    function _buildApiUrl(view) {
        const url = new URL(API_URL, window.location.origin);
        if (view && view !== 'full') url.searchParams.set('view', view);
        return url.toString();
    }

    function _captureGaugeTooltipState() {
        return ['gauge-benchmark-tooltip', 'gauge-benchmark-tooltip-mobile']
            .map(id => {
                const el = document.getElementById(id);
                if (!el || !el.innerHTML) return null;
                return {
                    id,
                    html: el.innerHTML,
                    className: el.className,
                    display: el.style.display,
                };
            })
            .filter(Boolean);
    }

    function _restoreGaugeTooltipState(snapshot) {
        (snapshot || []).forEach(item => {
            const el = document.getElementById(item.id);
            if (!el) return;
            el.innerHTML = item.html;
            el.className = item.className;
            el.style.display = item.display;
        });
    }

    function _captureMarketCommentaryState() {
        return Array.from(document.querySelectorAll('[data-market-commentary]'))
            .map((el, index) => {
                if (!el || !el.textContent) return null;
                return {
                    index,
                    text: el.textContent,
                };
            })
            .filter(Boolean);
    }

    function _restoreMarketCommentaryState(snapshot) {
        window._commentaryGen = (window._commentaryGen || 0) + 1; // cancel any typewriter in progress
        const targets = Array.from(document.querySelectorAll('[data-market-commentary]'));
        targets.forEach(el => el.classList.remove('commentary-typing'));
        (snapshot || []).forEach(item => {
            const el = targets[item.index];
            if (!el) return;
            el.textContent = item.text;
        });
    }

    function applyLiveData(data, options = {}) {
        const preserveDeferredData = !!options.preserveDeferredData;
        const persistCache = options.persistCache !== false;

        // ── History response: only merges benchmark data, no portfolio changes ─────
        if (data.responseMode === 'history') {
            if (data.benchmarkData) {
                // Preserve live intraday (from full response) — merge historical data alongside it
                const existing = window.BENCHMARK_DATA || {};
                window.BENCHMARK_DATA = {
                    ...existing,
                    daily:   data.benchmarkData.daily   || existing.daily   || [],
                    weekly:  data.benchmarkData.weekly  || existing.weekly  || [],
                    monthly: data.benchmarkData.monthly || existing.monthly || [],
                    hourly:  data.benchmarkData.hourly  || existing.hourly  || [],
                };
                window.WIG_DATA = window.BENCHMARK_DATA;
                // Cache history separately so it survives page reloads without re-fetching
                try {
                    const bmId = data.benchmarkId || window.BENCHMARK_ID || 'WIG';
                    localStorage.setItem(`benchmark_history_${bmId}`, JSON.stringify({
                        ts: Date.now(), data: data.benchmarkData,
                    }));
                } catch(_) {}
            }
            if (typeof renderBenchmarkChart === 'function') {
                renderBenchmarkChart(window.BENCHMARK_DATA, null, null);
            }
            document.dispatchEvent(new CustomEvent('benchmarkHistoryReady', { detail: data }));
            return;
        }

        const previousPortfolioData = Array.isArray(window.PORTFOLIO_DATA) ? window.PORTFOLIO_DATA : [];
        const previousWalletHoldings = window.WALLET_HOLDINGS || {};
        const previousBenchmarkId = window.BENCHMARK_ID || null;

        // Full arrives after lite: gauge/commentary are already rendered and frozen.
        // Portfolio daily % changes (lite=intraday, full=prev-close) — we update wallet
        // cards but do NOT change the gauge needle (PORTFOLIO_DAILY_CHANGE_PCT).
        const isFullAfterLite = data.responseMode === 'full' && window._gaugeDataReady;

        // Set all portfolio globals from API response
        window.PORTFOLIO_UPDATED_AT         = data.updatedAt;
        window.WALLET_SUMMARIES             = data.walletSummaries;
        window.PORTFOLIO_DATA               = preserveDeferredData
            ? _mergeHoldingBars(data.portfolioData || [], previousPortfolioData)
            : data.portfolioData;
        window.PORTFOLIO_TOTAL_VALUE        = data.portfolioTotalValue;
        window.PORTFOLIO_DAILY_CHANGE_PLN   = data.portfolioDailyChangePLN;
        window.PORTFOLIO_DAILY_CHANGE_PCT   = data.portfolioDailyChangePCT;
        try { localStorage.setItem('emerytura_daily_pct', data.portfolioDailyChangePCT); } catch(_) {}
        window.PORTFOLIO_ATH = data.portfolioAth || null;
        window.WALLET_ATHS = data.walletAths || {};
        window.WALLET_PORTFOLIO_IDS         = data.walletPortfolioIds || {};
        window.WALLET_HOLDINGS              = preserveDeferredData
            ? _mergeWalletHoldings(data.walletHoldings || {}, previousWalletHoldings)
            : (data.walletHoldings || {});
        
        window.ROAST_DATA                   = data.roastData || null;

        // Derive dynamic wallet list: Summary first, then remaining wallets in order
        if (data.walletSummaries) {
            const otherWallets = Object.keys(data.walletSummaries).filter(k => k !== 'Summary');
            window.PORTFOLIO_WALLETS = ['Summary', ...otherWallets];
        }

        // Apply benchmark data from response (user-specific)
        if (data.benchmarkId) {
            window.BENCHMARK_ID   = data.benchmarkId;
            window.BENCHMARK_NAME = data.benchmarkName || data.benchmarkId;
            const bmSel = document.getElementById('mgmt-benchmark-select');
            if (bmSel) bmSel.value = data.benchmarkId;
        } else {
            window.BENCHMARK_ID   = 'WIG';
            window.BENCHMARK_NAME = 'WIG';
        }
        if (!preserveDeferredData || (Array.isArray(data.marketCarousel) && data.marketCarousel.length)) {
            window.MARKET_CAROUSEL = Array.isArray(data.marketCarousel) ? data.marketCarousel : [];
        }
        if (previousBenchmarkId && previousBenchmarkId !== window.BENCHMARK_ID && typeof window.resetBenchmarkRangeAuto === 'function') {
            window.resetBenchmarkRangeAuto();
        }
        const benchmarkPayload = data.benchmarkData || data.wigData || null;
        // Benchmark history data (for chart).
        // Full response sends only intraday bars — merge into existing BENCHMARK_DATA
        // (preserving historical daily/weekly/monthly from static data or a prior history fetch).
        if (benchmarkPayload) {
            const existing = window.BENCHMARK_DATA || {};
            const hasExistingHistory = (existing.daily || []).length > 0;
            if (isFullAfterLite && hasExistingHistory && !benchmarkPayload.daily?.length) {
                // Full: only intraday arrived — update intraday but keep existing history
                window.BENCHMARK_DATA = {
                    ...existing,
                    intraday: benchmarkPayload.intraday || existing.intraday || [],
                };
            } else {
                window.BENCHMARK_DATA = benchmarkPayload;
            }
            window.WIG_DATA = window.BENCHMARK_DATA;
        }
        // Server-provided daily % from lite is authoritative (intraday open→current).
        // Full intentionally sends null so the gauge stays frozen after lite.
        if (!isFullAfterLite) {
            if (typeof data.benchmarkDailyPct === 'number') {
                window.BENCHMARK_DAILY_PCT = data.benchmarkDailyPct;
                window.WIG_DAILY_PCT       = data.benchmarkDailyPct;
                _cacheBenchmarkDailyPct(window.BENCHMARK_ID, data.benchmarkDailyPct);
            } else if (typeof data.wigDailyPct === 'number') {
                window.BENCHMARK_DAILY_PCT = data.wigDailyPct;
                window.WIG_DAILY_PCT       = data.wigDailyPct;
                _cacheBenchmarkDailyPct(window.BENCHMARK_ID, data.wigDailyPct);
            } else if (benchmarkPayload) {
                const computedBenchmarkPct = computeBenchmarkDailyPct(benchmarkPayload, window.BENCHMARK_ID);
                if (typeof computedBenchmarkPct === 'number' && !Number.isNaN(computedBenchmarkPct)) {
                    window.BENCHMARK_DAILY_PCT = computedBenchmarkPct;
                    window.WIG_DAILY_PCT       = computedBenchmarkPct;
                    _cacheBenchmarkDailyPct(window.BENCHMARK_ID, computedBenchmarkPct);
                }
            }
        }
        if (typeof updateBenchmarkChartLabels === 'function') updateBenchmarkChartLabels();

        // Cache full response so next page load shows these values instantly
        if (persistCache) {
            try {
                const currentUserId = window.AuthGuard && AuthGuard.getUserId ? AuthGuard.getUserId() : null;
                localStorage.setItem('lambda_cache', JSON.stringify({ ts: Date.now(), data, userId: currentUserId }));
            } catch(_) {}
        }

        // Signal other scripts that fresh data is available
        document.dispatchEvent(new CustomEvent('liveDataReady', { detail: data }));
    }

    function _restoreCachedBenchmarkHistory() {
        try {
            const bmId = window.BENCHMARK_ID || 'WIG';
            const raw  = localStorage.getItem(`benchmark_history_${bmId}`);
            if (!raw) return;
            const { ts, data: hist } = JSON.parse(raw);
            if (!hist || Date.now() - ts > 24 * 60 * 60 * 1000) return;
            const existing = window.BENCHMARK_DATA || {};
            window.BENCHMARK_DATA = {
                ...existing,
                daily:   hist.daily   || existing.daily   || [],
                weekly:  hist.weekly  || existing.weekly  || [],
                monthly: hist.monthly || existing.monthly || [],
                hourly:  hist.hourly  || existing.hourly  || [],
            };
            window.WIG_DATA = window.BENCHMARK_DATA;
        } catch(_) {}
    }

    function applyCachedLambdaData() {
        try {
            const raw = localStorage.getItem('lambda_cache');
            if (!raw) return false;
            const { ts, data, userId: cachedUserId } = JSON.parse(raw);
            // Discard cache if it belongs to a different user OR if we can't confirm it's the same user
            const currentUserId = window.AuthGuard && AuthGuard.getUserId ? AuthGuard.getUserId() : null;
            if (!currentUserId || !cachedUserId || currentUserId !== cachedUserId) {
                if (cachedUserId) {
                    localStorage.removeItem('lambda_cache');
                    console.log('[live-data] Cleared stale cache — user mismatch or unknown user');
                }
                return false;
            }
            // Only use cache if it's less than 24 hours old
            if (Date.now() - ts > 24 * 60 * 60 * 1000) return false;
            applyLiveData(data);
            _restoreCachedBenchmarkHistory();
            if (typeof renderDashboard === 'function') renderDashboard();
            if ((data.benchmarkData || data.wigData) && typeof renderBenchmarkChart === 'function') {
                renderBenchmarkChart(data.benchmarkData || data.wigData, null, null);
            }
            const age = Math.round((Date.now() - ts) / 60000);
            showStatus(`⟳ Cached (${age}m ago) — refreshing…`, 'loading');
            return true;
        } catch(_) { return false; }
    }

    async function fetchWithTimeout(url, ms, options = {}) {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), ms);
        try {
            const res = await fetch(url, { signal: controller.signal, ...options });
            clearTimeout(id);
            return res;
        } catch (e) {
            clearTimeout(id);
            throw e;
        }
    }

    function _authFetchOptions() {
        try {
            const token = window.AuthGuard && AuthGuard.getIdToken();
            if (token) {
                return { headers: { 'Authorization': `Bearer ${token}` } };
            }
        } catch (_) {}
        return {};
    }

    document.addEventListener('DOMContentLoaded', async () => {
        // New users start with empty portfolios — they use ⚙️ Manage to add holdings.
        // Do NOT auto-migrate CSV data (that's personal data belonging to one user).
        const hasWallets = await checkWalletBootstrapState();
        if (!hasWallets && window.__walletBootstrapState === 'empty') return;

        // Apply cached Lambda response immediately so the user sees recent data right away
        const hadCache = applyCachedLambdaData();
        if (!hadCache) showStatus('⟳ Refreshing prices…', 'loading');
        const liteOk = await doFetch('lite');
        if (liteOk) {
            void doFetch('full', 1, { background: true });
        } else {
            await doFetch('full');
        }
    });

    async function doFetch(view = 'full', attempt = 1, options = {}) {
        const isLite    = view === 'lite';
        const isHistory = view === 'history';
        const background = !!options.background;
        try {
            const timeoutMs = attempt > 1 ? RETRY_TIMEOUT_MS : TIMEOUT_MS;
            const res = await fetchWithTimeout(_buildApiUrl(view), timeoutMs, _authFetchOptions());
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            // History responses are handled entirely inside applyLiveData (early return)
            if (isHistory) {
                applyLiveData(data, {});
                return true;
            }
            applyLiveData(data, {
                preserveDeferredData: isLite,
                persistCache: !isLite,
            });
            if (isLite) {
                window._gaugeDataReady = true;
            } else if (window._gaugeDataReady == null) {
                window._gaugeDataReady = true;
            }
            const updatedWarsaw = formatWarsawTime(data.updatedAt);
            if (isLite) {
                showStatus(`✓ Live prices — loading charts… (${updatedWarsaw} Warsaw)`, 'ok');
            } else {
                showStatus(`✓ Live — ${updatedWarsaw} Warsaw`, 'ok');
            }

            // Re-render dashboard + WIG chart with fresh Lambda data
            // Freeze secondary narrative (gauge tooltip + market commentary) on the background full fetch
            // so the user sees stable text while the gauge needle updates to intraday accuracy
            const freezeSecondaryNarrative = background && !isLite;
            const frozenGaugeComment = freezeSecondaryNarrative ? _captureGaugeTooltipState() : null;
            const frozenMarketCommentary = freezeSecondaryNarrative ? _captureMarketCommentaryState() : null;
            if (typeof renderDashboard === 'function') renderDashboard();
            if ((data.benchmarkData || data.wigData) && typeof renderBenchmarkChart === 'function') {
                renderBenchmarkChart(data.benchmarkData || data.wigData, null, null);
            }

            const _portVal = Number(window.PORTFOLIO_DAILY_CHANGE_PCT || 0);
            const _bmVal = window.BENCHMARK_DAILY_PCT ?? (typeof WIG_DAILY_PCT !== 'undefined' ? WIG_DAILY_PCT : null);
            const _bmName = window.BENCHMARK_NAME;
            const _signature = [
                Number.isFinite(_portVal) ? _portVal.toFixed(2) : '0.00',
                Number.isFinite(_bmVal) ? Number(_bmVal).toFixed(2) : 'na',
            ].join('|');
            const _shouldAnimateGauge = typeof animateGaugeEntry === 'function' && window._lastGaugeAnimSignature !== _signature;
            window._lastGaugeAnimSignature = _signature;

            // Tell renderDashboard to leave the gauge canvas blank — animation will sweep in on next rAF
            if (_shouldAnimateGauge) window._gaugeAnimationPending = true;
            if (typeof renderDashboard === 'function') renderDashboard();

            const _finalizeNarrative = () => {
                if (frozenGaugeComment) _restoreGaugeTooltipState(frozenGaugeComment);

                // Render market commentary once after the lite fetch (first accurate live data).
                // On the full background fetch, restore it so it doesn't change.
                if (!window._marketCommentaryRendered && isLite) {
                    renderMarketCommentary(_bmVal, _bmName);
                    window._marketCommentaryRendered = true;
                } else if (frozenMarketCommentary) {
                    _restoreMarketCommentaryState(frozenMarketCommentary);
                }
            };

            if (_shouldAnimateGauge) {
                animateGaugeEntry('gaugeChart', _portVal, _bmVal, _finalizeNarrative);
            } else {
                _finalizeNarrative();
            }

            // Refresh portfolio tab if it was already initialized (user has visited it)
            if (typeof initPortfolioCharts === 'function') {
                window._portfolioInitialized = false; // reset guard so re-init runs
                if (document.getElementById('tab-portfolio') &&
                    document.getElementById('tab-portfolio').classList.contains('active')) {
                    initPortfolioCharts();
                }
            }
            return true;
        } catch (e) {
            const isAbort = e && (
                e.name === 'AbortError' ||
                String(e.message || '').toLowerCase().includes('signal is aborted')
            );
            if (isAbort && attempt === 1) {
                console.warn(`live-data.js: ${view} Lambda fetch timed out after ${TIMEOUT_MS}ms; retrying with ${RETRY_TIMEOUT_MS}ms`);
                if (!background) showStatus('⟳ Lambda is waking up — retrying…', 'loading');
                return doFetch(view, attempt + 1, options);
            }
            if (isAbort) {
                console.warn(`live-data.js: ${view} Lambda fetch timed out; using cache if available`);
            } else {
                console.error(`live-data.js: ${view} Lambda fetch failed:`, e);
            }
            if (background) {
                return false;
            }
            const hadCache = !!localStorage.getItem('lambda_cache');
            const fallbackMessage = isAbort ? 'request timed out' : e.message;
            showStatus(hadCache ? '⚠ Using cached prices' : '⚠ Using cached prices — ' + fallbackMessage, 'error');
            if (hadCache) document.dispatchEvent(new CustomEvent('liveDataReady'));
            return false;
        }
    }

    window.refreshLivePrices = async function () {
        if (window.__refreshLivePricesPromise) {
            return window.__refreshLivePricesPromise;
        }

        window.__refreshLivePricesPromise = (async () => {
            showStatus('⟳ Refreshing prices…', 'loading');
            window._lastGaugeAnimSignature = null;
            window._marketCommentaryRendered = false;
            window._gaugeDataReady = false;
            try { localStorage.removeItem('lambda_cache'); } catch (_) {}
            const liteOk = await doFetch('lite');
            if (liteOk) {
                void doFetch('full', 1, { background: true });
                return true;
            }
            return doFetch('full');
        })();

        try {
            return await window.__refreshLivePricesPromise;
        } finally {
            window.__refreshLivePricesPromise = null;
        }
    };

    window.addEventListener('portfolioHistoryRecalculated', () => {
        if (typeof window.refreshLivePrices === 'function') {
            window.refreshLivePrices();
        }
    });

    /** Fetch full benchmark history on-demand (called by setBenchmarkRange for YTD/1Y). */
    window.fetchBenchmarkHistory = async function () {
        return doFetch('history', 1, {});
    };
})();
