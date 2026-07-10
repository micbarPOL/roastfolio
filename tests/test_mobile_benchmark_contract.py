import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class MobileBenchmarkContractTests(unittest.TestCase):
    def setUp(self):
        self.index_html = (ROOT / "src" / "index.html").read_text()
        self.statistics_js = (ROOT / "src" / "scripts" / "statistics.js").read_text()
        self.main_css = (ROOT / "src" / "styles" / "main.css").read_text()

    def test_mobile_benchmark_structure_js(self):
        # Verify JavaScript contains the correct mobile-specific layout generation and classes
        self.assertIn("class=\"bm-mobile-row\"", self.statistics_js)
        self.assertIn("class=\"bm-mobile-summary\"", self.statistics_js)
        self.assertIn("class=\"bm-mobile-details\"", self.statistics_js)
        self.assertIn("class=\"bm-mobile-details-grid\"", self.statistics_js)
        self.assertIn("class=\"bm-mobile-detail-item", self.statistics_js)
        self.assertIn("class=\"bm-mobile-detail-name\"", self.statistics_js)
        self.assertIn("class=\"bm-mobile-detail-val\"", self.statistics_js)
        self.assertIn("class=\"bm-mobile-detail-diff\"", self.statistics_js)
        self.assertIn("window.toggleMobileBmRow = toggleMobileBmRow;", self.statistics_js)

    def test_mobile_benchmark_styling_css(self):
        # Verify CSS contains correct selectors for mobile responsive benchmark views
        self.assertIn(".bm-mobile-only", self.main_css)
        self.assertIn(".bm-mobile-row", self.main_css)
        self.assertIn(".bm-mobile-details", self.main_css)
        self.assertIn(".bm-mobile-detail-item", self.main_css)
        self.assertIn(".bm-mobile-detail-val", self.main_css)
        
        # Verify that color contrast colors are properly defined for light mode to avoid white-on-white/light-red
        self.assertIn(".bm-mobile-detail-item.bm-mobile-win .bm-mobile-detail-val {", self.main_css)
        self.assertIn(".bm-mobile-detail-item.bm-mobile-loss .bm-mobile-detail-val {", self.main_css)
        self.assertIn("color: #15803d !important;", self.main_css)
        self.assertIn("color: #b91c1c !important;", self.main_css)

        # Verify dark mode overrides are defined
        self.assertIn("@media (prefers-color-scheme: dark)", self.main_css)

if __name__ == "__main__":
    unittest.main()
