# Roast Engine Gauge Comments Plan

Current date: 2026-08-03

## Goal

Fix the daily comment shown under the dashboard gauge so it does two things well:

1. Picks the right scenario instead of falling into broad/default buckets.
2. Sounds like Roastfolio again: short, funny, user-setting aware, and not a text duplicate of the numbers already visible on the gauge.

## Current Findings

### 1. Scenario classification is polluted by a broad ATH/drawdown default

Relevant files:

- `lambda/roast_engine.py`
- `lambda/scenario_classifier.py`
- `tests/test_scenario_classifier.py`

`generate_daily_roast()` passes this data into the classifier:

```py
{
    "is_ath": current_snapshot.get("isAth", False),
    "portfolio_return": ...,
    "benchmark_return": ...
}
```

But `classify_scenario()` reads different keys:

```py
drawdown = data.get("drawdown_pct", 0.0)
is_ath = data.get("is_new_ath", False)
```

Because `drawdown_pct` defaults to `0.0`, the classifier treats missing drawdown data as "near ATH". That means `NEAR_ATH` is added to almost every classification, including flat days that do not actually provide drawdown context.

Observed locally:

```text
{portfolio_return: 0.05, benchmark_return: 0.05}
=> primary: NEAR_ATH
=> secondary: BOTH_FLAT
```

This is probably the broad first-condition problem. It is not always the primary scenario, but it contaminates the candidate list and can win when the real day signal is weak.

### 2. Relative-performance scenarios often become primary too aggressively

For same-direction days, the classifier can pick a relative scenario as primary even when the absolute scenario is easier to understand and more useful for comment selection.

Observed locally:

```text
{portfolio_return: -1.0, benchmark_return: -2.0}
=> primary: USER_OUTPERFORMED_BY_LARGE_MARGIN
=> secondary: BOTH_NEGATIVE_USER_BETTER, NEAR_ATH

{portfolio_return: 1.0, benchmark_return: 2.0}
=> primary: USER_UNDERPERFORMED_BY_LARGE_MARGIN
=> secondary: BOTH_POSITIVE_USER_WORSE, NEAR_ATH
```

The user already sees portfolio return and benchmark comparison on the gauge, so primary comments should not default to restating that comparison unless the benchmark contrast is the actual story.

### 3. The angle selector over-invites benchmark comments

`angle_selector.determine_eligible_angles()` always adds:

```py
BENCHMARK_COMPARISON
ABSOLUTE_RETURN
RELATIVE_RETURN
GENERAL_MARKET_CHAOS
```

Then `selectPreferredMessageAngle()` explicitly prioritizes `BENCHMARK_COMPARISON` if it was not recently used.

This encourages comments that say "you returned X" or "benchmark did Y" even when the UI already says that. The engine needs richer angles: asset drama, behavior, concentration, drawdown, ATH, inactivity, market chaos, and user voice.

### 4. Templates are structurally repetitive and too numeric

`lambda/roast_templates.json` contains many visible `messageTemplate` strings that repeat these placeholders:

- `{{portfolioReturnPercent}}`
- `{{benchmarkReturnPercent}}`
- `{{relativePerformancePercent}}`

Examples of the current pattern:

```text
Your {{portfolioReturnPercent}}% return...
A {{portfolioReturnPercent}}% day...
You returned {{portfolioReturnPercent}}%...
```

Those are boring under the gauge because the gauge already provides the numbers. The comment should interpret the situation, not transcribe the dial.

## Proposed Product Behavior

### Comment rules

Daily gauge comments should:

- Be one crisp sentence by default.
- Avoid repeating portfolio return, benchmark return, and relative performance in visible text.
- Use numbers only when the number is the joke or the user could not infer it from the gauge.
- Match `settings.roastIntensity`:
  - `gentle`: supportive, lightly funny, no insult framing.
  - `sarcastic`: dry and witty, default Roastfolio voice.
  - `brutal`: sharper, still about investing behavior, not identity.
  - `degen`: chaotic internet-finance style, but no reckless advice.
- Prefer behavior and narrative over scoreboard recap.
- Still save structured `mainReason`, `suggestedFocus`, `scenarioKey`, and telemetry for debugging/history, even if the visible comment is playful.

### Scenario priority proposal

Use this priority order for the primary daily scenario:

1. User behavior events: withdrawal, deposit discipline, concentration change, no-panic behavior.
2. Strong opposite-sign market outcomes: user negative while benchmark positive, user positive while benchmark negative.
3. Large absolute portfolio move: severe positive/negative day, volatility spike, asset drag/carry.
4. ATH/drawdown status, only when real ATH/drawdown data is present.
5. Same-direction absolute outcomes: both positive/both negative user better/worse.
6. Relative-performance margin, mainly as secondary context unless it is extreme or user settings prefer benchmark commentary.
7. Flat/no meaningful change.

This keeps benchmark comparison available, but prevents it from dominating every ordinary day.

## Development Plan

### Phase 1: Fix scenario input contract

Implementation options:

1. Preferred: normalize classifier input in `lambda/roast_engine.py`.

```py
data = {
    "portfolio": current_snapshot,
    "benchmark": benchmark_snapshot,
    "is_new_ath": current_snapshot.get("isAth", False),
    "drawdown_pct": current_snapshot.get("drawdownPct"),
    "portfolio_return": ...,
    "benchmark_return": ...,
    "recent_deposit": current_snapshot.get("recentDeposit"),
    "recent_withdrawal": current_snapshot.get("recentWithdrawal"),
    "best_asset_contribution": current_snapshot.get("topAssetPct"),
    "worst_asset_drag": current_snapshot.get("worstAssetPct"),
}
```

2. Also make `scenario_classifier.py` accept aliases defensively:

```py
is_ath = data.get("is_new_ath", data.get("is_ath", False))
```

Acceptance tests:

- `isAth=True` from a snapshot can produce `NEW_ATH_DAY`.
- A missing `drawdownPct` does not produce `NEAR_ATH`.
- A flat day without drawdown data produces `BOTH_FLAT` or `NO_MEANINGFUL_CHANGE`, not `NEAR_ATH`.

### Phase 2: Make drawdown classification explicit

Change `scenario_classifier.py` so drawdown scenarios run only when drawdown data exists.

Current behavior:

```py
drawdown = data.get("drawdown_pct", 0.0)
if drawdown < near_ath_margin:
    add_match("NEAR_ATH", ...)
```

Proposed behavior:

```py
drawdown_present = data.get("drawdown_pct") is not None
if is_ath:
    add_match("NEW_ATH_DAY", ...)
elif drawdown_present:
    # classify NEAR_ATH / DRAWDOWN_MILD / ...
```

Acceptance tests:

- `classify_scenario({"portfolio_return": 0.05, "benchmark_return": 0.05})` primary is not `NEAR_ATH`.
- `classify_scenario({"drawdown_pct": 1.0})` can still produce `NEAR_ATH`.
- `classify_scenario({"drawdown_pct": 30.0})` can still produce `DRAWDOWN_SEVERE`.

### Phase 3: Rebalance primary scenario selection

Replace simple novelty/severity sorting with a clearer score that includes scenario group priority.

Suggested scoring fields:

- `groupPriority`
- `noveltyPriority`
- `severity`
- `specificity`

Example group priority:

```py
GROUP_PRIORITY = {
    "behavioral": 70,
    "absolute_performance": 60,
    "asset": 55,
    "drawdown": 45,
    "relative_performance": 35,
    "fallback": 10,
}
```

Special case: opposite-sign absolute scenarios should outrank relative scenarios. Same-direction relative scenarios should usually remain secondary unless the relative gap is extreme.

Acceptance tests:

- `portfolio=-1, benchmark=-2` primary should be `BOTH_NEGATIVE_USER_BETTER` or another absolute/asset story, not automatic benchmark scoreboard text.
- `portfolio=1, benchmark=2` primary should be `BOTH_POSITIVE_USER_WORSE` unless benchmark commentary is explicitly selected.
- `portfolio=-2, benchmark=1` remains `USER_NEGATIVE_BENCHMARK_POSITIVE`.
- `portfolio=2, benchmark=-1` remains `USER_POSITIVE_BENCHMARK_NEGATIVE`.

### Phase 4: Stop benchmark angle from being the default voice

Change `angle_selector.py` so benchmark/relative angles are eligible but not baseline-preferred.

Proposed default angle pool:

```py
GENERAL_MARKET_CHAOS
ABSOLUTE_RETURN
```

Add contextual angles only when data supports them:

- `BEST_ASSET` if top asset moved enough.
- `WORST_ASSET` if worst asset moved enough.
- `ATH_STATUS` if `isAth` is true.
- `DRAWDOWN_STATUS` if real drawdown data is present and meaningful.
- `DEPOSIT_DISCIPLINE` / `WITHDRAWAL_BEHAVIOR` when those signals exist.
- `BENCHMARK_COMPARISON` only for opposite-sign days, large relative gaps, or explicit user preference.

Acceptance tests:

- Ordinary same-direction days do not always choose `BENCHMARK_COMPARISON`.
- Consecutive roasts rotate between angle families.
- Opposite-sign benchmark scenarios can still choose benchmark commentary.

### Phase 5: Add a visible-comment style guard

Add a small validator for visible message text before saving a template or accepting AI output.

Rules for daily gauge `message`:

- Reject if it contains `{{portfolioReturnPercent}}`, `{{benchmarkReturnPercent}}`, or `{{relativePerformancePercent}}` in visible text for normal gauge comments.
- Reject if it starts with repeated patterns like `You returned`, `A X% day`, `Your X% return`.
- Reject if message length is too long for the gauge area.
- Allow numeric placeholders in `mainReasonTemplate` and `suggestedFocusTemplate` because those are explanatory/debug fields, not the punchline.

Possible implementation:

- Add `template_bank.validate_visible_comment(template, context="daily_gauge")`.
- Use it in template import validation and optionally in runtime selection telemetry.

Acceptance tests:

- A template with `messageTemplate = "You returned {{portfolioReturnPercent}}%..."` is rejected for daily gauge context.
- A template with numbers only in `mainReasonTemplate` passes.

### Phase 6: Rewrite or regenerate the daily template bank by voice

Rewrite the highest-traffic daily scenarios first:

- `USER_NEGATIVE_BENCHMARK_POSITIVE`
- `BOTH_NEGATIVE_USER_WORSE`
- `BOTH_POSITIVE_USER_WORSE`
- `BOTH_POSITIVE_USER_BETTER`
- `NO_MEANINGFUL_CHANGE`
- `USER_FLAT_BENCHMARK_MOVED`
- `BENCHMARK_FLAT_USER_MOVED`
- `NEW_ATH_DAY`
- `DRAWDOWN_SIGNIFICANT`
- `WORST_ASSET_DRAGGED_PORTFOLIO`
- `BEST_ASSET_CARRIED_PORTFOLIO`

Template shape:

```json
{
  "scenarioKey": "BOTH_POSITIVE_USER_WORSE",
  "intensity": "sarcastic",
  "tone": "mixed",
  "messageAngle": "GENERAL_MARKET_CHAOS",
  "titleTemplate": "Technically Green",
  "messageTemplate": "You made money and still somehow gave the scoreboard a reason to clear its throat.",
  "mainReasonTemplate": "Portfolio was positive but lagged the benchmark.",
  "suggestedFocusTemplate": "Review what capped the upside today.",
  "structureFamily": "dry_observation",
  "metaphorCategory": "scoreboard"
}
```

Example voice targets:

```text
gentle:     Green day. A little less heroic than the index, but still a step forward.
sarcastic:  You made money and still found a way to look mildly supervised.
brutal:     Profit with benchmark envy. Impressive how you made green feel beige.
degen:      Portfolio green, index greener. The lobby won, you got participation loot.
```

### Phase 7: Optional user setting for comment personality

Current setting appears to be `settings.roastIntensity`. Keep that as the primary control for now.

If we want more control later, add a separate setting:

```json
"commentaryStyle": "coach" | "dry" | "chaos" | "minimal"
```

Then selection can combine:

- `roastIntensity`: how sharp the comment is.
- `commentaryStyle`: what kind of humor/motivation it uses.

Do not add this until the existing intensity mapping is respected consistently.

## Suggested First PR Scope

Keep the first implementation small:

1. Normalize classifier input keys in `roast_engine.py`.
2. Make drawdown classification require explicit drawdown data.
3. Add/adjust scenario classifier tests for flat day, ATH alias, and missing drawdown.
4. Lower benchmark angle priority in `angle_selector.py`.
5. Rewrite 20-30 templates across the most common daily scenarios to remove visible gauge-number repetition.

## Verification Plan

Automated:

```sh
python3 -m pytest tests/test_scenario_classifier.py tests/test_roast_engine.py tests/test_e2e_roast_engine.py
```

Manual dashboard checks:

- Flat day: comment should not talk about near ATH unless ATH/drawdown data is actually present.
- Positive but benchmark better: comment should be funny/mixed, not just "you returned X and benchmark returned Y".
- Negative while benchmark positive: roast should be sharper and scenario-specific.
- User switches `roastIntensity`: comment voice should visibly change.
- Repeated refreshes: no repeated title/message pattern unless `NO_CHANGE` mode deliberately reuses or lightens the comment.

## Open Decisions

1. Should same-direction underperformance use absolute scenario as primary and relative scenario as secondary by default?
2. Should benchmark commentary be opt-in, dramatically triggered, or just deprioritized?
3. Do we want the first rewrite to preserve the existing template count, or intentionally reduce to fewer but stronger templates?
4. Should `mainReason` and `suggestedFocus` remain hidden under the gauge, or be available in a details/debug area?
