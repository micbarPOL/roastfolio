import json
import pytest
import sys
import os

# Ensure lambda directory is in path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
from prompt_builder import build_roast_prompt

def test_base_system_prompt_safety():
    """Ensure all safety rules are present in the system prompt."""
    res = build_roast_prompt(promptType="daily_roast")
    sys_prompt = res["systemPrompt"]
    
    assert "Do not provide direct financial advice." in sys_prompt
    assert "Do not predict future market movements with certainty." in sys_prompt
    assert "Do not insult protected traits or personal identity." in sys_prompt

def test_prompt_types():
    """Ensure correct user prompt text and expected JSON schemas for each type."""
    # Daily Roast
    res_daily = build_roast_prompt(promptType="daily_roast")
    assert "Generate today's Roastfolio commentary" in res_daily["userPrompt"]
    assert "summary" not in res_daily["expectedOutputSchema"]["properties"]

    # Monthly Report
    res_monthly = build_roast_prompt(promptType="monthly_report")
    assert "monthly portfolio report" in res_monthly["userPrompt"]
    assert "summary" in res_monthly["expectedOutputSchema"]["properties"]
    assert "summary" in res_monthly["expectedOutputSchema"]["required"]

    # Achievement
    res_ach = build_roast_prompt(promptType="achievement", achievements=["10k"])
    assert "newly unlocked user achievement" in res_ach["userPrompt"]
    assert "10k" in res_ach["userPrompt"]

    # FIRE Progress
    res_fire = build_roast_prompt(promptType="fire_progress", fireProgress={"swr": 3.5})
    assert "Financial Independence, Retire Early" in res_fire["userPrompt"]
    assert "3.5" in res_fire["userPrompt"]

    # Asset Specific
    res_asset = build_roast_prompt(promptType="asset_specific", portfolioData={"ticker": "AAPL"})
    assert "specific asset's performance" in res_asset["userPrompt"]
    assert "AAPL" in res_asset["userPrompt"]

def test_constraints_injection():
    """Ensure custom constraints are appended to the user prompt."""
    res = build_roast_prompt(promptType="daily_roast", constraints={"max_words": 50})
    assert "Additional Constraints:" in res["userPrompt"]
    assert "max_words" in res["userPrompt"]
    assert "50" in res["userPrompt"]

def test_empty_data():
    """Ensure function does not crash when empty data is provided."""
    res = build_roast_prompt(promptType="unknown")
    assert res["systemPrompt"]
    assert res["userPrompt"]
    assert res["expectedOutputSchema"]

def test_recent_roasts_context():
    """Ensure recent roasts generate correct constraints in the system prompt."""
    recent_roasts = [
        {
            "createdAt": "2026-07-08T10:00:00Z",
            "scenarioKey": "NEW_ATH_DAY",
            "commentaryMode": "OPENING_CHECK",
            "title": "A New Peak",
            "message": "You actually made money today. I am shocked, completely shocked. Good job.",
            "templateId": None
        },
        {
            "createdAt": "2026-07-07T15:00:00Z",
            "scenarioKey": "VOLATILITY_SPIKE",
            "commentaryMode": "CLOSING_RECAP",
            "title": "Market Choppiness",
            "message": "The market went crazy today. Your portfolio survived. Barely.",
            "templateId": "test1"
        }
    ]
    
    res = build_roast_prompt(promptType="daily_roast", recentRoasts=recent_roasts)
    sys_prompt = res["systemPrompt"]
    user_prompt = res["userPrompt"]
    
    # Check that anti-repetition constraints exist in user_prompt instead of sys_prompt now
    assert "Do not repeat:" in user_prompt
    assert "A New Peak" in user_prompt
    assert "You actually made money today" in user_prompt
    assert "Barely." in user_prompt
    assert "The market went crazy today" in user_prompt
    
    # Check punchlines
    assert "Good job." in user_prompt
    
    # Also ensure user context is appended
    assert "recentRoastsContext" not in res["userPrompt"] # this was moved to the new structure completely
    assert "A New Peak" in user_prompt
