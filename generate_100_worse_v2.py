import json
import re

templates = []

# Gentle (20)
gentle_jokes = [
    ("BENCHMARK_COMPARISON", "A Fair Showing", "You secured {{portfolioReturnPercent}}, which is commendable. {{benchmarkName}} stretched a bit further to {{benchmarkReturnPercent}}, but green is green."),
    ("RELATIVE_RETURN", "Not Far Behind", "Closing the day {{relativePerformancePercent}} behind the market is fine when the overall direction is upward. Good steady progress."),
    ("ABSOLUTE_RETURN", "Positive Territory Secured", "Your balance increased by {{portfolioReturnPercent}}. We can save the relative performance charts for another day."),
    ("BEST_ASSET", "The Bright Spot", "{{dailyBestAsset}} had a great session. Even if the broader portfolio trailed the index, you had some winning picks."),
    ("WORST_ASSET", "A Minor Stumbling Block", "If {{dailyWorstAsset}} had cooperated, you might have caught the benchmark. Still, ending positive is the main goal."),
    ("GENERAL_MARKET_CHAOS", "Catching The Breeze", "The market was broadly supportive today. You caught enough of that momentum to finish higher."),
    ("BENCHMARK_COMPARISON", "Growing, Just Not Fastest", "{{benchmarkName}} sprinted to {{benchmarkReturnPercent}}, while your portfolio jogged to {{portfolioReturnPercent}}. Both finished the race."),
    ("RELATIVE_RETURN", "Respectable Deficit", "Trailing by {{relativePerformancePercent}} in a positive market is a perfectly acceptable outcome. You grew your wealth today."),
    ("ABSOLUTE_RETURN", "A Step Forward", "You took a {{portfolioReturnPercent}} step forward. The market took two, but progress is what matters."),
    ("BEST_ASSET", "Doing The Heavy Work", "{{dailyBestAsset}} kept you firmly in the green. A solid anchor in a rising market."),
    ("WORST_ASSET", "Patience Required", "{{dailyWorstAsset}} held you back from matching the market's enthusiasm, but the overall result is still favorable."),
    ("GENERAL_MARKET_CHAOS", "Following The Leader", "The broader market led the way up, and your portfolio followed safely behind. A low-stress positive day."),
    ("BENCHMARK_COMPARISON", "Solid Baseline", "Your {{portfolioReturnPercent}} is a solid baseline. {{benchmarkName}} showed what was possible, but your outcome is safe and green."),
    ("RELATIVE_RETURN", "Slight Drag", "You underperformed by {{relativePerformancePercent}}, but when the absolute return is positive, it's hard to complain."),
    ("ABSOLUTE_RETURN", "Quietly Accumulating", "A calm, collected {{portfolioReturnPercent}} gain. You don't need to beat the market every day to build wealth."),
    ("BEST_ASSET", "A True Contributor", "Thank you to {{dailyBestAsset}} for making sure the portfolio didn't miss out on the market's good mood."),
    ("WORST_ASSET", "The Laggard", "Every portfolio has a laggard. Today it was {{dailyWorstAsset}}. But you still finished up overall!"),
    ("GENERAL_MARKET_CHAOS", "Lifted Up", "The strong market conditions lifted your portfolio nicely. A good day to be invested."),
    ("BENCHMARK_COMPARISON", "Healthy Returns", "{{portfolioReturnPercent}} is a healthy return. {{benchmarkName}}'s {{benchmarkReturnPercent}} is just an overachiever."),
    ("RELATIVE_RETURN", "A Mild Miss", "Missing the benchmark by {{relativePerformancePercent}} is a minor footnote on an otherwise profitable day.")
]

for i, (angle, title, msg) in enumerate(gentle_jokes):
    templates.append({
        "templateId": f"both_positive_user_worse_v2_gentle_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_WORSE",
        "tone": "mixed",
        "intensity": "gentle",
        "messageAngle": angle,
        "structureFamily": "PRIVATE_BANKER_NOTE",
        "metaphorCategory": "BANKING",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive but underperformed the benchmark.",
        "suggestedFocusTemplate": "Check the laggards in a positive tape.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Sarcastic (35)
sarcastic_jokes = [
    ("BENCHMARK_COMPARISON", "Participation Award", "You made {{portfolioReturnPercent}}. The benchmark, which requires zero brain cells, made {{benchmarkReturnPercent}}. Excellent work."),
    ("RELATIVE_RETURN", "The Gap Of Mediocrity", "You are {{relativePerformancePercent}} behind a generic index. Your unique insights really paid off with less money."),
    ("ABSOLUTE_RETURN", "A Very Modest Plus", "You gained {{portfolioReturnPercent}}. Try not to brag too loudly, lest someone check the S&P 500."),
    ("BEST_ASSET", "Carrying The Team", "{{dailyBestAsset}} is the only reason your portfolio isn't a complete embarrassment today compared to the market."),
    ("WORST_ASSET", "Deliberate Friction", "You could have matched the market, but you insisted on holding {{dailyWorstAsset}}. It's important to have principles, even if they cost money."),
    ("GENERAL_MARKET_CHAOS", "Dragged Kicking And Screaming", "The market dragged your portfolio into the green, against its own best efforts to remain flat."),
    ("BENCHMARK_COMPARISON", "The Active Manager Penalty", "Your active decisions yielded {{portfolioReturnPercent}}. The passive alternative yielded {{benchmarkReturnPercent}}. The math is gently mocking you."),
    ("RELATIVE_RETURN", "Trailing With Style", "You are underperforming by {{relativePerformancePercent}}, but at least you did it with a bespoke asset allocation."),
    ("ABSOLUTE_RETURN", "Technically Not Losing", "You are up {{portfolioReturnPercent}}. It's not beating the market, but it beats a savings account... barely."),
    ("BEST_ASSET", "One Good Apple", "{{dailyBestAsset}} is doing its best to hide the fact that you underperformed a robot today."),
    ("WORST_ASSET", "Self-Inflicted Wound", "Holding {{dailyWorstAsset}} during a bull run is a fascinating strategy. Let's see how it plays out long term."),
    ("GENERAL_MARKET_CHAOS", "Accidental Profit", "The market was so overwhelmingly green that it was statistically difficult not to make money. Yet, you almost managed it."),
    ("BENCHMARK_COMPARISON", "The Benchmark's Shadow", "Living in the shadow of {{benchmarkName}}'s {{benchmarkReturnPercent}} gain with your {{portfolioReturnPercent}}. It's a quiet life."),
    ("RELATIVE_RETURN", "A Negative Alpha Day", "That {{relativePerformancePercent}} deficit is what we in the business call 'negative alpha'. It's very exclusive."),
    ("ABSOLUTE_RETURN", "Microscopic Gains", "You gained {{portfolioReturnPercent}}. A microscope is available upon request to view your outperformance. Oh wait, you underperformed."),
    ("BEST_ASSET", "The Lone Wolf", "{{dailyBestAsset}} is howling at the moon. The rest of your portfolio is hiding under the porch."),
    ("WORST_ASSET", "Dead Weight Distribution", "Your portfolio is perfectly optimized to hold exactly enough of {{dailyWorstAsset}} to ruin a good market day."),
    ("GENERAL_MARKET_CHAOS", "Riding The Coattails", "You didn't beat the market, you just rode its coattails and then complained about the view."),
    ("BENCHMARK_COMPARISON", "An Expensive Hobby V2", "You pay fees to get {{portfolioReturnPercent}} while the free benchmark gets {{benchmarkReturnPercent}}. You are a philanthropist."),
    ("RELATIVE_RETURN", "The Underachiever", "You are underachieving the market by {{relativePerformancePercent}}. But your spreadsheets look very complicated, which is what matters."),
    ("ABSOLUTE_RETURN", "Green, But Make It Disappointing", "It is remarkable how you can make a positive {{portfolioReturnPercent}} feel like a loss."),
    ("BEST_ASSET", "A Heavy Burden", "I hope {{dailyBestAsset}} has a good chiropractor after carrying you today."),
    ("WORST_ASSET", "The Anchor", "You threw {{dailyWorstAsset}} overboard, but forgot to untie it from your ankle first."),
    ("GENERAL_MARKET_CHAOS", "Beta Squeezed", "You managed to extract the absolute minimum amount of beta from a wildly positive market."),
    ("BENCHMARK_COMPARISON", "A Lesson In Humility", "Let {{benchmarkName}}'s {{benchmarkReturnPercent}} serve as a gentle reminder that your {{portfolioReturnPercent}} is not genius."),
    ("RELATIVE_RETURN", "The Gap Widens", "You are now {{relativePerformancePercent}} further behind the curve. Consistency is key."),
    ("ABSOLUTE_RETURN", "A Rounding Error", "Your {{portfolioReturnPercent}} gain is essentially a rounding error on a real investor's spreadsheet."),
    ("BEST_ASSET", "The Only Green Flag", "{{dailyBestAsset}} is the only green flag in a portfolio full of red ones."),
    ("WORST_ASSET", "A Terrible Companion", "Why did you bring {{dailyWorstAsset}} to a bull market? It's embarrassing everyone."),
    ("GENERAL_MARKET_CHAOS", "Market Did The Work", "You did nothing and the market went up. Unfortunately, your portfolio also did nothing."),
    ("BENCHMARK_COMPARISON", "The Superior Alternative", "{{benchmarkName}} returned {{benchmarkReturnPercent}}. You returned {{portfolioReturnPercent}}. I have no further questions, Your Honor."),
    ("RELATIVE_RETURN", "Mathematically Inferior", "A {{relativePerformancePercent}} deficit is just math's way of saying 'try again'."),
    ("ABSOLUTE_RETURN", "A Very Small Win", "Celebrate your {{portfolioReturnPercent}} win softly, so the benchmark doesn't hear you."),
    ("BEST_ASSET", " Atlas Exhausted", "{{dailyBestAsset}} is shrugging. It can't hold up this portfolio forever."),
    ("WORST_ASSET", "The Sandbag", "You are running a race with {{dailyWorstAsset}} tied to your back. The benchmark is wearing track shoes.")
]

for i, (angle, title, msg) in enumerate(sarcastic_jokes):
    templates.append({
        "templateId": f"both_positive_user_worse_v2_sarcastic_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_WORSE",
        "tone": "roast",
        "intensity": "sarcastic",
        "messageAngle": angle,
        "structureFamily": "DETECTIVE",
        "metaphorCategory": "DETECTIVE",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive but underperformed the benchmark.",
        "suggestedFocusTemplate": "Consider passive indexing.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Brutal (30)
brutal_jokes = [
    ("BENCHMARK_COMPARISON", "Embarrassingly Behind", "You logged in, made trades, and got {{portfolioReturnPercent}}. A comatose ape holding {{benchmarkName}} got {{benchmarkReturnPercent}}. Reflect on this."),
    ("RELATIVE_RETURN", "Hemorrhaging Alpha", "You bled {{relativePerformancePercent}} against the market today. Your stock picking is actively destroying your wealth."),
    ("ABSOLUTE_RETURN", "Pathetic Gains", "You are up {{portfolioReturnPercent}}. The market is up significantly more. This isn't a win, it's a humiliating consolation prize."),
    ("BEST_ASSET", "One Hostage Survived V2", "If it weren't for {{dailyBestAsset}}, you would be deeply red on a day when literal garbage went up. Stop trading."),
    ("WORST_ASSET", "Financial Suicide", "Holding {{dailyWorstAsset}} while the market moons is a masterclass in wealth destruction. You are your own worst enemy."),
    ("GENERAL_MARKET_CHAOS", "Idiot-Proof Market Failed", "The market was designed to be idiot-proof today, and you still managed to underperform it. That takes a special kind of talent."),
    ("BENCHMARK_COMPARISON", "The Definition Of Failure", "{{benchmarkName}} is up {{benchmarkReturnPercent}}. You are up {{portfolioReturnPercent}}. You failed the easiest test in finance: just buy the index."),
    ("RELATIVE_RETURN", "A Monument To Hubris", "That {{relativePerformancePercent}} lag is a monument to your arrogance. You thought you knew better than the market. You didn't."),
    ("ABSOLUTE_RETURN", "Pitiful Outturn", "{{portfolioReturnPercent}} is a rounding error. The market is leaving you behind and you're cheering for crumbs."),
    ("BEST_ASSET", "The Only Survivor", "Every other decision you made was wrong, but thank God {{dailyBestAsset}} bailed you out. Pure luck."),
    ("WORST_ASSET", "Toxic Waste", "{{dailyWorstAsset}} is toxic waste in your portfolio. You are paying for the privilege of underperforming."),
    ("GENERAL_MARKET_CHAOS", "Saved By Beta", "You generated zero alpha. You were saved entirely by market beta, and you barely even captured that."),
    ("BENCHMARK_COMPARISON", "A Mathematical Insult", "Your {{portfolioReturnPercent}} return is a direct insult to the {{benchmarkReturnPercent}} return of {{benchmarkName}}. Liquidate and index."),
    ("RELATIVE_RETURN", "The Gap Of Shame", "You underperformed by {{relativePerformancePercent}}. Print that number out and frame it so you remember why you shouldn't pick stocks."),
    ("ABSOLUTE_RETURN", "Illusion Of Success", "You see green and think you won. The benchmark sees your {{portfolioReturnPercent}} and pities you."),
    ("BEST_ASSET", "Accidental Genius", "You probably misclicked when you bought {{dailyBestAsset}}. It's the only logical explanation for why it's in this dumpster fire of a portfolio."),
    ("WORST_ASSET", "The Wealth Destroyer", "{{dailyWorstAsset}} is systematically dismantling your net worth while the rest of the world gets rich."),
    ("GENERAL_MARKET_CHAOS", "A Rising Tide Lifts Even You", "The rising tide lifted your leaky rowboat. Don't confuse buoyancy with nautical skill."),
    ("BENCHMARK_COMPARISON", "Index Domination", "The index dominated you. {{benchmarkReturnPercent}} vs {{portfolioReturnPercent}}. It wasn't even a fair fight. You brought a knife to a nuke fight."),
    ("RELATIVE_RETURN", "Bleeding Out", "You are bleeding out at a rate of {{relativePerformancePercent}} per day. Soon there will be nothing left but index funds and regret."),
    ("ABSOLUTE_RETURN", "Worthless Gains", "Your {{portfolioReturnPercent}} gain is practically worthless when adjusted for the opportunity cost of not just buying the market."),
    ("BEST_ASSET", "The Backpack", "Your portfolio is a backpack filled with rocks, and {{dailyBestAsset}} is the only one trying to carry it up the mountain."),
    ("WORST_ASSET", "Deliberate Sabotage", "Holding {{dailyWorstAsset}} today is proof that you are subconsciously sabotaging your own financial future."),
    ("GENERAL_MARKET_CHAOS", "Carried By The Mob", "You didn't walk forward, you were carried by a mob of smarter investors pushing the market up."),
    ("BENCHMARK_COMPARISON", "The Incompetence Tax", "The difference between {{benchmarkReturnPercent}} and {{portfolioReturnPercent}} is the tax you pay for thinking you are a fund manager."),
    ("RELATIVE_RETURN", "Statistically Terrible", "Underperforming by {{relativePerformancePercent}} in a bull market is statistically difficult, yet you accomplished it with ease."),
    ("ABSOLUTE_RETURN", "Fake Green", "It's green, but it's a fake green. A hollow, underperforming green that tastes like failure."),
    ("BEST_ASSET", "One Lucky Dart", "You threw ten darts and one hit {{dailyBestAsset}}. The rest hit the wall. The benchmark hit the bullseye without trying."),
    ("WORST_ASSET", "The Anchor V2", "Cut the cord on {{dailyWorstAsset}} before it drags you to the bottom of a rising ocean."),
    ("GENERAL_MARKET_CHAOS", "Market Beta Bailout V2", "The market bailed you out. Next time it drops, you won't be so lucky with this allocation.")
]

for i, (angle, title, msg) in enumerate(brutal_jokes):
    templates.append({
        "templateId": f"both_positive_user_worse_v2_brutal_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_WORSE",
        "tone": "roast",
        "intensity": "brutal",
        "messageAngle": angle,
        "structureFamily": "BUG_REPORT",
        "metaphorCategory": "SOFTWARE",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive but underperformed the benchmark.",
        "suggestedFocusTemplate": "Sell everything and buy an ETF.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Degen (15)
degen_jokes = [
    ("BENCHMARK_COMPARISON", "Boomer Chad Index", "The boomer {{benchmarkName}} printed {{benchmarkReturnPercent}} while your degen bags only managed {{portfolioReturnPercent}}. Absolutely dusted."),
    ("RELATIVE_RETURN", "Leaking Alpha", "Trailing by {{relativePerformancePercent}} on a green day. You are leaking alpha faster than a rugged protocol."),
    ("ABSOLUTE_RETURN", "Smol Green Dildo", "Up {{portfolioReturnPercent}}. It's a green candle, but it's smol. We need gigacandles, anon."),
    ("BEST_ASSET", "One Coin Carry", "If {{dailyBestAsset}} hadn't pumped, you'd be eating ramen tonight. The rest of your bags are rekt."),
    ("WORST_ASSET", "Holding The Bag", "You are literally holding the {{dailyWorstAsset}} bag while the rest of the market goes to Valhalla. Drop it."),
    ("GENERAL_MARKET_CHAOS", "Up Only Market", "It's an up-only market and you managed to go up the least. Turn in your trading badge."),
    ("BENCHMARK_COMPARISON", "Index Maxxing Fails", "You tried to outsmart the market and got {{portfolioReturnPercent}}. The index maxis got {{benchmarkReturnPercent}}. Get flexed on."),
    ("RELATIVE_RETURN", "Skill Issue V2", "Underperforming by {{relativePerformancePercent}} is a massive skill issue. Have you considered flipping burgers instead?"),
    ("ABSOLUTE_RETURN", "WAGMI Eventually", "You gained {{portfolioReturnPercent}}. We're all gonna make it, but you are taking the slow lane."),
    ("BEST_ASSET", "Saved By The Pump", "{{dailyBestAsset}} pumped and saved your entire net worth from embarrassment. Say thank you."),
    ("WORST_ASSET", "Paper Hands Energy", "{{dailyWorstAsset}} has massive paper hands energy. It's holding your whole vibe back."),
    ("GENERAL_MARKET_CHAOS", "Ape Market", "The apes pushed the market up, and you barely caught a ride. Buy higher, sell lower."),
    ("BENCHMARK_COMPARISON", "Getting Ratioed", "Your {{portfolioReturnPercent}} just got ratioed by {{benchmarkName}}'s {{benchmarkReturnPercent}}. Delete your account."),
    ("RELATIVE_RETURN", "Opportunity Cost", "That {{relativePerformancePercent}} deficit is pure opportunity cost. You could have been early, instead you were wrong."),
    ("ABSOLUTE_RETURN", "Not Enough Leverage", "You only made {{portfolioReturnPercent}}. Clearly, you didn't use enough leverage. (This is a joke, please don't use more leverage).")
]

for i, (angle, title, msg) in enumerate(degen_jokes):
    templates.append({
        "templateId": f"both_positive_user_worse_v2_degen_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_WORSE",
        "tone": "mixed",
        "intensity": "degen",
        "messageAngle": angle,
        "structureFamily": "GAMING",
        "metaphorCategory": "GAMING",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive but underperformed the benchmark.",
        "suggestedFocusTemplate": "Stop trading and touch grass.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

import re
for t in templates:
    rd = set()
    for word in t["messageTemplate"].split():
        matches = re.findall(r'\{\{([^}]+)\}\}', word)
        for m in matches:
            rd.add(m)
    t["requiredData"] = list(rd)

with open('lambda/data/comments.txt', 'w') as f:
    json.dump(templates, f, indent=2)

print(f"Generated {len(templates)} templates and overwrote comments.txt")
