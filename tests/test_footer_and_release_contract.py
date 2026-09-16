import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FooterAndReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index_html = (ROOT / "src" / "index.html").read_text()
        cls.guide_html = (ROOT / "src" / "guide.html").read_text()
        cls.auth_html = (ROOT / "src" / "auth.html").read_text()
        cls.main_css = (ROOT / "src" / "styles" / "main.css").read_text()
        cls.release_doc = (ROOT / "docs" / "RELEASE_NUMBERING.md").read_text()
        cls.package_json = json.loads((ROOT / "package.json").read_text())

        # Extract active release from RELEASE_NUMBERING.md
        match = re.search(r"\*\*Current Release:\*\*\s*`([^`]+)`", cls.release_doc)
        cls.active_version = match.group(1) if match else None

    def test_version_format_and_extraction(self):
        self.assertIsNotNone(self.active_version, "Active version could not be extracted from RELEASE_NUMBERING.md")
        self.assertRegex(self.active_version, r"^\d+\.\d+\.\d+$", f"Invalid version format: {self.active_version}")

    def test_app_footer_structure_and_attribution(self):
        # Footer element presence and accessibility role
        self.assertIn('<footer id="app-footer" class="app-global-footer"', self.index_html)
        self.assertIn('Powered by', self.index_html)
        self.assertIn('TOMINEX', self.index_html)

        # Version display
        self.assertIn('id="app-version-display"', self.index_html)
        self.assertIn(f'>{self.active_version}<', self.index_html)
        self.assertIn(f'v{self.active_version}', self.index_html)

        # Links to release numbering & guide
        self.assertIn('guide.html#release-numbering', self.index_html)
        self.assertIn('guide.html', self.index_html)

        # Sidenav and User Modal attribution
        self.assertIn('class="sidenav-bottom-brand"', self.index_html)
        self.assertIn('class="user-modal-branding"', self.index_html)

    def test_footer_css_styles_exist(self):
        self.assertIn('.app-global-footer', self.main_css)
        self.assertIn('.app-footer-card', self.main_css)
        self.assertIn('.tominex-brand-name', self.main_css)
        self.assertIn('.app-footer-version-pill', self.main_css)
        self.assertIn(':root[data-theme="light"] .app-footer-card', self.main_css)
        self.assertIn('@media (max-width: 768px)', self.main_css)

    def test_guide_html_documents_release_numbering(self):
        self.assertIn('id="release-numbering"', self.guide_html)
        self.assertIn('TOMINEX', self.guide_html)
        self.assertIn(f'v{self.active_version}', self.guide_html)

        # Verify semantic definitions
        self.assertIn('MAJOR', self.guide_html)
        self.assertIn('MINOR', self.guide_html)
        self.assertIn('SERVICE', self.guide_html)
        self.assertIn('New Features', self.guide_html)
        self.assertIn('Changes to Existing Features', self.guide_html)
        self.assertIn('Bug Fixes', self.guide_html)

        # Guide footer
        self.assertIn('class="guide-footer"', self.guide_html)

    def test_auth_html_contains_footer_and_version(self):
        self.assertIn('class="auth-page-footer"', self.auth_html)
        self.assertIn('TOMINEX', self.auth_html)
        self.assertIn(f'v{self.active_version}', self.auth_html)
        self.assertIn('guide.html#release-numbering', self.auth_html)

    def test_release_documentation_markdown(self):
        self.assertIn('TOMINEX', self.release_doc)
        self.assertIn(self.active_version, self.release_doc)
        self.assertIn('Major Version', self.release_doc)
        self.assertIn('Minor Version', self.release_doc)
        self.assertIn('Service Release', self.release_doc)
        self.assertIn('New features', self.release_doc)
        self.assertIn('Changes to existing features', self.release_doc)
        self.assertIn('Bug fixes', self.release_doc)

    def test_package_json_version_synced(self):
        self.assertEqual(self.package_json.get('version'), self.active_version)


if __name__ == "__main__":
    unittest.main()

