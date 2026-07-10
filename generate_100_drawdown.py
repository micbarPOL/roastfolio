import json
import re

templates = []

# Gentle (25)
gentle_jokes = [
    ("DRAWDOWN_STATUS", "A Historical Perspective", "You are currently {{currentDrawdownFromATH}} below your all-time high. Drawdowns are a normal part of the process, keep a steady hand."),
    ("ABSOLUTE_RETURN", "Patience Required", "We're noticing a {{currentDrawdownFromATH}} pullback from the peak. The daily {{portfolioReturnPercent}} return is just noise in the long run."),
    ("GENERAL_MARKET_CHAOS", "Weathering The Storm", "The market has been choppy, bringing you {{currentDrawdownFromATH}} below your peak. Stay the course."),
    ("BENCHMARK_COMPARISON", "A Temporary Setback", "You are {{currentDrawdownFromATH}} off your highs. {{benchmarkName}} is also navigating these waters with a {{benchmarkReturnPercent}} return."),
    ("DRAWDOWN_STATUS", "The Distance To The Peak", "The all-time high is currently {{athDistancePercent}} away. A noticeable gap, but nothing that can't be rebuilt over time."),
    ("ABSOLUTE_RETURN", "Calm Under Pressure", "A {{currentDrawdownFromATH}} drawdown requires calm. Focus on the strategy, not the daily {{portfolioReturnPercent}} fluctuations."),
    ("GENERAL_MARKET_CHAOS", "Market Ebb And Flow", "We are in the ebb phase right now, sitting {{currentDrawdownFromATH}} below the high water mark. The tide will eventually turn."),
    ("BENCHMARK_COMPARISON", "Comparative Drawdown", "Being {{currentDrawdownFromATH}} off the peak is uncomfortable, but keep an eye on how {{benchmarkName}} is handling its {{benchmarkReturnPercent}} return today."),
    ("DRAWDOWN_STATUS", "A Noticeable Dip", "The portfolio has taken a noticeable {{currentDrawdownFromATH}} dip from its best days. A good time to review fundamentals."),
    ("ABSOLUTE_RETURN", "Focus On The Horizon", "Despite being {{currentDrawdownFromATH}} off the all-time high, your daily {{portfolioReturnPercent}} movement is just a small step in a long journey."),
    ("GENERAL_MARKET_CHAOS", "Riding The Waves", "The market waves have pushed us {{currentDrawdownFromATH}} below the summit. Keep your lifejacket on and stay patient."),
    ("BENCHMARK_COMPARISON", "Context Matters", "You are {{currentDrawdownFromATH}} down from your peak. For context, {{benchmarkName}} returned {{benchmarkReturnPercent}} today. You aren't alone."),
    ("DRAWDOWN_STATUS", "The Rebuilding Phase", "We have {{athDistancePercent}} to climb to reach the peak again. The rebuilding phase requires discipline."),
    ("ABSOLUTE_RETURN", "Steady Hands", "Your portfolio is {{currentDrawdownFromATH}} below its high. Keep steady hands, regardless of today's {{portfolioReturnPercent}}."),
    ("GENERAL_MARKET_CHAOS", "A Broader Perspective", "Market chaos has led to a {{currentDrawdownFromATH}} drawdown. A broader perspective is helpful right now."),
    ("BENCHMARK_COMPARISON", "Parallel Paths", "Your {{currentDrawdownFromATH}} distance from the top is a shared experience. {{benchmarkName}} is also navigating a {{benchmarkReturnPercent}} return."),
    ("DRAWDOWN_STATUS", "The Summit Is Still There", "You are {{currentDrawdownFromATH}} below the summit. It hasn't moved, you just need to start climbing again."),
    ("ABSOLUTE_RETURN", "A Temporary Valuation", "The {{currentDrawdownFromATH}} pullback is just a temporary valuation. Focus on the assets, not the {{portfolioReturnPercent}} print."),
    ("GENERAL_MARKET_CHAOS", "Navigating Turbulence", "Turbulence has caused a {{currentDrawdownFromATH}} drop from your all-time high. Keep your seatbelt fastened."),
    ("BENCHMARK_COMPARISON", "A Gentle Reminder", "You are {{currentDrawdownFromATH}} off the high. Remember that even {{benchmarkName}} with its {{benchmarkReturnPercent}} return experiences these cycles."),
    ("DRAWDOWN_STATUS", "The Long View", "Taking the long view is essential when you are {{currentDrawdownFromATH}} below your historical peak."),
    ("ABSOLUTE_RETURN", "Managing Expectations", "A {{currentDrawdownFromATH}} drawdown is a good time to manage expectations and ignore the daily {{portfolioReturnPercent}} noise."),
    ("GENERAL_MARKET_CHAOS", "Staying Grounded", "The market is volatile, leaving you {{currentDrawdownFromATH}} off the high. Staying grounded is the best approach."),
    ("BENCHMARK_COMPARISON", "Shared Volatility", "Volatility affects everyone. You are {{currentDrawdownFromATH}} down, while {{benchmarkName}} returned {{benchmarkReturnPercent}}."),
    ("DRAWDOWN_STATUS", "A Measured Approach", "A measured approach is needed to close the {{athDistancePercent}} gap back to the all-time high.")
]

for i, (angle, title, msg) in enumerate(gentle_jokes):
    templates.append({
        "templateId": f"drawdown_significant_gentle_{angle}_{i+1:03d}",
        "scenarioKey": "DRAWDOWN_SIGNIFICANT",
        "tone": "mixed",
        "intensity": "gentle",
        "messageAngle": angle,
        "structureFamily": "WEATHER_REPORT",
        "metaphorCategory": "WEATHER",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is meaningfully below its all-time high.",
        "suggestedFocusTemplate": "Focus on the long-term fundamentals.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Sarcastic (35)
sarcastic_jokes = [
    ("DRAWDOWN_STATUS", "A Historical Artifact", "Your all-time high is now officially a historical artifact, currently sitting {{currentDrawdownFromATH}} above your present reality."),
    ("ABSOLUTE_RETURN", "The Nostalgia Portfolio", "Remember when you were rich? You are now {{currentDrawdownFromATH}} poorer than your peak. Today's {{portfolioReturnPercent}} is mostly decorative."),
    ("GENERAL_MARKET_CHAOS", "Emotional Depth Achieved", "Congratulations, your portfolio's {{currentDrawdownFromATH}} drawdown has given the chart a profound sense of emotional depth."),
    ("BENCHMARK_COMPARISON", "The Gravity Check", "You are {{currentDrawdownFromATH}} off your high. Gravity works. Meanwhile, {{benchmarkName}} logged {{benchmarkReturnPercent}} without complaining."),
    ("DRAWDOWN_STATUS", "The Silent Judgment", "The gauge is silently judging your {{currentDrawdownFromATH}} drawdown. It doesn't want to panic you, it's just disappointed."),
    ("ABSOLUTE_RETURN", "A Distant Memory", "The peak is {{athDistancePercent}} away. A distant memory, much like your confidence. Today's {{portfolioReturnPercent}} return is merely a footnote."),
    ("GENERAL_MARKET_CHAOS", "The Scenic Route Down", "The market decided to take the scenic route down, and you followed along perfectly to a {{currentDrawdownFromATH}} deficit."),
    ("BENCHMARK_COMPARISON", "Relative Misery", "You are down {{currentDrawdownFromATH}} from the peak. We hope comparing it to {{benchmarkName}}'s {{benchmarkReturnPercent}} brings you some cold comfort."),
    ("DRAWDOWN_STATUS", "A Noticeable Dent", "That {{currentDrawdownFromATH}} drawdown is not a scratch, it's a very noticeable dent in your financial vehicle."),
    ("ABSOLUTE_RETURN", "The Value Of Humility", "Your {{currentDrawdownFromATH}} drop from the peak is an excellent lesson in humility. The {{portfolioReturnPercent}} today is just the tuition fee."),
    ("GENERAL_MARKET_CHAOS", "Choppy Waters", "The market has been choppy, which is a polite way of saying your net worth has sunk {{currentDrawdownFromATH}} from its highest point."),
    ("BENCHMARK_COMPARISON", "Index Envy", "You are {{currentDrawdownFromATH}} off your highs. Do you ever look at {{benchmarkName}}'s {{benchmarkReturnPercent}} and wonder what if?"),
    ("DRAWDOWN_STATUS", "The Uncomfortable Truth", "The uncomfortable truth is you need a {{athDistancePercent}} climb just to break even with your past self."),
    ("ABSOLUTE_RETURN", "A Temporary Re-pricing", "We are calling this {{currentDrawdownFromATH}} drawdown a 'temporary re-pricing' to protect your feelings. The {{portfolioReturnPercent}} today is incidental."),
    ("GENERAL_MARKET_CHAOS", "Market Participation Trophy", "You participated in the market chaos and were rewarded with a {{currentDrawdownFromATH}} drawdown. Please collect your trophy at the desk."),
    ("BENCHMARK_COMPARISON", "The Benchmark's Shadow", "Sitting {{currentDrawdownFromATH}} below your peak while {{benchmarkName}} does {{benchmarkReturnPercent}}. The shadow is getting quite long."),
    ("DRAWDOWN_STATUS", "The Shrinking Pie", "Your portfolio is {{currentDrawdownFromATH}} smaller than it used to be. It's a diet nobody asked for."),
    ("ABSOLUTE_RETURN", "A Modest Decline", "We'll call it a 'modest decline' of {{currentDrawdownFromATH}}, though we both know it stings. Today's {{portfolioReturnPercent}} is largely irrelevant."),
    ("GENERAL_MARKET_CHAOS", "Turbulence Detected", "Severe turbulence has resulted in a {{currentDrawdownFromATH}} drop from your all-time high. Please remain seated."),
    ("BENCHMARK_COMPARISON", "A Fair Comparison", "You are down {{currentDrawdownFromATH}}. {{benchmarkName}} is at {{benchmarkReturnPercent}}. It's a fair comparison, even if you don't like the result."),
    ("DRAWDOWN_STATUS", "The Distant Summit", "The summit is {{athDistancePercent}} away. You might want to pack some extra oxygen for the climb back up."),
    ("ABSOLUTE_RETURN", "A Lesson In Patience", "A {{currentDrawdownFromATH}} drawdown is a masterclass in patience. Your daily {{portfolioReturnPercent}} is the pop quiz."),
    ("GENERAL_MARKET_CHAOS", "The Gravity Of The Situation", "The market has remembered gravity, pulling you {{currentDrawdownFromATH}} from your peak. Fascinating physics at work."),
    ("BENCHMARK_COMPARISON", "Comparative Suffering", "You are {{currentDrawdownFromATH}} down. Let's see how {{benchmarkName}}'s {{benchmarkReturnPercent}} compares to your suffering."),
    ("DRAWDOWN_STATUS", "The New Normal", "Is {{currentDrawdownFromATH}} below the peak the new normal? Only time, and better decisions, will tell."),
    ("ABSOLUTE_RETURN", "A Substantial Haircut", "That {{currentDrawdownFromATH}} drop is a substantial haircut. We hope you like the new style. The {{portfolioReturnPercent}} today won't grow it back quickly."),
    ("GENERAL_MARKET_CHAOS", "Market Induced Nausea", "The market chaos has induced a {{currentDrawdownFromATH}} drawdown. We recommend looking away from the screen."),
    ("BENCHMARK_COMPARISON", "The Underachiever's Guide", "You are {{currentDrawdownFromATH}} off the high. {{benchmarkName}} returned {{benchmarkReturnPercent}}. You might want to read the manual again."),
    ("DRAWDOWN_STATUS", "The Long Climb Back", "A {{athDistancePercent}} climb awaits you. We suggest wearing comfortable shoes."),
    ("ABSOLUTE_RETURN", "A Mathematical Correction", "The universe is applying a {{currentDrawdownFromATH}} mathematical correction to your previously inflated net worth. Today's {{portfolioReturnPercent}} is just a rounding error."),
    ("GENERAL_MARKET_CHAOS", "Riding The Down Draft", "You successfully rode the down draft to a {{currentDrawdownFromATH}} deficit. Flawless execution."),
    ("BENCHMARK_COMPARISON", "The Passive Mockery", "You are {{currentDrawdownFromATH}} down from your peak. The passive {{benchmarkName}} with its {{benchmarkReturnPercent}} is quietly mocking your efforts."),
    ("DRAWDOWN_STATUS", "A Deflated Ego", "Your portfolio and your ego are both {{currentDrawdownFromATH}} off their all-time highs. It's a package deal."),
    ("ABSOLUTE_RETURN", "The Reality Check", "This {{currentDrawdownFromATH}} drawdown is a reality check. The daily {{portfolioReturnPercent}} is just the background music to your realization."),
    ("GENERAL_MARKET_CHAOS", "A Victim Of Circumstance", "You are a victim of market circumstance, to the tune of {{currentDrawdownFromATH}} below your peak. A tragic, yet common, tale.")
]

for i, (angle, title, msg) in enumerate(sarcastic_jokes):
    templates.append({
        "templateId": f"drawdown_significant_sarcastic_{angle}_{i+1:03d}",
        "scenarioKey": "DRAWDOWN_SIGNIFICANT",
        "tone": "roast",
        "intensity": "sarcastic",
        "messageAngle": angle,
        "structureFamily": "SCIENTIFIC_OBSERVATION",
        "metaphorCategory": "SCIENCE",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is meaningfully below its all-time high.",
        "suggestedFocusTemplate": "Try not to obsess over the peak.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Brutal (25)
brutal_jokes = [
    ("DRAWDOWN_STATUS", "A Monument To Past Glory", "Your all-time high is a monument to a past you will not see again soon. You are {{currentDrawdownFromATH}} down and the climb looks exhausting."),
    ("ABSOLUTE_RETURN", "Wealth Destruction", "A {{currentDrawdownFromATH}} drawdown isn't a dip, it's wealth destruction. Whatever {{portfolioReturnPercent}} you made today is a rounding error on your failure."),
    ("GENERAL_MARKET_CHAOS", "The Illusion Of Competence", "The market has shattered your illusion of competence, dragging you {{currentDrawdownFromATH}} from the peak. Reality is harsh."),
    ("BENCHMARK_COMPARISON", "The Humbling", "You are {{currentDrawdownFromATH}} off your high. {{benchmarkName}} did {{benchmarkReturnPercent}}. You are paying fees to lose your own money."),
    ("DRAWDOWN_STATUS", "A Deep Crater", "That's not a pullback, that's a {{currentDrawdownFromATH}} crater. We suggest avoiding looking directly at the chart."),
    ("ABSOLUTE_RETURN", "The Painful Truth", "The painful truth is you are {{currentDrawdownFromATH}} poorer than your peak. Don't let today's {{portfolioReturnPercent}} distract you from the larger disaster."),
    ("GENERAL_MARKET_CHAOS", "Swept Away", "The market chaos easily swept away your gains, leaving you {{currentDrawdownFromATH}} down. Your strategy was built on sand."),
    ("BENCHMARK_COMPARISON", "Statistically Inferior", "You are {{currentDrawdownFromATH}} off your high. The {{benchmarkReturnPercent}} from {{benchmarkName}} highlights how unnecessary your active management truly is."),
    ("DRAWDOWN_STATUS", "The Impossible Climb", "You need a {{athDistancePercent}} return just to get back to where you started. That's a steep hill for someone with a history of bad decisions."),
    ("ABSOLUTE_RETURN", "A Bleeding Portfolio", "Your portfolio has bled out {{currentDrawdownFromATH}} from the top. Today's {{portfolioReturnPercent}} is just a band-aid on a gaping wound."),
    ("GENERAL_MARKET_CHAOS", "Exposed By The Tide", "The tide went out, and you were caught swimming naked to the tune of {{currentDrawdownFromATH}} below your peak."),
    ("BENCHMARK_COMPARISON", "An Expensive Lesson", "Being {{currentDrawdownFromATH}} down is an expensive lesson. Perhaps {{benchmarkName}} and its {{benchmarkReturnPercent}} can teach you something about humility."),
    ("DRAWDOWN_STATUS", "The Ghost Of Gains Past", "Your portfolio is haunted by the ghost of its all-time high, currently sitting {{currentDrawdownFromATH}} in the grave."),
    ("ABSOLUTE_RETURN", "Evaporating Wealth", "{{currentDrawdownFromATH}} of your peak wealth has simply evaporated. You can stare at today's {{portfolioReturnPercent}}, but it won't bring it back."),
    ("GENERAL_MARKET_CHAOS", "Crushed By Beta", "You thought you had alpha, but you were crushed by beta, resulting in a {{currentDrawdownFromATH}} drawdown."),
    ("BENCHMARK_COMPARISON", "The Incompetence Tax", "The {{currentDrawdownFromATH}} you lost from the peak is the incompetence tax. {{benchmarkName}} at {{benchmarkReturnPercent}} is tax-exempt."),
    ("DRAWDOWN_STATUS", "A Financial Sinkhole", "Your portfolio has fallen into a {{currentDrawdownFromATH}} sinkhole. We do not recommend throwing more money into it right now."),
    ("ABSOLUTE_RETURN", "A Bitter Pill", "Swallow the bitter pill: you are {{currentDrawdownFromATH}} below your peak. Your {{portfolioReturnPercent}} return today does not change the diagnosis."),
    ("GENERAL_MARKET_CHAOS", "Market Induced Reality", "The market has enforced a brutal reality check, pushing you {{currentDrawdownFromATH}} from your delusions of grandeur."),
    ("BENCHMARK_COMPARISON", "Comparative Failure", "You are {{currentDrawdownFromATH}} down from your best. Let's compare that failure to {{benchmarkName}}'s {{benchmarkReturnPercent}}."),
    ("DRAWDOWN_STATUS", "The Distant Mirage", "Your all-time high is a {{athDistancePercent}} distant mirage. You are walking in the desert of drawdown."),
    ("ABSOLUTE_RETURN", "A Harsh Correction", "This {{currentDrawdownFromATH}} drop is a harsh, but necessary, correction of your inflated ego. Today's {{portfolioReturnPercent}} is irrelevant."),
    ("GENERAL_MARKET_CHAOS", "The House Always Wins", "The market casino always wins eventually, taking back {{currentDrawdownFromATH}} of your chips."),
    ("BENCHMARK_COMPARISON", "The Index's Revenge", "{{benchmarkName}} is getting its revenge. You are {{currentDrawdownFromATH}} off your high, while it does {{benchmarkReturnPercent}}."),
    ("DRAWDOWN_STATUS", "A Masterclass In Losing", "You have masterfully lost {{currentDrawdownFromATH}} from your portfolio's peak. A truly breathtaking display of wealth destruction.")
]

for i, (angle, title, msg) in enumerate(brutal_jokes):
    templates.append({
        "templateId": f"drawdown_significant_brutal_{angle}_{i+1:03d}",
        "scenarioKey": "DRAWDOWN_SIGNIFICANT",
        "tone": "roast",
        "intensity": "brutal",
        "messageAngle": angle,
        "structureFamily": "COURTROOM_VERDICT",
        "metaphorCategory": "BUREAUCRACY",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is meaningfully below its all-time high.",
        "suggestedFocusTemplate": "Accept the reality of your current balance.",
        "requiredData": [p.strip('{}') for p in [w for w in msg.split() if w.startswith('{{')]],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    })

# Degen (15)
degen_jokes = [
    ("DRAWDOWN_STATUS", "The Bags Are Heavy", "You are {{currentDrawdownFromATH}} off the ATH. These bags are getting incredibly heavy, anon. Time to hit the gym."),
    ("ABSOLUTE_RETURN", "Rekt By The Chop", "Down {{currentDrawdownFromATH}} from the top. The chop is absolutely destroying you. Today's {{portfolioReturnPercent}} is just a tease."),
    ("GENERAL_MARKET_CHAOS", "Nuked From Orbit", "The market nuked your portfolio from orbit. {{currentDrawdownFromATH}} down. We are not gonna make it at this rate."),
    ("BENCHMARK_COMPARISON", "Boomers Winning", "You are {{currentDrawdownFromATH}} down from the top while the boomer {{benchmarkName}} does {{benchmarkReturnPercent}}. Embarrassing for the timeline."),
    ("DRAWDOWN_STATUS", "The {{athDistancePercent}} Squeeze", "You need a {{athDistancePercent}} god candle just to break even. The copium is running dangerously low."),
    ("ABSOLUTE_RETURN", "Liquidated Dreams", "{{currentDrawdownFromATH}} of your peak net worth is gone. Staring at today's {{portfolioReturnPercent}} won't bring the jpeg money back."),
    ("GENERAL_MARKET_CHAOS", "PvP Market Survior", "The PvP market took {{currentDrawdownFromATH}} of your health bar. Drink a potion and try not to get rugged again."),
    ("BENCHMARK_COMPARISON", "Chad Index Survives", "The Chad {{benchmarkName}} printed {{benchmarkReturnPercent}} while your degen bags are {{currentDrawdownFromATH}} off the ATH. Tragic."),
    ("DRAWDOWN_STATUS", "Down Bad", "You are officially down bad. {{currentDrawdownFromATH}} off the high is rough. Maybe touch some grass until the pump returns."),
    ("ABSOLUTE_RETURN", "Fading The Top", "You successfully faded your own top by {{currentDrawdownFromATH}}. Today's {{portfolioReturnPercent}} is just a dead cat bouncing."),
    ("GENERAL_MARKET_CHAOS", "Ape Tears", "The timeline is flooded with ape tears. You are {{currentDrawdownFromATH}} down from the promised land."),
    ("BENCHMARK_COMPARISON", "Tradfi Mockery", "The tradfi {{benchmarkName}} is laughing at your {{currentDrawdownFromATH}} drawdown with its {{benchmarkReturnPercent}} return. Delete the app."),
    ("DRAWDOWN_STATUS", "The Copium Climb", "You are huffing maximum copium hoping for a {{athDistancePercent}} pump to save your portfolio. Good luck."),
    ("ABSOLUTE_RETURN", "Generational Wealth Deleted", "You deleted {{currentDrawdownFromATH}} of potential generational wealth. At least you have {{portfolioReturnPercent}} today to stare at."),
    ("GENERAL_MARKET_CHAOS", "Bear Market Vibes", "The vibes are immaculate if you enjoy losing money. You are {{currentDrawdownFromATH}} off the peak. Turn off the monitor.")
]

for i, (angle, title, msg) in enumerate(degen_jokes):
    templates.append({
        "templateId": f"drawdown_significant_degen_{angle}_{i+1:03d}",
        "scenarioKey": "DRAWDOWN_SIGNIFICANT",
        "tone": "mixed",
        "intensity": "degen",
        "messageAngle": angle,
        "structureFamily": "GAMING",
        "metaphorCategory": "GAMING",
        "titleTemplate": title,
        "messageTemplate": msg,
        "mainReasonTemplate": "Portfolio is meaningfully below its all-time high.",
        "suggestedFocusTemplate": "Touch grass and wait for the pump.",
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

with open('lambda/data/cm.txt', 'w') as f:
    json.dump(templates, f, indent=2)

print(f"Generated {len(templates)} templates for DRAWDOWN_SIGNIFICANT and saved to cm.txt")
