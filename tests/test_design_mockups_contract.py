"""Mockups versus the design system: rules, Decision Log checks and the screen data inventory.

Static, no browser. Run with ./test.sh design.
"""
import re
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "design"))
import design_system as ds  # noqa: E402

pytestmark = pytest.mark.design

MOCKUP_FILES = sorted(ds.MOCKUPS.glob("*.html"))
FORBIDDEN_ANIMATED = {"width", "height", "margin", "padding", "top", "left", "right", "bottom",
                      "min-width", "min-height", "max-width", "max-height", "all"}
TIME_MIN_MS, TIME_MAX_MS = 150, 300
FINANCIAL = re.compile(r"[+\-−]?\d[\d\s\u00a0]*[.,]\d+|\d\s*%|\d[\d\s\u00a0]*\s?(?:PLN|USD|EUR)\b|\d{4}-\d{2}-\d{2}")
COLOR_PROPS = {"color", "background", "background-color", "border-color", "border", "border-left", "border-right",
               "border-top", "border-bottom", "fill", "stroke", "outline", "outline-color", "box-shadow",
               "text-shadow", "stop-color", "caret-color"}
RADIUS_OK = re.compile(r"^(var\(--radius-(sm|md|lg|xl)\)|0|50%|999px|2px|inherit)$")


class Mockup:
    def __init__(self, path):
        self.path = path
        self.html = path.read_text(encoding="utf-8")
        self.soup = BeautifulSoup(self.html, "html.parser")
        self.css_paths = [(path.parent / link["href"]).resolve() for link in self.soup.find_all("link", rel="stylesheet")]
        self.token_paths = [p for p in self.css_paths if p == ds.TOKENS_CSS.resolve()]
        self.own_paths = [p for p in self.css_paths if p not in self.token_paths]
        self.own_css = "\n".join(p.read_text(encoding="utf-8") for p in self.own_paths)
        self.all_css = self.own_css + "\n" + "\n".join(p.read_text(encoding="utf-8") for p in self.token_paths)
        self.rules = ds.parse_css(self.own_css)
        self.tokens = ds.registry()["dark"]

    def inline_styles(self):
        return [(tag.name, tag["style"]) for tag in self.soup.find_all(style=True)]

    def resolve(self, value):
        def sub(match):
            return self.tokens.get(match.group(1), match.group(0))
        return re.sub(r"var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)", sub, value)

    def declared_custom_props(self):
        declared = {prop for rule in self.rules for prop, _ in rule.declarations if prop.startswith("--")}
        for _, style in self.inline_styles():
            declared |= set(re.findall(r"(--[\w-]+)\s*:", style))
        return declared


def mockups():
    return [pytest.param(Mockup(p), id=p.stem) for p in MOCKUP_FILES]


def split_top(value, sep):
    parts, depth, current = [], 0, ""
    for ch in value:
        depth += (ch == "(") - (ch == ")")
        if ch == sep and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    parts.append(current.strip())
    return [p for p in parts if p]


def words(value):
    parts, depth, current = [], 0, ""
    for ch in value:
        depth += (ch == "(") - (ch == ")")
        if ch.isspace() and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return [p for p in parts if p]


def to_ms(token):
    match = re.fullmatch(r"(\d*\.?\d+)(ms|s)", token)
    if not match:
        return None
    return float(match.group(1)) * (1000 if match.group(2) == "s" else 1)


def reduced_motion(rule):
    return any("prefers-reduced-motion" in c for c in rule.context)


def test_there_is_a_dashboard_mockup():
    assert (ds.MOCKUPS / "dashboard.html").exists()


@pytest.mark.parametrize("mock", mockups())
def test_mockup_links_generated_tokens_and_declares_its_screen(mock):
    assert mock.token_paths, "mockup must link design/tokens-v9.css"
    assert mock.soup.html.get("data-mockup") == mock.path.stem
    assert mock.soup.html.get("data-theme") in ("dark", "light")


@pytest.mark.parametrize("mock", mockups())
def test_no_hardcoded_colours(mock):
    problems = []
    for rule in mock.rules:
        for prop, value in rule.declarations:
            bare = re.sub(r"url\([^)]*\)", "", value)
            if re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(", bare):
                problems.append(f"{rule.selector} {prop}: {value}")
            if prop in COLOR_PROPS and re.search(r"\b(?:black|white)\b", bare):
                problems.append(f"{rule.selector} {prop}: {value} (pure black or white)")
    for tag, style in mock.inline_styles():
        if re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(", style):
            problems.append(f"inline style on <{tag}>: {style}")
    for attr in ("fill", "stroke", "stop-color", "color", "flood-color"):
        for tag in mock.soup.find_all(attrs={attr: True}):
            if re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(", tag[attr]):
                problems.append(f"<{tag.name} {attr}={tag[attr]}>")
    assert not problems, "hardcoded colours (use tokens):\n" + "\n".join(problems)


@pytest.mark.parametrize("mock", mockups())
def test_every_custom_property_is_a_token_or_declared_locally(mock):
    used = set(re.findall(r"var\(\s*(--[\w-]+)", mock.own_css))
    for _, style in mock.inline_styles():
        used |= set(re.findall(r"var\(\s*(--[\w-]+)", style))
    unknown = sorted(used - set(mock.tokens) - mock.declared_custom_props())
    assert not unknown, f"undefined custom properties: {unknown}"


@pytest.mark.parametrize("mock", mockups())
def test_local_custom_properties_do_not_shadow_tokens(mock):
    shadowed = sorted(mock.declared_custom_props() & set(mock.tokens))
    assert not shadowed, f"mockup redefines design tokens: {shadowed}"


@pytest.mark.parametrize("mock", mockups())
def test_border_radius_uses_tokens(mock):
    bad = []
    for rule in mock.rules:
        for prop, value in rule.declarations:
            if prop == "border-radius" and not all(RADIUS_OK.match(part) for part in words(value)):
                bad.append(f"{rule.selector}: {value}")
    assert not bad, "border-radius must use --radius-* tokens:\n" + "\n".join(bad)


@pytest.mark.parametrize("mock", mockups())
def test_no_forbidden_animated_properties(mock):
    problems = []
    for rule in mock.rules:
        in_keyframes = any(c.startswith("@keyframes") for c in rule.context)
        for prop, value in rule.declarations:
            if in_keyframes and prop in FORBIDDEN_ANIMATED - {"all"}:
                problems.append(f"{rule.context[-1]} animates {prop}")
            if prop == "transition-property":
                bad = [p for p in split_top(value, ",") if p in FORBIDDEN_ANIMATED]
                problems += [f"{rule.selector} transitions {p}" for p in bad]
            if prop == "transition":
                for layer in split_top(mock.resolve(value), ","):
                    first = words(layer)[0] if words(layer) else ""
                    if first in FORBIDDEN_ANIMATED:
                        problems.append(f"{rule.selector} transitions {first}")
    assert not problems, "Section 4.14.B forbids animating layout properties:\n" + "\n".join(problems)


@pytest.mark.parametrize("mock", mockups())
def test_transition_and_finite_animation_durations_are_150_to_300ms(mock):
    problems = []
    for rule in mock.rules:
        if reduced_motion(rule) or any(c.startswith("@keyframes") for c in rule.context):
            continue
        for prop, value in rule.declarations:
            resolved = mock.resolve(value)
            durations = []
            if prop == "transition":
                durations = [next((to_ms(w) for w in words(layer) if to_ms(w) is not None), None) for layer in split_top(resolved, ",")]
            elif prop == "transition-duration":
                durations = [to_ms(p) for p in split_top(resolved, ",")]
            elif prop == "animation":
                for layer in split_top(resolved, ","):
                    if "infinite" not in words(layer):
                        durations.append(next((to_ms(w) for w in words(layer) if to_ms(w) is not None), None))
            elif prop == "animation-duration" and "infinite" not in mock.resolve(
                    next((v for p, v in rule.declarations if p == "animation-iteration-count"), "")):
                durations = [to_ms(p) for p in split_top(resolved, ",")]
            for ms in durations:
                if ms is None or not TIME_MIN_MS <= ms <= TIME_MAX_MS:
                    problems.append(f"{rule.selector} {prop}: {value} resolves to {ms}ms")
    assert not problems, f"durations must be {TIME_MIN_MS}-{TIME_MAX_MS}ms (Section 4.14.A):\n" + "\n".join(problems)


@pytest.mark.parametrize("mock", mockups())
def test_hover_effects_only_for_hover_devices(mock):
    bad = [r.selector for r in mock.rules if ":hover" in r.selector and not any("hover: hover" in c for c in r.context)]
    assert not bad, f"wrap in @media (hover: hover): {bad}"


@pytest.mark.parametrize("mock", mockups())
def test_motion_respects_reduced_motion_preference(mock):
    assert any("prefers-reduced-motion" in c for r in mock.rules for c in r.context)


@pytest.mark.parametrize("mock", mockups())
def test_tabular_numerals_on_financial_figures(mock):
    num_rules = [r for r in mock.rules if r.selector == ".num"]
    assert any(("font-variant-numeric", "tabular-nums") in r.declarations for r in num_rules), ".num must set tabular-nums"
    missing = []
    for node in mock.soup.find_all(string=True):
        if isinstance(node, Comment) or node.parent.name in ("script", "style", "title") or not FINANCIAL.search(str(node)):
            continue
        if node.find_parent(class_="num") is None:
            missing.append(str(node).strip()[:60])
    assert not missing, "financial figures outside .num (Section 4.16.C):\n" + "\n".join(missing)


@pytest.mark.parametrize("mock", mockups())
def test_wordmark_is_lowercase(mock):
    marks = mock.soup.select(".brand-wordmark")
    assert marks, "no wordmark in the mockup"
    assert {m.get_text(strip=True) for m in marks} == {"roastfolio"}
    for rule in mock.rules:
        if "brand-wordmark" in rule.selector:
            for prop, value in rule.declarations:
                assert not (prop == "text-transform" and value in ("uppercase", "capitalize")), rule.selector


@pytest.mark.parametrize("mock", mockups())
def test_no_new_spinners_and_the_app_loader_is_reused(mock):
    names = [c[len("@keyframes "):] for r in mock.rules for c in r.context if c.startswith("@keyframes")]
    assert not [n for n in names if re.search(r"spin|rotate|spinner|loading", n)], names
    assert not mock.soup.select('[class*="spinner"]')
    assert mock.soup.select(".card-cl-overlay .cl-loader .cl-candle"), "candle loader markup (D-011) missing"


@pytest.mark.parametrize("mock", mockups())
def test_empty_state_has_the_four_parts(mock):
    card = mock.soup.select_one(".empty-state-card")
    assert card is not None, "mockup has no empty state"
    for part in (".empty-state-icon", ".empty-state-title", ".empty-state-desc", "button.empty-state-btn"):
        assert card.select_one(part) is not None, f"empty state lacks {part} (Section 4.7.B)"


@pytest.mark.parametrize("mock", mockups())
def test_touch_action_is_set_on_controls(mock):
    assert any(("touch-action", "manipulation") in r.declarations and "button" in r.selector for r in mock.rules)


@pytest.mark.parametrize("mock", mockups())
def test_markup_integrity(mock):
    ids = [t["id"] for t in mock.soup.find_all(id=True)]
    assert len(ids) == len(set(ids)), f"duplicate ids: {sorted({i for i in ids if ids.count(i) > 1})}"
    for tag in mock.soup.find_all(attrs={"aria-controls": True}):
        assert tag["aria-controls"] in ids, f"aria-controls points to missing id {tag['aria-controls']}"
    assert not [i for i in mock.soup.find_all("img") if not i.has_attr("alt")], "img without alt"
    assert not [b for b in mock.soup.find_all("button") if not b.has_attr("type")], "button without type"
    for tag in mock.soup.find_all(attrs={"role": "tablist"}):
        assert tag.find_all(attrs={"role": "tab"}), "tablist without tabs"
        assert len(tag.find_all(attrs={"role": "tab", "aria-selected": "true"})) == 1, "tablist needs exactly one selected tab"


def decision_params():
    return [pytest.param(d, id=d["id"]) for d in ds.decisions() if d["status"] != "superseded"]


def mockup_for(scope):
    path = ds.MOCKUPS / f"{scope}.html"
    assert path.exists(), f"decision targets the '{scope}' mockup, which does not exist yet"
    return Mockup(path)


@pytest.mark.parametrize("decision", decision_params())
def test_decision_check_passes(decision):
    scope, kind, arg = ds.parse_check(decision["check"])
    mock = mockup_for(scope)
    where = f"{decision['id']} ({decision['status']}): {decision['decision'][:90]}"
    if kind == "dom":
        assert mock.soup.select(arg), f"no element matches '{arg}'. {where}"
    elif kind == "no-dom":
        assert not mock.soup.select(arg), f"unexpected element matches '{arg}'. {where}"
    elif kind == "count":
        selector, expected = arg
        found = len(mock.soup.select(selector))
        assert found == expected, f"'{selector}' matches {found}, expected {expected}. {where}"
    elif kind == "css":
        assert re.search(arg, mock.all_css), f"CSS does not match /{arg}/. {where}"


def test_dashboard_mockup_contains_every_registered_field():
    mock = Mockup(ds.MOCKUPS / "dashboard.html")
    missing = [f for f in ds.dashboard_fields() if not mock.soup.select(f'[data-field="{f}"]')]
    assert not missing, f"information the current dashboard shows is missing from the mockup: {missing}"


def test_dashboard_mockup_has_no_unregistered_fields():
    mock = Mockup(ds.MOCKUPS / "dashboard.html")
    present = {t["data-field"] for t in mock.soup.find_all(attrs={"data-field": True})}
    extra = sorted(present - set(ds.dashboard_fields()))
    assert not extra, f"fields in the mockup but not in Appendix A (register them or remove them): {extra}"
