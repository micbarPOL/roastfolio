import json
import re

templates = []

# Gentle (25)
gentle_jokes = [
    ("BENCHMARK_COMPARISON", "A Rare Outperformance", "You actually outpaced {{benchmarkName}} today. {{portfolioReturnPercent}} is a genuinely solid outcome compared to the market's {{benchmarkReturnPercent}}."),
    ("RELATIVE_RETURN", "Ahead Of The Curve", "Securing a {{relativePerformancePercent}} lead over the index is commendable. It seems the strategy is functioning as intended."),
    ("ABSOLUTE_RETURN", "Green And Growing", "A {{portfolioReturnPercent}} gain is excellent. We are reluctantly impressed by this display of competence."),
    ("BEST_ASSET", "The Star Player", "With {{dailyBestAsset}} leading the charge, you navigated the market conditions beautifully."),
    ("GENERAL_MARKET_CHAOS", "Navigating The Green", "The market was positive, but you were even more positive. It is a strange feeling, but you should enjoy it."),
    ("BENCHMARK_COMPARISON", "Exceeding Expectations", "We expected you to trail {{benchmarkName}}, but your {{portfolioReturnPercent}} handily beat its {{benchmarkReturnPercent}}. Well done."),
    ("RELATIVE_RETURN", "A Comfortable Margin", "Beating the market by {{relativePerformancePercent}} is a sign of good positioning today. Keep up the rational behavior."),
    ("ABSOLUTE_RETURN", "Quiet Competence", "Ending the day up {{portfolioReturnPercent}} shows a surprising level of stability. Good job."),
    ("BEST_ASSET", "A Heavy Lifter", "{{dailyBestAsset}} did exactly what you hoped it would do. Sometimes the plan actually works."),
    ("GENERAL_MARKET_CHAOS", "Rising Above", "Everyone made money today, but you managed to make slightly more. A rare and pleasant anomaly."),
    ("BENCHMARK_COMPARISON", "The Upper Hand", "Taking the upper hand against {{benchmarkName}} isn't easy, yet your {{portfolioReturnPercent}} proves it happened."),
    ("RELATIVE_RETURN", "Positive Alpha", "That {{relativePerformancePercent}} advantage is exactly why you manage your own money. Try to do it again tomorrow."),
    ("ABSOLUTE_RETURN", "Satisfactory Results", "A return of {{portfolioReturnPercent}} meets all our rigorous standards for not being terrible. Seriously, great work."),
    ("BEST_ASSET", "Brilliant Selection", "Your decision to hold {{dailyBestAsset}} paid off perfectly today. It's almost like you knew what you were doing."),
    ("GENERAL_MARKET_CHAOS", "Sailing Ahead", "The rising tide lifted you faster than the rest of the fleet. Enjoy the view from the front."),
    ("BENCHMARK_COMPARISON", "A Statistical Victory", "Statistically speaking, beating {{benchmarkName}}'s {{benchmarkReturnPercent}} is a solid win. You should be proud."),
    ("RELATIVE_RETURN", "Padding The Lead", "A {{relativePerformancePercent}} outperformance is a great way to build a buffer for the inevitable red days."),
    ("ABSOLUTE_RETURN", "Green Checkmark", "Task failed successfully. You aimed for {{portfolioReturnPercent}} and actually hit it."),
    ("BEST_ASSET", "The Right Choice", "Selecting {{dailyBestAsset}} was a stroke of genius, or at least very good luck. We'll give you the credit this time."),
    ("GENERAL_MARKET_CHAOS", "Outrunning The Pack", "In a market full of winners, you managed to run just a little bit faster than the crowd."),
    ("BENCHMARK_COMPARISON", "Index Defeated", "You defeated the index today. Your {{portfolioReturnPercent}} stands tall next to its {{benchmarkReturnPercent}}."),
    ("RELATIVE_RETURN", "The Gap Of Success", "That {{relativePerformancePercent}} gap between you and the market is the sweet spot of investing."),
    ("ABSOLUTE_RETURN", "A Tidy Profit", "You secured a tidy {{portfolioReturnPercent}} profit. The dashboard is very happy to display this number."),
    ("BEST_ASSET", "Stellar Performance", "{{dailyBestAsset}} provided the rocket fuel needed to escape the benchmark's gravity."),
    ("GENERAL_MARKET_CHAOS", "Maximizing The Bull", "You maximized the bullish conditions perfectly today. A textbook example of capturing upside.")
]

for i, (angle, title, msg) in enumerate(gentle_jokes):
    templates.append({
        "templateId": f"both_positive_user_better_gentle_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_BETTER",
        "tone": "praise",
        "intensity": "gentle",
        "messageAngle": angle,
        "structureFamily": "PERFORMANCE_REVIEW",
        "metaphorCategory": "OFFICE",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive and outperformed the benchmark.",
        "suggestedFocusTemplate": "Enjoy the win, but stay disciplined.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Sarcastic (35)
sarcastic_jokes = [
    ("BENCHMARK_COMPARISON", "A Statistical Anomaly", "Somehow, your {{portfolioReturnPercent}} beat {{benchmarkName}}'s {{benchmarkReturnPercent}}. The math department has been notified of this glitch."),
    ("RELATIVE_RETURN", "Accidental Alpha", "You stumbled into a {{relativePerformancePercent}} outperformance. Please do not mistake this for skill just yet."),
    ("ABSOLUTE_RETURN", "The Blind Squirrel", "A {{portfolioReturnPercent}} gain proves that even a blind squirrel occasionally finds a mathematically optimal acorn."),
    ("BEST_ASSET", "The Lottery Ticket", "We see that {{dailyBestAsset}} carried you today. It's nice when a gamble disguised as research pays off."),
    ("GENERAL_MARKET_CHAOS", "Failing Upward", "The market was so overwhelmingly positive that it dragged your eccentric asset allocation to victory."),
    ("BENCHMARK_COMPARISON", "The Passive Aggression", "You beat the passive {{benchmarkName}} by putting in ten times the effort for a {{portfolioReturnPercent}} return. Efficient."),
    ("RELATIVE_RETURN", "A Temporary Lead", "Enjoy your {{relativePerformancePercent}} lead over the index. Mean reversion is patiently waiting in the lobby."),
    ("ABSOLUTE_RETURN", "Suspiciously Competent", "Generating {{portfolioReturnPercent}} today is highly suspicious. Are you sure you didn't accidentally buy an index fund?"),
    ("BEST_ASSET", "Concentration Risk Rewarded", "Your heavy bet on {{dailyBestAsset}} worked today. The risk department is having a mild panic attack, but congratulations."),
    ("GENERAL_MARKET_CHAOS", "Riding The Beta", "You outperformed in a bull market. A rising tide lifts all boats, even the ones built with questionable blueprints."),
    ("BENCHMARK_COMPARISON", "The Rare W", "Logging a {{portfolioReturnPercent}} against {{benchmarkName}}'s {{benchmarkReturnPercent}} is a rare W. Screenshot this for your memoirs."),
    ("RELATIVE_RETURN", "Outsmarting The Room", "You outsmarted the market by {{relativePerformancePercent}}. Try not to let it go to your head, the market has a long memory."),
    ("ABSOLUTE_RETURN", "Mathematically Acceptable", "A {{portfolioReturnPercent}} return has been deemed mathematically acceptable by the spreadsheet. It is uncomfortable giving compliments."),
    ("BEST_ASSET", "The One Good Decision", "Thank the heavens for {{dailyBestAsset}}. Without it, we'd be having a very different, much more familiar conversation."),
    ("GENERAL_MARKET_CHAOS", "Market Conditions Apply", "You won today, but please remember that terms and conditions of a bull market apply to these results."),
    ("BENCHMARK_COMPARISON", "The Overachiever", "You got {{portfolioReturnPercent}} while {{benchmarkName}} settled for {{benchmarkReturnPercent}}. Calm down, you're making the index look bad."),
    ("RELATIVE_RETURN", "A Gap In Reality", "That {{relativePerformancePercent}} outperformance is a tear in the fabric of reality. We assume it will be patched soon."),
    ("ABSOLUTE_RETURN", "The Uncomfortable Truth", "The uncomfortable truth is that you actually did well today with a {{portfolioReturnPercent}} gain. We're still processing this."),
    ("BEST_ASSET", "Heavy Shoulders", "{{dailyBestAsset}} has very heavy shoulders from carrying the rest of your decisions today."),
    ("GENERAL_MARKET_CHAOS", "Buoyancy Achieved", "The market flooded with liquidity and you managed to float slightly higher than the rest. Excellent buoyancy."),
    ("BENCHMARK_COMPARISON", "David vs Goliath", "You (David) got {{portfolioReturnPercent}}. The Index (Goliath) got {{benchmarkReturnPercent}}. Let's see if you can do it twice."),
    ("RELATIVE_RETURN", "The Skill Illusion", "You generated {{relativePerformancePercent}} of relative performance. The line between genius and luck is very blurry right now."),
    ("ABSOLUTE_RETURN", "Profit Detected", "Sensors have detected a {{portfolioReturnPercent}} profit. Initiating slow, reluctant golf clap protocol."),
    ("BEST_ASSET", "The Savior", "{{dailyBestAsset}} saved you from mediocrity today. Send it a thank you note."),
    ("GENERAL_MARKET_CHAOS", "Bull Market Genius", "Everyone is a genius in a bull market, but you were slightly more of a genius than average today."),
    ("BENCHMARK_COMPARISON", "The Index Weeps", "{{benchmarkName}} is currently crying in a corner after your {{portfolioReturnPercent}} return humiliated its {{benchmarkReturnPercent}}."),
    ("RELATIVE_RETURN", "Alpha Generated", "You actually generated {{relativePerformancePercent}} of alpha. The simulation might be broken."),
    ("ABSOLUTE_RETURN", "A Positive Number", "{{portfolioReturnPercent}} is a positive number. You correctly identified the right direction on the chart. Bravo."),
    ("BEST_ASSET", "The Golden Goose", "You found the golden goose in {{dailyBestAsset}}. Try not to accidentally sell it for a loss tomorrow."),
    ("GENERAL_MARKET_CHAOS", "Chaos Mastered", "You mastered the market chaos today and came out on top. It's almost frightening."),
    ("BENCHMARK_COMPARISON", "Slightly Less Basic", "You outperformed {{benchmarkName}}. You have graduated from 'basic' to 'slightly less basic' for the next 24 hours."),
    ("RELATIVE_RETURN", "The Margin Of Victory", "A {{relativePerformancePercent}} margin of victory. The spreadsheet approves, though it refuses to smile."),
    ("ABSOLUTE_RETURN", "Acceptable Output", "The output of {{portfolioReturnPercent}} is acceptable. Return to your terminal and do it again."),
    ("BEST_ASSET", "One Lucky Strike", "You struck oil with {{dailyBestAsset}}. Now step away before you spill it."),
    ("GENERAL_MARKET_CHAOS", "Surviving Success", "You survived a green day and actually outperformed. This app doesn't know how to handle this state.")
]

for i, (angle, title, msg) in enumerate(sarcastic_jokes):
    templates.append({
        "templateId": f"both_positive_user_better_sarcastic_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_BETTER",
        "tone": "mixed",
        "intensity": "sarcastic",
        "messageAngle": angle,
        "structureFamily": "SCIENTIFIC_OBSERVATION",
        "metaphorCategory": "SCIENCE",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive and outperformed the benchmark.",
        "suggestedFocusTemplate": "Try not to let this rare victory ruin your humility.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Brutal (25)
brutal_jokes = [
    ("BENCHMARK_COMPARISON", "A Glitch In The Matrix", "You beating {{benchmarkName}} by posting {{portfolioReturnPercent}} is undeniable proof that we are living in a simulation and the code is broken."),
    ("RELATIVE_RETURN", "Dumb Luck Quantified", "You beat the market by {{relativePerformancePercent}}. Do not mistake this statistical anomaly for actual financial acumen."),
    ("ABSOLUTE_RETURN", "The Imposter Syndrome", "You are up {{portfolioReturnPercent}}. The imposter syndrome you are feeling right now is completely justified."),
    ("BEST_ASSET", "The Hail Mary", "You threw a desperation pass with {{dailyBestAsset}} and it actually landed. Don't think you can do this every week."),
    ("GENERAL_MARKET_CHAOS", "Even A Broken Clock", "The market pumped, and you pumped harder. Even a broken clock is right twice a day, and this was your second time."),
    ("BENCHMARK_COMPARISON", "Humiliating The Index", "You got {{portfolioReturnPercent}} while {{benchmarkName}} got {{benchmarkReturnPercent}}. The fact that *you* beat it is the ultimate insult to passive investing."),
    ("RELATIVE_RETURN", "The Arrogance Premium", "That {{relativePerformancePercent}} outperformance is going to fuel your insufferable arrogance for at least a month. We pre-apologize to your friends."),
    ("ABSOLUTE_RETURN", "Unwarranted Success", "A {{portfolioReturnPercent}} gain. It physically pains me to admit that your chaotic button-mashing actually generated wealth today."),
    ("BEST_ASSET", "Accidental Outperformance", "{{dailyBestAsset}} went up, saving you from your own terrible asset allocation. You failed your way to success."),
    ("GENERAL_MARKET_CHAOS", "The Dunning-Kruger Peak", "You outperformed today. You are now at the absolute peak of 'Mount Stupid' on the Dunning-Kruger curve. The descent will be terrifying."),
    ("BENCHMARK_COMPARISON", "A Terrible Precedent", "By beating {{benchmarkName}} with a {{portfolioReturnPercent}} return, you have set a terrible precedent. Now you'll think you can do it again."),
    ("RELATIVE_RETURN", "Statistical Noise", "Your {{relativePerformancePercent}} outperformance is just statistical noise. Enjoy the noise while it lasts."),
    ("ABSOLUTE_RETURN", "The Illusory Gain", "{{portfolioReturnPercent}} in profit. It looks like money, it spends like money, but we both know you didn't earn it through skill."),
    ("BEST_ASSET", "The One-Trick Pony", "Your entire outperformance rests on the back of {{dailyBestAsset}}. You aren't a genius, you're just a one-trick pony."),
    ("GENERAL_MARKET_CHAOS", "Surfing A Tsunami", "You outperformed during a market tsunami. Try doing that when the water is calm and you actually have to swim."),
    ("BENCHMARK_COMPARISON", "The Index Surrenders", "You got {{portfolioReturnPercent}}. The index surrendered at {{benchmarkReturnPercent}}. The fact that you won makes a mockery of modern portfolio theory."),
    ("RELATIVE_RETURN", "The Pride Before The Fall", "You are up {{relativePerformancePercent}} against the market. Please take a screenshot before you inevitably give it all back next week."),
    ("ABSOLUTE_RETURN", "Painfully Competent", "You made {{portfolioReturnPercent}}. I am programmed to roast you, but your annoying competence today has left me with nothing but dry resentment."),
    ("BEST_ASSET", "Concentration Risk Manifested", "You bet the farm on {{dailyBestAsset}} and won. The line between 'visionary' and 'homeless' was very thin today."),
    ("GENERAL_MARKET_CHAOS", "The Lucky Fool", "You are the lucky fool Nassim Taleb warned us about. You outperformed the chaos by being slightly more chaotic."),
    ("BENCHMARK_COMPARISON", "A Fleeting Victory", "Enjoy your {{portfolioReturnPercent}} victory over {{benchmarkName}}. The market will collect its tax on your ego eventually."),
    ("RELATIVE_RETURN", "The Illusion Of Edge", "A {{relativePerformancePercent}} lead gives you the illusion of an edge. It's a dangerous hallucination. Stay safe."),
    ("ABSOLUTE_RETURN", "Unbearable Smugness", "You gained {{portfolioReturnPercent}}. We can already feel your unbearable smugness radiating through the screen."),
    ("BEST_ASSET", "The Backpack Of Shame", "You stuffed {{dailyBestAsset}} in your backpack and let it carry you up the mountain. Don't pretend you hiked it yourself."),
    ("GENERAL_MARKET_CHAOS", "Beta Masquerading As Alpha", "You got swept up in a massive rally and think you're Warren Buffett. It's just beta masquerading as alpha.")
]

for i, (angle, title, msg) in enumerate(brutal_jokes):
    templates.append({
        "templateId": f"both_positive_user_better_brutal_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_BETTER",
        "tone": "mixed",
        "intensity": "brutal",
        "messageAngle": angle,
        "structureFamily": "COURTROOM_VERDICT",
        "metaphorCategory": "BUREAUCRACY",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is positive and outperformed the benchmark.",
        "suggestedFocusTemplate": "Prepare for mean reversion.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Degen (15)
degen_jokes = [
    ("BENCHMARK_COMPARISON", "Chad Portfolio", "You gigachad. Printing {{portfolioReturnPercent}} while the boomer {{benchmarkName}} only did {{benchmarkReturnPercent}}. The timeline respects you today."),
    ("RELATIVE_RETURN", "Max Alpha", "Generating {{relativePerformancePercent}} of pure, unadulterated alpha. You are the main character of the bull market."),
    ("ABSOLUTE_RETURN", "Green Dildos Only", "A massive {{portfolioReturnPercent}} green candle right in the market's face. The laser eyes are fully charged."),
    ("BEST_ASSET", "Moon Mission Accomplished", "{{dailyBestAsset}} literally teleported to the moon today and dragged your net worth with it. Incredible scenes."),
    ("GENERAL_MARKET_CHAOS", "Up Only Achieved", "The market went up only, and you went up *more* only. You cracked the code, anon."),
    ("BENCHMARK_COMPARISON", "Dusting The TradFi", "You dusted the TradFi benchmark today. {{portfolioReturnPercent}} vs their pathetic {{benchmarkReturnPercent}}. We love to see it."),
    ("RELATIVE_RETURN", "Squeezing The Shorts", "You beat the market by {{relativePerformancePercent}}. You are single-handedly squeezing the bears into oblivion."),
    ("ABSOLUTE_RETURN", "WAGMI Verified", "Up {{portfolioReturnPercent}}. WAGMI is no longer a meme, it is a mathematically proven reality for your wallet."),
    ("BEST_ASSET", "Diamond Hands Rewarded", "You diamond handed {{dailyBestAsset}} and it paid off massively today. True degen enlightenment."),
    ("GENERAL_MARKET_CHAOS", "Surfing The Pump", "You surfed the absolute top of the pump today. A masterclass in degenerate outperformance."),
    ("BENCHMARK_COMPARISON", "Outpacing The Suits", "The suits at {{benchmarkName}} got {{benchmarkReturnPercent}}. You got {{portfolioReturnPercent}} while shitposting. Glorious."),
    ("RELATIVE_RETURN", "Generational Wealth Flex", "A {{relativePerformancePercent}} outperformance. You are one step closer to generational wealth, or at least a nice jpeg."),
    ("ABSOLUTE_RETURN", "Printing Tendies", "The printer is running hot today. {{portfolioReturnPercent}} in pure tendies. Enjoy the feast."),
    ("BEST_ASSET", "The God Candle", "{{dailyBestAsset}} printed a literal god candle today. We bow to your superior bag-holding skills."),
    ("GENERAL_MARKET_CHAOS", "Ape Evolution", "You evolved from a regular ape to a gigabrain ape today by outperforming the entire casino.")
]

for i, (angle, title, msg) in enumerate(degen_jokes):
    templates.append({
        "templateId": f"both_positive_user_better_degen_{angle}_{i+1:03d}",
        "scenarioKey": "BOTH_POSITIVE_USER_BETTER",
        "tone": "praise",
        "intensity": "degen",
        "messageAngle": angle,
        "structureFamily": "GAMING",
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

print(f"Generated {len(templates)} templates for BOTH_POSITIVE_USER_BETTER and overwrote comments.txt")
