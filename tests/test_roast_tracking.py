import pytest

pytestmark = pytest.mark.full

import pytest
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
import roast_tracking

class MockTable:
    def __init__(self):
        self.called = False
        self.scan_return = {}

    def put_item(self, Item):
        self.called = True

    def scan(self, **kwargs):
        return self.scan_return

def test_record_event_valid(monkeypatch):
    mock_table = MockTable()
    monkeypatch.setattr(roast_tracking, "get_table", lambda: mock_table)
    
    payload = {
        "userId": "user-1",
        "templateId": "T-100",
        "eventType": "roast_displayed",
        "scenarioKey": "SCENARIO_1"
    }
    
    res = roast_tracking.record_event(payload)
    assert res["eventType"] == "roast_displayed"
    assert res["templateId"] == "T-100"
    assert mock_table.called


def test_fallback_and_wrong_reaction_events_persist_selection_context(monkeypatch):
    class CapturingTable(MockTable):
        def __init__(self):
            super().__init__()
            self.items = []

        def put_item(self, Item):
            self.called = True
            self.items.append(Item)

    table = CapturingTable()
    monkeypatch.setattr(roast_tracking, "get_table", lambda: table)
    selection_context = {"scenario": {"scenarioKey": "BOTH_NEGATIVE_USER_WORSE"}, "templateCriteria": {"intensity": "sarcastic"}}

    fallback = roast_tracking.record_event({
        "userId": "user-1", "eventType": "roast_fallback_displayed", "source": "deterministic_fallback",
        "scenarioKey": "BOTH_NEGATIVE_USER_WORSE", "selectionContext": selection_context,
    })
    wrong = roast_tracking.record_event({
        "userId": "user-1", "eventType": "roast_reacted_negative", "reaction": "wrong",
        "scenarioKey": "BOTH_NEGATIVE_USER_WORSE", "selectionContext": selection_context,
    })

    assert fallback["eventType"] == "roast_fallback_displayed"
    assert wrong["reaction"] == "wrong"
    assert table.items[0]["selectionContext"] == selection_context
    assert table.items[1]["selectionContext"] == selection_context

def test_record_event_invalid_type():
    payload = {
        "eventType": "invalid_event"
    }
    with pytest.raises(ValueError, match="Invalid eventType: invalid_event"):
        roast_tracking.record_event(payload)

def test_record_event_invalid_reaction():
    payload = {
        "eventType": "roast_reacted_positive",
        "reaction": "awesome"
    }
    with pytest.raises(ValueError, match="Invalid reaction: awesome"):
        roast_tracking.record_event(payload)

def test_get_template_report(monkeypatch):
    mock_table = MockTable()
    mock_table.scan_return = {
        "Items": [
            {"templateId": "T-1", "eventType": "roast_displayed", "scenarioKey": "S-1"},
            {"templateId": "T-1", "eventType": "roast_reacted_negative", "reaction": "too harsh", "scenarioKey": "S-1"},
            {"templateId": "T-1", "eventType": "roast_displayed", "scenarioKey": "S-1"},
            {"templateId": "T-1", "eventType": "roast_displayed", "scenarioKey": "S-1"},
            {"templateId": "T-1", "eventType": "roast_displayed", "scenarioKey": "S-1"},
            {"templateId": "T-1", "eventType": "roast_displayed", "scenarioKey": "S-1"},
            {"templateId": "T-1", "eventType": "roast_reacted_negative", "reaction": "repetitive", "scenarioKey": "S-1"},
            {"templateId": "T-1", "eventType": "roast_reacted_negative", "reaction": "too harsh", "scenarioKey": "S-1"},
        ]
    }
    monkeypatch.setattr(roast_tracking, "get_table", lambda: mock_table)
    
    report = roast_tracking.get_template_report()
    
    assert "T-1" in report["templates"]
    stats = report["templates"]["T-1"]
    assert stats["displayCount"] == 5
    assert stats["negativeRate"] == 3 / 5  # 0.6
    
    disable_cands = report["disable_candidates"]
    assert len(disable_cands) == 1
    assert disable_cands[0]["templateId"] == "T-1"
    assert disable_cands[0]["reason"] == "high_negative_rate"
