"""
test_transaction_inline_layout.py
=================================
Static-analysis tests for the inline Transaction card layout.

They verify:
  1. HTML structure — the transaction form is now an inline card
     (.wallet-tx-card) placed within the main wallet screen, not an overlay.
  2. CSS layout contracts — the card is flex-column and handles its internal
     structure correctly without fixed-height overlay restrictions.

These tests DO NOT require a browser or Selenium; they parse files directly.
Run with:  python -m pytest tests/test_transaction_inline_layout.py -v
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _css_block_for(selector: str, css: str) -> str:
    """
    Return the first CSS rule-block whose selector contains `selector`.
    """
    pat = re.escape(selector).replace(r"\.", ".")
    match = re.search(
        rf"{pat}\s*\{{([^}}]*)\}}", css, re.DOTALL | re.IGNORECASE
    )
    if not match:
        raise AssertionError(f"CSS block not found for selector: {selector!r}")
    return match.group(1)


def _all_css_blocks_for(selector: str, css: str) -> list[str]:
    """Return ALL css blocks whose selector fragment contains `selector`."""
    pat = re.escape(selector).replace(r"\.", ".")
    return [
        m.group(1)
        for m in re.finditer(
            rf"[^{{}}]*{pat}[^{{}}]*\{{([^}}]*)\}}", css, re.DOTALL | re.IGNORECASE
        )
    ]


class TransactionInlineHtmlStructureTests(unittest.TestCase):
    """Verify the HTML element order inside #wallet-transaction-card."""

    def setUp(self):
        self.html = (ROOT / "src" / "index.html").read_text()

    def _card_fragment(self) -> str:
        """Extract only the transaction card div from the full HTML."""
        start = self.html.find('id="wallet-transaction-card"')
        self.assertGreater(start, 0, "wallet-transaction-card not found in index.html")
        return self.html[start : start + 40960]

    def test_card_exists_with_wallet_tx_card_class(self):
        self.assertIn('class="wallet-card wallet-tx-card"', self.html)

    def test_overlay_removed(self):
        self.assertNotIn('id="mgmt-transaction-overlay"', self.html)
        self.assertNotIn('class="wallet-overlay-backdrop"', self.html)
        self.assertNotIn('class="tflow-overlay"', self.html)
        self.assertNotIn('class="tflow-sheet"', self.html)

    def test_tflow_footer_is_sibling_of_tflow_body_not_child(self):
        frag = self._card_fragment()

        body_pos   = frag.find('class="tflow-body"')
        footer_pos = frag.find('class="tflow-footer"')

        self.assertGreater(body_pos, 0, ".tflow-body not found inside card fragment")
        self.assertGreater(footer_pos, 0, ".tflow-footer not found inside card fragment")

        self.assertGreater(
            footer_pos, body_pos,
            ".tflow-footer must appear after .tflow-body in the DOM"
        )

        between = frag[body_pos:footer_pos]
        self.assertIn(
            "</div>", between,
            ".tflow-footer appears to be inside .tflow-body (no closing tag between them). "
            "Footer must be a sibling, not a child."
        )

    def test_amount_inputs_are_inside_tflow_body(self):
        frag = self._card_fragment()
        body_start = frag.find('class="tflow-body"')
        footer_start = frag.find('class="tflow-footer"')
        body_frag = frag[body_start:footer_start]

        for input_id in ("mgmt-units-input", "mgmt-price-input", "mgmt-total-input"):
            self.assertIn(
                f'id="{input_id}"', body_frag,
                f"#{input_id} must be inside .tflow-body"
            )


class TransactionInlineCssLayoutTests(unittest.TestCase):
    """Verify CSS rules for the inline transaction card."""

    def setUp(self):
        self.css = (ROOT / "src" / "styles" / "main.css").read_text()

    def test_wallet_tx_card_is_flex_column(self):
        blocks = _all_css_blocks_for(".wallet-tx-card", self.css)
        self.assertTrue(
            any("display" in b and "flex" in b for b in blocks),
            ".wallet-tx-card must set display:flex"
        )
        self.assertTrue(
            any("flex-direction" in b and "column" in b for b in blocks),
            ".wallet-tx-card must set flex-direction:column"
        )


if __name__ == "__main__":
    unittest.main()
