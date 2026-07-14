import argparse
import json
import glob
import os
import re
import sys
from collections import defaultdict

# Add current dir to path to import local modules
sys.path.append(os.path.dirname(__file__) or '.')
from validate_templates import SCENARIOS, INTENSITIES, ANGLES, TONES, SUPPORTED_PLACEHOLDERS, FORBIDDEN_TERMS
from similarity_detector import isRoastTooSimilar

# Extract valid families from existing bank
STRUCTURE_FAMILIES = [
    'ACHIEVEMENT_UNLOCKED', 'ANALYST_NOTE', 'BUG_REPORT', 'COURTROOM_VERDICT', 
    'DIRECT_COMPARISON', 'EMERGENCY_BROADCAST', 'FAKE_AWARD', 'INCIDENT_REPORT',
    'PERFORMANCE_REVIEW', 'PRIVATE_BANKER_NOTE', 'ROYAL_DECREE', 'SCIENTIFIC_OBSERVATION',
    'SPORTS_COMMENTARY', 'STATUS_UPDATE', 'WEATHER_REPORT'
]

METAPHOR_CATEGORIES = [
    'BANKING', 'BUREAUCRACY', 'COOKING', 'DETECTIVE', 'GAMING', 'MEDIEVAL', 
    'OFFICE', 'REALITY_TV', 'SCHOOL', 'SCIENCE', 'SOFTWARE', 'SPORTS', 
    'SPREADSHEET', 'THEATRE', 'TRANSPORT', 'WEATHER'
]

UNSAFE_WORDS = re.compile(r'\b(kill|suicide|rope|jump off|hang yourself|slit|bleach|bitch|cunt|dick|cock|pussy|asshole|faggot|retard)\b', re.IGNORECASE)

def _adapt_for_similarity(template: dict) -> dict:
    return {
        "title": template.get("titleTemplate", ""),
        "message": template.get("messageTemplate", "")
    }

def get_placeholders(text: str) -> set:
    return set(re.findall(r'\{\{([^}]+)\}\}', text))

def sort_key(item: dict) -> tuple:
    return (
        item.get("scenarioKey", ""),
        item.get("intensity", ""),
        item.get("messageAngle", ""),
        item.get("structureFamily", ""),
        item.get("metaphorCategory", ""),
        item.get("templateId", "")
    )

def main():
    parser = argparse.ArgumentParser(description="Import Roastfolio template packs.")
    parser.add_argument("--input", required=True, help="Directory containing new template packs (JSON files).")
    parser.add_argument("--output", required=True, help="Path to main roast_templates.json.")
    args = parser.parse_args()

    # 1. Load existing templates
    existing_templates = []
    if os.path.exists(args.output):
        with open(args.output, "r", encoding="utf-8") as f:
            try:
                existing_templates = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error loading existing output file: {e}")
                sys.exit(1)

    existing_ids = {t.get("templateId") for t in existing_templates if t.get("templateId")}
    existing_messages = {t.get("messageTemplate") for t in existing_templates if t.get("messageTemplate")}
    
    # Pre-adapt existing for similarity check
    recent_roasts = [_adapt_for_similarity(t) for t in existing_templates]

    # 2. Load all JSON files from --input
    input_files = glob.glob(os.path.join(args.input, "*.json"))
    incoming_templates = []
    for fp in input_files:
        with open(fp, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    incoming_templates.extend(data)
                elif isinstance(data, dict):
                    # Handle if the pack is a dict containing a list
                    for k, v in data.items():
                        if isinstance(v, list):
                            incoming_templates.extend(v)
            except json.JSONDecodeError as e:
                print(f"Skipping invalid JSON file: {fp} - {e}")

    attempted_count = len(incoming_templates)
    imported_count = 0
    rejected_count = 0
    rejections = []
    
    coverage_delta = {
        "byScenarioKey": defaultdict(int),
        "byIntensity": defaultdict(int),
        "byMessageAngle": defaultdict(int),
        "byStructureFamily": defaultdict(int),
        "byMetaphorCategory": defaultdict(int)
    }

    accepted_templates = []

    for t in incoming_templates:
        if not isinstance(t, dict):
            rejected_count += 1
            rejections.append({"templateId": "UNKNOWN", "reason": "Not a JSON object"})
            continue
            
        tid = t.get("templateId", "UNKNOWN")
        
        # 5. Reject duplicate templateId
        if tid in existing_ids:
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": "Duplicate templateId"})
            continue

        msg = t.get("messageTemplate", "")
        # 6. Reject duplicate messageTemplate
        if not msg:
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": "Missing messageTemplate"})
            continue

        if msg in existing_messages:
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": "Exact duplicate messageTemplate"})
            continue

        # 7. Reject near-duplicate messageTemplate
        cand_adapted = _adapt_for_similarity(t)
        sim_result = isRoastTooSimilar(cand_adapted, recent_roasts, {"lookbackCount": len(recent_roasts)})
        if sim_result.get("tooSimilar"):
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": f"Near-duplicate: {sim_result.get('reason')}"})
            continue

        # 8, 9, 10. Placeholders
        text_to_check = t.get("titleTemplate", "") + " " + msg + " " + t.get("mainReasonTemplate", "") + " " + (t.get("suggestedFocusTemplate") or "")
        placeholders_in_text = get_placeholders(text_to_check)
        
        req_data = set(t.get("requiredData", []) if isinstance(t.get("requiredData"), list) else [])
        
        # check against SUPPORTED_PLACEHOLDERS which has {{}} format
        unsupported = {p for p in placeholders_in_text if f"{{{{{p}}}}}" not in SUPPORTED_PLACEHOLDERS}
        if unsupported:
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": f"Unsupported placeholders: {unsupported}"})
            continue
            
        missing_from_req = placeholders_in_text - req_data
        if missing_from_req:
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": f"Placeholders in text but missing from requiredData: {missing_from_req}"})
            continue
            
        # Warning for unused requiredData (we do not reject, requirement 10 says "Warn")
        unused_req = req_data - placeholders_in_text
        if unused_req:
            print(f"WARNING: requiredData fields not used in text for {tid}: {unused_req}")

        # 11-16. Known Enums
        scenario = t.get("scenarioKey")
        if scenario not in SCENARIOS:
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": f"Unknown scenarioKey: {scenario}"})
            continue
            
        tone = t.get("tone")
        if tone not in TONES:
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": f"Unknown tone: {tone}"})
            continue
            
        intensity = t.get("intensity")
        if intensity not in INTENSITIES:
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": f"Unknown intensity: {intensity}"})
            continue
            
        angle = t.get("messageAngle")
        if angle not in ANGLES:
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": f"Unknown messageAngle: {angle}"})
            continue
            
        # Removed structureFamily validation
        structure = t.get("structureFamily")
            
        # Removed metaphorCategory validation
        metaphor = t.get("metaphorCategory")

        # 17. Reject unsafe financial advice
        msg_lower = msg.lower()
        has_advice = False
        for term in FORBIDDEN_TERMS:
            if re.search(r'\b' + term + r'\b', msg_lower):
                has_advice = True
                break
        if has_advice:
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": "Direct financial advice detected"})
            continue
            
        # 18. Reject explicit profanity
        if UNSAFE_WORDS.search(msg) or UNSAFE_WORDS.search(t.get("titleTemplate", "")):
            rejected_count += 1
            rejections.append({"templateId": tid, "reason": "Explicit profanity/vulgarity detected"})
            continue

        # Passed all checks
        accepted_templates.append(t)
        existing_ids.add(tid)
        existing_messages.add(msg)
        recent_roasts.append(cand_adapted)
        imported_count += 1
        
        coverage_delta["byScenarioKey"][scenario] += 1
        coverage_delta["byIntensity"][intensity] += 1
        coverage_delta["byMessageAngle"][angle] += 1
        coverage_delta["byStructureFamily"][structure] += 1
        coverage_delta["byMetaphorCategory"][metaphor] += 1

    # 19. Merge valid templates
    final_templates = existing_templates + accepted_templates
    
    # 20. Sort output deterministically
    final_templates.sort(key=sort_key)
    
    # 21. Save the updated roast_templates.json
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(final_templates, f, indent=2)
        
    # 22. Create an import report
    report = {
        "existingCount": len(existing_templates),
        "attemptedImportCount": attempted_count,
        "importedCount": imported_count,
        "rejectedCount": rejected_count,
        "finalCount": len(final_templates),
        "rejections": rejections,
        "coverageDelta": coverage_delta
    }
    
    with open("template_import_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Import complete. Imported {imported_count}/{attempted_count}. Final bank size: {len(final_templates)}.")

if __name__ == '__main__':
    main()
