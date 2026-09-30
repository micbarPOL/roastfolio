# Roastfolio UI Export for Google Stitch (stitch.withgoogle.com)

This directory contains modular screen components, design tokens, dedicated scoped CSS, and populated screenshots prepared specifically for Google Stitch.

## Screen Inventory

| Screen | Screenshot | HTML Component | Scoped CSS | Key Elements Included |
|---|---|---|---|---|
| **01 Dashboard** | `screenshots/01_dashboard.png` | `01_dashboard.html` | `00_design_tokens.css` | Total value card, 1D P&L, ATH drawdown, TWR dial gauge, Today's Movers cards, Monthly & Yearly returns, Retirement goals, WIG benchmark chart |
| **02 Wallets** | `screenshots/02_wallets.png` | `02_wallets.html` | `00_design_tokens.css` | Wallet chips (Summary, XTB, IKE), Active holdings table (AAPL, XTB, MSFT, CDR, Cash), Allocation donut, Quick Entry, Trade action buttons |
| **03 Portfolio** | `screenshots/03_portfolio.png` | `03_portfolio.html` | `03_portfolio.css` | Total portfolio donut chart with legend pills, individual wallet mini-donuts (XTB, IKE), holdings tabs, full holdings table with Price, Today, YTD, Current Value, Purchase Value, Profit/Loss, Total Return %, Portfolio % |
| **04 Statistics** | `screenshots/04_statistics.png` | `04_statistics.html` | `04_statistics.css` | All-Time / Monthly / Daily stats cards, Benchmark Comparison table (5 benchmarks vs Portfolio), Underwater Lakes drawdown charts, and Monthly Performance Heatmap table (2024–2026) |
| **05 Retirement** | `screenshots/05_retirement.png` | `05_retirement.html` | `05_retirement.css` | Retirement & FIRE forecast hero, Plan Setup inputs, past vs projected baseline simulation chart canvas, and key milestone summary cards |
| **06 Transactions** | `screenshots/06_transactions.png` | `06_transactions.html` | `06_transactions.css` | Turnover summary cards (Total, Inflow, Outflow, Dividends), Monthly turnover bar chart, 12-month activity calendar grid, and searchable transaction history table with op badges |
| **07 Coping Diary** | `screenshots/07_coping_diary.png` | `07_coping_diary.html` | `07_coping_diary.css` | Split pane Conviction Ledger with tag cloud chips (#HOLD, #TECH, #CONVICTION, #AI), active ledger cards, and Focus Sheet with note text, why buy thesis, checkpoints, and coping chat |
| **08 Analysis** | `screenshots/08_analysis.png` | `08_analysis.html` | `08_analysis.css` | Watchlist favorites strip with sparklines, interactive 1Y price chart, volume bars, technical indicator toggles (VOL, MA, MACD), fundamental properties grid |
| **09 Monthly Audit** | `screenshots/09_monthly_audit.png` | `09_monthly_audit.html` | `00_design_tokens.css` | Monthly recap bento grid, journey chart vs benchmark, milestone timeline, drawdown lakes, best/worst performance cards |
| **10 Releases** | `screenshots/10_releases.png` | `10_releases.html` | `00_design_tokens.css` | Release notes changelog, feature tags, version badge |
| **11 Auth** | `screenshots/11_auth.png` | `11_auth.html` | `00_design_tokens.css` | Fintech login / sign-up screen, credential inputs, OAuth actions |

## How to Show Screens to Google Stitch

### 1. Vision Input (Best for Visual Style & Layout)
- In Google Stitch, click the **Image Upload** icon next to the prompt bar.
- Upload the corresponding screenshot from `screenshots/` (e.g. `04_statistics.png`, `05_retirement.png`, `06_transactions.png`, or `07_coping_diary.png`).
- Stitch's vision model will instantly recognize the layout, dark-mode cards, gauges, charts, tables, and colors with **real numbers and filled components** (no loaders).

### 2. Code Input (For Semantic Structure & Data Fields)
- Open the corresponding `.html` file (e.g. `04_statistics.html`, `05_retirement.html`, `06_transactions.html`, or `07_coping_diary.html`).
- Copy the HTML section inside `<div class="stitch-screen-container">`.
- Also include the scoped CSS from the matching `.css` file (e.g. `04_statistics.css`, `05_retirement.css`, `06_transactions.css`, or `07_coping_diary.css`) along with `00_design_tokens.css`.
- Paste them into your prompt to tell Stitch what components, metrics, and actions exist.

---

## Example Prompts for Google Stitch

### Prompt for Statistics Screen (`04_statistics.html` + `04_statistics.css`):
```text
I am redesigning our fintech portfolio tracker web app "roastfolio".
I've attached a screenshot of our current Statistics & Benchmarks screen (04_statistics.png).
Here is the HTML structure and scoped CSS:

[PASTE HTML FROM 04_statistics.html HERE]
[PASTE CSS FROM 04_statistics.css HERE]

Design goals for this redesign:
- Keep the dark fintech neon aesthetic (cyan #00f2fe, emerald #4ade80, red #f87171, deep navy #050e18).
- Modernize the layout into a clean bento grid with glassmorphism cards.
- Highlight the 3 core sections:
  1. Performance metrics overview (All-time, monthly, daily cards).
  2. Benchmark comparison table (comparing portfolio return against WIG, S&P 500, NASDAQ, DAX, MSCI World).
  3. Underwater Lakes drawdown analysis and monthly performance heatmap grid.
- Keep tabular numbers aligned, with clear win/loss color badges and responsive mobile layout.
```

### Prompt for Retirement Screen (`05_retirement.html` + `05_retirement.css`):
```text
I am redesigning our fintech portfolio tracker web app "roastfolio".
I've attached a screenshot of our current Retirement & FIRE Forecast screen (05_retirement.png).
Here is the HTML structure and scoped CSS:

[PASTE HTML FROM 05_retirement.html HERE]
[PASTE CSS FROM 05_retirement.css HERE]

Design goals for this redesign:
- Maintain the dark fintech look and feel with high-contrast typography.
- Present a hero card showing the retirement target year, current nest egg, and monthly contribution progress.
- Include the simulation chart area with time range toggles (10Y, 20Y, 30Y, Full) comparing actual portfolio trajectory against baseline projections.
- Clean up the plan parameters form inputs (target amount, expected return, inflation, retirement age).
```

### Prompt for Transactions Screen (`06_transactions.html` + `06_transactions.css`):
```text
I am redesigning our fintech portfolio tracker web app "roastfolio".
I've attached a screenshot of our current Transactions screen (06_transactions.png).
Here is the HTML structure and scoped CSS:

[PASTE HTML FROM 06_transactions.html HERE]
[PASTE CSS FROM 06_transactions.css HERE]

Design goals for this redesign:
- Present 4 turnover KPI cards at top (Total Turnover, Inflow, Outflow, Dividends Received).
- Feature the 12-month activity heatmap calendar with Github-style intensity squares.
- Provide a clean, dense transaction ledger table with color-coded operation pills (BUY, SELL, DIVIDEND, DEPOSIT) and column filters.
```

### Prompt for Coping Diary Screen (`07_coping_diary.html` + `07_coping_diary.css`):
```text
I am redesigning our fintech portfolio tracker web app "roastfolio".
I've attached a screenshot of our Coping & Conviction Diary screen (07_coping_diary.png).
Here is the HTML structure and scoped CSS:

[PASTE HTML FROM 07_coping_diary.html HERE]
[PASTE CSS FROM 07_coping_diary.css HERE]

Design goals for this redesign:
- Elegant split-view layout: Left pane has the conviction tag cloud and asset ledger cards; Right pane has the Focus Sheet.
- The Focus Sheet displays:
  1. Header with investment thesis and active/inactive toggle slider.
  2. "Why Buy", "Exit Plan", and "Risk Factors" hypothesis cards.
  3. Milestone checkpoints checklist with due dates and checkboxes.
  4. Emotional coping log / commentary feed with timestamps and quick-entry input.
- Keep the purple/violet conviction accents (#a855f7) paired with cyber cyan (#00f2fe).
```
