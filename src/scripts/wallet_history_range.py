from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable


def _to_series(snapshots: Iterable[dict[str, Any]]) -> list[list[int | float]]:
    series: list[list[int | float]] = []
    for snapshot in snapshots or []:
        raw_value = snapshot.get("portfolioValue")
        raw_date = str(snapshot.get("snapshotDate") or "")[:10]
        if raw_value is None or raw_date == "":
            continue
        try:
            value = float(raw_value)
            ts = datetime.strptime(raw_date, "%Y-%m-%d").timestamp() * 1000
        except (TypeError, ValueError):
            continue
        series.append([int(ts), value])
    return sorted(series, key=lambda item: item[0])


def build_wallet_value_history_window(snapshots: Iterable[dict[str, Any]], now: datetime | None = None):
    """Return the projected range window for the wallet value-history sparkline.

    Rules:
    - start at the latest of the oldest snapshot and 3 years ago
    - end at the supplied `now` timestamp
    - always keep the right edge at today so the sparkline does not end mid-chart
    """
    now_value = now or datetime.now()
    series = _to_series(snapshots)

    if not series:
        return {
            "series": [],
            "displaySeries": [],
            "rightEdge": int(now_value.timestamp() * 1000),
            "startBound": int(now_value.timestamp() * 1000),
        }

    right_edge = int(now_value.timestamp() * 1000)
    three_years_ago = now_value - timedelta(days=3 * 365)
    oldest_ts = series[0][0]
    start_bound = max(oldest_ts, int(three_years_ago.timestamp() * 1000))

    trimmed_series = [point for point in series if start_bound <= point[0] <= right_edge]
    fallback_before_start = next((point for point in reversed(series) if point[0] < start_bound), None)
    fallback_series = [[start_bound, fallback_before_start[1]], [right_edge, fallback_before_start[1]]] if fallback_before_start else []
    base_series = trimmed_series if trimmed_series else fallback_series
    safe_base_series = base_series if base_series else [[start_bound, series[-1][1]], [right_edge, series[-1][1]]]
    last_point = safe_base_series[-1]

    display_series = safe_base_series + [[right_edge, last_point[1]]] if last_point[0] < right_edge else safe_base_series

    return {
        "series": series,
        "displaySeries": display_series,
        "rightEdge": right_edge,
        "startBound": start_bound,
        "oldestTs": oldest_ts,
        "threeYearsAgo": int(three_years_ago.timestamp() * 1000),
    }
