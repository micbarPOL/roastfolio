# Project TODOs

## General / Bug Fixes

- [ ] **Fix mWIG40 Table Disappearing Data**:
  - **Symptom**: The monthly returns table data for `mWIG40` is intermittently disappearing and showing again. It should remain static and stable.
  - **Context**: The `generate_returns_data()` function in `update-prices.py` parses `src/data/myfund.pl_Emerytura_StopaZwrotuWOkresach.csv` and merges it with existing hand-corrected values. We need to investigate why these values toggle or disappear and ensure the data loads and remains static in the frontend.
