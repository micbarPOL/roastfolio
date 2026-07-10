import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
import roast_engine
import template_bank

@pytest.fixture
def mock_dependencies():
    # We want to mock get_user, save_roast, but keep history stateful in memory to test rotation
    memory_history = []
    
    def mock_save(record):
        memory_history.insert(0, record)
        return record
        
    def mock_get_hist(user_id, limit=30):
        return memory_history[:limit]
        
    def mock_latest(user_id):
        return memory_history[0] if memory_history else None

    with patch('roast_engine.db.get_user') as mock_get_user, \
         patch('roast_engine.roast_history.get_recent_history') as mock_get_recent_history, \
         patch('roast_engine.roast_history.get_latest_roast_today') as mock_get_latest_roast_today, \
         patch('roast_engine.roast_history.save_roast') as mock_save_roast:
        
        mock_get_user.return_value = {"settings": {"roastIntensity": "sarcastic"}}
        mock_get_recent_history.side_effect = mock_get_hist
        mock_get_latest_roast_today.side_effect = mock_latest
        mock_save_roast.side_effect = mock_save
        
        template_bank.load_templates()
        
        yield {
            "get_user": mock_get_user,
            "get_recent_history": mock_get_recent_history,
            "get_latest_roast_today": mock_get_latest_roast_today,
            "save_roast": mock_save_roast,
            "history": memory_history
        }

def test_angle_rotation_sequence(mock_dependencies):
    user_id = "test_user_rotate"
    
    # Payload that triggers multiple eligible angles (ATH, Worst Asset, Benchmark)
    snapshot = {
        "totalPortfolioValue": 10000,
        "portfolioValue": 10000,
        "dailyChangePct": -2.5,
        "isAth": False,
        "worstAssetPct": -5.0,
        "drawdownPct": 6.0
    }
    benchmark = {"dailyChangePct": -0.5}
    
    # Call 1
    res1 = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
    angle1 = res1.get("messageAngle")
    assert angle1 is not None
    
    # Change payload slightly to trigger a Volatility check or just use same
    # But wait, intraday classifier might return "NO_CHANGE" if data is exactly the same, 
    # which limits eligible angles to ["NO_CHANGE"].
    # Let's change the payload slightly so it registers as MIDDAY_UPDATE
    
    snapshot["totalPortfolioValue"] = 9900 # changed by 1%, not enough for volatility spike, but enough for midday
    
    # Call 2
    res2 = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
    angle2 = res2.get("messageAngle")
    assert angle2 is not None
    assert angle2 != angle1 # Should have rotated away from angle1
    
    snapshot["totalPortfolioValue"] = 9800
    
    # Call 3
    res3 = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
    angle3 = res3.get("messageAngle")
    assert angle3 is not None
    assert angle3 != angle2 # Should rotate again
