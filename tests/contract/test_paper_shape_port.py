from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import yaml

from ky.exam.paper_shape import load_paper_shapes
from ky.models import ContractError


def _document() -> dict:
    return {
        "schema_version": 1,
        "kind": "paper_shapes",
        "subject_id": "cs408",
        "papers": [
            {
                "exam_year": 2027,
                "paper_source": "national",
                "question_count": 2,
                "sections": [
                    {"numbers": [1, 1], "question_type": "single_choice", "answer_letters": "ABCD"},
                    {"numbers": [2, 2], "question_type": "writing", "marks": {2: 3}},
                ],
                "basis": "Read from the registered paper.",
            }
        ],
    }


class PaperShapePortTests(unittest.TestCase):
    def _load(self, document: dict, subject_id: str = "cs408"):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "shapes.yaml"
            path.write_text(
                yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
            )
            return load_paper_shapes(path, subject_id=subject_id)

    def test_loads_record_and_answers_by_source(self) -> None:
        result = self._load(_document())
        shape = result.get(2027, "national")
        self.assertEqual(shape.question_count, 2)
        self.assertEqual(shape.sections[0].answer_letters, "ABCD")
        self.assertEqual(shape.sections[1].marks[2], 3)
        with self.assertRaises(ContractError):
            result.get(2028)

    def test_accepts_finite_fractional_marks(self) -> None:
        document = _document()
        document["papers"][0]["sections"][0]["marks_each"] = 0.5
        document["papers"][0]["sections"][1]["marks"] = {2: 0.5}
        shape = self._load(document).get(2027)
        self.assertEqual(shape.sections[0].marks_each, 0.5)
        self.assertEqual(shape.sections[1].marks[2], 0.5)

    def test_rejects_nonpositive_and_nonfinite_marks(self) -> None:
        for value in (0, -1, float("nan")):
            with self.subTest(value=value):
                document = _document()
                document["papers"][0]["sections"][0]["marks_each"] = value
                with self.assertRaises(ContractError):
                    self._load(document)

    def test_mixed_type_unknown_keys_report_a_paper_path(self) -> None:
        document = _document()
        document["papers"][0][7] = "unknown integer key"
        document["papers"][0]["unknown_string_key"] = True
        with self.assertRaises(ContractError) as raised:
            self._load(document)
        self.assertIn("unknown field", raised.exception.message)
        self.assertIn("papers[0].", raised.exception.path)

    def test_rejects_question_count_over_two_digit_limit(self) -> None:
        document = _document()
        paper = document["papers"][0]
        paper["question_count"] = 100
        paper["sections"] = [
            {"numbers": [1, 100], "question_type": "writing"}
        ]
        with self.assertRaises(ContractError) as raised:
            self._load(document)
        self.assertIn("question_count must be <= 99", raised.exception.message)

    def test_rejects_each_invalid_shape(self) -> None:
        cases = []

        doc = _document()
        doc["unknown"] = True
        cases.append(("unknown key", doc))

        doc = _document()
        doc["papers"][0]["sections"][1]["numbers"] = [1, 2]
        cases.append(("overlap", doc))

        doc = _document()
        doc["papers"][0]["sections"][1]["numbers"] = [3, 3]
        cases.append(("gap", doc))

        doc = _document()
        doc["papers"][0]["sections"][1]["numbers"] = [2, 3]
        cases.append(("overrun", doc))

        doc = _document()
        doc["papers"].append(copy.deepcopy(doc["papers"][0]))
        cases.append(("duplicate paper identity", doc))

        doc = _document()
        doc["papers"][0]["basis"] = "  "
        cases.append(("empty basis", doc))

        doc = _document()
        doc["papers"][0]["sections"][1]["marks"] = {1: 3}
        cases.append(("mark numbers mismatch", doc))

        doc = _document()
        doc["papers"][0]["sections"][0]["marks_each"] = 2
        doc["papers"][0]["sections"][0]["marks"] = {1: 2}
        cases.append(("multiple marks forms", doc))

        doc = _document()
        doc["papers"][0]["paper_source"] = "Xidian"
        cases.append(("invalid paper source", doc))

        for label, document in cases:
            with self.subTest(label=label), self.assertRaises(ContractError):
                self._load(document)

        with self.assertRaises(ContractError):
            self._load(_document(), subject_id="math1")


if __name__ == "__main__":
    unittest.main()
