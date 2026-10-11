from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import yaml

from ky.models import ContractError, load_config, load_review_items
from ky.projection import PROJECTION_SCHEMA_VERSION, build_projection
from ky.schedule.completion import CompletionEvent, ReviewCompletion, VocabProgress
from ky.schedule.fsrs_algorithm import FsrsAlgorithm
from ky.schedule.longitudinal import DayPlan
from ky.schedule.planning import Phase, RoutePlan, route_plan_to_mapping
from ky.storage.day_plan_store import DayPlanStore
from ky.storage.review_shards import ReviewShardStore
from ky.storage.route_store import RoutePlanStore
from ky.workspace import WORKSPACE_FILENAME, load_workspace


ROOT = Path(__file__).resolve().parents[2]
CONFIG_SOURCE = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
REVIEWS_SOURCE = ROOT / "tests" / "fixtures" / "reviews" / "reviews-normal.yaml"
SCHEMA2_COMMIT = "b97f3ac"
LEARNING_TABLES = {
    "review_items", "day_plans", "day_plan_subject_minutes", "completion_events",
    "completion_reviews", "completion_vocab_words", "freeze_events", "route_phases",
    "route_phase_review_minutes", "availability_days",
}


class LearningStateProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config_path = self.root / "config.yaml"
        self.config_path.write_bytes(CONFIG_SOURCE.read_bytes())
        self.config = load_config(self.config_path)
        self.subject = self.config.active_subjects()[0].subject_id
        self.old_id = f"{self.subject}.projection.old"
        self.new_id = f"{self.subject}.projection.new"
        self.from_version = str(date.today().year - 1)
        self.to_version = str(date.today().year)
        self.registry = self._write_workspace(routes=True, availability=True)
        self.workspace = load_workspace(self.registry)
        self.output = self.root / "data" / "projection.sqlite"

    def _point(self, point_id: str) -> dict[str, object]:
        return {
            "schema_version": 1, "knowledge_point_id": point_id, "title": point_id,
            "status": "raw", "source_kind": "official_outline", "scope": "item",
            "sources": [{"path": "fixture", "sha256": "a" * 64, "locator": {"page": 1}}],
        }

    def _write_workspace(
        self, *, routes: bool, availability: bool = False, create_availability: bool = True,
    ) -> Path:
        data = self.root / "data"
        data.mkdir(exist_ok=True)
        tree_old = data / "tree-old.yaml"
        tree_new = data / "tree-new.yaml"
        tree_old.write_text(yaml.safe_dump({"schema_version": 1, "items": [
            self._point(self.old_id),
        ]}), encoding="utf-8")
        tree_new.write_text(yaml.safe_dump({"schema_version": 1, "items": [
            self._point(self.new_id),
        ]}), encoding="utf-8")
        mapping = {
            "schema_version": 1, "kind": "syllabus_mapping", "subject_id": self.subject,
            "from_version": self.from_version, "to_version": self.to_version,
            "basis": "projection contract fixture",
            "changes": [{"from": self.old_id, "to": [self.new_id]}], "added": [],
        }
        (data / "mapping.yaml").write_text(yaml.safe_dump(mapping), encoding="utf-8")
        (data / "weights.json").write_text("{}\n", encoding="utf-8")
        (data / "vocabulary.sqlite").write_bytes(b"fixture database bytes")
        (data / "ledger.yaml").write_text("{}\n", encoding="utf-8")
        (data / "raw").mkdir(exist_ok=True)
        doc = {
            "schema_version": 2,
            "subjects": {
                item.subject_id: {
                    "name": item.display_name,
                    **({"tree_grammar": "flat"} if item.subject_id == self.subject else {}),
                }
                for item in self.config.subjects
            },
            "reference": {
                "knowledge_trees": {self.subject: "data/tree-new.yaml"},
                "syllabus_versions": {self.subject: {
                    "versions": {
                        self.from_version: "data/tree-old.yaml",
                        self.to_version: "data/tree-new.yaml",
                    },
                    "mappings": ["data/mapping.yaml"],
                }},
                "exam_indexes": {}, "paper_shapes": {},
                "topic_weights": "data/weights.json", "vocabulary_db": "data/vocabulary.sqlite",
                "ledger": "data/ledger.yaml",
            },
            "supplementary": {}, "materials": {"raw_root": "data/raw"}, "products": {},
            "settings": {"exam_config": "config.yaml"},
            "state": {"review_queue": "data/queue", "plans": "data/plans"},
            "staging": "staging", "projection": "data/projection.sqlite",
        }
        if routes:
            doc["state"]["routes"] = "data/routes"
        if availability:
            doc["state"]["availability"] = "data/availability.yaml"
            if create_availability:
                availability = {
                    "schema_version": 1,
                    "days": {date.today().isoformat(): 45},
                }
                (data / "availability.yaml").write_text(
                    yaml.safe_dump(availability, sort_keys=False), encoding="utf-8",
                )
            else:
                (data / "availability.yaml").unlink(missing_ok=True)
        registry = self.root / WORKSPACE_FILENAME
        registry_text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
        registry.write_text(registry_text, encoding="utf-8")
        return registry

    def _item(self, review_id: str, *, point_id: str | None = None, due: date | None = None):
        source = load_review_items(REVIEWS_SOURCE)[0]
        return replace(
            source, review_id=review_id, subject_id=self.subject,
            knowledge_point_id=point_id or self.old_id, due_date=due or date.today(),
            last_reviewed_on=None, last_quality=None,
        )

    def _run(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT) + os.pathsep + environment.get("PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, "-m", "ky", *args], cwd=self.root, env=environment,
            capture_output=True, check=False,
        )

    def _rows(self, table: str) -> list[tuple]:
        with closing(sqlite3.connect(self.output)) as con:
            return con.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()

    def _assert_projected_review_item(self, item) -> None:
        columns = (
            "review_id", "revision", "state", "due_date", "last_reviewed_on",
            "schedule_mode", "schedule_phase", "interval_days", "ease_factor",
            "repetitions", "lapses", "stability", "difficulty", "fsrs_reviewed_on",
            "defer_count", "last_quality", "last_self_rating",
        )
        selected = ", ".join(columns)
        with closing(sqlite3.connect(self.output)) as con:
            con.row_factory = sqlite3.Row
            row = con.execute(
                f"SELECT {selected} FROM review_items WHERE review_id = ?",
                (item.review_id,),
            ).fetchone()
        self.assertIsNotNone(row, item.review_id)
        schedule = item.schedule
        expected = {
            "review_id": item.review_id,
            "revision": item.revision,
            "state": item.state,
            "due_date": item.due_date.isoformat(),
            "last_reviewed_on": (
                item.last_reviewed_on.isoformat() if item.last_reviewed_on else None
            ),
            "schedule_mode": schedule.mode,
            "schedule_phase": schedule.phase,
            "interval_days": schedule.interval_days,
            "ease_factor": schedule.ease_factor,
            "repetitions": schedule.repetitions,
            "lapses": schedule.lapses,
            "stability": schedule.stability,
            "difficulty": schedule.difficulty,
            "fsrs_reviewed_on": (
                schedule.fsrs_reviewed_on.isoformat()
                if schedule.fsrs_reviewed_on is not None else None
            ),
            "defer_count": item.defer_count,
            "last_quality": item.last_quality,
            "last_self_rating": item.last_self_rating,
        }
        self.assertEqual(dict(row), expected)

    def test_fsrs_memory_state_is_projected(self) -> None:
        item = FsrsAlgorithm().advance(
            self._item("fsrs-review"),
            ReviewCompletion(
                "fsrs-review", date.today(), "past_question", "correct"
            ),
        )
        ReviewShardStore(self.workspace.review_queue).write((item,))
        build_projection(self.workspace, self.output)
        self._assert_projected_review_item(item)

    def _plan(self, day: date) -> DayPlan:
        return DayPlan(day=day, available_minutes=0,
                       subject_minutes={item.subject_id: 0
                                        for item in self.config.active_subjects()},
                       notes="projection contract")

    def test_real_cli_writes_are_visible_after_rebuild(self) -> None:
        day = date.today()
        plan_path = self.root / "manual-plan.yaml"
        plan_mapping = {
            "schema_version": 1, "day": day.isoformat(), "available_minutes": 0,
            "knowledge_minutes": 0, "vocab_minutes": 0, "vocab_new_items": 0,
            "phrase_minutes": 0, "backlog_minutes": 0,
            "subject_minutes": {item.subject_id: 0
                                for item in self.config.active_subjects()},
            "notes": "submitted",
        }
        plan_path.write_text(yaml.safe_dump(plan_mapping, allow_unicode=True), encoding="utf-8")
        result = self._run(
            "day-plan", "submit", "--config", str(self.config_path), "--plan", str(plan_path),
            "--workspace", str(self.registry),
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        build_projection(self.workspace, self.output)
        self.assertEqual(self._rows("day_plans")[0][0], day.isoformat())
        self.assertEqual(self._rows("day_plans")[0][7], "submitted")

        queue = ReviewShardStore(self.workspace.review_queue)
        queue.write((self._item("recorded-review"),))
        record_before = queue.load()[0]
        done_path = self.root / "done.yaml"
        done_path.write_text(yaml.safe_dump({
            "schema_version": 2, "day": day.isoformat(),
            "reviews": [{"review_id": "recorded-review", "completed_on": day.isoformat(),
                         "check": "past_question", "outcome": "correct",
                         "question_ref": "fixture-question", "self_rating": "fluent",
                         "completion_id": "written-completion"}],
            "vocab": {"delivered_words": ["shown"], "practiced_words": ["practiced"]},
        }, sort_keys=False), encoding="utf-8")
        result = self._run(
            "day-plan", "record", "--config", str(self.config_path), "--done", str(done_path),
            "--workspace", str(self.registry), "--review-store", str(self.workspace.review_queue),
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        build_projection(self.workspace, self.output)
        self.assertEqual(self._rows("completion_reviews")[0][2], "written-completion")
        self.assertEqual(self._rows("completion_reviews")[0][3], "recorded-review")
        self.assertEqual({row[1] for row in self._rows("completion_vocab_words")},
                         {"delivered", "practiced"})
        record_after = queue.load()[0]
        self._assert_projected_review_item(record_after)
        self.assertNotEqual(record_after.due_date, record_before.due_date)
        self.assertNotEqual(record_after.last_reviewed_on, record_before.last_reviewed_on)
        self.assertNotEqual(record_after.schedule, record_before.schedule)

        route = RoutePlan(
            route_id="projection-route", revision=1, start_date=day,
            target_exam_date=day + timedelta(days=60), policy_version="policy-v1",
            stage1_input_hash="a" * 64,
            phases=(Phase(0, day, day + timedelta(days=60), "fixture-phase",
                          {item.subject_id: 30
                           for item in self.config.active_subjects()}),),
        )
        route_path = self.root / "route-plan.yaml"
        route_path.write_text(yaml.safe_dump(route_plan_to_mapping(route), sort_keys=False),
                              encoding="utf-8")
        result = self._run("route", "submit", "--plan", str(route_path),
                           "--workspace", str(self.registry))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        build_projection(self.workspace, self.output)
        self.assertEqual(self._rows("route_phases")[0][0], route.route_id)

        overdue = self._item("resume-review", due=day - timedelta(days=4))
        queue.write((overdue,))
        resume_before = queue.load()[0]
        result = self._run("resume", "--date", day.isoformat(), "--workspace", str(self.registry))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        build_projection(self.workspace, self.output)
        self.assertIn((1, "resume", day.isoformat()), self._rows("freeze_events"))
        resume_after = queue.load()[0]
        self._assert_projected_review_item(resume_after)
        self.assertNotEqual(resume_after.due_date, resume_before.due_date)

        queue.write((self._item("migration-review"),))
        result = self._run(
            "review-queue", "migrate", "--subject", self.subject, "--from", self.from_version,
            "--workspace", str(self.registry), "--apply",
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        build_projection(self.workspace, self.output)
        migrated = next(row for row in self._rows("review_items")
                        if row[0] == "migration-review")
        self.assertEqual(migrated[3], self.new_id)

    def test_missing_state_inputs_follow_registry_and_port_rules(self) -> None:
        build_projection(self.workspace, self.output)
        self.assertEqual(self._rows("review_items"), [])
        without_route = load_workspace(self._write_workspace(routes=False))
        build_projection(without_route, self.output)
        self.assertEqual(self._rows("route_phases"), [])
        with_missing_availability = load_workspace(
            self._write_workspace(routes=False, availability=True, create_availability=False)
        )
        with self.assertRaises(ContractError):
            build_projection(with_missing_availability, self.output)

    def test_invalid_state_preserves_existing_projection_bytes(self) -> None:
        queue = ReviewShardStore(self.workspace.review_queue)
        queue.write((self._item("invalid-source"),))
        build_projection(self.workspace, self.output)
        before = self.output.read_bytes()
        shard = next((self.workspace.review_queue / "shards").glob("*.yaml"))
        shard.write_bytes(shard.read_bytes() + b"# changed\n")
        with self.assertRaises(ContractError):
            build_projection(self.workspace, self.output)
        self.assertEqual(self.output.read_bytes(), before)

    def test_determinism_and_state_input_hashes_use_port_sources(self) -> None:
        day = date.today()
        weights = {item.subject_id: item.weight for item in self.config.active_subjects()}
        store = DayPlanStore(self.workspace.plans, subject_weights=weights)
        store.write_day_plan(self._plan(day), actor="fixture-v1")
        store.write_day_plan(replace(self._plan(day), notes="current"), actor="fixture-v2")
        store.write_completion_event(CompletionEvent(
            day, (ReviewCompletion("review", day, completion_id="completion"),),
            VocabProgress(("delivered",), ("practiced",)),
        ))
        store.write_freeze_record(day, {"latched": True})
        ReviewShardStore(self.workspace.review_queue).write((self._item("source-review"),))
        route_store = RoutePlanStore(self.workspace.write_target("state.routes"))
        first_route = RoutePlan(
            "state-route", 1, day, day + timedelta(days=30), "policy-v1", "b" * 64,
            (Phase(0, day, day + timedelta(days=30), "phase", {
                item.subject_id: 0 for item in self.config.active_subjects()
            }),),
        )
        route_store.write_route_plan(first_route)
        route_store.write_route_plan(replace(first_route, revision=2))
        first = self.root / "one.sqlite"
        second = self.root / "two.sqlite"
        build_projection(self.workspace, first)
        build_projection(self.workspace, second)
        self.assertEqual(self._database_contents(first), self._database_contents(second))
        with closing(sqlite3.connect(first)) as con:
            metadata = dict(con.execute("SELECT key, value FROM projection_meta"))
        state_inputs = json.loads(metadata["state_inputs"])
        self.assertEqual(list(state_inputs), sorted(state_inputs))
        roots = {
            "state.review_queue": self.workspace.review_queue,
            "state.plans": self.workspace.plans,
            "state.routes": self.workspace.routes,
            "state.availability": self.workspace.availability.parent,
        }
        for key, digest in state_inputs.items():
            registry_key, relative = key.split("/", 1)
            actual = hashlib.sha256((roots[registry_key] / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, digest)
        self.assertFalse(any(
            key.startswith("state.plans/") and "--v1.yaml" in key for key in state_inputs
        ))
        self.assertFalse(any(
            key.startswith("state.routes/") and "route--r1.yaml" in key
            for key in state_inputs
        ))
        self.assertEqual(metadata["freeze_events_latched"], "1")
        self.assertEqual(self._rows_from(first, "day_plans")[0][7], "current")
        self.assertEqual(self._rows_from(first, "route_phases")[0][1], 2)
        self.assertEqual(self._rows_from(first, "availability_days")[0][1], 45)

    def test_schema2_reference_tables_match_pinned_builder(self) -> None:
        old_source = subprocess.run(
            ["git", "show", f"{SCHEMA2_COMMIT}:ky/projection/__init__.py"],
            cwd=ROOT, capture_output=True, check=False,
        )
        self.assertEqual(old_source.returncode, 0, old_source.stderr.decode("utf-8"))
        source_text = old_source.stdout.decode("utf-8")
        self.assertIn("PROJECTION_SCHEMA_VERSION = 2", source_text)
        with tempfile.TemporaryDirectory() as temporary:
            baseline_path = Path(temporary) / "projection_schema2.py"
            baseline_path.write_text(source_text, encoding="utf-8")
            spec = importlib.util.spec_from_file_location(
                "projection_schema2_baseline", baseline_path
            )
            self.assertIsNotNone(spec)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            try:
                spec.loader.exec_module(module)
                old_db = Path(temporary) / "old.sqlite"
                new_db = Path(temporary) / "new.sqlite"
                module.build_projection(self.workspace, old_db)
                build_projection(self.workspace, new_db)
                self.assertEqual(self._reference_contents(old_db),
                                 self._reference_contents(new_db))
                with closing(sqlite3.connect(old_db)) as con:
                    version = con.execute(
                        "SELECT value FROM projection_meta WHERE key='projection_schema_version'"
                    ).fetchone()[0]
                    old_meta = dict(con.execute("SELECT key, value FROM projection_meta"))
                self.assertEqual(version, "2")
                with closing(sqlite3.connect(new_db)) as con:
                    new_meta = dict(con.execute("SELECT key, value FROM projection_meta"))
                self.assertEqual(
                    set(new_meta) - set(old_meta),
                    {"state_inputs", "freeze_events_latched"},
                )
                changed = {
                    key for key in old_meta
                    if old_meta[key] != new_meta[key]
                }
                self.assertEqual(changed, {"projection_schema_version"})
                self.assertEqual(
                    new_meta["projection_schema_version"], str(PROJECTION_SCHEMA_VERSION)
                )
            finally:
                sys.modules.pop(spec.name, None)

    def _database_contents(self, path: Path) -> dict[str, list[tuple]]:
        with closing(sqlite3.connect(path)) as con:
            tables = [row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )]
            return {table: self._rows_from(path, table) for table in tables}

    def _reference_contents(self, path: Path) -> dict[str, list[tuple]]:
        with closing(sqlite3.connect(path)) as con:
            tables = [row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name != 'projection_meta' "
                "ORDER BY name"
            )]
        return {table: self._rows_from(path, table) for table in tables
                if table not in LEARNING_TABLES}

    def _rows_from(self, path: Path, table: str) -> list[tuple]:
        with closing(sqlite3.connect(path)) as con:
            columns = con.execute(f"PRAGMA table_info({table})").fetchall()
            order = ", ".join(str(row[0] + 1) for row in columns)
            return con.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()


if __name__ == "__main__":
    unittest.main()
