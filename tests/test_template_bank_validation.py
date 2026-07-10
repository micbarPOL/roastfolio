import json
import os
import re
import pytest
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'roast_templates.json')

MAJOR_SCENARIOS = [
    "BOTH_NEGATIVE_USER_BETTER",
    "BOTH_NEGATIVE_USER_WORSE",
    "BOTH_POSITIVE_USER_BETTER",
    "BOTH_POSITIVE_USER_WORSE",
    "USER_POSITIVE_BENCHMARK_NEGATIVE",
    "USER_NEGATIVE_BENCHMARK_POSITIVE",
    "USER_OUTPERFORMED_BY_LARGE_MARGIN",
    "USER_UNDERPERFORMED_BY_LARGE_MARGIN",
    "NEW_ATH_DAY",
    "DRAWDOWN_SIGNIFICANT",
    "BEST_ASSET_CARRIED_PORTFOLIO",
    "WORST_ASSET_DRAGGED_PORTFOLIO",
    "DEPOSIT_POSITIVE_BEHAVIOR",
    "WITHDRAWAL_DETECTED",
    "NO_MEANINGFUL_CHANGE",
]

INTENSITIES = ["gentle", "sarcastic", "brutal", "degen"]

SUPPORTED_PLACEHOLDERS = {
    "portfolioReturnPercent", "benchmarkReturnPercent", "relativePerformancePercent",
    "benchmarkName", "dailyBestAsset", "dailyWorstAsset", "totalPortfolioValue",
    "currentDrawdownFromATH", "depositStreak", "withdrawalFreeStreak", "currency",
    "largestWalletMover",
}

FORBIDDEN_WORDS = [
    r"\bbuy\b", r"\bsell\b", r"\bhold\b", r"\bshort\b",
    r"\bleverage\b", r"\ball[- ]in\b", r"\bdouble down\b",
]

@pytest.fixture(scope="module")
def templates():
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_templates_load(templates):
    assert isinstance(templates, list)
    assert len(templates) > 0


def test_all_template_ids_unique(templates):
    ids = [t["templateId"] for t in templates]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {[x for x in ids if ids.count(x) > 1]}"


def test_every_major_scenario_has_templates(templates):
    present = {t["scenarioKey"] for t in templates}
    for scenario in MAJOR_SCENARIOS:
        assert scenario in present, f"Missing templates for scenario: {scenario}"


def test_every_major_scenario_has_at_least_20(templates):
    from collections import Counter
    counts = Counter(t["scenarioKey"] for t in templates if t["scenarioKey"] in MAJOR_SCENARIOS)
    for scenario in MAJOR_SCENARIOS:
        assert counts.get(scenario, 0) >= 20, (
            f"Scenario {scenario} has only {counts.get(scenario, 0)} templates, expected >= 20"
        )


def test_every_intensity_has_coverage(templates):
    for scenario in MAJOR_SCENARIOS:
        scenario_templates = [t for t in templates if t["scenarioKey"] == scenario]
        intensities_present = {t["intensity"] for t in scenario_templates}
        for intensity in INTENSITIES:
            assert intensity in intensities_present, (
                f"Scenario {scenario} is missing intensity: {intensity}"
            )


def test_required_placeholders_are_supported(templates):
    for t in templates:
        for req in t.get("requires", []):
            assert req in SUPPORTED_PLACEHOLDERS, (
                f"Template {t['templateId']} requires unsupported placeholder: {req}"
            )


def test_placeholders_in_text_are_valid(templates):
    all_text_fields = ["titleTemplate", "messageTemplate", "mainReasonTemplate", "suggestedFocusTemplate"]
    for t in templates:
        for field in all_text_fields:
            text = t.get(field)
            if not text:
                continue
            found = re.findall(r"\{\{(\w+)\}\}", text)
            for placeholder in found:
                assert placeholder in SUPPORTED_PLACEHOLDERS, (
                    f"Template {t['templateId']} field '{field}' uses unsupported placeholder: {{{{{placeholder}}}}}"
                )


def test_templates_pass_safety_validator(templates):
    for t in templates:
        text_fields = [
            t.get("messageTemplate", ""),
            t.get("titleTemplate", ""),
            t.get("mainReasonTemplate", ""),
            t.get("suggestedFocusTemplate", ""),
        ]
        combined = " ".join(f for f in text_fields if f).lower()
        for pattern in FORBIDDEN_WORDS:
            matches = re.findall(pattern, combined, re.IGNORECASE)
            assert not matches, (
                f"Template {t['templateId']} contains forbidden word matching '{pattern}': found '{matches}'"
            )


def test_no_template_starts_with_your_portfolio_repeatedly(templates):
    """At most 10% of templates should start with 'Your portfolio'."""
    offending = [
        t["templateId"] for t in templates
        if t.get("messageTemplate", "").lower().startswith("your portfolio")
    ]
    max_allowed = len(templates) * 0.10
    assert len(offending) <= max_allowed, (
        f"{len(offending)} templates start with 'Your portfolio' (max allowed: {int(max_allowed)}). "
        f"Offenders: {offending[:10]}"
    )


def test_template_structure_schema(templates):
    required_keys = {"templateId", "scenarioKey", "tone", "intensity", "messageType", "weight", "cooldownDays", "requires", "messageTemplate"}
    for t in templates:
        for key in required_keys:
            assert key in t, f"Template {t.get('templateId', 'UNKNOWN')} is missing required key: {key}"
