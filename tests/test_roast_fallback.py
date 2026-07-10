import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), '../lambda'))
import roast_engine
import template_bank

@pytest.fixture
def mock_data():
    return {
        "current": {
            "portfolioValue": 10000,
            "dailyChangePct": 5.0,
            "topAsset": "BTC",
            "topAssetPct": 10.0,
            "worstAsset": "ETH",
            "worstAssetPct": -2.0,
            "isAth": False,
            "drawdownPct": -5.0
        },
        "benchmark": {
            "dailyChangePct": 2.0
        }
    }

@patch('roast_engine.roast_history.save_roast')
@patch('roast_engine.roast_history.get_recent_history')
@patch('roast_engine.roast_history.get_latest_roast_today')
@patch('roast_engine.db.get_user')
def test_template_success_bypasses_ai(mock_get_user, mock_latest, mock_history, mock_save, mock_data):
    # Setup mocks
    mock_get_user.return_value = {"settings": {"roastIntensity": "gentle"}}
    mock_latest.return_value = None
    mock_history.return_value = []
    
    # Mock template bank to return a valid template
    with patch('roast_engine.template_bank.get_best_template') as mock_bank:
        mock_bank.return_value = (
            {"templateId": "test_01", "titleTemplate": "Test", "messageTemplate": "Msg", "tone": "neutral"},
            {"fallbackReason": None, "eligibleTemplateCount": 1}
        )
        
        # Enable AI globally, but it shouldn't be called because template succeeds
        roast_engine.ENABLE_RUNTIME_AI_ROASTS = True
        
        with patch('roast_engine._call_llm') as mock_llm:
            result = roast_engine.generate_daily_roast("user1", mock_data["current"], mock_data["benchmark"])
            
            # Assertions
            mock_llm.assert_not_called()
            assert result["templateId"] == "test_01"
            assert result["telemetry"]["source"] == "template"
            assert result["telemetry"]["fallbackReason"] is None

@patch('roast_engine.roast_history.save_roast')
@patch('roast_engine.roast_history.get_recent_history')
@patch('roast_engine.roast_history.get_latest_roast_today')
@patch('roast_engine.db.get_user')
def test_ai_called_when_template_fails_and_ai_enabled(mock_get_user, mock_latest, mock_history, mock_save, mock_data):
    mock_get_user.return_value = {"settings": {"roastIntensity": "gentle"}}
    mock_latest.return_value = None
    mock_history.return_value = []
    
    # Mock template bank to return None (meaning it failed)
    with patch('roast_engine.template_bank.get_best_template') as mock_bank:
        mock_bank.return_value = (
            None,
            {"fallbackReason": "scenario coverage gap", "eligibleTemplateCount": 0}
        )
        
        roast_engine.ENABLE_RUNTIME_AI_ROASTS = True
        
        with patch('roast_engine._call_llm') as mock_llm:
            mock_llm.return_value = '{"title": "AI Gen", "message": "AI Roast", "tone": "mixed"}'
            
            result = roast_engine.generate_daily_roast("user1", mock_data["current"], mock_data["benchmark"], enable_ai=True)
            
            mock_llm.assert_called_once()
            assert result["title"] == "AI Gen"
            assert result["templateId"] is None
            assert result["telemetry"]["source"] == "ai"
            assert result["telemetry"]["fallbackReason"] == "scenario coverage gap"

@patch('roast_engine.roast_history.save_roast')
@patch('roast_engine.roast_history.get_recent_history')
@patch('roast_engine.roast_history.get_latest_roast_today')
@patch('roast_engine.db.get_user')
def test_deterministic_fallback_when_ai_disabled(mock_get_user, mock_latest, mock_history, mock_save, mock_data):
    mock_get_user.return_value = {"settings": {"roastIntensity": "gentle"}}
    mock_latest.return_value = None
    mock_history.return_value = []
    
    with patch('roast_engine.template_bank.get_best_template') as mock_bank:
        mock_bank.return_value = (
            None,
            {"fallbackReason": "all templates too similar", "rejectedBySimilarityCount": 5}
        )
        
        # DISABLE AI
        roast_engine.ENABLE_RUNTIME_AI_ROASTS = False
        
        with patch('roast_engine._call_llm') as mock_llm:
            result = roast_engine.generate_daily_roast("user1", mock_data["current"], mock_data["benchmark"], enable_ai=True)
            
            mock_llm.assert_not_called()
            assert result["title"] == "Portfolio Update"
            assert result["mainReason"] == "System error"
            assert result["telemetry"]["source"] == "deterministic_fallback"
            assert result["telemetry"]["fallbackReason"] == "all templates too similar"
