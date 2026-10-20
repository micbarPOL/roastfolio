# Project TODOs

## General / Bug Fixes

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
