import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

# Ensure lambda directory is in path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
import roast_engine
import template_bank

@pytest.fixture
def mock_dependencies():
    with patch('roast_engine.db.get_user') as mock_get_user, \
         patch('roast_engine.roast_history.get_recent_history') as mock_get_recent_history, \
         patch('roast_engine.roast_history.get_latest_roast_today') as mock_get_latest_roast_today, \
         patch('roast_engine.roast_history.save_roast') as mock_save_roast:
        
        mock_get_user.return_value = {"settings": {"roastIntensity": "sarcastic"}}
        mock_get_recent_history.return_value = []
        mock_get_latest_roast_today.return_value = None
        mock_save_roast.return_value = None
        
        # We need templates loaded for get_best_template
        # Let's ensure template_bank has loaded the templates
        template_bank.load_templates()
        
        yield {
            "get_user": mock_get_user,
            "get_recent_history": mock_get_recent_history,
            "get_latest_roast_today": mock_get_latest_roast_today,
            "save_roast": mock_save_roast
        }

def test_repeated_visits_same_data(mock_dependencies):
    user_id = "test_user_1"
    
    # First visit snapshot
    snapshot1 = {
        "totalPortfolioValue": 10000,
        "portfolioValue": 10000,
        "dailyChangePct": -1.5,
        "isAth": False
    }
    benchmark1 = {"dailyChangePct": -0.5}
    
    # First visit (no history)
    res1 = roast_engine.generate_daily_roast(user_id, snapshot1, benchmark1)
    
    assert res1["scenarioKey"] != "NO_MEANINGFUL_CHANGE"
    assert res1["commentaryMode"] == "OPENING_CHECK"
    assert res1["templateId"] is not None
    
    # Mock that the first visit was saved and is now returned as latest roast
    mock_dependencies["get_latest_roast_today"].return_value = {
        "templateId": res1["templateId"],
        "messageText": res1["message"],
        "totalPortfolioValue": 10000,
        "portfolioReturnPercent": -1.5,
        "benchmarkReturnPercent": -0.5
    }
    
    # Second visit with SAME data
    res2 = roast_engine.generate_daily_roast(user_id, snapshot1, benchmark1)
    
    assert res2["commentaryMode"] == "NO_CHANGE"
    assert res2["scenarioKey"] == "NO_MEANINGFUL_CHANGE"
    assert res2["templateId"] is not None

def test_repeated_visits_changing_data(mock_dependencies):
    user_id = "test_user_2"
    
    snapshot1 = {
        "totalPortfolioValue": 10000,
        "portfolioValue": 10000,
        "dailyChangePct": 0.5,
        "isAth": False
    }
    benchmark1 = {"dailyChangePct": 0.5}
    
    # Mock that there was a previous visit today with different values
    mock_dependencies["get_latest_roast_today"].return_value = {
        "templateId": "test_id",
        "messageText": "Previous message",
        "totalPortfolioValue": 9800, # Dropped by ~2% since last check
        "portfolioReturnPercent": 2.5,
        "benchmarkReturnPercent": 0.5
    }
    
    res = roast_engine.generate_daily_roast(user_id, snapshot1, benchmark1)
    
    # Intraday classifier should detect VOLATILITY_SPIKE since it changed by 200 (2%)
    assert res["commentaryMode"] == "VOLATILITY_SPIKE"

def test_cooldown_enforcement(mock_dependencies):
    user_id = "test_user_3"
    
    snapshot = {
        "totalPortfolioValue": 10000,
        "portfolioValue": 10000,
        "dailyChangePct": 1.5,
        "isAth": True
    }
    benchmark = {"dailyChangePct": 0.5}
    
    # Manually pick a template to exhaust
    criteria = {"scenarioKey": "NEAR_ATH", "intensity": "sarcastic"}
    template = template_bank.get_best_template(criteria, {"portfolio": snapshot, "benchmark": benchmark}, [])
    used_template_id = template["templateId"]
    
    # Inject it into recent history to trigger cooldown
    mock_dependencies["get_recent_history"].return_value = [{
        "templateId": used_template_id,
        "messageText": template["messageTemplate"],
        "createdAt": "2026-07-08T12:00:00Z"
    }]
    
    res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
    
    # Just verify it's the expected scenario (it could be NEAR_ATH depending on exact classifier logic)
    assert res["scenarioKey"] in ["NEW_ATH_DAY", "NEAR_ATH", "USER_OUTPERFORMED_BY_LARGE_MARGIN"]
    
    # Verify the used template ID was rejected due to cooldown and a DIFFERENT one was chosen
    assert res["templateId"] != used_template_id

@patch('roast_engine._call_llm')
def test_ai_fallback_to_template(mock_call_llm, mock_dependencies):
    user_id = "test_user_4"
    
    snapshot = {
        "portfolioValue": 10000,
        "dailyChangePct": -1.5,
        "isAth": False
    }
    benchmark = {"dailyChangePct": -0.5}
    
    # Mock LLM to return invalid JSON
    mock_call_llm.return_value = "This is not JSON"
    
    res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark, enable_ai=True)
    
    # Since AI failed (invalid JSON), it should fallback to a deterministic template
    assert res["templateId"] is not None
    assert "templateId" in res

@patch('roast_engine._call_llm')
def test_ai_similarity_retry(mock_call_llm, mock_dependencies):
    user_id = "test_user_5"
    
    snapshot = {
        "totalPortfolioValue": 10000,
        "portfolioValue": 10000,
        "dailyChangePct": -1.5,
        "isAth": False
    }
    benchmark = {"dailyChangePct": -0.5}
    
    # Add a message to history
    past_msg = "You lost money today, how original."
    mock_dependencies["get_recent_history"].return_value = [{
        "templateId": None,
        "messageText": past_msg,
        "createdAt": "2026-07-08T12:00:00Z"
    }]
    
    # Make LLM return the EXACT same opening phrase first time, then something different
    valid_json1 = json.dumps({"title": "Test1", "message": "You lost money today, how interesting.", "tone": "roast", "severity": 2}) # Same first 5 words
    valid_json2 = json.dumps({"title": "Test2", "message": "Market turbulence strikes again, unfortunately.", "tone": "roast", "severity": 2}) # Different
    
    mock_call_llm.side_effect = [valid_json1, valid_json2]
    
    res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark, enable_ai=True)
    
    # AI should have retried and picked the second one
    assert res["templateId"] is None # It's AI generated
    assert res["message"] == "Market turbulence strikes again, unfortunately."
    assert mock_call_llm.call_count == 2

@patch('roast_engine._call_llm')
def test_ai_similarity_retry_exhausted(mock_call_llm, mock_dependencies):
    user_id = "test_user_6"
    
    snapshot = {
        "totalPortfolioValue": 10000,
        "portfolioValue": 10000,
        "dailyChangePct": -1.5,
        "isAth": False
    }
    benchmark = {"dailyChangePct": -0.5}
    
    past_msg = "You lost money today, how original."
    mock_dependencies["get_recent_history"].return_value = [{
        "templateId": None,
        "messageText": past_msg,
        "createdAt": "2026-07-08T12:00:00Z"
    }]
    
    # LLM keeps returning the same opening phrase
    valid_json1 = json.dumps({"title": "Test1", "message": "You lost money today, how interesting.", "tone": "roast", "severity": 2})
    valid_json2 = json.dumps({"title": "Test2", "message": "You lost money today, how sad.", "tone": "roast", "severity": 2})
    
    mock_call_llm.side_effect = [valid_json1, valid_json2]
    
    res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark, enable_ai=True)
    
    # It should have tried 2 times, then fallen back to template
    assert mock_call_llm.call_count == 2
    assert res["templateId"] is not None # Fell back to template

@patch('roast_engine._call_llm')
def test_no_change_skips_ai(mock_call_llm, mock_dependencies):
    user_id = "test_user_no_change"
    
    snapshot = {
        "totalPortfolioValue": 10000.0,
        "portfolioValue": 10000.0,
        "dailyChangePct": 0.05,
        "benchmark_return": 0.04,
        "relative_performance": 0.01,
        "isAth": False,
        "best_asset": "AAPL",
        "worst_asset": "TSLA"
    }
    benchmark = {"dailyChangePct": 0.04}
    
    # Last roast has virtually identical numbers
    mock_dependencies["get_recent_history"].return_value = []
    mock_dependencies["get_latest_roast_today"].return_value = {
        "totalPortfolioValue": 9999.0, # Difference is 0.01%
        "benchmarkReturnPercent": 0.04,
        "relativePerformancePercent": 0.01,
        "isAth": False,
        "bestAsset": "AAPL",
        "worstAsset": "TSLA"
    }
    
    # We enable AI, but it should still be skipped because of NO_CHANGE
    res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark, enable_ai=True)
    
    # AI should not be called
    mock_call_llm.assert_not_called()
    
    assert res["scenarioKey"] == "NO_MEANINGFUL_CHANGE"
    assert res["commentaryMode"] == "NO_CHANGE"
    assert res["templateId"] is not None # Fell back to template

def test_debug_metadata_exposure(mock_dependencies):
    user_id = "test_debug"
    snapshot = {"portfolioValue": 10000, "dailyChangePct": 1.0, "isAth": True}
    benchmark = {"dailyChangePct": -1.0}
    
    # 1. Test enable_debug = False (Production default)
    res_prod = roast_engine.generate_daily_roast(user_id, snapshot, benchmark, enable_debug=False)
    assert "debug" not in res_prod
    
    # Verify roast_record doesn't have it either
    saved_record_prod = mock_dependencies["save_roast"].call_args[0][0]
    assert "debug" not in saved_record_prod
    
    # 2. Test enable_debug = True
    res_dev = roast_engine.generate_daily_roast(user_id, snapshot, benchmark, enable_debug=True)
    assert "debug" in res_dev
    
    debug_info = res_dev["debug"]
    assert "source" in debug_info
    assert "fallbackLevel" in debug_info
    assert "rejectedCandidateCount" in debug_info
    assert "rejectionReasons" in debug_info
    assert "recentTemplateIdsConsidered" in debug_info
    
    # Verify roast_record has it too
    saved_record_dev = mock_dependencies["save_roast"].call_args[0][0]
    assert "debug" in saved_record_dev
    assert saved_record_dev["debug"] == debug_info
