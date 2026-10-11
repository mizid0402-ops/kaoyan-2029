from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing, contextmanager
from pathlib import Path

import yaml

from ky.ledger import load_ledger
from ky.projection import build_projection
from ky.workspace import load_workspace
from tools.verify_408_index import extract_408_answers, verify
from tests._resources import require_path

ROOT = Path(__file__).resolve().parents[2]


def _source_recovery_hint(resource_id: str, source_url: str | None) -> str:
    if source_url:
        return (
            f"restore resource_id {resource_id} from data/materials.yaml "
            f"storage.url {source_url}"
        )
    return f"restore resource_id {resource_id} from data/materials.yaml"


def _raw_source_recovery_hint(relative: str) -> str:
    workspace = load_workspace(ROOT / "kaoyan.workspace.yaml")
    materials = load_ledger(workspace.ledger)
    material = next(
        (item for item in materials if item.storage.path == relative),
        None,
    )
    if material is None:
        return f"restore raw source from data/materials.yaml; registered path: {relative}"
    return _source_recovery_hint(material.resource_id, material.storage.url)


def _copy_file(workspace_root: Path, relative: str, *, require_raw: bool = False) -> None:
    source = ROOT / relative
    if relative.startswith("data/raw_materials/") and not source.exists():
        # Only tests that read the source bytes need them; format checks must still run in
        # a clone without raw materials (sol round 121, C1-1).
        if require_raw:
            require_path(None, source, _raw_source_recovery_hint(relative))
        return
    target = workspace_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _copy_workspace(workspace_root: Path, *, require_raw: bool = False) -> dict:
    document = yaml.safe_load((ROOT / "kaoyan.workspace.yaml").read_text(encoding="utf-8"))
    reference = document["reference"]
    for paths in reference["knowledge_trees"].values():
        _copy_file(workspace_root, paths)
    for paths in reference["exam_indexes"].values():
        for relative in paths:
            _copy_file(workspace_root, relative)
    for relative in reference["paper_shapes"].values():
        _copy_file(workspace_root, relative)
    for key in ("topic_weights", "vocabulary_db", "ledger"):
        _copy_file(workspace_root, reference[key])
    for view in document.get("supplementary", {}).values():
        for relative in view["files"].values():
            _copy_file(workspace_root, relative)

    source_index = json.loads(
        (ROOT / "data/exam_questions/408_index_2026.json").read_text(encoding="utf-8")
    )
    needed = {block["resource_id"] for block in source_index["provenance"].values()}
    ledger_path = workspace_root / reference["ledger"]
    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    for item in ledger["items"]:
        if item["resource_id"] not in needed:
            continue
        relative = item["storage"].get("path")
        if relative:
            _copy_file(workspace_root, relative, require_raw=require_raw)
    document["projection"] = "data/projections/test.sqlite"
    registry = workspace_root / "kaoyan.workspace.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return document


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _synchronize_synthetic_source_hashes(
    root: Path,
    document: dict,
    index: dict,
    materials: dict,
    source_bytes: bytes | None = None,
) -> dict:
    """Synchronize index and ledger evidence after the source DOM changes."""
    if source_bytes is None:
        answer_id = index["provenance"]["answer"]["resource_id"]
        answer_path = root / materials[answer_id].storage.path
        source_bytes = answer_path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()

    source_ids = {
        block["resource_id"] for block in index["provenance"].values()
    }
    source_ids.update(
        source["resource_id"]
        for entry in index["entries"]
        for source in entry.get("answer_sources", [])
    )
    ledger_path = root / document["reference"]["ledger"]
    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    for resource_id in source_ids:
        material = materials[resource_id]
        relative = material.storage.path
        if relative is None:
            raise AssertionError(f"synthetic source {resource_id} has no local path")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_bytes)
        item = next(row for row in ledger["items"] if row["resource_id"] == resource_id)
        item["storage"]["sha256"] = source_hash
        item["storage"]["byte_size"] = len(source_bytes)

    for block in index["provenance"].values():
        block["sha256"] = source_hash
    for entry in index["entries"]:
        entry["locator"]["paper_sha256"] = source_hash
        for source in entry.get("answer_sources", []):
            source["sha256"] = source_hash

    ledger_path.write_text(
        yaml.safe_dump(ledger, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return {item.resource_id: item for item in load_ledger(ledger_path)}


def _sync_synthetic_answer_source(
    root: Path, document: dict, index: dict, materials: dict
) -> dict:
    """Build the registered answer DOM from this index and synchronize its evidence."""
    answer_numbers = {
        entry["number"]: entry["answer"]
        for entry in index["entries"]
        if entry.get("answer") is not None
    }
    entries_by_number = {entry["number"]: entry for entry in index["entries"]}
    cards = []
    for number, answer in sorted(answer_numbers.items()):
        entry = entries_by_number[number]
        digest = hashlib.sha256(entry["question_id"].encode("utf-8")).hexdigest()[:16]
        cards.append(
            f'<div class="explanation" id="explanation-choice-{digest}-{number}">'
            f'<span class="correct-answer-text">{answer}</span></div>'
        )
    source_bytes = ("<html><body>" + "".join(cards) + "</body></html>").encode("utf-8")
    return _synchronize_synthetic_source_hashes(
        root, document, index, materials, source_bytes
    )


def _clone_index(year: int, paper_source: str = "national") -> dict:
    data = json.loads(
        (ROOT / "data/exam_questions/408_index_2026.json").read_text(encoding="utf-8")
    )
    data["exam_year"] = year
    if paper_source != "national":
        data["paper_source"] = paper_source
    for entry in data["entries"]:
        entry["exam_year"] = year
        entry["question_id"] = (
            f"cs408-{year}-{entry['number']:02d}"
            if paper_source == "national"
            else f"cs408-{paper_source}-{year}-{entry['number']:02d}"
        )
    return data


def _write_registry(root: Path, document: dict) -> Path:
    registry = root / "kaoyan.workspace.yaml"
    registry.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return registry


@contextmanager
def _temporary_workspace(*, require_raw: bool = False):
    """``require_raw=True`` for tests that read source bytes: skip if they are missing."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "workspace"
        root.mkdir()
        document = _copy_workspace(root, require_raw=require_raw)
        registry = _write_registry(root, document)
        workspace = load_workspace(registry)
        materials = {
            item.resource_id: item for item in load_ledger(workspace.ledger)
        }
        yield root, document, registry, workspace, materials


def _add_shape(root: Path, document: dict, shape: dict) -> Path:
    shapes_path = root / document["reference"]["paper_shapes"]["cs408"]
    shapes_doc = yaml.safe_load(shapes_path.read_text(encoding="utf-8"))
    shapes_doc["papers"].append(shape)
    shapes_path.write_text(
        yaml.safe_dump(shapes_doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return shapes_path


def _xidian_paper(root: Path, document: dict) -> tuple[Path, dict]:
    shapes_path = root / document["reference"]["paper_shapes"]["cs408"]
    shapes_doc = yaml.safe_load(shapes_path.read_text(encoding="utf-8"))
    shape = copy.deepcopy(shapes_doc["papers"][-1])
    shape["paper_source"] = "xidian"
    shapes_doc["papers"].append(shape)
    shapes_path.write_text(
        yaml.safe_dump(shapes_doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    index = _clone_index(2026, "xidian")
    path = root / "data/exam_questions/cs408-xidian.json"
    _write_json(path, index)
    return path, index


def _mutate_answer_source(
    root: Path, index: dict, materials: dict, *, add_question: bool
) -> None:
    resource_id = index["provenance"]["answer"]["resource_id"]
    answer_path = root / materials[resource_id].storage.path
    answers = extract_408_answers(answer_path)
    number = max(answers) if add_question else min(answers)
    pattern = re.compile(
        r'<div\s+class=(?:"?)explanation(?:"?)\s+'
        r'id=(?:"?)explanation-choice-[0-9a-f]+-(\d+)(?:"?)>(.*?)</div>',
        re.S,
    )
    source = answer_path.read_text(encoding="utf-8", errors="replace")
    match = next(
        (
            candidate
            for candidate in pattern.finditer(source)
            if int(candidate.group(1)) == number
        ),
        None,
    )
    if match is None:
        raise AssertionError(f"answer source has no card for question {number}")
    if add_question:
        extra_number = max(answers) + 1
        card = match.group(0)
        start, end = match.span(1)
        local_start = start - match.start()
        local_end = end - match.start()
        extra_card = card[:local_start] + str(extra_number) + card[local_end:]
        source += extra_card
    else:
        source = source[:match.start()] + source[match.end():]
    answer_path.write_text(source, encoding="utf-8")


def _assert_problem(
    case: unittest.TestCase,
    path: Path,
    workspace,
    materials: dict,
    expected: str,
) -> list[str]:
    problems = verify(path, workspace, materials)
    case.assertTrue(
        any(expected in problem for problem in problems),
        f"expected a problem containing {expected!r}, got {problems!r}",
    )
    return problems


def _registered_indexes_with_local_sources(workspace, materials: dict) -> tuple[list, list]:
    available = []
    missing = []
    for paths in workspace.exam_indexes.values():
        for index_path in paths:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            source_ids = {
                block["resource_id"]
                for block in index.get("provenance", {}).values()
                if isinstance(block, dict) and block.get("resource_id")
            }
            source_ids.update(
                source["resource_id"]
                for entry in index.get("entries", [])
                for source in entry.get("answer_sources", [])
                if isinstance(source, dict) and source.get("resource_id")
            )
            if not source_ids:
                missing.append(
                    (
                        index_path.with_suffix(index_path.suffix + ".source-missing"),
                        f"{index_path}: no registered answer source",
                    )
                )
                continue

            unavailable = []
            for resource_id in sorted(source_ids):
                material = materials.get(resource_id)
                relative = material.storage.path if material is not None else None
                source_path = workspace.root / relative if relative else None
                if source_path is not None and source_path.is_file():
                    continue
                source_url = material.storage.url if material is not None else None
                recovery = _source_recovery_hint(resource_id, source_url)
                missing_path = source_path or workspace.raw_root / f"{resource_id}.missing"
                unavailable.append((missing_path, recovery))
            if unavailable:
                missing.extend(
                    (path, f"{index_path.relative_to(workspace.root).as_posix()}: {hint}")
                    for path, hint in unavailable
                )
            else:
                available.append((index_path, index))
    return available, missing


class ExamIndexPortTests(unittest.TestCase):
    def test_real_raw_page_verifies_when_available(self) -> None:
        workspace = load_workspace(ROOT / "kaoyan.workspace.yaml")
        materials = {item.resource_id: item for item in load_ledger(workspace.ledger)}
        available, missing = _registered_indexes_with_local_sources(workspace, materials)
        if not available:
            missing_path = missing[0][0]
            recovery_sources = "; ".join(detail for _, detail in missing)
            require_path(
                self,
                missing_path,
                f"no registered index has all answer sources locally available; "
                f"selected records and recovery sources: {recovery_sources}",
            )
        for index_path, index in available:
            label = index_path.relative_to(workspace.root).as_posix()
            with self.subTest(index=label):
                self.assertEqual(verify(index_path, workspace, materials), [])

    def test_2027_national_paper_is_data_only_and_projected(self) -> None:
        with _temporary_workspace() as (root, document, _, workspace, materials):
            shapes_path = root / document["reference"]["paper_shapes"]["cs408"]
            shapes_doc = yaml.safe_load(shapes_path.read_text(encoding="utf-8"))
            next_shape = copy.deepcopy(shapes_doc["papers"][-1])
            next_shape["exam_year"] = 2027
            _add_shape(root, document, next_shape)

            new_index = _clone_index(2027)
            materials = _sync_synthetic_answer_source(root, document, new_index, materials)
            index_path = root / "data/exam_questions/cs408-2027.json"
            _write_json(index_path, new_index)
            document["reference"]["exam_indexes"]["cs408"].append(
                index_path.relative_to(root).as_posix()
            )
            registry = _write_registry(root, document)
            workspace = load_workspace(registry)
            self.assertEqual(verify(index_path, workspace, materials), [])

            projection_path = root / "data/projections/wp-h3.sqlite"
            build_projection(workspace, projection_path)
            with closing(sqlite3.connect(projection_path)) as connection:
                rows = connection.execute(
                    "SELECT question_id FROM exam_questions WHERE exam_year = ?",
                    (new_index["exam_year"],),
                ).fetchall()
            self.assertEqual(
                {row[0] for row in rows},
                {entry["question_id"] for entry in new_index["entries"]},
            )

    def test_custom_paper_source_is_required_in_question_ids(self) -> None:
        with _temporary_workspace() as (root, document, _, workspace, materials):
            valid_path, valid_index = _xidian_paper(root, document)
            materials = _sync_synthetic_answer_source(root, document, valid_index, materials)
            _write_json(valid_path, valid_index)
            self.assertEqual(verify(valid_path, workspace, materials), [])

            missing_unit = copy.deepcopy(valid_index)
            entry = missing_unit["entries"][0]
            entry["question_id"] = f"cs408-2026-{entry['number']:02d}"
            bad_path = root / "data/exam_questions/xidian-missing-unit.json"
            _write_json(bad_path, missing_unit)
            _assert_problem(
                self,
                bad_path,
                workspace,
                materials,
                f"expected cs408-xidian-2026-{entry['number']:02d}",
            )

            document["reference"]["exam_indexes"]["cs408"].append(
                valid_path.relative_to(root).as_posix()
            )
            registry = _write_registry(root, document)
            workspace = load_workspace(registry)
            projection_path = root / "data/projections/xidian.sqlite"
            build_projection(workspace, projection_path)
            prefix = valid_index["entries"][0]["question_id"].rsplit("-", 1)[0] + "-"
            with closing(sqlite3.connect(projection_path)) as connection:
                rows = connection.execute(
                    "SELECT question_id FROM exam_questions WHERE question_id LIKE ?",
                    (prefix + "%",),
                ).fetchall()
            self.assertEqual(
                {row[0] for row in rows},
                {entry["question_id"] for entry in valid_index["entries"]},
            )

    def test_cs408_choice_answer_rejects_e(self) -> None:
        with _temporary_workspace() as (root, _, _, workspace, materials):
            index = _clone_index(2026)
            index["entries"][0]["answer"] = "E"
            path = root / "data/exam_questions/answer-e.json"
            _write_json(path, index)
            _assert_problem(self, path, workspace, materials, "choice answers must be A-D")

    def test_answer_reader_rejects_one_missing_question(self) -> None:
        with _temporary_workspace() as (root, document, _, workspace, materials):
            index = _clone_index(2026)
            materials = _sync_synthetic_answer_source(root, document, index, materials)
            _mutate_answer_source(root, index, materials, add_question=False)
            materials = _synchronize_synthetic_source_hashes(
                root, document, index, materials
            )
            path = root / "data/exam_questions/missing-answer-card.json"
            _write_json(path, index)
            problems = _assert_problem(
                self, path, workspace, materials, "answer reader yielded question numbers"
            )
            self.assertFalse(
                any("disk hash != index hash" in problem for problem in problems), problems
            )

    def test_answer_reader_rejects_one_extra_question(self) -> None:
        with _temporary_workspace() as (root, document, _, workspace, materials):
            index = _clone_index(2026)
            materials = _sync_synthetic_answer_source(root, document, index, materials)
            _mutate_answer_source(root, index, materials, add_question=True)
            materials = _synchronize_synthetic_source_hashes(
                root, document, index, materials
            )
            path = root / "data/exam_questions/extra-answer-card.json"
            _write_json(path, index)
            problems = _assert_problem(
                self, path, workspace, materials, "answer reader yielded question numbers"
            )
            self.assertFalse(
                any("disk hash != index hash" in problem for problem in problems), problems
            )

    def test_missing_calibration_is_reported_with_official_claim(self) -> None:
        with _temporary_workspace() as (root, _, _, workspace, materials):
            index = _clone_index(2026)
            index.pop("calibration")
            index["entries"][0]["answer_confidence"] = "official"
            path = root / "data/exam_questions/missing-calibration.json"
            _write_json(path, index)
            _assert_problem(self, path, workspace, materials, "$.calibration: required field")

    def test_missing_kind_is_reported(self) -> None:
        with _temporary_workspace() as (root, _, _, workspace, materials):
            index = _clone_index(2026)
            index.pop("kind")
            path = root / "data/exam_questions/missing-kind.json"
            _write_json(path, index)
            _assert_problem(self, path, workspace, materials, "$.kind: required field")

    def test_null_calibration_or_kind_is_rejected(self) -> None:
        # sol round 67: a null value used to pass both the required-key and the enum check.
        for key in ("calibration", "kind"):
            with self.subTest(key=key), _temporary_workspace() as (
                root, _, _, workspace, materials
            ):
                index = _clone_index(2026)
                index[key] = None
                index["entries"][0]["answer_confidence"] = "official"
                path = root / f"data/exam_questions/null-{key}.json"
                _write_json(path, index)
                _assert_problem(self, path, workspace, materials, f"$.{key}: must not be null")

    def test_descriptive_fields_stay_optional(self) -> None:
        for key in ("content_policy", "verified_facts", "unverified_facts"):
            with self.subTest(key=key), _temporary_workspace() as (
                root, document, _, workspace, materials
            ):
                index = _clone_index(2026)
                materials = _sync_synthetic_answer_source(root, document, index, materials)
                index.pop(key)
                path = root / f"data/exam_questions/without-{key}.json"
                _write_json(path, index)
                self.assertEqual(verify(path, workspace, materials), [])

    def test_fractional_marks_sum_without_binary_rounding(self) -> None:
        with _temporary_workspace() as (root, document, _, workspace, materials):
            index = _clone_index(2027)
            index["entries"] = index["entries"][:3]
            index["question_count"] = len(index["entries"])
            index["marks_total"] = 0.3
            index["answer_source_coverage"]["choice_total"] = sum(
                entry["answer_kind"] == "letter" for entry in index["entries"]
            )
            for number, entry in enumerate(index["entries"], start=1):
                entry["number"] = number
                entry["exam_year"] = index["exam_year"]
                entry["question_id"] = f"cs408-2027-{number:02d}"
                entry["question_type"] = "single_choice"
                entry["marks"] = 0.1
            materials = _sync_synthetic_answer_source(root, document, index, materials)
            _add_shape(
                root,
                document,
                {
                    "exam_year": 2027,
                    "paper_source": "national",
                    "question_count": len(index["entries"]),
                    "sections": [
                        {
                            "numbers": [1, len(index["entries"])],
                            "question_type": "single_choice",
                            "marks_each": 0.1,
                            "answer_letters": "ABCD",
                        }
                    ],
                    "basis": "Decimal comparison regression case.",
                },
            )
            path = root / "data/exam_questions/fractional-marks.json"
            _write_json(path, index)
            self.assertEqual(verify(path, workspace, materials), [])

    def test_index_without_registered_paper_record_fails(self) -> None:
        with _temporary_workspace() as (root, _, _, workspace, materials):
            path = root / "data/exam_questions/no-shape.json"
            _write_json(path, _clone_index(2028))
            _assert_problem(self, path, workspace, materials, "no paper shape recorded")

    def test_subject_without_registered_shape_file_fails(self) -> None:
        with _temporary_workspace() as (root, document, _, _, materials):
            path = root / "data/exam_questions/no-shape-file.json"
            _write_json(path, _clone_index(2028))
            document["reference"]["paper_shapes"].pop("cs408")
            registry = _write_registry(root, document)
            _assert_problem(
                self,
                path,
                load_workspace(registry),
                materials,
                "no paper shape file registered",
            )

    def test_question_type_must_match_registered_section(self) -> None:
        with _temporary_workspace() as (root, _, _, workspace, materials):
            index = _clone_index(2026)
            index["entries"][0]["question_type"] = "writing"
            path = root / "data/exam_questions/wrong-type.json"
            _write_json(path, index)
            _assert_problem(
                self, path, workspace, materials, "question_type disagrees with paper shape"
            )

    def test_unverified_section_rejects_recorded_marks(self) -> None:
        with _temporary_workspace() as (root, _, _, workspace, materials):
            index = _clone_index(2026)
            entry = index["entries"][-1]
            entry["marks"] = 1
            path = root / "data/exam_questions/unverified-marks.json"
            _write_json(path, index)
            _assert_problem(self, path, workspace, materials, "unverified marks must be null")

    def test_unknown_answer_reader_fails(self) -> None:
        with _temporary_workspace() as (root, document, _, workspace, materials):
            index_path, _ = _xidian_paper(root, document)
            shapes_path = root / document["reference"]["paper_shapes"]["cs408"]
            shapes_doc = yaml.safe_load(shapes_path.read_text(encoding="utf-8"))
            shapes_doc["papers"][-1]["answer_reader"] = "unknown_reader"
            shapes_path.write_text(
                yaml.safe_dump(shapes_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            _assert_problem(
                self, index_path, workspace, materials, "unknown answer_reader 'unknown_reader'"
            )


if __name__ == "__main__":
    unittest.main()
