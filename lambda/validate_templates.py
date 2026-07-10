import json
import os
import re
import sys
from collections import defaultdict

try:
    from similarity_detector import _get_opening_phrase, _normalize_text, _jaccard_similarity
except ImportError:
    # Handle if run from outside lambda dir
    sys.path.append(os.path.join(os.path.dirname(__file__)))
    from similarity_detector import _get_opening_phrase, _normalize_text, _jaccard_similarity

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

HIGH_PRIORITY_SCENARIOS = ["USER_NEGATIVE_BENCHMARK_POSITIVE", "NO_MEANINGFUL_CHANGE", "BOTH_NEGATIVE_USER_WORSE"]

INTENSITIES = ["gentle", "sarcastic", "brutal", "degen"]
ANGLES = [
    "BENCHMARK_COMPARISON", "ABSOLUTE_RETURN", "RELATIVE_RETURN",
    "BEST_ASSET", "WORST_ASSET", "ATH_STATUS", "DRAWDOWN_STATUS",
    "DEPOSIT_DISCIPLINE", "WITHDRAWAL_BEHAVIOR", "VOLATILITY", "NO_CHANGE"
]
TONES = ["praise", "neutral", "roast", "mixed"]

SUPPORTED_PLACEHOLDERS = [
    "{{portfolioValue}}", "{{portfolioReturnPercent}}", "{{benchmarkReturnPercent}}",
    "{{relativePerformancePercent}}", "{{bestAsset}}", "{{worstAsset}}",
    "{{bestAssetReturn}}", "{{worstAssetReturn}}", "{{currentDrawdownFromATH}}",
    "{{currency}}", "{{dailyBestAsset}}", "{{dailyWorstAsset}}", "{{monthlyReturnPercent}}"
]

FORBIDDEN_TERMS = ["buy", "sell", "hold", "leverage", "short", "all-in"]

def load_templates(filepath=None):
    if not filepath:
        filepath = os.path.join(os.path.dirname(__file__), 'roast_templates.json')
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate(filepath=None):
    try:
        templates = load_templates(filepath)
    except Exception as e:
        print(f"ERROR: Could not load templates. {e}")
        return False
        
    errors = []
    warnings = []
    
    total = len(templates)
    
    counts = {
        "scenarioKey": defaultdict(int),
        "intensity": defaultdict(int),
        "messageAngle": defaultdict(int),
        "tone": defaultdict(int)
    }
    
    seen_ids = set()
    seen_titles = defaultdict(int)
    seen_messages = set()
    seen_openings = defaultdict(int)
    
    coverage = defaultdict(lambda: {"intensities": set(), "angles": set(), "count": 0})
    
    # 1. Validation loop
    for t in templates:
        tid = t.get("templateId")
        scenario = t.get("scenarioKey")
        intensity = t.get("intensity")
        angle = t.get("messageAngle")
        tone = t.get("tone")
        title = t.get("titleTemplate")
        message = t.get("messageTemplate")
        
        # Missing fields
        if not tid: errors.append(f"Missing templateId in: {t}")
        if not title: errors.append(f"Missing titleTemplate in: {tid}")
        if not message: errors.append(f"Missing messageTemplate in: {tid}")
        
        # Duplicate IDs
        if tid in seen_ids:
            errors.append(f"Duplicate templateId: {tid}")
        seen_ids.add(tid)
        
        # Exact duplicate messages
        if message in seen_messages:
            errors.append(f"Duplicate messageTemplate exactly: '{message}' (ID: {tid})")
        seen_messages.add(message)
        
        # Titles
        if title:
            seen_titles[title] += 1
            
        # Openings
        if message:
            opening = _get_opening_phrase(message)
            if opening:
                seen_openings[opening] += 1
                
        # Unknown values
        if scenario not in SCENARIOS: errors.append(f"Unknown scenarioKey: {scenario} (ID: {tid})")
        if intensity not in INTENSITIES: errors.append(f"Unknown intensity: {intensity} (ID: {tid})")
        if angle not in ANGLES: errors.append(f"Unknown messageAngle: {angle} (ID: {tid})")
        if tone not in TONES: errors.append(f"Unknown tone: {tone} (ID: {tid})")
        
        # Financial advice terms
        if message:
            msg_lower = message.lower()
            for term in FORBIDDEN_TERMS:
                if re.search(r'\b' + term + r'\b', msg_lower):
                    errors.append(f"Forbidden financial term '{term}' found in message (ID: {tid})")
                    
        # Placeholders
        if message:
            placeholders = re.findall(r'\{\{.*?\}\}', message)
            for p in placeholders:
                if p not in SUPPORTED_PLACEHOLDERS:
                    errors.append(f"Unsupported placeholder '{p}' in message (ID: {tid})")
                    
        # Counts
        if scenario: counts["scenarioKey"][scenario] += 1
        if intensity: counts["intensity"][intensity] += 1
        if angle: counts["messageAngle"][angle] += 1
        if tone: counts["tone"][tone] += 1
        
        if scenario:
            coverage[scenario]["count"] += 1
            if intensity: coverage[scenario]["intensities"].add(intensity)
            if angle: coverage[scenario]["angles"].add(angle)

    # 2. Thresholds
    for title, c in seen_titles.items():
        if c > 30:
            errors.append(f"Title '{title}' used too many times globally ({c} times > 30)")
            
    for opening, c in seen_openings.items():
        if c > 60:
            errors.append(f"Opening phrase '{opening}' used too many times globally ({c} times > 60)")
            
    # 3. High Priority Scenarios Coverage
    for hp in HIGH_PRIORITY_SCENARIOS:
        c = coverage.get(hp, {"count": 0, "intensities": set(), "angles": set()})
        if c["count"] < 50:
            errors.append(f"High-priority scenario '{hp}' has low coverage ({c['count']} < 50)")
        if len(c["intensities"]) < 4:
            errors.append(f"High-priority scenario '{hp}' is missing intensities (has {len(c['intensities'])}/4)")
        if len(c["angles"]) < 4:
            errors.append(f"High-priority scenario '{hp}' is missing message angles (has {len(c['angles'])}/4)")
            
    # Print Coverage Summary
    print("\n--- COVERAGE SUMMARY ---")
    print(f"Total Templates: {total}")
    print("\nIntensities:")
    for k, v in counts["intensity"].items(): print(f"  {k}: {v}")
    print("\nTones:")
    for k, v in counts["tone"].items(): print(f"  {k}: {v}")
    
    print("\n--- ERRORS ---")
    if not errors:
        print("No critical errors found.")
    else:
        for e in errors[:20]: # cap print to avoid spam
            print(f"ERROR: {e}")
        if len(errors) > 20:
            print(f"... and {len(errors) - 20} more errors.")
            
    return len(errors) == 0

if __name__ == '__main__':
    success = validate()
    sys.exit(0 if success else 1)
