# Project TODOs

## General / Bug Fixes

- [ ] **Dashboard Portfolio vs. Benchmark Chart Opening Dip**:
  - **Symptom**: Every day just after market opening hours, the portfolio return drops significantly and then goes back up. The benchmark return does not exhibit this drop.
  - **Investigation**: Investigate the intraday portfolio synthesis and quote timing right after exchange open (e.g. baseline quote mismatches, delayed quote arrivals, or cash/asset valuation discrepancies during opening minutes).

- [ ] **Synchronize Gauge and Portfolio vs. Benchmark Chart Return Values**:
  - **Symptom**: Return values on the dashboard gauge and the portfolio vs. benchmark chart disagree.
    - Example: Chart shows portfolio change `-0.12%` and benchmark `+0.13%`, whereas the gauge shows portfolio `+0.91%` and benchmark `+0.24%`.
  - **Action**: Align the calculation baseline, window reference (calendar-day vs. benchmark session / previous close), and data sources so that the gauge and the chart show identical portfolio and benchmark returns.

- [ ] **Fix mWIG40 Table Disappearing Data**:
  - **Symptom**: The monthly returns table data for `mWIG40` is intermittently disappearing and showing again. It should remain static and stable.
  - **Context**: The `generate_returns_data()` function in `update-prices.py` parses `src/data/myfund.pl_Emerytura_StopaZwrotuWOkresach.csv` and merges it with existing hand-corrected values. We need to investigate why these values toggle or disappear and ensure the data loads and remains static in the frontend.

## History UI 20 – Summaries poster (v15.3.0 on dev)

- [ ] **Poster stamp missing**: The circular "Beat the <benchmark>" sticker (stamp) is not visible on the Summaries poster in the app, although the mockup shows it when the benchmark was beaten.
- [ ] **Poster data placement differs from the mockup** (`design/mockups/history.html`, D-047):
  - The big TWR `+x.xx%`, nominal change, benchmarks and sparkline are placed differently than in the mockup.
  - Match the mockup layout: TWR block, side column with nominal change and benchmarks, and the sparkline in the poster body, on desktop and mobile.

## Features

- [ ] **Share today's daily return (poster)**:
  - **Goal**: Let the user share the current day's portfolio return as an image poster, very similar to the existing History Summaries share poster (`src/scripts/monthly-audit-share.js`).
  - **Content**: Today's % return (and optionally PLN, hidden by default like the recap amounts switch), benchmark return for the day, intraday sparkline, date, and Roastfolio branding.
  - **Comment engine**: Add a simple comment engine that picks a short, witty one-liner based on the day's scenario (e.g. big up day, big down day, flat, beat/lost to benchmark). Reuse tone profiles from the monthly commentary where possible, but keep it lightweight.

- [ ] **ATH Widget "Deep Ocean" Visual Redesign & Depth Thresholds**:
  - **Concept / Ocean Depth Zones**: Redesign the ATH widget ("Under the surface" lake) to visualize drawdowns as descending into a deep ocean:
    - **0% to -5% (Sunlit / Safe Shallows)**: Pleasant, friendly zone where we want to be; light water aesthetics with bubbles.
    - **-5% to -10% (Twilight / Danger Zone)**: Deeper, darker, unknown, and dangerous waters.
    - **Below -10% (Abyss / Deep & Scary)**: Deep, murky, and scary ocean depth (with markers for -10%, -15%, and beyond).
  - **Threshold Markers**: Explicitly display threshold indicators for `-5%`, `-10%`, and `-15%`.
  - **30-Day Deepest Level**: Visually show the deepest drawdown level reached in the last 30 days (e.g. max-depth indicator, anchor line, or ghost watermark).

- [ ] **Yearly Wrapped (Annual Portfolio Recap)**:
  - **Goal**: Implement the full "Yearly Wrapped" experience in History Summaries, activating the currently disabled `Yearly Soon` tab in the period navigator.
  - **UI & Bento Cards (Annual Scope)**:
    - Enable the `Monthly | Yearly` segmented switch in the period navigator, allowing users to browse completed calendar years (and current YTD).
    - Adapt recap Bento cards for 12-month data:
      - **Annual Return & Benchmarks**: Full-year TWR (%) vs WIG, S&P 500, MSCI World, DAX, etc., and total nominal return (PLN).
      - **Capital Flow & Savings**: Total annual deposits, withdrawals, and net savings rate.
      - **Extremes & Volatility**: Year's best day, worst day, and deepest underwater drawdown lake.
      - **MVPs & Anchors**: Top performing assets carrying gains vs biggest portfolio drags over the year.
      - **Trading Activity**: Total annual turnover, trade count, and dividend income collected.
      - **Retirement Milestone**: Annual target completion vs long-term retirement trajectory.
    - **Shareable Poster**: Exportable yearly wrap poster sized for social stories / chats, with privacy toggle for PLN amounts.
  - **Backend / Data Synthesis**:
    - Extend wrap generation (`wrap_generator.py`) or API endpoints to aggregate 12-month snapshot returns, cash flows, and annual commentary.

- [ ] **Learning Module: Financial Analysis & Reading Financial Reports with Real-World Examples**:
  - **Goal**: Build an accessible, beginner-friendly learning module in Roastfolio (e.g. dedicated guide section or interactive learning hub) explaining how to navigate corporate filings and analyze individual stocks from first principles.
  - **Structured Modules**:
    - **1. How to Read Financial Reports (Annual & Quarterly)**:
      - Where to source reports: SEC EDGAR (10-K, 10-Q) for US stocks, GPW ESPI/EBI / company IR pages for Polish equities, and investor presentation decks.
      - Key report sections: Management Discussion & Analysis (MD&A), auditor's opinion (clean vs qualified), and essential footnotes (accounting policy changes, contingent liabilities).
    - **2. The Big Three Financial Statements Deep-Dive**:
      - **Income Statement (Rachunek Zysków i Strat)**: Top-line revenue growth, Gross Margin, Operating Profit (EBIT / EBITDA), Net Income, and EPS. Differentiating organic recurring revenue from one-off non-operational gains.
      - **Balance Sheet (Bilans)**: Assets vs Liabilities & Equity. Liquidity checks (Working Capital, Current / Quick Ratio), debt maturity structure (short-term vs long-term obligations), and intangible assets / goodwill.
      - **Cash Flow Statement (Rachunek Przepływów Pieniężnych)**: Operating Cash Flow (OCF), CapEx, Free Cash Flow (FCF), and financing cash flows (dividends, share repurchases vs share dilution, debt issuance). Understanding why cash flow reflects business reality when net profit can be distorted.
    - **3. Essential Multiples & Valuation Ratios**:
      - Practical formula guide and benchmarks: P/E, P/B, EV/EBITDA, ROE, ROIC, Debt/Equity, Net Debt/EBITDA, and FCF Yield.
    - **4. Step-by-Step Practical Example**:
      - Live walkthrough using an actual company's annual/quarterly filing (e.g. XTB or Dino Polska on GPW / Apple or Microsoft globally): locating numbers in the raw PDF/Excel, computing the key ratios by hand, and interpreting competitive advantage / moat.
    - **5. Financial Red Flags & Sanity Checks**:
      - Warning signs: Divergence between Net Profit and Operating Cash Flow, aggressive capitalization of expenses, deteriorating operating margins, customer/supplier concentration, and imminent debt refinancing walls.
