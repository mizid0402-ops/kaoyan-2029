from __future__ import annotations

import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import yaml

from ky.freeze.port import FreezeEvent, FreezePolicy, assess_freeze, latch_active
from ky.models import ContractError, load_config, load_review_items
from ky.projection import build_projection
from ky.projection.status import status_as_of, status_to_mapping
from ky.schedule.completion import CompletionEvent, VocabProgress
from ky.schedule.longitudinal import DayPlan
from ky.schedule.planning import Phase, RoutePlan
from ky.schedule.state_snapshot import build_snapshot
from ky.storage.day_plan_store import DayPlanStore
from ky.storage.review_shards import ReviewShardStore
from ky.storage.route_store import RoutePlanStore
from ky.workspace import WORKSPACE_FILENAME, load_workspace

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "b867ae7"
CONFIG_SOURCE = ROOT / "tests/fixtures/config/config-minimal.yaml"
REVIEWS_SOURCE = ROOT / "tests/fixtures/reviews/reviews-normal.yaml"


class ProjectionStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.config_path = self.root / "config.yaml"
        self.config_path.write_bytes(CONFIG_SOURCE.read_bytes())
        self.config = load_config(self.config_path)
        self.day = date.today()
        self.subjects = self.config.active_subjects()
        self.subject_id = self.subjects[0].subject_id
        self.point_id = f"{self.subject_id}.status.fixture"
        self.registry = self._write_registry(include_config=True)
        self.workspace = load_workspace(self.registry)
        self.output = self.workspace.projection
        self.items = self._items()
        ReviewShardStore(self.workspace.review_queue).write(self.items)
        plans = DayPlanStore(
            self.workspace.plans,
            subject_weights={subject.subject_id: subject.weight for subject in self.subjects},
        )
        plans.write_day_plan(DayPlan(
            day=self.day,
            available_minutes=90,
            subject_minutes={subject.subject_id: 0 for subject in self.subjects},
            backlog_minutes=0,
            notes="fixed plan data",
        ), actor="status-fixture", input_hash="a" * 64)
        plans.write_completion_event(CompletionEvent(self.day, vocab=VocabProgress()))
        event_days = (
            self.day - timedelta(days=3),
            self.day - timedelta(days=2),
            self.day - timedelta(days=1),
        )
        plans.write_freeze_record(event_days[0], self._freeze_mapping())
        plans.write_resume_record(event_days[1], {"resume": "ky resume"})
        plans.write_freeze_record(event_days[2], self._freeze_mapping())
        route = RoutePlan(
            "status-route", 1, self.day - timedelta(days=1),
            self.day + timedelta(days=20), "fixture", "b" * 64,
            (Phase(0, self.day - timedelta(days=1), self.day + timedelta(days=20),
                   "fixture phase", {subject.subject_id: 25 for subject in self.subjects}),),
        )
        RoutePlanStore(self.workspace.routes).write_route_plan(route)
        build_projection(self.workspace, self.output)

    def _write_registry(self, *, include_config: bool) -> Path:
        (self.data / "weights.json").write_text("{}\n", encoding="utf-8")
        (self.data / "vocabulary.sqlite").write_bytes(b"fixture vocabulary database")
        (self.data / "ledger.yaml").write_text("{}\n", encoding="utf-8")
        (self.data / "raw").mkdir(exist_ok=True)
        (self.data / "availability.yaml").write_text(yaml.safe_dump({
            "schema_version": 1, "days": {self.day.isoformat(): 42},
        }, sort_keys=False), encoding="utf-8")
        registry = {
            "schema_version": 2,
            "subjects": {subject.subject_id: {"name": subject.display_name}
                         for subject in self.config.subjects},
            "reference": {
                "knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
                "topic_weights": "data/weights.json",
                "vocabulary_db": "data/vocabulary.sqlite", "ledger": "data/ledger.yaml",
            },
            "supplementary": {}, "materials": {"raw_root": "data/raw"}, "products": {},
            "settings": {"exam_config": "config.yaml"} if include_config else {},
            "state": {
                "review_queue": "data/queue", "plans": "data/plans",
                "routes": "data/routes", "availability": "data/availability.yaml",
            },
            "staging": "staging", "projection": "data/projection.sqlite",
        }
        path = self.root / WORKSPACE_FILENAME
        path.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")
        return path

    def _items(self):
        source = load_review_items(REVIEWS_SOURCE)
        cases = (
            ("queued", self.day - timedelta(days=1)),
            ("queued", self.day),
            ("queued", self.day + timedelta(days=1)),
            ("scheduled", self.day),
        )
        return tuple(
            replace(
                source[index % len(source)],
                review_id=f"status-{index}", subject_id=self.subject_id,
                knowledge_point_id=self.point_id, due_date=due, state=state,
            )
            for index, (state, due) in enumerate(cases)
        )

    @staticmethod
    def _freeze_mapping() -> dict[str, object]:
        return {
            "overdue_minutes": 1, "overdue_count": 1, "threshold_minutes": 1,
            "backlog_days": 1, "latched": True, "resume": "ky resume",
        }

    def test_counts_freeze_sequence_read_only_and_past_as_of(self) -> None:
        before = self.output.read_bytes()
        status = status_as_of(self.output, self.day, self.config, FreezePolicy())
        after = self.output.read_bytes()
        self.assertEqual(before, after)

        snapshot = build_snapshot(self.config, self.items, today=self.day, tree_paths={})
        subject = snapshot.subject(self.subject_id)
        status_subject = next(row for row in status.subjects
                              if row.subject_id == self.subject_id)
        self.assertEqual(status_subject.counts.in_review_queue, subject.in_review_queue)
        self.assertEqual(status_subject.counts.due_today_count, subject.due_today_count)
        self.assertEqual(status_subject.counts.due_today_minutes, subject.due_today_minutes)
        self.assertEqual(status_subject.counts.backlog_minutes, subject.backlog_minutes)

        expected_events = (
            FreezeEvent(1, "freeze", self.day - timedelta(days=3)),
            FreezeEvent(2, "resume", self.day - timedelta(days=2)),
            FreezeEvent(3, "freeze", self.day - timedelta(days=1)),
        )
        self.assertTrue(latch_active(expected_events))
        self.assertEqual(status.freeze, assess_freeze(
            self.day, self.config, self.items, FreezePolicy(), latched=True,
        ))
        past = self.day - timedelta(days=20)
        past_status = status_as_of(self.output, past, self.config, FreezePolicy())
        self.assertEqual(past_status.as_of, past)
        self.assertTrue(past_status.freeze.latched)
        self.assertTrue(past_status.freeze.frozen)

        mapping = status_to_mapping(status)
        self.assertTrue(mapping["completion_event_exists"])
        self.assertEqual(mapping["availability_minutes"], 42)
        self.assertEqual(mapping["day_plan"]["actor"], "status-fixture")
        self.assertEqual(mapping["route_phase"]["label"], "fixture phase")
        self.assertIs(mapping["freeze"]["frozen"], True)
        self.assertIn("resume", mapping["freeze"])
        no_events_db = self.root / "empty-events.sqlite"
        with closing(sqlite3.connect(self.output)) as source, closing(
            sqlite3.connect(no_events_db)
        ) as target:
            source.backup(target)
        with closing(sqlite3.connect(no_events_db)) as connection:
            connection.execute("DELETE FROM freeze_events")
            connection.commit()
        not_frozen = status_to_mapping(status_as_of(
            no_events_db, self.day, self.config, FreezePolicy(),
        ))["freeze"]
        self.assertIs(not_frozen["frozen"], False)
        self.assertNotIn("resume", not_frozen)

        absent_day = self.day + timedelta(days=21)
        absent = status_to_mapping(status_as_of(
            self.output, absent_day, self.config, FreezePolicy(),
        ))
        self.assertIsNone(absent["day_plan"])
        self.assertIs(absent["completion_event_exists"], False)
        self.assertIsNone(absent["availability_minutes"])
        self.assertIsNone(absent["route_phase"])

    def test_missing_schema_and_out_of_config_queue_are_contract_errors(self) -> None:
        with self.assertRaises(ContractError) as missing:
            status_as_of(self.root / "missing.sqlite", self.day, self.config)
        self.assertIn("rebuild", str(missing.exception))

        # Schema 3 lacks exam_questions.paper_source (WP-M15-small); it must be rebuilt too.
        for old_version in ("2", "3"):
            with self.subTest(version=old_version):
                old = self.root / f"schema{old_version}.sqlite"
                with closing(sqlite3.connect(old)) as connection:
                    connection.execute("CREATE TABLE projection_meta (key TEXT, value TEXT)")
                    connection.execute("INSERT INTO projection_meta VALUES (?, ?)",
                                       ("projection_schema_version", old_version))
                    connection.commit()
                with self.assertRaises(ContractError) as wrong_version:
                    status_as_of(old, self.day, self.config)
                self.assertIn("schema version", str(wrong_version.exception))
                self.assertIn("rebuild", str(wrong_version.exception))

        missing_table = self.root / "missing-table.sqlite"
        with closing(sqlite3.connect(missing_table)):
            pass
        with self.assertRaises(ContractError) as wrong_shape:
            status_as_of(missing_table, self.day, self.config)
        self.assertIn("projection_meta", str(wrong_shape.exception))

        outside = replace(self.config, subjects=tuple(
            subject for subject in self.config.subjects
            if subject.subject_id != self.subject_id
        ))
        with self.assertRaises(ContractError):
            status_as_of(self.output, self.day, outside)

    def test_status_cli_config_selection_and_rebuild_output_baseline(self) -> None:
        no_config_registry = self._write_registry(include_config=False)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT) + os.pathsep + environment.get("PYTHONPATH", "")
        base_command = [sys.executable, "-m", "ky.projection", "status", "--date",
                        self.day.isoformat(), "--workspace", str(no_config_registry)]
        missing = subprocess.run(base_command + ["--json"], cwd=self.root, env=environment,
                                 capture_output=True, check=False)
        self.assertEqual(missing.returncode, 2, missing.stderr.decode("utf-8"))
        self.assertIn("settings.exam_config", missing.stderr.decode("utf-8"))

        configured = subprocess.run(base_command + ["--config", str(self.config_path), "--json"],
                                    cwd=self.root, env=environment, capture_output=True,
                                    check=False)
        self.assertEqual(configured.returncode, 0, configured.stderr.decode("utf-8"))
        self.assertEqual(json.loads(configured.stdout)["as_of"], self.day.isoformat())

        old = subprocess.run(
            ["git", "show", f"{BASELINE}:ky/projection/__main__.py"],
            cwd=ROOT, capture_output=True, check=False,
        )
        self.assertEqual(old.returncode, 0, old.stderr.decode("utf-8"))
        old_source = old.stdout.decode("utf-8")
        self.assertIn('print("projection rebuilt")', old_source)
        self.assertNotIn("status_as_of", old_source)
        spec = importlib.util.spec_from_loader("projection_cli_baseline", loader=None)
        baseline_module = importlib.util.module_from_spec(spec)
        exec(compile(old_source, f"{BASELINE}:ky/projection/__main__.py", "exec"),
             baseline_module.__dict__)
        from ky.projection.__main__ import main as current_main

        shared_output = self.root / "rebuild-output.sqlite"
        args = ["--workspace", str(self.registry), "--out", str(shared_output), "--json"]
        old_stdout, old_stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(old_stdout), redirect_stderr(old_stderr):
            self.assertEqual(baseline_module.main(args), 0, old_stderr.getvalue())
        current_args = ["--workspace", str(self.registry), "--out", str(shared_output), "--json"]
        new_stdout, new_stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(new_stdout), redirect_stderr(new_stderr):
            self.assertEqual(current_main(current_args), 0, new_stderr.getvalue())
        self.assertEqual(old_stdout.getvalue().encode("utf-8"),
                         new_stdout.getvalue().encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
