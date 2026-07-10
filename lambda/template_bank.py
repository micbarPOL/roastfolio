import json
import os
import random
from datetime import datetime, timezone
from similarity_detector import isRoastTooSimilar

def load_templates(filepath=None):
    if not filepath:
        filepath = os.path.join(os.path.dirname(__file__), 'roast_templates.json')
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def filter_templates(templates, criteria, data):
    filtered = []
    missing_data = 0
    for t in templates:
        # Match filters
        if criteria.get('scenarioKey') and t.get('scenarioKey') != criteria['scenarioKey']:
            continue
        if criteria.get('tone') and t.get('tone') != criteria['tone']:
            continue
        if criteria.get('intensity') and t.get('intensity') != criteria['intensity']:
            continue
        if criteria.get('messageAngle') and t.get('messageAngle') and t.get('messageAngle') != criteria['messageAngle']:
            continue
            
        # Match requires (note: key is requiredData)
        has_all_reqs = True
        for req in t.get('requiredData', []):
            if req not in data or data[req] is None:
                has_all_reqs = False
                break
                
        if not has_all_reqs:
            missing_data += 1
            continue
            
        filtered.append(t)
    return filtered, missing_data

def apply_cooldowns(templates, history, check_titles=True, check_metadata=True):
    if not history:
        return templates
        
    allowed = []
    now = datetime.now(timezone.utc)
    
    last_used = {}
    for r in reversed(history):
        tid = r.get('templateId')
        dt_str = r.get('createdAt')
        if tid and dt_str:
            try:
                last_used[tid] = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            except:
                pass
                
    recent_titles = set(r.get('title') for r in history[:5] if r.get('title'))
    last_structure = history[0].get('structureFamily') if history and history[0].get('structureFamily') else None
    last_metaphor = history[0].get('metaphorCategory') if history and history[0].get('metaphorCategory') else None
    
    struct_counts = {}
    metaphor_counts = {}
    for r in history[:5]:
        s = r.get('structureFamily')
        m = r.get('metaphorCategory')
        if s: struct_counts[s] = struct_counts.get(s, 0) + 1
        if m: metaphor_counts[m] = metaphor_counts.get(m, 0) + 1
                
    for t in templates:
        t_id = t.get('templateId')
        if t_id in last_used:
            days_ago = (now - last_used[t_id]).days
            cooldown = t.get('cooldownDays', 14)
            if t.get('scenarioKey') == 'NO_MEANINGFUL_CHANGE':
                cooldown = 1
            if days_ago < cooldown:
                continue
                
        if check_titles:
            title_template = t.get('titleTemplate')
            if title_template and title_template in recent_titles:
                continue
                
        if check_metadata:
            t_struct = t.get('structureFamily')
            t_meta = t.get('metaphorCategory')
            
            if t_struct:
                if t_struct == last_structure:
                    continue
                if struct_counts.get(t_struct, 0) >= 2:
                    continue
                    
            if t_meta:
                if t_meta == last_metaphor:
                    continue
                if metaphor_counts.get(t_meta, 0) >= 2:
                    continue
                
        allowed.append(t)
        
    return allowed

def select_template(templates):
    if not templates:
        return None
        
    # Weighted random selection
    total_weight = sum(t.get('weight', 1.0) for t in templates)
    r = random.uniform(0, total_weight)
    
    upto = 0
    for t in templates:
        w = t.get('weight', 1.0)
        if upto + w >= r:
            return t
        upto += w
        
    return templates[-1]

def interpolate_template(template, data):
    import re
    result = dict(template)
    
    def replace_placeholders(text):
        if not text:
            return text
        
        def repl(match):
            key = match.group(1)
            val = data.get(key)
            if val is None:
                return f"{{{{{key}}}}}"
            return str(val)
            
        return re.sub(r'\{\{(\w+)\}\}', repl, text)
        
    result['titleTemplate'] = replace_placeholders(template.get('titleTemplate'))
    result['messageTemplate'] = replace_placeholders(template.get('messageTemplate'))
    result['mainReasonTemplate'] = replace_placeholders(template.get('mainReasonTemplate'))
    result['suggestedFocusTemplate'] = replace_placeholders(template.get('suggestedFocusTemplate'))
    
    return result

def get_best_template(criteria, data, history, templates=None):
    if templates is None:
        templates = load_templates()
        
    telemetry = {
        "eligibleTemplateCount": 0,
        "rejectedByCooldownCount": 0,
        "rejectedBySimilarityCount": 0,
        "fallbackReason": None
    }
    
    # Calculate base metrics for exact match to populate telemetry accurately
    exact_filtered, missing_data = filter_templates(templates, criteria, data)
    telemetry["eligibleTemplateCount"] = len(exact_filtered)
    
    if len(exact_filtered) == 0:
        if missing_data > 0:
            telemetry["fallbackReason"] = "missing required data"
        else:
            telemetry["fallbackReason"] = "scenario coverage gap"
    else:
        exact_allowed = apply_cooldowns(exact_filtered, history, True, True)
        telemetry["rejectedByCooldownCount"] = len(exact_filtered) - len(exact_allowed)
        if len(exact_allowed) == 0:
            telemetry["fallbackReason"] = "all templates blocked by cooldown"
        
    def try_cascade(check_titles, check_metadata):
        # 1. Exact match
        filtered, _ = filter_templates(templates, criteria, data)
        allowed = apply_cooldowns(filtered, history, check_titles, check_metadata)
        if allowed: return allowed, "Exact Match"
        
        # 2. Drop messageAngle
        if 'messageAngle' in criteria:
            c = dict(criteria)
            del c['messageAngle']
            filtered, _ = filter_templates(templates, c, data)
            allowed = apply_cooldowns(filtered, history, check_titles, check_metadata)
            if allowed: return allowed, "Dropped Angle"
            
        # 3. Drop intensity
        if 'intensity' in criteria:
            c = dict(criteria)
            if 'messageAngle' in c: del c['messageAngle']
            del c['intensity']
            filtered, _ = filter_templates(templates, c, data)
            allowed = apply_cooldowns(filtered, history, check_titles, check_metadata)
            if allowed: return allowed, "Dropped Intensity"
            
        # 4. Fallback to just tone
        if 'tone' in criteria:
            filtered, _ = filter_templates(templates, {'tone': criteria['tone']}, data)
            allowed = apply_cooldowns(filtered, history, check_titles, check_metadata)
            if allowed: return allowed, "Tone Only"
            
        return [], "None"

    # First try everything with title checking and metadata checking
    allowed, fallback_level = try_cascade(check_titles=True, check_metadata=True)
    
    # If that fails entirely, try again without title checking but keeping metadata checking
    if not allowed:
        allowed, fallback_level = try_cascade(check_titles=False, check_metadata=True)
        if allowed:
            fallback_level += " (Ignored Title Cooldown)"
            
    # If that fails, drop metadata checking as well
    if not allowed:
        allowed, fallback_level = try_cascade(check_titles=False, check_metadata=False)
        if allowed:
            fallback_level += " (Ignored Title and Metadata Cooldown)"
        
    if not allowed:
        if not telemetry["fallbackReason"]:
            telemetry["fallbackReason"] = "no eligible template"
        return None, telemetry
        
    # Try up to 5 candidates
    candidates = list(allowed)
    random.shuffle(candidates)
    
    rejected_count = 0
    rejection_reasons = []
    considered_ids = []
    
    for candidate_template in candidates[:5]:
        considered_ids.append(candidate_template.get("templateId"))
        interpolated = interpolate_template(candidate_template, data)
        sim_check = isRoastTooSimilar(interpolated, history)
        
        if not sim_check.get("tooSimilar"):
            # Attach debug metadata
            interpolated["_debug"] = {
                "source": "template",
                "fallbackLevel": fallback_level,
                "rejectedCandidateCount": rejected_count,
                "rejectionReasons": rejection_reasons,
                "recentTemplateIdsConsidered": considered_ids,
                "similarityScore": sim_check.get("similarityScore"),
                "selectedBecause": "Passed all similarity checks."
            }
            telemetry["rejectedBySimilarityCount"] = rejected_count
            telemetry["fallbackReason"] = None # Successfully found
            return interpolated, telemetry
        else:
            rejected_count += 1
            reason = sim_check.get('reason')
            score = sim_check.get('similarityScore')
            rejection_reasons.append(f"{reason} (Score: {score})")
            
    telemetry["rejectedBySimilarityCount"] = rejected_count
    telemetry["fallbackReason"] = "all templates too similar"
    return None, telemetry
