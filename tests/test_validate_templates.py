import sys
import os
import json
import tempfile
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from validate_templates import validate

def test_validate_success():
    templates = [
        {
            "templateId": "test_1",
            "scenarioKey": "USER_NEGATIVE_BENCHMARK_POSITIVE",
            "intensity": "sarcastic",
            "messageAngle": "BENCHMARK_COMPARISON",
            "tone": "roast",
            "titleTemplate": "Test Title",
            "messageTemplate": "This is a {{portfolioValue}} test."
        }
    ]
    # We duplicate it 50 times with different intensities/angles to pass coverage rules
    valid = []
    for i in range(50):
        t = dict(templates[0])
        t["templateId"] = f"test_{i}"
        t["titleTemplate"] = f"Test Title {i}"
        t["messageTemplate"] = f"This is a {i} test."
        t["intensity"] = ["gentle", "sarcastic", "brutal", "degen"][i % 4]
        t["messageAngle"] = ["BENCHMARK_COMPARISON", "ABSOLUTE_RETURN", "RELATIVE_RETURN", "BEST_ASSET"][i % 4]
        valid.append(t)
        
    for hp in ["NO_MEANINGFUL_CHANGE", "BOTH_NEGATIVE_USER_WORSE"]:
        for i in range(50):
            t = dict(templates[0])
            t["templateId"] = f"{hp}_{i}"
            t["scenarioKey"] = hp
            t["titleTemplate"] = f"{hp} Title {i}"
            t["messageTemplate"] = f"{hp} {i} test."
            t["intensity"] = ["gentle", "sarcastic", "brutal", "degen"][i % 4]
            t["messageAngle"] = ["BENCHMARK_COMPARISON", "ABSOLUTE_RETURN", "RELATIVE_RETURN", "BEST_ASSET"][i % 4]
            valid.append(t)
            
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        json.dump(valid, f)
        temp_path = f.name
        
    assert validate(temp_path) is True
    os.remove(temp_path)

def test_validate_forbidden_term():
    templates = [
        {
            "templateId": "test_bad",
            "scenarioKey": "USER_NEGATIVE_BENCHMARK_POSITIVE",
            "intensity": "sarcastic",
            "messageAngle": "BENCHMARK_COMPARISON",
            "tone": "roast",
            "titleTemplate": "Bad",
            "messageTemplate": "You should sell this immediately."
        }
    ]
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        json.dump(templates, f)
        temp_path = f.name
        
    assert validate(temp_path) is False
    os.remove(temp_path)

def test_validate_unsupported_placeholder():
    templates = [
        {
            "templateId": "test_bad",
            "scenarioKey": "USER_NEGATIVE_BENCHMARK_POSITIVE",
            "intensity": "sarcastic",
            "messageAngle": "BENCHMARK_COMPARISON",
            "tone": "roast",
            "titleTemplate": "Bad",
            "messageTemplate": "Value: {{unsupported}}"
        }
    ]
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        json.dump(templates, f)
        temp_path = f.name
        
    assert validate(temp_path) is False
    os.remove(temp_path)
