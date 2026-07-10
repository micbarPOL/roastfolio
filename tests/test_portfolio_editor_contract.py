import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PortfolioEditorContractTests(unittest.TestCase):
    def test_portfolio_screen_editor_is_pencil_driven(self):
        html = (ROOT / "src" / "index.html").read_text()
        js = (ROOT / "src" / "scripts" / "portfolio-chart.js").read_text()

        self.assertIn("id=\"mgmt-holdings-title\"", html)
        self.assertIn("id=\"mgmt-settings-actions\"", html)
        self.assertIn("onclick=\"toggleAthEditor('${row.key}')\"", js)
        self.assertIn("window.toggleAthEditor = toggleAthEditor;", js)
        self.assertIn("data-role=\"name\"", js)
        self.assertIn("<div class=\"portfolio-ath-form${isOpen ? ' is-open' : ''}\" ${isOpen ? '' : 'hidden aria-hidden=\"true\" style=\"display:none;\"'}>", js)
        self.assertIn("onclick=\"savePortfolioEditor('${row.key}')\"", js)
        self.assertIn("Reset from history", js)


if __name__ == "__main__":
    unittest.main()
