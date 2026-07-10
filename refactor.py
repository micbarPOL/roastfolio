import os

with open('lambda/roast_engine.py', 'r') as f:
    content = f.read()

# 1. Add os import and global variable
if 'import os\n' not in content:
    content = content.replace('import json\n', "import json\nimport os\n\nENABLE_RUNTIME_AI_ROASTS = os.environ.get('ENABLE_RUNTIME_AI_ROASTS', 'false').lower() == 'true'\n")

# 2. Update the template_bank call
content = content.replace(
    'template = template_bank.get_best_template(criteria, data, recent_history)',
    '''template, telemetry = template_bank.get_best_template(criteria, data, recent_history)
    telemetry["scenarioKey"] = scenario_key
    telemetry["intensity"] = roast_intensity
    telemetry["messageAngle"] = message_angle'''
)

# 3. Handle monthly roast
content = content.replace(
    'template = template_bank.get_best_template(criteria, data_payload, recent_history)',
    'template, telemetry = template_bank.get_best_template(criteria, data_payload, recent_history)'
)

# 4. Refactor the logic blocks in generate_daily_roast
old_block = '''    # 6. AI Generation Mode
    if enable_ai and not (mode == "NO_CHANGE" and not enable_ai_for_no_change):
        prompt = prompt_builder.build_roast_prompt(
            promptType="daily_roast",'''

new_block = '''    # 6. Use Template First
    if template:
        telemetry["source"] = "template"
        final_output = {
            "title": template.get("titleTemplate"),
            "message": template.get("messageTemplate"),
            "tone": template.get("tone", "neutral"),
            "severity": scenario_info.get("severity", 1),
            "mainReason": template.get("mainReasonTemplate"),
            "suggestedFocus": template.get("suggestedFocusTemplate"),
            "templateId": template.get("templateId"),
            "structureFamily": template.get("structureFamily"),
            "metaphorCategory": template.get("metaphorCategory")
        }
        if "_debug" in template:
            debug_metadata = template["_debug"]
            debug_metadata["scenarioKey"] = scenario_key
            debug_metadata["messageAngle"] = message_angle
            debug_metadata["templateId"] = template.get("templateId")

    # 6.5 AI Generation Mode (Fallback)
    if not final_output and ENABLE_RUNTIME_AI_ROASTS and not (mode == "NO_CHANGE" and not enable_ai_for_no_change):
        prompt = prompt_builder.build_roast_prompt(
            promptType="daily_roast",'''
            
content = content.replace(old_block, new_block)

# 5. Fix source tag if AI succeeds
ai_success_old = '''            # Passed checks!
            final_output = parsed
            final_output["templateId"] = None'''
ai_success_new = '''            # Passed checks!
            final_output = parsed
            final_output["templateId"] = None
            telemetry["source"] = "ai"'''
content = content.replace(ai_success_old, ai_success_new)

# 6. Refactor the Deterministic fallback logic
old_fallback_block = '''    # 7. Fallback to Template if AI failed or is disabled
    if not final_output:
        if template:
            final_output = {
                "title": template.get("titleTemplate"),
                "message": template.get("messageTemplate"),
                "tone": template.get("tone", "neutral"),
                "severity": scenario_info.get("severity", 1),
                "mainReason": template.get("mainReasonTemplate"),
                "suggestedFocus": template.get("suggestedFocusTemplate"),
                "templateId": template.get("templateId"),
                "structureFamily": template.get("structureFamily"),
                "metaphorCategory": template.get("metaphorCategory")
            }
            if "_debug" in template:
                debug_metadata = template["_debug"]
                debug_metadata["scenarioKey"] = scenario_key
                debug_metadata["messageAngle"] = message_angle
                debug_metadata["templateId"] = template.get("templateId")
        else:
            # Absolute fallback if even template bank fails (shouldn't happen with a populated bank)
            final_output = {
                "title": "Portfolio Update",
                "message": "We couldn't generate a fresh roast right now. Rest assured, you are probably still underperforming.",
                "tone": "neutral",
                "severity": 1,
                "mainReason": "System error",
                "suggestedFocus": None,
                "templateId": None,
                "structureFamily": None,
                "metaphorCategory": None
            }
            debug_metadata = {
                "source": "fallback",
                "scenarioKey": scenario_key,
                "messageAngle": message_angle,
                "templateId": None,
                "fallbackLevel": "Absolute Fallback",
                "similarityScore": None,
                "rejectedCandidateCount": 0,
                "rejectionReasons": [],
                "recentTemplateIdsConsidered": [],
                "selectedBecause": "All templates and AI failed."
            }'''

new_fallback_block = '''    # 7. Absolute Fallback if all else fails
    if not final_output:
        telemetry["source"] = "deterministic_fallback"
        final_output = {
            "title": "Portfolio Update",
            "message": "We couldn't generate a fresh roast right now. Rest assured, you are probably still underperforming.",
            "tone": "neutral",
            "severity": 1,
            "mainReason": "System error",
            "suggestedFocus": None,
            "templateId": None,
            "structureFamily": None,
            "metaphorCategory": None
        }
        debug_metadata = {
            "source": "fallback",
            "scenarioKey": scenario_key,
            "messageAngle": message_angle,
            "templateId": None,
            "fallbackLevel": "Absolute Fallback",
            "similarityScore": None,
            "rejectedCandidateCount": 0,
            "rejectionReasons": [],
            "recentTemplateIdsConsidered": [],
            "selectedBecause": "All templates and AI failed."
        }'''
content = content.replace(old_fallback_block, new_fallback_block)

# 7. Add telemetry to the final payload
enrich_old = '''    if enable_debug and debug_metadata:
        final_output["debug"] = debug_metadata
        roast_record["debug"] = debug_metadata'''
enrich_new = '''    roast_record["telemetry"] = telemetry
    final_output["telemetry"] = telemetry
    
    if enable_debug and debug_metadata:
        final_output["debug"] = debug_metadata
        roast_record["debug"] = debug_metadata'''
content = content.replace(enrich_old, enrich_new)

with open('lambda/roast_engine.py', 'w') as f:
    f.write(content)
