# Roastfolio Release Numbering & Versioning Policy

**Owner:** TOMINEX  
**Current Release:** `13.0.0`  
*Target Release Numbering Standard — v13.0.0*

---

## 1. Overview

Roastfolio uses a structured three-tier versioning format to identify every release deployed across development, staging/test, and production environments:

$$\textbf{MAJOR} \ . \ \textbf{MINOR} \ . \ \textbf{SERVICE}$$

Example: **`11.2.1`**

| Tier | Name | Purpose | Example Transition |
| :--- | :--- | :--- | :--- |
| **X** | **Major Version** | **New features** & capabilities added to the application | `11.2.1` $\rightarrow$ `12.0.0` |
| **Y** | **Minor Version** | **Changes to existing features** (refinements, UX redesigns, logic updates) | `11.2.1` $\rightarrow$ `11.3.0` |
| **Z** | **Service Release** | **Bug fixes**, performance improvements, security hotfixes | `11.2.1` $\rightarrow$ `11.2.2` |

---

## 2. Release Numbering Scheme

### 2.1 Major Releases (`MAJOR.0.0`)
A Major release represents **monumental architectural milestones, new fundamental sub-systems, or complete paradigm shifts**.

* **Triggers:**
  * Introducing a brand new core capability (e.g., automated monthly performance summaries, Monte Carlo retirement modeling engine, multi-wallet ledger reconciliation, or tax accounting overhaul).
  * Major breaking database schema transitions or protocol overhauls.
* **Increment Rules:** Major increments by 1; Minor and Service reset to 0.

### 2.2 Minor Releases (`MAJOR.MINOR.0`)
A Minor release introduces **significant functional enhancements, redesigned user journeys, or new views within existing modules**.

* **Triggers:**
  * Enhancements to existing features (e.g., hiding cash/PLN amounts in email notifications, interactive milestone calendars, floating tooltip charts).
  * Non-breaking data structure enrichments.
* **Increment Rules:** Minor increments by 1; Service resets to 0.

### 2.3 Service Releases (`MAJOR.MINOR.SERVICE`)
A Service release increment indicates **defect corrections, stability fixes, or performance optimizations**.
* **Triggers:**
  * Bug fixes (e.g., timezone parsing discrepancies, rounding errors, layout clipping on mobile).
  * Performance tuning (e.g., DynamoDB batch optimizations, client-side asset caching).
  * Security patches and dependency updates.
* **Increment Rules:** Service increments by 1; Major and Minor remain untouched.

---

## 3. Active Release State

* **Current Active Release:** `13.0.0`
  * **Major 13:** Spotify Wrapped & Revolut-style monthly audit email template redesign featuring inline SVG cumulative journey chart with dynamic green/red outperformance fill, 7-column calendar heatmap, Who Moved Your Month leader & anchor asset highlights, global benchmarks table, conditional seasonality analysis, and trailing 12-month turnover comparison.
  * **Minor 0:** Baseline for Major tier 13.
  * **Service Release 0:** Baseline for Major tier 13.
* **Prior Releases:**
  * **12.1.0:** Added user privacy preference to mask PLN cash flow and nominal positions in notification emails (`hideCashInNotifications`), integrated share dialog privacy checkbox with email dispatch, and resolved journey & market context benchmark return extraction.
  * **12.0.5:** Complete AWS SES domain & DKIM verification for `roastfolio.app` and update dev environment sender to `notifications@roastfolio.app`.
  * **12.0.4:** Update default notification sender address and domain references to `roastfolio.app` (`notifications@roastfolio.app`).
  * **12.0.3:** AWS SES sandbox verification error detection with user-friendly actionable status messages, HTTP 422 unverified identity response, and configurable dev environment SES notification sender address.
  * **12.0.2:** Client-side exponential backoff retry on transient 5xx server errors, graceful fallback caching in `portfolios.js`, and comprehensive exception resilience for `/benchmark-returns`.
  * **12.0.1:** Register `/monthly-wraps/email` in CloudFormation/SAM template to resolve API Gateway CORS preflight failure for email recap dispatches.
  * **12.0.0:** Baseline release for Major tier 12 (automated report email engine, multi-recipient notification preferences, and share dialog email recap trigger).
  * **11.8.0:** Added interactive daily returns calendar widget to The Milestones section on Monthly Summaries, featuring positive/negative return day coloring, hover tooltip with PLN and % returns, Best Day and Worst Day indicators, and celebratory All-Time High (ATH) styling with radiant gold pulsing halo and trophy badge.
  * **11.7.0:** Floating interactive hover tooltip directly on The Journey chart in Summaries (replacing static under-chart display section) showing detailed date, portfolio return, and benchmark return with indicator swatches and bounds clamping.
  * **11.6.2:** Continuous calendar day snapshot backfilling from earliest historical transaction dates (e.g. 2021), fast incremental XIRR/TWR recalculation, and background async worker dispatch for all transaction modifications.
  * **11.6.1:** Present transaction validation errors in dedicated modal popup dialogs instead of inline table rows.
  * **11.6.0:** Base release for Minor tier 6 (cash invariant validation and snapshot reuse).
  * **11.5.1:** Fix monthly wrap production authentication by enabling Authorization Bearer header fallback when API Gateway authorizer claims are omitted.
  * **11.5.0:** Base release for Minor tier 5 (Monthly Recap UX redesigns).
  * **11.4.5:** Benchmark returns API 500 error resilience and browser extension runtime.lastError suppression.
  * **11.4.0:** Summary wrapped benchmarks card in the right bottom corner displaying Poland (WIG) and World (MSCI ACWI) monthly returns.
  * **11.3.0:** Subtle tactile texture and ambient lighting mesh on wrapped covers, global market comparison one-liner against MSCI World, gapless weekend benchmark extrapolation in Journey, and dynamic benchmark returns in The Bigger Picture.
  * **11.2.1:** Boundary date alignments, asset query versioning, and stability fixes.
  * **11.2.0:** Editorial Bento presentation, interactive dated return charts, and private share sheets.
* **Organization:** Powered by **TOMINEX**.

---

## 4. Release Checklist & Version Bump Procedure

When preparing a release for deployment:

1. **Classify the Changes:**
   * Did you add a new feature? $\rightarrow$ Bump **Major** (`12.0.0`).
   * Did you modify an existing feature? $\rightarrow$ Bump **Minor** (`11.5.0`).
   * Did you only fix bugs or performance? $\rightarrow$ Bump **Service** (`11.2.2`).

2. **Update Version in Codebase:**
   * `src/index.html` (Footer badge `<span id="app-version-display">X.Y.Z</span>` and meta tags).
   * `src/guide.html` (Release Numbering section badge).
   * `src/auth.html` (Footer version indicator).
   * `docs/RELEASE_NUMBERING.md` (Current release header and history).

3. **Verify Contract & Integration Tests:**
   ```bash
   .venv/bin/pytest tests/test_footer_and_release_contract.py
   .venv/bin/pytest tests/test_dashboard_ui_contract.py tests/test_monthly_audit_ui_contract.py
   ```

4. **Commit & Deploy:**
   * Commit message format: `Release vX.Y.Z: Summary of changes`
   * Branch deployment follows workspace branching strategy (`dev` $\rightarrow$ `test` $\rightarrow$ `prod`).
