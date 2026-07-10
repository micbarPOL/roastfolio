#!/usr/bin/env python3
import json
import os
import sys
from collections import defaultdict

# Add lambda dir to path to use roast_history module if needed
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
from roast_history import is_too_similar_to_recent_message

def load_templates():
    filepath = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'roast_templates.json')
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find templates file at {filepath}")
        sys.exit(1)

def print_header(title):
    print(f"\n{'='*50}\n{title}\n{'='*50}")

def main():
    templates = load_templates()
    
    total_templates = len(templates)
    
    # Track statistics
    by_scenario = defaultdict(int)
    by_intensity = defaultdict(int)
    by_tone = defaultdict(int)
    by_angle = defaultdict(int)
    
    # Store message templates for duplicate/similarity checking
    messages = []
    
    # For safety checking
    forbidden_words = ["buy", "sell", "double down", "slur", "all-in", "leverage"]
    failed_safety = []
    invalid_placeholders = []
    missing_fields = []
    
    # Required fields
    required_keys = ["templateId", "scenarioKey", "intensity", "tone", "messageAngle", "messageTemplate", "titleTemplate"]
    
    # Analyze all templates
    for t in templates:
        scenario = t.get("scenarioKey", "UNKNOWN")
        intensity = t.get("intensity", "UNKNOWN")
        tone = t.get("tone", "UNKNOWN")
        angle = t.get("messageAngle", "UNKNOWN")
        
        by_scenario[scenario] += 1
        by_intensity[intensity] += 1
        by_tone[tone] += 1
        by_angle[angle] += 1
        
        msg = t.get("messageTemplate", "")
        messages.append((t.get("templateId"), msg))
        
        # Safety Check
        msg_lower = msg.lower()
        for fw in forbidden_words:
            if fw in msg_lower:
                failed_safety.append((t.get("templateId"), fw))
                
        # Placeholder Check (simple matching braces check)
        if msg.count("{{") != msg.count("}}"):
            invalid_placeholders.append(t.get("templateId"))
            
        # Missing fields check
        missing = [k for k in required_keys if k not in t or t[k] is None]
        if missing:
            missing_fields.append((t.get("templateId"), missing))

    print_header("Roastfolio Template Coverage Report")
    
    print(f"Total Templates: {total_templates}")
    
    print_header("Templates by Scenario")
    for s, count in sorted(by_scenario.items(), key=lambda x: x[1], reverse=True):
        print(f"{s.ljust(40)}: {count}")
        
    print_header("Templates by Intensity")
    for i, count in sorted(by_intensity.items(), key=lambda x: x[1], reverse=True):
        print(f"{i.ljust(15)}: {count}")
        
    print_header("Templates by Tone")
    for t, count in sorted(by_tone.items(), key=lambda x: x[1], reverse=True):
        print(f"{t.ljust(15)}: {count}")
        
    print_header("Templates by Message Angle")
    for a, count in sorted(by_angle.items(), key=lambda x: x[1], reverse=True):
        print(f"{a.ljust(25)}: {count}")
        
    print_header("Coverage Violations")
    violations = 0
    
    # Specific coverage rules
    for s, count in by_scenario.items():
        if count < 20 and s not in ["UNKNOWN", "NO_MEANINGFUL_CHANGE", "NO_CHANGE"]:
            print(f"[WARN] Scenario '{s}' has only {count} templates. (Goal: >=20)")
            violations += 1
            
    if by_scenario.get("NO_MEANINGFUL_CHANGE", 0) < 15:
        print(f"[WARN] NO_MEANINGFUL_CHANGE has only {by_scenario.get('NO_MEANINGFUL_CHANGE', 0)} templates. (Goal: >=15)")
        violations += 1
        
    # Check if USER_NEGATIVE_BENCHMARK_POSITIVE has high coverage
    unbp_count = by_scenario.get("USER_NEGATIVE_BENCHMARK_POSITIVE", 0)
    if unbp_count < 30:
        print(f"[WARN] USER_NEGATIVE_BENCHMARK_POSITIVE has {unbp_count} templates. This should have high coverage.")
        violations += 1
        
    if violations == 0:
        print("None detected.")
        
    print_header("Quality & Safety Issues")
    issues = 0
    
    if failed_safety:
        print(f"FAILED SAFETY VALIDATION: {len(failed_safety)}")
        for tid, fw in failed_safety:
            print(f"  - {tid} contains '{fw}'")
        issues += 1
        
    if invalid_placeholders:
        print(f"INVALID PLACEHOLDERS: {len(invalid_placeholders)}")
        for tid in invalid_placeholders:
            print(f"  - {tid}")
        issues += 1
        
    if missing_fields:
        print(f"MISSING FIELDS: {len(missing_fields)}")
        for tid, missing in missing_fields:
            print(f"  - {tid} missing: {missing}")
        issues += 1
        
    # Check exact duplicates
    msg_texts = [m for _, m in messages]
    duplicates = len(msg_texts) - len(set(msg_texts))
    if duplicates > 0:
        print(f"EXACT DUPLICATES: {duplicates} duplicate message templates found.")
        issues += 1
        
    if issues == 0:
        print("No safety, validation, or duplicate issues detected.")
        
    print("\nReport Complete.\n")

if __name__ == "__main__":
    main()
