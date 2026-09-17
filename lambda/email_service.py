"""
lambda/email_service.py — Monthly Recap Email Notification Service

Formats and sends monthly performance summaries via AWS SES.
Supports multi-recipient dispatch, user notification preferences,
and dark-themed fintech HTML templates with plaintext fallbacks.
"""

from __future__ import annotations

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
DEFAULT_FROM_EMAIL = "notifications@roastfolio.com"


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


def render_monthly_recap_email(user_profile: dict, wrap_document: dict) -> tuple[str, str, str]:
    """
    Render subject, plaintext body, and HTML body for a monthly recap email.
    """
    period = wrap_document.get("period", "")
    period_title = _period_display(period)
    nickname = user_profile.get("nickname") or "Investor"

    overall_twr = wrap_document.get("overall_twr_pct")
    twr_str = _fmt_pct(overall_twr, show_sign=True)

    nominal_change = wrap_document.get("overall_nominal_change_pln")
    nominal_str = _fmt_money(nominal_change, show_sign=True)

    cash_flow = wrap_document.get("cash_flow_pln")
    cash_flow_str = _fmt_money(cash_flow, show_sign=True)

    deposits = wrap_document.get("deposits_pln")
    deposits_str = _fmt_money(deposits, show_sign=False)

    withdrawals = wrap_document.get("withdrawals_pln")
    withdrawals_str = _fmt_money(withdrawals, show_sign=False)

    max_dd = wrap_document.get("max_drawdown_pct")
    max_dd_str = _fmt_pct(max_dd, show_sign=False)

    benchmark_id = wrap_document.get("benchmark_id") or "WIG"
    benchmark_ret = wrap_document.get("benchmark_return_pct")
    benchmark_str = _fmt_pct(benchmark_ret, show_sign=True)

    best_wallet = wrap_document.get("best_efficiency_wallet") or {}
    best_wallet_name = best_wallet.get("name") or "—"
    best_wallet_twr = _fmt_pct(best_wallet.get("twr_pct"), show_sign=True)

    profit_wallet = wrap_document.get("primary_profit_engine_wallet") or {}
    profit_wallet_name = profit_wallet.get("name") or "—"
    profit_wallet_nominal = _fmt_money(profit_wallet.get("nominal_change_pln"), show_sign=True)

    app_url = os.environ.get("APP_URL", "https://roastfolio.com")

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

    # Plain text version
    text_lines = [
        f"ROASTFOLIO MONTHLY RECAP: {period_title.upper()}",
        "=" * 44,
        f"Hello {nickname},",
        "",
        headline,
        "",
        f"• Time-Weighted Return (TWR): {twr_str}",
        f"• Nominal Change:              {nominal_str}",
        f"• Net Cash Flow:               {cash_flow_str} (Deposits: {deposits_str}, Withdrawals: {withdrawals_str})",
        f"• Benchmark ({benchmark_id}):           {benchmark_str}",
        f"• Maximum Drawdown:            {max_dd_str}",
        "",
        "PORTFOLIO HIGHLIGHTS:",
        f"• Best Return Wallet:          {best_wallet_name} ({best_wallet_twr})",
        f"• Primary Profit Engine:       {profit_wallet_name} ({profit_wallet_nominal})",
        "",
        f"View your interactive audit & shareable card: {app_url}",
        "",
        "-" * 44,
        "You received this email because email notifications are enabled in Roastfolio.",
        "You can manage your email notification settings and recipients anytime in User Settings.",
    ]
    text_body = "\n".join(text_lines)

    # HTML version
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 24px 12px; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f1f5f9; -webkit-font-smoothing: antialiased;">
  <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="max-width: 580px; margin: 0 auto; background-color: #131b2e; border-radius: 16px; border: 1px solid #1e293b; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);">
    <!-- Header -->
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

    <!-- Hero Return -->
    <tr>
      <td style="padding: 32px 32px 24px; text-align: center;">
        <span style="font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; color: #94a3b8;">Time-Weighted Return</span>
        <div style="font-size: 48px; font-weight: 800; letter-spacing: -1.5px; color: {accent_color}; margin: 8px 0 4px;">{twr_str}</div>
        <div style="font-size: 15px; color: #cbd5e1; font-weight: 500;">{headline}</div>
      </td>
    </tr>

    <!-- Bento Metric Cards -->
    <tr>
      <td style="padding: 0 24px 24px;">
        <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="8">
          <tr>
            <td width="50%" style="background-color: #1a233a; border-radius: 12px; padding: 16px; border: 1px solid #24304d;">
              <div style="font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Nominal Gain/Loss</div>
              <div style="font-size: 20px; font-weight: 700; color: #f8fafc; margin-top: 4px;">{nominal_str}</div>
            </td>
            <td width="50%" style="background-color: #1a233a; border-radius: 12px; padding: 16px; border: 1px solid #24304d;">
              <div style="font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Benchmark ({benchmark_id})</div>
              <div style="font-size: 20px; font-weight: 700; color: #f8fafc; margin-top: 4px;">{benchmark_str}</div>
            </td>
          </tr>
          <tr>
            <td width="50%" style="background-color: #1a233a; border-radius: 12px; padding: 16px; border: 1px solid #24304d;">
              <div style="font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Net Cash Flow</div>
              <div style="font-size: 17px; font-weight: 700; color: #f8fafc; margin-top: 4px;">{cash_flow_str}</div>
              <div style="font-size: 11px; color: #64748b; margin-top: 2px;">+{deposits_str} / -{withdrawals_str}</div>
            </td>
            <td width="50%" style="background-color: #1a233a; border-radius: 12px; padding: 16px; border: 1px solid #24304d;">
              <div style="font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Max Drawdown</div>
              <div style="font-size: 17px; font-weight: 700; color: #f8fafc; margin-top: 4px;">{max_dd_str}</div>
              <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Monthly low peak-to-trough</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- Highlights Section -->
    <tr>
      <td style="padding: 0 32px 28px;">
        <div style="background-color: #182035; border-radius: 12px; padding: 18px 20px; border: 1px solid #24304d;">
          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
            <tr>
              <td style="font-size: 13px; color: #94a3b8; padding-bottom: 8px;">Best Return Wallet</td>
              <td align="right" style="font-size: 13px; font-weight: 600; color: #f8fafc; padding-bottom: 8px;">{best_wallet_name} <span style="color: #4ade80;">({best_wallet_twr})</span></td>
            </tr>
            <tr>
              <td style="font-size: 13px; color: #94a3b8;">Primary Profit Engine</td>
              <td align="right" style="font-size: 13px; font-weight: 600; color: #f8fafc;">{profit_wallet_name} <span style="color: #94a3b8;">({profit_wallet_nominal})</span></td>
            </tr>
          </table>
        </div>
      </td>
    </tr>

    <!-- CTA Button -->
    <tr>
      <td align="center" style="padding: 0 32px 36px;">
        <a href="{app_url}" target="_blank" style="display: inline-block; background-color: #3b82f6; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 600; padding: 12px 28px; border-radius: 8px; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);">
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
    subject, text_body, html_body = render_monthly_recap_email(user_profile, wrap_document)

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

    return send_monthly_recap_email(user_profile, wrap_document, ses_client=ses_client)
