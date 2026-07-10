import pytest
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
import template_bank

def test_selector_avoids_repeated_structure():
    templates = [
        {"templateId": "1", "structureFamily": "WEATHER_REPORT", "titleTemplate": "T1"},
        {"templateId": "2", "structureFamily": "SPORTS_COMMENTARY", "titleTemplate": "T2"},
        {"templateId": "3", "structureFamily": "WEATHER_REPORT", "titleTemplate": "T3"}
    ]
    history = [
        {"templateId": "100", "structureFamily": "WEATHER_REPORT", "createdAt": datetime.now(timezone.utc).isoformat()}
    ]
    # Check what gets filtered out
    allowed = template_bank.apply_cooldowns(templates, history, check_titles=True, check_metadata=True)
    # WEATHER_REPORT was used in last roast, so only SPORTS_COMMENTARY should be allowed
    assert len(allowed) == 1
    assert allowed[0]["templateId"] == "2"

def test_selector_avoids_repeated_metaphor():
    templates = [
        {"templateId": "1", "metaphorCategory": "GAMING", "titleTemplate": "T1"},
        {"templateId": "2", "metaphorCategory": "MEDIEVAL", "titleTemplate": "T2"}
    ]
    history = [
        {"templateId": "100", "metaphorCategory": "GAMING", "createdAt": datetime.now(timezone.utc).isoformat()}
    ]
    allowed = template_bank.apply_cooldowns(templates, history, check_titles=True, check_metadata=True)
    assert len(allowed) == 1
    assert allowed[0]["templateId"] == "2"

def test_selector_avoids_metadata_more_than_twice_in_five():
    templates = [
        {"templateId": "1", "structureFamily": "WEATHER_REPORT", "titleTemplate": "T1"},
        {"templateId": "2", "structureFamily": "SPORTS_COMMENTARY", "titleTemplate": "T2"}
    ]
    # Used twice, but NOT the absolute last one (index 0)
    history = [
        {"templateId": "100", "structureFamily": "MEDIEVAL", "createdAt": datetime.now(timezone.utc).isoformat()},
        {"templateId": "101", "structureFamily": "WEATHER_REPORT", "createdAt": datetime.now(timezone.utc).isoformat()},
        {"templateId": "102", "structureFamily": "WEATHER_REPORT", "createdAt": datetime.now(timezone.utc).isoformat()}
    ]
    allowed = template_bank.apply_cooldowns(templates, history, check_titles=True, check_metadata=True)
    assert len(allowed) == 1
    assert allowed[0]["templateId"] == "2"

def test_selector_falls_back_safely():
    templates = [
        {"templateId": "1", "structureFamily": "WEATHER_REPORT", "titleTemplate": "T1"}
    ]
    history = [
        {"templateId": "100", "structureFamily": "WEATHER_REPORT", "createdAt": datetime.now(timezone.utc).isoformat()}
    ]
    
    # If check_metadata is True, it filters it out
    allowed_strict = template_bank.apply_cooldowns(templates, history, check_titles=True, check_metadata=True)
    assert len(allowed_strict) == 0
    
    # If check_metadata is False, it falls back and allows it
    allowed_fallback = template_bank.apply_cooldowns(templates, history, check_titles=True, check_metadata=False)
    assert len(allowed_fallback) == 1
    assert allowed_fallback[0]["templateId"] == "1"

def test_legacy_templates_and_history_work():
    templates = [
        {"templateId": "1", "titleTemplate": "Legacy Template"} # no metadata
    ]
    history = [
        {"templateId": "100", "titleTemplate": "Old History", "createdAt": datetime.now(timezone.utc).isoformat()} # no metadata
    ]
    
    allowed = template_bank.apply_cooldowns(templates, history, check_titles=True, check_metadata=True)
    assert len(allowed) == 1
    assert allowed[0]["templateId"] == "1"
