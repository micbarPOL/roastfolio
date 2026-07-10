import pytest
import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
import generate_templates
import validate_templates

def test_generator_produces_valid_schema():
    templates = generate_templates.generate_templates()
    assert len(templates) >= 1000
    
    # Check schema
    t = templates[0]
    assert "templateId" in t
    assert "scenarioKey" in t
    assert "tone" in t
    assert "intensity" in t
    assert "messageAngle" in t
    assert "structureFamily" in t
    assert "metaphorCategory" in t
    assert "titleTemplate" in t
    assert "messageTemplate" in t
    
def test_generator_avoids_duplicate_ids():
    templates = generate_templates.generate_templates()
    ids = [t["templateId"] for t in templates]
    assert len(ids) == len(set(ids))

def test_generator_avoids_exact_duplicate_messages():
    templates = generate_templates.generate_templates()
    msgs = [t["messageTemplate"] for t in templates]
    assert len(msgs) == len(set(msgs))
    
def test_generator_bank_passes_validation():
    # Write to a temp file and run validator
    templates = generate_templates.generate_templates()
    test_filepath = "/tmp/test_roast_templates.json"
    with open(test_filepath, "w", encoding="utf-8") as f:
        json.dump(templates, f)
        
    success = validate_templates.validate(test_filepath)
    assert success is True
