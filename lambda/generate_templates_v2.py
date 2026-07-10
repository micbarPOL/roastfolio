import json
import uuid
import random
import sys
import os

# Add lambda to path for similarity_detector if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from similarity_detector import isRoastTooSimilar

# Dimensions
SCENARIOS = [
    "BOTH_NEGATIVE_USER_BETTER", "BOTH_NEGATIVE_USER_WORSE",
    "BOTH_POSITIVE_USER_BETTER", "BOTH_POSITIVE_USER_WORSE",
    "USER_POSITIVE_BENCHMARK_NEGATIVE", "USER_NEGATIVE_BENCHMARK_POSITIVE",
    "BOTH_FLAT", "USER_OUTPERFORMED_BY_SMALL_MARGIN",
    "USER_OUTPERFORMED_BY_MEDIUM_MARGIN", "USER_OUTPERFORMED_BY_LARGE_MARGIN",
    "USER_UNDERPERFORMED_BY_SMALL_MARGIN", "USER_UNDERPERFORMED_BY_MEDIUM_MARGIN",
    "USER_UNDERPERFORMED_BY_LARGE_MARGIN", "NEW_ATH_DAY", "NEAR_ATH",
    "DRAWDOWN_MILD", "DRAWDOWN_SIGNIFICANT", "DRAWDOWN_SEVERE",
    "BEST_ASSET_CARRIED_PORTFOLIO", "WORST_ASSET_DRAGGED_PORTFOLIO",
    "DEPOSIT_POSITIVE_BEHAVIOR", "WITHDRAWAL_DETECTED", "NO_MEANINGFUL_CHANGE",
    "MONTHLY_BOTH_POSITIVE_USER_BETTER", "MONTHLY_BOTH_POSITIVE_USER_WORSE",
    "MONTHLY_BOTH_NEGATIVE_USER_BETTER", "MONTHLY_BOTH_NEGATIVE_USER_WORSE",
    "MONTHLY_USER_POSITIVE_BENCHMARK_NEGATIVE", "MONTHLY_USER_NEGATIVE_BENCHMARK_POSITIVE",
    "MONTHLY_FLAT"
]

HIGH_PRIORITY_SCENARIOS = [
    "BOTH_NEGATIVE_USER_WORSE", "BOTH_POSITIVE_USER_WORSE", 
    "USER_NEGATIVE_BENCHMARK_POSITIVE", "USER_UNDERPERFORMED_BY_LARGE_MARGIN", 
    "DRAWDOWN_SEVERE", "WORST_ASSET_DRAGGED_PORTFOLIO", 
    "USER_POSITIVE_BENCHMARK_NEGATIVE", "NEW_ATH_DAY",
    "BOTH_NEGATIVE_USER_BETTER", "NO_MEANINGFUL_CHANGE", "BOTH_FLAT"
]

INTENSITIES = ["gentle", "sarcastic", "brutal", "degen"]

ANGLES = [
    "BENCHMARK_COMPARISON", "ABSOLUTE_RETURN", "RELATIVE_RETURN",
    "BEST_ASSET", "WORST_ASSET", "ATH_STATUS", "DRAWDOWN_STATUS",
    "DEPOSIT_DISCIPLINE", "WITHDRAWAL_BEHAVIOR", "VOLATILITY", "NO_CHANGE"
]

STRUCTURE_FAMILIES = [
    "direct_comparison", "fake_award", "mock_analyst_note", "emergency_broadcast",
    "sports_commentary", "therapy_session", "courtroom_verdict", "weather_report",
    "product_review", "performance_review", "medieval_prophecy", "bug_report",
    "status_update", "achievement_unlocked", "autopsy_report"
]

METAPHOR_CATEGORIES = [
    "spreadsheet", "weather", "sports", "office_politics", "school_report",
    "gaming", "cooking", "transportation", "bureaucracy", "reality_tv",
    "medieval_kingdom", "software_bugs"
]

TITLES_BY_STRUCTURE = {
    "direct_comparison": ["Side By Side", "The Numbers Don't Lie", "Against The Benchmark", "Comparison Time", "A Direct Look"],
    "fake_award": ["And The Award Goes To...", "Participation Trophy", "First Place In Losing", "Gold Star Effort", "Achievement Unlocked?"],
    "mock_analyst_note": ["Analyst Downgrade", "Market Memo", "Urgent Update", "Financial Review", "Desk Note"],
    "emergency_broadcast": ["Emergency Alert", "Warning Issued", "Critical Update", "Seek Shelter", "System Failure"],
    "sports_commentary": ["Post-Game Analysis", "On The Sidelines", "Fumbled The Bag", "A Swing And A Miss", "Checking The Scoreboard"],
    "therapy_session": ["Let's Talk About It", "Financial Therapy", "Coping Mechanism", "A Safe Space", "Deep Breaths"],
    "courtroom_verdict": ["The Verdict Is In", "Guilty Of Underperformance", "Court Is In Session", "Final Judgment", "Evidence Presented"],
    "weather_report": ["Storm Warning", "Sunny With A Chance Of Red", "Market Climate", "Checking The Radar", "A Cold Front"],
    "product_review": ["One Star Review", "Would Not Recommend", "Defective Portfolio", "Return To Sender", "Poor Quality"],
    "performance_review": ["Quarterly Review", "Needs Improvement", "PIP Initiated", "Employee Of The Month?", "Meeting Expectations"],
    "medieval_prophecy": ["The King's Decree", "A Dark Omen", "The Oracle Speaks", "Winter Is Here", "Peasant Returns"],
    "bug_report": ["Error 404: Returns Not Found", "Critical Bug", "System Crash", "Glitch In The Matrix", "Patch Required"],
    "status_update": ["Current Status", "Quick Update", "Where We Stand", "Just Checking In", "Daily Ping"],
    "achievement_unlocked": ["Achievement Unlocked", "Level Up", "New High Score", "Game Over", "Quest Failed"],
    "autopsy_report": ["Post-Mortem", "Examining The Damage", "What Went Wrong", "Cause Of Failure", "Tracing The Wreckage"]
}

SCENARIO_CONTEXTS = {
    "BOTH_NEGATIVE_USER_BETTER": ["you lost money ({{portfolioReturnPercent}}%), but less than the market ({{benchmarkReturnPercent}}%)"],
    "BOTH_NEGATIVE_USER_WORSE": ["you lost {{portfolioReturnPercent}}%, completely trailing the {{benchmarkReturnPercent}}% market drop"],
    "BOTH_POSITIVE_USER_BETTER": ["you gained {{portfolioReturnPercent}}%, beating the {{benchmarkReturnPercent}}% market"],
    "BOTH_POSITIVE_USER_WORSE": ["the market gained {{benchmarkReturnPercent}}% but you only managed {{portfolioReturnPercent}}%"],
    "USER_POSITIVE_BENCHMARK_NEGATIVE": ["you gained {{portfolioReturnPercent}}% while the market dropped {{benchmarkReturnPercent}}%"],
    "USER_NEGATIVE_BENCHMARK_POSITIVE": ["you lost {{portfolioReturnPercent}}% while the market handed out a {{benchmarkReturnPercent}}% gain"],
    "BOTH_FLAT": ["nothing happened today"],
    "USER_OUTPERFORMED_BY_SMALL_MARGIN": ["you barely beat the market by {{relativePerformancePercent}}%"],
    "USER_OUTPERFORMED_BY_MEDIUM_MARGIN": ["you beat the market by a solid {{relativePerformancePercent}}%"],
    "USER_OUTPERFORMED_BY_LARGE_MARGIN": ["you crushed the market by {{relativePerformancePercent}}%"],
    "USER_UNDERPERFORMED_BY_SMALL_MARGIN": ["you lagged the market by a tiny {{relativePerformancePercent}}%"],
    "USER_UNDERPERFORMED_BY_MEDIUM_MARGIN": ["you trailed the benchmark by {{relativePerformancePercent}}%"],
    "USER_UNDERPERFORMED_BY_LARGE_MARGIN": ["you vastly underperformed the market by {{relativePerformancePercent}}%"],
    "NEW_ATH_DAY": ["you hit a new all-time high"],
    "NEAR_ATH": ["you are hovering right near your all-time high"],
    "DRAWDOWN_MILD": ["you slipped {{currentDrawdownFromATH}} from the peak"],
    "DRAWDOWN_SIGNIFICANT": ["you are down {{currentDrawdownFromATH}} from the highs"],
    "DRAWDOWN_SEVERE": ["your portfolio collapsed {{currentDrawdownFromATH}} from the top"],
    "BEST_ASSET_CARRIED_PORTFOLIO": ["{{dailyBestAsset}} was the only reason you survived"],
    "WORST_ASSET_DRAGGED_PORTFOLIO": ["{{dailyWorstAsset}} dragged everything down"],
    "DEPOSIT_POSITIVE_BEHAVIOR": ["you added fresh capital"],
    "WITHDRAWAL_DETECTED": ["you pulled funds out of the market"],
    "NO_MEANINGFUL_CHANGE": ["literally nothing changed"],
    "MONTHLY_BOTH_POSITIVE_USER_BETTER": ["you crushed the market this month with a {{monthlyReturnPercent}}% gain"],
    "MONTHLY_BOTH_POSITIVE_USER_WORSE": ["the market was up this month, but you only managed {{monthlyReturnPercent}}%"],
    "MONTHLY_BOTH_NEGATIVE_USER_BETTER": ["it was a bad month, but you lost less than the market"],
    "MONTHLY_BOTH_NEGATIVE_USER_WORSE": ["you underperformed the market during a terrible month"],
    "MONTHLY_USER_POSITIVE_BENCHMARK_NEGATIVE": ["you defied a red month with a {{monthlyReturnPercent}}% gain"],
    "MONTHLY_USER_NEGATIVE_BENCHMARK_POSITIVE": ["you managed to lose money in a green month"],
    "MONTHLY_FLAT": ["your portfolio went absolutely nowhere for 30 days"]
}

# Expand the templates dynamically
def generate_message(structure, metaphor, context, intensity):
    # A bit of logic to stitch them
    prefix = ""
    suffix = ""
    
    if structure == "direct_comparison":
        prefix = random.choice(["Looking closely,", "Comparing the data,", "Side by side,"])
        suffix = random.choice(["It is what it is.", "Numbers don't lie.", "Do better."])
    elif structure == "fake_award":
        prefix = random.choice(["Congratulations,", "Here is your trophy:", "A round of applause,"])
        suffix = random.choice(["Put it on your fridge.", "Be proud of this.", "What a legacy."])
    elif structure == "mock_analyst_note":
        prefix = random.choice(["Analyst downgrade:", "Memo to desk:", "Market update:"])
        suffix = random.choice(["Revise your thesis.", "Sell rating maintained.", "Client advised to stop."])
    elif structure == "emergency_broadcast":
        prefix = random.choice(["ALERT:", "This is not a drill:", "Warning:"])
        suffix = random.choice(["Evacuate immediately.", "Seek professional help.", "Stay indoors."])
    elif structure == "sports_commentary":
        prefix = random.choice(["Down on the field,", "Looking at the replay,", "In the post-game,"])
        suffix = random.choice(["They fumbled it.", "A terrible play.", "Better luck next season."])
    elif structure == "therapy_session":
        prefix = random.choice(["Let's explore this.", "How does it feel that", "Take a deep breath,"])
        suffix = random.choice(["We will work through this.", "Time heals all wounds.", "Acceptance is key."])
    elif structure == "courtroom_verdict":
        prefix = random.choice(["The jury has decided:", "Order in the court,", "Based on the evidence,"])
        suffix = random.choice(["Guilty as charged.", "Case closed.", "No appeal possible."])
    elif structure == "weather_report":
        prefix = random.choice(["Looking at the radar,", "A cold front is moving in,", "The forecast shows"])
        suffix = random.choice(["Bring an umbrella.", "Expect severe conditions.", "Stay warm out there."])
    elif structure == "product_review":
        prefix = random.choice(["One star.", "Would not recommend.", "Defective product:"])
        suffix = random.choice(["Requesting a refund.", "Terrible customer service.", "Do not buy."])
    elif structure == "performance_review":
        prefix = random.choice(["In your quarterly review,", "Regarding your performance,", "Let's look at your goals,"])
        suffix = random.choice(["PIP initiated.", "No bonus this year.", "We need to talk."])
    elif structure == "medieval_prophecy":
        prefix = random.choice(["The oracle foresaw this:", "Hear ye,", "A dark omen:"])
        suffix = random.choice(["Winter is here.", "The kingdom falls.", "Pray for mercy."])
    elif structure == "bug_report":
        prefix = random.choice(["Ticket #404:", "Critical error:", "System log:"])
        suffix = random.choice(["Won't fix.", "Working as intended?", "Reboot required."])
    elif structure == "status_update":
        prefix = random.choice(["Just checking in,", "Status:", "Quick update:"])
        suffix = random.choice(["End of report.", "Moving on.", "Nothing more to say."])
    elif structure == "achievement_unlocked":
        prefix = random.choice(["Achievement Unlocked:", "Level Up:", "New Title:"])
        suffix = random.choice(["0G awarded.", "Equip this badge.", "Try another game."])
    elif structure == "autopsy_report":
        prefix = random.choice(["Time of death:", "Examining the wreckage,", "The post-mortem reveals"])
        suffix = random.choice(["Cause: bad decisions.", "Case closed.", "Nothing could be done."])
    else:
        prefix = "Well,"
        suffix = "Okay then."

    return f"{prefix} {context}. {suffix}"

def generate_templates():
    templates = []
    seen_texts = set()
    
    # We want at least 1500 templates, distributed across SCENARIOS
    # High priority scenarios get more templates (50+)
    
    for scenario in SCENARIOS:
        is_hp = scenario in HIGH_PRIORITY_SCENARIOS
        target_count = 60 if is_hp else 15
        
        for i in range(target_count):
            intensity = random.choice(INTENSITIES)
            angle = random.choice(ANGLES)
            structure = random.choice(STRUCTURE_FAMILIES)
            metaphor = random.choice(METAPHOR_CATEGORIES)
            
            # Generate unique
            message = ""
            title = ""
            for _ in range(200):
                context = random.choice(SCENARIO_CONTEXTS.get(scenario, ["things happened"]))
                title = random.choice(TITLES_BY_STRUCTURE[structure]) + f" {random.choice(['!', '.', '...', '?', '!!'])}" 
                message = generate_message(structure, metaphor, context, intensity)
                
                # Simple dedup
                if message not in seen_texts:
                    seen_texts.add(message)
                    break
            
            tone = "roast"
            if "BETTER" in scenario or "NEW_ATH" in scenario or "DEPOSIT" in scenario or scenario == "USER_POSITIVE_BENCHMARK_NEGATIVE":
                tone = "praise" if random.random() > 0.3 else "mixed"
            elif scenario == "USER_NEGATIVE_BENCHMARK_POSITIVE" or "WORSE" in scenario or "DRAWDOWN" in scenario:
                tone = "roast" if random.random() > 0.3 else "mixed"
            elif "POSITIVE" in scenario:
                tone = "mixed"
            if "FLAT" in scenario or "NO_CHANGE" in scenario:
                tone = "neutral"
                
            # Avoid {{dailyBestAsset}} etc leaking if angle isn't supported, but validator handles that, actually wait:
            # We must ensure templates use context arrays correctly.
                
            t = {
                "templateId": f"gen_{scenario}_{intensity}_{i}_{str(uuid.uuid4())[:8]}",
                "scenarioKey": scenario,
                "tone": tone,
                "intensity": intensity,
                "messageAngle": angle,
                "structureFamily": structure,
                "metaphorCategory": metaphor,
                "cooldownDays": 14,
                "titleTemplate": title.strip(),
                "messageTemplate": message,
                "mainReasonTemplate": context.capitalize(),
                "suggestedFocusTemplate": f"Review your {angle.replace('_', ' ').lower()}"
            }
            templates.append(t)
            
    return templates

if __name__ == "__main__":
    templates = generate_templates()
    with open("roast_templates_test.json", "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2)
    print(f"Generated {len(templates)} templates.")
