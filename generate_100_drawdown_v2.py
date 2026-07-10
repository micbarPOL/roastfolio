import json
import re

templates = []

# Gentle (25)
gentle_jokes = [
    ("DRAWDOWN_STATUS", "The Valley Below", "You are currently {{currentDrawdownFromATH}} below the peak. Markets spend most of their time in drawdowns. Stay patient."),
    ("ABSOLUTE_RETURN", "A Temporary Dip", "The portfolio is {{currentDrawdownFromATH}} off its highs. Today's {{portfolioReturnPercent}} return is just one step on the long road back."),
    ("GENERAL_MARKET_CHAOS", "Navigating The Chop", "Market chaos has pushed the balance down by {{currentDrawdownFromATH}}. Choppy waters don't last forever."),
    ("BENCHMARK_COMPARISON", "A Shared Experience", "Being {{currentDrawdownFromATH}} down from the peak is tough, but note that {{benchmarkName}} is also at {{benchmarkReturnPercent}}. You aren't alone."),
    ("DRAWDOWN_STATUS", "Distance To Goal", "The ATH is {{athDistancePercent}} away. It seems far, but consistent compounding will bridge the gap."),
    ("ABSOLUTE_RETURN", "Keeping Perspective", "You are {{currentDrawdownFromATH}} below your best day. A {{portfolioReturnPercent}} daily move shouldn't distract from the big picture."),
    ("GENERAL_MARKET_CHAOS", "Market Ebb", "The tide is out, leaving you {{currentDrawdownFromATH}} from the high water mark. Keep your strategy intact."),
    ("BENCHMARK_COMPARISON", "Relative Drawdown", "A {{currentDrawdownFromATH}} drawdown is noticeable. Compare that to {{benchmarkName}}'s {{benchmarkReturnPercent}} to maintain perspective."),
    ("DRAWDOWN_STATUS", "The Historical Peak", "Your portfolio is taking a {{currentDrawdownFromATH}} breather from its historical peak. It happens to the best of them."),
    ("ABSOLUTE_RETURN", "Focus On The Process", "A {{currentDrawdownFromATH}} drawdown is a good time to focus on the process, rather than the daily {{portfolioReturnPercent}} noise."),
    ("GENERAL_MARKET_CHAOS", "Weathering Volatility", "Volatility has brought you {{currentDrawdownFromATH}} down. Weathering these periods is how long-term wealth is built."),
    ("BENCHMARK_COMPARISON", "Contextual Decline", "You are {{currentDrawdownFromATH}} down from the top. For context, {{benchmarkName}} is dealing with a {{benchmarkReturnPercent}} return today."),
    ("DRAWDOWN_STATUS", "The Next Ascent", "We need a {{athDistancePercent}} climb to reach the summit again. Pack your patience."),
    ("ABSOLUTE_RETURN", "Steady Nerves", "It takes steady nerves to sit through a {{currentDrawdownFromATH}} drawdown. Ignore today's {{portfolioReturnPercent}} print and hold the line."),
    ("GENERAL_MARKET_CHAOS", "A Broader View", "Market conditions have caused a {{currentDrawdownFromATH}} pullback. A broader view is necessary right now."),
    ("BENCHMARK_COMPARISON", "Parallel Struggles", "Your {{currentDrawdownFromATH}} distance from the top is mirrored by others. {{benchmarkName}}'s {{benchmarkReturnPercent}} is proof."),
    ("DRAWDOWN_STATUS", "The Summit Remains", "You are {{currentDrawdownFromATH}} below the summit. The mountain hasn't changed, only your position on it."),
    ("ABSOLUTE_RETURN", "Temporary Valuation V2", "The {{currentDrawdownFromATH}} pullback is temporary. Focus on the underlying assets, not the {{portfolioReturnPercent}} fluctuation."),
    ("GENERAL_MARKET_CHAOS", "Navigating Turbulence V2", "Turbulence has led to a {{currentDrawdownFromATH}} drop from your ATH. Keep your focus on the horizon."),
    ("BENCHMARK_COMPARISON", "A Gentle Context", "You are {{currentDrawdownFromATH}} off the high. Remember {{benchmarkName}} and its {{benchmarkReturnPercent}} return. It's a challenging environment."),
    ("DRAWDOWN_STATUS", "The Long View V2", "Taking the long view is helpful when you are {{currentDrawdownFromATH}} below your peak."),
    ("ABSOLUTE_RETURN", "Managing Expectations V2", "A {{currentDrawdownFromATH}} drawdown requires managing expectations and ignoring the daily {{portfolioReturnPercent}}."),
    ("GENERAL_MARKET_CHAOS", "Staying Grounded V2", "The market is volatile, leaving you {{currentDrawdownFromATH}} off the high. Staying grounded is key."),
    ("BENCHMARK_COMPARISON", "Shared Volatility V2", "Volatility is everywhere. You are {{currentDrawdownFromATH}} down, while {{benchmarkName}} returned {{benchmarkReturnPercent}}."),
    ("DRAWDOWN_STATUS", "A Measured Approach V2", "A measured approach is required to close the {{athDistancePercent}} gap back to the top.")
]

for i, (angle, title, msg) in enumerate(gentle_jokes):
    templates.append({
        "templateId": f"drawdown_significant_v2_gentle_{angle}_{i+1:03d}",
        "scenarioKey": "DRAWDOWN_SIGNIFICANT",
        "tone": "mixed",
        "intensity": "gentle",
        "messageAngle": angle,
        "structureFamily": "PRIVATE_BANKER_NOTE",
        "metaphorCategory": "BANKING",
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
    ("DRAWDOWN_STATUS", "A Museum Exhibit", "Your all-time high belongs in a museum. You are currently {{currentDrawdownFromATH}} below it, living in the present reality."),
    ("ABSOLUTE_RETURN", "The Good Old Days", "Remember the peak? You are now {{currentDrawdownFromATH}} poorer. The {{portfolioReturnPercent}} today is a nice, albeit useless, distraction."),
    ("GENERAL_MARKET_CHAOS", "A Scenic Dive", "The market took a dive and you gracefully followed it to a {{currentDrawdownFromATH}} deficit. A perfect 10 for execution."),
    ("BENCHMARK_COMPARISON", "Gravity Verified", "You are {{currentDrawdownFromATH}} off your high. Gravity works. {{benchmarkName}}'s {{benchmarkReturnPercent}} confirms the physics."),
    ("DRAWDOWN_STATUS", "The Judging Dashboard", "The dashboard is silently judging your {{currentDrawdownFromATH}} drawdown. It remembers when you were successful."),
    ("ABSOLUTE_RETURN", "A Distant Dream", "The peak is {{athDistancePercent}} away. A distant dream. Today's {{portfolioReturnPercent}} return won't bridge that chasm."),
    ("GENERAL_MARKET_CHAOS", "The Scenic Route Down V2", "The market decided to take the scenic route down, and you followed perfectly to a {{currentDrawdownFromATH}} loss."),
    ("BENCHMARK_COMPARISON", "Cold Comfort", "You are down {{currentDrawdownFromATH}} from the peak. We hope comparing it to {{benchmarkName}}'s {{benchmarkReturnPercent}} brings some cold comfort."),
    ("DRAWDOWN_STATUS", "A Very Visible Dent", "That {{currentDrawdownFromATH}} drawdown is a very visible dent. You can't just buff that out."),
    ("ABSOLUTE_RETURN", "The Tuition Fee", "Your {{currentDrawdownFromATH}} drop from the peak is the market's tuition fee. The {{portfolioReturnPercent}} today is just the receipt."),
    ("GENERAL_MARKET_CHAOS", "Choppy Waters V2", "The market has been choppy, meaning your net worth has sunk {{currentDrawdownFromATH}} from its highest point. Bring a towel."),
    ("BENCHMARK_COMPARISON", "Index Envy V2", "You are {{currentDrawdownFromATH}} off your highs. Look at {{benchmarkName}}'s {{benchmarkReturnPercent}} and wonder what went wrong."),
    ("DRAWDOWN_STATUS", "The Uncomfortable Math", "The uncomfortable math dictates a {{athDistancePercent}} climb just to break even with your former self."),
    ("ABSOLUTE_RETURN", "A Temporary Re-pricing V2", "We are calling this {{currentDrawdownFromATH}} drawdown a 're-pricing' to protect your ego. The {{portfolioReturnPercent}} today is irrelevant."),
    ("GENERAL_MARKET_CHAOS", "Participation Trophy", "You participated in the market chaos and earned a {{currentDrawdownFromATH}} drawdown. Please collect your trophy."),
    ("BENCHMARK_COMPARISON", "The Benchmark's Shadow V2", "Sitting {{currentDrawdownFromATH}} below your peak while {{benchmarkName}} does {{benchmarkReturnPercent}}. The shadow is long."),
    ("DRAWDOWN_STATUS", "The Diet Portfolio", "Your portfolio is {{currentDrawdownFromATH}} smaller. It's on a strict diet of your bad decisions."),
    ("ABSOLUTE_RETURN", "A Modest Decline V2", "We'll call it a 'modest decline' of {{currentDrawdownFromATH}}. Today's {{portfolioReturnPercent}} is largely decorative at this point."),
    ("GENERAL_MARKET_CHAOS", "Turbulence Detected V2", "Severe turbulence has resulted in a {{currentDrawdownFromATH}} drop. Please return your tray table to the upright position."),
    ("BENCHMARK_COMPARISON", "A Fair Comparison V2", "You are down {{currentDrawdownFromATH}}. {{benchmarkName}} is at {{benchmarkReturnPercent}}. It's a fair, if unpleasant, comparison."),
    ("DRAWDOWN_STATUS", "The Distant Summit V2", "The summit is {{athDistancePercent}} away. You might want to stretch before you start climbing again."),
    ("ABSOLUTE_RETURN", "A Lesson In Patience V2", "A {{currentDrawdownFromATH}} drawdown is a masterclass in patience. Your daily {{portfolioReturnPercent}} is the homework."),
    ("GENERAL_MARKET_CHAOS", "Physics At Work", "The market remembered gravity, pulling you {{currentDrawdownFromATH}} from your peak. Fascinating."),
    ("BENCHMARK_COMPARISON", "Comparative Suffering V2", "You are {{currentDrawdownFromATH}} down. Let's see how {{benchmarkName}}'s {{benchmarkReturnPercent}} compares to your misery."),
    ("DRAWDOWN_STATUS", "The New Normal V2", "Is {{currentDrawdownFromATH}} below the peak the new normal? Time will tell."),
    ("ABSOLUTE_RETURN", "A Substantial Haircut V2", "That {{currentDrawdownFromATH}} drop is a substantial haircut. The {{portfolioReturnPercent}} today won't grow it back."),
    ("GENERAL_MARKET_CHAOS", "Market Induced Nausea V2", "The market chaos has induced a {{currentDrawdownFromATH}} drawdown. Have a mint."),
    ("BENCHMARK_COMPARISON", "The Underachiever's Guide V2", "You are {{currentDrawdownFromATH}} off the high. {{benchmarkName}} returned {{benchmarkReturnPercent}}. Read the manual again."),
    ("DRAWDOWN_STATUS", "The Long Climb Back V2", "A {{athDistancePercent}} climb awaits you. We suggest wearing comfortable shoes."),
    ("ABSOLUTE_RETURN", "A Mathematical Correction V2", "The universe is applying a {{currentDrawdownFromATH}} mathematical correction to your net worth. Today's {{portfolioReturnPercent}} is a rounding error."),
    ("GENERAL_MARKET_CHAOS", "Riding The Down Draft V2", "You successfully rode the down draft to a {{currentDrawdownFromATH}} deficit. Flawless."),
    ("BENCHMARK_COMPARISON", "The Passive Mockery V2", "You are {{currentDrawdownFromATH}} down. The passive {{benchmarkName}} with its {{benchmarkReturnPercent}} is quietly mocking you."),
    ("DRAWDOWN_STATUS", "A Deflated Ego V2", "Your portfolio and ego are both {{currentDrawdownFromATH}} off their highs. A perfect match."),
    ("ABSOLUTE_RETURN", "The Reality Check V2", "This {{currentDrawdownFromATH}} drawdown is a reality check. The daily {{portfolioReturnPercent}} is background noise."),
    ("GENERAL_MARKET_CHAOS", "A Victim Of Circumstance V2", "You are a victim of circumstance, to the tune of {{currentDrawdownFromATH}} below your peak. Tragic.")
]

for i, (angle, title, msg) in enumerate(sarcastic_jokes):
    templates.append({
        "templateId": f"drawdown_significant_v2_sarcastic_{angle}_{i+1:03d}",
        "scenarioKey": "DRAWDOWN_SIGNIFICANT",
        "tone": "roast",
        "intensity": "sarcastic",
        "messageAngle": angle,
        "structureFamily": "DETECTIVE",
        "metaphorCategory": "DETECTIVE",
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
    ("DRAWDOWN_STATUS", "A Shrine To Failure", "Your all-time high is a shrine to a past you squandered. You are {{currentDrawdownFromATH}} down and the climb looks mathematically impossible for you."),
    ("ABSOLUTE_RETURN", "Wealth Erasure", "A {{currentDrawdownFromATH}} drawdown is wealth erasure. Whatever {{portfolioReturnPercent}} you made today is a rounding error on your long-term failure."),
    ("GENERAL_MARKET_CHAOS", "The Delusion Is Over", "The market shattered your delusion of competence, dragging you {{currentDrawdownFromATH}} from the peak. Reality remains undefeated."),
    ("BENCHMARK_COMPARISON", "The Humbling V2", "You are {{currentDrawdownFromATH}} off your high. {{benchmarkName}} did {{benchmarkReturnPercent}}. You are paying the market to humiliate you."),
    ("DRAWDOWN_STATUS", "The Abyss", "That's not a pullback, that's a {{currentDrawdownFromATH}} abyss. Do not look down."),
    ("ABSOLUTE_RETURN", "The Ugly Truth", "The ugly truth is you are {{currentDrawdownFromATH}} poorer than your peak. Today's {{portfolioReturnPercent}} doesn't hide the disaster."),
    ("GENERAL_MARKET_CHAOS", "Washed Away", "The market chaos washed away your gains, leaving you {{currentDrawdownFromATH}} down. Your portfolio was a sandcastle."),
    ("BENCHMARK_COMPARISON", "Mathematically Inferior", "You are {{currentDrawdownFromATH}} off your high. The {{benchmarkReturnPercent}} from {{benchmarkName}} proves your active management is a liability."),
    ("DRAWDOWN_STATUS", "The Sisyphus Portfolio", "You need a {{athDistancePercent}} return just to break even. Sisyphus had an easier time with his boulder."),
    ("ABSOLUTE_RETURN", "Hemorrhaging Capital", "Your portfolio has hemorrhaged {{currentDrawdownFromATH}} from the top. Today's {{portfolioReturnPercent}} is a placebo."),
    ("GENERAL_MARKET_CHAOS", "Exposed By The Tide V2", "The tide went out, and you were caught swimming naked, {{currentDrawdownFromATH}} below your peak."),
    ("BENCHMARK_COMPARISON", "The Cost Of Arrogance", "Being {{currentDrawdownFromATH}} down is the cost of arrogance. {{benchmarkName}}'s {{benchmarkReturnPercent}} is the alternative you rejected."),
    ("DRAWDOWN_STATUS", "The Graveyard Of Gains", "Your portfolio is the graveyard of its all-time high, currently buried {{currentDrawdownFromATH}} deep."),
    ("ABSOLUTE_RETURN", "Vaporized Wealth", "{{currentDrawdownFromATH}} of your peak wealth has vaporized. Today's {{portfolioReturnPercent}} won't condense it back."),
    ("GENERAL_MARKET_CHAOS", "Crushed By Reality", "You thought you had an edge, but you were crushed by reality, resulting in a {{currentDrawdownFromATH}} drawdown."),
    ("BENCHMARK_COMPARISON", "The Stupidity Tax", "The {{currentDrawdownFromATH}} you lost from the peak is a stupidity tax. {{benchmarkName}} at {{benchmarkReturnPercent}} is tax-free."),
    ("DRAWDOWN_STATUS", "A Black Hole", "Your portfolio is a {{currentDrawdownFromATH}} black hole. Light and capital cannot escape it."),
    ("ABSOLUTE_RETURN", "A Bitter Pill V2", "Swallow the pill: you are {{currentDrawdownFromATH}} below your peak. Your {{portfolioReturnPercent}} return today is meaningless."),
    ("GENERAL_MARKET_CHAOS", "Market Enforced Reality", "The market has enforced a brutal reality check, dropping you {{currentDrawdownFromATH}} from your delusions."),
    ("BENCHMARK_COMPARISON", "Comparative Disaster", "You are {{currentDrawdownFromATH}} down. Compare that disaster to {{benchmarkName}}'s {{benchmarkReturnPercent}}."),
    ("DRAWDOWN_STATUS", "The Distant Mirage V2", "Your all-time high is a {{athDistancePercent}} mirage. You are stranded in the desert."),
    ("ABSOLUTE_RETURN", "A Harsh Correction V2", "This {{currentDrawdownFromATH}} drop is a harsh correction of your inflated ego. Today's {{portfolioReturnPercent}} is irrelevant."),
    ("GENERAL_MARKET_CHAOS", "The Casino Wins", "The market casino always wins, taking back {{currentDrawdownFromATH}} of your chips permanently."),
    ("BENCHMARK_COMPARISON", "The Index's Revenge V2", "{{benchmarkName}} is getting revenge. You are {{currentDrawdownFromATH}} off your high, while it does {{benchmarkReturnPercent}}."),
    ("DRAWDOWN_STATUS", "A Masterclass In Wealth Destruction", "You have masterfully lost {{currentDrawdownFromATH}} from your peak. A breathtaking display of incompetence.")
]

for i, (angle, title, msg) in enumerate(brutal_jokes):
    templates.append({
        "templateId": f"drawdown_significant_v2_brutal_{angle}_{i+1:03d}",
        "scenarioKey": "DRAWDOWN_SIGNIFICANT",
        "tone": "roast",
        "intensity": "brutal",
        "messageAngle": angle,
        "structureFamily": "BUG_REPORT",
        "metaphorCategory": "SOFTWARE",
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
    ("DRAWDOWN_STATUS", "Holding The Heavy Bags", "You are {{currentDrawdownFromATH}} off the ATH. These bags are lead, anon. Lift with your knees."),
    ("ABSOLUTE_RETURN", "Rekt By The Chop V2", "Down {{currentDrawdownFromATH}} from the top. The chop is liquidating your soul. Today's {{portfolioReturnPercent}} is a trap."),
    ("GENERAL_MARKET_CHAOS", "Orbital Nuke", "The market dropped an orbital nuke on your portfolio. {{currentDrawdownFromATH}} down. NGMI."),
    ("BENCHMARK_COMPARISON", "Boomers Laughing", "You are {{currentDrawdownFromATH}} down while the boomer {{benchmarkName}} does {{benchmarkReturnPercent}}. The timeline is laughing at you."),
    ("DRAWDOWN_STATUS", "The {{athDistancePercent}} Squeeze V2", "You need a {{athDistancePercent}} god candle to survive. The copium tank is empty."),
    ("ABSOLUTE_RETURN", "Liquidated Dreams V2", "{{currentDrawdownFromATH}} of your peak net worth vanished. Staring at today's {{portfolioReturnPercent}} won't un-rekt you."),
    ("GENERAL_MARKET_CHAOS", "PvP Market Survior V2", "The PvP market took {{currentDrawdownFromATH}} of your HP. Use a medkit before you get fully rugged."),
    ("BENCHMARK_COMPARISON", "Chad Index Survives V2", "The Chad {{benchmarkName}} printed {{benchmarkReturnPercent}} while your bags are {{currentDrawdownFromATH}} off the ATH. Brutal."),
    ("DRAWDOWN_STATUS", "Down Horrendously", "You are down horrendously. {{currentDrawdownFromATH}} off the high. Log off and go outside."),
    ("ABSOLUTE_RETURN", "Fading The Top V2", "You faded your own ATH by {{currentDrawdownFromATH}}. Today's {{portfolioReturnPercent}} is a fakeout."),
    ("GENERAL_MARKET_CHAOS", "Ape Tears V2", "The timeline is drowning in ape tears. You are {{currentDrawdownFromATH}} down from the absolute top."),
    ("BENCHMARK_COMPARISON", "Tradfi Mockery V2", "The tradfi {{benchmarkName}} is mocking your {{currentDrawdownFromATH}} drawdown with its {{benchmarkReturnPercent}}. Uninstall."),
    ("DRAWDOWN_STATUS", "The Copium Climb V2", "Huffing raw copium hoping for a {{athDistancePercent}} pump to save you. Godspeed."),
    ("ABSOLUTE_RETURN", "Wealth Deleted", "You deleted {{currentDrawdownFromATH}} of wealth. At least you have a {{portfolioReturnPercent}} green candle today to look at."),
    ("GENERAL_MARKET_CHAOS", "Bear Market Vibes V2", "The vibes are terrible. You are {{currentDrawdownFromATH}} off the peak. Shut the laptop.")
]

for i, (angle, title, msg) in enumerate(degen_jokes):
    templates.append({
        "templateId": f"drawdown_significant_v2_degen_{angle}_{i+1:03d}",
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

print(f"Generated {len(templates)} templates for DRAWDOWN_SIGNIFICANT (V2) and saved to cm.txt")
