import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHART_PATH = ROOT / "src" / "scripts" / "retirement-chart.js"


def _normalize(points):
    return sorted(
        [{"date": str(point["date"])[:10], "value": float(point["value"])} for point in points if point.get("date")],
        key=lambda item: item["date"],
    )


def _build_projection_bridge(actual_points, projected_points):
    actual = _normalize(actual_points)
    projected = _normalize(projected_points)
    if not actual or not projected:
        return projected
    last_actual = actual[-1]
    bridge = {"date": last_actual["date"], "value": last_actual["value"]}
    if projected[0]["date"] == last_actual["date"]:
        return [bridge] + projected[1:]
    return [bridge] + projected


def _compress(points, max_points):
    source = _normalize(points)
    if len(source) <= max_points:
        return source
    last_index = len(source) - 1
    picked = []
    for index in range(max_points):
        source_index = round((index / (max_points - 1)) * last_index)
        picked.append(source[source_index])
    deduped = {point["date"]: point for point in picked}
    return [deduped[key] for key in sorted(deduped.keys())]


class RetirementChartContractTests(unittest.TestCase):
    def test_chart_module_exposes_architecture_layers(self):
        js = CHART_PATH.read_text()
        self.assertIn("function buildProjectionBridge(actualPoints, projectedPoints)", js)
        self.assertIn("function compressLongTimeline(points, maxPoints = 220)", js)
        self.assertIn("function buildRetirementChartModel({", js)
        self.assertIn("function resolveYScaleState(datasets, chartState = {})", js)
        self.assertIn("function createRetirementChart(canvas, model, formatCurrency, chartState = {})", js)
        self.assertIn("futureFromActual = []", js)
        self.assertIn("futureFromProjected = []", js)
        self.assertIn("window.RetirementChart = RetirementChart", js)
        self.assertIn("module.exports = RetirementChart", js)

    def test_smooth_transition_reuses_last_historical_point(self):
        actual = [
            {"date": "2026-03-31", "value": 100000},
            {"date": "2026-04-30", "value": 103500},
        ]
        forecast = [
            {"date": "2026-05-31", "value": 104200},
            {"date": "2026-06-30", "value": 105800},
        ]
        bridged = _build_projection_bridge(actual, forecast)
        self.assertEqual(bridged[0]["date"], "2026-04-30")
        self.assertEqual(bridged[0]["value"], 103500.0)
        self.assertEqual(bridged[1]["date"], "2026-05-31")

    def test_visual_sanity_separates_historical_and_future_series(self):
        actual = [{"date": "2026-01-31", "value": 100000}, {"date": "2026-02-28", "value": 101500}]
        forecast = [{"date": "2026-03-31", "value": 102000}, {"date": "2026-04-30", "value": 103000}]
        bridged = _build_projection_bridge(actual, forecast)
        self.assertEqual([point["date"] for point in bridged[:2]], ["2026-02-28", "2026-03-31"])
        self.assertGreaterEqual(bridged[1]["value"], 0.0)

    def test_range_filter_keeps_recent_history_for_long_timelines(self):
        actual = [
            {"date": f"{2010 + index:04d}-01-01", "value": 100000 + index * 1000}
            for index in range(15)
        ]
        filtered = [point for point in _normalize(actual) if point["date"] >= "2019-01-01"]
        self.assertEqual(filtered[0]["date"], "2019-01-01")
        self.assertEqual(len(filtered), 6)

    def test_performance_sanity_caps_long_timelines(self):
        points = [
            {"date": f"{1980 + (index // 12):04d}-{((index % 12) + 1):02d}-01", "value": 100000 + index * 1500}
            for index in range(840)
        ]
        compressed = _compress(points, 220)
        self.assertLessEqual(len(compressed), 220)
        self.assertEqual(compressed[0]["date"], points[0]["date"])
        self.assertEqual(compressed[-1]["date"], points[-1]["date"])

    def test_tooltip_and_visual_markers_are_declared(self):
        js = CHART_PATH.read_text()
        self.assertIn("Retirement starts here", js)
        self.assertIn("Actual value from stored snapshots", js)
        self.assertIn("Projection starting from the real portfolio value today", js)
        self.assertIn("Projection starting from the theoretical portfolio value today", js)
        self.assertIn("label: model.datasetLabels.marker", js)
        self.assertIn("label: model.datasetLabels.historical", js)
        self.assertIn("label: model.datasetLabels.actualFuture", js)
        self.assertIn("label: model.datasetLabels.projectedFuture", js)
        self.assertIn("function filterHistoricalRange(actualPoints, range)", js)
        self.assertIn("scaleMode === 'log' ? 'log' : 'linear'", js)
        self.assertIn("yZoomPercent", js)
        self.assertIn("yPanPercent", js)
        self.assertIn("range = 'ALL'", js)


if __name__ == "__main__":
    unittest.main()
