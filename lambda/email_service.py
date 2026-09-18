"""
lambda/email_service.py — Monthly Recap Email Notification Service

Formats and sends monthly performance summaries via AWS SES.
Supports multi-recipient dispatch, user notification preferences,
and dark-themed fintech HTML templates with plaintext fallbacks.
"""

from __future__ import annotations

import calendar
import logging
import os
import re
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEFAULT_FROM_EMAIL = "notifications@roastfolio.app"


def is_valid_email(email: str | None) -> bool:
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def normalize_email(email: str | None) -> str:
    return str(email or "").strip().lower()


def get_recipient_emails(user_profile: dict | None, include_default: bool = True) -> list[str]:
    """
    Compile a deduplicated list of notification emails for a user.
    Includes the user's primary account email (if include_default)
    plus any additional notification emails from settings.
    """
    if not user_profile or not isinstance(user_profile, dict):
        return []

    recipients: list[str] = []
    seen: set[str] = set()

    primary = normalize_email(user_profile.get("email"))
    if is_valid_email(primary):
        if include_default:
            recipients.append(primary)
        seen.add(primary)

    settings = user_profile.get("settings") or {}
    additional = settings.get("notificationEmails") or []
    if isinstance(additional, list):
        for raw in additional:
            addr = normalize_email(raw)
            if is_valid_email(addr) and addr not in seen:
                recipients.append(addr)
                seen.add(addr)

    return recipients


def _fmt_pct(value: Any, show_sign: bool = True) -> str:
    if value in (None, ""):
        return "No data"
    try:
        num = float(value)
        sign = "+" if (show_sign and num > 0) else ""
        return f"{sign}{num:.2f}%"
    except (ValueError, TypeError):
        return "No data"


def _fmt_money(value: Any, currency: str = "PLN", show_sign: bool = True) -> str:
    if value in (None, ""):
        return f"0 {currency}"
    try:
        num = round(float(value))
        sign = "+" if (show_sign and num > 0) else ""
        return f"{sign}{num:,} {currency}".replace(",", "\u00a0")
    except (ValueError, TypeError):
        return f"0 {currency}"


def _period_display(period: str | None) -> str:
    if not period or not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", str(period)):
        return "Monthly Recap"
    try:
        dt = datetime.strptime(f"{period}-01", "%Y-%m-%d")
        return dt.strftime("%B %Y")
    except ValueError:
        return str(period)


def _color_for_value(value: Any, positive: str = "#4ade80", negative: str = "#f87171", neutral: str = "#94a3b8") -> str:
    try:
        val = float(value)
        if val > 0:
            return positive
        elif val < 0:
            return negative
        return neutral
    except (ValueError, TypeError):
        return neutral


def _fmt_compact_money(val: Any) -> str:
    """Format nominal change compactly for calendar cells (e.g. +9.9k, -15k, +374)."""
    try:
        f = float(val or 0.0)
    except (ValueError, TypeError):
        return "\u2014"
    if abs(f) < 0.01:
        return "0"
    sign = "+" if f > 0 else "-"
    abs_f = abs(f)
    if abs_f >= 1_000_000:
        return f"{sign}{abs_f / 1_000_000:.1f}M"
    if abs_f >= 10_000:
        return f"{sign}{abs_f / 1_000:.0f}k"
    if abs_f >= 1_000:
        return f"{sign}{abs_f / 1_000:.1f}k"
    return f"{sign}{abs_f:.0f}"


# ---------------------------------------------------------------------------
# Narrative sentence generators
# ---------------------------------------------------------------------------

def _generate_journey_narrative(
    portfolio_pct: float | None,
    benchmark_pct: float | None,
    benchmark_id: str,
) -> str:
    """Return a one-sentence editorial about the benchmark comparison."""
    if portfolio_pct is None or benchmark_pct is None:
        return "Your portfolio journey through the month."
    try:
        p = float(portfolio_pct)
        b = float(benchmark_pct)
    except (ValueError, TypeError):
        return "Your portfolio journey through the month."
    diff = p - b
    diff_str = f"{abs(diff):.2f}pp"
    if diff > 0:
        if p >= 0 and b < 0:
            return f"You stayed positive while {benchmark_id} turned negative \u2014 beating it by {diff_str}."
        if p < 0:
            return f"A difficult month, but you weathered it better than {benchmark_id} by {diff_str}."
        return f"You beat {benchmark_id} by {diff_str} \u2014 the green line tells the story."
    elif diff < 0:
        if p > 0 and b < 0:
            return f"Both you and {benchmark_id} stayed positive this month. The market edged you by {diff_str}."
        if p < 0 and b >= 0:
            return f"A tough month. {benchmark_id} held positive territory while you dipped \u2014 trailing by {diff_str}."
        return f"The market ran harder this month \u2014 {benchmark_id} outpaced you by {diff_str}."
    return f"You matched {benchmark_id} exactly this month."


def _generate_calendar_narrative(best_day: dict | None, worst_day: dict | None) -> str:
    """Return a one-sentence editorial about the best/worst trading day."""
    if not best_day and not worst_day:
        return "Every day in the calendar tells part of the story."
    best_date = ""
    best_pct_str = ""
    if best_day:
        raw_date = str(best_day.get("date") or "")
        try:
            best_date = datetime.strptime(raw_date[:10], "%Y-%m-%d").strftime("%b %d")
        except ValueError:
            best_date = raw_date[5:] if len(raw_date) >= 7 else raw_date
        try:
            bp = float(best_day.get("change_pct") or 0.0)
            best_pct_str = f"+{bp:.1f}%"
        except (ValueError, TypeError):
            best_pct_str = ""
    worst_date = ""
    if worst_day:
        raw_date = str(worst_day.get("date") or "")
        try:
            worst_date = datetime.strptime(raw_date[:10], "%Y-%m-%d").strftime("%b %d")
        except ValueError:
            worst_date = raw_date[5:] if len(raw_date) >= 7 else raw_date
    if best_date and worst_date:
        suffix = f" \u2014 a {best_pct_str} gain in one session." if best_pct_str else "."
        return f"Your best day was {best_date}{suffix} Your worst? {worst_date}. But you kept going."
    if best_date:
        suffix = f" \u2014 {best_pct_str} in a single session." if best_pct_str else "."
        return f"Your standout day was {best_date}{suffix}"
    if worst_date:
        return f"A challenging month \u2014 {worst_date} was the hardest day."
    return "Every day in the calendar tells part of the story."


def _generate_mover_narrative(carry: dict | None, anchor: dict | None, hide_cash: bool) -> str:
    """Return a one-sentence editorial about the carry and anchor assets."""
    if not carry and not anchor:
        return "Every holding played a role this month."
    c_ticker = (carry.get("ticker") or carry.get("name") or "One position") if carry else None
    a_ticker = (anchor.get("ticker") or anchor.get("name") or "Another position") if anchor else None
    if c_ticker and a_ticker:
        if not hide_cash:
            c_pln = carry.get("net_contribution_pln")
            a_pln = anchor.get("net_contribution_pln")
            if c_pln is not None and a_pln is not None:
                try:
                    c_str = _fmt_compact_money(float(c_pln))
                    a_str = _fmt_compact_money(float(a_pln))
                    return f"{c_ticker} carried you ({c_str} PLN). {a_ticker} held you back ({a_str} PLN)."
                except (ValueError, TypeError):
                    pass
        return f"{c_ticker} carried you this month. {a_ticker} was the drag."
    if c_ticker:
        return f"{c_ticker} was the engine that drove your returns this month."
    if a_ticker:
        return f"{a_ticker} was the month\u2019s heaviest drag on your portfolio."
    return "Every holding played a role this month."


def _generate_global_narrative(
    portfolio_pct: float | None,
    msci_pct: float | None,
) -> str:
    """Return a one-sentence editorial about performance vs the global market."""
    if portfolio_pct is None or msci_pct is None:
        return "Here\u2019s how the world\u2019s markets fared this month."
    try:
        p = float(portfolio_pct)
        m = float(msci_pct)
    except (ValueError, TypeError):
        return "Here\u2019s how the world\u2019s markets fared this month."
    diff = p - m
    diff_str = f"{abs(diff):.2f}pp"
    if abs(diff) < 0.05:
        return "You matched the global market \u2014 pacing neck and neck with the MSCI World benchmark."
    if diff > 0:
        if p >= 0 and m < 0:
            return f"You outpaced the entire global market \u2014 staying positive while MSCI World slipped ({diff_str} alpha)."
        if p < 0:
            return f"You held up better than the global market \u2014 weathering the drop {diff_str} above MSCI World."
        return f"You outpaced the global market by {diff_str} \u2014 beating MSCI World this month."
    if p < 0 and m >= 0:
        return f"The global market held positive territory while you dipped \u2014 trailing MSCI World by {diff_str}."
    if p >= 0:
        return f"A positive month, but the global market ran faster \u2014 MSCI World beat you by {diff_str}."
    return f"A tough month. The global pullback weighed on you more than MSCI World by {diff_str}."


# ---------------------------------------------------------------------------
# Chapter header helper
# ---------------------------------------------------------------------------

def _chapter_header(eyebrow: str, title: str, narrative: str) -> str:
    """Render the eyebrow + chapter title + narrative sentence block."""
    return (
        '<div style="font-size: 10px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; color: #64748b; margin-bottom: 10px;">'
        + eyebrow
        + '</div>'
        + '<div style="font-size: 26px; font-weight: 800; color: #ffffff; margin-bottom: 8px; letter-spacing: -0.5px; line-height: 1.2;">'
        + title
        + '</div>'
        + '<div style="font-size: 14px; color: #94a3b8; margin-bottom: 22px; line-height: 1.6;">'
        + narrative
        + '</div>'
    )


def _chapter_separator() -> str:
    """Full-bleed thin horizontal rule between chapters."""
    return "\n    <!-- Chapter separator -->\n    <tr><td style=\"padding: 0;\"><div style=\"height: 1px; background-color: #1a2540; margin: 0;\"></div></td></tr>"


# ---------------------------------------------------------------------------
# Journey chart (wrapped style)
# ---------------------------------------------------------------------------

def _render_svg_journey_chart(
    journey: dict,
    benchmark_id: str = "WIG",
    period: str = "",
    benchmark_return_pct: float | None = None,
    portfolio_twr_pct: float | None = None,
) -> tuple[str, str]:
    """Render inline SVG comparing daily portfolio return vs benchmark return."""
    raw_points = journey.get("points") or []
    if len(raw_points) < 2:
        return "", ""

    parsed_points = []
    for pt in raw_points:
        date_str = str(pt.get("date") or "")
        try:
            p_val = float(pt.get("portfolio_pct") or 0.0)
        except (ValueError, TypeError):
            p_val = 0.0
        try:
            b_val = float(pt.get("benchmark_pct") or 0.0)
        except (ValueError, TypeError):
            b_val = 0.0
        parsed_points.append({"date": date_str, "p": p_val, "b": b_val})

    if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", period):
        month_pts = [pt for pt in parsed_points if pt["date"].startswith(period)]
        if len(month_pts) >= 2:
            parsed_points = month_pts
    elif parsed_points:
        first_ym = parsed_points[0]["date"][:7]
        if parsed_points[-1]["date"][:7] != first_ym:
            month_pts = [pt for pt in parsed_points if pt["date"][:7] == first_ym]
            if len(month_pts) >= 2:
                parsed_points = month_pts

    n = len(parsed_points)
    if n < 2:
        return "", ""

    p_vals = [pt["p"] for pt in parsed_points]
    b_vals = [pt["b"] for pt in parsed_points]

    min_val = min(min(p_vals), min(b_vals), 0.0)
    max_val = max(max(p_vals), max(b_vals), 0.0)
    if max_val == min_val:
        max_val += 1.0
        min_val -= 1.0

    pad = (max_val - min_val) * 0.12
    y_min = min_val - pad
    y_max = max_val + pad

    width = 516
    height = 200
    x_left = 42.0
    x_right = 500.0
    y_top = 20.0
    y_bottom = 158.0

    def get_x(i: int) -> float:
        return x_left + i * (x_right - x_left) / max(n - 1, 1)

    def get_y(val: float) -> float:
        ratio = (val - y_min) / (y_max - y_min)
        return y_bottom - ratio * (y_bottom - y_top)

    y_zero = get_y(0.0)

    coords = []
    for i, pt in enumerate(parsed_points):
        x = get_x(i)
        yp = get_y(pt["p"])
        yb = get_y(pt["b"])
        coords.append((x, yp, yb, pt["p"], pt["b"]))

    polygons = []
    for i in range(n - 1):
        x0, yp0, yb0, p0, b0 = coords[i]
        x1, yp1, yb1, p1, b1 = coords[i + 1]
        d0 = p0 - b0
        d1 = p1 - b1
        if (d0 > 0 and d1 < 0) or (d0 < 0 and d1 > 0):
            denom = abs(d0) + abs(d1)
            t = abs(d0) / denom if denom > 0 else 0.5
            xc = x0 + t * (x1 - x0)
            val_c = p0 + t * (p1 - p0)
            yc = get_y(val_c)
            col1 = "#1d4a30" if d0 > 0 else "#4a1d22"
            poly1 = f"{x0:.1f},{yp0:.1f} {xc:.1f},{yc:.1f} {x0:.1f},{yb0:.1f}"
            polygons.append(f'<polygon points="{poly1}" fill="{col1}" />')
            col2 = "#1d4a30" if d1 > 0 else "#4a1d22"
            poly2 = f"{xc:.1f},{yc:.1f} {x1:.1f},{yp1:.1f} {x1:.1f},{yb1:.1f}"
            polygons.append(f'<polygon points="{poly2}" fill="{col2}" />')
        else:
            col = "#1d4a30" if (d0 + d1) >= 0 else "#4a1d22"
            poly = f"{x0:.1f},{yp0:.1f} {x1:.1f},{yp1:.1f} {x1:.1f},{yb1:.1f} {x0:.1f},{yb0:.1f}"
            polygons.append(f'<polygon points="{poly}" fill="{col}" />')

    port_d = "M " + " L ".join(f"{c[0]:.1f},{c[1]:.1f}" for c in coords)
    bench_d = "M " + " L ".join(f"{c[0]:.1f},{c[2]:.1f}" for c in coords)

    last_pt = parsed_points[-1]
    first_pt = parsed_points[0]
    p_last = float(portfolio_twr_pct) if portfolio_twr_pct is not None else last_pt["p"]
    b_last = float(benchmark_return_pct) if benchmark_return_pct is not None else last_pt["b"]
    p_sign = "+" if p_last > 0 else ""
    b_sign = "+" if b_last > 0 else ""
    p_last_str = f"{p_sign}{p_last:.2f}%"
    b_last_str = f"{b_sign}{b_last:.2f}%"
    diff = p_last - b_last
    diff_sign = "+" if diff > 0 else ""
    diff_str = f"{diff_sign}{diff:.2f}%"

    p_col = "#4ade80" if p_last >= 0 else "#f87171"

    if diff > 0:
        badge_bg = "#143828"
        badge_border = "#1f6b45"
        badge_color = "#4ade80"
        badge_text = f"BEAT BY {diff_str}"
    elif diff < 0:
        badge_bg = "#38191e"
        badge_border = "#75242d"
        badge_color = "#f87171"
        badge_text = f"BEHIND BY {abs(diff):.2f}%"
    else:
        badge_bg = "#1e293b"
        badge_border = "#334155"
        badge_color = "#94a3b8"
        badge_text = "MATCHED"

    def _format_short_date(dt_s: str) -> str:
        try:
            return datetime.strptime(dt_s[:10], "%Y-%m-%d").strftime("%b %d")
        except ValueError:
            return dt_s[5:] if len(dt_s) >= 10 else dt_s

    start_date_label = _format_short_date(first_pt["date"])
    end_date_label = _format_short_date(last_pt["date"])

    polys_str = " ".join(polygons)
    svg_markup = (
        '<div style="font-size:0px;color:#07091A;line-height:0;mso-hide:all;">\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="{height}"'
        ' style="display: block; max-width: 516px; margin: 0 auto; overflow: visible;">'
        f'<line x1="{x_left}" y1="{y_zero:.1f}" x2="{x_right}" y2="{y_zero:.1f}" stroke="#1e293b" stroke-dasharray="4,4" stroke-width="1" />'
        f'<text x="{x_left + 4:.1f}" y="{y_zero - 4:.1f}" fill="#475569" font-size="9"'
        ' font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif" font-weight="600">0%</text>'
        + polys_str
        + f'<path d="{bench_d}" fill="none" stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="5,4" stroke-linejoin="round" />'
        f'<path d="{port_d}" fill="none" stroke="{p_col}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />'
        f'<circle cx="{coords[-1][0]:.1f}" cy="{coords[-1][2]:.1f}" r="3" fill="#a78bfa" />'
        f'<circle cx="{coords[-1][0]:.1f}" cy="{coords[-1][1]:.1f}" r="4.5" fill="{p_col}" />'
        f'<line x1="{x_left}" y1="{y_bottom}" x2="{x_right}" y2="{y_bottom}" stroke="#1e293b" stroke-width="1" />'
        f'<text x="{x_left}" y="184" fill="#64748b" font-size="10"'
        ' font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif" font-weight="600" text-anchor="start">'
        + start_date_label
        + f'</text><text x="{x_right}" y="184" fill="#64748b" font-size="10"'
        ' font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif" font-weight="600" text-anchor="end">'
        + end_date_label
        + '</text></svg>\n</div>'
    )

    mso_fallback = (
        "<!--[if mso]>"
        '<table role="presentation" width="100%" border="0" cellpadding="8" cellspacing="0">'
        f'<tr><td style="font-size:12px;color:#94a3b8;">Portfolio: <strong style="color:{p_col};">{p_last_str}</strong></td>'
        f'<td align="right" style="font-size:12px;color:#94a3b8;">Benchmark ({benchmark_id}): <strong style="color:#a78bfa;">{b_last_str}</strong></td></tr>'
        "</table><![endif]-->"
    )

    legend_html = (
        '<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 16px;">'
        '<tr><td>'
        f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:{p_col};vertical-align:middle;margin-right:6px;"></span>'
        f'<span style="font-size:12px;color:#94a3b8;vertical-align:middle;">Portfolio</span>'
        f'<strong style="font-size:13px;color:{p_col};margin-left:4px;vertical-align:middle;">{p_last_str}</strong>'
        '&nbsp;&nbsp;'
        '<span style="display:inline-block;width:16px;height:2px;background-color:#a78bfa;vertical-align:middle;margin-right:6px;margin-bottom:2px;"></span>'
        f'<span style="font-size:12px;color:#94a3b8;vertical-align:middle;">{benchmark_id}</span>'
        f'<strong style="font-size:13px;color:#a78bfa;margin-left:4px;vertical-align:middle;">{b_last_str}</strong>'
        '</td>'
        f'<td align="right"><span style="background-color:{badge_bg};border:1px solid {badge_border};color:{badge_color};padding:4px 12px;border-radius:20px;font-size:11px;font-weight:800;letter-spacing:0.5px;">{badge_text}</span></td>'
        '</tr></table>'
    )

    narrative = _generate_journey_narrative(p_last, b_last, benchmark_id)
    chapter_hdr = _chapter_header("RETURNS, SIDE BY SIDE", "The journey.", narrative)

    html_block = (
        "\n    <!-- Chapter 2: Journey Chart -->\n    <tr>\n      <td style=\"padding: 40px 32px 36px;\">"
        + chapter_hdr
        + legend_html
        + "<!--[if !mso]><!-->"
        + svg_markup
        + "<!--<![endif]-->"
        + mso_fallback
        + "\n      </td>\n    </tr>"
    )

    text_block = f"\u2022 Cumulative Journey: Portfolio {p_last_str} vs {benchmark_id} {b_last_str} ({diff_str})"
    return html_block, text_block


# ---------------------------------------------------------------------------
# Resolve daily moves fallback
# ---------------------------------------------------------------------------

def _resolve_daily_moves(wrap_document: dict) -> list[dict]:
    """Fallback to resolve or compute daily moves from snapshots table or journey points."""
    user_id = wrap_document.get("userId") or wrap_document.get("user_id") or ""
    if not user_id and "PK" in wrap_document:
        pk = str(wrap_document["PK"])
        if pk.startswith("USER#"):
            user_id = pk[5:]
    period = str(wrap_document.get("period") or "")
    if user_id and re.match(r"^\d{4}-(0[1-9]|1[0-2])$", period):
        try:
            year, month = int(period[:4]), int(period[5:7])
            start_date = date(year, month, 1)
            next_m = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            prev_day = (start_date - timedelta(days=1)).isoformat()
            last_day = (next_m - timedelta(days=1)).isoformat()

            import boto3 as _boto3
            from boto3.dynamodb.conditions import Key
            tbl_name = os.environ.get("SNAPSHOTS_TABLE", "roastfolio-snapshots")
            table = _boto3.resource("dynamodb").Table(tbl_name)
            resp = table.query(
                KeyConditionExpression=Key("userId").eq(user_id)
                & Key("sk").between(f"PORTFOLIO#summary#SNAPSHOT#{prev_day}", f"PORTFOLIO#summary#SNAPSHOT#{last_day}")
            )
            items = sorted(resp.get("Items", []), key=lambda x: x.get("sk", ""))
            if len(items) >= 2:
                moves = []
                for i in range(1, len(items)):
                    dt = items[i]["sk"].split("#")[-1]
                    if not dt.startswith(period):
                        continue
                    p_curr = float(items[i].get("portfolioValue") or 0)
                    p_prev = float(items[i - 1].get("portfolioValue") or 0)
                    diff = p_curr - p_prev
                    pct = (diff / p_prev * 100.0) if p_prev > 0 else 0.0
                    moves.append({"date": dt, "change_pln": diff, "change_pct": pct, "is_ath": False})
                if moves:
                    return moves
        except Exception as exc:
            print(f"_resolve_daily_moves snapshot query fallback error: {exc}")

    journey = wrap_document.get("journey") or {}
    points = journey.get("points") or []
    if len(points) >= 2:
        # Derive the period from first point if not directly available
        _period_filter = period if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", period) else (
            str(points[0].get("date") or "")[:7]
        )
        moves = []
        for i in range(1, len(points)):
            dt = str(points[i].get("date") or "")
            # Skip points that fall outside the audit month
            if _period_filter and not dt.startswith(_period_filter):
                continue
            pct_curr = float(points[i].get("portfolio_pct") or 0.0)
            pct_prev = float(points[i - 1].get("portfolio_pct") or 0.0)
            day_pct = pct_curr - pct_prev
            moves.append({"date": dt, "change_pln": 0.0, "change_pct": day_pct, "is_ath": False})
        return moves

    return []


# ---------------------------------------------------------------------------
# Calendar heatmap
# ---------------------------------------------------------------------------

def _render_calendar_heatmap(wrap_document: dict, hide_cash: bool = False) -> tuple[str, str]:
    """Render 7-column calendar heatmap with narrative header, no card box wrapper."""
    period = str(wrap_document.get("period") or "")
    if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", period):
        year, month = int(period[:4]), int(period[5:7])
    else:
        now = datetime.now()
        year, month = now.year, now.month

    daily_moves = wrap_document.get("daily_moves") or []
    if not daily_moves:
        daily_moves = _resolve_daily_moves(wrap_document)

    moves_by_day: dict[int, dict] = {}
    best_day = None
    worst_day = None

    for m in daily_moves:
        d_str = str(m.get("date") or "")
        try:
            day_num = int(d_str[8:10])
            moves_by_day[day_num] = m
            chg = float(m.get("change_pct") or 0.0)
            if best_day is None or chg > float(best_day.get("change_pct") or 0.0):
                best_day = m
            if worst_day is None or chg < float(worst_day.get("change_pct") or 0.0):
                worst_day = m
        except (ValueError, TypeError, IndexError):
            continue

    first_weekday, num_days = calendar.monthrange(year, month)

    weeks = []
    current_week: list = [None] * first_weekday
    for d in range(1, num_days + 1):
        current_week.append(d)
        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []
    if current_week:
        while len(current_week) < 7:
            current_week.append(None)
        weeks.append(current_week)

    headers = ["M", "T", "W", "T", "F", "S", "S"]
    header_cells = "".join(
        f'<th width="14.28%" style="padding: 4px 2px; font-size: 10px; font-weight: 700; color: #475569; text-align: center;">{h}</th>'
        for h in headers
    )

    rows_html = []
    for week in weeks:
        cells_html = []
        for d in week:
            if d is None:
                cells_html.append('<td width="14.28%" style="padding: 2px;"></td>')
            else:
                move = moves_by_day.get(d)
                if move and (move.get("change_pct") is not None or move.get("change_pln") is not None):
                    chg_val = float(move.get("change_pct") or 0.0)
                    chg_pln = float(move.get("change_pln") or 0.0)
                    sign = "+" if chg_val > 0 else ""
                    pct_str = f"{sign}{chg_val:.1f}%"
                    nom_str = _fmt_compact_money(chg_pln)

                    if chg_val > 0.05 or chg_pln > 1.0:
                        bg = "#132d1f"
                        border = "#1f6b45"
                        color = "#4ade80"
                        pct_color = "#86efac"
                        num_color = "#f0fdf4"
                    elif chg_val < -0.05 or chg_pln < -1.0:
                        bg = "#2e1115"
                        border = "#75242d"
                        color = "#f87171"
                        pct_color = "#fca5a5"
                        num_color = "#fff1f2"
                    else:
                        bg = "#141c30"
                        border = "#1e293b"
                        color = "#94a3b8"
                        pct_color = "#64748b"
                        num_color = "#f8fafc"

                    if hide_cash:
                        val_content = f'<div style="font-size:9px;font-weight:700;color:{color};margin-top:2px;line-height:1.1;">{pct_str}</div>'
                    else:
                        val_content = (
                            f'<div style="font-size:9px;font-weight:800;color:{color};margin-top:2px;line-height:1.1;">{nom_str}</div>'
                            f'<div style="font-size:7px;font-weight:500;color:{pct_color};margin-top:1px;line-height:1.1;">{pct_str}</div>'
                        )
                else:
                    bg = "#0f1624"
                    border = "#1a2540"
                    num_color = "#374151"
                    val_content = '<div style="font-size:9px;color:#374151;margin-top:2px;line-height:1.1;">&nbsp;</div>'

                ath_border = "border: 1px solid #f59e0b;" if (move and move.get("is_ath")) else f"border: 1px solid {border};"
                cell = (
                    f'<td width="14.28%" style="padding: 2px; text-align: center; vertical-align: top;">'
                    f'<div style="background-color:{bg};{ath_border}border-radius:5px;padding:4px 1px;min-height:40px;">'
                    f'<div style="font-size:10px;font-weight:700;color:{num_color};line-height:1.1;">{d}</div>'
                    + val_content
                    + "</div></td>"
                )
                cells_html.append(cell)
        rows_html.append(f"<tr>{''.join(cells_html)}</tr>")

    best_str = "\u2014"
    worst_str = "\u2014"

    if best_day and (best_day.get("change_pct") is not None or best_day.get("change_pln") is not None):
        b_dt = str(best_day.get("date") or "")[5:]
        b_val = float(best_day.get("change_pct") or 0.0)
        b_pln = float(best_day.get("change_pln") or 0.0)
        b_sign = "+" if b_val > 0 else ""
        if hide_cash or b_pln == 0:
            best_str = f"{b_dt} ({b_sign}{b_val:.2f}%)"
        else:
            best_str = f"{b_dt} (+{_fmt_money(b_pln, show_sign=False)} / {b_sign}{b_val:.2f}%)"

    if worst_day and (worst_day.get("change_pct") is not None or worst_day.get("change_pln") is not None):
        w_dt = str(worst_day.get("date") or "")[5:]
        w_val = float(worst_day.get("change_pct") or 0.0)
        w_pln = float(worst_day.get("change_pln") or 0.0)
        w_sign = "+" if w_val > 0 else ""
        if hide_cash or w_pln == 0:
            worst_str = f"{w_dt} ({w_sign}{w_val:.2f}%)"
        else:
            worst_str = f"{w_dt} ({_fmt_money(w_pln, show_sign=True)} / {w_sign}{w_val:.2f}%)"

    chips_html = ""
    if best_day or worst_day:
        chips_html = (
            '<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-top:18px;">'
            '<tr>'
            '<td style="padding-right:16px;">'
            '<div style="font-size:10px;font-weight:700;color:#4ade80;letter-spacing:0.5px;margin-bottom:2px;">&#9733; BEST DAY</div>'
            f'<div style="font-size:13px;font-weight:600;color:#f0fdf4;">{best_str}</div>'
            '</td>'
            '<td>'
            '<div style="font-size:10px;font-weight:700;color:#f87171;letter-spacing:0.5px;margin-bottom:2px;">&#9660; WORST DAY</div>'
            f'<div style="font-size:13px;font-weight:600;color:#fff1f2;">{worst_str}</div>'
            '</td>'
            '</tr></table>'
        )

    narrative = _generate_calendar_narrative(best_day, worst_day)
    chapter_hdr = _chapter_header("MOMENTS THAT MATTERED", "The milestones.", narrative)

    html_block = (
        "\n    <!-- Chapter 3: Calendar Heatmap -->\n    <tr>\n      <td style=\"padding: 40px 32px 36px;\">"
        + chapter_hdr
        + '<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="table-layout: fixed;">'
        + f'<thead><tr>{header_cells}</tr></thead>'
        + f'<tbody>{"".join(rows_html)}</tbody>'
        + '</table>'
        + chips_html
        + "\n      </td>\n    </tr>"
    )

    text_block = f"\u2022 Calendar Highlights: Best day {best_str} | Worst day {worst_str}"
    return html_block, text_block


# ---------------------------------------------------------------------------
# Leader / Anchor - typographic left-border rows
# ---------------------------------------------------------------------------

def _render_leader_anchor(carry: dict | None, anchor: dict | None, hide_cash: bool) -> tuple[str, str]:
    """Render Who Moved Your Month as typographic left-border rows."""
    if not carry and not anchor:
        return "", ""

    leader_html = ""
    anchor_html = ""
    leader_text = "None"
    anchor_text = "None"

    if carry:
        ticker = carry.get("ticker") or carry.get("name") or "\u2014"
        name = carry.get("name") or ticker
        val_str = "---" if hide_cash else _fmt_money(carry.get("net_contribution_pln"), show_sign=True)
        note = carry.get("context_note") or ""
        leader_text = f"{ticker} ({val_str}) - {note}"
        note_html = f'<div style="font-size:12px;color:#64748b;font-style:italic;margin-top:4px;">{note}</div>' if note else ""
        leader_html = (
            '<div style="border-left:3px solid #4ade80;padding-left:16px;margin-bottom:24px;">'
            '<div style="font-size:10px;font-weight:800;letter-spacing:1px;color:#4ade80;margin-bottom:6px;">&#9650; MONTH LEADER</div>'
            f'<div style="font-size:22px;font-weight:800;color:#f0fdf4;line-height:1.1;">{ticker}</div>'
            f'<div style="font-size:13px;color:#a7f3d0;margin:3px 0 6px;">{name}</div>'
            f'<div style="font-size:18px;font-weight:700;color:#4ade80;">{val_str}</div>'
            + note_html
            + "</div>"
        )

    if anchor:
        ticker = anchor.get("ticker") or anchor.get("name") or "\u2014"
        name = anchor.get("name") or ticker
        val_str = "---" if hide_cash else _fmt_money(anchor.get("net_contribution_pln"), show_sign=True)
        note = anchor.get("context_note") or ""
        anchor_text = f"{ticker} ({val_str}) - {note}"
        note_html = f'<div style="font-size:12px;color:#64748b;font-style:italic;margin-top:4px;">{note}</div>' if note else ""
        anchor_html = (
            '<div style="border-left:3px solid #f87171;padding-left:16px;margin-bottom:8px;">'
            '<div style="font-size:10px;font-weight:800;letter-spacing:1px;color:#f87171;margin-bottom:6px;">&#9660; MONTH ANCHOR</div>'
            f'<div style="font-size:22px;font-weight:800;color:#fff1f2;line-height:1.1;">{ticker}</div>'
            f'<div style="font-size:13px;color:#fecaca;margin:3px 0 6px;">{name}</div>'
            f'<div style="font-size:18px;font-weight:700;color:#f87171;">{val_str}</div>'
            + note_html
            + "</div>"
        )

    narrative = _generate_mover_narrative(carry, anchor, hide_cash)
    chapter_hdr = _chapter_header("WHO MOVED YOUR MONTH", "The movers.", narrative)

    html_block = (
        "\n    <!-- Chapter 4: Who Moved Your Month -->\n    <tr>\n      <td style=\"padding: 40px 32px 36px;\">"
        + chapter_hdr
        + leader_html
        + anchor_html
        + "\n      </td>\n    </tr>"
    )

    text_block = f"\u2022 Month Leader: {leader_text}\n\u2022 Month Anchor: {anchor_text}"
    return html_block, text_block


# ---------------------------------------------------------------------------
# Market context & seasonality
# ---------------------------------------------------------------------------

def _render_market_context_and_seasonality(
    wrap_document: dict,
    period_title: str,
    portfolio_twr_pct: float | None = None,
) -> tuple[str, str]:
    """Render global benchmarks as typographic list + optional seasonality bar."""
    market_context = wrap_document.get("market_context") or []

    benchmark_labels = {
        "WIG": "WIG \u00b7 Poland",
        "DAX": "DAX \u00b7 Germany",
        "SP500": "S&amp;P 500 \u00b7 US",
        "NASDAQ": "NASDAQ \u00b7 US",
        "FTSE100": "FTSE 100 \u00b7 UK",
        "MSCI_WORLD": "MSCI World \u00b7 Global",
    }

    msci_ret = None
    bench_rows_html = []
    bench_text_lines = []

    for ctx in market_context:
        bid = ctx.get("id") or ""
        label = benchmark_labels.get(bid, ctx.get("name") or bid)
        ret = ctx.get("return_pct")
        ret_str = _fmt_pct(ret, show_sign=True)
        try:
            val = float(ret) if ret is not None else None
        except (ValueError, TypeError):
            val = None

        if bid == "MSCI_WORLD" and val is not None:
            msci_ret = val

        color = "#4ade80" if (val is not None and val > 0) else ("#f87171" if (val is not None and val < 0) else "#94a3b8")

        row = (
            '<tr>'
            f'<td style="padding:11px 0;font-size:13px;color:#94a3b8;border-top:1px solid #1a2540;">{label}</td>'
            f'<td align="right" style="padding:11px 0;font-size:14px;font-weight:700;color:{color};border-top:1px solid #1a2540;">{ret_str}</td>'
            '</tr>'
        )
        bench_rows_html.append(row)
        bench_text_lines.append(f"  - {label}: {ret_str}")

    bench_table_html = ""
    if bench_rows_html:
        bench_table_html = (
            '<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">'
            + "".join(bench_rows_html)
            + "</table>"
        )

    historical_years_count = int(wrap_document.get("historical_years_count") or 0)
    seasonality_html = ""
    seasonality_text = ""

    if historical_years_count > 1:
        month_name = period_title.split()[0] if period_title else "Month"
        neg_count = int(wrap_document.get("negative_years_count") or 0)
        pos_count = int(wrap_document.get("positive_years_count") or 0)
        avg_neg = _fmt_pct(wrap_document.get("avg_negative_pct"), show_sign=True)
        avg_pos = _fmt_pct(wrap_document.get("avg_positive_pct"), show_sign=True)
        outperformed = wrap_document.get("outperformed_seasonal_history")

        total = max(neg_count + pos_count, 1)
        neg_pct = round((neg_count / total) * 100)
        pos_pct = 100 - neg_pct

        if outperformed is True:
            status_color = "#4ade80"
            status_text = "\u2713 You beat seasonal history this month."
        elif outperformed is False:
            status_color = "#f59e0b"
            status_text = "This month trailed your seasonal history."
        else:
            status_color = "#94a3b8"
            status_text = ""

        copy_text = (
            f"{month_name} was negative in {neg_count} of {total} historical observations"
            f" (avg {avg_neg}) and positive in {pos_count} (avg {avg_pos})."
        )

        bar_html = (
            '<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0"'
            ' style="height:8px;border-radius:4px;overflow:hidden;margin:12px 0 10px;">'
            '<tr>'
            f'<td width="{neg_pct}%" style="background-color:#f87171;height:8px;"></td>'
            f'<td width="{pos_pct}%" style="background-color:#4ade80;height:8px;"></td>'
            '</tr></table>'
        )

        status_line = f'<div style="font-size:12px;font-weight:600;color:{status_color};">{status_text}</div>' if status_text else ""

        seasonality_html = (
            '<div style="padding-top:20px;border-top:1px solid #1a2540;">'
            f'<div style="font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#64748b;margin-bottom:8px;">SEASONALITY \u00b7 {month_name.upper()}</div>'
            + bar_html
            + f'<div style="font-size:13px;color:#94a3b8;line-height:1.55;margin-bottom:8px;">{copy_text}</div>'
            + status_line
            + "</div>"
        )

        seasonality_text = f"\n\u2022 Seasonality ({month_name}): {copy_text}"

    narrative = _generate_global_narrative(portfolio_twr_pct, msci_ret)
    chapter_hdr = _chapter_header("A LITTLE PERSPECTIVE", "The bigger picture.", narrative)

    html_block = (
        "\n    <!-- Chapter 5: The Bigger Picture -->\n    <tr>\n      <td style=\"padding: 40px 32px 36px;\">"
        + chapter_hdr
        + bench_table_html
        + seasonality_html
        + "\n      </td>\n    </tr>"
    )

    bench_text_joined = "\n".join(bench_text_lines)
    text_block = f"\u2022 Global Benchmarks:\n{bench_text_joined}{seasonality_text}"
    return html_block, text_block


# ---------------------------------------------------------------------------
# Trading activity
# ---------------------------------------------------------------------------

def _render_trading_activity(trading_activity: dict | None, hide_cash: bool) -> tuple[str, str]:
    """Render turnover, buy/sell totals, and top 5 transactions."""
    if not trading_activity:
        return "", ""

    turnover = trading_activity.get("turnover_pln")
    avg_12m = trading_activity.get("avg_12m_turnover_pln")
    buy_total = trading_activity.get("buy_total_pln")
    sell_total = trading_activity.get("sell_total_pln")
    largest_txs = trading_activity.get("largest_transactions") or []

    turnover_str = "---" if hide_cash else _fmt_money(turnover, show_sign=False)
    buy_str = "---" if hide_cash else _fmt_money(buy_total, show_sign=False)
    sell_str = "---" if hide_cash else _fmt_money(sell_total, show_sign=False)

    comp_html = ""
    comp_text = ""
    if not hide_cash and avg_12m is not None:
        try:
            curr_val = float(turnover or 0.0)
            avg_val = float(avg_12m or 0.0)
            max_v = max(curr_val, avg_val, 1.0)
            curr_pct = max(int((curr_val / max_v) * 100), 4)
            avg_pct = max(int((avg_val / max_v) * 100), 4)
            diff_pct = ((curr_val - avg_val) / avg_val * 100) if avg_val > 0 else 0.0
            sign = "+" if diff_pct > 0 else ""
            diff_chip = f"{sign}{diff_pct:.0f}% vs 12m avg"
            bar_color = "#4ade80" if diff_pct >= 0 else "#94a3b8"

            comp_html = (
                '<div style="margin:12px 0 16px;">'
                '<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="4">'
                '<tr>'
                '<td width="100" style="font-size:11px;color:#94a3b8;">This Month</td>'
                '<td><div style="background-color:#1a2540;border-radius:3px;overflow:hidden;height:10px;">'
                f'<div style="background-color:{bar_color};width:{curr_pct}%;height:10px;border-radius:3px;"></div></div></td>'
                f'<td width="100" align="right" style="font-size:11px;font-weight:700;color:#f8fafc;">{turnover_str}</td>'
                '</tr>'
                '<tr>'
                '<td width="100" style="font-size:11px;color:#64748b;">12m Average</td>'
                '<td><div style="background-color:#1a2540;border-radius:3px;overflow:hidden;height:10px;">'
                f'<div style="background-color:#334155;width:{avg_pct}%;height:10px;border-radius:3px;"></div></div></td>'
                f'<td width="100" align="right" style="font-size:11px;color:#64748b;">{_fmt_money(avg_12m, show_sign=False)}</td>'
                '</tr></table>'
                f'<div style="font-size:10px;color:{"#4ade80" if diff_pct >= 0 else "#94a3b8"};text-align:right;margin-top:4px;">{diff_chip}</div>'
                '</div>'
            )
            comp_text = f" ({diff_chip})"
        except (ValueError, TypeError):
            pass

    buy_sell_html = (
        f'<div style="font-size:12px;color:#94a3b8;margin-bottom:14px;">'
        f'Bought: <strong style="color:#4ade80;">{buy_str}</strong>&nbsp;&bull;&nbsp;'
        f'Sold: <strong style="color:#f87171;">{sell_str}</strong>'
        '</div>'
    )

    tx_rows_html = []
    tx_text_lines = []
    for tx in largest_txs[:5]:
        d = str(tx.get("date") or "")
        k = str(tx.get("type") or "").upper()
        ticker = str(tx.get("ticker") or "\u2014")
        v = tx.get("value_pln")
        v_str = "---" if hide_cash else _fmt_money(v, show_sign=False)
        badge_bg = "#132d1f" if k == "BUY" else "#2e1115"
        badge_color = "#4ade80" if k == "BUY" else "#f87171"
        row = (
            '<tr>'
            f'<td style="padding:8px 0;font-size:12px;color:#64748b;border-top:1px solid #1a2540;width:80px;">{d}</td>'
            f'<td style="padding:8px 6px;border-top:1px solid #1a2540;width:50px;">'
            f'<span style="background-color:{badge_bg};color:{badge_color};padding:2px 8px;border-radius:4px;font-size:10px;font-weight:800;">{k}</span></td>'
            f'<td style="padding:8px 0;font-size:13px;font-weight:600;color:#f8fafc;border-top:1px solid #1a2540;">{ticker}</td>'
            f'<td align="right" style="padding:8px 0;font-size:12px;color:#94a3b8;border-top:1px solid #1a2540;">{v_str}</td>'
            '</tr>'
        )
        tx_rows_html.append(row)
        tx_text_lines.append(f"  - {d} {k} {ticker}: {v_str}")

    if tx_rows_html:
        tx_table_html = (
            '<div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#64748b;margin:16px 0 6px;">TOP TRANSACTIONS</div>'
            '<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">'
            + "".join(tx_rows_html)
            + "</table>"
        )
    else:
        tx_table_html = '<div style="font-size:12px;color:#475569;font-style:italic;margin-top:8px;">No trades executed this month.</div>'

    chapter_hdr = _chapter_header(
        "TRADING ACTIVITY",
        f"Turnover: {turnover_str}.",
        f"You moved {turnover_str} through the market this month.",
    )

    html_block = (
        "\n    <!-- Chapter 6: Trading Activity -->\n    <tr>\n      <td style=\"padding: 40px 32px 36px;\">"
        + chapter_hdr
        + comp_html
        + buy_sell_html
        + tx_table_html
        + "\n      </td>\n    </tr>"
    )

    text_block = (
        f"\u2022 Trading Activity: Turnover {turnover_str}{comp_text} (Buy: {buy_str}, Sell: {sell_str})\n"
        + ("".join([f"\n  - {tl}" for tl in tx_text_lines]) if tx_text_lines else "")
    )
    return html_block, text_block


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_monthly_recap_email(
    user_profile: dict,
    wrap_document: dict,
    hide_cash: bool | None = None,
) -> tuple[str, str, str]:
    """
    Render subject, plaintext body, and HTML body for a monthly recap email.
    If hide_cash is True (or enabled in user_profile settings), monetary PLN
    amounts are masked with '---' for privacy.
    """
    period = wrap_document.get("period", "")
    period_title = _period_display(period)
    nickname = user_profile.get("nickname") or "Investor"

    if hide_cash is None:
        settings = (user_profile.get("settings") or {}) if isinstance(user_profile, dict) else {}
        hide_cash = bool(settings.get("hideCashInNotifications") or settings.get("hideAmountsInNotifications"))

    overall_twr = wrap_document.get("overall_twr_pct")
    twr_str = _fmt_pct(overall_twr, show_sign=True)

    nominal_change = wrap_document.get("overall_nominal_change_pln")
    nominal_str = "---" if hide_cash else _fmt_money(nominal_change, show_sign=True)

    cash_flow = wrap_document.get("cash_flow_pln")
    cash_flow_str = "---" if hide_cash else _fmt_money(cash_flow, show_sign=True)

    deposits = wrap_document.get("deposits_pln")
    deposits_str = "---" if hide_cash else _fmt_money(deposits, show_sign=False)

    withdrawals = wrap_document.get("withdrawals_pln")
    withdrawals_str = "---" if hide_cash else _fmt_money(withdrawals, show_sign=False)

    max_dd = wrap_document.get("max_drawdown_pct")
    max_dd_str = _fmt_pct(max_dd, show_sign=False)

    journey = wrap_document.get("journey") or {}
    benchmark_id = (
        wrap_document.get("benchmark_id")
        or journey.get("benchmark_id")
        or (user_profile.get("settings") or {}).get("benchmark")
        or "WIG"
    )
    benchmark_name = journey.get("benchmark_name") or benchmark_id

    # Benchmark resolution: prioritize canonical market_context close-to-close monthly return
    benchmark_ret = None
    if isinstance(wrap_document.get("market_context"), list):
        for ctx in wrap_document["market_context"]:
            if ctx.get("id") == benchmark_id and ctx.get("return_pct") is not None:
                benchmark_ret = ctx.get("return_pct")
                if not benchmark_name or benchmark_name == benchmark_id:
                    benchmark_name = ctx.get("name") or benchmark_id
                break

    if benchmark_ret is None:
        benchmark_ret = wrap_document.get("benchmark_return_pct")
    if benchmark_ret is None:
        benchmark_ret = journey.get("benchmark_return_pct")
    benchmark_str = _fmt_pct(benchmark_ret, show_sign=True)

    world_ret = None
    if isinstance(wrap_document.get("market_context"), list):
        for ctx in wrap_document["market_context"]:
            if ctx.get("id") == "MSCI_WORLD" and ctx.get("return_pct") is not None:
                world_ret = ctx.get("return_pct")
                break
    world_str = _fmt_pct(world_ret, show_sign=True)

    best_wallet = wrap_document.get("best_efficiency_wallet") or {}
    best_wallet_name = best_wallet.get("name") or "\u2014"
    best_wallet_twr = _fmt_pct(best_wallet.get("twr_pct"), show_sign=True)
    best_wallet_twr_val = best_wallet.get("twr_pct")

    profit_wallet = wrap_document.get("primary_profit_engine_wallet") or {}
    profit_wallet_name = profit_wallet.get("name") or "\u2014"
    profit_wallet_nominal = "---" if hide_cash else _fmt_money(profit_wallet.get("nominal_change_pln"), show_sign=True)

    app_url = os.environ.get("APP_URL", "https://roastfolio.app")

    try:
        twr_val = float(overall_twr or 0)
    except (ValueError, TypeError):
        twr_val = 0.0

    if twr_val > 0:
        accent_color = "#4ade80"
        hero_headline = "A strong month."
        hero_subline = f"Your portfolio returned {twr_str} in {period_title}."
    elif twr_val < 0:
        accent_color = "#f87171"
        hero_headline = "The market tested you."
        hero_subline = f"Your portfolio returned {twr_str} in {period_title}."
    else:
        accent_color = "#94a3b8"
        hero_headline = "Holding your ground."
        hero_subline = f"Your portfolio returned {twr_str} in {period_title}."

    try:
        bench_diff = twr_val - float(benchmark_ret or 0)
        bench_diff_label = f"{'+' if bench_diff > 0 else ''}{bench_diff:.2f}pp vs {benchmark_id}"
        bench_diff_color = "#4ade80" if bench_diff > 0 else "#f87171"
    except (ValueError, TypeError):
        bench_diff_label = benchmark_str
        bench_diff_color = "#94a3b8"

    subject = f"Roastfolio Monthly Recap \u2014 {period_title} ({twr_str})"

    period_key = str(wrap_document.get("period") or "")
    journey_html, journey_text = _render_svg_journey_chart(
        journey,
        benchmark_id=benchmark_id,
        period=period_key,
        benchmark_return_pct=benchmark_ret,
        portfolio_twr_pct=twr_val if overall_twr is not None else None,
    )
    calendar_html, calendar_text = _render_calendar_heatmap(wrap_document, hide_cash=hide_cash)
    leader_anchor_html, leader_anchor_text = _render_leader_anchor(
        wrap_document.get("carry"), wrap_document.get("anchor"), hide_cash
    )
    market_context_html, market_context_text = _render_market_context_and_seasonality(
        wrap_document, period_title, portfolio_twr_pct=twr_val if overall_twr is not None else None
    )
    trading_html, trading_text = _render_trading_activity(wrap_document.get("trading_activity"), hide_cash)

    # Plain text
    if hide_cash:
        cash_flow_line = "\u2022 Net Cash Flow:               --- (amounts hidden)"
        nominal_line = "\u2022 Nominal Change:              --- (amounts hidden)"
        profit_wallet_line = f"\u2022 Primary Profit Engine:       {profit_wallet_name} (---)"
    else:
        cash_flow_line = f"\u2022 Net Cash Flow:               {cash_flow_str} (Deposits: {deposits_str}, Withdrawals: {withdrawals_str})"
        nominal_line = f"\u2022 Nominal Change:              {nominal_str}"
        profit_wallet_line = f"\u2022 Primary Profit Engine:       {profit_wallet_name} ({profit_wallet_nominal})"

    text_lines = [
        f"ROASTFOLIO MONTHLY RECAP: {period_title.upper()}",
        "=" * 44,
        f"Hello {nickname},",
        "",
        hero_headline,
        "",
        f"\u2022 Time-Weighted Return (TWR): {twr_str}",
        nominal_line,
        cash_flow_line,
        f"\u2022 Benchmark ({benchmark_id}):           {benchmark_str}",
        f"\u2022 World (MSCI World):          {world_str}",
        f"\u2022 Maximum Drawdown:            {max_dd_str}",
        "",
        "PORTFOLIO HIGHLIGHTS:",
        f"\u2022 Best Return Wallet:          {best_wallet_name} ({best_wallet_twr})",
        profit_wallet_line,
        "",
    ]
    if journey_text:
        text_lines.extend([journey_text, ""])
    if calendar_text:
        text_lines.extend([calendar_text, ""])
    if leader_anchor_text:
        text_lines.extend([leader_anchor_text, ""])
    if market_context_text:
        text_lines.extend([market_context_text, ""])
    if trading_text:
        text_lines.extend([trading_text, ""])
    text_lines.extend([
        f"View your interactive audit & shareable card: {app_url}",
        "",
        "-" * 44,
        "You received this email because email notifications are enabled in Roastfolio.",
        "You can manage your email notification settings and recipients anytime in User Settings.",
    ])
    text_body = "\n".join(text_lines)

    # Hero stat pills
    hero_pills = (
        '<table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin: 0 auto; margin-top: 24px;">'
        '<tr>'
        '<td style="padding: 0 5px;">'
        '<div style="background-color:#0d1525;border:1px solid #1a2540;border-radius:20px;padding:8px 16px;text-align:center;">'
        '<div style="font-size:9px;color:#64748b;font-weight:700;letter-spacing:0.5px;margin-bottom:2px;">GAIN / LOSS</div>'
        f'<div style="font-size:14px;font-weight:700;color:#f0fdf4;">{nominal_str}</div>'
        '</div></td>'
        '<td style="padding: 0 5px;">'
        '<div style="background-color:#0d1525;border:1px solid #1a2540;border-radius:20px;padding:8px 16px;text-align:center;">'
        '<div style="font-size:9px;color:#64748b;font-weight:700;letter-spacing:0.5px;margin-bottom:2px;">MAX DRAWDOWN</div>'
        f'<div style="font-size:14px;font-weight:700;color:#94a3b8;">{max_dd_str}</div>'
        '</div></td>'
        '<td style="padding: 0 5px;">'
        '<div style="background-color:#0d1525;border:1px solid #1a2540;border-radius:20px;padding:8px 16px;text-align:center;">'
        f'<div style="font-size:9px;color:#64748b;font-weight:700;letter-spacing:0.5px;margin-bottom:2px;">{benchmark_id.upper()}</div>'
        f'<div style="font-size:14px;font-weight:700;color:{bench_diff_color};">{bench_diff_label}</div>'
        '</div></td>'
        '</tr></table>'
    )

    # Wallet mini-strip
    bw_twr_color = _color_for_value(best_wallet_twr_val)
    wallet_html = ""
    if best_wallet_name != "\u2014" or profit_wallet_name != "\u2014":
        wallet_html = (
            "\n    <!-- Wallet mini-strip -->\n    <tr>\n      <td style=\"padding: 0 32px 36px;\">"
            '<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">'
            '<tr><td style="font-size:12px;color:#64748b;padding-bottom:6px;border-top:1px solid #1a2540;padding-top:14px;">'
            f'Best Return Wallet &mdash; <strong style="color:#94a3b8;">{best_wallet_name}</strong>'
            f'<span style="color:{bw_twr_color};">&nbsp;{best_wallet_twr}</span>'
            '</td></tr>'
            '<tr><td style="font-size:12px;color:#64748b;padding-bottom:4px;">'
            f'Primary Profit Engine &mdash; <strong style="color:#94a3b8;">{profit_wallet_name}</strong>'
            f'<span style="color:#94a3b8;">&nbsp;{profit_wallet_nominal}</span>'
            '</td></tr></table>'
            "\n      </td>\n    </tr>"
        )

    sep = _chapter_separator()

    html_body = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'  <title>{subject}</title>\n'
        '  <style>\n'
        '    @media only screen and (max-width: 600px) {\n'
        '      .email-container { width: 100% !important; border-radius: 0 !important; }\n'
        '      .hero-number { font-size: 52px !important; }\n'
        '    }\n'
        '  </style>\n'
        '</head>\n'
        '<body style="margin:0;padding:20px 12px;background-color:#050813;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Helvetica,Arial,sans-serif;color:#f1f5f9;-webkit-font-smoothing:antialiased;">\n'
        '  <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" class="email-container"'
        ' style="max-width:600px;margin:0 auto;background-color:#07091A;border-radius:16px;border:1px solid #1a2540;overflow:hidden;box-shadow:0 20px 40px rgba(0,0,0,0.6);">\n\n'
        # HEADER
        '    <!-- HEADER -->\n'
        '    <tr>\n      <td style="padding:20px 32px 18px;border-bottom:1px solid #1a2540;">\n'
        '        <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0"><tr>\n'
        '          <td><span style="font-size:18px;font-weight:800;letter-spacing:-0.5px;color:#ffffff;">roastfolio</span></td>\n'
        f'          <td align="right"><span style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#64748b;">{period_title.upper()}</span></td>\n'
        '        </tr></table>\n      </td>\n    </tr>\n\n'
        # HERO
        '    <!-- CHAPTER 1: HERO -->\n'
        '    <tr>\n'
        '      <td style="padding:52px 32px 44px;text-align:center;background:radial-gradient(ellipse at 50% 0%,#0d1d35 0%,#07091A 70%);">\n'
        f'        <div style="font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#64748b;margin-bottom:14px;">YOUR MONTHLY RECAP &bull; {period_title.upper()}</div>\n'
        f'        <div style="font-size:15px;color:#94a3b8;margin-bottom:10px;">Hello, {nickname}.</div>\n'
        f'        <div class="hero-number" style="font-size:72px;font-weight:800;letter-spacing:-3px;color:{accent_color};line-height:1;margin-bottom:12px;">{twr_str}</div>\n'
        f'        <div style="font-size:18px;font-weight:600;color:#f8fafc;margin-bottom:6px;">{hero_headline}</div>\n'
        f'        <div style="font-size:14px;color:#64748b;margin-bottom:24px;">{hero_subline}</div>\n'
        f'        {hero_pills}\n'
        '      </td>\n    </tr>\n\n'
        + wallet_html
        + sep + journey_html
        + sep + calendar_html
        + (sep + leader_anchor_html if leader_anchor_html else "")
        + sep + market_context_html
        + (sep + trading_html if trading_html else "")
        # CTA
        + '\n    <!-- CTA -->\n'
        '    <tr><td style="padding:0;"><div style="height:1px;background-color:#1a2540;"></div></td></tr>\n'
        '    <tr>\n      <td align="center" style="padding:40px 32px 44px;">\n'
        '        <div style="font-size:13px;color:#64748b;margin-bottom:20px;">Ready to go deeper?</div>\n'
        f'        <a href="{app_url}" target="_blank"'
        ' style="display:inline-block;background-color:#3b82f6;color:#ffffff;text-decoration:none;font-size:14px;font-weight:700;padding:14px 36px;border-radius:100px;letter-spacing:0.3px;">'
        'Open Full Audit &rarr;</a>\n'
        '      </td>\n    </tr>\n\n'
        # FOOTER
        '    <!-- FOOTER -->\n'
        '    <tr>\n      <td style="padding:20px 32px;background-color:#050813;border-top:1px solid #1a2540;text-align:center;">\n'
        '        <p style="margin:0 0 4px;font-size:11px;color:#475569;">You received this because email notifications are enabled for your Roastfolio account.</p>\n'
        '        <p style="margin:0;font-size:10px;color:#334155;">Powered by TOMINEX &bull; Roastfolio Investment History &bull; Not investment advice.</p>\n'
        '      </td>\n    </tr>\n\n'
        '  </table>\n</body>\n</html>'
    )

    return subject, text_body, html_body


# ---------------------------------------------------------------------------
# Send helpers
# ---------------------------------------------------------------------------

def send_monthly_recap_email(
    user_profile: dict,
    wrap_document: dict,
    recipients: list[str] | None = None,
    ses_client: Any = None,
    hide_cash: bool | None = None,
) -> dict:
    """
    Deliver the monthly recap email to the specified recipients,
    or resolve recipient emails from user_profile.
    """
    if recipients is None:
        recipients = get_recipient_emails(user_profile)

    if not recipients:
        logger.warning("No recipient emails available for user %s", user_profile.get("userId"))
        return {"success": False, "error": "No recipient emails found"}

    from_email = os.environ.get("NOTIFICATION_FROM_EMAIL", DEFAULT_FROM_EMAIL)
    if "<" not in from_email:
        from_email = f"Roastfolio <{from_email}>"
    subject, text_body, html_body = render_monthly_recap_email(
        user_profile, wrap_document, hide_cash=hide_cash
    )

    client = ses_client or boto3.client("ses", region_name=os.environ.get("AWS_REGION", "eu-central-1"))

    try:
        response = client.send_email(
            Source=from_email,
            Destination={"ToAddresses": recipients},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
            },
        )
        message_id = response.get("MessageId")
        logger.info(
            "Recap email sent for user %s to %s recipients (MessageId: %s)",
            user_profile.get("userId"),
            len(recipients),
            message_id,
        )
        return {"success": True, "message_id": message_id, "recipients": recipients}
    except ClientError as err:
        logger.error("SES ClientError sending recap email: %s", err)
        raw_msg = str(err)
        error_code = err.response.get("Error", {}).get("Code", "")
        error_text = err.response.get("Error", {}).get("Message", raw_msg)
        is_unverified = (
            error_code == "MessageRejected"
            or "Email address is not verified" in raw_msg
            or "Email address is not verified" in error_text
        )
        if is_unverified:
            user_msg = (
                f"Email delivery failed: Email address is not verified in AWS SES (Sandbox mode). "
                f"Both sender ({from_email}) and recipient addresses must be verified identities."
            )
            return {
                "success": False,
                "error": user_msg,
                "raw_error": raw_msg,
                "unverified": True,
                "recipients": recipients,
            }
        return {"success": False, "error": raw_msg, "recipients": recipients}
    except Exception as exc:
        logger.error("Unexpected error sending recap email: %s", exc)
        return {"success": False, "error": str(exc), "recipients": recipients}


def send_monthly_recap_email_if_enabled(
    user_profile: dict,
    wrap_document: dict,
    ses_client: Any = None,
    hide_cash: bool | None = None,
) -> dict:
    """
    Check if the user has email notifications turned on in settings.
    If enabled, send the monthly recap; otherwise return early.
    """
    settings = (user_profile.get("settings") or {}) if isinstance(user_profile, dict) else {}
    enabled = bool(settings.get("emailNotifications") or settings.get("notifications"))

    if not enabled:
        logger.info(
            "Skipping automated recap email for user %s (notifications disabled)",
            user_profile.get("userId") if isinstance(user_profile, dict) else "unknown",
        )
        return {"success": False, "skipped": True, "reason": "Notifications disabled"}

    return send_monthly_recap_email(
        user_profile, wrap_document, ses_client=ses_client, hide_cash=hide_cash
    )
