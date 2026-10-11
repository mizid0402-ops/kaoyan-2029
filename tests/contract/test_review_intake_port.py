from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

from ky.__main__ import learn_main, review_questions_main
from ky.models import ReviewItem, validate_review_item
from ky.storage.review_shards import ReviewShardStore
from ky.workspace import WORKSPACE_FILENAME

ROOT = Path(__file__).resolve().parents[2]
LEARNED_POINT = "math1.demo.chapter.item-a"
PARENT = "math1.demo.chapter"


def _node(point_id: str, title: str, scope: str = "item") -> dict:
    return {
        "schema_version": 1,
        "knowledge_point_id": point_id,
        "title": title,
        "scope": scope,
        "status": "raw",
        "source_kind": "manual",
        "sources": [{"path": "synthetic.pdf", "sha256": "0" * 64,
                     "locator": {"page": 1}}],
    }


def _workspace(root: Path, *, active: bool = True) -> Path:
    registry_doc = copy.deepcopy(yaml.safe_load(
        (ROOT / WORKSPACE_FILENAME).read_text(encoding="utf-8")
    ))
    registry_doc["subjects"] = {"math1": {"name": "Math", "tree_grammar": "flat"}}
    registry_doc["reference"]["knowledge_trees"] = {"math1": "trees/tree.yaml"}
    registry_doc["reference"]["syllabus_versions"] = {}
    registry_doc["reference"]["exam_indexes"] = {"math1": ["indexes/questions.json"]}
    registry_doc["reference"]["topic_weights"] = "weights/topic_weights.json"
    registry_doc["reference"]["paper_shapes"] = {}
    registry_doc["supplementary"] = {}
    registry_doc["settings"] = {"exam_config": "config.yaml"}
    registry_doc["state"] = {
        "review_queue": "state/review_queue",
        "plans": "state/plans",
        "question_bank": "state/question_bank",
    }
    registry_doc["staging"] = "staging"

    config = yaml.safe_load(
        (ROOT / "tests/fixtures/config/config-minimal.yaml").read_text(encoding="utf-8")
    )
    config["subjects"] = [{
        "subject_id": "math1", "display_name": "数学一", "weight": 1.0 if active else 0.0,
        "active": active, "min_daily_minutes": 0,
    }]
    if not active:
        config["subjects"].append({
            "subject_id": "eng1", "display_name": "英语一", "weight": 1.0,
            "active": True, "min_daily_minutes": 0,
        })
        registry_doc["subjects"]["eng1"] = {"name": "English", "tree_grammar": "flat"}
        registry_doc["reference"]["knowledge_trees"]["eng1"] = "trees/eng1.yaml"
        registry_doc["reference"]["exam_indexes"]["eng1"] = ["indexes/eng1.json"]

    tree = [
        _node(PARENT, "示例章节", "chapter"),
        _node(LEARNED_POINT, "示例知识点"),
        _node("math1.demo.chapter.item-b", "第二知识点"),
        _node("math1.demo.tracker", "跟踪节点", "subject"),
    ]
    tree_path = root / "trees/tree.yaml"
    tree_path.parent.mkdir(parents=True)
    tree_path.write_text(yaml.safe_dump(tree, allow_unicode=True), encoding="utf-8")
    if not active:
        (root / "trees/eng1.yaml").write_text(
            yaml.safe_dump([_node("eng1.demo.point", "英语知识点")], allow_unicode=True),
            encoding="utf-8",
        )
        english_index = root / "indexes/eng1.json"
        english_index.parent.mkdir(parents=True, exist_ok=True)
        english_index.write_text(
            json.dumps({"entries": []}), encoding="utf-8"
        )
    index = root / "indexes/questions.json"
    index.parent.mkdir(exist_ok=True)
    index.write_text(json.dumps({"entries": []}), encoding="utf-8")
    weights = root / "weights/topic_weights.json"
    weights.parent.mkdir()
    weights.write_text(json.dumps({"per_question": {}}), encoding="utf-8")
    (root / "config.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    registry = root / WORKSPACE_FILENAME
    registry.write_text(
        yaml.safe_dump(registry_doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return registry


def _item(
    point_id: str = LEARNED_POINT,
    review_id: str = "rv-existing",
    *,
    state: str = "queued",
) -> ReviewItem:
    return validate_review_item({
        "review_id": review_id,
        "revision": 1,
        "subject_id": point_id.split(".", 1)[0],
        "knowledge_point_id": point_id,
        "title": "已有项目",
        "granularity": "concept",
        "state": state,
        "estimated_minutes": 5,
        "introduced_on": "2026-09-01",
        "due_date": "2026-09-02",
        "last_reviewed_on": None,
        "schedule": {
            "mode": "fixed_bootstrap", "phase": 0, "interval_days": 1,
            "ease_factor": 2.5, "repetitions": 0, "lapses": 0,
        },
        "defer_count": 0,
        "last_quality": None,
        "self_rating": None,
    })


def _queue_bytes(path: Path) -> dict[str, bytes]:
    return {
        child.relative_to(path).as_posix(): child.read_bytes()
        for child in path.rglob("*") if child.is_file()
    } if path.exists() else {}


class ReviewIntakePortTests(unittest.TestCase):
    def test_first_learn_creates_valid_next_day_item_from_empty_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            code = learn_main([
                "--date", "2026-10-01", "--knowledge-point", LEARNED_POINT,
                "--workspace", str(registry),
            ])
            self.assertEqual(code, 0)
            item = ReviewShardStore(root / "state/review_queue").load()[0]
            self.assertEqual(item.review_id, f"rv-{LEARNED_POINT}")
            self.assertEqual(item.revision, 1)
            self.assertEqual(item.subject_id, "math1")
            self.assertEqual(item.knowledge_point_id, LEARNED_POINT)
            self.assertEqual(item.title, "示例知识点")
            self.assertEqual(item.granularity, "concept")
            self.assertEqual(item.state, "queued")
            self.assertEqual(item.estimated_minutes, 5)
            self.assertEqual(item.introduced_on, date(2026, 10, 1))
            self.assertEqual(item.due_date, date(2026, 10, 2))
            self.assertIsNone(item.last_reviewed_on)
            self.assertEqual(item.last_quality, None)
            self.assertIsNone(item.last_self_rating)
            self.assertEqual(item.schedule.mode, "fixed_bootstrap")
            self.assertEqual(item.schedule.phase, 0)
            self.assertEqual(item.schedule.interval_days, 1)
            self.assertEqual(item.schedule.ease_factor, 2.5)
            self.assertEqual(item.schedule.repetitions, 0)
            self.assertEqual(item.schedule.lapses, 0)
            self.assertEqual(item.defer_count, 0)

    def test_direct_duplicate_tracker_unregistered_and_inactive_inputs_do_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            queue_path = root / "state/review_queue"
            ReviewShardStore(queue_path).write([_item(review_id="rv-current")])
            before = _queue_bytes(queue_path)
            cases = [
                (["--knowledge-point", LEARNED_POINT], 2),
                (["--knowledge-point", "math1.demo.tracker"], 2),
                (["--knowledge-point", "unknown.point"], 2),
                (["--knowledge-point", "eng1.demo.point"], 2),
            ]
            for options, expected in cases:
                with self.subTest(options=options):
                    args = ["--date", "2026-10-01", *options, "--workspace", str(registry)]
                    self.assertEqual(learn_main(args), expected)
                    self.assertEqual(_queue_bytes(queue_path), before)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root, active=False)
            self.assertEqual(learn_main([
                "--date", "2026-10-01", "--knowledge-point", LEARNED_POINT,
                "--workspace", str(registry),
            ]), 2)
            self.assertEqual(_queue_bytes(root / "state/review_queue"), {})

    def test_duplicate_argument_is_usage_error_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            args = [
                "--date", "2026-10-01", "--knowledge-point", LEARNED_POINT,
                "--knowledge-point", LEARNED_POINT, "--workspace", str(registry),
            ]
            self.assertEqual(learn_main(args), 3)
            self.assertEqual(_queue_bytes(root / "state/review_queue"), {})

    def test_leaves_under_skips_queued_leaf_and_empty_result_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            queue_path = root / "state/review_queue"
            ReviewShardStore(queue_path).write([_item(review_id="rv-current")])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = learn_main([
                    "--date", "2026-10-01", "--leaves-under", PARENT,
                    "--workspace", str(registry),
                ])
            self.assertEqual(code, 0)
            self.assertIn("跳过", output.getvalue())
            self.assertIn("rv-current", output.getvalue())
            items = ReviewShardStore(queue_path).load()
            self.assertEqual(
                {item.knowledge_point_id for item in items},
                {LEARNED_POINT, "math1.demo.chapter.item-b"},
            )
            ReviewShardStore(queue_path).write([
                *items, _item("math1.demo.chapter.item-b", "rv-second")
            ])
            before = _queue_bytes(queue_path)
            empty_output = io.StringIO()
            with contextlib.redirect_stdout(empty_output):
                code = learn_main([
                    "--date", "2026-10-01", "--leaves-under", PARENT,
                    "--workspace", str(registry),
                ])
            self.assertEqual(code, 2)
            self.assertIn("跳过", empty_output.getvalue())
            self.assertEqual(_queue_bytes(queue_path), before)

    def test_retired_item_reserves_base_id_and_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            queue_path = root / "state/review_queue"
            ReviewShardStore(queue_path).write([
                _item(LEARNED_POINT, f"rv-{LEARNED_POINT}", state="retired")
            ])
            before = _queue_bytes(queue_path)
            self.assertEqual(learn_main([
                "--date", "2026-10-01", "--knowledge-point", LEARNED_POINT,
                "--dry-run", "--workspace", str(registry),
            ]), 0)
            self.assertEqual(_queue_bytes(queue_path), before)
            self.assertEqual(learn_main([
                "--date", "2026-10-01", "--knowledge-point", LEARNED_POINT,
                "--workspace", str(registry),
            ]), 0)
            ids = {item.review_id for item in ReviewShardStore(queue_path).load()}
            self.assertIn(f"rv-{LEARNED_POINT}-2", ids)

    def test_learned_item_is_visible_to_review_questions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _workspace(root)
            self.assertEqual(learn_main([
                "--date", "2026-10-01", "--knowledge-point", LEARNED_POINT,
                "--workspace", str(registry),
            ]), 0)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = review_questions_main([
                    "--date", "2026-10-02", "--workspace", str(registry), "--json",
                ])
            self.assertEqual(code, 0)
            review = json.loads(output.getvalue())["reviews"][0]
            self.assertEqual(review["review_id"], f"rv-{LEARNED_POINT}")
            self.assertEqual(review["level"], "learned")


if __name__ == "__main__":
    unittest.main()
