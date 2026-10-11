"""Round-29: tests for the keymap-based quote_ref locator.

Regression cases are drawn from the 24 real CS408 detail/note nodes whose
raw 2022-title match was confirmed only at round22_extract.key()'s fuzzy
normalization level (punctuation/whitespace/case stripped) and did NOT
literally substring-match under verify_tree.py's much gentler whitespace-only
normalization -- see review/rounds/round-29-tree-split-claude.md section 3.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from tests._resources import require_path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cs408_quote_locate import build_keymap, locate_quote  # noqa: E402

EXTRACTED_TEXT_PATH = ROOT / "data/raw_materials/cs408/syllabus/408_syllabus_2022.extracted.txt"


def verify_tree_norm(text: str) -> str:
    """The exact normalization tools/verify_tree.py's norm() applies."""
    return re.sub(r"[\s　\xa0]+", "", text)


class LocateQuoteAgainstRealSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        require_path(
            None,
            EXTRACTED_TEXT_PATH,
            "按 data/materials.yaml 对应的 2022 大纲来源重新获取并抽取",
        )
        cls.source_text = EXTRACTED_TEXT_PATH.read_text(encoding="utf-8")
        cls.keymap = build_keymap(cls.source_text)
        cls.norm_source = verify_tree_norm(cls.source_text)

    def _assert_resolves(self, raw: str) -> None:
        quote = locate_quote(raw, self.source_text, self.keymap)
        self.assertIsNotNone(quote, f"no quote found for {raw!r}")
        self.assertIn(verify_tree_norm(quote), self.norm_source)

    def test_trailing_punctuation_mismatch_case(self) -> None:
        # HTML title ends in a full-width period the 2022 PDF text doesn't have
        # at that position (a line break follows instead).
        self._assert_resolves("IEEE 754 标准。")

    def test_quoted_term_with_curly_quotes(self) -> None:
        self._assert_resolves("“存储程序”工作方式，高级语言程序与机器语言程序之间的转换，程序和指令的执行过程。")

    def test_long_enumeration_with_mixed_separators(self) -> None:
        self._assert_resolves("吞吐量、响应时间；CPU 时钟周期、主频、CPI、CPU 执行时间；MIPS、MFLOPS、GFLOPS、TFLOPS、PFLOPS、EFLOPS、ZFLOPS。")

    def test_ocr_glitched_io_abbreviation(self) -> None:
        # The 2022 PDF's text layer has "l/o" (lowercase L) for "I/O" at this
        # exact spot; the OCR fix in key() is required to find it at all.
        self._assert_resolves("设备的基本概念，设备的分类，I/O 接口，I/O 端口。")

    def test_no_match_returns_none(self) -> None:
        quote = locate_quote("这段文字完全不会出现在任何来源文本之中的胡编乱造内容", self.source_text, self.keymap)
        self.assertIsNone(quote)

    def test_empty_input_returns_none(self) -> None:
        self.assertIsNone(locate_quote("", self.source_text, self.keymap))
        self.assertIsNone(locate_quote("   ", self.source_text, self.keymap))


if __name__ == "__main__":
    unittest.main()
