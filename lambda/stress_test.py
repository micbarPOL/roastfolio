import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.append(os.path.dirname(__file__) or '.')
import template_bank

MOCK_DATA = {
    "portfolioValue": "10,000",
    "portfolioReturnPercent": "5.0",
    "benchmarkReturnPercent": "3.0",
    "relativePerformancePercent": "2.0",
    "bestAsset": "AAPL",
    "worstAsset": "TSLA",
    "bestAssetReturn": "15.0",
    "worstAssetReturn": "-10.0",
    "currentDrawdownFromATH": "5.0",
    "currency": "$",
    "dailyBestAsset": "AAPL",
    "dailyWorstAsset": "TSLA",
    "monthlyReturnPercent": "2.5"
}

COMMON_SCENARIOS = [
    "BOTH_POSITIVE_USER_BETTER", "BOTH_NEGATIVE_USER_WORSE", "USER_NEGATIVE_BENCHMARK_POSITIVE",
    "NEW_ATH_DAY", "DRAWDOWN_SIGNIFICANT", "NO_MEANINGFUL_CHANGE", "BOTH_NEGATIVE_USER_BETTER"
]

def run_simulation(name, days, checks_per_day, scenario_generator, templates):
    history = []
    
    metrics = {
        "totalRoasts": 0,
        "templateRoasts": 0,
        "deterministicFallbackRoasts": 0,
        "aiFallbackWouldHaveTriggered": 0,
        "duplicateTemplateWithinCooldown": 0,
        "duplicateRecentTitle": 0,
        "structureFamilyRuleViolations": 0,
        "metaphorCategoryRuleViolations": 0,
        "averageSimilarityScore": 0.0,
        "maxSimilarityScore": 0.0,
        "scenarioExhaustion": {}
    }
    
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    total_sim_score = 0.0
    sim_scores_count = 0
    
    # We patch datetime inside template_bank to simulate time passing
    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.current_sim_time
            
    with patch('template_bank.datetime', MockDatetime):
        for day in range(days):
            for check in range(checks_per_day):
                current_time = start_date + timedelta(days=day, hours=(24 / checks_per_day) * check)
                MockDatetime.current_sim_time = current_time
                
                metrics["totalRoasts"] += 1
                scenario = scenario_generator()
                
                # Fetch template
                criteria = {"scenarioKey": scenario}
                
                template = template_bank.get_best_template(criteria, MOCK_DATA, history, templates)
                
                if template is None:
                    metrics["aiFallbackWouldHaveTriggered"] += 1
                    metrics["scenarioExhaustion"][scenario] = metrics["scenarioExhaustion"].get(scenario, 0) + 1
                    continue
                    
                debug = template.get("_debug", {})
                fallback_level = debug.get("fallbackLevel", "")
                
                if "Absolute Fallback" in fallback_level:
                    metrics["deterministicFallbackRoasts"] += 1
                else:
                    metrics["templateRoasts"] += 1
                    
                if "Ignored Title Cooldown" in fallback_level:
                    metrics["duplicateRecentTitle"] += 1
                if "Ignored Title and Metadata Cooldown" in fallback_level:
                    metrics["structureFamilyRuleViolations"] += 1
                    metrics["metaphorCategoryRuleViolations"] += 1
                    
                sim_score = debug.get("similarityScore")
                if sim_score is not None:
                    total_sim_score += sim_score
                    sim_scores_count += 1
                    metrics["maxSimilarityScore"] = max(metrics["maxSimilarityScore"], sim_score)
                    
                # We need to manually check duplicate cooldown because the engine might have ignored it?
                # Actually apply_cooldowns NEVER ignores the ID-based cooldown. So if it was returned, it either passed cooldown or it was absolute fallback.
                # Let's manually verify cooldown.
                tid = template.get("templateId")
                cooldown_days = template.get("cooldownDays", 14)
                if scenario == "NO_MEANINGFUL_CHANGE": cooldown_days = 1
                
                for r in history:
                    if r.get("templateId") == tid:
                        dt = datetime.fromisoformat(r["createdAt"].replace('Z', '+00:00'))
                        if (current_time - dt).days < cooldown_days:
                            if "Absolute Fallback" not in fallback_level: # Absolute fallback uses the last template, bypassing all rules
                                metrics["duplicateTemplateWithinCooldown"] += 1
                        break
                        
                # Add to history
                template_copy = dict(template)
                template_copy["createdAt"] = current_time.isoformat()
                history.insert(0, template_copy)
                
    if sim_scores_count > 0:
        metrics["averageSimilarityScore"] = total_sim_score / sim_scores_count
        
    return metrics

def main():
    templates = template_bank.load_templates()
    if not templates:
        print("No templates found in roast_templates.json")
        sys.exit(1)
        
    # We only want enabled templates
    enabled_templates = [t for t in templates if t.get("enabled", False)]
    if not enabled_templates:
        print("No enabled templates available.")
        sys.exit(1)

    print(f"Starting stress test with {len(enabled_templates)} enabled templates...\n")
    
    results = {}
    
    # 1. Normal user
    print("Running Normal User...")
    results["normal_user"] = run_simulation("Normal", 30, 3, lambda: random.choice(COMMON_SCENARIOS), enabled_templates)
    
    # 2. Power user
    print("Running Power User...")
    results["power_user"] = run_simulation("Power", 30, 15, lambda: random.choice(COMMON_SCENARIOS), enabled_templates)
    
    # 3. Obsessive checker
    print("Running Obsessive Checker...")
    def obsessive_gen():
        return "NO_MEANINGFUL_CHANGE" if random.random() < 0.8 else random.choice(COMMON_SCENARIOS)
    results["obsessive_checker"] = run_simulation("Obsessive", 14, 50, obsessive_gen, enabled_templates)
    
    # 4. Same bad scenario user
    print("Running Same Bad Scenario User...")
    results["bad_scenario_user"] = run_simulation("BadScenario", 30, 10, lambda: "USER_NEGATIVE_BENCHMARK_POSITIVE", enabled_templates)
    
    # 5. Same good scenario user
    print("Running Same Good Scenario User...")
    results["good_scenario_user"] = run_simulation("GoodScenario", 30, 10, lambda: "BOTH_POSITIVE_USER_BETTER", enabled_templates)
    
    # 6. Mixed scenario user
    print("Running Mixed Scenario User...")
    results["mixed_scenario_user"] = run_simulation("MixedScenario", 90, 10, lambda: random.choice(COMMON_SCENARIOS), enabled_templates)
    
    # Write report
    with open("stress_test_report.json", "w") as f:
        json.dump(results, f, indent=2)
        
    # Validation against pass criteria
    passed = True
    
    def check_criteria(name, metrics, rules):
        nonlocal passed
        for rule_name, rule_fn in rules.items():
            if not rule_fn(metrics):
                print(f"FAIL [{name}]: {rule_name} (Got: {metrics})")
                passed = False
                
    zero_violations = {
        "duplicateTemplateWithinCooldown == 0": lambda m: m["duplicateTemplateWithinCooldown"] == 0,
        "duplicateRecentTitle == 0": lambda m: m["duplicateRecentTitle"] == 0,
        "structureFamilyRuleViolations == 0": lambda m: m["structureFamilyRuleViolations"] == 0,
        "metaphorCategoryRuleViolations == 0": lambda m: m["metaphorCategoryRuleViolations"] == 0
    }
    
    print("\n--- Validation Results ---")
    
    for name, metrics in results.items():
        check_criteria(name, metrics, zero_violations)
        
    # Deterministic fallback limits
    if results["normal_user"]["totalRoasts"] > 0:
        det_rate = results["normal_user"]["deterministicFallbackRoasts"] / results["normal_user"]["totalRoasts"]
        if det_rate > 0.01:
            print(f"FAIL [Normal User]: Deterministic fallback rate {det_rate:.2%} > 1%")
            passed = False
            
    if results["power_user"]["totalRoasts"] > 0:
        det_rate = results["power_user"]["deterministicFallbackRoasts"] / results["power_user"]["totalRoasts"]
        if det_rate > 0.03:
            print(f"FAIL [Power User]: Deterministic fallback rate {det_rate:.2%} > 3%")
            passed = False
            
    # AI Fallback limits
    if results["normal_user"]["aiFallbackWouldHaveTriggered"] > 0:
        print(f"FAIL [Normal User]: GPT fallback triggered ({results['normal_user']['aiFallbackWouldHaveTriggered']} times)")
        passed = False
        
    if results["power_user"]["aiFallbackWouldHaveTriggered"] > 0:
        print(f"FAIL [Power User]: GPT fallback triggered ({results['power_user']['aiFallbackWouldHaveTriggered']} times)")
        passed = False
        
    # Obsessive exhaustion limit
    if "NO_MEANINGFUL_CHANGE" in results["obsessive_checker"]["scenarioExhaustion"]:
        print(f"FAIL [Obsessive Checker]: NO_MEANINGFUL_CHANGE exhausted!")
        passed = False

    if passed:
        print("All stress tests PASSED successfully!")
        sys.exit(0)
    else:
        print("Stress tests FAILED.")
        sys.exit(1)

if __name__ == '__main__':
    main()
