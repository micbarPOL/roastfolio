import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from angle_selector import determine_eligible_angles, selectPreferredMessageAngle

def test_avoids_same_angle_twice_in_a_row():
    params = {
        "scenarioKey": "BOTH_NEGATIVE_USER_BETTER",
        "availableAngles": ["BENCHMARK_COMPARISON", "WORST_ASSET"],
        "recentRoasts": [{"messageAngle": "BENCHMARK_COMPARISON"}]
    }
    angle = selectPreferredMessageAngle(params)
    assert angle == "WORST_ASSET"

def test_allows_same_angle_if_only_option():
    params = {
        "scenarioKey": "BOTH_NEGATIVE_USER_BETTER",
        "availableAngles": ["BENCHMARK_COMPARISON"],
        "recentRoasts": [{"messageAngle": "BENCHMARK_COMPARISON"}]
    }
    angle = selectPreferredMessageAngle(params)
    assert angle == "BENCHMARK_COMPARISON"

def test_prioritizes_no_change_when_data_barely_changed():
    params = {
        "scenarioKey": "NO_MEANINGFUL_CHANGE",
        "availableAngles": ["BENCHMARK_COMPARISON", "NO_CHANGE"],
        "recentRoasts": [],
        "commentaryMode": "NO_CHANGE"
    }
    angle = selectPreferredMessageAngle(params)
    assert angle == "NO_CHANGE"

def test_avoids_angle_used_more_than_twice_in_last_5():
    params = {
        "scenarioKey": "BOTH_NEGATIVE_USER_BETTER",
        "availableAngles": ["BENCHMARK_COMPARISON", "WORST_ASSET", "BEST_ASSET"],
        "recentRoasts": [
            {"messageAngle": "WORST_ASSET"},
            {"messageAngle": "BENCHMARK_COMPARISON"},
            {"messageAngle": "BENCHMARK_COMPARISON"},
            {"messageAngle": "BEST_ASSET"},
            {"messageAngle": "BENCHMARK_COMPARISON"}
        ]
    }
    # BENCHMARK_COMPARISON appears 3 times in last 5.
    # WORST_ASSET is last_used.
    # So strictly available should be just BEST_ASSET.
    angle = selectPreferredMessageAngle(params)
    assert angle == "BEST_ASSET"

def test_handles_missing_history_safely():
    params = {
        "scenarioKey": "BOTH_NEGATIVE_USER_BETTER",
        "availableAngles": ["WORST_ASSET", "BENCHMARK_COMPARISON"],
        "recentRoasts": None
    }
    angle = selectPreferredMessageAngle(params)
    assert angle in ["WORST_ASSET", "BENCHMARK_COMPARISON"]

def test_ordinary_same_direction_day_does_not_offer_benchmark_by_default():
    angles = determine_eligible_angles(
        {"dailyChangePct": 0.4, "isAth": False},
        {"dailyChangePct": 0.2},
        "OPENING_CHECK"
    )
    assert "BENCHMARK_COMPARISON" not in angles
    assert "RELATIVE_RETURN" not in angles
    assert "GENERAL_MARKET_CHAOS" in angles
    assert "ABSOLUTE_RETURN" in angles

def test_benchmark_angle_still_available_for_opposite_sign_day():
    angles = determine_eligible_angles(
        {"dailyChangePct": -0.4, "isAth": False},
        {"dailyChangePct": 0.2},
        "OPENING_CHECK"
    )
    assert "BENCHMARK_COMPARISON" in angles
    assert "RELATIVE_RETURN" in angles

def test_prefers_general_commentary_over_benchmark_for_ordinary_day():
    params = {
        "scenarioKey": "BOTH_POSITIVE_USER_WORSE",
        "availableAngles": ["BENCHMARK_COMPARISON", "GENERAL_MARKET_CHAOS", "ABSOLUTE_RETURN"],
        "recentRoasts": []
    }
    angle = selectPreferredMessageAngle(params)
    assert angle == "GENERAL_MARKET_CHAOS"
