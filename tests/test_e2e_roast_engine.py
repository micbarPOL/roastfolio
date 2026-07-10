import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

# Ensure lambda directory is in path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
import roast_engine
import template_bank

@pytest.fixture(autouse=True)
def setup_teardown():
    template_bank.load_templates()
    yield

class MockDB:
    def __init__(self):
        self.history = []
        self.settings = {"roastIntensity": "sarcastic"}
        
    def get_user(self, user_id):
        return {"settings": self.settings}
        
    def get_recent_history(self, user_id, limit=30):
        # We need a stable reverse sort to get newest first even if timestamps are identical.
        # Enumerate gives us original index, we sort by (createdAt, index) reversed.
        with_idx = [(i, x) for i, x in enumerate(self.history)]
        sorted_history = sorted(with_idx, key=lambda item: (item[1].get("createdAt", ""), item[0]), reverse=True)
        return [x for i, x in sorted_history][:limit]
        
    def get_latest_roast_today(self, user_id):
        recent = self.get_recent_history(user_id)
        if not recent:
            return None
        # Assume all in mock are today for simplicity
        return recent[0]
        
    def save_roast(self, roast):
        roast["createdAt"] = datetime.now(timezone.utc).isoformat()
        self.history.append(roast)

@pytest.fixture
def mock_db():
    db = MockDB()
    with patch('roast_engine.db.get_user', side_effect=db.get_user), \
         patch('roast_engine.roast_history.get_recent_history', side_effect=db.get_recent_history), \
         patch('roast_engine.roast_history.get_latest_roast_today', side_effect=db.get_latest_roast_today), \
         patch('roast_engine.roast_history.save_roast', side_effect=db.save_roast):
        yield db

def test_e2e_case_1_identical_data_visits(mock_db):
    """1. Same user opens app 5 times with identical data."""
    user_id = "u1"
    snapshot = {"totalPortfolioValue": 10000, "portfolioValue": 10000, "dailyChangePct": -1.5, "isAth": False}
    benchmark = {"dailyChangePct": -0.5}
    
    titles = set()
    messages = set()
    template_ids = set()
    
    for i in range(5):
        res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
        # engine saves it automatically now. We don't double save.
        
        assert res["title"] not in titles or res["commentaryMode"] == "NO_CHANGE"
        assert res["message"] not in messages or res["commentaryMode"] == "NO_CHANGE"
        
        if res.get("templateId"):
            assert res["templateId"] not in template_ids
            template_ids.add(res["templateId"])
            
        titles.add(res["title"])
        messages.add(res["message"])
        
        if i == 0:
            assert res["commentaryMode"] == "OPENING_CHECK"
        else:
            assert res["commentaryMode"] == "NO_CHANGE"

def test_e2e_case_2_slightly_changing_data(mock_db):
    """2. Same user opens app 5 times while portfolio changes slightly."""
    user_id = "u2"
    base_val = 10000
    titles = set()
    messages = set()
    template_ids = set()
    
    for i in range(5):
        # Slightly change data, but under 0.1% to trigger NO_CHANGE or MICRO_MOVEMENT
        val = base_val + (i * 5) # 5 dollars is 0.05%
        snapshot = {"totalPortfolioValue": val, "portfolioValue": val, "dailyChangePct": 0.1, "isAth": False}
        benchmark = {"dailyChangePct": 0.1}
        
        res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
        # engine saves it automatically now. We don't double save.
        
        assert res["title"] not in titles or res["commentaryMode"] in ["NO_CHANGE", "MICRO_MOVEMENT"]
        if res.get("templateId"):
            assert res["templateId"] not in template_ids
            template_ids.add(res["templateId"])
            
        titles.add(res["title"])
        
        if i > 0:
            assert res["commentaryMode"] in ["NO_CHANGE", "MICRO_MOVEMENT"]

def test_e2e_case_3_negative_benchmark_positive(mock_db):
    """3. Same user has USER_NEGATIVE_BENCHMARK_POSITIVE scenario for 5 consecutive checks."""
    user_id = "u3"
    titles = set()
    messages = set()
    template_ids = set()
    
    for i in range(5):
        val = 10000 - (i * 200) # Drops 2% each time to force non-micro movement
        snapshot = {"totalPortfolioValue": val, "portfolioValue": val, "dailyChangePct": -2.0, "isAth": False}
        benchmark = {"dailyChangePct": 1.0} # Benchmark up
        
        res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
        # engine saves it automatically now. We don't double save.
        
        assert res["scenarioKey"] == "USER_NEGATIVE_BENCHMARK_POSITIVE"
        assert res["tone"] in ["roast", "neutral", "mixed"] # Must be negative/mixed
        
        if res.get("templateId"):
            assert res["templateId"] not in template_ids
            template_ids.add(res["templateId"])
            
        # Ensure no identical titles
        if res["title"] in titles:
            print(f"FAILED AT ITER {i}: '{res['title']}' in {titles}")
        assert res["title"] not in titles
        titles.add(res["title"])

def test_e2e_case_4_intensity_change(mock_db):
    """4. User changes roast intensity."""
    user_id = "u4"
    snapshot = {"totalPortfolioValue": 10000, "portfolioValue": 10000, "dailyChangePct": -1.5, "isAth": False}
    benchmark = {"dailyChangePct": -0.5}
    
    # 1. Brutal check
    mock_db.settings["roastIntensity"] = "brutal"
    res1 = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
    mock_db.save_roast({
        "userId": user_id,
        "templateId": res1.get("templateId"),
        "title": res1["title"],
        "messageText": res1["message"],
        "totalPortfolioValue": 10000,
        "portfolioReturnPercent": -1.5,
        "benchmarkReturnPercent": -0.5,
        "commentaryMode": res1["commentaryMode"]
    })
    
    # 2. Change to gentle, make a big data change to force a new message
    mock_db.settings["roastIntensity"] = "gentle"
    snapshot2 = {"totalPortfolioValue": 9000, "portfolioValue": 9000, "dailyChangePct": -10.0, "isAth": False}
    res2 = roast_engine.generate_daily_roast(user_id, snapshot2, benchmark)
    
    if res1.get("templateId") and res2.get("templateId"):
        t1 = next((t for t in template_bank.load_templates() if t["templateId"] == res1["templateId"]), None)
        t2 = next((t for t in template_bank.load_templates() if t["templateId"] == res2["templateId"]), None)
        assert t1["intensity"] == "brutal"
        assert t2["intensity"] == "gentle"

@patch('roast_engine._call_llm')
def test_e2e_case_5_ai_similarity_retry(mock_call_llm, mock_db):
    """5. AI returns similar output twice."""
    user_id = "u5"
    snapshot = {"totalPortfolioValue": 10000, "portfolioValue": 10000, "dailyChangePct": -1.5, "isAth": False}
    benchmark = {"dailyChangePct": -0.5}
    
    # Put an existing AI response in history
    mock_db.save_roast({
        "userId": user_id,
        "title": "Terrible Day",
        "messageText": "You lost money today. It is really bad. I can't believe it.",
        "templateId": None,
        "totalPortfolioValue": 10150,
        "portfolioReturnPercent": 0,
        "benchmarkReturnPercent": 0,
        "commentaryMode": "OPENING_CHECK",
        "createdAt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    })
    
    # Mock LLM to return exactly the same text on first call, and on second call as well
    mock_call_llm.side_effect = [
        '{"title": "Terrible Day", "message": "You lost money today. It is really bad. I can\'t believe it.", "tone": "roast", "severity": 5, "mainReason": "loss"}',
        '{"title": "Terrible Day", "message": "You lost money today. It is really bad. I can\'t believe it.", "tone": "roast", "severity": 5, "mainReason": "loss"}'
    ]
    
    res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark, enable_ai=True)
    
    assert mock_call_llm.call_count == 2 # Tried once, retried once
    # Since it failed retry, it fell back to template
    assert res["templateId"] is not None
    assert res["title"] != "Terrible Day"

def test_e2e_case_6_7_template_bank_matching(mock_db):
    """6 & 7. Template bank selection and missing matches."""
    user_id = "u6"
    snapshot = {"totalPortfolioValue": 10000, "portfolioValue": 10000, "dailyChangePct": -1.5, "isAth": False}
    benchmark = {"dailyChangePct": -0.5}
    
    res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
    assert res["templateId"] is not None # Found a match
    assert "title" in res
    
    # Now simulate a bizarre scenario that definitely doesn't exist
    with patch('scenario_classifier.classify_scenario') as mock_classify:
        mock_classify.return_value = {"scenarioKey": "NON_EXISTENT_SCENARIO", "outcomeType": "roast", "severity": 5, "baseIntensity": "brutal"}
        snapshot["totalPortfolioValue"] = 8000 # Force change
        res2 = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
        
        # Should gracefully fall back to the last available template or a generic one without crashing
        assert res2["templateId"] is not None
        assert "title" in res2

def test_e2e_case_8_legacy_records(mock_db):
    """8. Old roast history records have missing fields."""
    user_id = "u8"
    snapshot = {"totalPortfolioValue": 10000, "portfolioValue": 10000, "dailyChangePct": -1.5, "isAth": False}
    benchmark = {"dailyChangePct": -0.5}
    
    # Legacy record missing messageText, templateId, scenarioKey, etc.
    mock_db.save_roast({
        "userId": user_id,
        "text": "Old message format",
        "createdAt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    })
    
    # Should not crash
    res = roast_engine.generate_daily_roast(user_id, snapshot, benchmark)
    assert res["title"] is not None
    assert res["message"] is not None
