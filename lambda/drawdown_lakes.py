"""Drawdown lake analysis utilities.

This module computes daily high-water marks and drawdown series, then groups
contiguous underwater periods (drawdown < 0) into "lakes".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class LakeSummary:
    lake_id: int
    start_date: str
    end_date: str
    is_open: bool
    peak_trough_depth_pct: float
    duration_days: int
    trough_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "lakeId": self.lake_id,
            "startDate": self.start_date,
            "endDate": self.end_date,
            "isOpen": self.is_open,
            "peakTroughDepthPct": self.peak_trough_depth_pct,
            "durationDays": self.duration_days,
            "troughDate": self.trough_date,
        }


class DrawdownLakeAnalyzer:
    """Analyze drawdown lakes from a daily portfolio value time series.

    Accepted inputs:
      - ``pd.Series`` with a DatetimeIndex where each value is portfolio value.
      - ``pd.DataFrame`` with a DatetimeIndex and a numeric ``value`` column
        (or a custom column passed via ``value_col``).
    """

    def __init__(self, value_col: str = "value"):
        self.value_col = value_col

    def analyze(self, data: pd.Series | pd.DataFrame) -> dict[str, Any]:
        """Return daily drawdown frame, lake list, and global extremes."""
        daily = self.build_daily_drawdown(data)
        lakes = self.extract_lakes(daily)

        deepest = None
        widest = None
        if lakes:
            deepest = min(lakes, key=lambda row: row["peakTroughDepthPct"])
            widest = max(lakes, key=lambda row: row["durationDays"])

        return {
            "daily": daily,
            "lakes": lakes,
            "deepestLake": deepest,
            "widestLake": widest,
        }

    def build_daily_drawdown(self, data: pd.Series | pd.DataFrame) -> pd.DataFrame:
        """Build a daily frame with HWM, drawdown %, and lake identifiers."""
        frame = self._normalize_input(data)

        frame["hwm"] = frame[self.value_col].cummax()
        frame["drawdown"] = (frame[self.value_col] - frame["hwm"]) / frame["hwm"] * 100.0

        underwater = frame["drawdown"] < 0.0
        lake_starts = underwater & ~underwater.shift(fill_value=False)
        lake_ids = lake_starts.cumsum()

        frame["isUnderwater"] = underwater
        frame["lakeId"] = lake_ids.where(underwater, 0).astype(int)
        return frame

    def extract_lakes(self, drawdown_df: pd.DataFrame) -> list[dict[str, Any]]:
        """Summarize contiguous underwater periods into drawdown lakes."""
        if drawdown_df.empty:
            return []

        underwater_df = drawdown_df[drawdown_df["lakeId"] > 0].copy()
        if underwater_df.empty:
            return []

        full_index = drawdown_df.index
        full_len = len(drawdown_df)

        pos_map = pd.Series(range(full_len), index=full_index)
        lakes: list[LakeSummary] = []

        for lake_id, rows in underwater_df.groupby("lakeId", sort=True):
            start_ts = rows.index.min()
            last_underwater_ts = rows.index.max()
            trough_ts = rows["drawdown"].idxmin()
            peak_trough_depth = float(rows["drawdown"].min())

            last_pos = int(pos_map[last_underwater_ts])
            recovery_ts = None
            is_open = True

            if last_pos + 1 < full_len:
                next_ts = full_index[last_pos + 1]
                next_drawdown = float(drawdown_df["drawdown"].iloc[last_pos + 1])
                if next_drawdown >= 0.0:
                    recovery_ts = next_ts
                    is_open = False

            effective_end_ts = recovery_ts if recovery_ts is not None else full_index[-1]
            duration_days = int((effective_end_ts.normalize() - start_ts.normalize()).days) + 1

            lakes.append(
                LakeSummary(
                    lake_id=int(lake_id),
                    start_date=self._to_iso_date(start_ts),
                    end_date="Open" if is_open else self._to_iso_date(recovery_ts),
                    is_open=is_open,
                    peak_trough_depth_pct=round(peak_trough_depth, 6),
                    duration_days=duration_days,
                    trough_date=self._to_iso_date(trough_ts),
                )
            )

        return [lake.to_dict() for lake in lakes]

    def _normalize_input(self, data: pd.Series | pd.DataFrame) -> pd.DataFrame:
        if isinstance(data, pd.Series):
            frame = data.to_frame(name=self.value_col)
        elif isinstance(data, pd.DataFrame):
            frame = data.copy()
        else:
            raise TypeError("data must be a pandas Series or DataFrame")

        if self.value_col not in frame.columns:
            raise ValueError(f"Missing required column: {self.value_col}")

        frame = frame[[self.value_col]].copy()
        frame.index = pd.to_datetime(frame.index)
        frame = frame.sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        frame[self.value_col] = pd.to_numeric(frame[self.value_col], errors="coerce")
        frame = frame.dropna(subset=[self.value_col])

        if frame.empty:
            return frame

        if (frame[self.value_col] <= 0).any():
            raise ValueError("Portfolio values must be strictly positive for drawdown math")

        return frame

    @staticmethod
    def _to_iso_date(ts: pd.Timestamp | None) -> str:
        if ts is None:
            return ""
        return pd.Timestamp(ts).strftime("%Y-%m-%d")
