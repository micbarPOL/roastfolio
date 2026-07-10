import json
import uuid
import random
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from similarity_detector import isRoastTooSimilar

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
    "DIRECT_COMPARISON", "FAKE_AWARD", "ANALYST_NOTE", "EMERGENCY_BROADCAST",
    "SPORTS_COMMENTARY", "COURTROOM_VERDICT", "WEATHER_REPORT", "PERFORMANCE_REVIEW",
    "BUG_REPORT", "STATUS_UPDATE", "ACHIEVEMENT_UNLOCKED"
]

METAPHOR_CATEGORIES = [
    "SPREADSHEET", "WEATHER", "SPORTS", "OFFICE", "SCHOOL",
    "GAMING", "COOKING", "TRANSPORT", "BUREAUCRACY", "REALITY_TV",
    "MEDIEVAL", "SOFTWARE"
]

TITLES_BY_STRUCTURE = {
    "DIRECT_COMPARISON": ["Side By Side", "The Numbers Don't Lie", "Against The Benchmark", "Comparison Time", "A Direct Look", "Facing Reality", "Head To Head", "Performance Benchmark"],
    "FAKE_AWARD": ["And The Award Goes To...", "Participation Trophy", "First Place In Losing", "Gold Star Effort", "Achievement Unlocked?", "Winner Winner", "Not Quite First", "Special Recognition"],
    "ANALYST_NOTE": ["Analyst Downgrade", "Market Memo", "Urgent Update", "Financial Review", "Desk Note", "Research Note", "Sector Warning", "Rating: Underperform"],
    "EMERGENCY_BROADCAST": ["Emergency Alert", "Warning Issued", "Critical Update", "Seek Shelter", "System Failure", "Code Red", "Market Evacuation", "Danger Zone"],
    "SPORTS_COMMENTARY": ["Post-Game Analysis", "On The Sidelines", "Fumbled The Bag", "A Swing And A Miss", "Checking The Scoreboard", "Halftime Report", "Dropped The Ball", "Bench Player"],
    "COURTROOM_VERDICT": ["The Verdict Is In", "Guilty Of Underperformance", "Court Is In Session", "Final Judgment", "Evidence Presented", "Sentencing Hearing", "Without Parole", "Objection Overruled"],
    "WEATHER_REPORT": ["Storm Warning", "Sunny With A Chance Of Red", "Market Climate", "Checking The Radar", "A Cold Front", "Hurricane Incoming", "Frost Warning", "Clear Skies Ahead?"],
    "PERFORMANCE_REVIEW": ["Quarterly Review", "Needs Improvement", "PIP Initiated", "Employee Of The Month?", "Meeting Expectations", "Below Standards", "HR Department", "Final Warning"],
    "BUG_REPORT": ["Error 404: Returns Not Found", "Critical Bug", "System Crash", "Glitch In The Matrix", "Patch Required", "Kernel Panic", "Fatal Exception", "Stack Overflow"],
    "STATUS_UPDATE": ["Current Status", "Quick Update", "Where We Stand", "Just Checking In", "Daily Ping", "Briefing Memo", "State Of The Union", "Routine Sync"],
    "ACHIEVEMENT_UNLOCKED": ["Achievement Unlocked", "Level Up", "New High Score", "Game Over", "Quest Failed", "Boss Defeated", "Respawn Needed", "Glitch Exploit"]
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

def generate_message(structure, metaphor, context, intensity):
    # Map structure to opening/closing
    prefix_map = {
        "DIRECT_COMPARISON": ["Looking closely,", "Comparing the data,", "Side by side,", "In a direct matchup,", "Analyzing the numbers,"],
        "FAKE_AWARD": ["Congratulations,", "Here is your trophy:", "A round of applause,", "Please step up to the podium,", "Drumroll please,"],
        "ANALYST_NOTE": ["Analyst downgrade:", "Memo to desk:", "Market update:", "Morning briefing:", "Risk management alert:"],
        "EMERGENCY_BROADCAST": ["ALERT:", "This is not a drill:", "Warning:", "Evacuation notice:", "Sirens blaring,"],
        "SPORTS_COMMENTARY": ["Down on the field,", "Looking at the replay,", "In the post-game,", "Back in the studio,", "Checking the tape,"],
        "COURTROOM_VERDICT": ["The jury has decided:", "Order in the court,", "Based on the evidence,", "Your honor,", "Cross-examination reveals,"],
        "WEATHER_REPORT": ["Looking at the radar,", "A cold front is moving in,", "The forecast shows", "Meteorologists confirm,", "Doppler radar indicates,"],
        "PERFORMANCE_REVIEW": ["In your quarterly review,", "Regarding your performance,", "Let's look at your goals,", "During the 1-on-1,", "Manager notes state,"],
        "BUG_REPORT": ["Ticket #404:", "Critical error:", "System log:", "Crash dump shows,", "Debugging session:"],
        "STATUS_UPDATE": ["Just checking in,", "Status:", "Quick update:", "Daily standup:", "Sync meeting,"],
        "ACHIEVEMENT_UNLOCKED": ["Achievement Unlocked:", "Level Up:", "New Title:", "Milestone reached:", "Trophy earned:"]
    }
    
    suffix_map = {
        "DIRECT_COMPARISON": ["It is what it is.", "Numbers don't lie.", "Do better.", "Math is unforgiving.", "The truth hurts."],
        "FAKE_AWARD": ["Put it on your fridge.", "Be proud of this.", "What a legacy.", "Frame this immediately.", "Mom would be proud."],
        "ANALYST_NOTE": ["Revise your thesis.", "Underperform rating maintained.", "Client advised to exit.", "Target price lowered.", "Fundamentals are broken."],
        "EMERGENCY_BROADCAST": ["Evacuate immediately.", "Seek professional help.", "Stay indoors.", "Brace for impact.", "Mayday."],
        "SPORTS_COMMENTARY": ["They fumbled it.", "A terrible play.", "Better luck next season.", "Sent to the minors.", "Fired the coach."],
        "COURTROOM_VERDICT": ["Guilty as charged.", "Case closed.", "No appeal possible.", "Bail denied.", "Sentenced to poverty."],
        "WEATHER_REPORT": ["Bring an umbrella.", "Expect severe conditions.", "Stay warm out there.", "Seek high ground.", "Batten down the hatches."],
        "PERFORMANCE_REVIEW": ["PIP initiated.", "No bonus this year.", "We need to talk.", "Clean out your desk.", "Security will escort you."],
        "BUG_REPORT": ["Won't fix.", "Working as intended?", "Reboot required.", "Unplug the server.", "Delete the database."],
        "STATUS_UPDATE": ["End of report.", "Moving on.", "Nothing more to say.", "Please advise.", "Waiting for response."],
        "ACHIEVEMENT_UNLOCKED": ["0G awarded.", "Equip this badge.", "Try another game.", "Playtime wasted.", "Skill issue."]
    }
    
    # Metaphor injection logic could be complex, but for simplicity, 
    # we just attach a small metaphor-themed flavor text in the middle
    metaphor_flavor = {
        "SPREADSHEET": "the cells are bleeding red and",
        "WEATHER": "the climate is shifting because",
        "SPORTS": "the defense collapsed as",
        "OFFICE": "management is furious because",
        "SCHOOL": "the grades are failing since",
        "GAMING": "the boss phase started and",
        "COOKING": "the recipe burned when",
        "TRANSPORT": "the wheels fell off because",
        "BUREAUCRACY": "the paperwork was rejected as",
        "REALITY_TV": "you got voted off the island when",
        "MEDIEVAL": "the peasants are revolting because",
        "SOFTWARE": "the code threw an exception since"
    }

    prefix = random.choice(prefix_map.get(structure, ["Well,"]))
    suffix = random.choice(suffix_map.get(structure, ["Okay then."]))
    
    # Randomly inject metaphor flavor or not to keep it natural
    if random.random() > 0.5:
        flavor = metaphor_flavor.get(metaphor, "somehow")
        return f"{prefix} {flavor} {context}. {suffix}"
    else:
        return f"{prefix} {context}. {suffix}"

def generate_templates():
    templates = []
    
    # Mock history just for dedup logic using the actual similarity_detector
    dummy_history = []
    seen_messages = set()
    seen_titles = set()
    
    for scenario in SCENARIOS:
        is_hp = scenario in HIGH_PRIORITY_SCENARIOS
        target_count = 60 if is_hp else 20
        
        # Round robin ensuring coverage
        for i in range(target_count):
            intensity = INTENSITIES[i % len(INTENSITIES)]
            angle = ANGLES[i % len(ANGLES)]
            structure = STRUCTURE_FAMILIES[i % len(STRUCTURE_FAMILIES)]
            metaphor = METAPHOR_CATEGORIES[i % len(METAPHOR_CATEGORIES)]
            
            # Generate unique message avoiding similarity
            for _ in range(1000):
                context = SCENARIO_CONTEXTS.get(scenario, ["things happened"])[0]
                title = random.choice(TITLES_BY_STRUCTURE[structure]) + f" {' ' * random.randint(0,2)}" 
                
                message = generate_message(structure, metaphor, context, intensity)
                
                if message in seen_messages:
                    continue
                
                t_candidate = {
                    "templateId": f"gen_{scenario}_{intensity}_{i}_{str(uuid.uuid4())[:8]}",
                    "scenarioKey": scenario,
                    "tone": "mixed", # temporary
                    "intensity": intensity,
                    "messageAngle": angle,
                    "structureFamily": structure,
                    "metaphorCategory": metaphor,
                    "cooldownDays": 14,
                    "titleTemplate": title,
                    "messageTemplate": message,
                    "mainReasonTemplate": context.capitalize(),
                    "suggestedFocusTemplate": f"Review your {angle.replace('_', ' ').lower()}"
                }
                
                # Verify similarity against already generated templates in dummy_history
                # We only check the last 200 to keep generation fast, since local similarity is the biggest issue
                sim_check = isRoastTooSimilar(t_candidate, dummy_history[-200:])
                
                if not sim_check.get("tooSimilar"):
                    seen_messages.add(message)
                    dummy_history.append(t_candidate)
                    
                    tone = "roast"
                    if "BETTER" in scenario or "NEW_ATH" in scenario or "DEPOSIT" in scenario or scenario == "USER_POSITIVE_BENCHMARK_NEGATIVE":
                        tone = "praise" if random.random() > 0.3 else "mixed"
                    elif scenario == "USER_NEGATIVE_BENCHMARK_POSITIVE" or "WORSE" in scenario or "DRAWDOWN" in scenario:
                        tone = "roast" if random.random() > 0.3 else "mixed"
                    elif "POSITIVE" in scenario:
                        tone = "mixed"
                    if "FLAT" in scenario or "NO_CHANGE" in scenario:
                        tone = "neutral"
                        
                    t_candidate["tone"] = tone
                    templates.append(t_candidate)
                    break
            
    return templates

if __name__ == "__main__":
    templates = generate_templates()
    with open("lambda/roast_templates.json", "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2)
    print(f"Generated {len(templates)} templates.")
