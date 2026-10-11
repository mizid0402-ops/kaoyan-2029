"""Current behavior checks for registered CS408 HTML question extraction."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from ky.workspace import load_workspace
from tests._resources import require_path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "kaoyan.workspace.yaml"
EXTRACTOR = ROOT / "tools" / "extract_408_questions_from_html.py"
VERIFIER = ROOT / "tools" / "verify_408_question_extraction.py"


def _extractor_module():
    spec = importlib.util.spec_from_file_location("current_question_extractor", EXTRACTOR)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load the current question extractor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require_registered_html(testcase: unittest.TestCase, workspace) -> None:
    require_path(testcase, workspace.raw_root, "restore registered raw materials")
    for index_path in workspace.require_all("reference.exam_indexes.cs408"):
        document = json.loads(index_path.read_text(encoding="utf-8"))
        quiz_path = workspace.raw_root / "cs408" / "quiz_pages" / (
            f"cs408_quiz_{document['exam_year']}.html"
        )
        require_path(testcase, quiz_path, "restore registered raw quiz HTML")


class QuestionExtractionTests(unittest.TestCase):
    def test_registered_extraction_writes_current_outputs(self) -> None:
        workspace = load_workspace(REGISTRY)
        _require_registered_html(self, workspace)
        module = _extractor_module()

        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            original_require = workspace.require

            class ProductWorkspace:
                def __getattr__(self, name):
                    return getattr(workspace, name)

                def require(self, key):
                    if key == "products.cs408_lecture_workspace":
                        return output_root
                    return original_require(key)

            module.load_workspace = lambda _path: ProductWorkspace()
            stdout = StringIO()
            stderr = StringIO()
            with patch("sys.argv", [str(EXTRACTOR), "--workspace", str(REGISTRY)]):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    module.main()

            questions = output_root / "questions"
            index_path = questions / "questions_index.json"
            report_path = questions / "extraction_report.json"
            deck_map_path = output_root / "deck_question_map.json"
            self.assertTrue(index_path.is_file())
            self.assertTrue(report_path.is_file())
            self.assertTrue(deck_map_path.is_file())
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertTrue(index)
            self.assertTrue(stdout.getvalue())
            self.assertEqual(stderr.getvalue(), "")

    def test_registered_question_extraction_verifier_accepts_outputs(self) -> None:
        workspace = load_workspace(REGISTRY)
        product_root = workspace.products["cs408_lecture_workspace"]
        require_path(
            self,
            product_root / "questions" / "questions_index.json",
            "generate registered products with the current HTML extractor",
        )
        result = subprocess.run(
            [sys.executable, str(VERIFIER), "--workspace", str(REGISTRY)],
            cwd=ROOT,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
