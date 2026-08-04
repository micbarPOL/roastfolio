from datetime import datetime, timezone

def hasMeaningfulChangeSinceLastRoast(currentSnapshot: dict, lastSnapshot: dict, thresholds: dict = None) -> bool:
    """
    Checks if there has been a meaningful change since the last visit.
    """
    if not lastSnapshot:
        return True
        
    if thresholds is None:
        thresholds = {
            "portfolioReturnDiff": 0.10,
            "benchmarkReturnDiff": 0.10,
            "relativePerfDiff": 0.15,
            "portfolioValueDiffPct": 0.10,
            "drawdownDiff": 1.0
        }
        
    # Portfolio value / return
    current_value = currentSnapshot.get('totalPortfolioValue')
    last_value = float(lastSnapshot.get('totalPortfolioValue', 0)) if lastSnapshot.get('totalPortfolioValue') is not None else None
    
    if current_value is not None and last_value is not None and last_value > 0:
        value_change_pct = abs((current_value - last_value) / last_value) * 100
        if value_change_pct >= thresholds["portfolioValueDiffPct"]:
            return True
            
    current_port_ret = currentSnapshot.get('dailyChangePct', currentSnapshot.get('portfolioReturnPercent', 0))
    last_port_ret = float(lastSnapshot.get('portfolioReturnPercent', current_port_ret)) if lastSnapshot.get('portfolioReturnPercent') is not None else current_port_ret
    if abs(current_port_ret - last_port_ret) >= thresholds["portfolioReturnDiff"]:
        return True
        
    # Benchmark return
    current_bench = currentSnapshot.get('benchmark_return', currentSnapshot.get('benchmarkReturnPercent', 0))
    last_bench = float(lastSnapshot.get('benchmarkReturnPercent', current_bench)) if lastSnapshot.get('benchmarkReturnPercent') is not None else current_bench
    if abs(current_bench - last_bench) >= thresholds["benchmarkReturnDiff"]:
        return True
        
    # Relative performance
    current_rel = currentSnapshot.get('relative_performance', currentSnapshot.get('relativePerformancePercent', 0))
    last_rel = float(lastSnapshot.get('relativePerformancePercent', current_rel)) if lastSnapshot.get('relativePerformancePercent') is not None else current_rel
    if abs(current_rel - last_rel) >= thresholds["relativePerfDiff"]:
        return True
        
    # ATH Status
    current_ath = currentSnapshot.get('isAth', False)
    last_ath = lastSnapshot.get('isNewATH', lastSnapshot.get('isAth', False))
    if current_ath != last_ath:
        return True
        
    # Best/Worst Asset changes
    current_best_asset = currentSnapshot.get('best_asset', currentSnapshot.get('dailyBestAsset', currentSnapshot.get('topAsset')))
    last_best_asset = lastSnapshot.get('dailyBestAsset', lastSnapshot.get('bestAsset', lastSnapshot.get('topAsset')))
    if current_best_asset and last_best_asset and current_best_asset != last_best_asset:
        return True
    
    current_worst_asset = currentSnapshot.get('worst_asset', currentSnapshot.get('dailyWorstAsset'))
    last_worst_asset = lastSnapshot.get('dailyWorstAsset', lastSnapshot.get('worstAsset'))
    if current_worst_asset and last_worst_asset and current_worst_asset != last_worst_asset:
        return True
        
    # Drawdown threshold changed
    current_dd = currentSnapshot.get('drawdownPct', currentSnapshot.get('currentDrawdownFromATH', 0))
    last_dd = float(lastSnapshot.get('currentDrawdownFromATH', current_dd)) if lastSnapshot.get('currentDrawdownFromATH') is not None else current_dd
    if abs(current_dd - last_dd) >= thresholds["drawdownDiff"]:
        return True
        
    return False

def determine_commentary_mode(current_snapshot: dict, last_roast: dict, benchmark_snapshot: dict = None, current_time: datetime = None) -> str:
    """
    Determines the intraday commentary mode based on the current snapshot and the last roast today.
    """
    if benchmark_snapshot is None:
        benchmark_snapshot = {}
    if current_time is None:
        current_time = datetime.now(timezone.utc)
        
    # If no roast today, it's the first visit
    if not last_roast:
        return "OPENING_CHECK"
        
    # Check if we are near market close (e.g., after 20:00 UTC)
    if current_time.hour >= 20:
        last_time_str = last_roast.get('createdAt')
        if last_time_str:
            try:
                last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
                if last_time.hour < 20:
                    return "CLOSING_RECAP"
            except ValueError:
                pass
                
    # Normalize current snapshot fields for the new meaningful change function
    normalized_current = dict(current_snapshot)
    if benchmark_snapshot:
        normalized_current['benchmark_return'] = benchmark_snapshot.get('dailyChangePct', benchmark_snapshot.get('benchmarkReturnPercent', 0))
        normalized_current['relative_performance'] = normalized_current.get('dailyChangePct', 0) - normalized_current['benchmark_return']
        
    if not hasMeaningfulChangeSinceLastRoast(normalized_current, last_roast):
        return "NO_CHANGE"
        
    # Calculate deltas for volatile classifications
    current_value = current_snapshot.get('totalPortfolioValue')
    last_value = float(last_roast.get('totalPortfolioValue', 0)) if last_roast.get('totalPortfolioValue') is not None else None
    
    if current_value is not None and last_value is not None and last_value > 0:
        value_change_pct = abs((current_value - last_value) / last_value) * 100
    else:
        value_change_pct = 0.0

    current_rel_perf = normalized_current.get('relative_performance')
    last_rel_perf = float(last_roast.get('relativePerformancePercent', 0)) if last_roast.get('relativePerformancePercent') is not None else None
    
    # Check for benchmark reversal
    if current_rel_perf is not None and last_rel_perf is not None:
        if (last_rel_perf > 0 and current_rel_perf < 0) or (last_rel_perf < 0 and current_rel_perf > 0):
            return "BENCHMARK_REVERSAL"
            
    # Check for volatility spikes
    if value_change_pct >= 1.5:
        return "VOLATILITY_SPIKE"
        
    # Check for asset mover
    current_best_asset = current_snapshot.get('best_asset')
    last_best_asset = last_roast.get('bestAsset', last_roast.get('dailyBestAsset'))
    current_best_return = current_snapshot.get('best_asset_return')
    last_best_return = float(last_roast.get('bestAssetReturn', 0)) if last_roast.get('bestAssetReturn') is not None else None
    
    if current_best_asset and current_best_asset == last_best_asset and current_best_return is not None and last_best_return is not None:
        if abs(current_best_return - last_best_return) >= 2.0:
            return "ASSET_MOVER_UPDATE"
            
    if value_change_pct < 0.2:
        return "MICRO_MOVEMENT"
        
    return "MIDDAY_UPDATE"
