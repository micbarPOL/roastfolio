import math

DEFAULT_THRESHOLDS = {
    "flat_margin": 0.1,
    "near_ath_margin": 2.0,
    "mild_drawdown_margin": 5.0,
    "significant_drawdown_margin": 15.0,
    "severe_drawdown_margin": 25.0,
    "carry_threshold": 1.5,
    "drag_threshold": -1.5,
    "dominance_ratio": 2.0
}


SCENARIO_PRIORITY = {
    "WITHDRAWAL_DETECTED": 100,
    "DEPOSIT_POSITIVE_BEHAVIOR": 90,
    "USER_NEGATIVE_BENCHMARK_POSITIVE": 85,
    "USER_POSITIVE_BENCHMARK_NEGATIVE": 85,
    "WORST_ASSET_DRAGGED_PORTFOLIO": 80,
    "BEST_ASSET_CARRIED_PORTFOLIO": 75,
    "DRAWDOWN_SEVERE": 72,
    "DRAWDOWN_SIGNIFICANT": 68,
    "NEW_ATH_DAY": 66,
    "DRAWDOWN_MILD": 62,
    "NEAR_ATH": 58,
    "BOTH_NEGATIVE_USER_WORSE": 56,
    "BOTH_NEGATIVE_USER_BETTER": 54,
    "BOTH_POSITIVE_USER_BETTER": 54,
    "BOTH_POSITIVE_USER_WORSE": 52,
    "USER_FLAT_BENCHMARK_MOVED": 48,
    "BENCHMARK_FLAT_USER_MOVED": 48,
    "USER_UNDERPERFORMED_BY_LARGE_MARGIN": 44,
    "USER_OUTPERFORMED_BY_LARGE_MARGIN": 42,
    "USER_UNDERPERFORMED_BY_MEDIUM_MARGIN": 38,
    "USER_OUTPERFORMED_BY_MEDIUM_MARGIN": 36,
    "USER_UNDERPERFORMED_BY_SMALL_MARGIN": 34,
    "USER_OUTPERFORMED_BY_SMALL_MARGIN": 32,
    "BOTH_FLAT": 25,
    "NO_MEANINGFUL_CHANGE": 10,
}

def classify_scenario(data: dict, thresholds: dict = None) -> dict:
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    else:
        thresholds = {**DEFAULT_THRESHOLDS, **thresholds}

    flat_m = thresholds["flat_margin"]
    port = data.get("portfolio_return", 0.0)
    bench = data.get("benchmark_return", 0.0)
    rel_perf = data.get("relative_performance", port - bench)

    matches = []

    # Helper to add scenarios
    def add_match(key, group, outcome, severity, novelty, reason):
        matches.append({
            "scenarioKey": key,
            "scenarioGroup": group,
            "outcomeType": outcome,
            "severity": severity,
            "noveltyPriority": novelty,
            "reason": reason
        })

    # Behavioral
    if data.get("recent_deposit"):
        add_match("DEPOSIT_POSITIVE_BEHAVIOR", "behavioral", "praise", 1, "high", "User recently deposited money.")
    if data.get("recent_withdrawal"):
        add_match("WITHDRAWAL_DETECTED", "behavioral", "roast", 3, "high", "Withdrawal detected.")

    # ATH and Drawdown
    drawdown = data.get("drawdown_pct", data.get("drawdownPct"))
    drawdown_present = drawdown is not None
    is_ath = data.get("is_new_ath", data.get("is_ath", False))

    if is_ath:
        add_match("NEW_ATH_DAY", "drawdown", "praise", 1, "high", "Portfolio reached a new all-time high.")
    elif drawdown_present:
        if drawdown < thresholds["near_ath_margin"]:
            add_match("NEAR_ATH", "drawdown", "neutral", 1, "low", "Portfolio is near all-time high.")
        elif drawdown < thresholds["mild_drawdown_margin"]:
            add_match("DRAWDOWN_MILD", "drawdown", "mixed", 2, "low", "Mild drawdown from ATH.")
        elif drawdown < thresholds["significant_drawdown_margin"]:
            add_match("DRAWDOWN_SIGNIFICANT", "drawdown", "roast", 3, "medium", "Significant drawdown from ATH.")
        else:
            add_match("DRAWDOWN_SEVERE", "drawdown", "roast", 5, "high", "Severe drawdown from ATH.")

    # Asset Contribution (in PLN / monetary gain or drag)
    best_contrib = data.get("best_asset_contribution", 0.0)
    second_best_contrib = data.get("second_best_asset_contribution")
    worst_drag = data.get("worst_asset_drag", 0.0)
    second_worst_drag = data.get("second_worst_asset_drag")
    holdings_count = data.get("holdings_count")
    dom_ratio = thresholds.get("dominance_ratio", 2.0)

    if holdings_count != 1:
        if best_contrib > 0:
            if second_best_contrib is None or second_best_contrib <= 0 or best_contrib >= dom_ratio * second_best_contrib:
                add_match("BEST_ASSET_CARRIED_PORTFOLIO", "asset", "mixed", 3, "medium", "One asset contributed disproportionately to gains.")

        if worst_drag < 0:
            if second_worst_drag is None or second_worst_drag >= 0 or abs(worst_drag) >= dom_ratio * abs(second_worst_drag):
                add_match("WORST_ASSET_DRAGGED_PORTFOLIO", "asset", "roast", 4, "high", "One asset dragged the portfolio down significantly.")

    # Flat conditions
    is_port_flat = abs(port) <= flat_m
    is_bench_flat = abs(bench) <= flat_m

    if is_port_flat and is_bench_flat:
        add_match("BOTH_FLAT", "absolute_performance", "neutral", 1, "low", "Both portfolio and benchmark are flat.")
    elif is_port_flat and not is_bench_flat:
        add_match("USER_FLAT_BENCHMARK_MOVED", "absolute_performance", "mixed", 2, "medium", "Portfolio is flat but benchmark moved.")
    elif not is_port_flat and is_bench_flat:
        add_match("BENCHMARK_FLAT_USER_MOVED", "absolute_performance", "mixed", 2, "medium", "Benchmark is flat but portfolio moved.")
    else:
        # Absolute Performance Direction (when neither is flat)
        if port < -flat_m and bench < -flat_m:
            if port > bench:
                add_match("BOTH_NEGATIVE_USER_BETTER", "absolute_performance", "mixed", 2, "low", "User lost money, but less than benchmark.")
            elif port < bench:
                add_match("BOTH_NEGATIVE_USER_WORSE", "absolute_performance", "roast", 3, "medium", "User lost more money than benchmark.")
        elif port > flat_m and bench > flat_m:
            if port > bench:
                add_match("BOTH_POSITIVE_USER_BETTER", "absolute_performance", "praise", 2, "medium", "Both positive, user outperformed.")
            elif port < bench:
                add_match("BOTH_POSITIVE_USER_WORSE", "absolute_performance", "mixed", 2, "low", "Both positive, user underperformed.")
        elif port > flat_m and bench < -flat_m:
            add_match("USER_POSITIVE_BENCHMARK_NEGATIVE", "absolute_performance", "praise", 3, "high", "User positive while benchmark is negative.")
        elif port < -flat_m and bench > flat_m:
            add_match("USER_NEGATIVE_BENCHMARK_POSITIVE", "absolute_performance", "roast", 4, "high", "User negative while benchmark is positive.")

    # Relative Performance Margins
    if rel_perf > flat_m:
        if rel_perf < 0.5:
            add_match("USER_OUTPERFORMED_BY_SMALL_MARGIN", "relative_performance", "praise", 1, "low", "Outperformed by small margin.")
        elif rel_perf < 1.0:
            add_match("USER_OUTPERFORMED_BY_MEDIUM_MARGIN", "relative_performance", "praise", 2, "medium", "Outperformed by medium margin.")
        else:
            add_match("USER_OUTPERFORMED_BY_LARGE_MARGIN", "relative_performance", "praise", 3, "high", "Outperformed by large margin.")
    elif rel_perf < -flat_m:
        if rel_perf > -0.5:
            add_match("USER_UNDERPERFORMED_BY_SMALL_MARGIN", "relative_performance", "mixed", 1, "low", "Underperformed by small margin.")
        elif rel_perf > -1.0:
            add_match("USER_UNDERPERFORMED_BY_MEDIUM_MARGIN", "relative_performance", "roast", 2, "medium", "Underperformed by medium margin.")
        else:
            add_match("USER_UNDERPERFORMED_BY_LARGE_MARGIN", "relative_performance", "roast", 4, "high", "Underperformed by large margin.")

    if not matches:
        add_match("NO_MEANINGFUL_CHANGE", "fallback", "neutral", 1, "low", "Nothing important happened.")

    # Priority mapping
    novelty_score = {"low": 1, "medium": 2, "high": 3}

    # Sort matches by business priority first, then novelty and severity.
    # This keeps scoreboard-style relative margins as useful secondary context
    # instead of letting them dominate the concrete story of the day.
    matches.sort(
        key=lambda x: (
            SCENARIO_PRIORITY.get(x["scenarioKey"], 0),
            novelty_score[x["noveltyPriority"]],
            x["severity"]
        ),
        reverse=True
    )

    primary = matches[0]
    secondary = [m["scenarioKey"] for m in matches[1:]]

    return {
        "scenarioKey": primary["scenarioKey"],
        "secondaryScenarioKeys": secondary,
        "scenarioGroup": primary["scenarioGroup"],
        "outcomeType": primary["outcomeType"],
        "severity": primary["severity"],
        "noveltyPriority": primary["noveltyPriority"],
        "reason": primary["reason"]
    }
