import json
import os
import tempfile
import subprocess
import pytest

def run_analyzer(template_file):
    script_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'template_coverage_report.py')
    result = subprocess.run(
        ['python3', script_path, '--input', template_file],
        capture_output=True,
        text=True
    )
    return result

@pytest.fixture
def valid_template():
    return {
        "templateId": "test_1",
        "scenarioKey": "NEW_ATH_DAY",
        "tone": "praise",
        "intensity": "gentle",
        "messageAngle": "ATH_STATUS",
        "structureFamily": "STATUS_UPDATE",
        "metaphorCategory": "OFFICE",
        "titleTemplate": "Test Title",
        "messageTemplate": "This is a test message with {{portfolioValue}}.",
        "requiredData": ["portfolioValue"],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    }

def test_successful_analysis(valid_template):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        json.dump([valid_template], f)
        f.flush()
        
    try:
        res = run_analyzer(f.name)
        assert res.returncode == 0
        
        with open('template_coverage_report.json', 'r') as r:
            report = json.load(r)
            
        assert report['dimensions']['total_enabled'] == 1
        # It's expected to have missing targets because we only have 1 template
        assert "NEW_ATH_DAY" in report['dimensions']['scenarios_below_target']
    finally:
        os.remove(f.name)

def test_critical_error_invalid_json():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("[ invalid json ]")
        f.flush()
        
    try:
        res = run_analyzer(f.name)
        assert res.returncode == 1
        assert "Invalid JSON" in res.stdout
    finally:
        os.remove(f.name)

def test_critical_error_duplicate_id(valid_template):
    t2 = dict(valid_template)
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        json.dump([valid_template, t2], f)
        f.flush()
        
    try:
        res = run_analyzer(f.name)
        assert res.returncode == 1
        assert "Duplicate templateId" in res.stdout
    finally:
        os.remove(f.name)

def test_critical_error_unsupported_placeholder(valid_template):
    t2 = dict(valid_template)
    t2['messageTemplate'] = "Hello {{invalid_placeholder}}"
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        json.dump([t2], f)
        f.flush()
        
    try:
        res = run_analyzer(f.name)
        assert res.returncode == 1
        assert "Unsupported placeholders" in res.stdout
    finally:
        os.remove(f.name)

def test_critical_error_invalid_enum(valid_template):
    t2 = dict(valid_template)
    t2['scenarioKey'] = "FROGS_IN_SPACE"
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        json.dump([t2], f)
        f.flush()
        
    try:
        res = run_analyzer(f.name)
        assert res.returncode == 1
        assert "Invalid scenarioKey" in res.stdout
    finally:
        os.remove(f.name)
