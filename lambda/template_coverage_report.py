import json
import os
import re
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(__file__) or '.')
from validate_templates import SCENARIOS, INTENSITIES, ANGLES, TONES, SUPPORTED_PLACEHOLDERS
from similarity_detector import _get_opening_phrase, _normalize_text, _get_trigrams, _jaccard_similarity, _get_distinctive_words

TARGETS_VERY_HIGH = {
    "NO_MEANINGFUL_CHANGE": 500,
    "USER_NEGATIVE_BENCHMARK_POSITIVE": 300,
    "BOTH_POSITIVE_USER_WORSE": 250,
    "USER_UNDERPERFORMED_BY_LARGE_MARGIN": 250,
    "BOTH_NEGATIVE_USER_BETTER": 250,
    "BOTH_POSITIVE_USER_BETTER": 250,
    "USER_POSITIVE_BENCHMARK_NEGATIVE": 250
}

TARGETS_MEDIUM = {
    "BOTH_NEGATIVE_USER_WORSE": 200,
    "DRAWDOWN_SIGNIFICANT": 150,
    "DRAWDOWN_SEVERE": 150,
    "WORST_ASSET_DRAGGED_PORTFOLIO": 150,
    "BEST_ASSET_CARRIED_PORTFOLIO": 150,
    "NEW_ATH_DAY": 150,
    "NEAR_ATH": 100,
    "DEPOSIT_POSITIVE_BEHAVIOR": 100
}

def is_near_duplicate(cand_msg, cand_title, recent_roasts):
    """Simplified similarity check for reporting."""
    cand_norm = cand_msg.strip().lower()
    cand_tokens = _normalize_text(cand_msg)
    cand_set = set(cand_tokens)
    cand_trigrams = _get_trigrams(cand_tokens)
    cand_opening = _get_opening_phrase(cand_msg)
    cand_distinctive = _get_distinctive_words(cand_tokens)
    
    for hist in recent_roasts:
        if cand_norm == hist['msg_norm']: continue
        
        # Opening phrase match
        if cand_opening and hist['opening'] and cand_opening == hist['opening']:
            return True
        
        # Token overlap
        if _jaccard_similarity(cand_set, hist['set']) > 0.6:
            return True
            
        # Trigram overlap
        if _jaccard_similarity(cand_trigrams, hist['trigrams']) > 0.3:
            return True
            
    return False

def get_placeholders(text: str) -> set:
    return set(re.findall(r'\{\{([^}]+)\}\}', text))

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=os.path.join(os.path.dirname(__file__), 'roast_templates.json'))
    args = parser.parse_args()
    
    template_file = args.input
    if not os.path.exists(template_file):
        print(f"File not found: {template_file}")
        sys.exit(1)

    try:
        with open(template_file, "r", encoding="utf-8") as f:
            templates = json.load(f)
    except json.JSONDecodeError as e:
        print(f"CRITICAL ERROR: Invalid JSON - {e}")
        sys.exit(1)

    # Hard failure tracking
    critical_errors = []
    
    # Report Data
    report = {
        "dimensions": {
            "total_enabled": 0,
            "total_disabled": 0,
            "by_scenario": defaultdict(int),
            "by_scenario_intensity": defaultdict(int),
            "by_scenario_angle": defaultdict(int),
            "by_scenario_structure": defaultdict(int),
            "by_scenario_metaphor": defaultdict(int),
            "by_tone": defaultdict(int),
            "by_cooldown": defaultdict(int),
            "repeated_title_count": 0,
            "repeated_opening_count": 0,
            "duplicate_message_count": 0,
            "near_duplicate_warning_count": 0,
            "unsupported_placeholder_count": 0,
            "scenarios_below_target": {},
            "intensities_missing": {},
            "angles_missing": {},
            "structures_overused": {},
            "metaphors_overused": {}
        }
    }

    seen_ids = set()
    seen_messages = set()
    title_counts = defaultdict(int)
    opening_counts = defaultdict(int)
    
    # Used for coverage checks
    scenarios_coverage = defaultdict(lambda: {
        "count": 0,
        "intensities": set(),
        "angles": set(),
        "structures": defaultdict(int),
        "metaphors": defaultdict(int)
    })

    recent_roasts = []

    for t in templates:
        tid = t.get("templateId")
        if not tid:
            continue
            
        if tid in seen_ids:
            critical_errors.append(f"Duplicate templateId: {tid}")
        seen_ids.add(tid)

        scenario = t.get("scenarioKey")
        intensity = t.get("intensity")
        angle = t.get("messageAngle")
        tone = t.get("tone")
        structure = t.get("structureFamily")
        metaphor = t.get("metaphorCategory")
        title = t.get("titleTemplate")
        msg = t.get("messageTemplate")

        if scenario and scenario not in SCENARIOS:
            critical_errors.append(f"Invalid scenarioKey: {scenario} (ID: {tid})")
        if intensity and intensity not in INTENSITIES:
            critical_errors.append(f"Invalid intensity: {intensity} (ID: {tid})")
        if tone and tone not in TONES:
            critical_errors.append(f"Invalid tone: {tone} (ID: {tid})")
        if angle and angle not in ANGLES:
            critical_errors.append(f"Invalid messageAngle: {angle} (ID: {tid})")

        text_to_check = (title or "") + " " + (msg or "") + " " + t.get("mainReasonTemplate", "") + " " + (t.get("suggestedFocusTemplate") or "")
        placeholders = get_placeholders(text_to_check)
        unsupported = {p for p in placeholders if f"{{{{{p}}}}}".lower() not in [sp.lower() for sp in SUPPORTED_PLACEHOLDERS]}
        if unsupported:
            critical_errors.append(f"Unsupported placeholders {unsupported} (ID: {tid})")
            report["dimensions"]["unsupported_placeholder_count"] += 1

        if t.get("enabled"):
            report["dimensions"]["total_enabled"] += 1
        else:
            report["dimensions"]["total_disabled"] += 1

        if scenario: report["dimensions"]["by_scenario"][scenario] += 1
        if scenario and intensity: report["dimensions"]["by_scenario_intensity"][f"{scenario}_{intensity}"] += 1
        if scenario and angle: report["dimensions"]["by_scenario_angle"][f"{scenario}_{angle}"] += 1
        if scenario and structure: report["dimensions"]["by_scenario_structure"][f"{scenario}_{structure}"] += 1
        if scenario and metaphor: report["dimensions"]["by_scenario_metaphor"][f"{scenario}_{metaphor}"] += 1
        if tone: report["dimensions"]["by_tone"][tone] += 1
        
        cd = t.get("cooldownDays")
        if cd is not None:
            bucket = f"{cd // 7 * 7}-{(cd // 7 + 1) * 7} days"
            report["dimensions"]["by_cooldown"][bucket] += 1

        if msg in seen_messages:
            report["dimensions"]["duplicate_message_count"] += 1
        seen_messages.add(msg)

        if title: title_counts[title] += 1
        if msg:
            opening = _get_opening_phrase(msg)
            if opening: opening_counts[opening] += 1
            
            # Prepare for similarity
            tokens = _normalize_text(msg)
            recent_roasts.append({
                "msg_norm": msg.strip().lower(),
                "opening": opening,
                "set": set(tokens),
                "trigrams": _get_trigrams(tokens)
            })

        if scenario:
            scenarios_coverage[scenario]["count"] += 1
            if intensity: scenarios_coverage[scenario]["intensities"].add(intensity)
            if angle: scenarios_coverage[scenario]["angles"].add(angle)
            if structure: scenarios_coverage[scenario]["structures"][structure] += 1
            if metaphor: scenarios_coverage[scenario]["metaphors"][metaphor] += 1

    if critical_errors:
        print("CRITICAL ERRORS FOUND. Failing analysis.")
        for e in critical_errors[:20]: print(f" - {e}")
        if len(critical_errors) > 20: print(f" - ... and {len(critical_errors) - 20} more.")
        sys.exit(1)

    # Post-process dimensions
    for title, c in title_counts.items():
        if c > 5: report["dimensions"]["repeated_title_count"] += 1

    for opening, c in opening_counts.items():
        if c > 5: report["dimensions"]["repeated_opening_count"] += 1

    # Similarity checks
    for idx, cand in enumerate(recent_roasts):
        # check against last 50
        history = recent_roasts[max(0, idx-50):idx]
        if is_near_duplicate(cand['msg_norm'], "", history):
            report["dimensions"]["near_duplicate_warning_count"] += 1

    # Targets
    warnings = []
    
    for scenario, target in {**TARGETS_VERY_HIGH, **TARGETS_MEDIUM}.items():
        cov = scenarios_coverage[scenario]
        
        if cov["count"] < target:
            report["dimensions"]["scenarios_below_target"][scenario] = f"{cov['count']}/{target}"
            warnings.append(f"Scenario {scenario} is below target ({cov['count']}/{target})")
            
        if scenario in TARGETS_VERY_HIGH:
            missing_int = set(INTENSITIES) - cov["intensities"]
            if missing_int:
                report["dimensions"]["intensities_missing"][scenario] = list(missing_int)
                warnings.append(f"Scenario {scenario} missing intensities: {missing_int}")
                
            if len(cov["angles"]) < 6:
                report["dimensions"]["angles_missing"][scenario] = f"Has {len(cov['angles'])}, wants >= 6"
                warnings.append(f"Scenario {scenario} lacks message angle diversity.")
                
            if len(cov["structures"]) < 8:
                report["dimensions"]["structures_overused"][scenario] = f"Has {len(cov['structures'])}, wants >= 8"
                warnings.append(f"Scenario {scenario} lacks structure family diversity.")
                
            if len(cov["metaphors"]) < 8:
                report["dimensions"]["metaphors_overused"][scenario] = f"Has {len(cov['metaphors'])}, wants >= 8"
                warnings.append(f"Scenario {scenario} lacks metaphor category diversity.")

    with open("template_coverage_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("=== TEMPLATE COVERAGE SUMMARY ===")
    print(f"Total Enabled: {report['dimensions']['total_enabled']}")
    print(f"Total Disabled: {report['dimensions']['total_disabled']}")
    print(f"Repeated Titles (>5): {report['dimensions']['repeated_title_count']}")
    print(f"Repeated Openings (>5): {report['dimensions']['repeated_opening_count']}")
    print(f"Duplicate Messages: {report['dimensions']['duplicate_message_count']}")
    print(f"Near-Duplicate Warnings: {report['dimensions']['near_duplicate_warning_count']}")
    print(f"Unsupported Placeholders: {report['dimensions']['unsupported_placeholder_count']}")
    
    print("\n--- Intensity Distribution by Scenario ---")
    for scenario in {**TARGETS_VERY_HIGH, **TARGETS_MEDIUM}.keys():
        total = scenarios_coverage[scenario]["count"]
        gentle = report["dimensions"]["by_scenario_intensity"].get(f"{scenario}_gentle", 0)
        sarcastic = report["dimensions"]["by_scenario_intensity"].get(f"{scenario}_sarcastic", 0)
        brutal = report["dimensions"]["by_scenario_intensity"].get(f"{scenario}_brutal", 0)
        degen = report["dimensions"]["by_scenario_intensity"].get(f"{scenario}_degen", 0)
        print(f" {scenario} ({total}): Gentle {gentle} | Sarcastic {sarcastic} | Brutal {brutal} | Degen {degen}")

    print("\n--- Coverage Warnings ---")
    if warnings:
        for w in warnings[:15]: print(f" [!] {w}")
        if len(warnings) > 15: print(f" ... and {len(warnings) - 15} more warnings.")
    else:
        print(" All high/medium frequency scenarios meet targets!")
        
    print("\nReport written to template_coverage_report.json")

if __name__ == '__main__':
    main()
