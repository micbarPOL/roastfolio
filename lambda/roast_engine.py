import json
import os
import re

ENABLE_RUNTIME_AI_ROASTS = os.environ.get('ENABLE_RUNTIME_AI_ROASTS', 'false').lower() == 'true'
import uuid
from datetime import datetime, timezone

import db
import scenario_classifier
import intraday_classifier
import roast_history
import template_bank
import prompt_builder
import angle_selector

def _build_template_vars(current: dict, bench: dict) -> dict:
    vars_dict = {}
    
    port_ret = current.get("dailyChangePct", 0.0)
    vars_dict["portfolioReturnPercent"] = f"{port_ret:+.1f}" if port_ret else "0.0"
    vars_dict["portfolioReturnAbs"] = f"{current.get('dailyChange', 0.0):+.2f}"
    vars_dict["portfolioValue"] = f"{current.get('portfolioValue', 0.0):.2f}"
    vars_dict["currency"] = current.get("currency", "PLN")
    vars_dict["isATH"] = "true" if current.get("isAth") else "false"
    
    if bench:
        bench_ret = bench.get("dailyChangePct", 0.0)
        vars_dict["benchmarkName"] = bench.get("benchmarkId", "WIG")
        vars_dict["benchmarkReturnPercent"] = f"{bench_ret:+.1f}" if bench_ret else "0.0"
        rel_perf = port_ret - bench_ret
        vars_dict["relativePerformancePercent"] = f"{rel_perf:+.1f}" if rel_perf else "0.0"
    
    top = current.get("dailyBestAsset")
    if top:
        vars_dict["topAsset"] = top
        vars_dict["dailyBestAsset"] = top
        vars_dict["topAssetReturn"] = f"{current.get('topAssetPct', 0.0):+.1f}"
        
    worst = current.get("dailyWorstAsset")
    if worst:
        vars_dict["worstAsset"] = worst
        vars_dict["dailyWorstAsset"] = worst
        vars_dict["worstAssetReturn"] = f"{current.get('worstAssetPct', 0.0):+.1f}"
        
    dd = current.get("drawdownPct", 0.0)
    vars_dict["drawdownPercent"] = f"{-dd:.1f}" if dd > 0 else "0.0"
    vars_dict["streakDays"] = str(current.get("streakDays", 0))
    
    return vars_dict

def _interpolate(template_str: str, vars_dict: dict) -> str:
    if not template_str:
        return template_str
    
    def replacer(match):
        key = match.group(1)
        val = vars_dict.get(key)
        return str(val) if val is not None else ""
        
    return re.sub(r"\{\{?(\w+)\}\}?", replacer, template_str)

def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Mock LLM call."""
    return ""

def _parse_llm_json(response: str) -> dict:
    try:
        return json.loads(response)
    except:
        return {}

def generate_daily_roast(user_id: str, current_snapshot: dict, benchmark_snapshot: dict, enable_ai: bool = False, enable_retry: bool = True, enable_ai_for_no_change: bool = False, enable_debug: bool = False) -> dict:
    # 1. Load user profile for settings
    profile = db.get_user(user_id) or {}
    settings = profile.get("settings", {})
    roast_intensity = settings.get("roastIntensity", "sarcastic")
    
    # 2. Build data context
    data = {
        "portfolio": current_snapshot,
        "benchmark": benchmark_snapshot,
        "is_ath": current_snapshot.get("isAth", False),
        "portfolio_return": current_snapshot.get("dailyChangePct", current_snapshot.get("portfolioReturnPercent", 0.0)),
        "benchmark_return": benchmark_snapshot.get("dailyChangePct", benchmark_snapshot.get("benchmarkReturnPercent", 0.0))
    }
    
    # 3. Classify Scenario
    scenario_info = scenario_classifier.classify_scenario(data)
    scenario_key = scenario_info["scenarioKey"]
    
    # 4. Fetch recent history & determine mode
    recent_history = roast_history.get_recent_history(user_id)
    last_roast = roast_history.get_latest_roast_today(user_id)
    
    mode = intraday_classifier.determine_commentary_mode(current_snapshot, last_roast, benchmark_snapshot)
    
    # 4.1 Debounce rapid requests to prevent flickering (e.g., lite then full API calls)
    if last_roast:
        last_time_str = last_roast.get('createdAt')
        if last_time_str:
            try:
                last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
                delta_minutes = (datetime.now(timezone.utc) - last_time).total_seconds() / 60
                
                # If generated less than 5 minutes ago and settings are the same, return it to avoid flickering
                last_intensity = last_roast.get("roastIntensity") or last_roast.get("intensity")
                if delta_minutes < 5 and last_intensity == roast_intensity:
                    return {
                        "title": last_roast.get("title", ""),
                        "message": last_roast.get("messageText", ""),
                        "tone": last_roast.get("tone", "neutral"),
                        "severity": last_roast.get("severity", 1),
                        "mainReason": "",
                        "suggestedFocus": "",
                        "templateId": last_roast.get("templateId"),
                        "structureFamily": last_roast.get("structureFamily"),
                        "metaphorCategory": last_roast.get("metaphorCategory")
                    }
            except Exception:
                pass
    # Check if we should short-circuit NO_CHANGE via template logic
    if mode == "NO_CHANGE":
        scenario_key = "NO_MEANINGFUL_CHANGE"
        scenario_info["outcomeType"] = "neutral"
        scenario_info["severity"] = 1
        
    # 4.5 Select Message Angle
    eligible_angles = angle_selector.determine_eligible_angles(current_snapshot, benchmark_snapshot, mode)
    angle_params = {
        "scenarioKey": scenario_key,
        "availableAngles": eligible_angles,
        "recentRoasts": recent_history,
        "availableData": current_snapshot,
        "commentaryMode": mode
    }
    message_angle = angle_selector.selectPreferredMessageAngle(angle_params)
    
    # 5. Try selecting a template
    criteria = {
        "scenarioKey": scenario_key,
        "intensity": roast_intensity,
        "messageAngle": message_angle
    }
    template, telemetry = template_bank.get_best_template(criteria, data, recent_history)
    telemetry["scenarioKey"] = scenario_key
    telemetry["intensity"] = roast_intensity
    telemetry["messageAngle"] = message_angle
    
    final_output = None
    debug_metadata = None
    
    # 6. Use Template First
    if template:
        telemetry["source"] = "template"
        t_vars = _build_template_vars(current_snapshot, benchmark_snapshot)
        final_output = {
            "title": _interpolate(template.get("titleTemplate"), t_vars),
            "message": _interpolate(template.get("messageTemplate"), t_vars),
            "tone": template.get("tone", "neutral"),
            "severity": scenario_info.get("severity", 1),
            "mainReason": _interpolate(template.get("mainReasonTemplate"), t_vars),
            "suggestedFocus": _interpolate(template.get("suggestedFocusTemplate"), t_vars),
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
            promptType="daily_roast",
            roastIntensity=roast_intensity,
            outcomeType=scenario_info["outcomeType"],
            portfolioData=current_snapshot,
            benchmarkData=benchmark_snapshot,
            commentaryMode=mode,
            recentRoasts=recent_history,
            messageAngle=message_angle,
            scenarioKey=scenario_key
        )
        
        system_prompt = prompt["systemPrompt"]
        user_prompt = prompt["userPrompt"]
        
        max_attempts = 2 if enable_retry else 1
        
        ai_rejection_reasons = []
        ai_rejected_count = 0
        
        # Attempt AI generation with optional retry
        for attempt in range(max_attempts):
            llm_response = _call_llm(system_prompt, user_prompt)
            if not llm_response:
                continue
                
            parsed = _parse_llm_json(llm_response)
            if not parsed or "message" not in parsed:
                continue
                
            # Check similarity against history
            dummy_roast = {"messageText": parsed.get("message", ""), "title": parsed.get("title", "")}
            cooldown_res = roast_history.check_cooldowns(dummy_roast, recent_history)
            
            if not cooldown_res.get("allowed", False):
                # Failed cooldown check (too similar)
                reason = cooldown_res.get("reason", "Unknown similarity")
                ai_rejected_count += 1
                ai_rejection_reasons.append(reason)
                print(f"AI Generation Retry Reason: {reason}")
                
                if attempt == 0 and enable_retry:
                    # Build second prompt with stronger constraints
                    retry_prompt = prompt_builder.build_retry_prompt(
                        base_prompt=prompt,
                        rejected_output=parsed,
                        similarity_reason=reason,
                        recent_roasts=recent_history
                    )
                    system_prompt = retry_prompt["systemPrompt"]
                    user_prompt = retry_prompt["userPrompt"]
                continue
                
            # Passed checks!
            final_output = parsed
            final_output["templateId"] = None
            telemetry["source"] = "ai"
            
            debug_metadata = {
                "source": "ai",
                "scenarioKey": scenario_key,
                "messageAngle": message_angle,
                "templateId": None,
                "fallbackLevel": f"Attempt {attempt + 1}",
                "similarityScore": cooldown_res.get("similarityScore"),
                "rejectedCandidateCount": ai_rejected_count,
                "rejectionReasons": ai_rejection_reasons,
                "recentTemplateIdsConsidered": [],
                "selectedBecause": "Passed AI similarity checks."
            }
            break
            
    # 7. Absolute Fallback if all else fails
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
        }
            
    # 8. Enrich output and save history
    final_output["scenarioKey"] = scenario_key
    final_output["commentaryMode"] = mode
    final_output["messageAngle"] = message_angle
    
    # Expose tracking parameters for frontend telemetry
    final_output["portfolioChange"] = current_snapshot.get("dailyChangePct")
    final_output["benchmarkChange"] = benchmark_snapshot.get("dailyChangePct")
    final_output["bestAsset"] = current_snapshot.get("dailyBestAsset")
    final_output["worstAsset"] = current_snapshot.get("dailyWorstAsset")
    
    roast_record = {
        "id": str(uuid.uuid4()),
        "userId": user_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "periodType": "daily",
        "scenarioKey": scenario_key,
        "scenarioGroup": scenario_info.get("scenarioGroup", "UNKNOWN"),
        "messageAngle": message_angle,
        "templateId": final_output.get("templateId"),
        "structureFamily": final_output.get("structureFamily"),
        "metaphorCategory": final_output.get("metaphorCategory"),
        "title": final_output.get("title", ""),
        "messageText": final_output.get("message", ""),
        "tone": final_output.get("tone", "neutral"),
        "severity": final_output.get("severity", 1),
        "roastIntensity": roast_intensity,
        "portfolioReturnPercent": current_snapshot.get("dailyChangePct"),
        "benchmarkReturnPercent": benchmark_snapshot.get("dailyChangePct"),
        "totalPortfolioValue": current_snapshot.get("portfolioValue"),
        "bestAssetReturn": current_snapshot.get("topAssetPct"),
        "worstAssetReturn": current_snapshot.get("worstAssetPct"),
        "relativePerformancePercent": current_snapshot.get("dailyChangePct", 0) - benchmark_snapshot.get("dailyChangePct", 0) if current_snapshot.get("dailyChangePct") is not None and benchmark_snapshot.get("dailyChangePct") is not None else None,
        "dailyBestAsset": current_snapshot.get("topAsset"),
        "dailyWorstAsset": current_snapshot.get("worstAsset"),
        "isNewATH": current_snapshot.get("isAth", False),
        "currentDrawdownFromATH": current_snapshot.get("drawdownPct", 0)
    }
    
    roast_record["telemetry"] = telemetry
    final_output["telemetry"] = telemetry
    
    if enable_debug and debug_metadata:
        final_output["debug"] = debug_metadata
        roast_record["debug"] = debug_metadata
        
    roast_history.save_roast(roast_record)
    
    return final_output

def generate_monthly_roast(user_id: str, current_snapshot: dict, prev_month_snapshot: dict, benchmark_monthly_pct: float, enable_ai: bool = False, enable_retry: bool = True) -> dict:
    """
    Generate a monthly roast comparing the latest snapshot to the one from 30 days ago.
    """
    settings = db.get_user(user_id).get('settings', {})
    roast_intensity = settings.get('roastIntensity', 'sarcastic')
    
    # 1. Determine Monthly Scenario
    port_val_now = current_snapshot.get("portfolioValue", 0)
    port_val_prev = prev_month_snapshot.get("portfolioValue", 0)
    
    if port_val_prev > 0:
        monthly_pct = ((port_val_now - port_val_prev) / port_val_prev) * 100.0
    else:
        monthly_pct = 0.0
        
    if monthly_pct > 0.5 and benchmark_monthly_pct > 0.5:
        scenario_key = "MONTHLY_BOTH_POSITIVE_USER_BETTER" if monthly_pct > benchmark_monthly_pct else "MONTHLY_BOTH_POSITIVE_USER_WORSE"
    elif monthly_pct < -0.5 and benchmark_monthly_pct < -0.5:
        scenario_key = "MONTHLY_BOTH_NEGATIVE_USER_BETTER" if monthly_pct > benchmark_monthly_pct else "MONTHLY_BOTH_NEGATIVE_USER_WORSE"
    elif monthly_pct > 0.5 and benchmark_monthly_pct < -0.5:
        scenario_key = "MONTHLY_USER_POSITIVE_BENCHMARK_NEGATIVE"
    elif monthly_pct < -0.5 and benchmark_monthly_pct > 0.5:
        scenario_key = "MONTHLY_USER_NEGATIVE_BENCHMARK_POSITIVE"
    else:
        scenario_key = "MONTHLY_FLAT"
        
    scenario_info = {"scenarioGroup": "MONTHLY_SUMMARY", "severity": 1}
    
    # 2. Get history to avoid repetition
    recent_history = roast_history.get_recent_history(user_id, days=180, period_type="monthly")
    
    # 3. Find Template
    criteria = {
        "scenarioKey": scenario_key,
        "intensity": roast_intensity
    }
    
    data_payload = {
        "monthlyReturnPercent": round(monthly_pct, 2),
        "benchmarkMonthlyReturnPercent": round(benchmark_monthly_pct, 2),
        "portfolioValue": port_val_now,
        "topAsset": current_snapshot.get("topAsset", "Unknown"),
        "topAssetPct": current_snapshot.get("topAssetPct", 0.0),
        "worstAsset": current_snapshot.get("worstAsset", "Unknown"),
        "worstAssetPct": current_snapshot.get("worstAssetPct", 0.0)
    }
    
    template, telemetry = template_bank.get_best_template(criteria, data_payload, recent_history)
    
    # 4. Generate text (AI or Template)
    final_output = None
    
    if enable_ai and prompt_builder and get_openai_client:
        try:
            client = get_openai_client()
            if client:
                prompt = prompt_builder.build_ai_prompt(
                    user_id=user_id,
                    scenario_key=scenario_key,
                    commentary_mode="MONTHLY_SUMMARY",
                    roast_intensity=roast_intensity,
                    outcome_type=scenario_info.get("scenarioGroup"),
                    data_payload=data_payload,
                    recent_history=recent_history,
                    message_angle=None,
                    is_monthly=True
                )
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt_builder.build_system_prompt()},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                import json
                ai_result = json.loads(response.choices[0].message.content)
                
                final_output = {
                    "title": ai_result.get("title", "Monthly Update"),
                    "message": ai_result.get("message", "Here is your monthly roast."),
                    "tone": ai_result.get("tone", "neutral"),
                    "severity": ai_result.get("severity", 1),
                    "mainReason": ai_result.get("mainReason"),
                    "suggestedFocus": ai_result.get("suggestedFocus"),
                    "templateId": None
                }
        except Exception as e:
            logger.error(f"AI monthly generation failed: {e}")
            
    if not final_output:
        if template:
            final_output = {
                "title": template.get("titleTemplate"),
                "message": template.get("messageTemplate"),
                "tone": template.get("tone", "neutral"),
                "severity": scenario_info.get("severity", 1),
                "mainReason": template.get("mainReasonTemplate"),
                "suggestedFocus": template.get("suggestedFocusTemplate"),
                "templateId": template.get("templateId")
            }
        else:
            final_output = {
                "title": "Monthly Update",
                "message": "Another month has passed. We couldn't generate a fresh roast right now. Rest assured, you are probably still underperforming.",
                "tone": "neutral",
                "severity": 1,
                "mainReason": "System error",
                "suggestedFocus": None,
                "templateId": None
            }
            
    final_output["scenarioKey"] = scenario_key
    final_output["commentaryMode"] = "MONTHLY_SUMMARY"
    final_output["messageAngle"] = None
    
    roast_record = {
        "id": str(uuid.uuid4()),
        "userId": user_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "periodType": "monthly",
        "scenarioKey": scenario_key,
        "title": final_output.get("title", ""),
        "messageText": final_output.get("message", ""),
        "tone": final_output.get("tone", "neutral"),
        "severity": final_output.get("severity", 1),
        "suggestedFocus": final_output.get("suggestedFocus"),
        "roastIntensity": roast_intensity,
        "portfolioReturnPercent": round(monthly_pct, 2),
        "benchmarkReturnPercent": round(benchmark_monthly_pct, 2),
        "totalPortfolioValue": port_val_now,
        "bestAssetReturn": current_snapshot.get("topAssetPct"),
        "worstAssetReturn": current_snapshot.get("worstAssetPct")
    }
    
    try:
        roast_history.save_roast(roast_record)
    except Exception as e:
        logger.error(f"Failed to save monthly roast: {e}")
        
    return final_output
