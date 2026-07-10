import pytest
from datetime import datetime, timezone, timedelta
import sys
import os

# Ensure lambda directory is in path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
from roast_history import check_cooldowns, _get_opening_phrase, get_latest_roast_today
from unittest.mock import patch, MagicMock

def test_opening_phrase_extraction():
    assert _get_opening_phrase("You lost money today, unfortunately.") == "you lost money today unfortunately"
    assert _get_opening_phrase("You lost money") == "you lost money"
    assert _get_opening_phrase("   WOW! This is a test.   ") == "wow this is a test"

def test_cooldown_exact_message_rejected():
    now = datetime.now(timezone.utc)
    
    candidate = {
        "messageHash": "hash123",
        "messageText": "Hello world"
    }
    
    # 89 days ago -> rejected (90 day cooldown)
    history = [{
        "createdAt": (now - timedelta(days=89)).isoformat(),
        "messageHash": "hash123"
    }]
    
    res = check_cooldowns(candidate, history)
    assert not res["allowed"]
    assert "90-day" in res["reason"]

def test_cooldown_exact_message_allowed():
    now = datetime.now(timezone.utc)
    candidate = {"messageHash": "hash123", "messageText": "Hello world"}
    
    # 91 days ago -> allowed
    history = [{
        "createdAt": (now - timedelta(days=91)).isoformat(),
        "messageHash": "hash123"
    }]
    
    res = check_cooldowns(candidate, history)
    assert res["allowed"]

def test_cooldown_template_id_rejected():
    now = datetime.now(timezone.utc)
    candidate = {"templateId": "tpl_01", "messageText": "Different message entirely"}
    
    # 13 days ago -> rejected (14 day cooldown)
    history = [{
        "createdAt": (now - timedelta(days=13)).isoformat(),
        "templateId": "tpl_01",
        "messageText": "Something else"
    }]
    
    res = check_cooldowns(candidate, history)
    assert not res["allowed"]
    assert "14-day" in res["reason"]

def test_cooldown_template_id_allowed():
    now = datetime.now(timezone.utc)
    candidate = {"templateId": "tpl_01", "messageText": "Different message"}
    
    # 15 days ago -> allowed
    history = [{
        "createdAt": (now - timedelta(days=15)).isoformat(),
        "templateId": "tpl_01",
        "messageText": "Something else"
    }]
    
    res = check_cooldowns(candidate, history)
    assert res["allowed"]

def test_cooldown_opening_phrase_rejected():
    now = datetime.now(timezone.utc)
    candidate = {"messageText": "You underperformed the benchmark again. Stop doing that."}
    
    # 6 days ago -> rejected (7 day cooldown)
    history = [{
        "createdAt": (now - timedelta(days=6)).isoformat(),
        "messageText": "You underperformed the benchmark again. But this time it's worse."
    }]
    
    res = check_cooldowns(candidate, history)
    assert not res["allowed"]
    assert "opening phrase" in res["reason"].lower()

def test_cooldown_opening_phrase_allowed():
    now = datetime.now(timezone.utc)
    candidate = {"messageText": "You underperformed the benchmark again. Stop doing that."}
    
    # 8 days ago -> allowed
    history = [{
        "createdAt": (now - timedelta(days=8)).isoformat(),
        "messageText": "You underperformed the benchmark again. But this time it's worse."
    }]
    
    res = check_cooldowns(candidate, history)
    assert res["allowed"]

def test_scenario_reuse_is_allowed():
    now = datetime.now(timezone.utc)
    candidate = {
        "scenarioKey": "BOTH_NEGATIVE_USER_WORSE",
        "templateId": "tpl_02",
        "messageText": "Totally different text."
    }
    
    # 1 day ago -> allowed (same scenario is fine, as long as template/message/phrase are different)
    history = [{
        "createdAt": (now - timedelta(days=1)).isoformat(),
        "scenarioKey": "BOTH_NEGATIVE_USER_WORSE",
        "templateId": "tpl_01",
        "messageText": "Wow, this is a bad day."
    }]
    
    res = check_cooldowns(candidate, history)
    assert res["allowed"]

@patch('roast_history.get_table')
def test_get_latest_roast_today(mock_get_table):
    mock_table = MagicMock()
    mock_get_table.return_value = mock_table
    
    # Mocking query response
    now = datetime.now(timezone.utc)
    mock_table.query.return_value = {
        'Items': [{
            'id': 'roast-1',
            'createdAt': now.isoformat()
        }]
    }
    
    res = get_latest_roast_today("user123")
    
    assert res is not None
    assert res['id'] == 'roast-1'
    mock_table.query.assert_called_once()
    
    # check that Limit=1 was passed
    _, kwargs = mock_table.query.call_args
    assert kwargs.get('Limit') == 1
    assert "createdAt >= :startOfDay" in kwargs.get('KeyConditionExpression')

@patch('roast_history.get_table')
def test_get_latest_roast_today_empty(mock_get_table):
    mock_table = MagicMock()
    mock_get_table.return_value = mock_table
    mock_table.query.return_value = {'Items': []}
    
    res = get_latest_roast_today("user123")
    assert res is None

from roast_history import is_too_similar_to_recent_message

def test_is_too_similar_exact_match():
    new_msg = {"messageText": "This is an exact match!"}
    recent = [{"id": "1", "messageText": "This is an exact match!"}]
    res = is_too_similar_to_recent_message(new_msg, recent)
    assert res["tooSimilar"] is True
    assert res["reason"] == "Exact message match."

def test_is_too_similar_same_opening():
    new_msg = {"messageText": "Wow you lost money today, that is sad."}
    recent = [{"id": "1", "messageText": "Wow you lost money today, I can't believe it."}]
    res = is_too_similar_to_recent_message(new_msg, recent)
    assert res["tooSimilar"] is True
    assert res["reason"] == "Same opening phrase."

def test_is_too_similar_minor_wording_changes():
    # Only a few stop words changed
    new_msg = {"messageText": "The portfolio dropped like a rock yesterday."}
    recent = [{"id": "1", "messageText": "Portfolio dropped like rock yesterday."}]
    res = is_too_similar_to_recent_message(new_msg, recent)
    assert res["tooSimilar"] is True
    assert "High token overlap" in res["reason"]

def test_is_too_similar_trigrams():
    # Distinctive phrasing overlap
    new_msg = {"messageText": "Totally different start but it dropped like a heavy rock from space."}
    recent = [{"id": "1", "messageText": "Yesterday it dropped like a heavy rock and crashed."}]
    res = is_too_similar_to_recent_message(new_msg, recent, {"token_overlap_threshold": 0.9, "trigram_overlap_threshold": 0.2})
    assert res["tooSimilar"] is True
    assert "distinctive phrase overlap" in res["reason"]

def test_genuinely_different_messages():
    new_msg = {"messageText": "Good job making a profit."}
    recent = [{"id": "1", "messageText": "You lost money today, that is sad."}]
    res = is_too_similar_to_recent_message(new_msg, recent)
    assert res["tooSimilar"] is False
