# Proper Daily Change Calculation

The current "Daily Change" for portfolios is calculated by summing the daily price changes of all currently held assets. This is flawed because if you sell a holding today, its daily profit is lost from the sum; if you buy a holding today, its full daily return (from yesterday's close) is added to the sum.

## User Review Required

To properly calculate the exact portfolio daily change, we should use:
`Daily Change = Current Portfolio Value - Yesterday's Portfolio Value`

However, if you make a DEPOSIT or WITHDRAWAL today, that cash flow changes your Current Portfolio Value artificially. For example, if you deposit 10,000 PLN today, `Current Value - Yesterday Value` will show an artificial +10,000 PLN daily profit.

To fix this completely, the mathematically correct formula is:
`Daily Change = Current Portfolio Value - Yesterday's Portfolio Value - Net Deposits Today`

Do you want me to subtract today's Net Deposits (Deposits - Withdrawals) so that depositing cash doesn't artificially inflate your daily profit?

## Proposed Changes

### `lambda/handler.py`
#### [MODIFY] `lambda/handler.py`
- In `prices_handler`, load the latest snapshot for each portfolio using `snapshots.list_snapshots(user_id, pid, limit=1)`.
- If a snapshot exists, calculate `dailyChangePLN = current_total - snapshot["portfolioValue"]`.
- To adjust for deposits, query transactions from today (or since the snapshot date) and subtract `Net Deposits`.
- Do the same for the Summary portfolio.

## Verification Plan
### Automated Tests
- Run `tests/test_prices.py` (if exists) or local script.
- Verify `dailyChangePLN` equals `Current - Yesterday - Deposits`.

### Manual Verification
- Check the gauge and portfolio cards on the dashboard to ensure the daily change is accurate.
