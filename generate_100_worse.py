import json
import os

templates = []

# Gentle (20)
gentle_jokes = [
    ("BENCHMARK_COMPARISON", "A Win Is A Win", "The portfolio managed {{portfolioReturnPercent}}, which is positive. The fact that {{benchmarkName}} did {{benchmarkReturnPercent}} just means there's a higher ceiling to aim for."),
    ("RELATIVE_RETURN", "Slightly Behind The Pace", "Up is up, even if you are {{relativePerformancePercent}} behind the pace car. Solid effort, just needs a tune-up."),
    ("ABSOLUTE_RETURN", "Green Ink Verified", "Positive territory at {{portfolioReturnPercent}}. We won't mention the broader market unless you want to use it as motivation."),
    ("BEST_ASSET", "Carrying The Baton", "{{dailyBestAsset}} put in a shift today. The rest of the portfolio was a bit shy compared to the benchmark, but progress is progress."),
    ("WORST_ASSET", "Minor Drag Identified", "A positive finish! It would have been closer to the benchmark's run if {{dailyWorstAsset}} hadn't taken a nap."),
    ("GENERAL_MARKET_CHAOS", "Riding The Wave Safely", "The market was broadly generous today. The portfolio caught some of the wave, even if it stayed closer to shore."),
    ("BENCHMARK_COMPARISON", "Good, But Not Index Good", "You made money! {{portfolioReturnPercent}} is a step forward. {{benchmarkName}} took a slightly larger step at {{benchmarkReturnPercent}}."),
    ("RELATIVE_RETURN", "Positive Gap", "Making money while trailing by {{relativePerformancePercent}} is still making money. The math is kind today."),
    ("ABSOLUTE_RETURN", "Quietly Gaining", "A calm {{portfolioReturnPercent}} gain. It doesn't break records compared to the index, but it doesn't break hearts either."),
    ("BEST_ASSET", "Heavy Lifting By One", "Grateful for {{dailyBestAsset}} keeping the portfolio green while the benchmark ran ahead."),
    ("WORST_ASSET", "Room For Improvement", "Green day secured. If we can get {{dailyWorstAsset}} to stop acting like an anchor, we might catch the benchmark next time."),
    ("GENERAL_MARKET_CHAOS", "Participation Ribbon", "The market handed out gains today. You collected your share, though some others grabbed a bit more. Still a good day!"),
    ("BENCHMARK_COMPARISON", "A Modest Slice", "{{benchmarkName}} served up {{benchmarkReturnPercent}}. Your slice was {{portfolioReturnPercent}}. Still delicious, just a smaller piece."),
    ("RELATIVE_RETURN", "Trailed But Thrived", "You survived the turbulence and ended green, trailing only by {{relativePerformancePercent}}. A safe and steady outcome."),
    ("ABSOLUTE_RETURN", "Upward Trajectory", "You are up {{portfolioReturnPercent}}. The index was louder about its success, but your account is still heavier than yesterday."),
    ("BEST_ASSET", "Star Player", "{{dailyBestAsset}} kept you in the positive column. The benchmark had a deeper bench today, but your star performed."),
    ("WORST_ASSET", "The Missing Link", "You still made money despite {{dailyWorstAsset}} dragging its feet. Imagine the returns when everyone cooperates!"),
    ("GENERAL_MARKET_CHAOS", "Gentle Tailwind", "The market winds were strong today. Your portfolio caught a nice gentle breeze."),
    ("BENCHMARK_COMPARISON", "Second Place Finish", "Second place to {{benchmarkName}} still means you crossed the finish line in the green. Well done."),
    ("RELATIVE_RETURN", "Respectable Distance", "Trailing by {{relativePerformancePercent}} on a green day is a luxury problem. Enjoy the gains.")
]

for i, (angle, title, msg) in enumerate(gentle_jokes):
    templates.append({
        "templateId": f"both_positive_user_worse_gentle_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_WORSE",
        "tone": "mixed",
        "intensity": "gentle",
        "messageAngle": angle,
        "structureFamily": "SPORTS_COMMENTARY",
        "metaphorCategory": "SPORTS",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive but underperformed the benchmark.",
        "suggestedFocusTemplate": "Look at assets holding back the overall positive trend.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Sarcastic (35)
sarcastic_jokes = [
    ("BENCHMARK_COMPARISON", "Technically Profitable", "Congratulations on your {{portfolioReturnPercent}} gain. {{benchmarkName}} did {{benchmarkReturnPercent}} with zero active management, but your buttons are very shiny."),
    ("RELATIVE_RETURN", "A Tax on Creativity", "You are underperforming a passive index by {{relativePerformancePercent}}. Think of it as a fee you pay for the illusion of control."),
    ("ABSOLUTE_RETURN", "A Win On Paper", "{{portfolioReturnPercent}} is mathematically a positive number. Please do not look at the benchmark if you wish to maintain your current mood."),
    ("BEST_ASSET", "One Good Decision", "{{dailyBestAsset}} did its best to hide your other decisions. The benchmark, meanwhile, required no decisions and still beat you."),
    ("WORST_ASSET", "Anchor Management", "You made money, miraculously, despite {{dailyWorstAsset}}. The benchmark did not have this specific self-sabotage."),
    ("GENERAL_MARKET_CHAOS", "Rising Tide, Leaky Boat", "The market tide lifted all boats. Yours just happened to have a small leak, hence the underperformance."),
    ("BENCHMARK_COMPARISON", "The Active Penalty", "You spent time researching, only to get {{portfolioReturnPercent}}. A dartboard and {{benchmarkName}} got {{benchmarkReturnPercent}}."),
    ("RELATIVE_RETURN", "Mathematically Slower", "You are up, but you are trailing by {{relativePerformancePercent}}. It's like winning a race where you were the only one walking."),
    ("ABSOLUTE_RETURN", "Lower Case Gains", "You achieved gains, but they must be written in lowercase letters so as not to offend the benchmark."),
    ("BEST_ASSET", "Hero Syndrome", "{{dailyBestAsset}} is carrying this portfolio like a substitute teacher on a Friday. The index is just relaxing."),
    ("WORST_ASSET", "A Heavy Backpack", "You finished green, but {{dailyWorstAsset}} made you work for it. The index travels light."),
    ("GENERAL_MARKET_CHAOS", "Accidental Success", "The market was so overwhelmingly positive today that even your portfolio accidentally made money."),
    ("BENCHMARK_COMPARISON", "Index Envy", "Your {{portfolioReturnPercent}} looks great until it stands next to {{benchmarkName}}'s {{benchmarkReturnPercent}}. Posture matters."),
    ("RELATIVE_RETURN", "A Polished Bronze", "Trailing by {{relativePerformancePercent}} in a bull run is a special kind of talent. But hey, bronze is still a medal."),
    ("ABSOLUTE_RETURN", "Positive But Pedantic", "{{portfolioReturnPercent}} up. The index is higher. You are technically wealthy, relatively speaking."),
    ("BEST_ASSET", "Lonely At The Top", "{{dailyBestAsset}} is doing the heavy lifting. The benchmark has a team. You have one tired employee."),
    ("WORST_ASSET", "Unnecessary Headwinds", "You deliberately held {{dailyWorstAsset}} and still made money. The market is very forgiving today."),
    ("GENERAL_MARKET_CHAOS", "Market Beta Bailout", "You didn't beat the market, the market beat you with money. Accept the bailout."),
    ("BENCHMARK_COMPARISON", "A Study In Suboptimality", "{{benchmarkName}} delivered {{benchmarkReturnPercent}}. You curated your way to {{portfolioReturnPercent}}. Art takes time, clearly."),
    ("RELATIVE_RETURN", "The Gap Of Pride", "That {{relativePerformancePercent}} gap is the exact cost of your personal market thesis today."),
    ("ABSOLUTE_RETURN", "Green Is Green", "You are green. The benchmark is neon green. You are basically wearing camouflage at a rave."),
    ("BEST_ASSET", "Asymmetric Effort", "Thank {{dailyBestAsset}} for the positive day. The benchmark didn't try this hard and still won."),
    ("WORST_ASSET", "The Slower Gazelle", "{{dailyWorstAsset}} ensured you were the slowest gazelle today. Fortunately, there were no lions, just a very fast benchmark."),
    ("GENERAL_MARKET_CHAOS", "A Rising Tide Lifts Everything", "Even portfolios with questionable asset allocation went up today. Congratulations on being part of 'everything'."),
    ("BENCHMARK_COMPARISON", "Passive Aggressive", "A passive strategy would have yielded {{benchmarkReturnPercent}}. Your active strategy yielded {{portfolioReturnPercent}}. The math is gently judging you."),
    ("RELATIVE_RETURN", "Margin of Error", "You underperformed by {{relativePerformancePercent}}. In science, that's a margin of error. In finance, it's just an error."),
    ("ABSOLUTE_RETURN", "Small Victories", "{{portfolioReturnPercent}} is a victory. The index had a parade, but your small gathering was nice too."),
    ("BEST_ASSET", "One Atlas", "{{dailyBestAsset}} holding up the world while the benchmark just floated away effortlessly."),
    ("WORST_ASSET", "Self-Imposed Friction", "You would have matched the market if you hadn't insisted on owning {{dailyWorstAsset}}."),
    ("GENERAL_MARKET_CHAOS", "Gravity Denied", "The market went up so hard it pulled your portfolio with it, despite its best efforts to remain grounded."),
    ("BENCHMARK_COMPARISON", "An Expensive Hobby", "Stock picking gave you {{portfolioReturnPercent}}. Doing nothing gave {{benchmarkName}} {{benchmarkReturnPercent}}. Hobbies are supposed to cost money."),
    ("RELATIVE_RETURN", "The Scenic Route", "You took the scenic route to profits, trailing the direct path by {{relativePerformancePercent}}."),
    ("ABSOLUTE_RETURN", "Faint Applause", "Please accept this slow, quiet golf clap for your {{portfolioReturnPercent}} gain."),
    ("BEST_ASSET", "The Carry Job", "Without {{dailyBestAsset}}, this would have been a very different, much more awkward conversation."),
    ("WORST_ASSET", "Dead Weight", "You dragged {{dailyWorstAsset}} across the finish line. The benchmark simply took an Uber.")
]

for i, (angle, title, msg) in enumerate(sarcastic_jokes):
    templates.append({
        "templateId": f"both_positive_user_worse_sarcastic_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_WORSE",
        "tone": "roast",
        "intensity": "sarcastic",
        "messageAngle": angle,
        "structureFamily": "ACADEMIC_REVIEW",
        "metaphorCategory": "ACADEMIA",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive but underperformed the benchmark.",
        "suggestedFocusTemplate": "Stop picking stocks and buy the index.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Brutal (30)
brutal_jokes = [
    ("BENCHMARK_COMPARISON", "Outsmarted By A Spreadsheet", "You spent hours agonizing over charts to get {{portfolioReturnPercent}}. A literal unfeeling formula called {{benchmarkName}} did {{benchmarkReturnPercent}}. Rest well."),
    ("RELATIVE_RETURN", "The Cost Of Hubris", "You paid a {{relativePerformancePercent}} tax on your own arrogance today. A dead monkey throwing darts would have matched the index."),
    ("ABSOLUTE_RETURN", "A Pity Profit", "You are up {{portfolioReturnPercent}}. It's the market's equivalent of a participation trophy handed to the slowest runner."),
    ("BEST_ASSET", "One Hostage Survived", "{{dailyBestAsset}} managed to escape the gravity of your terrible decision-making, keeping the portfolio barely green."),
    ("WORST_ASSET", "A Masterclass In Drag", "The market sprinted. You tied {{dailyWorstAsset}} to your ankle and jogged. Truly breathtaking self-sabotage."),
    ("GENERAL_MARKET_CHAOS", "Idiot-Proof Market", "Today was so aggressively bullish that literally any random assortment of assets went up. You simply found the slowest ones."),
    ("BENCHMARK_COMPARISON", "The Alpha Illusion", "{{benchmarkName}} got {{benchmarkReturnPercent}}. You got {{portfolioReturnPercent}}. Please update your LinkedIn bio to remove 'Investor'."),
    ("RELATIVE_RETURN", "Subsidized Ego", "Trailing the market by {{relativePerformancePercent}} on a green day is how the universe reminds you that you are not the main character."),
    ("ABSOLUTE_RETURN", "Crumbs From The Table", "The market feasted. You scraped {{portfolioReturnPercent}} off the floor and called it a meal."),
    ("BEST_ASSET", "Back Pain", "{{dailyBestAsset}} requires immediate medical attention after carrying the dead weight of your other holdings today."),
    ("WORST_ASSET", "Financial Masochism", "You could have just bought the index. Instead, you bought {{dailyWorstAsset}} because you enjoy suffering, even on green days."),
    ("GENERAL_MARKET_CHAOS", "Saved By The Bell", "You didn't generate alpha. You generated beta, and barely enough of it to avoid a margin call. You're welcome."),
    ("BENCHMARK_COMPARISON", "Statistically Insignificant", "Your {{portfolioReturnPercent}} is a rounding error on {{benchmarkName}}'s {{benchmarkReturnPercent}} gain. You are a rounding error."),
    ("RELATIVE_RETURN", "The Lagging Indicator", "If we want to know what the market did yesterday, we'll look at your portfolio today. Trailing by {{relativePerformancePercent}} is an art form."),
    ("ABSOLUTE_RETURN", "Micro-Gains", "You made {{portfolioReturnPercent}}. Try not to spend it all on the electricity it took to load this dashboard."),
    ("BEST_ASSET", "Accidental Brilliance", "You bought {{dailyBestAsset}} by mistake, didn't you? It's the only reason you aren't negative right now."),
    ("WORST_ASSET", "Dead Inside", "{{dailyWorstAsset}} is rotting in your portfolio, stinking up what would have otherwise been a perfectly decent market day."),
    ("GENERAL_MARKET_CHAOS", "A Rising Tide Lifts Even Garbage", "The market surged. Your portfolio floated up slightly, mostly because it's buoyant, not because it's seaworthy."),
    ("BENCHMARK_COMPARISON", "Passive Aggression", "Doing nothing: {{benchmarkReturnPercent}}. Your 'strategy': {{portfolioReturnPercent}}. Have you considered doing nothing? Forever?"),
    ("RELATIVE_RETURN", "Bleeding Alpha", "You are hemorrhaging alpha at a rate of {{relativePerformancePercent}} per day. A tourniquet of index funds is required."),
    ("ABSOLUTE_RETURN", "A Green Illusion", "It's green, but we both know it's a failure. {{portfolioReturnPercent}} is the color of disappointment disguised as success."),
    ("BEST_ASSET", "The Lone Survivor", "{{dailyBestAsset}} survived the massacre of your terrible asset allocation. Salute it."),
    ("WORST_ASSET", "Anchor In A Bull Market", "The market tried to hand you money. You used {{dailyWorstAsset}} to block it. Incredible defense."),
    ("GENERAL_MARKET_CHAOS", "Unearned Arrogance", "You will probably brag about today's gains to your friends, completely omitting how badly you trailed the index. We know the truth."),
    ("BENCHMARK_COMPARISON", "The Dunning-Kruger Portfolio", "You thought you could beat {{benchmarkName}}. It returned {{benchmarkReturnPercent}}. You returned {{portfolioReturnPercent}}. The chart speaks for itself."),
    ("RELATIVE_RETURN", "Negative Edge", "Your trading edge is currently negative {{relativePerformancePercent}}. You would literally make more money by doing the opposite of your instincts."),
    ("ABSOLUTE_RETURN", "Pennies On The Dollar", "The index minted dollars today. You picked up pennies in front of a steamroller that happened to be parked."),
    ("BEST_ASSET", "Atlas Shrugged", "{{dailyBestAsset}} can only carry you so far before it realizes you are dead weight."),
    ("WORST_ASSET", "The Leak", "Your portfolio is a bucket. {{dailyWorstAsset}} is a massive hole. You are standing under a waterfall of market gains, holding a sieve."),
    ("GENERAL_MARKET_CHAOS", "Beta Cuck", "You relied entirely on the market's momentum to save you from your own stock picking. And it barely worked.")
]

for i, (angle, title, msg) in enumerate(brutal_jokes):
    templates.append({
        "templateId": f"both_positive_user_worse_brutal_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_WORSE",
        "tone": "roast",
        "intensity": "brutal",
        "messageAngle": angle,
        "structureFamily": "COURTROOM_VERDICT",
        "metaphorCategory": "BUREAUCRACY",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive but underperformed the benchmark.",
        "suggestedFocusTemplate": "Liquidate and buy an index fund before you hurt yourself.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Degen (15)
degen_jokes = [
    ("BENCHMARK_COMPARISON", "Boomer Rock Outperformed", "You really let {{benchmarkName}} do {{benchmarkReturnPercent}} while your bags only printed {{portfolioReturnPercent}}? The index boomers are laughing at us."),
    ("RELATIVE_RETURN", "Ngmi With That Alpha", "Trailing the timeline by {{relativePerformancePercent}} on a green day. The meme coins are disappointed in your lack of leverage."),
    ("ABSOLUTE_RETURN", "Green Candles, Weak Hands", "Up {{portfolioReturnPercent}}. Nice green dildo, but the index had a bigger one. Hit the gym."),
    ("BEST_ASSET", "One Coin Carrying", "Thank the simulation for {{dailyBestAsset}} pumping. The rest of your wallet is basically a stablecoin on a bull day."),
    ("WORST_ASSET", "Rekt By One Bag", "You survived the chop, but holding {{dailyWorstAsset}} while the market moons is criminal behavior."),
    ("GENERAL_MARKET_CHAOS", "Ape Relief", "Apes together strong. The market pumped, you got a crumb. Buy higher next time."),
    ("BENCHMARK_COMPARISON", "Chad Index Vs Virgin Portfolio", "The Chad {{benchmarkName}} gigapumped {{benchmarkReturnPercent}}. Your virgin bag squeezed out {{portfolioReturnPercent}}. Tragic."),
    ("RELATIVE_RETURN", "Leaking Sats", "You are bleeding {{relativePerformancePercent}} in opportunity cost. The laser eyes are fading."),
    ("ABSOLUTE_RETURN", "Smol Gains", "{{portfolioReturnPercent}} is cute. It's green, but it won't buy a Lambo. Maybe a nice Honda Civic."),
    ("BEST_ASSET", "To The Moon (Slightly)", "{{dailyBestAsset}} tried to take you to the moon, but your overall portfolio barely made it to low earth orbit."),
    ("WORST_ASSET", "Paper Handed Drag", "{{dailyWorstAsset}} acting like absolute dead weight while the timeline celebrates. Drop the bags."),
    ("GENERAL_MARKET_CHAOS", "Up Only (Mostly)", "Market went up only mode. You went up slightly mode. Turn on the monitor."),
    ("BENCHMARK_COMPARISON", "Index Maxxing", "{{benchmarkName}} maxxing would have yielded {{benchmarkReturnPercent}}. You got {{portfolioReturnPercent}} by galaxy-braining it."),
    ("RELATIVE_RETURN", "Skill Issue", "Trailing the pump by {{relativePerformancePercent}} is a certified skill issue. git gud."),
    ("ABSOLUTE_RETURN", "WAGMI (Barely)", "We are all gonna make it, but with {{portfolioReturnPercent}} gains, you're gonna make it very slowly.")
]

for i, (angle, title, msg) in enumerate(degen_jokes):
    templates.append({
        "templateId": f"both_positive_user_worse_degen_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_WORSE",
        "tone": "mixed",
        "intensity": "degen",
        "messageAngle": angle,
        "structureFamily": "GAMING",
        "metaphorCategory": "GAMING",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive but underperformed the benchmark.",
        "suggestedFocusTemplate": "Stop galaxy-braining and ride the trend.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Clean required data fields (remove punctuation from matches)
import re
for t in templates:
    rd = set()
    for word in t["messageTemplate"].split():
        matches = re.findall(r'\{\{([^}]+)\}\}', word)
        for m in matches:
            rd.add(m)
    t["requiredData"] = list(rd)

with open('lambda/data/comments.txt', 'a') as f:
    f.write('\n\n')
    json.dump(templates, f, indent=2)

print(f"Generated {len(templates)} templates and appended to comments.txt")
