"""Design system document health, and document-versus-app agreement. Run with ./test.sh design."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "design"))
import design_system as ds  # noqa: E402

pytestmark = pytest.mark.design

STATUSES = {"active", "provisional", "superseded"}
APP_CSS = (ROOT / "src" / "styles" / "main.css").read_text(encoding="utf-8")


def numbered_sections():
    return [n for _, t, _ in ds.headings() if (n := ds.section_number(t))]


def test_section_numbers_are_unique():
    numbers = numbered_sections()
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    assert not duplicates, f"duplicate section numbers: {duplicates}"


def test_chapter_4_has_no_gaps():
    subsections = sorted(int(n.split(".")[1]) for n in numbered_sections() if re.fullmatch(r"4\.\d+", n))
    assert subsections == list(range(1, subsections[-1] + 1)), f"chapter 4 jumps: {subsections}"


def test_every_section_reference_resolves():
    known = set(numbered_sections())
    refs = re.findall(r"Sections? (\d+(?:\.\d+)*)", re.sub(r"`[^`]*`", "CODE", ds.prose_text()))
    missing = sorted({r for r in refs if r not in known})
    assert not missing, f"references to sections that do not exist: {missing}"


def test_no_inline_code_was_lost():
    text = ds.prose_text()
    assert "``" not in text, "empty inline code span"
    stripped = re.sub(r"`[^`]*`", "CODE", text)
    patterns = {
        "empty bold": r"\*\*\*\*",
        "empty parentheses": r"\(\s*\)",
        "parenthesis starting with a comma": r"\(\s*,",
        "comma before closing parenthesis": r",\s*\)",
        "space after opening parenthesis": r"\(\s+\S",
        "space before comma": r"\S ,",
        "double space inside a sentence": r"[A-Za-z]  [A-Za-z]",
    }
    problems = []
    for line in stripped.splitlines():
        if line.startswith("|"):
            continue
        problems += [f"{label}: {line.strip()[:90]}" for label, rx in patterns.items() if re.search(rx, line)]
    assert not problems, "text that looks like lost inline code:\n" + "\n".join(problems)


def test_tokens_file_matches_document():
    assert ds.tokens_file_registry() == ds.registry(), (
        "design/tokens-v9.css differs from Section 2. Regenerate: .venv/bin/python design/design_system.py --write-tokens"
    )


def test_registry_has_both_themes_and_core_tokens():
    reg = ds.registry()
    for token in ("--bg-canvas", "--text-primary", "--accent-primary", "--color-success", "--dur-base", "--ease-enter"):
        assert token in reg["dark"], f"{token} missing from the dark registry"
    assert reg["light_overrides"], "light theme overrides missing"
    assert set(reg["light_overrides"]) <= set(reg["dark"]), "light theme overrides a token the dark theme does not define"


def test_document_css_snippets_use_only_defined_tokens():
    defined = set(ds.registry()["dark"])
    used = {m for block in ds.all_css_fences() for m in re.findall(r"var\(\s*(--[\w-]+)", block)}
    undefined = sorted(used - defined)
    assert not undefined, f"snippets use tokens that Section 2 does not define: {undefined}"


def _solid(theme, token):
    rgba = ds.parse_color(ds.registry()[theme][token])
    assert rgba is not None and rgba[3] == 1.0, f"{theme} {token} is not a solid colour"
    return rgba[:3]


def test_contrast_contract_holds():
    failures = []
    for theme, foregrounds, backgrounds, required in ds.contrast_contract():
        for fg in foregrounds:
            for bg in backgrounds:
                ratio = ds.contrast_ratio(_solid(theme, fg), _solid(theme, bg))
                if ratio < required:
                    failures.append(f"{theme}: {fg} on {bg} is {ratio:.2f}, needs {required}")
    assert not failures, "\n".join(failures)


def test_known_contrast_limits_are_accurate():
    wrong = []
    for theme, fg, bg, documented in ds.known_contrast_limits():
        ratio = ds.contrast_ratio(_solid(theme, fg), _solid(theme, bg))
        if ratio >= 4.5 or abs(ratio - documented) > 0.01:
            wrong.append(f"{theme}: {fg} on {bg} is {ratio:.2f}, documented {documented}")
    assert not wrong, "Known Contrast Limits table is out of date:\n" + "\n".join(wrong)


def test_decision_log_is_well_formed():
    rows = ds.decisions()
    assert rows, "Decision Log is empty"
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate decision ids"
    for row in rows:
        assert re.fullmatch(r"D-\d{3}", row["id"]), f"bad id {row['id']}"
        assert row["status"] in STATUSES, f"{row['id']} has unknown status {row['status']!r}"
        _, kind, _ = ds.parse_check(row["check"])
        if row["status"] != "superseded":
            assert kind != "none", f"{row['id']} is {row['status']} but has no executable check"


def test_mentioned_decisions_and_questions_exist():
    text = ds.prose_text()
    decisions = {r["id"] for r in ds.decisions()}
    questions = set(ds.open_question_ids())
    assert set(re.findall(r"\bD-\d{3}\b", text)) <= decisions, "document mentions a decision id that is not in the log"
    assert set(re.findall(r"\bOQ-\d+\b", text)) <= questions, "document mentions an open question that is not listed"


def test_dashboard_registry_ids_are_unique():
    fields = ds.dashboard_fields()
    assert len(fields) == len(set(fields)), "duplicate field ids in Appendix A"


def test_document_does_not_name_components_the_app_lacks():
    text = ds.prose_text() + "\n".join(ds.all_css_fences())
    for stale in ("#loader", ".loader-container", ".empty-state-container"):
        assert stale not in text, f"{stale} does not exist in the app; use .cl-loader, .card-cl-overlay or .empty-state-card"


def test_components_the_document_calls_existing_are_in_the_app():
    for selector in (".cl-loader", ".card-cl-overlay", ".empty-state-card", "#dash-empty-state"):
        assert selector in ds.prose_text(), f"document no longer mentions {selector}"
        assert selector in APP_CSS, f"{selector} is not defined in src/styles/main.css any more"


def test_light_theme_switch_matches_the_app():
    assert ds.LIGHT_SELECTOR in APP_CSS, "the app no longer switches the light theme with :root[data-theme=\"light\"]"


def test_wordmark_rule_matches_the_manifest():
    manifest = json.loads((ROOT / "src" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "roastfolio" and manifest["short_name"] == "roastfolio"
    assert "all-lowercase `roastfolio`" in ds.prose_text()
