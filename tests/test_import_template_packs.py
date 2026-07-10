import json
import os
import tempfile
import subprocess
import pytest

# Helper to run the script
def run_import_script(input_dir, output_file):
    script_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'import_template_packs.py')
    result = subprocess.run(
        ['python3', script_path, '--input', input_dir, '--output', output_file],
        capture_output=True,
        text=True
    )
    return result

@pytest.fixture
def base_template():
    return {
        "templateId": "test_id_1",
        "scenarioKey": "NEW_ATH_DAY",
        "tone": "praise",
        "intensity": "gentle",
        "messageAngle": "ATH_STATUS",
        "structureFamily": "STATUS_UPDATE",
        "metaphorCategory": "OFFICE",
        "titleTemplate": "Test Title",
        "messageTemplate": "This is a test message. Welcome to {{currency}}{{portfolioValue}}.",
        "mainReasonTemplate": "Test reason.",
        "suggestedFocusTemplate": "Test focus.",
        "requiredData": ["currency", "portfolioValue"],
        "cooldownDays": 14,
        "weight": 1,
        "enabled": True
    }

def test_successful_import_and_report(base_template):
    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        output_file = os.path.join(output_dir, 'roast_templates.json')
        with open(output_file, 'w') as f:
            json.dump([], f)
            
        pack_file = os.path.join(input_dir, 'pack1.json')
        with open(pack_file, 'w') as f:
            json.dump([base_template], f)
            
        run_import_script(input_dir, output_file)
        
        with open(output_file, 'r') as f:
            final_templates = json.load(f)
            
        assert len(final_templates) == 1
        assert final_templates[0]['templateId'] == 'test_id_1'
        
        with open('template_import_report.json', 'r') as f:
            report = json.load(f)
            assert report['attemptedImportCount'] == 1
            assert report['importedCount'] == 1
            assert report['rejectedCount'] == 0
            assert report['finalCount'] == 1

def test_rejects_invalid_json():
    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        output_file = os.path.join(output_dir, 'roast_templates.json')
        with open(output_file, 'w') as f:
            json.dump([], f)
            
        pack_file = os.path.join(input_dir, 'pack1.json')
        with open(pack_file, 'w') as f:
            f.write("[ { invalid json ]")
            
        res = run_import_script(input_dir, output_file)
        
        with open(output_file, 'r') as f:
            final_templates = json.load(f)
        assert len(final_templates) == 0

def test_rejects_duplicate_templateId(base_template):
    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        output_file = os.path.join(output_dir, 'roast_templates.json')
        with open(output_file, 'w') as f:
            json.dump([base_template], f) # already exists
            
        # Try to import same templateId with different message
        new_template = dict(base_template)
        new_template['messageTemplate'] = "Different message"
        
        pack_file = os.path.join(input_dir, 'pack1.json')
        with open(pack_file, 'w') as f:
            json.dump([new_template], f)
            
        run_import_script(input_dir, output_file)
        
        with open('template_import_report.json', 'r') as f:
            report = json.load(f)
            assert report['rejectedCount'] == 1
            assert report['rejections'][0]['reason'] == 'Duplicate templateId'

def test_rejects_duplicate_messageTemplate(base_template):
    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        output_file = os.path.join(output_dir, 'roast_templates.json')
        with open(output_file, 'w') as f:
            json.dump([base_template], f)
            
        new_template = dict(base_template)
        new_template['templateId'] = "test_id_2"
        
        pack_file = os.path.join(input_dir, 'pack1.json')
        with open(pack_file, 'w') as f:
            json.dump([new_template], f)
            
        run_import_script(input_dir, output_file)
        
        with open('template_import_report.json', 'r') as f:
            report = json.load(f)
            assert report['rejectedCount'] == 1
            assert report['rejections'][0]['reason'] == 'Exact duplicate messageTemplate'

def test_rejects_near_duplicate_templates(base_template):
    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        output_file = os.path.join(output_dir, 'roast_templates.json')
        with open(output_file, 'w') as f:
            json.dump([base_template], f)
            
        new_template = dict(base_template)
        new_template['templateId'] = "test_id_2"
        # Only changed one word, should be caught by similarity_detector
        new_template['messageTemplate'] = "This is a test message. Hello to {{currency}}{{totalPortfolioValue}}."
        
        pack_file = os.path.join(input_dir, 'pack1.json')
        with open(pack_file, 'w') as f:
            json.dump([new_template], f)
            
        run_import_script(input_dir, output_file)
        
        with open('template_import_report.json', 'r') as f:
            report = json.load(f)
            assert report['rejectedCount'] == 1
            assert "Near-duplicate" in report['rejections'][0]['reason']

def test_rejects_unsupported_placeholders(base_template):
    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        output_file = os.path.join(output_dir, 'roast_templates.json')
        with open(output_file, 'w') as f: json.dump([], f)
            
        base_template['messageTemplate'] = "Hello {{fake_data}}"
        base_template['requiredData'] = ["fake_data"]
        
        pack_file = os.path.join(input_dir, 'pack1.json')
        with open(pack_file, 'w') as f: json.dump([base_template], f)
            
        run_import_script(input_dir, output_file)
        
        with open('template_import_report.json', 'r') as f:
            report = json.load(f)
            assert report['rejectedCount'] == 1
            assert "Unsupported placeholders" in report['rejections'][0]['reason']

def test_rejects_unsupported_enum_values(base_template):
    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        output_file = os.path.join(output_dir, 'roast_templates.json')
        with open(output_file, 'w') as f: json.dump([], f)
            
        base_template['scenarioKey'] = "UNKNOWN_SCENARIO"
        
        pack_file = os.path.join(input_dir, 'pack1.json')
        with open(pack_file, 'w') as f: json.dump([base_template], f)
            
        run_import_script(input_dir, output_file)
        
        with open('template_import_report.json', 'r') as f:
            report = json.load(f)
            assert report['rejectedCount'] == 1
            assert "Unknown scenarioKey" in report['rejections'][0]['reason']

def test_deterministic_sort(base_template):
    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        output_file = os.path.join(output_dir, 'roast_templates.json')
        with open(output_file, 'w') as f: json.dump([], f)
            
        t1 = dict(base_template)
        t1['templateId'] = "id_2"
        t1['messageTemplate'] = "Message 2"
        t1['scenarioKey'] = "NEW_ATH_DAY"
        
        t2 = dict(base_template)
        t2['templateId'] = "id_1"
        t2['titleTemplate'] = "Different Title"
        t2['messageTemplate'] = "Completely unique text here to avoid similarity."
        t2['scenarioKey'] = "BOTH_FLAT" # Should come first alphabetically
        
        pack_file = os.path.join(input_dir, 'pack1.json')
        with open(pack_file, 'w') as f: json.dump([t1, t2], f)
            
        run_import_script(input_dir, output_file)
        
        with open(output_file, 'r') as f:
            final_templates = json.load(f)
            assert len(final_templates) == 2
            # BOTH_FLAT comes before NEW_ATH_DAY
            assert final_templates[0]['templateId'] == "id_1"
            assert final_templates[1]['templateId'] == "id_2"
