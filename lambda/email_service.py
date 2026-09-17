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
from datetime import datetime
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
        return f"{sign}{num:,} {currency}".replace(",", " ")
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


def _render_svg_journey_chart(journey: dict, benchmark_id: str = "WIG") -> tuple[str, str]:
    """Render inline SVG comparing daily portfolio return vs benchmark return with gradient/fill."""
    points = journey.get("points") or []
    if len(points) < 2:
        return "", ""

    parsed_points = []
    for pt in points:
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

    n = len(parsed_points)
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
    y_top = 26.0
    y_bottom = 162.0

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

    # Shaded fill polygons between portfolio and benchmark
    polygons = []
    for i in range(n - 1):
        x0, yp0, yb0, p0, b0 = coords[i]
        x1, yp1, yb1, p1, b1 = coords[i + 1]

        d0 = p0 - b0
        d1 = p1 - b1

        # Segment crossing check
        if (d0 > 0 and d1 < 0) or (d0 < 0 and d1 > 0):
            denom = abs(d0) + abs(d1)
            t = abs(d0) / denom if denom > 0 else 0.5
            xc = x0 + t * (x1 - x0)
            val_c = p0 + t * (p1 - p0)
            yc = get_y(val_c)

            col1 = "rgba(74, 222, 128, 0.20)" if d0 > 0 else "rgba(248, 113, 113, 0.16)"
            poly1 = f"{x0:.1f},{yp0:.1f} {xc:.1f},{yc:.1f} {x0:.1f},{yb0:.1f}"
            polygons.append(f'<polygon points="{poly1}" fill="{col1}" />')

            col2 = "rgba(74, 222, 128, 0.20)" if d1 > 0 else "rgba(248, 113, 113, 0.16)"
            poly2 = f"{xc:.1f},{yc:.1f} {x1:.1f},{yp1:.1f} {x1:.1f},{yb1:.1f}"
            polygons.append(f'<polygon points="{poly2}" fill="{col2}" />')
        else:
            col = "rgba(74, 222, 128, 0.20)" if (d0 + d1) >= 0 else "rgba(248, 113, 113, 0.16)"
            poly = f"{x0:.1f},{yp0:.1f} {x1:.1f},{yp1:.1f} {x1:.1f},{yb1:.1f} {x0:.1f},{yb0:.1f}"
            polygons.append(f'<polygon points="{poly}" fill="{col}" />')

    port_d = "M " + " L ".join(f"{c[0]:.1f},{c[1]:.1f}" for c in coords)
    bench_d = "M " + " L ".join(f"{c[0]:.1f},{c[2]:.1f}" for c in coords)

    last_pt = parsed_points[-1]
    first_pt = parsed_points[0]
    p_last = last_pt["p"]
    b_last = last_pt["b"]
    p_sign = "+" if p_last > 0 else ""
    b_sign = "+" if b_last > 0 else ""
    p_last_str = f"{p_sign}{p_last:.2f}%"
    b_last_str = f"{b_sign}{b_last:.2f}%"
    diff = p_last - b_last
    diff_sign = "+" if diff > 0 else ""
    diff_str = f"{diff_sign}{diff:.2f}%"

    if diff > 0:
        win_badge = f'<span style="background-color: rgba(74, 222, 128, 0.15); border: 1px solid rgba(74, 222, 128, 0.35); color: #4ade80; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;">★ BEAT BENCHMARK BY {diff_str}</span>'
        text_status = f"Beat benchmark by {diff_str}"
    elif diff < 0:
        win_badge = f'<span style="background-color: rgba(248, 113, 113, 0.12); border: 1px solid rgba(248, 113, 113, 0.30); color: #f87171; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;">LAGGED BENCHMARK BY {diff_str}</span>'
        text_status = f"Lagged benchmark by {diff_str}"
    else:
        win_badge = f'<span style="background-color: #1e293b; color: #94a3b8; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;">MATCHED BENCHMARK</span>'
        text_status = "Matched benchmark"

    # Date formatting for labels
    def _format_short_date(dt_s: str) -> str:
        try:
            return datetime.strptime(dt_s[:10], "%Y-%m-%d").strftime("%b %d")
        except ValueError:
            return dt_s[5:] if len(dt_s) >= 10 else dt_s

    start_date_label = _format_short_date(first_pt["date"])
    end_date_label = _format_short_date(last_pt["date"])

    svg_markup = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="{height}" style="display: block; max-width: {width}px; margin: 0 auto; overflow: visible;">
      <!-- Zero baseline -->
      <line x1="{x_left}" y1="{y_zero:.1f}" x2="{x_right}" y2="{y_zero:.1f}" stroke="rgba(148, 163, 184, 0.25)" stroke-dasharray="4,5" stroke-width="1" />
      <text x="{x_left - 6:.1f}" y="{y_zero + 3:.1f}" fill="#64748b" font-size="9" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" text-anchor="end">0%</text>

      <!-- Fill polygons (green outperformance, red underperformance) -->
      {' '.join(polygons)}

      <!-- Benchmark line (dashed purple) -->
      <path d="{bench_d}" fill="none" stroke="#a78bfa" stroke-width="2" stroke-dasharray="5,4" stroke-linejoin="round" />

      <!-- Portfolio line (solid green) -->
      <path d="{port_d}" fill="none" stroke="#4ade80" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />

      <!-- End circles -->
      <circle cx="{coords[-1][0]:.1f}" cy="{coords[-1][2]:.1f}" r="3.5" fill="#a78bfa" />
      <circle cx="{coords[-1][0]:.1f}" cy="{coords[-1][1]:.1f}" r="4.5" fill="#4ade80" />

      <!-- X-axis date labels -->
      <text x="{x_left}" y="188" fill="#64748b" font-size="10" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" text-anchor="start">{start_date_label}</text>
      <text x="{x_right}" y="188" fill="#64748b" font-size="10" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" text-anchor="end">{end_date_label}</text>
    </svg>"""

    mso_fallback = f"""<!--[if mso]>
    <table role="presentation" width="100%" border="0" cellpadding="8" cellspacing="0" style="background-color: #1a233a; border-radius: 8px; border: 1px solid #24304d;">
      <tr>
        <td style="font-size: 12px; color: #94a3b8;">Portfolio: <strong style="color: #4ade80;">{p_last_str}</strong></td>
        <td align="right" style="font-size: 12px; color: #94a3b8;">Benchmark ({benchmark_id}): <strong style="color: #a78bfa;">{b_last_str}</strong></td>
      </tr>
    </table>
    <![endif]-->"""

    html_block = f"""
    <!-- Section 3: Journey Chart -->
    <tr>
      <td style="padding: 0 24px 24px;">
        <div style="background-color: #131d33; border: 1px solid #24304d; border-radius: 12px; padding: 20px 18px 16px;">
          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 12px;">
            <tr>
              <td>
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8;">CUMULATIVE JOURNEY</div>
                <div style="font-size: 13px; color: #cbd5e1; margin-top: 4px;">
                  <span style="color: #4ade80; font-weight: 700;">●</span> Portfolio ({p_last_str}) &nbsp;&bull;&nbsp;
                  <span style="color: #a78bfa; font-weight: 700;">◦</span> {benchmark_id} ({b_last_str})
                </div>
              </td>
              <td align="right" valign="top">
                {win_badge}
              </td>
            </tr>
          </table>

          <!--[if !mso]><!-->
          {svg_markup}
          <!--<![endif]-->
          {mso_fallback}
        </div>
      </td>
    </tr>"""

    text_block = f"• Cumulative Journey: Portfolio {p_last_str} vs {benchmark_id} {b_last_str} ({text_status})"
    return html_block, text_block


def _render_calendar_heatmap(wrap_document: dict) -> tuple[str, str]:
    """Render 7-column calendar table with daily performance cells, ATH highlight, and best/worst days."""
    period = str(wrap_document.get("period") or "")
    if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", period):
        year, month = int(period[:4]), int(period[5:7])
    else:
        now = datetime.now()
        year, month = now.year, now.month

    daily_moves = wrap_document.get("daily_moves") or []
    moves_by_day = {}
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

    first_weekday, num_days = calendar.monthrange(year, month)  # 0=Mon, 6=Sun

    weeks = []
    current_week = [None] * first_weekday
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
        f'<th width="14.28%" style="padding: 4px; font-size: 10px; font-weight: 700; color: #64748b; text-align: center;">{h}</th>'
        for h in headers
    )

    rows_html = []
    for week in weeks:
        cells_html = []
        for d in week:
            if d is None:
                cells_html.append('<td width="14.28%" style="padding: 3px;"></td>')
            else:
                move = moves_by_day.get(d)
                if move and move.get("change_pct") is not None:
                    chg_val = float(move["change_pct"])
                    sign = "+" if chg_val > 0 else ""
                    pct_str = f"{sign}{chg_val:.1f}%"
                    if chg_val > 0:
                        bg = "rgba(74, 222, 128, 0.16)"
                        border = "rgba(74, 222, 128, 0.35)"
                        color = "#4ade80"
                    elif chg_val < 0:
                        bg = "rgba(248, 113, 113, 0.14)"
                        border = "rgba(248, 113, 113, 0.30)"
                        color = "#f87171"
                    else:
                        bg = "#1a233a"
                        border = "#24304d"
                        color = "#94a3b8"
                else:
                    bg = "#161e31"
                    border = "#1f2a44"
                    color = "#475569"
                    pct_str = "&nbsp;"

                ath_border = "border: 1px solid #f59e0b;" if (move and move.get("is_ath")) else f"border: 1px solid {border};"

                cell = f"""<td width="14.28%" style="padding: 3px; text-align: center; vertical-align: top;">
                  <div style="background-color: {bg}; {ath_border} border-radius: 6px; padding: 4px 1px; min-height: 38px;">
                    <div style="font-size: 11px; font-weight: 700; color: #f8fafc; line-height: 1.1;">{d}</div>
                    <div style="font-size: 9px; font-weight: 600; color: {color}; margin-top: 2px; line-height: 1.1;">{pct_str}</div>
                  </div>
                </td>"""
                cells_html.append(cell)
        rows_html.append(f"<tr>{''.join(cells_html)}</tr>")

    best_str = "—"
    worst_str = "—"
    chips_html = ""
    if best_day and best_day.get("change_pct") is not None:
        b_dt = str(best_day.get("date") or "")[5:]
        b_val = float(best_day["change_pct"])
        b_sign = "+" if b_val > 0 else ""
        best_str = f"{b_dt} ({b_sign}{b_val:.2f}%)"
    if worst_day and worst_day.get("change_pct") is not None:
        w_dt = str(worst_day.get("date") or "")[5:]
        w_val = float(worst_day["change_pct"])
        w_sign = "+" if w_val > 0 else ""
        worst_str = f"{w_dt} ({w_sign}{w_val:.2f}%)"

    if best_day or worst_day:
        chips_html = f"""<div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid #1e293b; font-size: 12px; color: #94a3b8;">
          <span style="color: #4ade80; font-weight: 600;">★ Best day:</span> {best_str} &nbsp;&bull;&nbsp;
          <span style="color: #f87171; font-weight: 600;">▼ Worst day:</span> {worst_str}
        </div>"""

    html_block = f"""
    <!-- Section 4: Daily Calendar Heatmap -->
    <tr>
      <td style="padding: 0 24px 24px;">
        <div style="background-color: #131d33; border: 1px solid #24304d; border-radius: 12px; padding: 18px 16px 14px;">
          <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; margin-bottom: 12px;">DAILY CALENDAR HEATMAP</div>
          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="table-layout: fixed;">
            <thead><tr>{header_cells}</tr></thead>
            <tbody>{''.join(rows_html)}</tbody>
          </table>
          {chips_html}
        </div>
      </td>
    </tr>"""

    text_block = f"• Calendar Highlights: Best day {best_str} | Worst day {worst_str}"
    return html_block, text_block


def _render_leader_anchor(carry: dict | None, anchor: dict | None, hide_cash: bool) -> tuple[str, str]:
    """Render Who Moved Your Month cards for leader and anchor assets."""
    if not carry and not anchor:
        return "", ""

    leader_html = ""
    anchor_html = ""
    leader_text = "None"
    anchor_text = "None"

    if carry:
        ticker = carry.get("ticker") or carry.get("name") or "—"
        name = carry.get("name") or ticker
        val_str = "---" if hide_cash else _fmt_money(carry.get("net_contribution_pln"), show_sign=True)
        note = carry.get("context_note") or ""
        leader_text = f"{ticker} ({val_str}) - {note}"
        leader_html = f"""<td width="50%" valign="top" style="padding: 0 4px 0 0;" class="stack-mobile-cell">
          <div style="background-color: #0b3a30; border: 1px solid #1d7a67; border-radius: 12px; padding: 16px;">
            <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #4ade80;">▲ MONTH LEADER</div>
            <div style="font-size: 18px; font-weight: 800; color: #f0fdf4; margin-top: 6px;">{ticker}</div>
            <div style="font-size: 12px; color: #a7f3d0; margin-bottom: 8px;">{name}</div>
            <div style="font-size: 15px; font-weight: 700; color: #4ade80;">{val_str}</div>
            <div style="font-size: 11px; color: #94a3b8; font-style: italic; margin-top: 4px;">{note}</div>
          </div>
        </td>"""

    if anchor:
        ticker = anchor.get("ticker") or anchor.get("name") or "—"
        name = anchor.get("name") or ticker
        val_str = "---" if hide_cash else _fmt_money(anchor.get("net_contribution_pln"), show_sign=True)
        note = anchor.get("context_note") or ""
        anchor_text = f"{ticker} ({val_str}) - {note}"
        anchor_html = f"""<td width="50%" valign="top" style="padding: 0 0 0 4px;" class="stack-mobile-cell">
          <div style="background-color: #3a1f20; border: 1px solid #7f3d3d; border-radius: 12px; padding: 16px;">
            <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #f87171;">▼ MONTH ANCHOR</div>
            <div style="font-size: 18px; font-weight: 800; color: #fff1f2; margin-top: 6px;">{ticker}</div>
            <div style="font-size: 12px; color: #fecaca; margin-bottom: 8px;">{name}</div>
            <div style="font-size: 15px; font-weight: 700; color: #f87171;">{val_str}</div>
            <div style="font-size: 11px; color: #94a3b8; font-style: italic; margin-top: 4px;">{note}</div>
          </div>
        </td>"""

    if carry and not anchor:
        inner_table = f"<tr>{leader_html.replace('width=\"50%\"', 'width=\"100%\"').replace('padding: 0 4px 0 0;', '')}</tr>"
    elif anchor and not carry:
        inner_table = f"<tr>{anchor_html.replace('width=\"50%\"', 'width=\"100%\"').replace('padding: 0 0 0 4px;', '')}</tr>"
    else:
        inner_table = f"<tr>{leader_html}{anchor_html}</tr>"

    html_block = f"""
    <!-- Section 5: Who Moved Your Month -->
    <tr>
      <td style="padding: 0 24px 24px;">
        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; margin-bottom: 10px;">WHO MOVED YOUR MONTH</div>
        <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" class="stack-mobile">
          {inner_table}
        </table>
      </td>
    </tr>"""

    text_block = f"• Month Leader: {leader_text}\n• Month Anchor: {anchor_text}"
    return html_block, text_block


def _render_market_context_and_seasonality(wrap_document: dict, period_title: str) -> tuple[str, str]:
    """Render global benchmarks and conditional seasonality section."""
    market_context = wrap_document.get("market_context") or []

    benchmark_labels = {
        "WIG": "WIG (Poland)",
        "DAX": "DAX (Germany)",
        "SP500": "S&P 500 (US)",
        "NASDAQ": "NASDAQ (US)",
        "FTSE100": "FTSE 100 (UK)",
        "MSCI_WORLD": "MSCI World",
    }

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

        if val is not None:
            color = "#4ade80" if val > 0 else ("#f87171" if val < 0 else "#94a3b8")
        else:
            color = "#64748b"

        row = f"""<tr>
          <td style="padding: 9px 12px; font-size: 13px; color: #cbd5e1; border-top: 1px solid #1e293b;">{label}</td>
          <td align="right" style="padding: 9px 12px; font-size: 13px; font-weight: 700; color: {color}; border-top: 1px solid #1e293b;">{ret_str}</td>
        </tr>"""
        bench_rows_html.append(row)
        bench_text_lines.append(f"  - {label}: {ret_str}")

    bench_table_html = ""
    if bench_rows_html:
        bench_table_html = f"""<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #1a233a; border-radius: 10px; border: 1px solid #24304d; overflow: hidden; margin-bottom: 14px;">
          {''.join(bench_rows_html)}
        </table>"""

    historical_years_count = int(wrap_document.get("historical_years_count") or 0)
    seasonality_html = ""
    seasonality_text = ""

    # User rule: only if we have more than 1 historical record for the same month!
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
            status_chip = '<span style="color: #4ade80; font-weight: 700;">✓ Current result beat seasonal history</span>'
            status_text = "Beat seasonal history"
        elif outperformed is False:
            status_chip = '<span style="color: #f59e0b; font-weight: 600;">Current result trailed seasonal history</span>'
            status_text = "Trailed seasonal history"
        else:
            status_chip = ""
            status_text = ""

        bar_html = f"""<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="height: 10px; border-radius: 5px; overflow: hidden; margin: 10px 0;">
          <tr>
            <td width="{neg_pct}%" style="background-color: #f87171; height: 10px;"></td>
            <td width="{pos_pct}%" style="background-color: #4ade80; height: 10px;"></td>
          </tr>
        </table>"""

        copy_text = f"{month_name} was negative in {neg_count} of {total} observations (avg {avg_neg}) and positive in {pos_count} (avg {avg_pos})."

        seasonality_html = f"""<div style="background-color: #1a233a; border-radius: 10px; border: 1px solid #24304d; padding: 14px 16px;">
          <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8;">SEASONALITY &bull; {month_name.upper()}</div>
          {bar_html}
          <div style="font-size: 12px; color: #cbd5e1; margin-bottom: 6px;">{copy_text}</div>
          <div style="font-size: 11px;">{status_chip}</div>
        </div>"""

        seasonality_text = f"\n• Seasonality ({month_name}): {copy_text} ({status_text})"

    html_block = f"""
    <!-- Section 6: The Bigger Picture -->
    <tr>
      <td style="padding: 0 24px 24px;">
        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; margin-bottom: 10px;">THE BIGGER PICTURE &bull; GLOBAL BENCHMARKS</div>
        {bench_table_html}
        {seasonality_html}
      </td>
    </tr>"""

    bench_text_joined = "\n".join(bench_text_lines)
    text_block = f"• Global Benchmarks:\n{bench_text_joined}{seasonality_text}"
    return html_block, text_block


def _render_trading_activity(trading_activity: dict | None, hide_cash: bool) -> tuple[str, str]:
    """Render turnover, 12m average comparison, and top 5 transactions."""
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
    avg_12m_str = "---" if hide_cash else (_fmt_money(avg_12m, show_sign=False) if avg_12m is not None else None)

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

            comp_html = f"""<div style="margin: 12px 0 16px;">
              <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="4">
                <tr>
                  <td width="90" style="font-size: 11px; color: #94a3b8;">This Month</td>
                  <td>
                    <div style="background-color: #1e293b; border-radius: 4px; overflow: hidden; height: 12px;">
                      <div style="background-color: #3b82f6; width: {curr_pct}%; height: 12px; border-radius: 4px;"></div>
                    </div>
                  </td>
                  <td width="90" align="right" style="font-size: 11px; font-weight: 700; color: #f8fafc;">{turnover_str}</td>
                </tr>
                <tr>
                  <td width="90" style="font-size: 11px; color: #64748b;">12m Average</td>
                  <td>
                    <div style="background-color: #1e293b; border-radius: 4px; overflow: hidden; height: 12px;">
                      <div style="background-color: #475569; width: {avg_pct}%; height: 12px; border-radius: 4px;"></div>
                    </div>
                  </td>
                  <td width="90" align="right" style="font-size: 11px; color: #94a3b8;">{avg_12m_str}</td>
                </tr>
              </table>
              <div style="font-size: 10px; color: {'#4ade80' if diff_pct > 0 else '#94a3b8'}; text-align: right; margin-top: 4px;">{diff_chip}</div>
            </div>"""
            comp_text = f" ({diff_chip})"
        except (ValueError, TypeError):
            pass

    buy_sell_html = f"""<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 12px;">
      <tr>
        <td style="font-size: 12px; color: #94a3b8;">
          BUY total: <strong style="color: #4ade80;">{buy_str}</strong> &nbsp;&bull;&nbsp;
          SELL total: <strong style="color: #f87171;">{sell_str}</strong>
        </td>
      </tr>
    </table>"""

    tx_rows_html = []
    tx_text_lines = []
    for tx in largest_txs[:5]:
        d = str(tx.get("date") or "")
        k = str(tx.get("type") or "").upper()
        ticker = str(tx.get("ticker") or "—")
        v = tx.get("value_pln")
        v_str = "---" if hide_cash else _fmt_money(v, show_sign=False)

        badge_bg = "rgba(74, 222, 128, 0.15)" if k == "BUY" else "rgba(248, 113, 113, 0.12)"
        badge_color = "#4ade80" if k == "BUY" else "#f87171"

        row = f"""<tr>
          <td style="padding: 7px 10px; font-size: 12px; color: #94a3b8; border-top: 1px solid #1e293b;">{d}</td>
          <td style="padding: 7px 10px; font-size: 10px; border-top: 1px solid #1e293b;">
            <span style="background-color: {badge_bg}; color: {badge_color}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">{k}</span>
          </td>
          <td style="padding: 7px 10px; font-size: 12px; font-weight: 600; color: #f8fafc; border-top: 1px solid #1e293b;">{ticker}</td>
          <td align="right" style="padding: 7px 10px; font-size: 12px; color: #cbd5e1; border-top: 1px solid #1e293b;">{v_str}</td>
        </tr>"""
        tx_rows_html.append(row)
        tx_text_lines.append(f"  - {d} {k} {ticker}: {v_str}")

    if tx_rows_html:
        tx_table_html = f"""<div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #94a3b8; margin: 10px 0 8px;">TOP 5 TRANSACTIONS</div>
        <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #1a233a; border-radius: 8px; border: 1px solid #24304d; overflow: hidden;">
          {''.join(tx_rows_html)}
        </table>"""
    else:
        tx_table_html = '<div style="font-size: 12px; color: #64748b; font-style: italic; margin-top: 8px;">No trades executed this month</div>'

    html_block = f"""
    <!-- Section 7: Trading Activity -->
    <tr>
      <td style="padding: 0 24px 28px;">
        <div style="background-color: #131d33; border: 1px solid #24304d; border-radius: 12px; padding: 18px 16px;">
          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8;">TRADING ACTIVITY</div>
                <div style="font-size: 20px; font-weight: 800; color: #f8fafc; margin-top: 4px;">Turnover: {turnover_str}</div>
              </td>
            </tr>
          </table>
          {comp_html}
          {buy_sell_html}
          {tx_table_html}
        </div>
      </td>
    </tr>"""

    text_block = f"• Trading Activity: Turnover {turnover_str}{comp_text} (Buy: {buy_str}, Sell: {sell_str})\n" + (
        "• Top Transactions:\n" + "\n".join(tx_text_lines) if tx_text_lines else ""
    )
    return html_block, text_block


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

    # Benchmark resolution
    journey = wrap_document.get("journey") or {}
    benchmark_id = (
        wrap_document.get("benchmark_id")
        or journey.get("benchmark_id")
        or (user_profile.get("settings") or {}).get("benchmark")
        or "WIG"
    )
    benchmark_name = journey.get("benchmark_name") or benchmark_id

    benchmark_ret = wrap_document.get("benchmark_return_pct")
    if benchmark_ret is None:
        benchmark_ret = journey.get("benchmark_return_pct")
    if benchmark_ret is None and isinstance(wrap_document.get("market_context"), list):
        for ctx in wrap_document["market_context"]:
            if ctx.get("id") == benchmark_id and ctx.get("return_pct") is not None:
                benchmark_ret = ctx.get("return_pct")
                if not benchmark_name or benchmark_name == benchmark_id:
                    benchmark_name = ctx.get("name") or benchmark_id
                break
    benchmark_str = _fmt_pct(benchmark_ret, show_sign=True)

    # World benchmark from market_context
    world_ret = None
    if isinstance(wrap_document.get("market_context"), list):
        for ctx in wrap_document["market_context"]:
            if ctx.get("id") == "MSCI_WORLD" and ctx.get("return_pct") is not None:
                world_ret = ctx.get("return_pct")
                break
    world_str = _fmt_pct(world_ret, show_sign=True)

    best_wallet = wrap_document.get("best_efficiency_wallet") or {}
    best_wallet_name = best_wallet.get("name") or "—"
    best_wallet_twr = _fmt_pct(best_wallet.get("twr_pct"), show_sign=True)

    profit_wallet = wrap_document.get("primary_profit_engine_wallet") or {}
    profit_wallet_name = profit_wallet.get("name") or "—"
    profit_wallet_nominal = "---" if hide_cash else _fmt_money(profit_wallet.get("nominal_change_pln"), show_sign=True)

    app_url = os.environ.get("APP_URL", "https://roastfolio.app")

    # Direction styling
    try:
        twr_val = float(overall_twr or 0)
    except (ValueError, TypeError):
        twr_val = 0.0

    if twr_val > 0:
        accent_color = "#4ade80"  # emerald-400
        headline = "A little more momentum."
    elif twr_val < 0:
        accent_color = "#f87171"  # red-400
        headline = "A step back. The story continues."
    else:
        accent_color = "#94a3b8"  # slate-400
        headline = "Holding your ground."

    # Subject line
    subject = f"Roastfolio Monthly Recap — {period_title} ({twr_str})"

    # Render modular sections
    journey_html, journey_text = _render_svg_journey_chart(journey, benchmark_id)
    calendar_html, calendar_text = _render_calendar_heatmap(wrap_document)
    leader_anchor_html, leader_anchor_text = _render_leader_anchor(
        wrap_document.get("carry"), wrap_document.get("anchor"), hide_cash
    )
    market_context_html, market_context_text = _render_market_context_and_seasonality(
        wrap_document, period_title
    )
    trading_html, trading_text = _render_trading_activity(
        wrap_document.get("trading_activity"), hide_cash
    )

    # Plain text version
    if hide_cash:
        cash_flow_line = "• Net Cash Flow:               --- (amounts hidden)"
        nominal_line = "• Nominal Change:              --- (amounts hidden)"
        profit_wallet_line = f"• Primary Profit Engine:       {profit_wallet_name} (---)"
    else:
        cash_flow_line = f"• Net Cash Flow:               {cash_flow_str} (Deposits: {deposits_str}, Withdrawals: {withdrawals_str})"
        nominal_line = f"• Nominal Change:              {nominal_str}"
        profit_wallet_line = f"• Primary Profit Engine:       {profit_wallet_name} ({profit_wallet_nominal})"

    text_lines = [
        f"ROASTFOLIO MONTHLY RECAP: {period_title.upper()}",
        "=" * 44,
        f"Hello {nickname},",
        "",
        headline,
        "",
        f"• Time-Weighted Return (TWR): {twr_str}",
        nominal_line,
        cash_flow_line,
        f"• Benchmark ({benchmark_id}):           {benchmark_str}",
        f"• World (MSCI World):          {world_str}",
        f"• Maximum Drawdown:            {max_dd_str}",
        "",
        "PORTFOLIO HIGHLIGHTS:",
        f"• Best Return Wallet:          {best_wallet_name} ({best_wallet_twr})",
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

    # Subtitles for cards in privacy mode vs normal mode
    nominal_sub = '<div style="font-size: 11px; color: #64748b; margin-top: 2px;">Amounts hidden (privacy mode)</div>' if hide_cash else ''

    # HTML version
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    @media only screen and (max-width: 600px) {{
      .email-container {{ width: 100% !important; border-radius: 0 !important; }}
      .hero-number {{ font-size: 42px !important; }}
      .stack-mobile {{ display: block !important; width: 100% !important; }}
      .stack-mobile-cell {{ display: block !important; width: 100% !important; padding: 0 0 8px 0 !important; }}
    }}
  </style>
</head>
<body style="margin: 0; padding: 24px 12px; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f1f5f9; -webkit-font-smoothing: antialiased;">
  <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" class="email-container" style="max-width: 580px; margin: 0 auto; background-color: #131b2e; border-radius: 16px; border: 1px solid #1e293b; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);">
    <!-- Section 1: Header -->
    <tr>
      <td style="padding: 28px 32px 20px; border-bottom: 1px solid #1e293b;">
        <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <span style="font-size: 20px; font-weight: 800; letter-spacing: -0.5px; color: #ffffff;">roastfolio</span>
            </td>
            <td align="right">
              <span style="font-size: 11px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; color: #94a3b8; background-color: #1e293b; padding: 4px 10px; border-radius: 12px;">{period_title}</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- Section 2: Hero Return & Bento Cards -->
    <tr>
      <td style="padding: 32px 32px 20px; text-align: center;">
        <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8;">TIME-WEIGHTED RETURN</span>
        <div class="hero-number" style="font-size: 52px; font-weight: 800; letter-spacing: -2px; color: {accent_color}; margin: 8px 0 4px;">{twr_str}</div>
        <div style="font-size: 15px; color: #cbd5e1; font-weight: 500;">{headline}</div>
      </td>
    </tr>

    <!-- Bento Metric Cards (2x2) -->
    <tr>
      <td style="padding: 0 24px 20px;">
        <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="8" class="stack-mobile">
          <tr>
            <td width="50%" style="background-color: #1a233a; border-radius: 12px; padding: 16px; border: 1px solid #24304d;" class="stack-mobile-cell">
              <div style="font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Nominal Gain/Loss</div>
              <div style="font-size: 20px; font-weight: 700; color: #f8fafc; margin-top: 4px;">{nominal_str}</div>
              {nominal_sub}
            </td>
            <td width="50%" style="background-color: #1a233a; border-radius: 12px; padding: 16px; border: 1px solid #24304d;" class="stack-mobile-cell">
              <div style="font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Benchmark ({benchmark_id})</div>
              <div style="font-size: 20px; font-weight: 700; color: #f8fafc; margin-top: 4px;">{benchmark_str}</div>
              <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Selected comparison</div>
            </td>
          </tr>
          <tr>
            <td width="50%" style="background-color: #1a233a; border-radius: 12px; padding: 16px; border: 1px solid #24304d;" class="stack-mobile-cell">
              <div style="font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">World (MSCI World)</div>
              <div style="font-size: 20px; font-weight: 700; color: #f8fafc; margin-top: 4px;">{world_str}</div>
              <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Global equities benchmark</div>
            </td>
            <td width="50%" style="background-color: #1a233a; border-radius: 12px; padding: 16px; border: 1px solid #24304d;" class="stack-mobile-cell">
              <div style="font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Max Drawdown</div>
              <div style="font-size: 20px; font-weight: 700; color: #f8fafc; margin-top: 4px;">{max_dd_str}</div>
              <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Peak-to-trough low</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- Wallet Highlights -->
    <tr>
      <td style="padding: 0 24px 24px;">
        <div style="background-color: #182035; border-radius: 12px; padding: 16px 20px; border: 1px solid #24304d;">
          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
            <tr>
              <td style="font-size: 13px; color: #94a3b8; padding-bottom: 6px;">Best Return Wallet</td>
              <td align="right" style="font-size: 13px; font-weight: 600; color: #f8fafc; padding-bottom: 6px;">{best_wallet_name} <span style="color: #4ade80;">({best_wallet_twr})</span></td>
            </tr>
            <tr>
              <td style="font-size: 13px; color: #94a3b8;">Primary Profit Engine</td>
              <td align="right" style="font-size: 13px; font-weight: 600; color: #f8fafc;">{profit_wallet_name} <span style="color: #94a3b8;">({profit_wallet_nominal})</span></td>
            </tr>
          </table>
        </div>
      </td>
    </tr>

    {journey_html}
    {calendar_html}
    {leader_anchor_html}
    {market_context_html}
    {trading_html}

    <!-- Section 8: CTA Button -->
    <tr>
      <td align="center" style="padding: 8px 32px 36px;">
        <a href="{app_url}" target="_blank" style="display: inline-block; background-color: #3b82f6; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 700; padding: 14px 32px; border-radius: 8px; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);">
          View Full Recap in Roastfolio &rarr;
        </a>
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="padding: 20px 32px; background-color: #0e1424; border-top: 1px solid #1e293b; text-align: center;">
        <p style="margin: 0 0 6px; font-size: 12px; color: #64748b;">
          You received this report because email notifications are enabled for your Roastfolio account.
        </p>
        <p style="margin: 0; font-size: 11px; color: #475569;">
          Powered by TOMINEX &bull; Roastfolio Investment History &bull; Not investment advice.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return subject, text_body, html_body


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
