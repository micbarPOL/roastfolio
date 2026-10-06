"""Parser and helpers for docs/DESIGN_SYSTEM_2026_V9.md.

Used by the design consistency tests and by `--write-tokens`, which regenerates
design/tokens-v9.css from Section 2 of the document.
"""
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "DESIGN_SYSTEM_2026_V9.md"
TOKENS_CSS = ROOT / "design" / "tokens-v9.css"
MOCKUPS = ROOT / "design" / "mockups"

DARK_SELECTOR = ":root"
LIGHT_SELECTOR = ':root[data-theme="light"]'


# --------------------------------------------------------------------------- doc


def doc_lines():
    """Yield (line_number, text, in_fence) for every line of the design document."""
    in_fence = False
    for number, line in enumerate(DOC.read_text(encoding="utf-8").splitlines(), start=1):
        if line.lstrip().startswith("```"):
            yield number, line, True
            in_fence = not in_fence
            continue
        yield number, line, in_fence


def headings():
    """Return [(level, title, line_number)] for headings outside code fences."""
    found = []
    for number, line, in_fence in doc_lines():
        match = None if in_fence else re.match(r"^(#{1,4})\s+(.*\S)\s*$", line)
        if match:
            found.append((len(match.group(1)), match.group(2), number))
    return found


def section_number(title):
    """'4.12 Dropdown ...' -> '4.12'; 'Appendix A. ...' -> 'A'; otherwise None."""
    match = re.match(r"^(\d+(?:\.\d+)*)\.?\s", title)
    if match:
        return match.group(1)
    match = re.match(r"^Appendix ([A-Z])\.", title)
    return match.group(1) if match else None


def prose_text():
    """Document text without fenced code blocks."""
    return "\n".join(line for _, line, in_fence in doc_lines() if not in_fence)


def css_fences(start_title_re, end_title_re):
    """Fenced ```css blocks between two headings (regexes matched against titles)."""
    marks = headings()
    start = next(n for _, t, n in marks if re.match(start_title_re, t))
    end = next(n for _, t, n in marks if n > start and re.match(end_title_re, t))
    blocks, current = [], None
    for number, line, in_fence in doc_lines():
        if number <= start or number >= end:
            continue
        if line.lstrip().startswith("```"):
            if current is None and line.strip() == "```css":
                current = []
            elif current is not None:
                blocks.append("\n".join(current))
                current = None
        elif current is not None:
            current.append(line)
    return blocks


def all_css_fences():
    """Every ```css block in the document."""
    blocks, current = [], None
    for _, line, _ in doc_lines():
        if line.lstrip().startswith("```"):
            if current is None and line.strip() == "```css":
                current = []
            elif current is not None:
                blocks.append("\n".join(current))
                current = None
        elif current is not None:
            current.append(line)
    return blocks


def table_rows(start_title_re, end_title_re=None):
    """Raw cell rows of every markdown table after a heading, up to the next matching heading."""
    marks = headings()
    start = next(n for _, t, n in marks if re.match(start_title_re, t))
    end = (
        next((n for _, t, n in marks if n > start and re.match(end_title_re, t)), 10**9)
        if end_title_re
        else next((n for _, _, n in marks if n > start), 10**9)
    )
    rows = []
    for number, line, in_fence in doc_lines():
        if number <= start or number >= end or in_fence or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else rows  # drop header row


def unwrap(cell):
    return cell.strip().strip("`").strip()


# --------------------------------------------------------------------------- css


@dataclass
class Rule:
    selector: str
    declarations: list
    context: tuple


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _split_declarations(text):
    parts, depth, current = [], 0, ""
    for ch in text:
        depth += (ch == "(") - (ch == ")")
        if ch == ";" and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    declarations = []
    for part in parts:
        if ":" not in part:
            continue
        prop, value = part.split(":", 1)
        value = re.sub(r"\s*!important\s*$", "", value.strip())
        declarations.append((prop.strip().lower(), value))
    return declarations


def parse_css(css):
    """Parse CSS (including nested @media/@keyframes) into flat Rule objects."""
    rules, stack, buf, depth = [], [], "", 0
    for ch in strip_comments(css):
        depth += (ch == "(") - (ch == ")")
        if ch == "{" and depth == 0:
            stack.append([buf.strip(), ""])
            buf = ""
        elif ch == "}" and depth == 0 and stack:
            prelude, body = stack.pop()
            body += buf
            buf = ""
            if body.strip():
                context = tuple(p for p, _ in stack)
                rules.append(Rule(re.sub(r"\s+", " ", prelude), _split_declarations(body), context))
        elif ch == ";" and depth == 0 and stack:
            stack[-1][1] += buf + ";"
            buf = ""
        else:
            buf += ch
    return rules


def registry(css_blocks=None):
    """Token registry parsed from Section 2: {'dark': {...}, 'light': {...}} (light = dark + overrides)."""
    blocks = css_blocks if css_blocks is not None else css_fences(r"2\.\s", r"3\.\s")
    dark, light_overrides = {}, {}
    for rule in parse_css("\n".join(blocks)):
        target = dark if rule.selector == DARK_SELECTOR else light_overrides if rule.selector == LIGHT_SELECTOR else None
        if target is None:
            continue
        for prop, value in rule.declarations:
            if prop.startswith("--"):
                target[prop] = value
    return {"dark": dark, "light": {**dark, **light_overrides}, "light_overrides": light_overrides}


def tokens_file_registry():
    return registry([TOKENS_CSS.read_text(encoding="utf-8")])


# ---------------------------------------------------------------------- colours


def parse_color(value):
    """'#rrggbb', '#rgb' or 'rgb(a)(r, g, b[, a])' -> (r, g, b, a); None if not a plain colour."""
    value = value.strip().lower()
    match = re.fullmatch(r"#([0-9a-f]{6})", value)
    if match:
        h = match.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
    match = re.fullmatch(r"#([0-9a-f]{3})", value)
    if match:
        h = match.group(1)
        return int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 1.0
    match = re.fullmatch(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,/\s]+([\d.]+%?))?\s*\)", value)
    if match:
        alpha = match.group(4)
        a = 1.0 if alpha is None else float(alpha[:-1]) / 100 if alpha.endswith("%") else float(alpha)
        return float(match.group(1)), float(match.group(2)), float(match.group(3)), a
    return None


def composite(fg, bg):
    """Alpha-composite an (r, g, b, a) foreground over an opaque (r, g, b, ...) background."""
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))


def _channel(c):
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = (_channel(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_rgb, bg_rgb):
    light, dark = sorted((luminance(fg_rgb), luminance(bg_rgb)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


# --------------------------------------------------------------------- decisions


def decisions():
    """Decision Log rows as dicts with id, status, decision and check."""
    return [
        {"id": unwrap(r[0]), "status": unwrap(r[1]), "decision": r[2], "check": unwrap(r[3])}
        for r in table_rows(r"9\.\s", r"10\.\s")
        if len(r) == 4
    ]


def parse_check(check):
    """'@wallets dom: .x' -> ('wallets', 'dom', '.x'); 'count: .x = 1' -> ('dashboard', 'count', ('.x', 1))."""
    scope = "dashboard"
    match = re.match(r"^@([\w-]+)\s+(.*)$", check)
    if match:
        scope, check = match.group(1), match.group(2)
    if check == "none":
        return scope, "none", None
    kind, _, arg = check.partition(":")
    kind, arg = kind.strip(), arg.strip()
    if kind == "count":
        selector, _, number = arg.rpartition("=")
        return scope, kind, (selector.strip(), int(number))
    if kind in ("dom", "no-dom", "css"):
        return scope, kind, arg
    raise ValueError(f"Unknown check kind in {check!r}")


def contrast_contract():
    """[(theme, [fg tokens], [bg tokens], ratio)] from the Contrast Contract table."""
    rows = table_rows(r"Contrast Contract", r"Known Contrast Limits")
    return [(r[0], _tokens(r[1]), _tokens(r[2]), float(r[3])) for r in rows]


def known_contrast_limits():
    """[(theme, fg token, bg token, documented ratio)] from the Known Contrast Limits table."""
    rows = table_rows(r"Known Contrast Limits", r"11\.\s")
    return [(r[0], r[1], r[2], float(r[3])) for r in rows]


def _tokens(cell):
    return [t.strip() for t in cell.split(",") if t.strip()]


def open_question_ids():
    return [unwrap(r[0]) for r in table_rows(r"11\.\s", r"Appendix A")]


def dashboard_fields():
    """Field ids registered in Appendix A (every table row whose first cell is a backticked id)."""
    marks = headings()
    start = next(n for _, t, n in marks if t.startswith("Appendix A"))
    fields = []
    for number, line, in_fence in doc_lines():
        if number <= start or in_fence or not line.startswith("|"):
            continue
        first = line.strip().strip("|").split("|")[0].strip()
        match = re.fullmatch(r"`([A-Za-z0-9_-]+)`", first)
        if match:
            fields.append(match.group(1))
    return fields


# --------------------------------------------------------------------------- cli


def write_tokens():
    blocks = css_fences(r"2\.\s", r"3\.\s")
    header = (
        "/* GENERATED from docs/DESIGN_SYSTEM_2026_V9.md Section 2. Do not edit by hand.\n"
        "   Regenerate: .venv/bin/python design/design_system.py --write-tokens */\n\n"
    )
    TOKENS_CSS.write_text(header + "\n\n".join(b.strip() for b in blocks) + "\n", encoding="utf-8")
    print(f"wrote {TOKENS_CSS.relative_to(ROOT)}")


if __name__ == "__main__":
    if "--write-tokens" in sys.argv:
        write_tokens()
    else:
        print("usage: design_system.py --write-tokens")
        sys.exit(2)
