import json
import re

templates = []

# Gentle (25)
gentle_jokes = [
    ("BENCHMARK_COMPARISON", "A Step Ahead", "You finished ahead of {{benchmarkName}} today. {{portfolioReturnPercent}} is a great result compared to their {{benchmarkReturnPercent}}."),
    ("RELATIVE_RETURN", "Positive Momentum", "A {{relativePerformancePercent}} lead over the market shows your portfolio is well-positioned for these conditions."),
    ("ABSOLUTE_RETURN", "Steady Growth", "Securing {{portfolioReturnPercent}} in profit today is exactly the kind of steady growth we like to see."),
    ("BEST_ASSET", "Leading The Way", "{{dailyBestAsset}} really led the way today, pushing your portfolio into outperformance territory."),
    ("GENERAL_MARKET_CHAOS", "Riding High", "You rode the market's positive momentum perfectly today and even managed to pull ahead."),
    ("BENCHMARK_COMPARISON", "Beating The Average", "The average return was {{benchmarkReturnPercent}}, but you achieved {{portfolioReturnPercent}}. Nice work beating the baseline."),
    ("RELATIVE_RETURN", "A Clear Advantage", "You held a {{relativePerformancePercent}} advantage today. It's always nice to see the numbers validate your strategy."),
    ("ABSOLUTE_RETURN", "Building Wealth", "Every {{portfolioReturnPercent}} day is another brick in the wall of your financial goals."),
    ("BEST_ASSET", "The Catalyst", "We can point to {{dailyBestAsset}} as the main catalyst for today's successful outperformance."),
    ("GENERAL_MARKET_CHAOS", "Market Outlier", "In a broadly positive market, being a positive outlier is exactly what you want."),
    ("BENCHMARK_COMPARISON", "A Healthy Margin", "You beat {{benchmarkName}} by a healthy margin today. {{portfolioReturnPercent}} looks great on the dashboard."),
    ("RELATIVE_RETURN", "Creating Space", "Creating a {{relativePerformancePercent}} gap between you and the index requires good execution. Well done."),
    ("ABSOLUTE_RETURN", "A Green Day", "A perfectly green day with {{portfolioReturnPercent}} to show for it. No complaints here."),
    ("BEST_ASSET", "Strong Conviction", "Your conviction in {{dailyBestAsset}} paid off today, lifting the whole portfolio."),
    ("GENERAL_MARKET_CHAOS", "Smooth Sailing", "The market provided the wind, and you navigated perfectly to capture it all."),
    ("BENCHMARK_COMPARISON", "Exceeding The Standard", "{{benchmarkName}} sets the standard, and your {{portfolioReturnPercent}} exceeded it today."),
    ("RELATIVE_RETURN", "A Measurable Win", "Outperforming by {{relativePerformancePercent}} is a measurable win that you should be happy with."),
    ("ABSOLUTE_RETURN", "Progress Achieved", "You achieved {{portfolioReturnPercent}} progress today. Slow and steady, or fast and steady, it's all good."),
    ("BEST_ASSET", "The Anchor In Reverse", "Instead of dragging you down, {{dailyBestAsset}} pulled you up and over the benchmark line."),
    ("GENERAL_MARKET_CHAOS", "Capturing The Upside", "You successfully captured the market upside and then some. A very productive session."),
    ("BENCHMARK_COMPARISON", "The Better Choice", "Your choices yielded {{portfolioReturnPercent}}, while the default choice yielded {{benchmarkReturnPercent}}. You chose well today."),
    ("RELATIVE_RETURN", "A Welcome Boost", "That extra {{relativePerformancePercent}} is a welcome boost to your long-term averages."),
    ("ABSOLUTE_RETURN", "Positive Reinforcement", "Let {{portfolioReturnPercent}} serve as positive reinforcement for your current strategy."),
    ("BEST_ASSET", "Highlight Of The Day", "The highlight of the day was definitely {{dailyBestAsset}}, which drove your outperformance."),
    ("GENERAL_MARKET_CHAOS", "Above The Fray", "The market was noisy and green, but you rose slightly above the fray for the win.")
]

for i, (angle, title, msg) in enumerate(gentle_jokes):
    templates.append({
        "templateId": f"both_positive_user_better_v2_gentle_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_BETTER",
        "tone": "praise",
        "intensity": "gentle",
        "messageAngle": angle,
        "structureFamily": "STATUS_UPDATE",
        "metaphorCategory": "OFFICE",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive and outperformed the benchmark.",
        "suggestedFocusTemplate": "Maintain discipline and don't get complacent.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Sarcastic (35)
sarcastic_jokes = [
    ("BENCHMARK_COMPARISON", "The Unthinkable Happened", "You achieved {{portfolioReturnPercent}} while {{benchmarkName}} only managed {{benchmarkReturnPercent}}. We are currently reviewing the logs for errors."),
    ("RELATIVE_RETURN", "A Temporary Anomaly", "Enjoy your {{relativePerformancePercent}} outperformance. We assume this anomaly will correct itself by tomorrow morning."),
    ("ABSOLUTE_RETURN", "Mildly Impressive", "You gained {{portfolioReturnPercent}}. It is mildly impressive, like watching a toddler successfully use a spoon."),
    ("BEST_ASSET", "Carried By Luck", "We all know {{dailyBestAsset}} is the only reason you beat the market today. Try to act like it was on purpose."),
    ("GENERAL_MARKET_CHAOS", "A Rising Tide Lifts Everything", "You didn't beat the market through skill, the market was just so buoyant it accidentally lifted you higher."),
    ("BENCHMARK_COMPARISON", "The Spreadsheet Is Confused", "The spreadsheet is very confused as to how your {{portfolioReturnPercent}} is higher than {{benchmarkReturnPercent}}. We are restarting the system."),
    ("RELATIVE_RETURN", "An Accidental Edge", "You found a {{relativePerformancePercent}} edge today. Please be careful with it, it looks sharp."),
    ("ABSOLUTE_RETURN", "Green Numbers Detected", "Sensors indicate a {{portfolioReturnPercent}} gain. We will monitor the situation closely to ensure you don't ruin it."),
    ("BEST_ASSET", "The Golden Ticket", "You held {{dailyBestAsset}} and it actually went up. Lightning rarely strikes twice, so be warned."),
    ("GENERAL_MARKET_CHAOS", "Beta Masquerading As Alpha V2", "You rode the market wave and called it alpha. We will let you have this illusion for today."),
    ("BENCHMARK_COMPARISON", "Beating The Robot", "You beat the passive {{benchmarkName}} algorithm today with {{portfolioReturnPercent}}. John Connor would be proud."),
    ("RELATIVE_RETURN", "A Statistical Fluke", "A {{relativePerformancePercent}} outperformance is well within the margin of error for a statistical fluke. Keep your ego in check."),
    ("ABSOLUTE_RETURN", "Acceptable Output V2", "Your {{portfolioReturnPercent}} return is acceptable. We expected worse, frankly."),
    ("BEST_ASSET", "The Lone Contributor", "Without {{dailyBestAsset}}, you would be trailing the index right now. Send it some flowers."),
    ("GENERAL_MARKET_CHAOS", "Chaos Beneficiary", "You are the prime beneficiary of today's market chaos. Do not mistake this for a repeatable strategy."),
    ("BENCHMARK_COMPARISON", "The Rare Exception", "Usually {{benchmarkName}} wins. Today, your {{portfolioReturnPercent}} is the rare exception that proves the rule."),
    ("RELATIVE_RETURN", "A Margin Of Luck", "You call it outperformance, we call it a {{relativePerformancePercent}} margin of luck. Tomato, tomahto."),
    ("ABSOLUTE_RETURN", "Profit Registered", "Profit of {{portfolioReturnPercent}} registered. The algorithm is displeased by your success but accepts the data."),
    ("BEST_ASSET", "Heavy Lifting Noticed", "We noticed {{dailyBestAsset}} doing all the heavy lifting today while your other assets took a coffee break."),
    ("GENERAL_MARKET_CHAOS", "Surviving The Pump", "You survived the market pump and came out ahead. Try not to let this rare victory ruin your humility."),
    ("BENCHMARK_COMPARISON", "Index Humiliated (Slightly)", "You slightly humiliated {{benchmarkName}} today with your {{portfolioReturnPercent}} return. It will seek revenge tomorrow."),
    ("RELATIVE_RETURN", "The Gap Of Arrogance", "That {{relativePerformancePercent}} gap is exactly how much more arrogant you will be at dinner tonight."),
    ("ABSOLUTE_RETURN", "A Non-Negative Result", "{{portfolioReturnPercent}} is a non-negative result. That is the highest praise we are authorized to give."),
    ("BEST_ASSET", "The Savior Complex", "{{dailyBestAsset}} saved your portfolio today. Do not develop a savior complex, you just got lucky."),
    ("GENERAL_MARKET_CHAOS", "Floating Slightly Higher", "In a sea of green, you managed to float slightly higher than the rest of the garbage. Well done."),
    ("BENCHMARK_COMPARISON", "The Passive Defeat", "You defeated the passive index. {{portfolioReturnPercent}} vs {{benchmarkReturnPercent}}. The index does not care, but you seem very happy."),
    ("RELATIVE_RETURN", "A Measurable Anomaly", "We have measured a {{relativePerformancePercent}} anomaly in your favor. Enjoy it while the simulation allows it."),
    ("ABSOLUTE_RETURN", "Wealth Accrued", "Wealth of {{portfolioReturnPercent}} has been accrued. We are as surprised as you are."),
    ("BEST_ASSET", "The Outlier", "{{dailyBestAsset}} is a statistical outlier in your otherwise mediocre portfolio. We respect its effort."),
    ("GENERAL_MARKET_CHAOS", "Bull Market Participation", "You participated in the bull market and actually took home more than your fair share. The SEC has been notified."),
    ("BENCHMARK_COMPARISON", "A Minor Miracle", "It's a minor miracle that your {{portfolioReturnPercent}} beat {{benchmarkName}}. We suggest cashing out and moving to a farm."),
    ("RELATIVE_RETURN", "The Spread Of Hubris", "Your {{relativePerformancePercent}} spread over the market is pure fuel for your future hubris."),
    ("ABSOLUTE_RETURN", "A Plus Sign", "There is a plus sign next to your {{portfolioReturnPercent}} return. We double-checked the math, it appears to be correct."),
    ("BEST_ASSET", "The Carry Job V2", "We acknowledge the carry job performed by {{dailyBestAsset}} today. The rest of the portfolio should be ashamed."),
    ("GENERAL_MARKET_CHAOS", "Accidental Genius V2", "You accidentally outperformed the market. We will file this under 'Unexplained Phenomena'.")
]

for i, (angle, title, msg) in enumerate(sarcastic_jokes):
    templates.append({
        "templateId": f"both_positive_user_better_v2_sarcastic_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_BETTER",
        "tone": "mixed",
        "intensity": "sarcastic",
        "messageAngle": angle,
        "structureFamily": "INCIDENT_REPORT",
        "metaphorCategory": "BUREAUCRACY",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive and outperformed the benchmark.",
        "suggestedFocusTemplate": "Do not let this go to your head.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Brutal (25)
brutal_jokes = [
    ("BENCHMARK_COMPARISON", "System Error", "You beat {{benchmarkName}} by logging {{portfolioReturnPercent}}. This is clear evidence that the universe has stopped making sense and entropy is accelerating."),
    ("RELATIVE_RETURN", "The Luck Tax", "You outperformed by {{relativePerformancePercent}}. Enjoy it, because the market will inevitably tax this luck back with interest very soon."),
    ("ABSOLUTE_RETURN", "Undeserved Gains", "You are up {{portfolioReturnPercent}}. We both know you don't deserve this, but the market is occasionally generous to the undeserving."),
    ("BEST_ASSET", "Saved By One Bet", "If you hadn't blindly stumbled into holding {{dailyBestAsset}}, you would have underperformed. Your entire strategy is just closing your eyes and hoping."),
    ("GENERAL_MARKET_CHAOS", "The Idiot's Bull Market", "This is an idiot's bull market, and you are currently its king. You outperformed everyone by doing absolutely nothing intelligent."),
    ("BENCHMARK_COMPARISON", "A Mathematical Insult V2", "Your {{portfolioReturnPercent}} beat {{benchmarkName}}'s {{benchmarkReturnPercent}}. The fact that your chaotic button mashing beat a highly optimized index is insulting to finance."),
    ("RELATIVE_RETURN", "Statistical Noise V2", "That {{relativePerformancePercent}} lead is just statistical noise. Do not write a newsletter, do not launch a fund, just stay quiet and be grateful."),
    ("ABSOLUTE_RETURN", "The Illusion Of Skill", "A {{portfolioReturnPercent}} gain gives you the illusion of skill. It is a very dangerous illusion that usually ends in tears."),
    ("BEST_ASSET", "The Lottery Winner", "You picked {{dailyBestAsset}} and it went up. You are basically a lottery winner bragging about your 'number selection strategy'."),
    ("GENERAL_MARKET_CHAOS", "Surfing A Tsunami V2", "You outperformed during a market tsunami. A dead fish can also surf a tsunami. Keep that in mind."),
    ("BENCHMARK_COMPARISON", "The Passive Defeat V2", "You beat the passive {{benchmarkName}}. Enjoy your {{portfolioReturnPercent}}. The index will outlive you, out-earn you, and never feel stress."),
    ("RELATIVE_RETURN", "The Hubris Premium", "You earned a {{relativePerformancePercent}} premium today. We will watch with great interest as you give it all back trying to 'double down'."),
    ("ABSOLUTE_RETURN", "Unbearable Competence", "You made {{portfolioReturnPercent}}. I am forced to acknowledge your competence today, and it is ruining my entire day."),
    ("BEST_ASSET", "The Backpack Of Shame V2", "You shoved {{dailyBestAsset}} into your portfolio and let it drag your terrible ideas across the finish line. Don't pretend you planned this."),
    ("GENERAL_MARKET_CHAOS", "Beta Masquerading As Alpha V3", "You got swept up in a massive rally and think you generated alpha. You are just a passenger on a very fast train."),
    ("BENCHMARK_COMPARISON", "A Terrible Precedent V2", "By beating {{benchmarkName}} with a {{portfolioReturnPercent}} return, you have learned nothing. Success is a terrible teacher."),
    ("RELATIVE_RETURN", "The Pride Before The Fall V2", "You are up {{relativePerformancePercent}}. The hubris is intoxicating, isn't it? The market is already preparing its humbling mechanism."),
    ("ABSOLUTE_RETURN", "A Pity Profit V2", "You made {{portfolioReturnPercent}}. It's a pity profit from a market that feels sorry for your long-term returns."),
    ("BEST_ASSET", "The Lone Survivor V2", "Everything else you own is trash, but {{dailyBestAsset}} survived the dumpster fire to give you a positive day."),
    ("GENERAL_MARKET_CHAOS", "The Lucky Fool V2", "You are the definition of a lucky fool today. You outperformed the chaos by pure, unadulterated chance."),
    ("BENCHMARK_COMPARISON", "Humiliating The Index V2", "You got {{portfolioReturnPercent}} while {{benchmarkName}} got {{benchmarkReturnPercent}}. Passive investors everywhere just felt a disturbance in the force."),
    ("RELATIVE_RETURN", "The Gap Of Shame V2", "You beat the market by {{relativePerformancePercent}}. Print that number out and frame it, because you won't see it again for a decade."),
    ("ABSOLUTE_RETURN", "The Illusory Gain V2", "Your {{portfolioReturnPercent}} gain is illusory. It will vanish the moment you try to apply this 'strategy' in a bear market."),
    ("BEST_ASSET", "The One-Trick Pony V2", "Your entire net worth rests on {{dailyBestAsset}}. You aren't an investor, you're a hostage to one ticker."),
    ("GENERAL_MARKET_CHAOS", "A Rising Tide Lifts Garbage V2", "The rising tide lifted your leaky rowboat faster than the yachts today. Don't confuse buoyancy with nautical skill.")
]

for i, (angle, title, msg) in enumerate(brutal_jokes):
    templates.append({
        "templateId": f"both_positive_user_better_v2_brutal_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_BETTER",
        "tone": "mixed",
        "intensity": "brutal",
        "messageAngle": angle,
        "structureFamily": "COURTROOM_VERDICT",
        "metaphorCategory": "BUREAUCRACY",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive and outperformed the benchmark.",
        "suggestedFocusTemplate": "Do not let this go to your head.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Degen (15)
degen_jokes = [
    ("BENCHMARK_COMPARISON", "Dunking On Boomers", "You literally dunked on {{benchmarkName}} today. {{portfolioReturnPercent}} vs {{benchmarkReturnPercent}}. The tradfi boomers are in shambles."),
    ("RELATIVE_RETURN", "Gigabrain Alpha", "You printed {{relativePerformancePercent}} of pure gigabrain alpha. You are the chosen one of the timeline today."),
    ("ABSOLUTE_RETURN", "Massive Green Dildo", "A massive {{portfolioReturnPercent}} green candle right in the timeline's face. We are all gonna make it."),
    ("BEST_ASSET", "To Valhalla", "{{dailyBestAsset}} took you straight to Valhalla today. The rest of the market is eating your dust."),
    ("GENERAL_MARKET_CHAOS", "Ape King", "You are the Ape King today. The market pumped, and you pumped the hardest. Pure degenerate outperformance."),
    ("BENCHMARK_COMPARISON", "Dusting The Suits", "You dusted the suits at {{benchmarkName}} today. {{portfolioReturnPercent}} is a flex. Keep posting those Ws."),
    ("RELATIVE_RETURN", "Squeezing The Bears", "You beat the market by {{relativePerformancePercent}}. You are single-handedly liquidating every bear on the timeline."),
    ("ABSOLUTE_RETURN", "Printing Unlimited Tendies", "The money printer is running hot and it's pointing directly at your wallet. {{portfolioReturnPercent}} in pure tendies."),
    ("BEST_ASSET", "Diamond Hands Flex", "You diamond handed {{dailyBestAsset}} and it rewarded you with absolute outperformance. Maximum respect."),
    ("GENERAL_MARKET_CHAOS", "Surfing The Megapump", "You surfed the absolute crest of the megapump today. A masterclass in degenerate timing."),
    ("BENCHMARK_COMPARISON", "Chad Index Defeated", "You defeated the Chad {{benchmarkName}} today. {{portfolioReturnPercent}} is a certified W."),
    ("RELATIVE_RETURN", "Generational Alpha", "A {{relativePerformancePercent}} outperformance. You are one step closer to buying the citadel."),
    ("ABSOLUTE_RETURN", "Green Candles Only", "Up {{portfolioReturnPercent}}. We only know green candles today. The vibes are immaculate."),
    ("BEST_ASSET", "The God Candle V2", "{{dailyBestAsset}} printed a god candle and carried your entire net worth. Say thank you to the devs."),
    ("GENERAL_MARKET_CHAOS", "Ape Evolution V2", "You evolved into the ultimate gigabrain ape today by outperforming the entire casino. WAGMI.")
]

for i, (angle, title, msg) in enumerate(degen_jokes):
    templates.append({
        "templateId": f"both_positive_user_better_v2_degen_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_BETTER",
        "tone": "praise",
        "intensity": "degen",
        "messageAngle": angle,
        "structureFamily": "ACHIEVEMENT_UNLOCKED",
        "metaphorCategory": "GAMING",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive and outperformed the benchmark.",
        "suggestedFocusTemplate": "Keep printing, anon.",
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

print(f"Generated {len(templates)} templates for BOTH_POSITIVE_USER_BETTER (V2) and overwrote comments.txt")
