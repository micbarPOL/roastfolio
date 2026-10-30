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
