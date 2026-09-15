# Monthly recap presentation

Summaries uses Editorial Bento with a compact native month picker, an understated
typographic r/ brand accent and no circular seal. Return calculations remain in
the monthly-wrap generator; the browser only positions supplied values and
computes descriptive percentage-point comparisons and target ratios. Wallet and
AVCO details remain available on demand. No backend changes are needed here.

## Main journey: dated returns, not account balance

The primary plot consumes `journey` exactly as supplied:

- `benchmark_id`, `benchmark_name`, `benchmark_currency` identify the comparison.
- `points: [{date, portfolio_pct: number|null, benchmark_pct: number|null}]` supplies
	cumulative portfolio TWR and benchmark returns. Portfolio is solid green;
	benchmark is dashed lavender. Both use one percentage axis and elapsed-date X axis.
- `start_date`, `end_date` disclose the portfolio boundaries; these can include the
	first snapshot of the next month. No month-end date is invented by the UI.
- `benchmark_return_pct`, `benchmark_start_price_date`, `benchmark_end_price_date`
	display the actual boundary return and quote dates, including as-of quotes.

Dates are displayed as stored ISO strings. Each series splits independently at
null observations; an isolated observation is a dot, not a fabricated line.
Missing dated history shows unavailable text, never a nominal-value fallback.
The keyboard-operable scrubber reads actual stored dates and values, including
“No data”. Deposits and withdrawals do not affect chart geometry.

Benchmark returns are explicitly in their native currency, not converted to PLN.
MSCI World is a proxy; the IWDA listing is quoted in EUR, not fund-base USD.
Deepest drawdown, month-end drawdown and its change remain compact metrics;
the legacy drawdown lake is optional inside details, without inferred dates.

## Movers: one symmetric PLN scale

Both horizontal rows share the same width, zero at 50%, and domain `[-S, +S]`, where
`S = max(abs(month total), abs(leader), abs(anchor), 1)`. Positive values extend
right from zero and negative values left. Signed PLN labels remain visible.
A dashed marker on both rows and a labeled “Month total” reference show the
nominal monthly result net of external flows. The common-scale legend describes
the endpoints and distinguishes the full extent from the month total.

**The leader is not always full length.** If the month total dominates, both
contributions are shorter. If a contribution exceeds the net month, it defines
the extent and the month marker moves inward; there is no clipping. Zero-net
months and two contributions of the same sign still use the same symmetric axis.
Missing contributions do not draw a fake zero bar; missing month totals do not
draw a reference marker.

## Bigger picture and trading activity

`market_context` is an array of `{id, name, currency, return_pct: number|null,
start_price_date, end_price_date}`. The five stable rows are world / `MSCI_WORLD`
(proxy), US / `SP500`, US technology / `NASDAQ`, Europe / `DAX`, Europe / `FTSE100`.
Each compares the supplied monthly portfolio TWR with a native-currency market
return in plain English, or says comparison unavailable. Market quote dates are
always shown; a mismatch with portfolio boundaries is explicitly flagged.
Calendar close-to-close returns are not silently treated as identical to the
portfolio snapshot period. Existing seasonal statistics remain below the markets.

“Trading activity” replaces the diary/process panel. It consumes only
`trading_activity`: `buy_total_pln`, `sell_total_pln`, `turnover_pln`,
`dividend_total_pln`, `transaction_count`, and
`largest_transactions: [{date, type: 'BUY'|'SELL', ticker, value_pln}]`.
Supplied settled values and transaction order are preserved. Turnover is described
as BUY + SELL volume, not return; dividends are separate and shown when nonzero.
Missing fields show unavailable text. Explicit zero counts show no trades, while
an absent list with a positive/unknown count says transaction details unavailable.

## Target: one signed track

Large rounded progress text uses `actual_nominal_gain_pln / monthly_target_nominal_pln`.
The old ring and duplicate progress bar are removed. A single track shares the
PLN scale `S = max(target, abs(actual), 1)` with an explicitly labeled target marker.
For nonnegative actuals the domain is `[0, S]`: target 100 and actual 300 place the
marker at one third, with 300% displayed. For losses the domain is `[-S, +S]`, zero
is centered and the actual fill extends left. Missing actual/valid positive target
does not produce a progress track. AVCO details remain independent of target setup.

## Sharing now

`monthly-audit-share.js` owns a versioned, allowlisted `buildModel(item, options)`
contract and a `drawPoster(canvas, model)` renderer. The 1080 × 1350 PNG is a designed
share card, not a screenshot of the entire account. Rendering uses native Canvas
with system fonts and no remote images, libraries, CORS dependencies or uploads.

- Preview before sharing; hide PLN amounts by default on every opening.
- Percent returns and drawdowns remain visible, as explicitly disclosed.
- Never include user identity, holdings, balances, wallet names or diary content.
- The private model contains no nominal amount, not merely an invisible label.
- Prepare a File in advance so Web Share runs within a fresh user gesture.
- Feature-detect file sharing; always offer PNG download. Cancellation is not an error.
- Invalidate pending image generation when toggling privacy or closing the modal.
- Native dialog supplies focus trapping, Escape and focus restoration on close.

The poster intentionally includes only the return, optional nominal gain and the
stored drawdown detail (explicitly titled “DRAWDOWN DETAIL”, not the main TWR
journey). No synthetic comparison chart, market data, transaction tickers or new
identity fields enter the export. The cover uses a subtle diagonal rule, no rings.
The full report stays inside the authenticated application.

## Future email (not implemented or scheduled)

Use the schemaVersion 1 presentation fields as a contract for an email-safe HTML
template and/or an attached PNG. A backend adapter will need to implement this
contract; the browser module is not a server-side email renderer. Keep delivery
separate from report generation. Do not call SES on viewing or sharing a recap.

Before enabling delivery: authenticated recipient selection, explicit consent,
privacy preference, idempotency by user/period, retry handling, unsubscribe controls
for scheduled mail, and tests for HTML escaping and exclusion of private fields.
The existing SES module is not connected by this change. No inactive email button
is shown in the UI.

## Data honesty

Legacy drawdowns use only the stored series, not an invented start/end curve.
Missing observations split the lake in details and the exported plot; missing
series show unavailable text. No dates are inferred for these legacy observations.
The main dated TWR plot and legacy drawdown detail are intentionally different.

The localhost-only inline mock provides three synthetic editions: June gains with
no trading, July losses with an unavailable FTSE return and a benchmark gap, and
August gains with an offsetting leader/anchor pair plus goal 100 / actual 300.
They include next-month portfolio boundaries, differing market calendar dates,
native currencies, and reconciled trading and external-flow totals. These are
explicit demo values, not a production data fallback. Cache versions are bumped
for recap CSS/JS and existing manage/profile assets without editing those modules.

## Validation

The standalone browser fixture at `tests/monthly-audit.browser.html` loads real
production CSS/JS with synthetic data and no authentication or API requests. It
checks the presentation model, privacy and renderer; inspect at 390px/1440px and
both themes. Python UI contracts also check asset wiring and export safeguards.

`tests/test_monthly_audit_browser.py` runs repeatable headless checks using the
optional development dependency `playwright` (with its Chromium runtime). Tests
cover 360–1440px, both themes, real PNG download bytes/dimensions, explicit amount
opt-in, privacy reset, no share-time network requests, missing/sparse histories,
long amounts and focus restoration. New behavioral tests measure common mover
zero/scale and month markers, over-net contributions, positive/negative/zero goals,
nonuniform stored dates, independent gaps, deposit-invariant return geometry,
missing benchmark and trading data, calendar/currency disclosure, escaping and
all three localhost mock schemas. Screenshots cover all three editions as well
as dark/light desktop/mobile recaps and share dialogs.
Native Web Share is stubbed to verify File
delivery within user activation, cancellation and rejection; actual OS share
targets still require a device smoke test. Screenshots are written under `tmp/`.