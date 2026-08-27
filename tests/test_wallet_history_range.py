from datetime import datetime, timedelta

from src.scripts.wallet_history_range import build_wallet_value_history_window


def test_wallet_history_starts_at_three_years_ago_or_oldest_snapshot_and_ends_today():
    now = datetime(2026, 8, 27, 12, 0, 0)
    snapshots = [
        {"portfolioValue": 100, "snapshotDate": "2023-01-01"},
        {"portfolioValue": 130, "snapshotDate": "2024-01-01"},
        {"portfolioValue": 150, "snapshotDate": "2025-01-01"},
        {"portfolioValue": 180, "snapshotDate": "2026-01-01"},
    ]

    result = build_wallet_value_history_window(snapshots, now)
    three_years_ago = now - timedelta(days=3 * 365)

    assert result["startBound"] >= int(three_years_ago.timestamp() * 1000)
    assert result["displaySeries"][-1][0] == int(now.timestamp() * 1000)
    assert all(ts <= int(now.timestamp() * 1000) for ts, _ in result["displaySeries"])


def test_wallet_history_keeps_older_history_but_still_forces_today_end():
    now = datetime(2026, 8, 27, 12, 0, 0)
    snapshots = [
        {"portfolioValue": 80, "snapshotDate": "2020-01-01"},
        {"portfolioValue": 95, "snapshotDate": "2021-01-01"},
        {"portfolioValue": 120, "snapshotDate": "2025-01-01"},
    ]

    result = build_wallet_value_history_window(snapshots, now)
    three_years_ago = now - timedelta(days=3 * 365)

    assert result["startBound"] >= int(three_years_ago.timestamp() * 1000)
    assert result["displaySeries"][-1][0] == int(now.timestamp() * 1000)
    assert result["displaySeries"][0][0] >= result["startBound"]
