from __future__ import annotations

import copy
import hashlib
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

from ky.knowledge.syllabus_mapping import SyllabusMapping, load_syllabus_mapping
from ky.models import ContractError, ReviewItem, ReviewSchedule
from ky.review.syllabus_migration import (
    check_queue_references,
    plan_queue_migration,
    resolve_mapping_chain,
)
from ky.storage.review_shards import ReviewShardStore
from ky.workspace import WORKSPACE_FILENAME, load_workspace
from tests.contract.test_workspace import BASE_DOCUMENT, _write_doc


SUBJECT = "cs408"
OLD = tuple(f"cs408.ds.chapter-01.section-{number:02d}" for number in range(1, 7))
NEW = tuple(f"cs408.ds.chapter-01.section-{number:02d}" for number in range(11, 17))


def mapping(source: str, target: str, old_ids: set[str], changes=None) -> SyllabusMapping:
    return SyllabusMapping(SUBJECT, source, target, changes or {}, frozenset(old_ids))


def item(review_id: str, point_id: str, *, subject: str = SUBJECT, due= date(2026, 10, 1),
         state: str = "queued") -> ReviewItem:
    return ReviewItem(
        review_id, 4, subject, point_id, f"Title {review_id}", "concept", state, 12,
        date(2026, 9, 1), due, date(2026, 9, 15),
        ReviewSchedule("fixed_bootstrap", 2, 5, 2.2, 1, 0), 3, 4, "basic",
    )


def run_ky(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ky", *args], cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, encoding="utf-8",
    )


class SyllabusMigrationPortTests(unittest.TestCase):
    def test_chain_resolution_single_two_step_and_same_version(self) -> None:
        first = mapping("2026", "2027", {OLD[0]})
        second = mapping("2027", "2028", {NEW[0]})
        self.assertEqual(resolve_mapping_chain([first], "2026", "2027"), (first,))
        self.assertEqual(resolve_mapping_chain([second, first], "2026", "2028"), (first, second))
        self.assertEqual(resolve_mapping_chain([first], "2026", "2026"), ())

    def test_chain_rejects_missing_multiple_duplicate_edges_and_cycles(self) -> None:
        first = mapping("2026", "2027", {OLD[0]})
        second = mapping("2027", "2028", {NEW[0]})
        alternatives = mapping("2026", "2028", {OLD[0]})
        cases = (
            ([first], "2026", "2028", "no mapping path"),
            ([first, second, alternatives], "2026", "2028", "multiple mapping paths"),
            ([first, first], "2026", "2027", "duplicate mapping edge"),
            ([first, mapping("2027", "2026", {NEW[0]})], "2026", "2027", "cycle"),
            ([first, first], "2026", "2026", "duplicate mapping edge"),
            ([first, mapping("2027", "2026", {NEW[0]})], "2026", "2026", "cycle"),
        )
        for mappings, start, end, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ContractError, message):
                resolve_mapping_chain(mappings, start, end)

    def test_migration_applies_keep_rename_split_delete_and_records(self) -> None:
        changes = {
            OLD[1]: (NEW[1],),
            OLD[2]: (NEW[2], NEW[3]),
            OLD[3]: (),
        }
        source = mapping("2026", "2027", set(OLD[:4]), changes)
        original = [item("keep", OLD[0]), item("rename", OLD[1]), item("split", OLD[2]),
                    item("delete", OLD[3])]
        plan = plan_queue_migration(original, [source], subject_id=SUBJECT)
        actual = {candidate.review_id: candidate for candidate in plan.items}
        self.assertEqual(actual["keep"], original[0])
        self.assertEqual(actual["rename"].knowledge_point_id, NEW[1])
        self.assertEqual(actual["rename"].revision, 5)
        self.assertEqual(actual["split"].state, "retired")
        self.assertEqual(actual["split"].revision, 5)
        for review_id, target in ((f"split>{NEW[2]}", NEW[2]), (f"split>{NEW[3]}", NEW[3])):
            split_item = actual[review_id]
            self.assertEqual(split_item.knowledge_point_id, target)
            self.assertEqual(split_item.due_date, original[2].due_date)
            self.assertEqual(split_item.schedule, original[2].schedule)
            self.assertEqual(split_item.introduced_on, original[2].introduced_on)
            self.assertEqual(split_item.last_reviewed_on, original[2].last_reviewed_on)
            self.assertEqual(split_item.last_quality, original[2].last_quality)
            self.assertEqual(split_item.estimated_minutes, original[2].estimated_minutes)
            self.assertEqual(split_item.revision, 1)
            self.assertEqual(split_item.defer_count, 0)
        self.assertEqual(actual["delete"].state, "retired")
        self.assertEqual(actual["delete"].revision, 5)
        self.assertEqual(plan.unchanged, ("keep",))
        self.assertEqual(plan.renamed, ("rename",))
        self.assertEqual(plan.split, ("split",))
        self.assertEqual(plan.retired, ("delete", "split"))

    def test_split_children_continue_through_next_mapping(self) -> None:
        first = mapping("2026", "2027", {OLD[0]}, {OLD[0]: (NEW[0], NEW[1])})
        child = "cs408.ds.chapter-01.section-07"
        second = mapping("2027", "2028", {NEW[0], NEW[1]}, {NEW[0]: (child,)})
        plan = plan_queue_migration([item("rv", OLD[0])], [first, second], subject_id=SUBJECT)
        active_items = {
            candidate.knowledge_point_id: candidate
            for candidate in plan.items if candidate.state != "retired"
        }
        active = set(active_items)
        self.assertEqual(active, {child, NEW[1]})
        self.assertEqual(active_items[child].review_id, f"rv>{NEW[0]}")
        self.assertEqual(active_items[child].revision, 2)
        self.assertEqual(active_items[NEW[1]].review_id, f"rv>{NEW[1]}")
        self.assertEqual(active_items[NEW[1]].revision, 1)

    def test_merge_dedup_uses_earliest_due_then_review_id(self) -> None:
        changes = {OLD[1]: (NEW[4],), OLD[2]: (NEW[4],), OLD[3]: (NEW[4],)}
        source = mapping("2026", "2027", set(OLD[:4]), changes)
        queue = [item("later", OLD[1], due=date(2026, 10, 2)),
                 item("early-z", OLD[2]), item("early-a", OLD[3])]
        plan = plan_queue_migration(queue, [source], subject_id=SUBJECT)
        by_id = {candidate.review_id: candidate for candidate in plan.items}
        self.assertEqual(by_id["early-a"].state, "queued")
        self.assertEqual(by_id["early-z"].state, "retired")
        self.assertEqual(by_id["early-z"].revision, 6)
        self.assertEqual(by_id["later"].state, "retired")
        self.assertEqual(plan.merged, ("early-z", "later"))
        self.assertEqual(plan.retired, ("early-z", "later"))

    def test_merge_prefers_queued_over_earlier_suspended_item(self) -> None:
        changes = {OLD[1]: (NEW[4],), OLD[2]: (NEW[4],)}
        source = mapping("2026", "2027", set(OLD[:3]), changes)
        queue = [item("suspended", OLD[1], due=date(2026, 9, 1), state="suspended"),
                 item("queued", OLD[2], due=date(2026, 10, 1), state="queued")]
        plan = plan_queue_migration(queue, [source], subject_id=SUBJECT)
        by_id = {candidate.review_id: candidate for candidate in plan.items}
        self.assertEqual(by_id["queued"].state, "queued")
        self.assertEqual(by_id["suspended"].state, "retired")

    def test_merge_prefers_queued_over_expired_scheduled_item(self) -> None:
        changes = {OLD[1]: (NEW[4],), OLD[2]: (NEW[4],)}
        source = mapping("2026", "2027", set(OLD[:3]), changes)
        queue = [item("expired-scheduled", OLD[1], due=date(2026, 9, 1), state="scheduled"),
                 item("queued", OLD[2], due=date(2026, 10, 1), state="queued")]
        plan = plan_queue_migration(queue, [source], subject_id=SUBJECT)
        by_id = {candidate.review_id: candidate for candidate in plan.items}
        self.assertEqual(by_id["queued"].state, "queued")
        self.assertEqual(by_id["expired-scheduled"].state, "retired")

    def test_dangling_ids_are_aggregated_and_foreign_and_retired_items_remain(self) -> None:
        source = mapping("2026", "2027", {OLD[0]})
        queue = [item("ghost-a", OLD[1]), item("ghost-b", OLD[2]),
                 item("other", OLD[1], subject="eng1"), item("dead", OLD[1], state="retired")]
        with self.assertRaisesRegex(ContractError, "ghost-a, ghost-b"):
            plan_queue_migration(queue, [source], subject_id=SUBJECT)
        no_migration = plan_queue_migration(queue[2:], [source], subject_id=SUBJECT)
        self.assertEqual({candidate.review_id: candidate for candidate in no_migration.items},
                         {candidate.review_id: candidate for candidate in queue[2:]})

    def test_split_id_collision_is_rejected(self) -> None:
        source = mapping("2026", "2027", set(OLD[:2]), {OLD[0]: (NEW[0], NEW[1])})
        queue = [item("rv", OLD[0]), item(f"rv>{NEW[0]}", OLD[1])]
        with self.assertRaisesRegex(ContractError, "collision"):
            plan_queue_migration(queue, [source], subject_id=SUBJECT)

    def test_reference_check_pass_fail_and_missing_tree(self) -> None:
        queue = [item("ok", OLD[0]), item("missing", OLD[1]),
                 item("no-tree", OLD[0], subject="eng1"), item("retired", OLD[1], state="retired")]
        problems = check_queue_references(queue, {SUBJECT: {OLD[0]}})
        self.assertEqual(len(problems), 2)
        self.assertIn("missing", problems[0])
        self.assertIn("该科无生效树", problems[1])
        self.assertEqual(check_queue_references([queue[0]], {SUBJECT: {OLD[0]}}), [])


class SyllabusMigrationCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        source_file = self.data / "outline.txt"
        source_file.write_text("outline", encoding="utf-8")
        digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
        self.old_ids = [f"cs408.ds.chapter-01.section-{n:02d}" for n in range(1, 7)]
        self.new_ids = [self.old_ids[0], *[f"cs408.ds.chapter-01.section-{n:02d}"
                                         for n in range(7, 12)]]
        self._write_tree("old.yaml", self.old_ids, digest)
        self._write_tree("new.yaml", self.new_ids, digest)
        document = copy.deepcopy(BASE_DOCUMENT)
        document["subjects"] = {
            SUBJECT: {"name": "CS408", "tree_grammar": "numbered_chapters"}
        }
        document["reference"]["knowledge_trees"] = {SUBJECT: "data/old.yaml"}
        document["reference"]["exam_indexes"] = {SUBJECT: ["data/index.json"]}
        document["supplementary"] = {}
        document["reference"]["syllabus_versions"] = {
            SUBJECT: {"versions": {"2026": "data/old.yaml", "2027": "data/new.yaml"},
                      "mappings": ["data/map.yaml"]}
        }
        self.registry_path = self.root / WORKSPACE_FILENAME
        self.registry_doc = document
        self.mapping_path = self.data / "map.yaml"
        map_doc = {
            "schema_version": 1, "kind": "syllabus_mapping", "subject_id": SUBJECT,
            "from_version": "2026", "to_version": "2027", "basis": "outline comparison",
            "changes": [
                {"from": self.old_ids[1], "to": [self.new_ids[1]]},
                {"from": self.old_ids[2], "to": [self.new_ids[2], self.new_ids[3]]},
                {"from": self.old_ids[3], "to": [self.new_ids[4]]},
                {"from": self.old_ids[4], "to": [self.new_ids[4]]},
                {"from": self.old_ids[5], "to": []},
            ],
            "added": [self.new_ids[5]],
        }
        self._write_yaml(self.mapping_path, map_doc)
        _write_doc(self.registry_path, document)
        self.workspace = load_workspace(self.registry_path)
        self.queue = self.data / "queue"
        self.store = ReviewShardStore(self.queue)
        self.items = [item(f"rv-{index}", point) for index, point in enumerate(self.old_ids)]
        self.store.write(self.items)

    def _write_yaml(self, path: Path, value: object) -> None:
        rendered = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
        path.write_text(rendered, encoding="utf-8")

    def _write_tree(self, name: str, ids: list[str], digest: str) -> None:
        nodes = [{
            "schema_version": 1, "knowledge_point_id": point_id, "title": point_id,
            "status": "raw", "source_kind": "official_outline",
            "sources": [{"path": "outline.txt", "sha256": digest,
                         "locator": {"quote_ref": "outline"}}], "scope": "section",
        } for point_id in ids]
        self._write_yaml(self.data / name, nodes)

    def _snapshot(self) -> dict[Path, bytes | None]:
        entries: dict[Path, bytes | None] = {self.queue: None}
        for path in self.queue.rglob("*"):
            entries[path] = path.read_bytes() if path.is_file() else None
        return entries

    def _cli(self, *args: str) -> subprocess.CompletedProcess:
        return run_ky(*args, "--workspace", str(self.registry_path), "--store", str(self.queue))

    def _cli_without_store(self, *args: str) -> subprocess.CompletedProcess:
        return run_ky(*args, "--workspace", str(self.registry_path))

    def test_end_to_end_registered_versions_apply_switch_check_and_snapshot(self) -> None:
        plan = self._cli("review-queue", "migrate", "--subject", SUBJECT, "--from", "2026",
                         "--to", "2027", "--apply")
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertIn("Applied", plan.stdout)
        migrated = self.store.load()
        self.assertTrue(any(candidate.state == "retired" for candidate in migrated), plan.stdout)
        self.registry_doc["reference"]["knowledge_trees"][SUBJECT] = "data/new.yaml"
        _write_doc(self.registry_path, self.registry_doc)
        checked = self._cli("review-queue", "check")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        config = self.root / "config.yaml"
        config_doc = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "fixtures/config/config-minimal.yaml")
            .read_text(encoding="utf-8")
        )
        config_doc["subjects"] = [{
            "subject_id": SUBJECT, "display_name": "CS408", "weight": 1.0,
            "active": True, "min_daily_minutes": 0,
        }]
        self._write_yaml(config, config_doc)
        snapshot = run_ky("snapshot", "--config", str(config), "--items", str(self.queue),
                          "--workspace", str(self.registry_path))
        self.assertEqual(snapshot.returncode, 0, snapshot.stderr)

    def test_dry_run_does_not_write_and_apply_writes(self) -> None:
        before = self._snapshot()
        dry = self._cli("review-queue", "migrate", "--subject", SUBJECT, "--from", "2026",
                        "--to", "2027")
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertEqual(self._snapshot(), before)
        applied = self._cli("review-queue", "migrate", "--subject", SUBJECT, "--from", "2026",
                            "--to", "2027", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertNotEqual(self._snapshot(), before)

    def test_check_uses_registered_default_store(self) -> None:
        result = self._cli_without_store("review-queue", "check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_migrate_uses_registered_default_store(self) -> None:
        result = self._cli_without_store(
            "review-queue", "migrate", "--subject", SUBJECT, "--from", "2026",
            "--to", "2027",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Migration plan", result.stdout)
        self.assertIn("分类可重叠", result.stdout)

    def test_apply_same_version_is_a_noop_without_manifest_write(self) -> None:
        before = self._snapshot()
        result = self._cli(
            "review-queue", "migrate", "--subject", SUBJECT, "--from", "2026",
            "--to", "2026", "--apply",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("无需迁移（from == to）", result.stdout)
        self.assertNotIn("Applied", result.stdout)
        self.assertEqual(self._snapshot(), before)

    def test_same_version_apply_still_checks_version_and_queue(self) -> None:
        # sol round 77, N1: the empty-chain shortcut must not skip the target checks.
        before = self._snapshot()
        cases = (("2099", "not registered"), ("2027", "不在科目"))
        for version, expected in cases:
            with self.subTest(version=version):
                result = self._cli("review-queue", "migrate", "--subject", SUBJECT,
                                   "--from", version, "--to", version, "--apply")
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn(expected, result.stderr)
                self.assertNotIn("无需迁移", result.stdout)
                self.assertEqual(self._snapshot(), before)

    def test_failed_reference_check_does_not_write(self) -> None:
        self.store.write([*self.items, item("foreign", "unknown", subject="eng1")])
        before = self._snapshot()
        result = self._cli("review-queue", "migrate", "--subject", SUBJECT,
                           "--from", "2026", "--to", "2027", "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self._snapshot(), before)

    def test_versions_registered_by_loader_match_each_mapping_tree(self) -> None:
        loaded = load_syllabus_mapping(self.mapping_path, self.workspace, subject_id=SUBJECT)
        self.assertEqual((loaded.from_version, loaded.to_version), ("2026", "2027"))


if __name__ == "__main__":
    unittest.main()
