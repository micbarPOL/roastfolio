"""Transactional recap email sender for Roastfolio periodic wrap summaries."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "wrap_email.html"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def _money_label(value: Any) -> str:
    if value is None:
        return "0"
    amount = float(value)
    prefix = "+" if amount >= 0 else "-"
    return f"{prefix}{abs(amount):,.0f} PLN"


def _format_signed_pct(value: Any) -> str:
    if value is None:
        return "0.0%"
    pct = float(value)
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _wallet_rows(wallets: list[dict[str, Any]]) -> str:
    if not wallets:
        return "<tr><td style='padding:16px 18px; color:#9ca3af; font-size:14px;'>Brak aktywnych portfeli w tym okresie.</td></tr>"

    rows = []
    for wallet in wallets:
        name = _safe_text(wallet.get("name", "Wallet"))
        flow = _safe_text(wallet.get("net_cash_flow", 0))
        twr = _safe_text(wallet.get("twr", 0))
        rows.append(
            """
            <tr class="stat-row" style="border-top:1px solid #1f2937;">
              <td style="padding:14px 18px; font-size:14px; color:#f3f4f6; font-weight:700; width:34%;">{wallet_name}</td>
              <td style="padding:14px 18px; font-size:14px; color:#d1d5db; width:33%;">Net Cash Flow: {flow_label}</td>
              <td style="padding:14px 18px; font-size:14px; color:#d1d5db; width:33%; text-align:right;">TWR: {twr_value}</td>
            </tr>
            """.format(
                wallet_name=name,
                flow_label=_safe_text(f"{_format_signed_pct(float(flow)) if flow is not None else '0.0%'}"),
                twr_value=_format_signed_pct(twr),
            )
        )
    return "".join(rows)


def _benchmark_rows(markets: list[dict[str, Any]]) -> str:
    if not markets:
        return "<tr><td style='padding:16px 18px; color:#9ca3af; font-size:14px;'>Brak danych benchmarku.</td></tr>"

    rows = []
    for item in markets:
        label = _safe_text(item.get("label", "Benchmark"))
        value = _format_signed_pct(item.get("value", 0))
        rows.append(
            """
            <tr style="border-top:1px solid #1f2937;">
              <td style="padding:14px 18px; font-size:14px; color:#f3f4f6; font-weight:700; width:50%;">{label}</td>
              <td style="padding:14px 18px; font-size:14px; color:#d1d5db; text-align:right; width:50%;">{value}</td>
            </tr>
            """.format(label=label, value=value)
        )
    return "".join(rows)


def _diary_rows(diary_entries: list[dict[str, Any]]) -> str:
    if not diary_entries:
        return ""  # monthly block optional

    html_rows = []
    for entry in diary_entries:
        label = _safe_text(entry.get("label", "Hipoteza"))
        status = str(entry.get("status", "pending")).lower()
        if status == "verified":
            dot = "<span style='display:inline-block; width:10px; height:10px; background-color:#34d399; border-radius:50%; margin-right:8px; vertical-align:middle;'></span>"
            status_label = "Verified"
        elif status == "falsified":
            dot = "<span style='display:inline-block; width:10px; height:10px; background-color:#fbbf24; border-radius:50%; margin-right:8px; vertical-align:middle;'></span>"
            status_label = "Falsified"
        else:
            dot = "<span style='display:inline-block; width:10px; height:10px; background:linear-gradient(135deg,#f59e0b,#ef4444); border-radius:50%; box-shadow:0 0 0 2px rgba(245,158,11,0.25); margin-right:8px; vertical-align:middle;'></span>"
            status_label = "Pending"

        html_rows.append(
            """
            <tr>
              <td style="padding:8px 18px; font-size:14px; color:#e5e7eb;">
                {dot}<span style="font-weight:700;">{label}</span>
                <span style="color:#9ca3af;"> · {status_label}</span>
              </td>
            </tr>
            """.format(dot=dot, label=label, status_label=status_label)
        )

    return """
      <tr>
        <td class="mobile-pad" style="padding:0 22px 18px 22px;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#111827; border:1px solid #1f2937; border-radius:14px; overflow:hidden;">
            <tr>
              <td style="padding:18px; border-bottom:1px solid #1f2937; font-size:12px; letter-spacing:1.2px; text-transform:uppercase; color:#9ca3af; font-weight:700;">
                Diary Hypotheses
              </td>
            </tr>
            <tr>
              <td style="padding:8px 0;">
                {rows}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    """.format(rows="".join(html_rows))


def render_periodic_recap_email(payload: dict[str, Any]) -> str:
    """Render a premium HTML recap email from the wrap payload."""
    period = str(payload.get("period", "weekly")).lower()
    title = payload.get("title") or ("Twoja Tygodniowa Triada" if period == "weekly" else "Miesięczny Audyt")
    user_name = payload.get("user_name") or "Twój profil"
    period_label = "Tygodniowy przegląd" if period == "weekly" else "Miesięczny audyt"

    wallet_html = _wallet_rows(payload.get("wallets") or [])
    benchmark_html = _benchmark_rows(payload.get("market") or [])
    carry_name = _safe_text((payload.get("carry") or {}).get("name", "Best asset"))
    carry_value = _format_signed_pct((payload.get("carry") or {}).get("value", 0))
    anchor_name = _safe_text((payload.get("anchor") or {}).get("name", "Weakest asset"))
    anchor_value = _format_signed_pct((payload.get("anchor") or {}).get("value", 0))
    diary_html = _diary_rows(payload.get("diary") or []) if period == "monthly" else ""
    cta_url = payload.get("cta_url") or "https://app.roastfolio.com/dashboard"

    template = _TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "%%TITLE%%": _safe_text(title),
        "%%USER_NAME%%": _safe_text(user_name),
        "%%PERIOD_LABEL%%": _safe_text(period_label),
        "%%WALLET_ROWS%%": wallet_html,
        "%%BENCHMARK_ROWS%%": benchmark_html,
        "%%CARRY_NAME%%": carry_name,
        "%%CARRY_VALUE%%": carry_value,
        "%%ANCHOR_NAME%%": anchor_name,
        "%%ANCHOR_VALUE%%": anchor_value,
        "%%DIARY_BLOCK%%": diary_html,
        "%%CTA_URL%%": _safe_text(cta_url),
    }

    compiled = template
    for key, value in replacements.items():
        compiled = compiled.replace(key, value)
    return compiled


def trigger_recap_delivery(recipient_email: str, payload: dict[str, Any], sender_email: str | None = None, subject: str | None = None, region_name: str | None = None) -> dict[str, Any]:
    """Render and send a recap email through Amazon SES."""
    if not recipient_email:
        raise ValueError("recipient_email is required")

    sender = sender_email or os.environ.get("SES_FROM_EMAIL")
    if not sender:
        raise ValueError("sender_email or SES_FROM_EMAIL must be set")

    body_html = render_periodic_recap_email(payload)
    subject_line = subject or payload.get("subject") or "Roastfolio Weekly Summary"

    try:
        client = boto3.client("ses", region_name=region_name or os.environ.get("AWS_REGION", "eu-west-1"))
        response = client.send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient_email]},
            Message={
                "Subject": {"Data": subject_line, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": body_html, "Charset": "UTF-8"},
                    "Text": {"Data": "Roastfolio recap summary. Open your dashboard for full details.", "Charset": "UTF-8"},
                },
            },
        )
        return {"ok": True, "message_id": response.get("MessageId"), "recipient": recipient_email}
    except (BotoCoreError, ClientError, ValueError) as exc:
        return {"ok": False, "error": str(exc), "recipient": recipient_email}


def dispatch_periodic_recap_email(recipient_email: str, payload: dict[str, Any], sender_email: str | None = None, subject: str | None = None, region_name: str | None = None) -> dict[str, Any]:
    return trigger_recap_delivery(recipient_email, payload, sender_email=sender_email, subject=subject, region_name=region_name)


_TEMPLATE = _TEMPLATE_PATH
