# Roastfolio Template Bank System

This document outlines the architecture and behavior of the Roastfolio Template Bank system, which provides deterministic, randomized commentary to users without requiring an expensive or slow AI call for every dashboard visit.

## 1. Overview
The template bank consists of parameterized JSON objects (`lambda/roast_templates.json`) loaded at runtime. The `template_bank.py` module is responsible for filtering, evaluating cooldowns, applying fallbacks, and rendering these templates into a standard `Daily Roast v2` format.

## 2. Template Schema
Each template follows this JSON structure:
```json
{
  "templateId": "gen_USER_NEGATIVE_BENCHMARK_POSITIVE_sarcastic_1_66493f81",
  "scenarioKey": "USER_NEGATIVE_BENCHMARK_POSITIVE",
  "tone": "roast",
  "intensity": "sarcastic",
  "messageAngle": "NO_CHANGE",
  "cooldownDays": 14,
  "titleTemplate": "Wow, Much Returns",
  "messageTemplate": "In a stunning twist, your portfolio reflects your personality because the market is up {{benchmarkReturnPercent}}% but you are down {{portfolioReturnPercent}}%. Keep up the mediocrity.",
  "mainReasonTemplate": "The market is up {{benchmarkreturnpercent}}% but you are down {{portfolioreturnpercent}}%",
  "suggestedFocusTemplate": "Review your no change",
  "requires": [] // Optional placeholders that must exist in data
}
```

## 3. Supported Scenario Keys
Templates are heavily segmented by market scenarios. The engine classifies the user's data into one of the following:

### Common Scenarios
- `BOTH_NEGATIVE_USER_BETTER`
- `BOTH_NEGATIVE_USER_WORSE`
- `BOTH_POSITIVE_USER_BETTER`
- `BOTH_POSITIVE_USER_WORSE`
- `USER_POSITIVE_BENCHMARK_NEGATIVE`
- `USER_NEGATIVE_BENCHMARK_POSITIVE`
- `BOTH_FLAT`

### Performance Margin
- `USER_OUTPERFORMED_BY_SMALL_MARGIN`
- `USER_OUTPERFORMED_BY_MEDIUM_MARGIN`
- `USER_OUTPERFORMED_BY_LARGE_MARGIN`
- `USER_UNDERPERFORMED_BY_SMALL_MARGIN`
- `USER_UNDERPERFORMED_BY_MEDIUM_MARGIN`
- `USER_UNDERPERFORMED_BY_LARGE_MARGIN`

### Account Status
- `NEW_ATH_DAY`
- `NEAR_ATH`
- `DRAWDOWN_MILD`
- `DRAWDOWN_SIGNIFICANT`
- `DRAWDOWN_SEVERE`

### Asset Specific
- `BEST_ASSET_CARRIED_PORTFOLIO`
- `WORST_ASSET_DRAGGED_PORTFOLIO`

### User Behavior
- `DEPOSIT_POSITIVE_BEHAVIOR`
- `WITHDRAWAL_DETECTED`
- `NO_MEANINGFUL_CHANGE`

### Monthly Aggregations
- `MONTHLY_BOTH_POSITIVE_USER_BETTER`
- `MONTHLY_BOTH_POSITIVE_USER_WORSE`
- `MONTHLY_BOTH_NEGATIVE_USER_BETTER`
- `MONTHLY_BOTH_NEGATIVE_USER_WORSE`
- `MONTHLY_USER_POSITIVE_BENCHMARK_NEGATIVE`
- `MONTHLY_USER_NEGATIVE_BENCHMARK_POSITIVE`
- `MONTHLY_FLAT`

## 4. Supported Placeholders
Placeholders are injected natively into templates. Ensure your templates only utilize the following variables:
- `{{portfolioReturnPercent}}`
- `{{portfolioDailyReturnAmount}}`
- `{{benchmarkReturnPercent}}`
- `{{relativePerformancePercent}}`
- `{{monthlyReturnPercent}}`
- `{{benchmarkMonthlyReturnPercent}}`
- `{{benchmarkName}}`
- `{{dailyBestAsset}}`
- `{{dailyWorstAsset}}`
- `{{largestWalletMover}}`
- `{{totalPortfolioValue}}`
- `{{currentDrawdownFromATH}}`
- `{{depositStreak}}`
- `{{withdrawalFreeStreak}}`
- `{{currency}}`
- `{{athDistancePercent}}`
- `{{walletName}}`

If a template defines `requires: ["currentDrawdownFromATH"]`, it will be skipped entirely if the user data payload lacks that field.

## 5. How Cooldown and Recent Template Exclusion Works
To prevent repetitive messaging, the engine tracks the past 30 days of roasts for each user.
1. **Cooldown Tracking**: A template's `cooldownDays` specifies how long it is ineligible after being used.
2. **Title Exclusivity**: If the user has seen the title `Wow, Much Returns` in their last 5 interactions, all templates sharing that title are excluded to ensure variety.

## 6. How Fallback Selection Works
If no template perfectly matches the user's `scenarioKey`, `intensity`, and `messageAngle`, the `template_bank.py` algorithm gracefully falls back using a cascade model:

1. **Exact Match**: Tries to match all criteria while avoiding any recently used titles.
2. **Drop Angle**: Drops `messageAngle` requirement.
3. **Drop Intensity**: Drops `intensity` requirement.
4. **Drop Tone**: Drops all constraints except the base `tone`.
5. **No Unique Titles**: If all the above fail (e.g., the user has exhausted all unique titles for this scenario), it repeats the cascade but ignores title exclusivity rules.
6. **AI Retry**: If even the final fallback yields nothing, it calls the AI to generate a message on-the-fly.

## 7. How to Add a New Template
1. Open `lambda/generate_templates.py`.
2. Add any new vocabulary (titles, snippets, etc.) to the `VOCAB` or `SCENARIO_CONTEXTS` dictionaries.
3. Run the generator script: `python3 lambda/generate_templates.py`
4. This script rebuilds `lambda/roast_templates.json` with the new combinations while maintaining test integrity and required uniqueness validations.
