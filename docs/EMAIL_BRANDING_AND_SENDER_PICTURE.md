# Roastfolio Email Branding & Sender Picture Setup Guide

This guide describes how the Roastfolio logo is integrated into transactional/recap emails and how to configure the sender profile picture (avatar) across major email clients (Gmail, Apple Mail, Yahoo Mail, Outlook, etc.).

---

## 1. Summary Wrapped Email Header Logo

The monthly recap email template in [`lambda/email_service.py`](file:///Users/michal.bardadyn/Documents/Code/Dash/investment-history/lambda/email_service.py) renders the official Roastfolio logo (`https://roastfolio.app/data/logos/icon-192.png`) directly in the header table alongside the `roastfolio` wordmark:

```html
<table role="presentation" border="0" cellpadding="0" cellspacing="0">
  <tr>
    <td style="vertical-align:middle;padding-right:12px;">
      <img src="https://roastfolio.app/data/logos/icon-192.png" width="34" height="34" alt="roastfolio logo"
           style="display:block;width:34px;height:34px;border-radius:9px;border:1px solid rgba(0,242,254,0.3);box-shadow:0 2px 8px rgba(0,242,254,0.15);" border="0" />
    </td>
    <td style="vertical-align:middle;">
      <span style="font-size:18px;font-weight:800;letter-spacing:-0.5px;color:#ffffff;line-height:34px;">roastfolio</span>
    </td>
  </tr>
</table>
```

---

## 2. Sender Picture (Avatar) Configuration

Email clients do not allow arbitrary avatar images to be embedded in email headers directly. Instead, email providers pull sender pictures using four industry standards. Follow the options below to display the Roastfolio logo as the sender picture for `notifications@roastfolio.app`:

### Option A: BIMI (Brand Indicators for Message Identification)
**Supported by:** Apple Mail (iOS 16+, macOS Ventura+), Yahoo Mail, Fastmail, and Gmail (with VMC).

1. **Hosted SVG Asset**:
   - The official BIMI-compliant SVG vector is hosted at:  
     `https://roastfolio.app/data/logos/roastfolio-bimi.svg` (and `roastfolio-logo.svg`).

2. **Cloudflare DNS Configuration**:
   Log in to Cloudflare DNS for `roastfolio.app` and add the following records:

   | Type | Name | Content / Value | TTL |
   | :--- | :--- | :--- | :--- |
   | **TXT** | `default._bimi` | `v=BIMI1; l=https://roastfolio.app/data/logos/roastfolio-bimi.svg; a=;` | Auto |
   | **TXT** | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:notifications@roastfolio.app` | Auto |

   *(Note: Ensure your SPF and AWS SES DKIM records remain active for `roastfolio.app`).*

---

### Option B: Google Account Profile Picture (100% Coverage for Gmail Users)
**Supported by:** All Gmail web and mobile app users.

Gmail displays the Google profile picture associated with the sender email address:

1. Go to [Google Sign Up](https://accounts.google.com/signup) or Google Account settings.
2. Select **"Use my current email address instead"** and enter:  
   `notifications@roastfolio.app`
3. Verify the email address using the confirmation code sent by Google to that address.
4. Once verified, go to **Google Account Profile** $\rightarrow$ **Profile Picture**.
5. Upload [`src/data/logos/icon-512.png`](file:///Users/michal.bardadyn/Documents/Code/Dash/investment-history/src/data/logos/icon-512.png).
6. **Result:** All Gmail users will immediately see the official neon candlestick Roastfolio logo next to incoming notification emails.

---

### Option C: Gravatar (Universal Avatar Service)
**Supported by:** Thunderbird, Spark, webmail clients, CRM platforms, and developer mail tools.

1. Go to [Gravatar.com](https://gravatar.com) and create/sign in to an account.
2. Add email address: `notifications@roastfolio.app`
   *(MD5 hash: `6754b6d6a65f5b411540010ef027679f`)*
3. Upload [`src/data/logos/icon-512.png`](file:///Users/michal.bardadyn/Documents/Code/Dash/investment-history/src/data/logos/icon-512.png).
4. Set rating to **G (General Audiences)**.

---

### Option D: Apple Business Connect (Apple Mail Verified Brand)
**Supported by:** Apple Mail on iOS, iPadOS, and macOS.

1. Visit [Apple Business Connect](https://business.apple.com).
2. Sign in with an Apple ID and register the organization **TOMINEX / Roastfolio**.
3. Under **Branding / Mail**, submit the domain `roastfolio.app` and upload the square Roastfolio logo (`src/data/logos/icon-512.png`).
4. Once verified by Apple, the logo appears automatically across Apple Mail.

---

## 3. Brand Assets Summary

| File | Purpose | Resolution / Format |
| :--- | :--- | :--- |
| `src/data/logos/icon-192.png` | Email Header & PWA Icons | 192x192 PNG |
| `src/data/logos/icon-512.png` | High-Res Logo / Avatars | 512x512 PNG |
| `src/data/logos/roastfolio-bimi.svg` | BIMI Tiny-PS Vector Standard | Vector SVG (512x512 viewBox) |
| `src/data/logos/roastfolio-logo.svg` | Standard SVG Vector Logo | Vector SVG (512x512 viewBox) |
