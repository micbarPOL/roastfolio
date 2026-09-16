# Roastfolio Release Numbering & Versioning Policy

**Owner:** TOMINEX  
**Current Release:** `11.6.2`  
**Standard:** Custom Three-Tier Semantic Release Standard

---

## 1. Overview

Roastfolio uses a structured three-tier versioning format to identify every release deployed across development, staging/test, and production environments:

$$\textbf{MAJOR} \ . \ \textbf{MINOR} \ . \ \textbf{SERVICE}$$

Example: **`11.2.1`**

| Tier | Name | Purpose | Example Transition |
| :--- | :--- | :--- | :--- |
| **X** | **Major Version** | **New features & capabilities** added to the application | `11.2.1` $\rightarrow$ `12.0.0` |
| **Y** | **Minor Version** | **Changes to existing features** (refinements, UX redesigns, logic updates) | `11.2.1` $\rightarrow$ `11.3.0` |
| **Z** | **Service Release** | **Bug fixes**, performance improvements, security hotfixes | `11.2.1` $\rightarrow$ `11.2.2` |

---

## 2. Release Tier Definitions

### 2.1 Major Versions (`MAJOR.0.0`)
A Major version increment indicates the introduction of **entirely new features or capabilities** to Roastfolio.

* **Triggers:**
  * Launch of a brand-new tab, screen, or tool (e.g., Coping Diary, Retirement Plan Simulator, Monthly Recaps, Asset Analysis).
  * Introduction of a new asset class or data engine (e.g., options tracking, crypto staking analytics).
  * Major architectural additions (e.g., native PDF/Canvas export engines, multi-portfolio consolidation engine).
* **Reset Rules:** When the Major version increases, the Minor and Service numbers reset to zero (e.g., `11.2.1` $\rightarrow$ `12.0.0`).

### 2.2 Minor Versions (`MAJOR.MINOR.0`)
A Minor version increment indicates **changes, improvements, or redesigns to existing features**.

* **Triggers:**
  * UI/UX layout redesigns of existing screens (e.g., Editorial Bento layout for Monthly Summaries, reworked transactions table, enhanced candlestick/sparkline components).
  * Enhancements to existing calculations (e.g., switching Average Cost Basis (AVCO) display models, adding new benchmark indices, adjusting time-weighted return charts).
  * Workflow changes or new configuration options within existing settings (e.g., roast intensity toggles, benchmark selector updates).
* **Reset Rules:** When the Minor version increases, the Service number resets to zero (e.g., `11.2.1` $\rightarrow$ `11.3.0`).

### 2.3 Service Releases (`MAJOR.MINOR.SERVICE`)
A Service release (also called patch or maintenance release) is dedicated exclusively to **bug fixes, reliability improvements, and corrections**.

* **Triggers:**
  * Bug fixes in calculation formulas, time-zone alignment, or date boundaries.
  * Visual regression fixes, CSS alignment, or responsive mobile glitch corrections.
  * Browser compatibility fixes (e.g., Safari iOS rendering quirks, dialog focus management).
  * Performance optimizations, memory leak fixes, or caching corrections.
  * Security patches and dependency maintenance.
* **Reset Rules:** The Service number increments by 1 for each bug fix deployment (e.g., `11.2.0` $\rightarrow$ `11.2.1`).

---

## 3. Current Release Status

* **Current Active Release:** `11.6.2`
  * **Major 11:** Multi-asset portfolio intelligence, Coping Diary, and Monthly Recaps.
  * **Minor 6:** Negative cash balance invariant validation across ledger history, snapshot reuse optimization for cash transaction edits, asynchronous background snapshot recalculation, and prominent UI error presentation.
  * **Service Release 2:** Continuous calendar day snapshot backfilling from earliest historical transaction dates (e.g. 2021), fast incremental XIRR/TWR recalculation, and background async worker dispatch for all transaction modifications.
* **Prior Releases:**
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
