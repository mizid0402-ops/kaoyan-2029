from __future__ import annotations

import unittest
import subprocess
import hashlib
import io
import math
import os
import shutil
import sys
import tarfile
import tempfile
import textwrap
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import yaml

from ky.freeze import FreezePolicy, assess_freeze, overdue_review_items
from ky.freeze.resume import plan_resume, resume_plan_to_mapping
from ky.models import load_config, load_review_items
from ky.planner.port import create_planner_input
from ky.schedule.planning import RoutePlan
from ky.schedule.state_snapshot import count_review_items_by_subject
from ky.storage.review_shards import ReviewShardStore
from ky.workspace import WORKSPACE_FILENAME, load_workspace

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "tests/fixtures/config/config-minimal.yaml"
REVIEWS = ROOT / "tests/fixtures/reviews/reviews-normal.yaml"
DAY = load_review_items(REVIEWS)[0].due_date + timedelta(days=3)
BASELINE = "81285d26cec32762755cabf2f667203366ae83d2"


class FreezeScheduledBacklogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG)
        self.base = load_review_items(REVIEWS)[0]

    def item(self, state: str, offset: int, minutes: int = 8):
        return replace(
            self.base, review_id=f"scheduled-{state}-{offset}", state=state,
            due_date=DAY + timedelta(days=offset), estimated_minutes=minutes,
        )

    def test_strict_date_boundary_and_shared_backlog_accounting(self) -> None:
        items = (
            self.item("scheduled", -1), self.item("scheduled", 0),
            self.item("scheduled", 1), self.item("queued", -1),
            self.item("retired", -1), self.item("suspended", -1),
        )
        overdue = overdue_review_items(DAY, items)
        self.assertEqual({item.state for item in overdue}, {"queued", "scheduled"})
        status = assess_freeze(DAY, self.config, items)
        counts = count_review_items_by_subject(items, DAY)
        self.assertEqual(status.overdue_minutes, sum(x.estimated_minutes for x in overdue))
        self.assertEqual(
            counts[self.base.subject_id].backlog_minutes,
            sum(x.estimated_minutes for x in overdue),
        )
        self.assertEqual(counts[self.base.subject_id].due_today_count, 0)
        exact = self.config.review_hard_cap_minutes() * FreezePolicy().backlog_days
        self.assertTrue(assess_freeze(
            DAY, self.config, (self.item("scheduled", -1, exact),),
        ).frozen)
        self.assertFalse(assess_freeze(DAY, self.config, ()).frozen)

    def test_resume_converts_scheduled_without_revision_change(self) -> None:
        scheduled = replace(
            self.item("scheduled", -1), revision=self.base.revision,
        )
        plan = plan_resume(
            DAY, self.config, (scheduled,), availability=None, route=None,
        )
        changed = plan.updated_items[0]
        self.assertEqual(changed.state, "queued")
        self.assertEqual(changed.revision, scheduled.revision)
        self.assertGreaterEqual(changed.due_date, DAY)
        self.assertEqual(changed.defer_count, 0)
        mapping = resume_plan_to_mapping(plan)
        self.assertEqual(mapping["scheduled_to_queued_count"], 1)

    def test_fixed_baseline_source_is_the_dispatch_commit(self) -> None:
        source = subprocess.run(
            ["git", "show", f"{BASELINE}:ky/freeze/port.py"], cwd=ROOT,
            capture_output=True, check=False,
        )
        self.assertEqual(source.returncode, 0, source.stderr.decode("utf-8", "replace"))
        old_port = source.stdout.decode("utf-8")
        self.assertIn("def overdue_review_items", old_port)
        self.assertIn('item.state == "queued"', old_port)
        self.assertNotIn('item.state in ("queued", "scheduled")', old_port)

    def test_preflight_bytes_match_fixed_baseline_without_overdue_scheduled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_root = root / "baseline"
            baseline_root.mkdir()
            archive = subprocess.run(
                ["git", "archive", BASELINE], cwd=ROOT,
                capture_output=True, check=False,
            )
            self.assertEqual(archive.returncode, 0, archive.stderr.decode("utf-8", "replace"))
            with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
                bundle.extractall(baseline_root)
            self.assertTrue((baseline_root / "ky/freeze/port.py").is_file())

            config_path = root / "config.yaml"
            shutil.copyfile(CONFIG, config_path)
            raw = yaml.safe_load(REVIEWS.read_text(encoding="utf-8"))
            latest_due = max(row["due_date"] for row in raw["items"])
            day = latest_due + timedelta(days=1)
            cases = {"queued": raw}
            cases["empty"] = {"schema_version": raw["schema_version"], "items": []}
            for offset in (0, 1):
                scheduled = yaml.safe_load(yaml.safe_dump(raw))
                for row in scheduled["items"]:
                    row["state"] = "scheduled"
                    row["due_date"] = day + timedelta(days=offset)
                cases[f"scheduled_{offset}"] = scheduled

            for name, payload in cases.items():
                items_path = root / f"{name}.yaml"
                items_path.write_text(
                    yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                for json_mode in (False, True):
                    args = [
                        "-m", "ky", "preflight", "--config", str(config_path),
                        "--items", str(items_path), "--date", day.isoformat(),
                    ]
                    if json_mode:
                        args.append("--json")
                    outcomes = []
                    for checkout in (baseline_root, ROOT):
                        result = _run_checkout(checkout, args, cwd=root)
                        outcomes.append((result.returncode, result.stdout, result.stderr))
                    self.assertEqual(
                        outcomes[0], outcomes[1],
                        f"preflight baseline mismatch: {name}/{json_mode}",
                    )

    def test_preflight_backlog_explanation_follows_freeze_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, _, workspace = _write_probe_workspace(Path(temporary), self.config)
            scheduled = tuple(
                replace(item, state="scheduled")
                for item in _overdue_items(self.base, self.config, DAY)
            )
            ReviewShardStore(workspace.review_queue).write(scheduled)
            result = _run_checkout(
                ROOT,
                ["-m", "ky", "preflight", "--config", "config.yaml",
                 "--items", "data/review_queue", "--date", DAY.isoformat()],
                cwd=workspace.root,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            minutes = sum(item.estimated_minutes for item in scheduled)
            explanation = (
                f"其中 {len(scheduled)} 项（{minutes} 分钟）为已过期的 scheduled "
                "（M9 列为 unreachable），已计入冻结积压；"
                "deferred -> backlog 一行只计本次裁剪延期。\r\n"
            ).encode("utf-8")
            frozen_line_end = result.stdout.index(b"FROZEN             :")
            frozen_line_end = result.stdout.index(b"\n", frozen_line_end) + 1
            self.assertEqual(
                result.stdout[frozen_line_end:frozen_line_end + len(explanation)],
                explanation,
            )

    def test_record_submit_and_resume_match_fixed_baseline_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_root = root / "baseline"
            baseline_root.mkdir()
            archive = subprocess.run(
                ["git", "archive", BASELINE], cwd=ROOT,
                capture_output=True, check=False,
            )
            self.assertEqual(archive.returncode, 0, archive.stderr.decode("utf-8", "replace"))
            with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
                bundle.extractall(baseline_root)
            config = load_config(CONFIG)
            plan = _empty_plan_mapping(config, DAY)
            plan.update({"available_minutes": config.default_daily_minutes})
            for command_case in ("record", "submit"):
                results = []
                saved = []
                for checkout in (baseline_root, ROOT):
                    run_root = root / f"{command_case}-{checkout.name}"
                    run_root.mkdir()
                    shutil.copyfile(CONFIG, run_root / "config.yaml")
                    if command_case == "record":
                        (run_root / "done.yaml").write_text(yaml.safe_dump({
                            "schema_version": 2, "day": DAY.isoformat(), "reviews": [],
                        }), encoding="utf-8")
                        args = ["-m", "ky", "day-plan", "record", "--config", "config.yaml",
                                "--done", "done.yaml", "--store", "plans"]
                    else:
                        (run_root / "plan.yaml").write_text(
                            yaml.safe_dump(plan), encoding="utf-8",
                        )
                        args = ["-m", "ky", "day-plan", "submit", "--config", "config.yaml",
                                "--plan", "plan.yaml", "--store", "plans"]
                    result = _run_checkout(checkout, args, cwd=run_root)
                    results.append((result.returncode, result.stdout, result.stderr))
                    saved.append(_workspace_hashes(run_root / "plans"))
                self.assertEqual(results[0], results[1], command_case)
                self.assertEqual(saved[0], saved[1], command_case)

            for dry_run in (False, True):
                for json_mode in (False, True):
                    outcomes = []
                    saved = []
                    for checkout in (baseline_root, ROOT):
                        run_root = root / f"resume-{checkout.name}-{dry_run}-{json_mode}"
                        run_root.mkdir()
                        shutil.copyfile(CONFIG, run_root / "config.yaml")
                        subjects = {
                            subject.subject_id: {"name": subject.display_name}
                            for subject in config.subjects
                        }
                        (run_root / "workspace.yaml").write_text(yaml.safe_dump({
                            "schema_version": 2, "subjects": subjects,
                            "reference": {
                                "knowledge_trees": {}, "exam_indexes": {},
                                "paper_shapes": {}, "topic_weights": "data/weights.json",
                                "weight_batches": "data/batches.yaml",
                                "vocabulary_db": "data/vocabulary.sqlite",
                                "ledger": "data/ledger.yaml",
                            },
                            "supplementary": {},
                            "materials": {"raw_root": "data/raw"}, "products": {},
                            "settings": {"exam_config": "config.yaml"},
                            "state": {"review_queue": "queue", "plans": "plans"},
                            "staging": "staging", "projection": "projection.sqlite",
                        }), encoding="utf-8")
                        args = ["-m", "ky", "resume", "--date", DAY.isoformat(),
                                "--config", "config.yaml", "--workspace", "workspace.yaml"]
                        if dry_run:
                            args.append("--dry-run")
                        if json_mode:
                            args.append("--json")
                        result = _run_checkout(checkout, args, cwd=run_root)
                        outcomes.append((result.returncode, result.stdout, result.stderr))
                        saved.append(_workspace_hashes(run_root / "plans"))
                    self.assertEqual(outcomes[0], outcomes[1], (dry_run, json_mode))
                    self.assertEqual(saved[0], saved[1], (dry_run, json_mode))

    def test_registered_freeze_and_nonempty_resume_match_fixed_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old_root = _extract_baseline(root)
            config_path, workspace_path, workspace = _write_probe_workspace(
                root / "probe", self.config,
            )
            items = _overdue_items(self.base, self.config, DAY)
            ReviewShardStore(workspace.review_queue).write(items)
            done_path = workspace.root / "done.yaml"
            done_path.write_text(yaml.safe_dump({
                "schema_version": 2, "day": DAY.isoformat(), "reviews": [],
            }), encoding="utf-8")
            plan_path = workspace.root / "plan.yaml"
            plan_path.write_text(yaml.safe_dump(_empty_plan_mapping(self.config, DAY)),
                                 encoding="utf-8")
            initial = _tree_bytes(workspace.root)

            for dry_run in (False, True):
                for json_mode in (False, True):
                    args = ["-m", "ky", "resume", "--date", DAY.isoformat(),
                            "--config", "config.yaml", "--workspace", "workspace.yaml"]
                    if dry_run:
                        args.append("--dry-run")
                    if json_mode:
                        args.append("--json")
                    old = _paired_command(
                        workspace.root, initial, old_root, args,
                    )
                    new = _paired_command(
                        workspace.root, initial, _new_checkout(), args,
                    )
                    self.assertEqual(old[0], new[0], (dry_run, json_mode))
                    self.assertEqual(old[1], new[1], (dry_run, json_mode))

            record_args = [
                "-m", "ky", "day-plan", "record", "--config", "config.yaml",
                "--done", "done.yaml", "--workspace", "workspace.yaml",
                "--store", "data/plans",
            ]
            for json_mode in (False, True):
                args = [*record_args, *( ["--json"] if json_mode else [])]
                old = _paired_command(workspace.root, initial, old_root, args)
                new = _paired_command(workspace.root, initial, _new_checkout(), args)
                self.assertEqual(old[0], new[0], ("record", json_mode))
                self.assertEqual(old[1], new[1], ("record", json_mode))

            submit_args = [
                "-m", "ky", "day-plan", "submit", "--plan", "plan.yaml",
                "--config", "config.yaml", "--workspace", "workspace.yaml",
                "--store", "data/plans",
            ]
            old = _paired_command(workspace.root, initial, old_root, submit_args)
            new = _paired_command(workspace.root, initial, _new_checkout(), submit_args)
            self.assertEqual(old[0], new[0], "submit --plan")
            self.assertEqual(old[1], new[1], "submit --plan")

    def test_m12_m15_mappings_match_fixed_baseline_for_four_queue_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old_root = _extract_baseline(root)
            config_path, workspace_path, workspace = _write_probe_workspace(
                root / "probe", self.config,
            )
            base_items = load_review_items(REVIEWS)
            cases = {
                "queued": tuple(
                    replace(item, state="queued", due_date=DAY - timedelta(days=1))
                    for item in base_items
                ),
                "empty": (),
                "scheduled_d": tuple(
                    replace(item, state="scheduled", due_date=DAY) for item in base_items
                ),
                "scheduled_d_plus_one": tuple(
                    replace(item, state="scheduled", due_date=DAY + timedelta(days=1))
                    for item in base_items
                ),
            }
            script = textwrap.dedent("""\
                import dataclasses, json, sys
                from datetime import date
                from ky.models import load_config
                from pathlib import Path
                from ky.projection import build_projection
                from ky.projection.status import status_as_of, status_to_mapping
                from ky.workspace import load_workspace
                from ky.schedule.state_snapshot import count_review_items_by_subject
                from ky.storage.review_shards import ReviewShardStore
                day = date.fromisoformat(sys.argv[1])
                projection = Path(sys.argv[2])
                # Each checkout builds its own projection: schema 5 (FSRS columns) is an
                # explicit, versioned exception, so an old reader cannot read a new build.
                build_projection(load_workspace(Path('workspace.yaml')), projection)
                config = load_config('config.yaml')
                items = ReviewShardStore('data/review_queue').load()
                counts = count_review_items_by_subject(items, day)
                result = {
                    'm12': {key: dataclasses.asdict(value) for key, value in counts.items()},
                    'm15': status_to_mapping(status_as_of(
                        projection, day, config,
                    )),
                }
                sys.stdout.write(json.dumps(result, sort_keys=True, separators=(',', ':')))
            """)
            for case, items in cases.items():
                with self.subTest(queue=case):
                    ReviewShardStore(workspace.review_queue).write(items)
                    before = _tree_bytes(workspace.root)
                    old = _paired_command(workspace.root, before, old_root, [
                        "-c", script, DAY.isoformat(), str(root / f"{case}-old.sqlite"),
                    ])
                    new = _paired_command(workspace.root, before, _new_checkout(), [
                        "-c", script, DAY.isoformat(), str(root / f"{case}-new.sqlite"),
                    ])
                    self.assertEqual(old[0], new[0], case)
                    self.assertEqual(old[1], new[1], case)

    def test_record_rejects_invalid_scheduled_subject_before_any_write(self) -> None:
        for subject_kind in ("inactive", "outside"):
            for with_review, explicit_store in (
                (False, False), (True, False), (True, True),
            ):
                with self.subTest(
                    subject_kind=subject_kind, with_review=with_review,
                    explicit_store=explicit_store,
                ):
                    fixture = _FreezeCliFixture(self.config, self.base)
                    self.addCleanup(fixture.close)
                    inactive_subject = next(
                        subject.subject_id for subject in fixture.config.subjects
                        if not subject.active
                    )
                    invalid_ids = (
                        inactive_subject,
                        f"outside-{fixture.config.subjects[0].subject_id}",
                    )
                    subject_id = invalid_ids[0 if subject_kind == "inactive" else 1]
                    items = tuple(
                        replace(item, state="scheduled", subject_id=subject_id)
                        for item in _overdue_items(fixture.base, self.config, DAY)
                    )
                    fixture.write_queue(items)
                    review_store = fixture.workspace.review_queue
                    if explicit_store:
                        review_store = fixture.root / "separate-review-store"
                        ReviewShardStore(review_store).write(items)
                    done_path = fixture.root / "invalid-done.yaml"
                    payload = {
                        "schema_version": 2, "day": DAY.isoformat(),
                        "reviews": ([{
                            "review_id": items[0].review_id,
                            "completed_on": DAY.isoformat(),
                            "check": "past_question", "outcome": "correct",
                        }] if with_review else []),
                    }
                    done_path.write_text(
                        yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8",
                    )
                    before = _workspace_hashes(fixture.root)
                    args = [
                        "day-plan", "record", "--config", str(fixture.config_path),
                        "--done", str(done_path), "--workspace",
                        str(fixture.workspace_path), "--store", str(fixture.workspace.plans),
                    ]
                    if explicit_store:
                        args.extend(("--review-store", str(review_store)))
                    result = fixture.run(*args)
                    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
                    self.assertIn(b"inactive subject" if subject_id == inactive_subject else
                                  b"not declared", result.stderr)
                    self.assertNotIn(b"Traceback", result.stderr)
                    self.assertEqual(_workspace_hashes(fixture.root), before)

    def test_submit_and_resume_reject_invalid_subject_before_any_write(self) -> None:
        fixture = _FreezeCliFixture(self.config, self.base)
        self.addCleanup(fixture.close)
        inactive_subject = next(
            subject.subject_id for subject in fixture.config.subjects if not subject.active
        )
        invalid_ids = (
            inactive_subject,
            f"outside-{fixture.config.subjects[0].subject_id}",
        )
        for subject_id in invalid_ids:
            for entry in ("submit-plan", "submit-staging", "resume"):
                with self.subTest(subject_id=subject_id, entry=entry):
                    items = tuple(
                        replace(item, state="scheduled", subject_id=subject_id)
                        for item in _overdue_items(fixture.base, self.config, DAY)
                    )
                    fixture.write_queue(fixture.base_items)
                    staged_path = (
                        fixture.workspace.write_target("staging")
                        / "day_plans" / "proposal.yaml"
                    )
                    if entry == "submit-staging":
                        _, input_hash = create_planner_input(
                            DAY, config_path=fixture.config_path,
                            workspace_path=fixture.workspace_path,
                        )
                        staged_path.parent.mkdir(parents=True, exist_ok=True)
                        staged_path.write_text(yaml.safe_dump({
                            "schema_version": 1, "kind": "day_plan_proposal",
                            "actor": "human", "input_hash": input_hash,
                            "plan": _empty_plan_mapping(fixture.config, DAY),
                        }), encoding="utf-8")
                    fixture.write_queue(items)
                    if entry == "submit-plan":
                        plan_path = fixture.root / "plan.yaml"
                        plan_path.write_text(yaml.safe_dump(
                            _empty_plan_mapping(fixture.config, DAY),
                        ), encoding="utf-8")
                    before = _workspace_hashes(fixture.root)
                    if entry == "submit-plan":
                        args = (
                            "day-plan", "submit", "--plan", str(plan_path), "--config",
                            str(fixture.config_path), "--workspace",
                            str(fixture.workspace_path), "--store", str(fixture.workspace.plans),
                        )
                    elif entry == "submit-staging":
                        args = (
                            "day-plan", "submit", "--from-staging", str(staged_path),
                            "--config", str(fixture.config_path), "--workspace",
                            str(fixture.workspace_path), "--store", str(fixture.workspace.plans),
                        )
                    else:
                        args = (
                            "resume", "--date", DAY.isoformat(), "--workspace",
                            str(fixture.workspace_path), "--config", str(fixture.config_path),
                        )
                    result = fixture.run(*args)
                    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
                    self.assertIn(b"inactive subject" if subject_id == inactive_subject else
                                  b"not declared", result.stderr)
                    self.assertNotIn(b"Traceback", result.stderr)
                    self.assertEqual(_workspace_hashes(fixture.root), before)


def _workspace_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def _overdue_items(base, config, day: date, minutes: int = 8):
    threshold = FreezePolicy().backlog_days * config.review_hard_cap_minutes()
    count = math.ceil(threshold / minutes)
    return tuple(
        replace(
            base, review_id=f"scheduled-backlog-{index}", state="queued",
            due_date=day - timedelta(days=1), estimated_minutes=minutes,
        )
        for index in range(count)
    )


class _FreezeCliFixture:
    """Small local CLI fixture to avoid collecting another unittest.TestCase."""

    def __init__(self, config, base) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="freeze-scheduled-test-"))
        self.config = config
        self.base = base
        self.base_items = load_review_items(REVIEWS)
        self.config_path = self.root / "config.yaml"
        shutil.copyfile(CONFIG, self.config_path)
        workspace_doc = {
            "schema_version": 2,
            "subjects": {
                subject.subject_id: {"name": subject.display_name}
                for subject in config.subjects
            },
            "reference": {
                "knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
                "topic_weights": "data/weights.json", "weight_batches": "data/batches.yaml",
                "vocabulary_db": "data/vocabulary.sqlite", "ledger": "data/ledger.yaml",
            },
            "supplementary": {}, "materials": {"raw_root": "data/raw"},
            "products": {}, "settings": {"exam_config": "config.yaml"},
            "state": {"review_queue": "data/review_queue", "plans": "data/plans"},
            "staging": "staging", "projection": "data/projection.sqlite",
        }
        self.workspace_path = self.root / WORKSPACE_FILENAME
        self.workspace_path.write_text(
            yaml.safe_dump(workspace_doc, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        self.workspace = load_workspace(self.workspace_path)

    def close(self) -> None:
        shutil.rmtree(self.root)

    def write_queue(self, items) -> None:
        ReviewShardStore(self.workspace.review_queue).write(items)

    def run(self, *args):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, "-m", "ky", *args], cwd=self.root,
            env=env, capture_output=True, check=False,
        )


def _empty_plan_mapping(config, day: date) -> dict[str, object]:
    return {
        "schema_version": 1, "day": day.isoformat(), "available_minutes": 0,
        "knowledge_minutes": 0, "vocab_minutes": 0, "vocab_new_items": 0,
        "phrase_minutes": 0, "backlog_minutes": 0,
        "subject_minutes": {subject.subject_id: 0 for subject in config.active_subjects()},
        "notes": "",
    }


def _extract_baseline(destination: Path) -> Path:
    source_root = destination / "baseline-source"
    source_root.mkdir()
    archive = subprocess.run(
        ["git", "archive", BASELINE], cwd=ROOT,
        capture_output=True, check=False,
    )
    if archive.returncode != 0:
        raise AssertionError(archive.stderr.decode("utf-8", "replace"))
    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
        bundle.extractall(source_root)
    old_port = (source_root / "ky/freeze/port.py").read_text(encoding="utf-8")
    if 'item.state == "queued"' not in old_port:
        raise AssertionError("baseline M27 no longer has the queued-only predicate")
    if 'item.state in ("queued", "scheduled")' in old_port:
        raise AssertionError("archive is not the pre-change D11 baseline")
    return source_root


def _write_probe_workspace(root: Path, config):
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "config.yaml"
    shutil.copyfile(CONFIG, config_path)
    data = root / "data"
    data.mkdir(exist_ok=True)
    (data / "topic_weights.json").write_text("{}\n", encoding="utf-8")
    (data / "vocabulary.sqlite").write_bytes(b"probe vocabulary bytes")
    (data / "raw").mkdir(exist_ok=True)
    workspace_doc = {
        "schema_version": 2,
        "subjects": {
            subject.subject_id: {"name": subject.display_name}
            for subject in config.subjects
        },
        "reference": {
            "knowledge_trees": {}, "exam_indexes": {}, "paper_shapes": {},
            "topic_weights": "data/topic_weights.json", "weight_batches": "data/batches.yaml",
            "vocabulary_db": "data/vocabulary.sqlite", "ledger": "data/ledger.yaml",
        },
        "supplementary": {}, "materials": {"raw_root": "data/raw"},
        "products": {}, "settings": {"exam_config": "config.yaml"},
        "state": {"review_queue": "data/review_queue", "plans": "data/plans"},
        "staging": "staging", "projection": "data/projection.sqlite",
    }
    workspace_path = root / "workspace.yaml"
    workspace_path.write_text(
        yaml.safe_dump(workspace_doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    from ky.workspace import load_workspace

    return config_path, workspace_path, load_workspace(workspace_path)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }


def _paired_command(root: Path, initial: dict[str, bytes], checkout: Path, args):
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for relative, content in initial.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(checkout)
    env["GIT_DIR"] = str(ROOT / ".git")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = _checkout_command(checkout, args)
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, check=False)
    triple = (result.returncode, result.stdout, result.stderr)
    return triple, _tree_bytes(root)


def _run_checkout(checkout: Path, args, *, cwd: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(checkout)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        _checkout_command(checkout, args), cwd=cwd, env=env,
        capture_output=True, check=False,
    )


def _checkout_command(checkout: Path, args) -> list[str]:
    source_check = (
        "from pathlib import Path; import ky; "
        f"expected = Path({str(checkout)!r}).resolve(); "
        "actual = Path(ky.__file__).resolve().parent.parent; "
        "assert actual == expected, f'ky source mismatch: {actual} != {expected}'; "
    )
    if args[:2] == ["-m", "ky"]:
        runner = (
            source_check
            + "import runpy, sys; "
            + f"sys.argv = ['ky', *{args[2:]!r}]; "
            + "runpy.run_module('ky.__main__', run_name='__main__', alter_sys=True)"
        )
        return [sys.executable, "-c", runner]
    if args and args[0] == "-c":
        return [sys.executable, "-c", source_check + args[1], *args[2:]]
    raise AssertionError(f"unsupported checkout command: {args!r}")


def _new_checkout() -> Path:
    return ROOT


if __name__ == "__main__":
    unittest.main()
