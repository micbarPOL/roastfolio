/* roast-engine.js — Roastfolio Sarcastic Commentary Engine
 *
 * "I'm not being sarcastic. I'm making accurate observations in a register
 *  that some people find socially uncomfortable. That is a them problem."
 *
 * Tone: Sheldon Cooper — precise, condescending, accidentally supportive.
 * 14 market-condition categories. 124 distinct commentary entries.
 * Rotation: no repeat within the last 3 picks per category.
 *
 * Context schema:
 *   changePct         {number}       — today's portfolio Δ% (signed, e.g. -2.3)
 *   isATH             {boolean}      — portfolio at all-time high
 *   benchmarkDiff     {number}       — portfolio minus benchmark Δ% today
 *   depositGoalMet    {boolean|null} — null = no goal configured
 *   streak            {number}       — longest active streak in months
 *   concentrationPct  {number}       — largest single-holding weight %
 *   concentrationName {string}       — name of that holding
 *   volatilityHigh    {boolean}      — elevated intraday swing detected
 *   swingPct          {number}       — intraday high/low range %
 *   roastIntensity    {string}       — tone setting (gentle | sarcastic | brutal | degen)
 *   recentDeposit     {boolean}      — user made a deposit recently
 *   noWithdrawalStreak{number}       — months without withdrawal
 *   fireProgressImproved {boolean}   — FIRE progress improved
 *   heldDuringDrawdown {boolean}     — user did not panic sell
 *   concentrationReduced {boolean}   — user reduced concentration risk
 *   monthlyChangePct   {number}      — monthly return
 *   monthlyBenchmarkDiff {number}    — monthly portfolio minus benchmark
 *
 * Returns: { text: string, category: string, outcomeType: string, timestamp: number }
 *
 * I want to note, for the record: I did not design the stock market.
 * I only comment on it. These are categorically different responsibilities
 * with different accountability structures. I find the distinction important.
 */
(function () {
    'use strict';

    var HISTORY_SIZE = 3;

    // ═══════════════════════════════════════════════════════════════════════════
    // COMMENTARY POOLS  —  124 entries across 14 categories
    // ═══════════════════════════════════════════════════════════════════════════
    var POOLS = {

        // ── POSITIVE: MILD  (+0.1 % → +1 %) ──────────────────────────────────
        positive_mild: [
            "Portfolio up {pct}. In the grand scheme of market mechanics, this is technically progress. I'll allow it.",
            "A {pct} gain. Statistically unremarkable, but I've learned to acknowledge incremental victories when positive reinforcement appears warranted.",
            "Up {pct}. The market, in its infinite and mostly irrational wisdom, has decided to reward you today. File this under 'pleasant anomalies.'",
            "Portfolio increased by {pct}. I ran the numbers three times. The result is internally consistent. You're welcome for the confirmation.",
            "Up {pct}. Not significant enough to cite in a research paper, but sufficient for a mild, controlled sense of forward momentum.",
            "The portfolio registered a {pct} gain. The trajectory is correct. The rate, however, leaves measurable room for improvement. I'm simply being thorough.",
            "Forward motion: {pct}. Even the Voyager probe had unremarkable transit days between notable observations.",
            "Your portfolio climbed {pct}. The market occasionally rewards patience with small increments. Today was one of those increments.",
            "Up {pct}. By my calculations, you are fractionally less wrong than you were yesterday. Statistically, that is what progress looks like.",
            "Portfolio: {pct}. The second law of thermodynamics suggests entropy increases over time. Today you've temporarily, and I want to stress temporarily, resisted the trend.",
            "Up {pct}. I suppose in a universe tending toward maximum entropy, any localized increase in value is a statistical anomaly worth a minor physical acknowledgment. Nod.",
            "A {pct} gain. It\u2019s barely above the margin of error of a rounding function, but I\u2019ll concede it is technically positive. Barely.",
        ],

        // ── POSITIVE: STRONG  (+1 % → +3 %) ──────────────────────────────────
        positive_strong: [
            "Up {pct}. That's a statistically interesting outcome. I'd say 'impressive,' but I don't want to create expectations that exceed the reproducible mean.",
            "{pct} gain today. The market has behaved in a manner consistent with your preferred hypothesis. Enjoy this before regression to the mean reasserts itself.",
            "Portfolio {pct}. In the scientific community this would be a reproducible positive result. In investing, we call it Thursday.",
            "A {pct} increase. Your portfolio is performing like a well-cited paper — gathering positive attention. Whether the methodology is sound remains a separate inquiry.",
            "Up {pct} today. This is what compound interest looks like when it's in a cooperative mood. I would recommend noting the date for reference.",
            "{pct} — not quite extraordinary, but comfortably above the mean. You're operating in what I'd classify as the 'pleasant surprise' percentile.",
            "Portfolio up {pct}. The laws of mathematics are working in your favor today. This is not entirely your doing, but I'll permit you the satisfaction.",
            "A {pct} return. In controlled conditions, I would include this in a working paper. In the market, I simply note it and continue the observation.",
            "Up {pct}. Even I find this mildly satisfying, and I have an extremely high threshold for satisfaction. That should register as meaningful feedback.",
            "{pct} today. The system is behaving in accordance with the long-term model's projections. 'Eventually' occasionally arrives ahead of schedule.",
            "Up {pct}. Statistically significant. I would offer you a hot beverage, but I reserve those for emotional distress, and you appear to be experiencing unwarranted euphoria.",
            "A {pct} increase. Your portfolio is expanding. Unlike the universe, however, this expansion is highly unlikely to be infinite or constant. Enjoy it while the math permits.",
        ],

        // ── POSITIVE: EXCEPTIONAL  (> +3 %) ──────────────────────────────────
        positive_exceptional: [
            "Up {pct}. I calculated the probability distribution for today's outcomes. This region was not high-frequency. Congratulations on your statistically improbable session.",
            "{pct} gain. The market has temporarily lost its mind in your favor. Log the result, derive no generalizable lesson from it, and proceed accordingly.",
            "Portfolio {pct}. I would express excitement, but performative enthusiasm is intellectually undignified. This is, however, objectively excellent by every metric I track.",
            "Up {pct}. This is what physicists call a 'large deviation event.' The market is not usually this cooperative. I suggest appreciating the anomaly without over-indexing on it.",
            "A {pct} day. In the game theory of long-term investing, you just drew the best available card from the deck. Statistically, it was due to appear eventually.",
            "Up {pct}. I'm not attributing this to brilliance on your part. I'm noting you were positioned correctly for a tail event. The distinction is important for reproducibility.",
            "{pct} in a single session. The portfolio equivalent of predicting a solar eclipse accurate to the nearest five minutes. Well positioned.",
            "Portfolio up {pct}. Even by my rigorous analytical standards, this qualifies as 'impressive.' Filed under: exceptions that support the long-run mean rather than contradict it.",
            "Up {pct}. I want to formally state that this is not normal. I also want to formally state that you should enjoy it. Both propositions are simultaneously true.",
            "{pct}. The mathematics of wealth accumulation produced an unusually clear and favorable result today. I find this difficult to criticize, so I've elected not to.",
            "Up {pct} in a single session. This level of variance is highly irregular. I suggest checking for calculation errors before engaging in any primitive celebratory rituals.",
            "A {pct} gain. While you may attribute this to your own financial genius, probability theory dictates you merely experienced a favorable tail-event. You're welcome for the reality check.",
        ],

        // ── NEGATIVE: MILD  (−0.1 % → −1 %) ─────────────────────────────────
        negative_mild: [
            "Down {pct}. This falls within normal operating parameters. I'm noting it solely because ignoring data is intellectually irresponsible.",
            "Portfolio {pct}. A minor correction. The market is exercising its well-documented right to be irrational in small, manageable increments.",
            "{pct} today. Statistically, this is noise. Emotionally, I understand it may register as a signal. For the record: it is not a signal.",
            "Down {pct}. The portfolio experienced a minor gravitational adjustment. Standard market physics. No corrective action is indicated.",
            "A {pct} day. In the context of your long-term trajectory, this is approximately as significant as a typographical error in a four-hundred-page thesis.",
            "Portfolio down {pct}. I've reviewed the data. This is not a trend. It is a Tuesday expressing itself through the equity market.",
            "{pct}. The market sneezed. Your portfolio said 'gesundheit' with a modest decline. No further clinical response is required.",
            "Down {pct}. The market is periodically testing your commitment to rational decision-making. This particular test has a passing grade, and it is: inaction.",
            "{pct} today. I want to note that I modeled this as one of several possible outcomes. Science routinely produces multiple possible outcomes. This is one of them.",
            "Portfolio: {pct}. Minor turbulence. The statistical equivalent of a delayed departure, not an accident investigation.",
            "Down {pct}. A negligible contraction. If you are experiencing distress over this, I recommend recalibrating your emotional baseline to account for basic market thermodynamics.",
            "A {pct} drop. You lost money. Not enough to warrant panic, but certainly enough to remind you that your asset allocation is subject to the whims of lesser minds trading on margin.",
        ],

        // ── NEGATIVE: STRONG  (−1 % → −3 %) ─────────────────────────────────
        negative_strong: [
            "Down {pct}. This is uncomfortable by design. The market is recalibrating. Your assignment, for which there is no partial credit, is to remain boring.",
            "Portfolio {pct}. Irksome. Not catastrophic. Not acceptable as a permanent state. Temporary, if the historical record is admitted as evidence.",
            "{pct}. The market has determined that your portfolio requires a stress test today. This is not personal. Markets lack the cognitive hardware for personal.",
            "Down {pct} today. In the grand experiment of long-term investing, this is a control variable, not a confounding result. Update the model, not the strategy.",
            "A {pct} session. I've reviewed three prior market cycles. Drawdowns of this magnitude preceded recoveries in a substantial and statistically significant majority of cases.",
            "Portfolio down {pct}. The correct response is inaction. The incorrect responses include, but are not limited to: panic-selling, revenge-buying, and calling anyone.",
            "{pct}. This is what 'short-term volatility' looks like when it has a name. It has a name because it is a recurring phenomenon. Recurring phenomena have names.",
            "Down {pct}. I'd offer condolences, but that would imply the position has ended. It has not ended. It is open. These are different states.",
            "{pct} today. The market expressed an opinion. You were not required to agree with it. The long-term thesis remains your most defensible counterargument.",
            "Portfolio {pct}. I recommend reviewing your investment thesis rather than your current balance. The thesis is the object that actually contains useful information.",
            "Down {pct}. This is a statistically notable deviation downward. I'd offer sympathy, but I find mathematics far more comforting than human platitudes.",
            "A {pct} decline. If your portfolio were a train, it would currently be experiencing a minor derailment. I suggest remaining seated until the variance normalizes.",
        ],

        // ── NEGATIVE: SEVERE  (< −3 %) ───────────────────────────────────────
        negative_severe: [
            "Down {pct}. The market has entered what I would diplomatically describe as 'an irrational emotional episode.' You are not the therapist here. Do not engage.",
            "{pct}. Significant drawdown detected. This is where the empirical separation between investors and people who used to be investors becomes directly observable.",
            "Portfolio {pct}. Uncomfortable? Objectively, yes. Terminal? Only for those who convert paper losses into realized ones by selling. The decision, structurally, is still yours.",
            "A {pct} loss. I want to be precise: this is not a catastrophe. It is a test. The question on the test is: do you actually understand what you own?",
            "Down {pct}. Historical context: in October 1987, the Dow fell 22.6% in a single session. Holders recovered. Sellers crystallized permanent losses. I offer this as data.",
            "{pct}. The portfolio is experiencing what market participants euphemistically call a 'correction.' I call it 'opportunity cost made visible for the impatient.'",
            "Down {pct} today. I've updated the model. The long-term projection has not materially changed. The short-term projection is most accurately described as 'unpleasant.'",
            "Portfolio {pct}. Every investor eventually encounters a session like this. Most survive it. The variable that determines survival is not portfolio quality. It's behavior.",
            "{pct}. This is a stress test for your own risk tolerance — not for the quality of your holdings. These are not the same measurement. The distinction matters.",
            "Down {pct}. The market periodically needs to remind participants that certainty belongs to mathematics and not to equities. Consider yourself formally reminded today.",
            "Down {pct}. Fascinating. Your wealth is evaporating at a rate that almost rivals the half-life of Francium. I am observing this with intense scientific curiosity.",
            "A {pct} drop. This is a catastrophic localized failure of your asset values. Please ensure you do not make any sudden, emotionally compromised decisions. Or do. The data will be interesting either way.",
        ],

        // ── FLAT  (±0.1 %) ────────────────────────────────────────────────────
        flat: [
            "Portfolio: {pct}. The market achieved near-perfect thermodynamic equilibrium today. Fascinating in a deeply unremarkable way.",
            "Flat session. The market spent the day in a state of statistical indifference. Much like how I experience most social gatherings, but with slightly more liquidity.",
            "{pct}. You could have done literally nothing today. You did, in fact, do that. That was the correct decision. Well executed.",
            "Portfolio unchanged. Today the market adopted the philosophical position: 'Why move when stasis is available?' I find this unusually relatable.",
            "A flat day. The market assessed your portfolio with complete neutrality and moved on. Mutual indifference. A structurally healthy dynamic.",
            "{pct}. By definition, today's performance was average for a day that produces zero movement. The only correct outcome for a flat day is a flat day.",
            "Neither up nor down. The market achieved the investing equivalent of a held breath. It will exhale eventually. These things have historically resolved.",
            "Portfolio: {pct}. The arithmetic is unambiguous. The market had no strong feelings about your allocation today. I suggest you reciprocate that energy.",
            "Change: {pct}. Your portfolio achieved a state of perfect inertia today. Sir Isaac Newton would be incredibly proud of your financial stagnation.",
            "Flat. No movement. The financial equivalent of absolute zero, where all market thermodynamic activity has apparently ceased in your account.",
        ],

        // ── ALL-TIME HIGH ─────────────────────────────────────────────────────
        ath: [
            "New all-time high. The portfolio has exceeded every value it has previously held. I've updated the spreadsheet. The new maximum is highlighted.",
            "ATH. Every future value must now either match or exceed this number to represent forward progress. You have raised the baseline. That is what accumulation does.",
            "All-time high. I ran a probabilistic analysis of reaching this exact value from your starting point. The probability was non-zero. Evidently.",
            "Portfolio at a new peak. The mathematics of compounding are performing precisely as long-run models predict, given sufficient patience. This is what that looks like.",
            "New ATH. The correct response is not celebration but continuation — doing exactly what produced this result. That said: objectively, this is good. I'm acknowledging it.",
            "All-time high reached. I want to note this with appropriate gravity. The accumulation strategy is producing measurable output. The evidence is this specific number.",
            "New peak. The portfolio has no historical precedent for its current value. That is, by definition, the point of long-term compounding. Records exist to be exceeded.",
            "ATH registered. I would advise against excessive emotional response, but some acknowledgment is statistically appropriate given the inputs required to reach this point.",
            "New All-Time High. You have achieved a local maximum. Statistically speaking, the only mathematically guaranteed direction from a peak is down. Have a nice day.",
            "ATH reached. I am obligated by social convention to say 'congratulations,' despite the fact that this is merely the expected outcome of an upward-drifting geometric Brownian motion.",
        ],

        // ── MISSED GOAL ───────────────────────────────────────────────────────
        missed_goal: [
            "Monthly deposit target: not met. I understand life is occasionally uncooperative. I'm the record-keeper. The record currently shows an unfilled cell.",
            "Goal missed this month. The plan remains structurally viable. It functions only when reactivated. Passive observation of a missed target is not a recovery mechanism.",
            "Deposit goal: missed. I won't deliver a lecture. I'll simply note that the compound effect of a missing contribution accumulates over time, and allow you to run the arithmetic.",
            "You didn't hit the deposit target this month. The market is unaware of this. Your future self, however, is already computing the downstream implications.",
            "Goal missed. The streak has ended. A new one is available to start immediately. I find this mathematically straightforward and, unexpectedly, somewhat poetic.",
            "Monthly target: unmet. One missed contribution is a rounding error over a long horizon. A pattern of missed contributions is an entirely different calculation. Know which this is.",
            "Deposit fell short this month. The plan was designed to accommodate occasional human inconsistency. What it cannot accommodate is indefinite non-resumption. Resume.",
            "Monthly goal: not reached. I've noted this without judgment. The compound interest model has also noted it, with the cold neutrality that arithmetic consistently provides.",
            "Deposit goal missed. I have updated my models to account for your behavioral inconsistency. The projected date of your financial independence has been extended accordingly.",
            "You failed to hit your deposit target. I could explain the long-term impact of interrupted compounding, but I fear the math would only induce a stress-related headache.",
        ],

        // ── STRONG CONSISTENCY ────────────────────────────────────────────────
        strong_consistency: [
            "Streak at {n} months. You've empirically identified the single most effective force in personal investing: showing up with capital when there is nothing exciting to report.",
            "{n}-month contribution streak. At this point you're not merely depositing money. You're operating a systematic capital acquisition protocol. The distinction is non-trivial.",
            "Consistency indicator: {n} consecutive months. I've analyzed behavioral patterns across multiple cohorts. This one correlates with outcomes. The correlation is not accidental.",
            "Month {n} in a row. Some investors read about discipline. You appear to be implementing it. The measurable gap between those two activities is the entire ballgame.",
            "{n} consecutive deposits. The market has provided approximately {n} separate invitations to lose conviction. You've declined each one. This is statistically the correct response.",
            "Streak: {n} months. The documented value of doing a thing consistently exceeds the value of doing the theoretically optimal thing occasionally. You've found the more valuable behavior.",
            "{n}-month streak. There is a threshold at which a habit stops being a conscious choice and becomes structural behavior. Based on the data, you are approaching that threshold.",
            "Consistency score: elevated. The portfolio does not know why you're consistent. It only processes the result. The result is accumulation, which is the entire objective function.",
            "Streak: {n} months. You are demonstrating a level of repetitive, unvarying behavior that I find deeply comforting. Please do not alter this variable.",
            "{n} consecutive deposits. Your adherence to the schedule is highly commendable. It borders on the compulsive. We have so much in common.",
        ],

        // ── BENCHMARK BEAT ────────────────────────────────────────────────────
        benchmark_beat: [
            "You beat the benchmark by {diff} today. I'd say congratulations, but some percentage of investors outperform in any given session. You were in that cohort. Note it accordingly.",
            "Portfolio outperformed by {diff}. The benchmark is not a ceiling. You've treated it as a floor today. I recommend maintaining this structural orientation.",
            "Up {diff} vs the index. Your allocation produced a better result than the passive alternative. Whether this reflects skill or variance requires more than one observation.",
            "Benchmark beaten by {diff}. I've recorded this. I've also noted that one session is insufficient for a general conclusion. Both facts coexist without contradiction.",
            "You outperformed by {diff}. The market was not equally favorable to everyone today. It was comparatively more favorable to your specific allocation. I acknowledge this.",
            "Better than the index by {diff}. Active decisions produced passive-beating results. This is not guaranteed to repeat. It is, however, today's data point. Data points matter.",
            "Beat the benchmark today. In the ongoing empirical debate between active and passive investing, you've registered one vote for active. The study population remains open.",
            "Outperformed by {diff}. I want to note that this is harder to accomplish than the financial media implies. Most professionally managed funds fail at it. You did not. Today.",
            "Outperformed the benchmark by {diff}. A fascinating anomaly. Given the efficient market hypothesis, I must assume you are either in possession of insider information or merely exceedingly lucky. I will assume the latter to protect myself legally.",
            "Beat the index by {diff}. You bested the average. Given the general cognitive baseline of the average market participant, this is less impressive than you think it is.",
        ],

        // ── BENCHMARK LAG ─────────────────────────────────────────────────────
        benchmark_lag: [
            "Lagged the benchmark by {diff} today. The index outperformed you. The index has no strategy, no ego, and no feelings about this fact. I suggest you adopt a similar posture.",
            "Down {diff} vs the benchmark. The market rose more than your portfolio did. This is the core empirical argument for index funds delivered as a single, clean data point.",
            "Underperformed by {diff}. It occurs. The relevant question is whether this constitutes signal or noise. One session is noise. Six consecutive months is a thesis worth examining.",
            "Benchmark beat you by {diff}. I'm not advising a strategy change. I'm advising that you understand why this happened. Understanding causation precedes any rational response.",
            "Below the index by {diff}. The benchmark has no feelings, no strategy, and no ego. It outperformed today. This should register as informative rather than existential.",
            "Lagged by {diff}. Certain allocation decisions underperformed the market average today. This is data. Data should be distinguished from judgment. They are not the same thing.",
            "Underperformed the index by {diff}. If this is the fifth consecutive week, a strategic review is warranted. If this is one Tuesday in an otherwise functional year, it is probably not.",
            "{diff} below benchmark. The market has a mechanism for humbling everyone at regular intervals. Today was yours. Tomorrow is an independent data point with no memory of today.",
            "Lagged the benchmark by {diff}. The passive, unthinking market aggregate outperformed your active, presumably thoughtful strategy. The irony is palpable.",
            "Underperformed by {diff}. You would have literally generated more wealth by doing absolutely nothing and holding the index. Your active interference was mathematically detrimental.",
        ],

        // ── CONCENTRATION RISK  (≥ 40 % single holding) ───────────────────────
        concentration_risk: [
            "{holding} is {conc}% of your portfolio. In the field of risk management, this is classified as 'a bold hypothesis.' I'd recommend introducing a control group.",
            "Concentration alert: {holding} at {conc}%. This is either visionary positioning or overconfidence. Historical precedent contains documented examples of both outcomes.",
            "{conc}% in one position. Diversification exists for a documented mathematical reason. I'll present the data point and allow you to reach the logical conclusion independently.",
            "One holding at {conc}% of total portfolio value. This would be fine if you possessed perfect information about future prices. You do not. Nobody does. It's a structural constraint.",
            "Concentration at {conc}%. I'm not arguing the position is wrong. I'm noting that when {conc}% concentration moves against you, it does so substantially. That is the relevant theorem.",
            "{holding} at {conc}% of portfolio. This is, in the technical sense of the word, a bet. Bets can pay off. They can also reverse. The magnitude of either is amplified by the concentration.",
            "High concentration in {holding}: {conc}%. The efficient market hypothesis and your current risk profile appear to have reached a philosophical disagreement worth mediating.",
            "{conc}% in a single name. Warren Buffett operated at this concentration on companies he studied for decades with a team of analysts. I offer this as context, not endorsement.",
            "Concentration alert: {holding} is at {conc}%. You are putting an irrational number of eggs in one basket. If the basket is dropped, the resulting mess will be entirely your fault.",
            "Your allocation to {holding} is {conc}%. This lack of diversification violates basic Modern Portfolio Theory. Harry Markowitz is weeping, and I am highly disappointed.",
        ],

        // ── VOLATILITY HIGH ───────────────────────────────────────────────────
        volatility_high: [
            "Elevated volatility detected. The portfolio is moving more than the underlying fundamentals warrant. The market is experiencing feelings. This is both normal and irritating.",
            "High volatility today. Discipline is now the only variable separating investors from people who used to be investors. Apply it. There is no partial credit for applying it halfway.",
            "Significant price movement today. The market is not operating rationally in the short term. The good news: you are not required to respond irrationally. This remains your choice.",
            "Volatile session: {swing}% intraday range. The price of what you own moved considerably. The value of what you own almost certainly did not move by the same proportion.",
            "Elevated volatility. Your primary objective right now is to do nothing of consequence. Nothing of consequence is simultaneously the most difficult and most valuable strategy available.",
            "High volatility session. I've reviewed the historical data: volatility itself is not correlated with permanent portfolio loss. Selling during volatility is. The distinction is critical.",
            "Portfolio exhibiting elevated movement. In physics, this system would be described as 'far from equilibrium.' In investing, the documented historical pattern is eventual normalization.",
            "Volatility spike: {swing}% range. The market is reacting disproportionately to the available information. This occurs with sufficient regularity that it has documented patterns. Patterns resolve.",
            "Volatility is at {swing}%. Your portfolio is oscillating wildly. If it were a particle, its position and momentum would be entirely unknowable according to Heisenberg. Please stabilize.",
            "A {swing}% swing. The standard deviation of your returns is unacceptably high. This is an investment account, not a chaotic pendulum. Do try to reduce the entropy.",
        ],

        // ── PRAISE MODE (NEW) ─────────────────────────────────────────────────
        praise: [
            "You beat the benchmark today. I’m uncomfortable saying this, but that was competent.",
            "New all-time high. I didn't think you had it in you.",
            "FIRE progress improved. You're slightly less likely to work forever.",
            "Deposit streak maintained. Keep this up and you might actually retire.",
            "No panic selling detected. Are you feeling okay?",
            "You reduced concentration risk. A rare moment of rationality.",
            "You beat the benchmark, maintained your streak, and generated positive returns. I am struggling to find a flaw in your methodology today. It is highly frustrating.",
            "An optimal outcome. Everything executed precisely according to the parameters of a successful financial model. Bazinga! Just kidding, there is no joke. You actually did well.",
        ],

        mixed: [
            "You made money today, but the benchmark made more. Congratulations on being technically profitable and emotionally disappointing.",
            "You reduced concentration risk, but the portfolio still looks like a random number generator.",
            "Positive return today. Unfortunately, literally everyone else also had a positive return today.",
            "You made money, but underperformed the benchmark. You won the race, but only because the faster runner tripped. I will record it as a win, with an asterisk.",
            "Positive returns, but you lagged the index. It\u2019s the financial equivalent of getting a B+ on a physics exam. Acceptable to average people, but fundamentally disappointing to me.",
        ],

        roast: [
            "You underperformed the benchmark again. At this point, the index fund is not your benchmark, it’s your parent.",
            "Negative return, lagging the benchmark. Have you considered a high-yield savings account?",
            "You missed your deposit goal. The math doesn't care about your excuses.",
            "Down, lagging, and volatile. Your portfolio is currently a case study in how not to manage capital. I would write a paper on this, but the academic journals only publish novel phenomena, and incompetence is exceedingly common.",
            "Negative returns and benchmark underperformance. You have achieved a state of complete financial failure today. Would you like me to sing 'Soft Kitty' to soothe your ego?",
        ],

    };

    // ═══════════════════════════════════════════════════════════════════════════
    // ROTATION ENGINE
    // ═══════════════════════════════════════════════════════════════════════════
    var _seenMap = {};

    function _pick(category) {
        var pool = POOLS[category];
        if (!pool || !pool.length) return null;

        var seen      = _seenMap[category] || [];
        var available = [];
        for (var i = 0; i < pool.length; i++) {
            if (seen.indexOf(i) === -1) available.push(i);
        }

        var candidates = available.length ? available : pool.map(function (_, j) { return j; });
        var idx        = candidates[Math.floor(Math.random() * candidates.length)];

        _seenMap[category] = seen.concat(idx).slice(-HISTORY_SIZE);
        return pool[idx];
    }

    function _interpolate(template, vars) {
        return template.replace(/\{(\w+)\}/g, function (_, key) {
            return (vars[key] !== undefined && vars[key] !== null) ? vars[key] : '';
        });
    }

    function _fmt(n, signed) {
        var value = parseFloat(n);
        if (isNaN(value)) return '';
        var abs  = Math.abs(value).toFixed(1);
        var sign = signed ? (value >= 0 ? '+' : '−') : '';
        return sign + abs + '%';
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // CATEGORIZATION
    // Priority: ATH → volatility → concentration → benchmark → performance → flat
    // Note: missed_goal and strong_consistency are lifecycle-triggered — use
    //       getForCategory() explicitly at month-end or streak-milestone events.
    // ═══════════════════════════════════════════════════════════════════════════
    function categorize(ctx) {
        if (!ctx) return 'flat';
        
        var outcome = determineOutcomeType(ctx);
        if (outcome === 'praise') return 'praise';
        if (outcome === 'mixed') return 'mixed';
        if (outcome === 'roast') return 'roast';

        if (ctx.isATH)                              return 'ath';
        if (ctx.volatilityHigh)                     return 'volatility_high';
        if ((ctx.concentrationPct || 0) >= 40)      return 'concentration_risk';
        if ((ctx.benchmarkDiff || 0) >= 1)          return 'benchmark_beat';
        if ((ctx.benchmarkDiff || 0) <= -1)         return 'benchmark_lag';

        var pct = parseFloat(ctx.changePct) || 0;
        if (pct >= 3)    return 'positive_exceptional';
        if (pct >= 1)    return 'positive_strong';
        if (pct >  0.1)  return 'positive_mild';
        if (pct <= -3)   return 'negative_severe';
        if (pct <= -1)   return 'negative_strong';
        if (pct < -0.1)  return 'negative_mild';
        return 'flat';
    }

    function determineOutcomeType(ctx) {
        if (!ctx) return 'neutral';

        var pct = parseFloat(ctx.changePct) || 0;
        var bDiff = parseFloat(ctx.benchmarkDiff) || 0;
        var mPct = parseFloat(ctx.monthlyChangePct) || 0;
        var mBDiff = parseFloat(ctx.monthlyBenchmarkDiff) || 0;
        var benchPct = pct - bDiff; 

        var isStronglyPositive = (
            bDiff > 0 ||
            (pct > 0 && benchPct < 0) ||
            ctx.recentDeposit ||
            (ctx.streak && ctx.streak >= 1) ||
            (ctx.noWithdrawalStreak && ctx.noWithdrawalStreak > 0) ||
            ctx.isATH ||
            ctx.fireProgressImproved ||
            ctx.heldDuringDrawdown ||
            ctx.concentrationReduced ||
            (mPct > 0 && mBDiff > 0)
        );

        if (isStronglyPositive) return 'praise';
        if (pct > 0 && bDiff < 0) return 'mixed';
        if (ctx.concentrationReduced) return 'mixed';
        if (pct < 0 && bDiff < 0) return 'roast';
        if (ctx.volatilityHigh) return 'roast';
        if (ctx.concentrationPct >= 40 && !ctx.concentrationReduced) return 'roast';

        return 'neutral';
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PUBLIC API
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Get contextual commentary for the current portfolio state.
     *
     * @param  {object} ctx              — portfolio context (see schema in header)
     * @param  {string} [forceCategory]  — bypass auto-categorization
     * @returns {{ text: string, category: string, timestamp: number } | null}
     *
     * Example:
     *   const r = RoastEngine.getCommentary({ changePct: -2.1, isATH: false });
     *   console.log(r.text);  // "Down −2.1%. The market has determined that..."
     */
    function getCommentary(ctx, forceCategory) {
        ctx = ctx || {};
        var category = forceCategory || categorize(ctx);
        var template = _pick(category);
        if (!template) return null;

        var vars = {
            pct:     _fmt(ctx.changePct, true),
            n:       ctx.streak            !== undefined ? String(Math.round(ctx.streak)) : '',
            holding: ctx.concentrationName || 'your largest position',
            conc:    ctx.concentrationPct  !== undefined ? parseFloat(ctx.concentrationPct).toFixed(0) : '',
            diff:    _fmt(ctx.benchmarkDiff, false),
            swing:   ctx.swingPct          !== undefined ? parseFloat(ctx.swingPct).toFixed(1) : '',
        };

        return {
            text:      _interpolate(template, vars),
            category:  category,
            outcomeType: determineOutcomeType(ctx),
            timestamp: Date.now(),
        };
    }

    /**
     * Get commentary for a specific category, regardless of portfolio state.
     * Use for lifecycle events: month-end (missed_goal), streak milestones
     * (strong_consistency), or UI testing.
     *
     * @param  {string}  category
     * @param  {object}  [ctx]
     */
    function getForCategory(category, ctx) {
        return getCommentary(ctx || {}, category);
    }

    /**
     * Returns one sample entry per category — for onboarding demos or UI previews.
     * Does not affect the rotation state.
     */
    function getPreview() {
        return Object.keys(POOLS).map(function (cat) {
            return { category: cat, sample: POOLS[cat][0] };
        });
    }

    window.RoastEngine = {
        getCommentary:        getCommentary,
        categorize:           categorize,
        determineOutcomeType: determineOutcomeType,
        getForCategory:       getForCategory,
        getPreview:           getPreview,
        categories:           Object.keys(POOLS),
    };

}());
