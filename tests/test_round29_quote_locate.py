"""M4 synthetic quote-locator cases; see contracts/knowledge_tree.md.

Public tests cover punctuation, quoted terms, mixed separators and OCR matching
without redistributing source passages. Real-source validation stays local.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cs408_quote_locate import build_keymap, locate_quote  # noqa: E402

SYNTHETIC_SOURCE = (
    "Signal format 16bit standard\n"
    "Example “planner” entry and storage.\n"
    "units 1, 2, 3; rates 4, 5, 6; totals 7, 8, 9.\n"
    "device l/o path and port.\n"
)


def verify_tree_norm(text: str) -> str:
    """The exact normalization tools/verify_tree.py's norm() applies."""
    return re.sub(r"[\s　\xa0]+", "", text)


class LocateQuoteAgainstSyntheticSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_text = SYNTHETIC_SOURCE
        cls.keymap = build_keymap(cls.source_text)
        cls.norm_source = verify_tree_norm(cls.source_text)

    def _assert_resolves(self, raw: str) -> None:
        quote = locate_quote(raw, self.source_text, self.keymap)
        self.assertIsNotNone(quote, f"no quote found for {raw!r}")
        self.assertIn(verify_tree_norm(quote), self.norm_source)

    def test_trailing_punctuation_mismatch_case(self) -> None:
        # A line boundary can replace the final punctuation in an input label.
        self._assert_resolves("Signal format 16bit standard。")

    def test_quoted_term_with_curly_quotes(self) -> None:
        self._assert_resolves("Example “planner” entry and storage。")

    def test_long_enumeration_with_mixed_separators(self) -> None:
        self._assert_resolves("units 1, 2, 3；rates 4, 5, 6；totals 7, 8, 9。")

    def test_ocr_glitched_io_abbreviation(self) -> None:
        # The synthetic source models a lowercase-L OCR substitution.
        self._assert_resolves("device I/O path and port。")

    def test_no_match_returns_none(self) -> None:
        quote = locate_quote("这段文字完全不会出现在任何来源文本之中的胡编乱造内容", self.source_text, self.keymap)
        self.assertIsNone(quote)

    def test_empty_input_returns_none(self) -> None:
        self.assertIsNone(locate_quote("", self.source_text, self.keymap))
        self.assertIsNone(locate_quote("   ", self.source_text, self.keymap))


if __name__ == "__main__":
    unittest.main()
