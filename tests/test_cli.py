"""End-to-end CLI regression tests for ``py -m ky preflight``.

These spawn the real CLI as a subprocess so a failure mode that only shows up
in ``ky/__main__.py`` (an uncaught exception, a wrong exit code) cannot hide
behind unit tests that call the library functions directly. Run with:

    py -m unittest -v tests.test_cli
"""

from __future__ import annotations

import json
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ky.__main__ import SUBCOMMANDS, timetable_main
from ky.models import load_config
from ky.schedule.planning import Phase, RoutePlan
from ky.workspace import WORKSPACE_ENV, load_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
CONFIG_MINIMAL = FIXTURES / "config" / "config-minimal.yaml"
CONFIG_WEIGHTS_NOT_CLOSED = FIXTURES / "config" / "config-weights-not-closed.yaml"
REVIEWS_NORMAL = FIXTURES / "reviews" / "reviews-normal.yaml"

CONFIG_MINIMAL_TEXT = CONFIG_MINIMAL.read_text(encoding="utf-8")
LEGACY_CLI_REVISION = "0c3b3e54929a9b72aa740f410b7302e51b646f41"


def _legacy_cli_path(directory: Path) -> Path:
    result = subprocess.run(
        ["git", "show", f"{LEGACY_CLI_REVISION}:ky/__main__.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    source = result.stdout
    if b"workspace_not_found = (" not in source:
        raise AssertionError("git show did not return the expected legacy CLI source")
    legacy_path = directory / "legacy_main.py"
    legacy_path.write_bytes(source)
    return legacy_path


def run_raw_ky(
    args: list[str], *, legacy_main: Path | None = None, cwd: Path = REPO_ROOT,
    clear_workspace_env: bool = False,
):
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT) if not python_path else (
        str(REPO_ROOT) + os.pathsep + python_path
    )
    if clear_workspace_env:
        env.pop(WORKSPACE_ENV, None)
    command = (
        [sys.executable, str(legacy_main)] if legacy_main is not None
        else [sys.executable, "-m", "ky"]
    )
    return subprocess.run(command + args, cwd=cwd, env=env, capture_output=True)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ky", "preflight", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def run_ky(*args: str) -> subprocess.CompletedProcess:
    """Like run_cli, but without forcing the `preflight` subcommand -- for snapshot/day-plan/
    month-close."""
    return subprocess.run(
        [sys.executable, "-m", "ky", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def run_ky_at(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else (
        str(REPO_ROOT) + os.pathsep + existing_pythonpath
    )
    return subprocess.run(
        [sys.executable, "-m", "ky", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _tree_files(root: Path) -> dict:
    if not root.is_dir():
        return {}
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class CliContractTest(unittest.TestCase):
    def test_normal_fixtures_exit_0(self) -> None:
        result = run_cli(
            "--config", str(CONFIG_MINIMAL),
            "--items", str(REVIEWS_NORMAL),
            "--date", "2026-09-12",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_preflight_json_is_identical_for_flat_and_sharded_review_queues(self) -> None:
        from ky.models import load_review_items
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "review-queue" / "manifest.yaml"
            ReviewShardStore(manifest.parent).write(load_review_items(REVIEWS_NORMAL))
            flat = run_cli(
                "--config", str(CONFIG_MINIMAL), "--items", str(REVIEWS_NORMAL),
                "--date", "2026-09-12", "--json",
            )
            sharded = run_cli(
                "--config", str(CONFIG_MINIMAL), "--items", str(manifest.parent),
                "--date", "2026-09-12", "--json",
            )
            manifest_file = run_cli(
                "--config", str(CONFIG_MINIMAL), "--items", str(manifest),
                "--date", "2026-09-12", "--json",
            )

        for result in (flat, sharded, manifest_file):
            self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(flat.stdout.encode("utf-8"), sharded.stdout.encode("utf-8"))
        self.assertEqual(flat.stdout.encode("utf-8"), manifest_file.stdout.encode("utf-8"))

    def test_preflight_empty_review_store_is_contract_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty_queue = Path(tmp) / "empty-queue"
            empty_queue.mkdir()
            result = run_cli(
                "--config", str(CONFIG_MINIMAL), "--items", str(empty_queue),
                "--date", "2026-09-12", "--json",
            )

        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("contract violation:"), result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_weights_not_closed_exits_2(self) -> None:
        result = run_cli(
            "--config", str(CONFIG_WEIGHTS_NOT_CLOSED),
            "--items", str(REVIEWS_NORMAL),
            "--date", "2026-09-12",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("contract violation", result.stderr)

    def test_misspelled_config_field_exits_2_not_silently_accepted(self) -> None:
        # min_daily_minute (missing the trailing 's') must be rejected, not
        # silently ignored and defaulted to 0 -- this is the exact M1
        # regression Codex's round-3 review demanded.
        with tempfile.TemporaryDirectory() as tmp:
            bad_config = Path(tmp) / "config-typo.yaml"
            bad_config.write_text(
                CONFIG_MINIMAL_TEXT.replace("min_daily_minutes: 15", "min_daily_minute: 15"),
                encoding="utf-8",
            )
            result = run_cli(
                "--config", str(bad_config),
                "--items", str(REVIEWS_NORMAL),
                "--date", "2026-09-12",
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("min_daily_minute", result.stderr)

    def test_unsupported_reviews_schema_version_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_reviews = Path(tmp) / "reviews-bad-version.yaml"
            bad_reviews.write_text("schema_version: 99\nitems: []\n", encoding="utf-8")
            result = run_cli(
                "--config", str(CONFIG_MINIMAL),
                "--items", str(bad_reviews),
                "--date", "2026-09-12",
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("schema_version", result.stderr)

    def test_urgent_overdue_days_zero_is_a_controlled_usage_error(self) -> None:
        # ReviewPolicy(urgent_overdue_days=0) raises ValueError; the CLI must
        # turn that into a documented exit-3 usage error, not let it surface
        # as an unhandled traceback (which used to exit 1).
        result = run_cli(
            "--config", str(CONFIG_MINIMAL),
            "--items", str(REVIEWS_NORMAL),
            "--date", "2026-09-12",
            "--urgent-overdue-days", "0",
        )
        self.assertEqual(result.returncode, 3)
        self.assertNotIn("Traceback", result.stderr)

    def test_an_astronomically_large_usage_value_does_not_traceback(self) -> None:
        # The CLI validates each --usage value as a non-negative int and
        # nothing more, so a caller can hand it a number far outside the float
        # range. That used to reach _deficit_ratio's float() conversion and
        # escape as an uncaught OverflowError traceback with exit code 1 --
        # not one of the four documented outcomes. Spawned as a real
        # subprocess because the bug was only visible at the process boundary.
        with tempfile.TemporaryDirectory() as tmp:
            usage = Path(tmp) / "usage.json"
            usage.write_text(json.dumps({"math1": 10**400}), encoding="utf-8")
            result = run_cli(
                "--config", str(CONFIG_MINIMAL),
                "--items", str(REVIEWS_NORMAL),
                "--date", "2026-09-12",
                "--usage", str(usage),
            )
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_duplicate_config_field_exits_2_not_silently_last_wins(self) -> None:
        # YAML resolves a repeated key to the last occurrence, so this file
        # used to load as a 30-minute day with the declared 120 discarded and
        # no diagnostic at all.
        with tempfile.TemporaryDirectory() as tmp:
            bad_config = Path(tmp) / "config-dup.yaml"
            bad_config.write_text(
                CONFIG_MINIMAL_TEXT.replace(
                    "default_daily_minutes: 120",
                    "default_daily_minutes: 120\ndefault_daily_minutes: 30",
                ),
                encoding="utf-8",
            )
            result = run_cli(
                "--config", str(bad_config),
                "--items", str(REVIEWS_NORMAL),
                "--date", "2026-09-12",
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate field", result.stderr)
        self.assertIn("default_daily_minutes", result.stderr)

    def test_unknown_subject_id_in_items_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_reviews = Path(tmp) / "reviews-ghost.yaml"
            bad_reviews.write_text(
                "schema_version: 1\n"
                "items:\n"
                "  - review_id: rv_ghost\n"
                "    revision: 1\n"
                "    subject_id: ghost\n"
                "    knowledge_point_id: ghost.demo\n"
                "    title: ghost\n"
                "    granularity: concept\n"
                "    state: queued\n"
                "    estimated_minutes: 10\n"
                "    introduced_on: 2026-09-01\n"
                "    due_date: 2026-09-12\n"
                "    schedule:\n"
                "      mode: fixed_bootstrap\n"
                "      phase: 1\n"
                "      interval_days: 3\n"
                "      ease_factor: 2.5\n"
                "      repetitions: 1\n"
                "      lapses: 0\n"
                "    defer_count: 0\n"
                "    last_quality: 4\n",
                encoding="utf-8",
            )
            result = run_cli(
                "--config", str(CONFIG_MINIMAL),
                "--items", str(bad_reviews),
                "--date", "2026-09-12",
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("ghost", result.stderr)
        self.assertIn("not declared in config.subjects", result.stderr)


def _registry_with_queue(workspace_root: Path, queue: str) -> Path:
    """A minimal registry (no trees) whose state.review_queue is ``queue``."""
    import yaml as _yaml

    source = _yaml.safe_load((REPO_ROOT / "kaoyan.workspace.yaml").read_text(encoding="utf-8"))
    source["reference"]["knowledge_trees"] = {}
    source["reference"].pop("syllabus_versions", None)
    source["state"] = {"review_queue": queue, "plans": "data/plans"}
    workspace_root.mkdir(parents=True, exist_ok=True)
    registry = workspace_root / "kaoyan.workspace.yaml"
    registry.write_text(_yaml.safe_dump(source, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")
    return registry


class CliTopLevelHelpTest(unittest.TestCase):
    def test_top_level_help_lists_the_registered_commands(self) -> None:
        for option in ("-h", "--help"):
            with self.subTest(option=option):
                result = run_ky(option)
                self.assertEqual(result.returncode, 0, result.stderr)
                lines = result.stdout.splitlines()
                for name, (_, description) in SUBCOMMANDS.items():
                    self.assertIn(f"  {name:<14} {description}", lines)


class TimetableCliTest(unittest.TestCase):
    def test_week_grid_applies_no_class_and_follow_exceptions(self) -> None:
        # sol round 224 R1: the grid shows each date's resolved classes, like the minutes row.
        import yaml

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _registry_with_queue(root, "data/review_queue")
            document = yaml.safe_load(registry.read_text(encoding="utf-8"))
            document["reference"]["timetable_schools"] = {"demo": "data/demo.yaml"}
            document["state"]["timetable"] = "data/timetable.yaml"
            registry.write_text(
                yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8",
            )
            (root / "data").mkdir(parents=True, exist_ok=True)
            (root / "data" / "demo.yaml").write_text(
                "schema_version: 1\nschool_id: demo\nname: Demo\nsystem: demo\n"
                "source:\n  kind: official\n  recorded_on: 2026-09-30\n"
                "periods:\n  1: {start: '09:00', end: '10:00'}\nblocks: [[1]]\n",
                encoding="utf-8",
            )
            (root / "data" / "timetable.yaml").write_text(
                "schema_version: 1\nrules:\n  study_window: {start: '08:00', end: '12:00'}\n"
                "  buffer_minutes: 0\n  min_gap_minutes: 0\n"
                "  block_deduction_minutes: 30\n  daily_cap_minutes: 120\n"
                "semesters:\n  - label: demo-term\n    school: demo\n"
                "    week1_monday: 2025-09-01\n    weeks: 2\n    courses:\n"
                "      - {name: CourseA, weekday: 1, periods: '1', weeks: '1'}\n"
                "      - {name: CourseB, weekday: 3, periods: '1', weeks: '2'}\n"
                "    exceptions:\n"
                "      - {date: 2025-09-01, kind: no_class}\n"
                "      - {date: 2025-09-02, kind: follow, follow: 2025-09-10}\n",
                encoding="utf-8",
            )
            week = run_ky_at(
                root, "timetable", "show", "--week", "1",
                "--config", str(CONFIG_MINIMAL), "--workspace", str(registry),
            )
            self.assertEqual(week.returncode, 0, week.stderr)
            first_row = next(
                line for line in week.stdout.splitlines() if line.lstrip().startswith("1 ")
            )
            self.assertIn("周一 - | 周二 CourseB | 周三 -", first_row)
            self.assertNotIn("CourseA", week.stdout)
            self.assertIn("minutes            : 120 90 120 120 120 120 120", week.stdout)

    def test_timetable_show_check_and_usage_paths(self) -> None:
        import yaml

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = _registry_with_queue(root, "data/review_queue")
            document = yaml.safe_load(registry.read_text(encoding="utf-8"))
            document["reference"]["timetable_schools"] = {"demo": "data/demo.yaml"}
            document["state"]["timetable"] = "data/timetable.yaml"
            school_path = root / "data" / "demo.yaml"
            school_path.parent.mkdir(parents=True, exist_ok=True)
            school_path.write_text(
                "schema_version: 1\nschool_id: demo\nname: Demo\nsystem: demo\n"
                "source:\n  kind: official\n  recorded_on: 2026-09-30\n"
                "periods:\n  1: {start: '08:00', end: '08:45', unconfirmed: true}\n"
                "blocks: [[1]]\n",
                encoding="utf-8",
            )
            timetable_path = root / "data" / "timetable.yaml"
            timetable_path.write_text(
                "schema_version: 1\nrules:\n  study_window: {start: '08:00', end: '22:00'}\n"
                "  buffer_minutes: 0\n  min_gap_minutes: 0\n"
                "  block_deduction_minutes: 0\n  daily_cap_minutes: 75\n"
                "semesters:\n  - label: first\n    school: demo\n"
                "    week1_monday: 2025-09-01\n    weeks: 1\n    courses:\n"
                "      - {name: Course, weekday: 1, periods: '1', weeks: '1'}\n"
                "      - {name: Conflict, weekday: 1, periods: '1', weeks: '1'}\n",
                encoding="utf-8",
            )
            valid_timetable = timetable_path.read_bytes()
            registry.write_text(
                yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            config_args = ("--config", str(CONFIG_MINIMAL), "--workspace", str(registry))

            week = run_ky_at(root, "timetable", "show", "--week", "1", *config_args)
            self.assertEqual(week.returncode, 0, week.stderr)
            self.assertIn("Course", week.stdout)
            self.assertIn("08:00-08:45", week.stdout)
            self.assertIn("*", week.stdout)

            shown = run_ky_at(
                root, "timetable", "show", "--date", "2025-09-01", *config_args
            )
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertIn("Course", shown.stdout)
            self.assertIn("unconfirmed", shown.stdout)

            preflight = run_ky_at(
                root,
                "preflight",
                "--config",
                str(CONFIG_MINIMAL),
                "--items",
                str(REVIEWS_NORMAL),
                "--workspace",
                str(registry),
                "--date",
                "2025-09-01",
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            summary = preflight.stdout.splitlines()
            budget_row = summary.index("daily budget       : 75 min")
            self.assertIn("first 第 1 周 星期一", summary[budget_row + 1])
            self.assertIn("含待确认节次 1", summary[budget_row + 1])

            outside = run_ky_at(
                root, "timetable", "show", "--date", "2025-09-08", *config_args
            )
            self.assertEqual(outside.returncode, 0, outside.stderr)
            self.assertIn("课表不覆盖此日", outside.stdout)

            no_registry_timetable = dict(document)
            no_registry_timetable["state"] = {
                key: value for key, value in document["state"].items()
                if key != "timetable"
            }
            no_timetable_registry = root / "no-timetable.workspace.yaml"
            no_timetable_registry.write_text(
                yaml.safe_dump(no_registry_timetable, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            unregistered = run_ky_at(
                root,
                "timetable", "show", "--date", "2025-09-01",
                "--config", str(CONFIG_MINIMAL), "--workspace", str(no_timetable_registry),
            )
            self.assertEqual(unregistered.returncode, 0, unregistered.stderr)
            self.assertIn("课表不覆盖此日", unregistered.stdout)

            missing_selector = run_ky_at(
                root, "timetable", "show", "--config", str(CONFIG_MINIMAL),
                "--workspace", str(registry),
            )
            both_selectors = run_ky_at(
                root, "timetable", "show", "--week", "1", "--date", "2025-09-01",
                *config_args,
            )
            self.assertEqual(missing_selector.returncode, 3)
            self.assertEqual(both_selectors.returncode, 3)

            for args in (
                ("--week", "2"),
                ("--week", "1", "--semester", "missing"),
            ):
                result = run_ky_at(
                    root, "timetable", "show", *args, *config_args
                )
                self.assertEqual(result.returncode, 3, result.stderr)

            multiple = yaml.safe_load(timetable_path.read_text(encoding="utf-8"))
            multiple["semesters"].append({
                **multiple["semesters"][0],
                "label": "second",
                "week1_monday": "2026-01-05",
            })
            timetable_path.write_text(
                yaml.safe_dump(multiple, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            registry.write_text(
                yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            ambiguous = run_ky_at(
                root, "timetable", "show", "--week", "1", *config_args
            )
            self.assertEqual(ambiguous.returncode, 3, ambiguous.stderr)
            selected = run_ky_at(
                root,
                "timetable", "show", "--week", "1", "--semester", "second",
                *config_args,
            )
            self.assertEqual(selected.returncode, 0, selected.stderr)

            checked = run_ky_at(
                root, "timetable", "check", "--workspace", str(registry)
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn("course overlap", checked.stdout)
            self.assertIn("unconfirmed periods", checked.stdout)

            timetable_path.write_text("schema_version: 2\n", encoding="utf-8")
            invalid_timetable = run_ky_at(
                root,
                "timetable", "show", "--date", "2025-09-01", *config_args,
            )
            self.assertEqual(invalid_timetable.returncode, 2)
            timetable_path.write_bytes(valid_timetable)

            check_without_timetable = run_ky_at(
                root, "timetable", "check", "--workspace", str(no_timetable_registry)
            )
            self.assertEqual(
                check_without_timetable.returncode, 0, check_without_timetable.stderr
            )

            empty = dict(multiple)
            empty["semesters"] = []
            timetable_path.write_text(
                yaml.safe_dump(empty, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            no_terms = run_ky_at(
                root, "timetable", "show", "--week", "1", *config_args
            )
            self.assertEqual(no_terms.returncode, 3, no_terms.stderr)

            candidate = run_ky_at(
                root,
                "timetable", "check", "--school", str(school_path),
                "--workspace", str(root / "missing-registry.yaml"),
            )
            self.assertEqual(candidate.returncode, 0, candidate.stderr)
            self.assertIn("OK school profile", candidate.stdout)
            invalid_candidate_path = root / "bad-school.yaml"
            invalid_candidate_path.write_text("schema_version: false\n", encoding="utf-8")
            invalid_candidate = run_ky_at(
                root, "timetable", "check", "--school", str(invalid_candidate_path)
            )
            self.assertEqual(invalid_candidate.returncode, 2)


class TimetableRouteBaseTests(unittest.TestCase):
    def test_show_uses_the_requested_day_base_and_each_weeks_phase_base(self) -> None:
        config = load_config(CONFIG_MINIMAL)
        subject_id = config.active_subjects()[0].subject_id
        monday = date.today() - timedelta(days=date.today().weekday())
        wednesday = monday + timedelta(days=2)
        sunday = monday + timedelta(days=6)
        route = RoutePlan(
            route_id="synthetic-route", revision=1, start_date=monday,
            target_exam_date=sunday + timedelta(days=1), policy_version="test",
            stage1_input_hash="0" * 64,
            phases=(
                Phase(0, monday, wednesday, "first", {subject_id: 0}, 180),
                Phase(
                    1, wednesday, sunday + timedelta(days=1), "second",
                    {subject_id: 0}, 240,
                ),
            ),
        )

        class Timetable:
            def __init__(self):
                self.calls = []
                self.timetable = SimpleNamespace(semesters=(SimpleNamespace(
                    label="term", weeks=1, week1_monday=monday, school="school",
                ),))
                self.schools = {"school": SimpleNamespace(periods={})}

            def day(self, day, base_minutes):
                self.calls.append((day, base_minutes))
                return SimpleNamespace(
                    classes=(), free_segments=(), blocks=3, cap=base_minutes,
                    minutes=base_minutes - 45, unconfirmed_periods=(),
                )

        timetable = Timetable()
        current_reads = []
        workspace = SimpleNamespace(
            routes=Path("routes"), write_target=lambda _key: Path("routes"),
        )
        current_route_store = SimpleNamespace(current=lambda: current_reads.append(route) or route)

        def run(args):
            parser = SimpleNamespace(parse_args=lambda _argv: args)
            output = io.StringIO()
            with (
                patch("ky.__main__._reconfigure_streams_utf8"),
                patch("ky.__main__._timetable_parser", return_value=parser),
                patch("ky.__main__._discovered_workspace", return_value=workspace),
                patch("ky.__main__.load_config", return_value=config),
                patch("ky.__main__.timetable_for_workspace", return_value=timetable),
                patch("ky.__main__.RoutePlanStore", return_value=current_route_store),
                patch("ky.__main__._timetable_print_grid"),
                redirect_stdout(output),
            ):
                status = timetable_main([])
            self.assertEqual(status, 0)
            return output.getvalue()

        date_args = SimpleNamespace(
            action="show", date=(monday + timedelta(days=1)).isoformat(), week=None,
            semester=None, config="config", workspace=None,
        )
        date_output = run(date_args)
        self.assertIn("cap                : 180", date_output)
        self.assertIn("minutes            : 135", date_output)
        self.assertEqual(timetable.calls, [(monday + timedelta(days=1), 180)])
        self.assertEqual(len(current_reads), 1)

        timetable.calls.clear()
        week_args = SimpleNamespace(
            action="show", date=None, week=1, semester=None,
            config="config", workspace=None,
        )
        run(week_args)
        self.assertEqual(
            timetable.calls,
            [(monday + timedelta(days=i), 180 if i < 2 else 240) for i in range(7)],
        )
        self.assertEqual(len(current_reads), 2)


class CliLegacyOutputTest(unittest.TestCase):
    @staticmethod
    def _without_freeze_help_block(output: bytes) -> bytes:
        start = output.index(b"  --freeze-backlog-days")
        end = output.index(b"  --json", start)
        return output[:start] + output[end:]

    def test_preflight_and_argument_errors_match_fixed_legacy_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            legacy_main = _legacy_cli_path(Path(tmp))
            cases = (
                ["preflight", "-h"],
                ["--date", "2026-09-15", "-h"],
                [],
                ["unknown-subcommand"],
                ["--unknown-option"],
            )
            for args in cases:
                with self.subTest(args=args):
                    old = run_raw_ky(args, legacy_main=legacy_main)
                    new = run_raw_ky(args)
                    if args in (["preflight", "-h"], ["--date", "2026-09-15", "-h"]):
                        self.assertEqual(new.returncode, old.returncode)
                        self.assertEqual(new.stderr, old.stderr)
                        self.assertEqual(
                            self._without_freeze_help_block(new.stdout),
                            self._without_freeze_help_block(old.stdout),
                        )
                        start = new.stdout.index(b"  --freeze-backlog-days")
                        end = new.stdout.index(b"  --json", start)
                        self.assertEqual(new.stdout[start:end], (
                            b"  --freeze-backlog-days FREEZE_BACKLOG_DAYS\r\n"
                            b"                        freeze when overdue queued or scheduled reviews reach\r\n"
                            b"                        this many configured review-cap days\r\n"
                        ))
                        continue
                    self.assertEqual(
                        (new.returncode, new.stdout, new.stderr),
                        (old.returncode, old.stdout, old.stderr),
                    )


class RegisteredQueueDefaultTest(unittest.TestCase):
    """sol round 90: the registered default queue is bounds- and type-checked (C1 / C2)."""

    def test_registered_queue_that_is_a_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            registry = _registry_with_queue(root, "data/flat.yaml")
            (root / "data").mkdir()
            shutil.copyfile(REVIEWS_NORMAL, root / "data" / "flat.yaml")
            result = run_cli("--config", str(CONFIG_MINIMAL), "--workspace", str(registry),
                             "--date", "2026-09-12")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("expected a directory", result.stderr)

    def test_snapshot_and_review_queue_check_reject_registered_queue_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            registry = _registry_with_queue(root, "data/flat.yaml")
            (root / "data").mkdir()
            shutil.copyfile(REVIEWS_NORMAL, root / "data" / "flat.yaml")

            snapshot = run_ky(
                "snapshot", "--config", str(CONFIG_MINIMAL), "--workspace", str(registry),
                "--date", "2026-09-12",
            )
            queue_check = run_ky("review-queue", "check", "--workspace", str(registry))

        for command, result in (("snapshot", snapshot), ("review-queue check", queue_check)):
            with self.subTest(command=command):
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("expected a directory", result.stderr)

    def test_registered_queue_outside_the_workspace_is_rejected(self) -> None:
        import _winapi
        from ky.models import load_review_items
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside"
            ReviewShardStore(outside / "queue").write(load_review_items(REVIEWS_NORMAL))
            root = Path(tmp) / "workspace"
            registry = _registry_with_queue(root, "linked/queue")
            try:
                _winapi.CreateJunction(str(outside), str(root / "linked"))
            except OSError as exc:
                self.skipTest(f"junction unavailable: {exc}")
            try:
                for command in (("preflight",), ("snapshot",)):
                    result = run_ky(*command, "--config", str(CONFIG_MINIMAL),
                                    "--workspace", str(registry), "--date", "2026-09-12")
                    self.assertEqual(result.returncode, 2, (command, result.stdout))
                    self.assertIn("resolves outside the workspace", result.stderr)
            finally:
                os.rmdir(root / "linked")


class SnapshotCliTest(unittest.TestCase):
    """round-37 §5.2: py -m ky snapshot is read-only."""

    def test_snapshot_exits_0_and_prints_tree_status(self) -> None:
        result = run_ky(
            "snapshot", "--config", str(CONFIG_MINIMAL), "--items", str(REVIEWS_NORMAL),
            "--date", "2026-09-12",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("tree:", result.stdout)

    def test_snapshot_json_round_trips(self) -> None:
        result = run_ky(
            "snapshot", "--config", str(CONFIG_MINIMAL), "--items", str(REVIEWS_NORMAL),
            "--date", "2026-09-12", "--json",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["as_of"], "2026-09-12")
        subject_ids = {s["subject_id"] for s in payload["subjects"]}
        self.assertEqual(subject_ids, {"math1", "eng1", "cs408", "politics"})
        for subject in payload["subjects"]:
            if subject["subject_id"] == "politics":
                self.assertIsNone(subject["tree_total"])
            else:
                self.assertIn("tree_status", subject["tree_total"])

    def test_snapshot_without_items_reads_registered_review_queue(self) -> None:
        import yaml as _yaml
        from ky.models import load_review_items
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace_root = root / "workspace"
            workspace_root.mkdir()
            registry_source = _yaml.safe_load(
                (REPO_ROOT / "kaoyan.workspace.yaml").read_text(encoding="utf-8")
            )
            registry_source["subjects"] = {"math1": registry_source["subjects"]["math1"]}
            registry_source["reference"]["knowledge_trees"] = {
                "math1": "data/math1-tree.yaml"
            }
            registry_source["reference"]["exam_indexes"] = {"math1": ["indexes/questions.json"]}
            registry_source["reference"].pop("syllabus_versions", None)
            registry_source["reference"].pop("paper_shapes", None)
            registry_source["supplementary"] = {}
            tree_path = workspace_root / "data" / "math1-tree.yaml"
            tree_path.parent.mkdir()
            source_tree = REPO_ROOT / "data" / "structured_materials" / "math1" / "knowledge_tree.yaml"
            shutil.copyfile(source_tree, tree_path)
            registry_source["state"] = {
                "review_queue": "data/review_queue",
                "plans": "data/plans",
            }
            registry = workspace_root / "kaoyan.workspace.yaml"
            registry.write_text(
                _yaml.safe_dump(registry_source, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            config = _yaml.safe_load(CONFIG_MINIMAL_TEXT)
            config["subjects"] = [
                subject for subject in config["subjects"] if subject["subject_id"] == "math1"
            ]
            config["subjects"][0]["weight"] = 1.0
            config_path = root / "config.yaml"
            config_path.write_text(
                _yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            registered_queue = workspace_root / "data" / "review_queue"
            math_items = [
                item for item in load_review_items(REVIEWS_NORMAL) if item.subject_id == "math1"
            ]
            ReviewShardStore(registered_queue).write(math_items)

            result = run_ky(
                "snapshot", "--config", str(config_path), "--workspace", str(registry),
                "--date", "2026-09-12", "--json",
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["subjects"][0]["in_review_queue"], len(math_items))

    def test_snapshot_json_is_identical_for_flat_and_sharded_review_queues(self) -> None:
        from ky.models import load_review_items
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "review-queue" / "manifest.yaml"
            ReviewShardStore(manifest.parent).write(load_review_items(REVIEWS_NORMAL))
            flat = run_ky(
                "snapshot", "--config", str(CONFIG_MINIMAL), "--items", str(REVIEWS_NORMAL),
                "--date", "2026-09-12", "--json",
            )
            sharded = run_ky(
                "snapshot", "--config", str(CONFIG_MINIMAL), "--items", str(manifest.parent),
                "--date", "2026-09-12", "--json",
            )
            manifest_file = run_ky(
                "snapshot", "--config", str(CONFIG_MINIMAL), "--items", str(manifest),
                "--date", "2026-09-12", "--json",
            )

        for result in (flat, sharded, manifest_file):
            self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(flat.stdout.encode("utf-8"), sharded.stdout.encode("utf-8"))
        self.assertEqual(flat.stdout.encode("utf-8"), manifest_file.stdout.encode("utf-8"))

    def test_snapshot_empty_review_store_is_contract_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty_queue = Path(tmp) / "empty-queue"
            empty_queue.mkdir()
            result = run_ky(
                "snapshot", "--config", str(CONFIG_MINIMAL), "--items", str(empty_queue),
                "--date", "2026-09-12", "--json",
            )

        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("contract violation:"), result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_corrupt_or_missing_review_shard_is_contract_violation_in_both_clis(self) -> None:
        from ky.models import load_review_items
        from ky.storage.review_shards import write_review_queue

        for failure in ("tampered", "missing"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                queue = Path(tmp) / "review-queue"
                write_review_queue(queue, load_review_items(REVIEWS_NORMAL))
                shard = next((queue / "shards").glob("*.yaml"))
                if failure == "tampered":
                    original = shard.read_bytes()
                    revision_marker = original.index(b"revision: 1")
                    tampered = bytearray(original)
                    tampered[revision_marker + len(b"revision: ")] = ord("2")
                    shard.write_bytes(tampered)
                else:
                    shard.unlink()

                for command in ("preflight", "snapshot"):
                    if command == "preflight":
                        result = run_cli(
                            "--config", str(CONFIG_MINIMAL), "--items", str(queue),
                            "--date", "2026-09-12", "--json",
                        )
                    else:
                        result = run_ky(
                            "snapshot", "--config", str(CONFIG_MINIMAL), "--items", str(queue),
                            "--date", "2026-09-12", "--json",
                        )
                    self.assertEqual(result.returncode, 2, msg=result.stderr)
                    self.assertTrue(result.stderr.startswith("contract violation:"), result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_unknown_subject_in_sharded_queue_matches_flat_yaml_rejection(self) -> None:
        import yaml as _yaml
        from ky.storage.review_shards import write_review_queue

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            flat_payload = _yaml.safe_load(REVIEWS_NORMAL.read_text(encoding="utf-8"))
            unknown_item = flat_payload["items"][0]
            unknown_item["subject_id"] = "ghost"
            unknown_item["knowledge_point_id"] = "ghost.demo.unknown"
            flat_path = tmp_path / "unknown-reviews.yaml"
            flat_path.write_text(
                _yaml.safe_dump(flat_payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            queue = tmp_path / "unknown-queue"
            write_review_queue(queue, [unknown_item])

            flat = run_cli(
                "--config", str(CONFIG_MINIMAL), "--items", str(flat_path),
                "--date", "2026-09-12", "--json",
            )
            sharded = run_cli(
                "--config", str(CONFIG_MINIMAL), "--items", str(queue),
                "--date", "2026-09-12", "--json",
            )

        self.assertEqual(flat.returncode, 2, msg=flat.stderr)
        self.assertEqual(sharded.returncode, 2, msg=sharded.stderr)
        self.assertIn("ghost", flat.stderr)
        self.assertIn("ghost", sharded.stderr)
        self.assertEqual(sharded.stderr, flat.stderr)
        self.assertNotIn("Traceback", flat.stderr)
        self.assertNotIn("Traceback", sharded.stderr)

    def test_bad_config_exits_2(self) -> None:
        result = run_ky(
            "snapshot", "--config", str(CONFIG_WEIGHTS_NOT_CLOSED), "--items", str(REVIEWS_NORMAL),
        )
        self.assertEqual(result.returncode, 2)

    def test_snapshot_missing_config_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_ky(
                "snapshot", "--config", str(Path(temporary) / "missing-config.yaml"),
                "--items", str(REVIEWS_NORMAL), "--workspace", str(REPO_ROOT / "kaoyan.workspace.yaml"),
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("file does not exist", result.stderr)
        self.assertIn("missing-config.yaml", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_route_show_rejects_zero_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_ky(
                "route", "show", "--store", str(Path(temporary) / "routes"), "--revision", "0",
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("revision", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_route_show_empty_store_json_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_ky(
                "route", "show", "--store", str(Path(temporary) / "routes"), "--json",
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(result.stdout.strip())
        self.assertNotIn("Traceback", result.stderr)

    def test_review_queue_check_succeeds_for_registered_empty_queue(self) -> None:
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue = root / "review-queue"
            ReviewShardStore(queue).write([])
            result = run_ky(
                "review-queue", "check", "--workspace",
                str(REPO_ROOT / "kaoyan.workspace.yaml"), "--store", str(queue),
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("OK", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_review_queue_migration_rejects_unregistered_source_version(self) -> None:
        workspace = load_workspace(REPO_ROOT / "kaoyan.workspace.yaml")
        subject_id = next(iter(workspace.syllabus_versions))
        target = workspace.effective_version(subject_id)
        self.assertIsNotNone(target)
        with tempfile.TemporaryDirectory() as temporary:
            from ky.storage.review_shards import ReviewShardStore

            queue = Path(temporary) / "review-queue"
            ReviewShardStore(queue).write([])
            result = run_ky(
                "review-queue", "migrate", "--subject", subject_id,
                "--from", "unregistered-version", "--to", target,
                "--workspace", str(REPO_ROOT / "kaoyan.workspace.yaml"),
                "--store", str(queue),
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unregistered-version", result.stderr)
        self.assertIn("mappings", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_bad_date_exits_3(self) -> None:
        result = run_ky(
            "snapshot", "--config", str(CONFIG_MINIMAL), "--items", str(REVIEWS_NORMAL),
            "--date", "not-a-date",
        )
        self.assertEqual(result.returncode, 3)


class DayPlanCliTest(unittest.TestCase):
    """round-37 §5.2 / §7 standard #6: violating input must produce zero files."""

    def _write_plan(self, tmp: Path, **overrides) -> Path:
        fields = {
            "day": "2026-09-15", "available_minutes": 120, "knowledge_minutes": 60,
            "vocab_minutes": 30, "vocab_new_items": 15,
            "subject_minutes": {"math1": 24, "eng1": 12, "cs408": 24},
        }
        fields.update(overrides)
        path = tmp / "plan.yaml"
        import yaml as _yaml
        path.write_text(_yaml.safe_dump(fields, allow_unicode=True), encoding="utf-8")
        return path

    def test_valid_plan_submits_and_reads_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plan_path = self._write_plan(tmp_path)
            store = tmp_path / "store"
            result = run_ky(
                "day-plan", "submit", "--config", str(CONFIG_MINIMAL),
                "--plan", str(plan_path), "--store", str(store),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((store / "2026-09" / "day_plans_manifest.yaml").is_file())

    def test_violating_plan_exits_2_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            store = tmp_path / "store"
            store.mkdir()
            before = _tree_files(store)
            # hole #5 regression at the CLI boundary: capacity 60, allocated 100.
            plan_path = self._write_plan(
                tmp_path, available_minutes=60, knowledge_minutes=100, backlog_minutes=40,
                subject_minutes={"math1": 40, "eng1": 20, "cs408": 40},
            )
            result = run_ky(
                "day-plan", "submit", "--config", str(CONFIG_MINIMAL),
                "--plan", str(plan_path), "--store", str(store),
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(_tree_files(store), before)

    def _submit(self, plan_path: Path, store: Path) -> subprocess.CompletedProcess:
        return run_ky(
            "day-plan", "submit", "--config", str(CONFIG_MINIMAL),
            "--plan", str(plan_path), "--store", str(store),
        )

    def test_unquoted_yaml_date_submits_as_that_day(self) -> None:
        # WP-R3 (round 153 D2): ``day: 2026-09-15`` without quotes is how people type it.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plan_path = self._write_plan(tmp_path, day=date(2026, 9, 15))
            self.assertIn("day: 2026-09-15\n", plan_path.read_text(encoding="utf-8"))
            store = tmp_path / "store"
            result = self._submit(plan_path, store)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((store / "2026-09" / "day_plans_manifest.yaml").is_file())

    def test_impossible_date_or_string_minutes_exit_2_without_traceback(self) -> None:
        # WP-R3 (round 153 D2 / D3): these used to end in a ValueError / TypeError traceback.
        for overrides, field in (
            ({"day": "2026-13-01"}, "day"),
            ({"available_minutes": "120"}, "available_minutes"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                store = tmp_path / "store"
                store.mkdir()
                before = _tree_files(store)
                result = self._submit(self._write_plan(tmp_path, **overrides), store)
                self.assertEqual(result.returncode, 2, msg=result.stderr)
                self.assertIn(f"plan.yaml.{field}", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(_tree_files(store), before)

    def test_missing_plan_file_exits_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_ky(
                "day-plan", "submit", "--config", str(CONFIG_MINIMAL),
                "--plan", str(Path(tmp) / "absent.yaml"), "--store", str(Path(tmp) / "store"),
            )
            self.assertEqual(result.returncode, 3)

    def test_record_completion_event_and_duplicate_day_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            store = tmp_path / "store"
            done_path = tmp_path / "done.yaml"
            import yaml as _yaml
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2,
                "day": "2026-09-15",
                "reviews": [{"review_id": "rv1", "completed_on": "2026-09-15",
                             "check": "past_question", "outcome": "correct",
                             "question_ref": "cs408-2023-1", "self_rating": "fluent"}],
                "vocab": {"delivered_words": ["abate"], "practiced_words": []},
            }), encoding="utf-8")

            first = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL),
                "--done", str(done_path), "--store", str(store),
            )
            self.assertEqual(first.returncode, 0, msg=first.stderr)

            before = _tree_files(store)
            second = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL),
                "--done", str(done_path), "--store", str(store),
            )
            self.assertEqual(second.returncode, 2)
            self.assertEqual(_tree_files(store), before)

    def test_record_reads_registered_exam_config_when_config_is_omitted(self) -> None:
        import shutil
        import yaml as _yaml

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._question_workspace(root, "math1.demo.rv1")
            registry_data = _yaml.safe_load(registry.read_text(encoding="utf-8"))
            registry_data["settings"] = {"exam_config": "config.yaml"}
            registry.write_text(_yaml.safe_dump(registry_data, allow_unicode=True,
                                                 sort_keys=False), encoding="utf-8")
            shutil.copyfile(CONFIG_MINIMAL, registry.parent / "config.yaml")
            done_path = root / "done.yaml"
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2, "day": "2026-09-15",
                "reviews": [{"review_id": "rv1", "completed_on": "2026-09-15",
                             "check": "exercise", "outcome": "correct"}],
            }), encoding="utf-8")
            recorded = run_ky(
                "day-plan", "record", "--done", str(done_path),
                "--store", str(root / "store"), "--workspace", str(registry),
            )
            self.assertEqual(recorded.returncode, 0, msg=recorded.stderr)
            # No --config and no registry to fall back on: a contract error, not a guess.
            bare = root / "bare"
            bare.mkdir()
            missing = run_ky_at(
                bare, "day-plan", "record", "--done", str(done_path),
                "--store", str(root / "store2"),
            )
            self.assertEqual(missing.returncode, 2, msg=missing.stderr)
            self.assertIn("--config", missing.stderr)

    def _record_failure_with_injected_fault(self, root: Path, fault: str):
        import yaml as _yaml
        from ky.storage.review_shards import ReviewShardStore

        registry, _ = self._question_workspace(root, "math1.demo.rv1")
        review_store = root / "review-queue"
        item = self._review_item("rv1")
        item["knowledge_point_id"] = "math1.demo.rv1"
        item["introduced_on"] = "2026-09-05"
        item["due_date"] = "2026-09-12"
        ReviewShardStore(review_store).write([item])
        done_path = root / "done.yaml"
        done_path.write_text(_yaml.safe_dump({
            "schema_version": 2,
            "day": "2026-09-12",
            "reviews": [{
                "review_id": "rv1", "completed_on": "2026-09-12",
                "check": "past_question", "outcome": "correct",
            }],
        }), encoding="utf-8")
        args = [
            "day-plan", "record", "--config", str(CONFIG_MINIMAL), "--done", str(done_path),
            "--store", str(root / "day-plans"), "--review-store", str(review_store),
            "--workspace", str(registry),
        ]
        runner = root / "run_with_fault.py"
        runner.write_text(
            "import sys\n"
            "import ky.__main__ as cli\n"
            "import ky.today.record as today_record\n"
            "from ky.models import ContractError\n"
            "from ky.storage.day_plan_store import StorageError\n"
            "fault = sys.argv[1]\n"
            "if fault == 'freeze':\n"
            "    def fail(*args, **kwargs):\n"
            "        raise StorageError('forced freeze write error', 'freeze')\n"
            "    today_record.latch_freeze_if_needed = fail\n"
            "else:\n"
            "    def fail(*args, **kwargs):\n"
            "        raise ContractError('forced advance failure', 'queue')\n"
            "    cli.advance_review_queue = fail\n"
            "raise SystemExit(cli.main(sys.argv[2:]))\n",
            encoding="ascii",
        )
        env = os.environ.copy()
        env.pop(WORKSPACE_ENV, None)
        python_path = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(REPO_ROOT) if not python_path else (
            str(REPO_ROOT) + os.pathsep + python_path
        )
        return subprocess.run(
            [sys.executable, str(runner), fault, *args], cwd=REPO_ROOT, env=env,
            capture_output=True, text=True, encoding="utf-8",
        ), root / "day-plans"

    def test_record_freeze_write_failure_does_not_write_completion_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result, store = self._record_failure_with_injected_fault(Path(temporary), "freeze")
            event_files = list(store.rglob("completion--*.yaml")) if store.exists() else []
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertIn("forced freeze write error", result.stderr)
        self.assertEqual(event_files, [])
        self.assertNotIn("Traceback", result.stderr)

    def test_record_advance_failure_keeps_written_completion_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result, store = self._record_failure_with_injected_fault(Path(temporary), "advance")
            event_files = list(store.rglob("completion--*.yaml")) if store.exists() else []
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertIn("forced advance failure", result.stderr)
        self.assertEqual(len(event_files), 1)
        self.assertNotIn("Traceback", result.stderr)

    def test_record_without_store_writes_to_registered_plans_directory(self) -> None:
        import yaml as _yaml

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._question_workspace(root, "math1.demo.rv1")
            registry_doc = _yaml.safe_load(registry.read_text(encoding="utf-8"))
            registry_doc["state"]["plans"] = "data/plans"
            registry.write_text(
                _yaml.safe_dump(registry_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            done_path = root / "done.yaml"
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2, "day": "2026-09-15", "reviews": [],
            }), encoding="utf-8")

            result = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL), "--done", str(done_path),
                "--workspace", str(registry),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(
                (registry.parent / "data" / "plans" / "2026-09" / "completion--2026-09-15.yaml").is_file()
            )

    def test_explicit_store_overrides_registered_plans_directory(self) -> None:
        import yaml as _yaml

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._question_workspace(root, "math1.demo.rv1")
            registry_doc = _yaml.safe_load(registry.read_text(encoding="utf-8"))
            registry_doc["state"]["plans"] = "data/plans"
            registry.write_text(
                _yaml.safe_dump(registry_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            done_path = root / "done.yaml"
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2, "day": "2026-09-15", "reviews": [],
            }), encoding="utf-8")
            explicit_store = root / "explicit-store"

            result = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL), "--done", str(done_path),
                "--store", str(explicit_store), "--workspace", str(registry),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(
                (explicit_store / "2026-09" / "completion--2026-09-15.yaml").is_file()
            )
            self.assertFalse((registry.parent / "data" / "plans").exists())

    def test_default_store_without_workspace_registry_exits_2_with_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            done_path = root / "done.yaml"
            done_path.write_text(
                "schema_version: 2\nday: '2026-09-15'\nreviews: []\n", encoding="utf-8"
            )

            result = run_ky_at(
                root, "day-plan", "record", "--config", str(CONFIG_MINIMAL),
                "--done", str(done_path),
            )

        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("contract violation:"), result.stderr)
        self.assertIn("--store", result.stderr)
        self.assertIn("--workspace", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_malformed_completion_event_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            done_path = tmp_path / "done.yaml"
            import yaml as _yaml
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2,
                "day": "2026-09-15",
                "reviews": [{"review_id": "rv1", "completed_on": "2026-09-15",
                             "check": "past_question", "outcome": "unverified"}],
            }), encoding="utf-8")
            result = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL),
                "--done", str(done_path), "--store", str(tmp_path / "store"),
            )
            self.assertEqual(result.returncode, 2)

    def _review_item(self, review_id: str) -> dict:
        return {
            "review_id": review_id, "revision": 1, "subject_id": "math1",
            "knowledge_point_id": f"math1.demo.{review_id}", "title": "demo",
            "granularity": "concept", "state": "queued", "estimated_minutes": 10,
            "introduced_on": "2026-09-01", "due_date": "2026-09-12",
            "schedule": {"mode": "fixed_bootstrap", "phase": 0, "interval_days": 1,
                         "ease_factor": 2.5, "repetitions": 0, "lapses": 0},
            "defer_count": 0, "last_quality": None,
        }

    def _question_workspace(self, root: Path, knowledge_point_id: str) -> tuple[Path, Path]:
        import yaml as _yaml

        registry_source = _yaml.safe_load(
            (REPO_ROOT / "kaoyan.workspace.yaml").read_text(encoding="utf-8")
        )
        workspace_root = root / "workspace"
        workspace_root.mkdir()
        registry_source["subjects"] = {"math1": registry_source["subjects"]["math1"]}
        registry_source["reference"]["knowledge_trees"] = {
            "math1": registry_source["reference"]["knowledge_trees"]["math1"]
        }
        registry_source["reference"]["exam_indexes"] = {
            "math1": ["indexes/questions.json"]
        }
        registry_source["reference"].pop("paper_shapes", None)
        registry_source["reference"].pop("syllabus_versions", None)
        registry_source["reference"]["topic_weights"] = "weights/topic_weights.json"
        registry_source["supplementary"] = {}

        index = {
            "entries": [{
                "question_id": "temporary-question",
                "subject_id": "math1",
                "exam_year": 2024,
                "number": 2,
                "knowledge_point_weights": {knowledge_point_id: 1.0},
                "locator": {"page": 9},
            }]
        }
        index_path = workspace_root / "indexes" / "questions.json"
        index_path.parent.mkdir()
        index_path.write_text(json.dumps(index), encoding="utf-8")
        weights_path = workspace_root / "weights" / "topic_weights.json"
        weights_path.parent.mkdir()
        weights_path.write_text('{"topic_weight":{"math1":{}}}', encoding="utf-8")
        registry = workspace_root / "kaoyan.workspace.yaml"
        registry.write_text(
            _yaml.safe_dump(registry_source, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return registry, index_path

    def _record_lenient_unchecked(self, root: Path, registry: Path | None, *, as_json: bool):
        return run_ky(*self._record_lenient_unchecked_args(root, registry, as_json=as_json))

    def _record_lenient_unchecked_args(
        self, root: Path, registry: Path | None, *, as_json: bool
    ) -> list[str]:
        import yaml as _yaml

        review_id = "rv1"
        review_store = root / "review-queue"
        from ky.storage.review_shards import ReviewShardStore
        ReviewShardStore(review_store).write([self._review_item(review_id)])
        config = _yaml.safe_load(CONFIG_MINIMAL_TEXT)
        config["review_policy"] = {"self_rating_mode": "lenient"}
        config_path = root / "config.yaml"
        config_path.write_text(
            _yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        done_path = root / "done.yaml"
        done_path.write_text(_yaml.safe_dump({
            "schema_version": 2,
            "day": "2026-09-12",
            "reviews": [{
                "review_id": review_id,
                "completed_on": "2026-09-12",
                "check": "none",
                "self_rating": "fluent",
            }],
        }), encoding="utf-8")
        args = [
            "day-plan", "record", "--config", str(config_path),
            "--done", str(done_path), "--store", str(root / "day-plans"),
            "--review-store", str(review_store),
        ]
        if registry is not None:
            args.extend(["--workspace", str(registry)])
        if as_json:
            args.append("--json")
        return args

    def test_lenient_fluent_unchecked_record_lists_index_candidate(self) -> None:
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            knowledge_point_id = "math1.demo.rv1"
            registry, index_path = self._question_workspace(root, knowledge_point_id)
            index = json.loads(index_path.read_text(encoding="utf-8"))
            expected = index["entries"][0]
            result = self._record_lenient_unchecked(root, registry, as_json=False)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn(
                f"rv1 需要核对：{expected['question_id']}（{expected['exam_year']} 第 "
                f"{expected['number']} 题，卷面第 {expected['locator']['page']} 页）",
                result.stdout,
            )
            queue = ReviewShardStore(root / "review-queue").load()
            self.assertEqual(queue[0].knowledge_point_id, knowledge_point_id)

    def test_lenient_fluent_json_contains_question_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, index_path = self._question_workspace(root, "math1.demo.rv1")
            expected_id = json.loads(index_path.read_text(encoding="utf-8"))["entries"][0][
                "question_id"
            ]
            result = self._record_lenient_unchecked(root, registry, as_json=True)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["check_question_candidates"][0]["review_id"], "rv1")
        self.assertEqual(
            payload["check_question_candidates"][0]["candidates"][0]["question_id"],
            expected_id,
        )

    def test_record_partial_question_lookup_failure_keeps_earlier_candidate(self) -> None:
        import yaml as _yaml
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, _ = self._question_workspace(root, "math1.demo.rv1")
            registry_doc = _yaml.safe_load(registry.read_text(encoding="utf-8"))
            config = _yaml.safe_load(CONFIG_MINIMAL_TEXT)
            second_subject = next(
                subject["subject_id"] for subject in config["subjects"]
                if subject["active"] and subject["subject_id"] != "math1"
            )
            source_registry = _yaml.safe_load(
                (REPO_ROOT / "kaoyan.workspace.yaml").read_text(encoding="utf-8")
            )
            registry_doc["subjects"][second_subject] = source_registry["subjects"][second_subject]
            registry_doc["reference"]["knowledge_trees"][second_subject] = (
                source_registry["reference"]["knowledge_trees"][second_subject]
            )
            registry.write_text(
                _yaml.safe_dump(registry_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            config["review_policy"] = {"self_rating_mode": "lenient"}
            config_path = root / "config.yaml"
            config_path.write_text(
                _yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            review_store = root / "review-queue"
            first = self._review_item("record-review")
            first["knowledge_point_id"] = "math1.demo.rv1"
            second = self._review_item("record-second")
            second["subject_id"] = second_subject
            second["knowledge_point_id"] = f"{second_subject}.generated.second"
            ReviewShardStore(review_store).write([first, second])
            done_path = root / "done.yaml"
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2,
                "day": "2026-09-12",
                "reviews": [
                    {"review_id": rid, "completed_on": "2026-09-12", "check": "none",
                     "self_rating": "fluent"}
                    for rid in ("record-review", "record-second")
                ],
            }), encoding="utf-8")
            result = run_ky(
                "day-plan", "record", "--config", str(config_path), "--done", str(done_path),
                "--store", str(root / "day-plans"), "--review-store", str(review_store),
                "--workspace", str(registry), "--json",
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        groups = payload["check_question_candidates"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["review_id"], "record-review")
        self.assertTrue(groups[0]["candidates"])
        self.assertIn("check_question_suggestions_skipped", payload)

    def test_record_partial_question_lookup_failure_prints_text_hint(self) -> None:
        import yaml as _yaml
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, _ = self._question_workspace(root, "math1.demo.rv1")
            registry_doc = _yaml.safe_load(registry.read_text(encoding="utf-8"))
            config = _yaml.safe_load(CONFIG_MINIMAL_TEXT)
            second_subject = next(
                subject["subject_id"] for subject in config["subjects"]
                if subject["active"] and subject["subject_id"] != "math1"
            )
            source_registry = _yaml.safe_load(
                (REPO_ROOT / "kaoyan.workspace.yaml").read_text(encoding="utf-8")
            )
            registry_doc["subjects"][second_subject] = source_registry["subjects"][second_subject]
            registry_doc["reference"]["knowledge_trees"][second_subject] = (
                source_registry["reference"]["knowledge_trees"][second_subject]
            )
            registry.write_text(
                _yaml.safe_dump(registry_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            config["review_policy"] = {"self_rating_mode": "lenient"}
            config_path = root / "config.yaml"
            config_path.write_text(
                _yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            review_store = root / "review-queue"
            first = self._review_item("record-review")
            first["knowledge_point_id"] = "math1.demo.rv1"
            second = self._review_item("record-second")
            second["subject_id"] = second_subject
            second["knowledge_point_id"] = f"{second_subject}.generated.second"
            ReviewShardStore(review_store).write([first, second])
            done_path = root / "done.yaml"
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2,
                "day": "2026-09-12",
                "reviews": [
                    {"review_id": rid, "completed_on": "2026-09-12", "check": "none",
                     "self_rating": "fluent"}
                    for rid in ("record-review", "record-second")
                ],
            }), encoding="utf-8")
            result = run_ky(
                "day-plan", "record", "--config", str(config_path), "--done", str(done_path),
                "--store", str(root / "day-plans"), "--review-store", str(review_store),
                "--workspace", str(registry),
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(any(
            line.startswith("出题查询失败") for line in result.stdout.splitlines()
        ), result.stdout)

    def test_strict_fluent_unchecked_record_has_no_question_candidates(self) -> None:
        import yaml as _yaml
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._question_workspace(root, "math1.demo.rv1")
            review_store = root / "review-queue"
            ReviewShardStore(review_store).write([self._review_item("rv1")])
            done_path = root / "done.yaml"
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2,
                "day": "2026-09-12",
                "reviews": [{"review_id": "rv1", "completed_on": "2026-09-12",
                             "check": "none", "self_rating": "fluent"}],
            }), encoding="utf-8")
            result = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL),
                "--done", str(done_path), "--store", str(root / "day-plans"),
                "--review-store", str(review_store), "--workspace", str(registry), "--json",
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(json.loads(result.stdout)["check_question_candidates"], [])

    def test_missing_workspace_skips_questions_after_recording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._record_lenient_unchecked(
                root, root / "missing-registry.yaml", as_json=False
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("未找到工作区注册表，跳过出题", result.stdout)
        self.assertIn("review queue advanced:", result.stdout)

    def test_record_with_review_store_advances_the_queue_end_to_end(self) -> None:
        # round-38 residual A: `day-plan record --review-store` is the real conduit from
        # "a completion event was recorded" to "the review queue actually moved".
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            review_store_path = tmp_path / "review-queue"
            ReviewShardStore(review_store_path).write([self._review_item("rv1")])

            # Precondition: rv1 is due on the day, so "nothing due after recording" below
            # proves the queue actually moved rather than holding vacuously.
            before = run_cli(
                "--config", str(CONFIG_MINIMAL), "--items", str(review_store_path),
                "--date", "2026-09-12", "--json",
            )
            self.assertEqual(before.returncode, 0, msg=before.stderr)
            self.assertEqual(len(json.loads(before.stdout)["selected"]), 1)

            done_path = tmp_path / "done.yaml"
            import yaml as _yaml
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2,
                "day": "2026-09-12",
                "reviews": [{"review_id": "rv1", "completed_on": "2026-09-12",
                             "check": "past_question", "outcome": "correct"}],
            }), encoding="utf-8")

            result = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL),
                "--done", str(done_path), "--store", str(tmp_path / "store"),
                "--review-store", str(review_store_path),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("review queue advanced: 1", result.stdout)

            reread = ReviewShardStore(review_store_path).load()
            self.assertEqual(len(reread), 1)
            self.assertEqual(reread[0].due_date.isoformat(), "2026-09-14")  # +2 days, ladder[1]
            self.assertEqual(reread[0].schedule.interval_days, 2)
            self.assertEqual(reread[0].last_reviewed_on.isoformat(), "2026-09-12")

            preflight = run_cli(
                "--config", str(CONFIG_MINIMAL), "--items", str(review_store_path),
                "--date", "2026-09-12", "--json",
            )
            snapshot = run_ky(
                "snapshot", "--config", str(CONFIG_MINIMAL), "--items", str(review_store_path),
                "--date", "2026-09-12", "--json",
            )
            self.assertEqual(preflight.returncode, 0, msg=preflight.stderr)
            self.assertEqual(snapshot.returncode, 0, msg=snapshot.stderr)
            self.assertEqual(json.loads(preflight.stdout)["selected"], [])
            math1 = next(
                subject for subject in json.loads(snapshot.stdout)["subjects"]
                if subject["subject_id"] == "math1"
            )
            self.assertEqual(math1["due_today_count"], 0)

    def test_record_uses_configured_fsrs_and_reports_late_checked_completion(self) -> None:
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import yaml as _yaml
            config = _yaml.safe_load(CONFIG_MINIMAL.read_text(encoding="utf-8"))
            config["review_policy"] = {"algorithm": "fsrs"}
            config_path = root / "config.yaml"
            config_path.write_text(
                _yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            review_store = root / "review-queue"
            ReviewShardStore(review_store).write([self._review_item("rv1")])

            for event_day, completed_on, name in (
                ("2026-10-10", "2026-10-10", "first"),
                ("2026-10-11", "2026-10-05", "late"),
            ):
                done_path = root / f"{name}.yaml"
                done_path.write_text(_yaml.safe_dump({
                    "schema_version": 2,
                    "day": event_day,
                    "reviews": [{
                        "review_id": "rv1", "completed_on": completed_on,
                        "check": "past_question", "outcome": "correct",
                    }],
                }), encoding="utf-8")
                result = run_ky(
                    "day-plan", "record", "--config", str(config_path),
                    "--done", str(done_path), "--store", str(root / "plans"),
                    "--review-store", str(review_store),
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                if name == "late":
                    self.assertIn("晚到的核对未被 FSRS 采用：rv1", result.stdout)

            final = ReviewShardStore(review_store).load()[0]
            self.assertEqual(final.schedule.mode, "fsrs")
            self.assertEqual(final.schedule.fsrs_reviewed_on, date(2026, 10, 10))

    def test_record_with_review_store_and_unknown_review_id_exits_2_and_writes_nothing(self) -> None:
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            review_store_path = tmp_path / "review-queue"
            ReviewShardStore(review_store_path).write([self._review_item("rv1")])
            review_queue_before = _tree_files(review_store_path)

            done_path = tmp_path / "done.yaml"
            import yaml as _yaml
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2,
                "day": "2026-09-12",
                "reviews": [{"review_id": "does-not-exist", "completed_on": "2026-09-12",
                             "check": "past_question", "outcome": "correct"}],
            }), encoding="utf-8")

            store_path = tmp_path / "store"
            result = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL),
                "--done", str(done_path), "--store", str(store_path),
                "--review-store", str(review_store_path),
            )
            self.assertEqual(result.returncode, 2)
            # Neither the completion event nor the review queue may end up written.
            self.assertEqual(_tree_files(store_path), {})
            self.assertEqual(_tree_files(review_store_path), review_queue_before)

    def test_record_on_legacy_reviewed_queue_exits_2_and_writes_nothing(self) -> None:
        # sol round 60, C2: the legacy refusal used to fire only after the write-once
        # completion event had been written, leaving an orphan event and a traceback.
        import hashlib as _hashlib
        import yaml as _yaml
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            review_store_path = tmp_path / "review-queue"
            reviewed = {**self._review_item("rv1"), "last_reviewed_on": "2026-09-11"}
            store = ReviewShardStore(review_store_path)
            store.write([reviewed])
            manifest = _yaml.safe_load(store.manifest_path.read_text(encoding="utf-8"))
            manifest["schema_version"] = 1
            manifest.pop("calculated_completion_ids")
            payload = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            manifest["manifest_sha256"] = _hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            store.manifest_path.write_text(_yaml.safe_dump(manifest, sort_keys=False),
                                           encoding="utf-8")
            review_queue_before = _tree_files(review_store_path)

            done_path = tmp_path / "done.yaml"
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2,
                "day": "2026-09-12",
                "reviews": [{"review_id": "rv1", "completed_on": "2026-09-12",
                             "check": "past_question", "outcome": "correct"}],
            }), encoding="utf-8")
            store_path = tmp_path / "store"
            result = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL),
                "--done", str(done_path), "--store", str(store_path),
                "--review-store", str(review_store_path),
            )
            self.assertEqual(result.returncode, 2, msg=result.stderr)
            self.assertIn("请先升级队列", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(_tree_files(store_path), {})
            self.assertEqual(_tree_files(review_store_path), review_queue_before)

    def test_record_accepts_late_completion_and_advances_before_writing(self) -> None:
        from ky.storage.review_shards import ReviewShardStore

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            review_store_path = tmp_path / "review-queue"
            current = self._review_item("rv1")
            current["last_reviewed_on"] = "2026-09-12"
            current["last_quality"] = 4
            ReviewShardStore(review_store_path).write([current])

            done_path = tmp_path / "done.yaml"
            import yaml as _yaml
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2,
                "day": "2026-09-13",
                "reviews": [{"review_id": "rv1", "completed_on": "2026-09-10",
                             "check": "exercise", "outcome": "partial"}],
            }), encoding="utf-8")

            store_path = tmp_path / "store"
            result = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL),
                "--done", str(done_path), "--store", str(store_path),
                "--review-store", str(review_store_path),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("late: 1", result.stdout)
            self.assertTrue(_tree_files(store_path))
            self.assertNotEqual(_tree_files(review_store_path), {})

    def _compare_registry_skip_output(
        self, *, missing: bool, as_json: bool, no_discovery: bool = False
    ) -> None:
        from ky.storage.review_shards import ReviewShardStore
        import yaml as _yaml

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._question_workspace(root, "math1.demo.rv1")
            if missing:
                registry_argument = root / "absent.workspace.yaml"
            else:
                registry.write_text("schema_version: [\n", encoding="utf-8")
                registry_argument = registry

            review_store = root / "review-queue"
            ReviewShardStore(review_store).write([self._review_item("rv1")])
            config = _yaml.safe_load(CONFIG_MINIMAL_TEXT)
            config["review_policy"] = {"self_rating_mode": "lenient"}
            config_path = root / "config.yaml"
            config_path.write_text(
                _yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            done_path = root / "done.yaml"
            done_path.write_text(_yaml.safe_dump({
                "schema_version": 2,
                "day": "2026-09-12",
                "reviews": [{
                    "review_id": "rv1", "completed_on": "2026-09-12",
                    "check": "none", "self_rating": "fluent",
                }],
            }), encoding="utf-8")
            args = [
                "day-plan", "record", "--config", str(config_path),
                "--done", str(done_path), "--store", str(root / "day-plans"),
                "--review-store", str(review_store),
            ]
            if not no_discovery:
                args.extend(["--workspace", str(registry_argument)])
            if as_json:
                args.append("--json")

            legacy_main = _legacy_cli_path(root)
            legacy = run_raw_ky(
                args, legacy_main=legacy_main, cwd=root, clear_workspace_env=no_discovery
            )
            shutil.rmtree(root / "day-plans", ignore_errors=True)
            shutil.rmtree(review_store, ignore_errors=True)
            ReviewShardStore(review_store).write([self._review_item("rv1")])
            current = run_raw_ky(args, cwd=root, clear_workspace_env=no_discovery)
            self.assertEqual(
                (current.returncode, current.stdout, current.stderr),
                (legacy.returncode, legacy.stdout, legacy.stderr),
            )

    def test_record_missing_registry_text_and_json_match_fixed_legacy_bytes(self) -> None:
        for no_discovery in (False, True):
            for as_json in (False, True):
                with self.subTest(no_discovery=no_discovery, as_json=as_json):
                    self._compare_registry_skip_output(
                        missing=True, as_json=as_json, no_discovery=no_discovery
                    )

    def test_record_invalid_registry_text_and_json_match_fixed_legacy_bytes(self) -> None:
        for as_json in (False, True):
            with self.subTest(as_json=as_json):
                self._compare_registry_skip_output(missing=False, as_json=as_json)

    def test_record_classifies_registry_by_lookup_stage_not_error_text(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch

        import ky.__main__ as cli_module
        from ky.models import ContractError

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._question_workspace(root, "math1.demo.rv1")
            args = self._record_lenient_unchecked_args(root, registry, as_json=False)
            output = StringIO()
            with (
                patch.object(cli_module, "find_workspace", return_value=registry) as find,
                patch.object(
                    cli_module, "load_workspace",
                    side_effect=ContractError("workspace path not found in registry contents"),
                ) as load,
                redirect_stdout(output),
            ):
                result = cli_module.day_plan_main(args[1:])

            self.assertEqual(result, 0)
            self.assertEqual(find.call_count, 1)
            self.assertEqual(load.call_count, 1)
            self.assertIn(
                "出题查询失败，已跳过：workspace path not found in registry contents",
                output.getvalue(),
            )

    def test_record_without_store_reads_the_registry_once(self) -> None:
        # sol round 130, M1: the default store path and the freeze / question steps share one
        # loaded registry instead of loading it again.
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch

        import ky.__main__ as cli_module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._question_workspace(root, "math1.demo.rv1")
            args = self._record_lenient_unchecked_args(root, registry, as_json=False)
            store_at = args.index("--store")
            del args[store_at:store_at + 2]
            with (
                patch.object(cli_module, "find_workspace", wraps=cli_module.find_workspace) as find,
                patch.object(cli_module, "load_workspace", wraps=cli_module.load_workspace) as load,
                redirect_stdout(StringIO()),
            ):
                result = cli_module.day_plan_main(args[1:])

            self.assertEqual(result, 0)
            self.assertEqual(load.call_count, 1)
            self.assertEqual(find.call_count, 0)
            plans = load_workspace(registry).write_target("state.plans")
            self.assertTrue(list(plans.rglob("completion--*.yaml")))

class MonthCloseCliTest(unittest.TestCase):
    """round-37 §5.2 / §8: month-close is read-only -- it never writes a month_close.yaml."""

    def test_reads_back_committed_day_plans_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            store = tmp_path / "store"
            plan_path = tmp_path / "plan.yaml"
            import yaml as _yaml
            plan_path.write_text(_yaml.safe_dump({
                "day": "2026-09-15", "available_minutes": 120, "knowledge_minutes": 60,
                "vocab_minutes": 30, "subject_minutes": {"math1": 24, "eng1": 12, "cs408": 24},
            }), encoding="utf-8")
            submit = run_ky(
                "day-plan", "submit", "--config", str(CONFIG_MINIMAL),
                "--plan", str(plan_path), "--store", str(store),
            )
            self.assertEqual(submit.returncode, 0, msg=submit.stderr)

            before = _tree_files(store)
            result = run_ky(
                "month-close", "--config", str(CONFIG_MINIMAL), "--store", str(store),
                "--year", "2026", "--month", "9", "--json",
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            after = _tree_files(store)
            self.assertEqual(before, after, "month-close must never write month_close.yaml itself")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["days_planned"], 1)
            self.assertEqual(payload["available_minutes"], 120)
            # round-38 residual B: the CLI always looks for completion events now. None were
            # recorded here, so this is a measured zero, not "unmeasured".
            self.assertTrue(payload["actual_data_available"])
            self.assertEqual(payload["actual_reviews_completed"], 0)
            self.assertEqual(payload["actual_vocab_delivered_words"], 0)
            self.assertEqual(payload["actual_vocab_practiced_words"], 0)

    def test_planned_and_actual_are_both_reported_and_reconcilable(self) -> None:
        # round-38 residual B: monthly close must consume CompletionEvent and report plan vs.
        # actual side by side, without merging delivered and practiced word counts.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            store = tmp_path / "store"
            plan_path = tmp_path / "plan.yaml"
            import yaml as _yaml
            plan_path.write_text(_yaml.safe_dump({
                "day": "2026-09-15", "available_minutes": 120, "knowledge_minutes": 60,
                "vocab_minutes": 30, "vocab_new_items": 15,
                "subject_minutes": {"math1": 24, "eng1": 12, "cs408": 24},
            }), encoding="utf-8")
            submit = run_ky(
                "day-plan", "submit", "--config", str(CONFIG_MINIMAL),
                "--plan", str(plan_path), "--store", str(store),
            )
            self.assertEqual(submit.returncode, 0, msg=submit.stderr)

            done_path = tmp_path / "done.yaml"
            done_path.write_text(_yaml.safe_dump({
                "day": "2026-09-15",
                "vocab": {
                    "delivered_words": ["abate", "abdicate", "abstain"],
                    "practiced_words": ["abate"],
                },
            }), encoding="utf-8")
            record = run_ky(
                "day-plan", "record", "--config", str(CONFIG_MINIMAL),
                "--done", str(done_path), "--store", str(store),
            )
            self.assertEqual(record.returncode, 0, msg=record.stderr)

            result = run_ky(
                "month-close", "--config", str(CONFIG_MINIMAL), "--store", str(store),
                "--year", "2026", "--month", "9", "--json",
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)

            self.assertTrue(payload["actual_data_available"])
            self.assertEqual(payload["vocab_items_introduced"], 15)  # planned, from DayPlan
            self.assertEqual(payload["actual_vocab_delivered_words"], 3)  # actual, from CompletionEvent
            self.assertEqual(payload["actual_vocab_practiced_words"], 1)  # kept separate
            # There is no combined "delivered+practiced" field at all -- they are reported and
            # remain addressable as two distinct keys, never merged into one number.
            self.assertNotIn("actual_vocab_words", payload)
            self.assertNotIn("actual_vocab_total", payload)
            # The reconcilable difference: actual delivered minus planned new-items.
            self.assertEqual(payload["vocab_delivered_vs_planned"], 3 - 15)

    def test_invalid_month_exits_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_ky(
                "month-close", "--config", str(CONFIG_MINIMAL), "--store", tmp,
                "--year", "2026", "--month", "13",
            )
            self.assertEqual(result.returncode, 3)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
