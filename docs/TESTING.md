# Testing Guidelines & Architecture — roastfolio

This document outlines the testing strategy, test classifications, speed optimizations, and authentication bypass procedures for roastfolio.

---

## 1. Overview & Strategy

To maintain rapid development velocity and ensure rock-solid stability, tests in roastfolio are divided into three distinct tiers:

| Tier | Runner Command | Typical Runtime | Target Use Cases |
| :--- | :--- | :--- | :--- |
| **Smoke Tests** | `./test.sh smoke` or `npm run test:smoke` | **< 1.0 second** | UI changes, CSS tweaks, DOM IDs, footer versioning, template contracts, layout regressions |
| **Full Tests** | `./test.sh full` or `npm run test:full` | ~15–30 seconds | Backend calculations, financial models (XIRR, TWR, AVCO), ledger sync, Lambda handlers |
| **Browser Tests** | `./test.sh browser` or `npm run test:browser` | ~3–5 seconds | Playwright/Chromium isolated frontend behavior and dialog interactions (mock fixtures) |

---

## 2. Smoke Tests (Fast UI Verification)

### When to run:
Run after **any change** to HTML files, CSS styles, JavaScript frontend layout, footer versioning, brand assets, or guide pages.

### Included Suites:
- `tests/test_footer_and_release_contract.py`: Validates footer DOM, version synchronization across all screens, and links.
- `tests/test_dashboard_ui_contract.py`: Validates dashboard layout, KPI elements, service worker cache, and styles.
- `tests/test_guide_mobile_contract.py`: Verifies responsive guide structure.
- `tests/test_monthly_audit_ui_contract.py`: Verifies monthly audit modal DOM contracts.
- `tests/test_mobile_benchmark_contract.py`: Verifies mobile benchmark dropdowns and event wiring.
- `tests/test_template_contract.py`: Ensures template bank integrity and syntax.
- `tests/test_portfolio_editor_contract.py`: Validates portfolio editor DOM contracts.
- `tests/test_retirement_chart_contract.py`: Validates retirement chart and slider contracts.
- `tests/test_retirement_simulation_contract.py`: Verifies simulation UI and parameter inputs.
- `tests/test_transaction_inline_layout.py`: Verifies inline `.wallet-tx-card` layout and flexbox contracts.
- `tests/test_prompt_builder.py`: Verifies AI prompt builder safety rules and output schemas.

### Command:
```bash
./test.sh smoke
# or
npm run test:smoke
```

---

## 3. Strict Rule: Never Create Users or Reset Passwords for UI Testing

### 🚫 Prohibited Anti-Pattern:
Do **NOT** automate sign-up flows, Cognito user pool registrations, or password reset flows during UI development or testing. These operations:
- Introduce network latencies (10–30+ seconds).
- Clutter user pools and database records with temporary test accounts.
- Risk AWS SES / Cognito rate limits or sandbox restrictions.
- Are completely unnecessary for verifying UI state, layouts, and DOM contracts.

### ✅ Recommended Mock Authentication:
`src/scripts/auth-guard.js` has built-in instantaneous mock authentication bypasses.

To access any protected screen in a local browser or test harness without network or Cognito calls:
1. **URL Query Parameter**:
   ```
   http://localhost:8080/index.html?devAuth=1
   ```
2. **Browser LocalStorage**:
   ```javascript
   localStorage.setItem('roastfolio.devAuth', '1');
   ```

When enabled, `auth-guard.js` instantly creates a mock session for a developer account without making any network requests or requiring authentication credentials.

---

## 4. Full & Backend Test Suite

For modifications affecting financial mathematics, database queries, Lambda handlers, or data pipelines, run the full backend suite:

```bash
./test.sh full
# or
npm run test:full
```

This executes all backend unit and integration tests (including XIRR, AVCO, ledger transactions, report generators, and DynamoDB mocks), while excluding heavy browser-driven suites.

---

## 5. Browser Automation Suite (Playwright)

For isolated browser interactions using Playwright and headless Chromium with mocked local fixtures:

```bash
./test.sh browser
# or
npm run test:browser
```

These tests run against isolated local HTML files (e.g. `tests/monthly-audit.browser.html`) and do not connect to external AWS infrastructure.
