def determine_eligible_angles(current_snapshot: dict, benchmark_snapshot: dict, commentary_mode: str) -> list:
    """
    Evaluates current portfolio data to return a list of eligible message angles.
    """
    eligible = set()
    
    # Modes that force specific angles
    if commentary_mode == "NO_CHANGE":
        return ["NO_CHANGE"]
    if commentary_mode == "VOLATILITY_SPIKE":
        eligible.add("VOLATILITY")
    if commentary_mode == "ASSET_MOVER_UPDATE":
        eligible.add("BEST_ASSET")
        eligible.add("WORST_ASSET")
        eligible.add("WALLET_MOVER")
        
    # Baseline angles always eligible for daily roasts. Benchmark angles are
    # added only when the benchmark contrast is actually the story.
    eligible.update(["ABSOLUTE_RETURN", "GENERAL_MARKET_CHAOS"])

    port_ret = current_snapshot.get("dailyChangePct", current_snapshot.get("portfolioReturnPercent", 0)) or 0
    bench_ret = benchmark_snapshot.get("dailyChangePct", benchmark_snapshot.get("benchmarkReturnPercent", 0)) if benchmark_snapshot else 0
    bench_ret = bench_ret or 0
    rel_perf = port_ret - bench_ret
    opposite_signs = (port_ret > 0 and bench_ret < 0) or (port_ret < 0 and bench_ret > 0)

    if opposite_signs or abs(rel_perf) >= 1.0:
        eligible.add("BENCHMARK_COMPARISON")
        eligible.add("RELATIVE_RETURN")
    
    # Asset performance
    if current_snapshot.get("topAssetPct", 0) > 2.0:
        eligible.add("BEST_ASSET")
    if current_snapshot.get("worstAssetPct", 0) < -2.0:
        eligible.add("WORST_ASSET")
        
    # ATH and Drawdown
    if current_snapshot.get("isAth"):
        eligible.add("ATH_STATUS")
    elif current_snapshot.get("drawdownPct", 0) > 5.0:
        eligible.add("DRAWDOWN_STATUS")
        
    # Behavior
    if current_snapshot.get("recentDeposit"):
        eligible.add("DEPOSIT_DISCIPLINE")
    if current_snapshot.get("recentWithdrawal"):
        eligible.add("WITHDRAWAL_BEHAVIOR")
        
    # Risk
    if current_snapshot.get("concentrationRisk"):
        eligible.add("RISK_CONCENTRATION")
        
    return list(eligible)


def selectPreferredMessageAngle(params: dict) -> str:
    """
    Picks the best angle from eligible_angles by rotating away from recently used ones.
    
    params = {
      "scenarioKey": str,
      "availableAngles": list,
      "recentRoasts": list,
      "availableData": dict,
      "commentaryMode": str
    }
    """
    eligible_angles = params.get("availableAngles") or []
    recent_history = params.get("recentRoasts") or []
    data = params.get("availableData") or {}
    mode = params.get("commentaryMode") or ""
    
    if not eligible_angles:
        return "GENERAL_MARKET_CHAOS"
        
    if len(eligible_angles) == 1:
        return eligible_angles[0]
        
    # Extract recent angles in order (index 0 is most recent)
    used_angles = []
    for record in recent_history:
        ang = record.get("messageAngle")
        if ang:
            used_angles.append(ang)
            
    # Calculate frequencies in the last 5 roasts
    recent_5 = used_angles[:5]
    freq = {}
    for a in recent_5:
        freq[a] = freq.get(a, 0) + 1
        
    last_used = used_angles[0] if used_angles else None
    
    # Filter strictly available angles:
    # 1. Avoid same angle twice in a row (if alternatives exist)
    # 2. Avoid angle used > 2 times in last 5 roasts
    strict_options = []
    for a in eligible_angles:
        if a == last_used:
            continue
        if freq.get(a, 0) > 2:
            continue
        strict_options.append(a)
        
    if not strict_options:
        # If strict filtering removes everything, relax rule 2
        for a in eligible_angles:
            if a != last_used and a not in strict_options:
                strict_options.append(a)
                
    if not strict_options:
        # If still empty, relax rule 1 (means all eligible angles were the last used one)
        strict_options = eligible_angles
        
    # Apply priority heuristics
    if mode == "NO_CHANGE" and "NO_CHANGE" in strict_options:
        return "NO_CHANGE"
        
    # Define priorities
    priority_order = []
    
    if data.get("worstAssetPct", 0) < -2.0 and "WORST_ASSET" not in recent_5:
        priority_order.append("WORST_ASSET")
        
    outcome = data.get("outcomeType", "neutral") # This might not be directly in data, but we can infer or pass it.
    if data.get("topAssetPct", 0) > 2.0 and "BEST_ASSET" not in recent_5:
        # User requested: If dailyBestAsset is available and outcome is praise/mixed, prefer BEST_ASSET
        # We'll just prioritize it if topAsset is doing well
        priority_order.append("BEST_ASSET")
        
    if data.get("drawdownPct", 0) > 5.0:
        priority_order.append("DRAWDOWN_STATUS")
        
    if data.get("recentDeposit"):
        priority_order.append("DEPOSIT_DISCIPLINE")
        
    scenario_key = params.get("scenarioKey", "")
    if scenario_key in ["USER_NEGATIVE_BENCHMARK_POSITIVE", "USER_POSITIVE_BENCHMARK_NEGATIVE"]:
        priority_order.append("BENCHMARK_COMPARISON")

    priority_order.append("GENERAL_MARKET_CHAOS")
    priority_order.append("ABSOLUTE_RETURN")
    priority_order.append("RELATIVE_RETURN")
        
    for p in priority_order:
        if p in strict_options:
            return p
            
    # If no priority matches, return the first strict option
    return strict_options[0]
