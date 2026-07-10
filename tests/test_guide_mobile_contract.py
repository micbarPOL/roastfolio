import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GuideMobileContractTests(unittest.TestCase):
    def test_guide_has_mobile_friendly_navigation(self):
        html = (ROOT / "src" / "guide.html").read_text()

        required = [
            'name="viewport" content="width=device-width, initial-scale=1.0"',
            'class="mobile-header"',
            'class="mobile-menu-button"',
            'id="mobile-quick-nav"',
            'function buildMobileQuickNav()',
            'function toggleMobileNav(show)',
            'body.nav-open',
            'aria-expanded',
            'env(safe-area-inset-top',
            'env(safe-area-inset-bottom',
        ]
        for marker in required:
            self.assertIn(marker, html)

    def test_guide_mobile_tables_are_cardified(self):
        html = (ROOT / "src" / "guide.html").read_text()

        self.assertIn('two-col-mobile', html)
        self.assertIn("firstRow.children.length === 2", html)
        self.assertIn('.table-scroll-wrapper table.two-col-mobile tr', html)
        self.assertIn('.table-scroll-wrapper table.two-col-mobile td:first-child', html)
        self.assertIn('overflow-wrap: anywhere', html)
        self.assertIn('overflow-x: hidden', html)


if __name__ == "__main__":
    unittest.main()
