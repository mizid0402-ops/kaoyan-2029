from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from ky.models import ContractError
from ky.planner.port import canonical_json_bytes
from ky.timetable import (
    Semester,
    semester_from_mapping,
    semester_to_mapping,
    timetable_from_mapping,
    timetable_to_mapping,
)
from ky.timetable_io import (
    Isolation,
    StagedSemester,
    apply_staging,
    check_isolated_path,
    inspect_isolation,
    parse_staging_bytes,
    publish_staging,
    read_staging,
    restage,
    staged_to_bytes,
    staging_hash12,
)
from ky.workspace import WORKSPACE_FILENAME, load_workspace

ROOT = Path(__file__).resolve().parents[2]
SOURCE_HASH = "a" * 64


def _detached_isolation(root: Path) -> Isolation:
    from ky.timetable_io import isolation as isolation_module

    with patch.object(isolation_module, "_has_git_marker", return_value=False):
        return inspect_isolation(root)


def _school_document(school_id: str = "demo") -> dict:
    return {
        "schema_version": 1,
        "school_id": school_id,
        "name": "Synthetic School",
        "system": "sample_system",
        "source": {"kind": "user_statement", "recorded_on": "2026-09-30"},
        "periods": {
            1: {"start": "08:00", "end": "08:45"},
            2: {"start": "08:55", "end": "09:40"},
            3: {"start": "10:10", "end": "10:55"},
            4: {"start": "11:05", "end": "11:50"},
        },
        "blocks": [[1, 2], [3, 4]],
    }


def _course(name: str = "Math", periods: str = "1-2", weeks: str = "1-2") -> dict:
    return {"name": name, "weekday": 1, "periods": periods, "weeks": weeks}


def _semester(
    label: str = "term-a",
    monday: str = "2026-09-07",
    *,
    name: str = "Math",
    weeks: int = 2,
    exceptions: list[dict] | None = None,
) -> dict:
    result = {
        "label": label,
        "school": "demo",
        "week1_monday": monday,
        "weeks": weeks,
        "courses": [_course(name, weeks=f"1-{weeks}")],
    }
    if exceptions is not None:
        result["exceptions"] = exceptions
    return result


def _timetable(semesters: list[dict] | None = None) -> dict:
    return {
        "schema_version": 1,
        "rules": {
            "study_window": {"start": "07:30", "end": "12:00"},
            "buffer_minutes": 5,
            "min_gap_minutes": 10,
            "block_deduction_minutes": 15,
        },
        "semesters": [_semester()] if semesters is None else semesters,
    }


def _workspace(root: Path, *, school_path: str = "data/schools/demo.yaml"):
    root.mkdir(parents=True, exist_ok=True)
    registry = {
        "schema_version": 2,
        "subjects": {"alpha": {"name": "Alpha"}},
        "reference": {
            "knowledge_trees": {},
            "exam_indexes": {},
            "paper_shapes": {},
            "topic_weights": "data/topic_weights.json",
            "vocabulary_db": "data/vocabulary.sqlite",
            "ledger": "data/ledger.yaml",
            "timetable_schools": {"demo": school_path},
        },
        "supplementary": {},
        "materials": {"raw_root": "data/raw"},
        "products": {},
        "settings": {},
        "state": {
            "review_queue": "data/queue",
            "plans": "data/plans",
            "timetable": "data/timetable.yaml",
        },
        "staging": "staging",
        "projection": "data/projection.sqlite",
    }
    path = root / WORKSPACE_FILENAME
    path.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    school = root / school_path
    school.parent.mkdir(parents=True, exist_ok=True)
    school.write_text(
        yaml.safe_dump(_school_document(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    timetable_path = root / "data/timetable.yaml"
    timetable_path.parent.mkdir(parents=True, exist_ok=True)
    timetable_path.write_text(
        yaml.safe_dump(_timetable(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return load_workspace(path), timetable_path, school


def _staged(semester: dict | Semester | None = None, *, notes: tuple[str, ...] = ()):
    value = semester_from_mapping(
        _semester() if semester is None else semester, "semester"
    ) if not isinstance(semester, Semester) else semester
    return StagedSemester("ics", SOURCE_HASH, value, notes)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=True
    )


class TimetableIOContractTests(unittest.TestCase):
    def test_staging_shape_hash_duplicate_and_round_trip(self) -> None:
        candidate = _staged(notes=("fixture note",))
        encoded = staged_to_bytes(candidate)
        parsed = parse_staging_bytes(encoded, Path("candidate.yaml"))
        self.assertEqual(parsed, candidate)
        self.assertEqual(staging_hash12(parsed), staging_hash12(candidate))
        hash_input = {
            "schema_version": 1,
            "kind": "timetable_import",
            "source": {"adapter": "ics", "sha256": SOURCE_HASH},
            "semester": semester_to_mapping(candidate.semester),
        }
        expected = hashlib.sha256(canonical_json_bytes(hash_input)).hexdigest()[:12]
        self.assertEqual(staging_hash12(candidate), expected)
        mapping = yaml.safe_load(encoded)
        self.assertEqual(mapping["kind"], "timetable_import")
        self.assertEqual(len(staging_hash12(candidate)), 12)

        duplicated = encoded.replace(
            b"kind: timetable_import\n",
            b"kind: timetable_import\nkind: timetable_import\n",
        )
        with self.assertRaises(ContractError) as caught:
            parse_staging_bytes(duplicated, Path("candidate.yaml"))
        self.assertEqual(caught.exception.path, "kind")

        for raw, field in (
            ({"schema_version": True}, "schema_version"),
            ({"kind": "other"}, "kind"),
            ({"source": {"adapter": "other", "sha256": SOURCE_HASH}}, "source.adapter"),
            ({"source": {"adapter": "ics", "sha256": "bad"}}, "source.sha256"),
            ({"notes": [4]}, "notes[0]"),
        ):
            invalid = yaml.safe_load(encoded)
            invalid.update(raw)
            with self.subTest(field=field), self.assertRaises(ContractError) as caught:
                parse_staging_bytes(
                    yaml.safe_dump(invalid, sort_keys=False).encode("utf-8"),
                    Path("candidate.yaml"),
                )
            self.assertEqual(caught.exception.path, field)

    def test_isolation_states_and_each_repository_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            _git(root, "init", "-q")
            (root / ".gitignore").write_text("ignored/\nstaging/\n", encoding="utf-8")
            workspace_root = root / "nested" / "workspace"
            workspace_root.mkdir(parents=True)
            isolation = inspect_isolation(workspace_root)
            self.assertEqual(isolation.state, "A")
            self.assertEqual(isolation.worktree_root, root.resolve())

            allowed = root / "ignored" / "new.yaml"
            self.assertEqual(check_isolated_path(isolation, allowed), allowed.resolve())
            tracked = root / "ignored" / "tracked.yaml"
            tracked.parent.mkdir(parents=True, exist_ok=True)
            tracked.write_bytes(b"synthetic")
            _git(root, "add", "-f", "ignored/tracked.yaml")
            with self.assertRaises(ContractError):
                check_isolated_path(isolation, tracked)
            with self.assertRaises(ContractError):
                check_isolated_path(isolation, root / "visible" / "new.yaml")

            # The target is outside the nested workspace, but remains inside its repository.
            self.assertEqual(
                check_isolated_path(isolation, root / "ignored" / "outside-workspace.yaml"),
                (root / "ignored" / "outside-workspace.yaml").resolve(),
            )

        with tempfile.TemporaryDirectory() as temporary:
            detached = Path(temporary) / "copy"
            detached.mkdir()
            isolation = _detached_isolation(detached)
            self.assertEqual(isolation.state, "B")
            self.assertEqual(check_isolated_path(isolation, detached / "new.yaml"),
                             (detached / "new.yaml").resolve())

    def test_git_query_failure_is_uncertain_for_nonzero_and_oserror(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            failed = subprocess.CompletedProcess([], 128, b"", b"")
            with patch("ky.timetable_io.isolation.subprocess.run", return_value=failed):
                self.assertEqual(inspect_isolation(root).state, "C")
            with patch(
                "ky.timetable_io.isolation.subprocess.run",
                side_effect=OSError("git unavailable"),
            ):
                self.assertEqual(inspect_isolation(root).state, "C")
            with self.assertRaises(ContractError) as caught:
                check_isolated_path(
                    inspect_isolation(root), root / "staging" / "file.yaml"
                )
            self.assertEqual(caught.exception.message, "无法确认个人数据不会进仓库")

    def test_staging_publication_is_once_only_and_checks_temporary_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _, _ = _workspace(Path(temporary) / "workspace")
            isolation = _detached_isolation(workspace.root)
            candidate = _staged(notes=("kept",))
            from ky.timetable_io import staging as staging_module

            checked: list[Path] = []
            original_check = staging_module.check_isolated_path

            def record(isolation_value, path):
                checked.append(Path(path))
                return original_check(isolation_value, path)

            with patch.object(staging_module, "check_isolated_path", side_effect=record):
                path, published = publish_staging(workspace, candidate, isolation)
            self.assertTrue(published)
            self.assertTrue(any(item.name.endswith(".tmp") for item in checked))
            original = path.read_bytes()
            same_path, published_again = publish_staging(workspace, candidate, isolation)
            self.assertEqual(same_path, path)
            self.assertFalse(published_again)

            conflict = _staged(candidate.semester, notes=("different note",))
            with self.assertRaises(ContractError):
                publish_staging(workspace, conflict, isolation)
            self.assertEqual(path.read_bytes(), original)

    def test_restaging_same_hash_rehash_and_preserve_exceptions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _, _ = _workspace(Path(temporary) / "workspace")
            isolation = _detached_isolation(workspace.root)
            candidate = _staged(
                _semester(
                    exceptions=[
                        {"kind": "no_class", "date": "2026-09-08"},
                    ]
                ),
                notes=("manual",),
            )
            original_path, _ = publish_staging(workspace, candidate, isolation)
            same = restage(workspace, original_path, isolation)
            self.assertEqual(same.path, original_path)
            self.assertFalse(same.published)

            edited = _staged(
                _semester(
                    name="Physics",
                    exceptions=[{"kind": "no_class", "date": "2026-09-08"}],
                ),
                notes=("manual",),
            )
            edited_path = original_path.with_name("edited.yaml")
            edited_path.write_bytes(staged_to_bytes(edited))
            updated = restage(workspace, edited_path, isolation)
            self.assertTrue(updated.published)
            self.assertNotEqual(updated.path, original_path)
            self.assertIn("新增课程", "\n".join(updated.changes))
            reloaded, _ = read_staging(updated.path)
            self.assertEqual(reloaded.semester.exceptions, edited.semester.exceptions)

    def test_apply_append_replace_conflicts_and_already_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, timetable_path, _ = _workspace(Path(temporary) / "workspace")
            isolation = _detached_isolation(workspace.root)
            original = timetable_path.read_bytes()
            original_table = timetable_from_mapping(yaml.safe_load(original))
            candidate = _staged(_semester("term-b", "2027-01-04"))
            stage, _ = publish_staging(workspace, candidate, isolation)
            result = apply_staging(workspace, stage, isolation)
            self.assertEqual(result.status, "applied")
            self.assertIsNotNone(result.backup)
            self.assertEqual(result.backup.read_bytes(), original)
            after_append = timetable_from_mapping(yaml.safe_load(timetable_path.read_bytes()))
            self.assertEqual([term.label for term in after_append.semesters], ["term-a", "term-b"])
            self.assertEqual(after_append.rules, original_table.rules)

        with tempfile.TemporaryDirectory() as temporary:
            workspace, timetable_path, _ = _workspace(Path(temporary) / "workspace")
            isolation = _detached_isolation(workspace.root)
            candidate = _staged(_semester(name="Physics"))
            stage, _ = publish_staging(workspace, candidate, isolation)
            original = timetable_path.read_bytes()
            with self.assertRaises(ContractError) as conflict:
                apply_staging(workspace, stage, isolation)
            self.assertEqual(conflict.exception.path, "semester.label")
            self.assertEqual(timetable_path.read_bytes(), original)
            replaced = apply_staging(workspace, stage, isolation, replace=True)
            self.assertEqual(replaced.status, "applied")
            result = timetable_from_mapping(yaml.safe_load(timetable_path.read_bytes()))
            self.assertEqual(result.semesters[0].courses[0].name, "Physics")

        for replace_flag in (False, True):
            with self.subTest(replace=replace_flag), tempfile.TemporaryDirectory() as temporary:
                workspace, timetable_path, _ = _workspace(Path(temporary) / "workspace")
                isolation = _detached_isolation(workspace.root)
                staged = _staged(_semester())
                stage, _ = publish_staging(workspace, staged, isolation)
                before = timetable_path.read_bytes()
                result = apply_staging(
                    workspace, stage, isolation, replace=replace_flag
                )
                self.assertEqual(result.status, "already_applied")
                self.assertEqual(timetable_path.read_bytes(), before)
                self.assertEqual(tuple(timetable_path.parent.glob("*.previous-*.yaml")), ())

    def test_apply_validates_missing_school_overlap_backup_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, timetable_path, missing = _workspace(
                Path(temporary) / "workspace", school_path="data/schools/missing.yaml"
            )
            isolation = _detached_isolation(workspace.root)
            same = _staged(_semester())
            stage, _ = publish_staging(workspace, same, isolation)
            missing.unlink(missing_ok=True)
            with self.assertRaises(ContractError):
                apply_staging(workspace, stage, isolation)

        with tempfile.TemporaryDirectory() as temporary:
            workspace, timetable_path, _ = _workspace(Path(temporary) / "workspace")
            isolation = _detached_isolation(workspace.root)
            overlap = _staged(_semester("overlap", "2026-09-14"))
            stage, _ = publish_staging(workspace, overlap, isolation)
            original = timetable_path.read_bytes()
            with self.assertRaises(ContractError) as caught:
                apply_staging(workspace, stage, isolation)
            self.assertEqual(caught.exception.path, "semesters[1].week1_monday")
            self.assertEqual(timetable_path.read_bytes(), original)

        with tempfile.TemporaryDirectory() as temporary:
            workspace, timetable_path, _ = _workspace(Path(temporary) / "workspace")
            isolation = _detached_isolation(workspace.root)
            addition = _staged(_semester("term-b", "2027-01-04"))
            stage, _ = publish_staging(workspace, addition, isolation)
            original = timetable_path.read_bytes()
            digest = hashlib.sha256(original).hexdigest()[:12]
            backup = timetable_path.with_name(f"timetable.previous-{digest}.yaml")
            backup.write_bytes(b"different backup")
            with self.assertRaises(ContractError):
                apply_staging(workspace, stage, isolation)
            self.assertEqual(timetable_path.read_bytes(), original)

        with tempfile.TemporaryDirectory() as temporary:
            workspace, timetable_path, _ = _workspace(Path(temporary) / "workspace")
            isolation = _detached_isolation(workspace.root)
            addition = _staged(_semester("term-b", "2027-01-04"))
            stage, _ = publish_staging(workspace, addition, isolation)
            before = timetable_path.read_bytes()
            result = apply_staging(workspace, stage, isolation, dry_run=True)
            self.assertEqual(result.status, "dry_run")
            self.assertEqual(timetable_path.read_bytes(), before)
            self.assertEqual(tuple(timetable_path.parent.glob("*.previous-*.yaml")), ())

    def test_apply_staging_guard_and_recover_after_backup_interruption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, timetable_path, _ = _workspace(Path(temporary) / "workspace")
            isolation = _detached_isolation(workspace.root)
            candidate = _staged(_semester("term-b", "2027-01-04"))
            stage, _ = publish_staging(workspace, candidate, isolation)
            outside = workspace.root / "outside.yaml"
            shutil.copyfile(stage, outside)
            with self.assertRaises(ContractError) as caught:
                apply_staging(workspace, outside, isolation)
            self.assertEqual(caught.exception.path, "staging")

            original = timetable_path.read_bytes()
            import ky.timetable_io.operations as operations

            isolated_checks: list[Path] = []
            original_check = operations.check_isolated_path

            def record_check(isolation_value, path):
                isolated_checks.append(Path(path))
                return original_check(isolation_value, path)

            with patch.object(operations, "check_isolated_path", side_effect=record_check):
                with patch(
                    "ky.timetable_io.operations.replace_bytes",
                    side_effect=OSError("interrupted"),
                ):
                    with self.assertRaises(ContractError):
                        apply_staging(workspace, stage, isolation)
            self.assertTrue(any(path.name.endswith(".tmp") for path in isolated_checks))
            backups = tuple(timetable_path.parent.glob("*.previous-*.yaml"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            self.assertEqual(timetable_path.read_bytes(), original)
            retried = apply_staging(workspace, stage, isolation)
            self.assertEqual(retried.status, "applied")

    def test_cli_restaging_and_apply_exit_codes_and_single_isolation_check(self) -> None:
        from ky import __main__ as cli

        with tempfile.TemporaryDirectory() as temporary:
            workspace, timetable_path, _ = _workspace(Path(temporary) / "workspace")
            candidate = _staged(_semester("term-b", "2027-01-04"))
            incoming = workspace.root / "incoming.yaml"
            incoming.write_bytes(staged_to_bytes(candidate))
            stdout = io.StringIO()
            stderr = io.StringIO()
            isolated = Isolation("B", workspace.root, None)
            with patch.object(cli, "inspect_isolation", return_value=isolated) as inspect:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = cli.timetable_main(
                        ["restage", str(incoming), "--workspace", str(workspace.source)]
                    )
            self.assertEqual(code, 0, stderr.getvalue())
            self.assertEqual(inspect.call_count, 1)
            staged_path = next((workspace.root / "staging/timetables").glob("import--*.yaml"))
            with patch.object(cli, "inspect_isolation", return_value=isolated) as inspect:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = cli.timetable_main([
                        "apply", "--from-staging", str(staged_path),
                        "--workspace", str(workspace.source),
                    ])
            self.assertEqual(code, 0, stderr.getvalue())
            self.assertEqual(inspect.call_count, 1)
            self.assertTrue(timetable_path.read_bytes())
            self.assertIn("第 1 周课程网格", stdout.getvalue())

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.timetable_main(["apply"])
        self.assertEqual(code, 3)


class TimetableIORound236Tests(unittest.TestCase):
    """Regression cases from sol round 236 (R1 isolation of real temporaries, R2 one read)."""

    def test_file_level_ignores_allow_apply_and_check_the_replacement_temporary(self) -> None:
        import ky.storage.atomic as atomic
        import ky.timetable_io.operations as operations

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            workspace, target, _ = _workspace(root)
            _git(root, "init", "-q")
            (root / ".gitignore").write_text(
                "staging/\ndata/timetable.yaml\ndata/timetable.previous-*.yaml\n"
                "data/.timetable*.tmp\n",
                encoding="utf-8",
            )
            isolation = inspect_isolation(root)
            stage, _ = publish_staging(
                workspace, _staged(_semester("term-b", "2027-01-04")), isolation
            )
            created: list[Path] = []
            checked: list[Path] = []
            original_mkstemp = atomic.tempfile.mkstemp
            original_check = operations.check_isolated_path

            def recording_mkstemp(*args, **kwargs):
                descriptor, name = original_mkstemp(*args, **kwargs)
                created.append(Path(name).resolve())
                return descriptor, name

            def recording_check(state, path):
                checked.append(Path(path).resolve())
                return original_check(state, path)

            with patch.object(atomic.tempfile, "mkstemp", recording_mkstemp), \
                    patch.object(operations, "check_isolated_path", recording_check):
                result = apply_staging(workspace, stage, isolation)
            self.assertEqual(result.status, "applied")
            self.assertEqual(len(created), 1)
            self.assertIn(created[0], checked)
            self.assertNotIn(target.parent.resolve(), checked)
            labels = [item["label"] for item in yaml.safe_load(target.read_bytes())["semesters"]]
            self.assertIn("term-b", labels)

    def test_unignored_replacement_temporary_blocks_the_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            workspace, target, _ = _workspace(root)
            _git(root, "init", "-q")
            # Backup temporaries are ignored; only the replacement temporary is not.
            (root / ".gitignore").write_text(
                "staging/\ndata/timetable.yaml\ndata/timetable.previous-*.yaml\n"
                "data/.timetable.previous-*.tmp\n",
                encoding="utf-8",
            )
            before = target.read_bytes()
            isolation = inspect_isolation(root)
            stage, _ = publish_staging(
                workspace, _staged(_semester("term-b", "2027-01-04")), isolation
            )
            with self.assertRaises(ContractError):
                apply_staging(workspace, stage, isolation)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(len(list(target.parent.glob("timetable.previous-*.yaml"))), 1)
            self.assertEqual(list(target.parent.glob(".timetable*.tmp")), [])

    def test_shared_school_file_is_read_once_and_keeps_the_semester_error_path(self) -> None:
        from ky.timetable import timetable_for_workspace

        with tempfile.TemporaryDirectory() as temporary:
            workspace, target, school = _workspace(Path(temporary) / "fixture")
            registry = yaml.safe_load(workspace.source.read_bytes())
            registry["reference"]["timetable_schools"]["other"] = "data/schools/demo.yaml"
            workspace.source.write_text(yaml.safe_dump(registry), encoding="utf-8")
            table = yaml.safe_load(target.read_bytes())
            term = _semester("term-b", "2027-01-04")
            term["school"] = "other"
            table["semesters"].append(term)
            target.write_text(yaml.safe_dump(table), encoding="utf-8")
            original_read = Path.read_bytes
            reads: list[Path] = []

            def counted(path: Path) -> bytes:
                if path.name == school.name:
                    reads.append(path)
                return original_read(path)

            with patch.object(Path, "read_bytes", counted):
                with self.assertRaises(ContractError) as caught:
                    timetable_for_workspace(load_workspace(workspace.source))
            self.assertEqual(caught.exception.path, "semesters[1].school")
            self.assertEqual(len(reads), 1)


class TimetableIOIcsTests(unittest.TestCase):
    def _import_text(self, workspace, temporary: Path, text: str, **options):
        from ky.timetable_io import import_ics

        source = temporary / "synthetic.ics"
        source.write_bytes(text.encode("utf-8"))
        with redirect_stdout(io.StringIO()), patch(
            "ky.timetable_io.ics_import.inspect_isolation", _detached_isolation
        ):
            return import_ics(
                workspace, source, school="demo", label="candidate",
                week1=date(2026, 9, 7), **options,
            )

    def test_import_floating_event_publishes_a_candidate_semester(self) -> None:
        from ky.timetable_io import import_ics, read_staging

        with tempfile.TemporaryDirectory() as temporary:
            workspace, _, _ = _workspace(Path(temporary) / "fixture")
            source = Path(temporary) / "synthetic.ics"
            source.write_bytes((
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
                "UID:synthetic-1\r\nDTSTART:20260907T080000\r\n"
                "DTEND:20260907T084500\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
                "END:VCALENDAR\r\n"
            ).encode("utf-8"))
            with redirect_stdout(io.StringIO()):
                with patch(
                    "ky.timetable_io.ics_import.inspect_isolation",
                    _detached_isolation,
                ):
                    target = import_ics(
                        workspace, source, school="demo", label="candidate",
                        week1=date(2026, 9, 7),
                    )
            staged, _ = read_staging(target)
            self.assertEqual(staged.semester.label, "candidate")
            self.assertEqual(staged.semester.courses[0].name, "Math")
            self.assertEqual(staged.semester.courses[0].weeks, frozenset({1}))

    def test_export_writes_same_bytes_for_same_synthetic_workspace(self) -> None:
        from icalendar import Calendar
        from ky.models import ContractError
        from ky.timetable_io import export_ics

        with tempfile.TemporaryDirectory() as temporary:
            workspace, _, _ = _workspace(Path(temporary) / "fixture")
            config = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
            first = Path(temporary) / "first.ics"
            second = Path(temporary) / "second.ics"
            with patch("ky.timetable_io.ics_export.inspect_isolation", _detached_isolation):
                export_ics(workspace, date(2026, 9, 7), date(2026, 9, 8), config, first)
                export_ics(workspace, date(2026, 9, 7), date(2026, 9, 8), config, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertIn(b"VERSION:2.0", first.read_bytes())
            self.assertIn(b"SUMMARY:Math", first.read_bytes())
            class_only = Path(temporary) / "classes.ics"
            with patch("ky.timetable_io.ics_export.inspect_isolation", _detached_isolation):
                export_ics(
                    workspace, date(2026, 9, 7), date(2026, 9, 8), config,
                    class_only, classes_only=True,
                )
                with self.assertRaises(ContractError):
                    export_ics(
                        workspace, date(2026, 9, 7), date(2026, 9, 8), config, first
                    )
            full_uids = {
                str(item.get("UID"))
                for item in Calendar.from_ical(first.read_bytes()).walk("VEVENT")
                if str(item.get("SUMMARY")) == "Math"
            }
            class_uids = {
                str(item.get("UID"))
                for item in Calendar.from_ical(class_only.read_bytes()).walk("VEVENT")
            }
            self.assertEqual(full_uids, class_uids)

    def test_classes_only_can_publish_empty_calendar_for_a_covered_no_class_day(self) -> None:
        from icalendar import Calendar
        from ky.timetable_io import export_ics

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, table_path, _ = _workspace(root / "fixture")
            table = yaml.safe_load(table_path.read_bytes())
            table["semesters"][0]["exceptions"] = [
                {"date": "2026-09-07", "kind": "no_class"}
            ]
            table_path.write_text(
                yaml.safe_dump(table, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            config = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
            output = root / "empty.ics"
            with patch("ky.timetable_io.ics_export.inspect_isolation", _detached_isolation):
                export_ics(
                    workspace, date(2026, 9, 7), date(2026, 9, 8), config, output,
                    classes_only=True,
                )
            self.assertEqual(Calendar.from_ical(output.read_bytes()).walk("VEVENT"), [])

    def test_export_rejects_unignored_repo_target_and_uncovered_range(self) -> None:
        from ky.models import ContractError
        from ky.timetable_io import export_ics

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            workspace, _, _ = _workspace(root / "work")
            _git(root, "init", "-q")
            config = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
            output = root / "calendar.ics"
            with self.assertRaises(ContractError):
                export_ics(
                    workspace, date(2026, 9, 7), date(2026, 9, 8), config, output
                )
            self.assertFalse(output.exists())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            output = root / "uncovered.ics"
            config = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
            with patch("ky.timetable_io.ics_export.inspect_isolation", _detached_isolation):
                with self.assertRaises(ContractError):
                    export_ics(
                        workspace, date(2027, 1, 4), date(2027, 1, 5), config, output
                    )
            self.assertFalse(output.exists())

    def test_export_distinguishes_repeated_course_identity_with_stable_indexes(self) -> None:
        from icalendar import Calendar
        from ky.timetable_io import export_ics

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, table_path, _ = _workspace(root / "fixture")
            table = yaml.safe_load(table_path.read_bytes())
            table["semesters"][0]["courses"].append(
                dict(table["semesters"][0]["courses"][0])
            )
            table_path.write_text(
                yaml.safe_dump(table, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            config = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
            full, classes = root / "full.ics", root / "classes.ics"
            with patch("ky.timetable_io.ics_export.inspect_isolation", _detached_isolation):
                export_ics(workspace, date(2026, 9, 7), date(2026, 9, 8), config, full)
                export_ics(
                    workspace, date(2026, 9, 7), date(2026, 9, 8), config, classes,
                    classes_only=True,
                )
            events = [
                item for item in Calendar.from_ical(full.read_bytes()).walk("VEVENT")
                if str(item.get("SUMMARY")) == "Math"
            ]
            class_events = Calendar.from_ical(classes.read_bytes()).walk("VEVENT")
            self.assertEqual(len(events), 2)
            self.assertEqual(len({str(item.get("UID")) for item in events}), 2)
            self.assertEqual(
                {str(item.get("UID")) for item in events},
                {str(item.get("UID")) for item in class_events},
            )

    def test_weekly_count_and_exdate_use_original_instances(self) -> None:
        from ky.timetable_io import read_staging

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = (
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
                "UID:weekly\r\nDTSTART:20260907T080000\r\n"
                "DTEND:20260907T084500\r\nRRULE:FREQ=WEEKLY;COUNT=2\r\n"
                "EXDATE:20260914T080000\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
                "END:VCALENDAR\r\n"
            )
            staged, _ = read_staging(self._import_text(workspace, root, content))
            self.assertEqual(staged.semester.weeks, 1)
            self.assertEqual(staged.semester.courses[0].weeks, frozenset({1}))

    def test_unbounded_rule_requires_weeks_and_discards_projected_extra_instance(self) -> None:
        from ky.models import ContractError
        from ky.timetable_io import read_staging

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = (
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
                "UID:unbounded\r\nDTSTART:20260913T080000\r\n"
                "DTEND:20260913T084500\r\nRRULE:FREQ=WEEKLY;BYDAY=SU\r\n"
                "SUMMARY:Math\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
            )
            with self.assertRaises(ContractError) as caught:
                self._import_text(workspace, root, content)
            self.assertEqual(caught.exception.path, "UID unbounded.RRULE")
            staged, _ = read_staging(self._import_text(workspace, root, content, weeks=1))
            self.assertEqual(staged.semester.weeks, 1)
            self.assertEqual(staged.semester.courses[0].weeks, frozenset({1}))

    def test_utc_previous_day_is_mapped_by_target_local_date(self) -> None:
        from ky.timetable_io import read_staging

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = (
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
                "UID:utc\r\nDTSTART:20260906T230000Z\r\n"
                "DTEND:20260906T234500Z\r\nSUMMARY:Math\r\n"
                "END:VEVENT\r\nEND:VCALENDAR\r\n"
            )
            staged, _ = read_staging(self._import_text(
                workspace, root, content, timezone_name="Asia/Tokyo"
            ))
            self.assertEqual(staged.semester.courses[0].weekday, 1)

    def test_override_moved_outside_domain_is_rejected(self) -> None:
        from ky.models import ContractError

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = (
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
                "UID:moved\r\nDTSTART:20260907T080000\r\n"
                "DTEND:20260907T084500\r\nRRULE:FREQ=WEEKLY;COUNT=1\r\n"
                "SUMMARY:Math\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:moved\r\n"
                "RECURRENCE-ID:20260907T080000\r\n"
                "DTSTART:20260914T080000\r\nDTEND:20260914T084500\r\n"
                "END:VEVENT\r\nEND:VCALENDAR\r\n"
            )
            with self.assertRaises(ContractError) as caught:
                self._import_text(workspace, root, content, weeks=1)
            self.assertEqual(caught.exception.path, "UID moved.DTSTART")

    def test_rrule_interval_byday_until_and_multiple_exdates(self) -> None:
        from ky.timetable_io import read_staging

        cases = (
            (
                "RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=3\r\n",
                "DTSTART:20260907T080000\r\nDTEND:20260907T084500\r\n",
                5, [(1, frozenset({1, 3, 5}))],
            ),
            (
                "RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=3\r\n",
                "DTSTART:20260907T080000\r\nDTEND:20260907T084500\r\n",
                2, [(1, frozenset({1, 2})), (3, frozenset({1}))],
            ),
            (
                "RRULE:FREQ=WEEKLY;UNTIL=20260921T080000\r\n",
                "DTSTART:20260907T080000\r\nDTEND:20260907T084500\r\n",
                3, [(1, frozenset({1, 2, 3}))],
            ),
            (
                "RRULE:FREQ=WEEKLY;COUNT=4\r\n"
                "EXDATE:20260914T080000,20260921T080000\r\n"
                "EXDATE:20260928T080000\r\n",
                "DTSTART:20260907T080000\r\nDTEND:20260907T084500\r\n",
                1, [(1, frozenset({1}))],
            ),
        )
        for index, (recurrence, dates, expected_weeks, courses) in enumerate(cases):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                workspace, _, _ = _workspace(root / "fixture")
                event = (
                    "BEGIN:VEVENT\r\nUID:rule\r\n" + dates + recurrence
                    + "SUMMARY:Math\r\nEND:VEVENT\r\n"
                )
                content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{event}END:VCALENDAR\r\n"
                staged, _ = read_staging(self._import_text(workspace, root, content))
                self.assertEqual(staged.semester.weeks, expected_weeks)
                actual = sorted(
                    (course.weekday, course.weeks) for course in staged.semester.courses
                )
                self.assertEqual(actual, courses)

    def test_cancelled_and_moved_overrides_replace_original_occurrence(self) -> None:
        from ky.timetable_io import read_staging

        cancelled = (
            "BEGIN:VEVENT\r\nUID:cancel\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nRRULE:FREQ=WEEKLY;COUNT=3\r\n"
            "SUMMARY:Math\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:cancel\r\n"
            "RECURRENCE-ID:20260914T080000\r\nSTATUS:CANCELLED\r\n"
            "END:VEVENT\r\n"
        )
        moved = (
            "BEGIN:VEVENT\r\nUID:move\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nRRULE:FREQ=WEEKLY;COUNT=3\r\n"
            "SUMMARY:Math\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:move\r\n"
            "RECURRENCE-ID:20260914T080000\r\nDTSTART:20260915T080000\r\n"
            "DTEND:20260915T084500\r\nEND:VEVENT\r\n"
        )
        for event, expected in (
            (cancelled, [(1, frozenset({1, 3}))]),
            (moved, [(1, frozenset({1, 3})), (2, frozenset({2}))]),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                workspace, _, _ = _workspace(root / "fixture")
                content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{event}END:VCALENDAR\r\n"
                staged, _ = read_staging(self._import_text(workspace, root, content))
                actual = sorted(
                    (course.weekday, course.weeks) for course in staged.semester.courses
                )
                self.assertEqual(actual, expected)

    def test_skipped_all_day_cross_date_and_missing_end_events_make_visible_notes(self) -> None:
        from ky.timetable_io import read_staging

        event = (
            "BEGIN:VEVENT\r\nUID:valid\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
            "BEGIN:VEVENT\r\nUID:all-day\r\nDTSTART;VALUE=DATE:20300101\r\n"
            "DTEND;VALUE=DATE:20300102\r\nSUMMARY:Ignored\r\nEND:VEVENT\r\n"
            "BEGIN:VEVENT\r\nUID:cross\r\nDTSTART:20260907T230000\r\n"
            "DTEND:20260908T000000\r\nSUMMARY:Cross\r\nEND:VEVENT\r\n"
            "BEGIN:VEVENT\r\nUID:no-end\r\nDTSTART:20260907T080000\r\n"
            "SUMMARY:No end\r\nEND:VEVENT\r\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{event}END:VCALENDAR\r\n"
            staged, _ = read_staging(self._import_text(workspace, root, content))
            self.assertEqual(len(staged.notes), 3)
            self.assertEqual(staged.semester.courses[0].name, "Math")

    def test_floating_timezone_seconds_and_dtend_duration_rules(self) -> None:
        from ky.models import ContractError
        from ky.timetable_io import read_staging

        floating = (
            "BEGIN:VEVENT\r\nUID:floating\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{floating}END:VCALENDAR\r\n"
            staged, _ = read_staging(self._import_text(
                workspace, root, content, timezone_name="Asia/Tokyo"
            ))
            self.assertEqual(staged.semester.courses[0].weekday, 1)

        cases = (
            ("DTSTART:20260907T080000Z\r\nDTEND:20260907T084500Z\r\n", None),
            ("DTSTART;TZID=Unknown/Zone:20260907T080000\r\n"
             "DTEND;TZID=Unknown/Zone:20260907T084500\r\n", "Asia/Tokyo"),
            ("DTSTART:20260907T080030\r\nDTEND:20260907T084530\r\n", None),
            ("DTSTART:20260907T080000\r\nDTEND:20260907T084500\r\n"
             "DURATION:PT45M\r\n", None),
        )
        for index, (times, zone) in enumerate(cases):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                workspace, _, _ = _workspace(root / "fixture")
                event = (
                    "BEGIN:VEVENT\r\nUID:invalid\r\n" + times
                    + "SUMMARY:Math\r\nEND:VEVENT\r\n"
                )
                content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{event}END:VCALENDAR\r\n"
                with self.assertRaises(ContractError):
                    self._import_text(workspace, root, content, timezone_name=zone)

    def test_duration_repeats_from_each_occurrence_and_invalid_import_keys_fail(self) -> None:
        from ky.models import ContractError
        from ky.timetable_io import read_staging

        duration_event = (
            "BEGIN:VEVENT\r\nUID:duration\r\nDTSTART:20260907T080000\r\n"
            "DURATION:PT45M\r\nRRULE:FREQ=WEEKLY;COUNT=2\r\n"
            "SUMMARY:Math\r\nEND:VEVENT\r\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{duration_event}END:VCALENDAR\r\n"
            staged, _ = read_staging(self._import_text(workspace, root, content))
            self.assertEqual(staged.semester.courses[0].weeks, frozenset({1, 2}))

        invalid_events = (
            "BEGIN:VEVENT\r\nUID:rdate\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nRDATE:20260914T080000\r\nSUMMARY:Math\r\n"
            "END:VEVENT\r\n",
            "BEGIN:VEVENT\r\nUID:daily\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nRRULE:FREQ=DAILY;COUNT=2\r\n"
            "SUMMARY:Math\r\nEND:VEVENT\r\n",
            "BEGIN:VEVENT\r\nUID:blank\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nSUMMARY:  \r\nEND:VEVENT\r\n",
            "BEGIN:VEVENT\r\nUID:mismatch\r\nDTSTART;VALUE=DATE:20260907\r\n"
            "DTEND:20260907T084500\r\nSUMMARY:Math\r\nEND:VEVENT\r\n",
        )
        for index, event in enumerate(invalid_events):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                workspace, _, _ = _workspace(root / "fixture")
                content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{event}END:VCALENDAR\r\n"
                with self.assertRaises(ContractError):
                    self._import_text(workspace, root, content)

    def test_invalid_duration_is_contract_error_and_not_staged(self) -> None:
        event = (
            "BEGIN:VEVENT\r\nUID:cut-duration\r\nDTSTART:20260907T080000\r\n"
            "DURATION:PT45\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{event}END:VCALENDAR\r\n"
            with self.assertRaises(ContractError) as caught:
                self._import_text(workspace, root, content)
            self.assertIn("UID cut-duration.DURATION", str(caught.exception))
            self.assertFalse(list((root / "fixture" / "staging").rglob("*.yaml")))

    def test_duplicate_course_occurrence_rejects_but_different_summary_is_kept(self) -> None:
        from ky.models import ContractError
        from ky.timetable_io import read_staging

        def event(uid: str, summary: str) -> str:
            return (
                f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART:20260907T080000\r\n"
                f"DTEND:20260907T084500\r\nSUMMARY:{summary}\r\nEND:VEVENT\r\n"
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            duplicate = event("one", "Math") + event("two", "Math")
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{duplicate}END:VCALENDAR\r\n"
            with self.assertRaises(ContractError):
                self._import_text(workspace, root, content)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            collision = event("one", "Math") + event("two", "Physics")
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{collision}END:VCALENDAR\r\n"
            staged, _ = read_staging(self._import_text(workspace, root, content))
            self.assertEqual(len(staged.semester.courses), 2)

    def test_cli_import_export_and_usage_exit_codes(self) -> None:
        from ky.__main__ import timetable_main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            source = root / "synthetic.ics"
            source.write_bytes(
                b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
                b"UID:cli\r\nDTSTART:20260907T080000\r\n"
                b"DTEND:20260907T084500\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
                b"END:VCALENDAR\r\n"
            )
            config = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
            output = root / "export.ics"
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch("ky.timetable_io.ics_import.inspect_isolation", _detached_isolation), \
                    patch("ky.timetable_io.ics_export.inspect_isolation", _detached_isolation), \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                import_args = [
                    "import-ics", str(source), "--school", "demo", "--label", "cli-term",
                    "--week1", "2026-09-07", "--workspace", str(workspace.source),
                ]
                imported = timetable_main(import_args)
                repeated_import = timetable_main(import_args)
                exported = timetable_main([
                    "export-ics", "--from", "2026-09-07", "--to", "2026-09-08",
                    "--config", str(config), "--out", str(output),
                    "--workspace", str(workspace.source),
                ])
                usage = timetable_main([
                    "export-ics", "--from", "2026-09-08", "--to", "2026-09-07",
                    "--config", str(config), "--out", str(root / "invalid.ics"),
                    "--workspace", str(workspace.source),
                ])
            self.assertEqual((imported, repeated_import, exported, usage), (0, 0, 0, 3))
            self.assertTrue(output.is_file())
            self.assertEqual(stderr.getvalue(), "--from must precede --to\n")

    def test_long_free_gap_splits_course_events_only_for_positive_intersection(self) -> None:
        from icalendar import Calendar
        from ky.timetable_io import export_ics

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, table_path, school_path = _workspace(root / "fixture")
            school = yaml.safe_load(school_path.read_bytes())
            school["periods"] = {
                1: {"start": "09:00", "end": "10:00"},
                2: {"start": "13:00", "end": "14:00"},
            }
            school["blocks"] = [[1, 2]]
            school_path.write_text(
                yaml.safe_dump(school, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            table = yaml.safe_load(table_path.read_bytes())
            table["rules"].update(
                study_window={"start": "08:00", "end": "16:00"},
                buffer_minutes=0, min_gap_minutes=0, block_deduction_minutes=0,
            )
            table_path.write_text(
                yaml.safe_dump(table, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            output = root / "split.ics"
            config = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
            with patch("ky.timetable_io.ics_export.inspect_isolation", _detached_isolation):
                export_ics(
                    workspace, date(2026, 9, 7), date(2026, 9, 8), config, output,
                    classes_only=True,
                )
            parsed = Calendar.from_ical(output.read_bytes())
            events = [item for item in parsed.walk("VEVENT") if str(item.get("SUMMARY")) == "Math"]
            intervals = [
                (item.get("DTSTART").dt.time(), item.get("DTEND").dt.time())
                for item in events
            ]
            self.assertEqual(intervals, [(time(9), time(10)), (time(13), time(14))])

    def test_independent_single_events_merge_and_school_is_read_once(self) -> None:
        from ky.timetable_io import read_staging

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, school_path = _workspace(root / "fixture")
            events = "".join(
                f"BEGIN:VEVENT\r\nUID:one-{day}\r\n"
                f"DTSTART:202609{day:02d}T080000\r\n"
                f"DTEND:202609{day:02d}T084500\r\n"
                "SUMMARY:Math\r\nEND:VEVENT\r\n"
                for day in (7, 14, 21)
            )
            source = root / "three.ics"
            source.write_bytes(
                f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{events}END:VCALENDAR\r\n".encode()
            )
            original_read_bytes = Path.read_bytes
            reads = []

            def counted(path):
                if path == school_path:
                    reads.append(path)
                return original_read_bytes(path)

            with patch.object(Path, "read_bytes", counted), redirect_stdout(io.StringIO()), \
                    patch("ky.timetable_io.ics_import.inspect_isolation", _detached_isolation):
                from ky.timetable_io import import_ics

                target = import_ics(
                    workspace, source, school="demo", label="candidate",
                    week1=date(2026, 9, 7),
                )
            staged, _ = read_staging(target)
            self.assertEqual(len(reads), 1)
            self.assertEqual(staged.semester.courses[0].weeks, frozenset({1, 2, 3}))

    def test_timezone_validation_skips_excluded_events_and_checks_each_exdate(self) -> None:
        from ky.timetable_io import read_staging

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            events = (
                "BEGIN:VEVENT\r\nUID:cancelled\r\nDTSTART:20260907T080000Z\r\n"
                "DTEND:20260907T084500Z\r\nSTATUS:CANCELLED\r\n"
                "SUMMARY:Ignored\r\nEND:VEVENT\r\n"
                "BEGIN:VEVENT\r\nUID:active\r\nDTSTART:20260907T080000\r\n"
                "DTEND:20260907T084500\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
            )
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{events}END:VCALENDAR\r\n"
            staged, _ = read_staging(self._import_text(workspace, root, content))
            self.assertEqual(staged.semester.courses[0].name, "Math")
            self.assertTrue(any("cancelled" in note for note in staged.notes))

        invalid = (
            "BEGIN:VEVENT\r\nUID:bad-exdate\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nEXDATE;TZID=Unknown/Zone:20260914T080000\r\n"
            "SUMMARY:Math\r\nEND:VEVENT\r\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{invalid}END:VCALENDAR\r\n"
            with self.assertRaises(ContractError) as caught:
                self._import_text(workspace, root, content)
            self.assertIn("EXDATE.TZID", caught.exception.path)
            self.assertFalse(list((root / "fixture" / "staging").rglob("*.yaml")))

    def test_repeated_import_keeps_staging_bytes_and_skips_second_publish(self) -> None:
        from ky.timetable_io import import_ics
        from ky.timetable_io.ics_import import publish_staging as real_publish

        event = (
            "BEGIN:VEVENT\r\nUID:repeat\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            source = root / "repeat.ics"
            source.write_bytes(
                f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{event}END:VCALENDAR\r\n".encode()
            )
            results = []

            def tracked_publish(*args, **kwargs):
                result = real_publish(*args, **kwargs)
                results.append(result[1])
                return result

            with patch("ky.timetable_io.ics_import.publish_staging", tracked_publish), \
                    patch("ky.timetable_io.ics_import.inspect_isolation", _detached_isolation), \
                    redirect_stdout(io.StringIO()):
                first = import_ics(
                    workspace, source, school="demo", label="candidate",
                    week1=date(2026, 9, 7),
                )
                before = first.read_bytes()
                second = import_ics(
                    workspace, source, school="demo", label="candidate",
                    week1=date(2026, 9, 7),
                )
            self.assertEqual(first, second)
            self.assertEqual(first.read_bytes(), before)
            self.assertEqual(results, [True, False])

    def test_valid_tzid_and_mixed_timezone_domain_have_contract_results(self) -> None:
        from ky.timetable_io import read_staging

        event = (
            "BEGIN:VEVENT\r\nUID:tokyo\r\n"
            "DTSTART;TZID=Asia/Tokyo:20260907T080000\r\n"
            "DTEND;TZID=Asia/Tokyo:20260907T084500\r\n"
            "SUMMARY:Math\r\nEND:VEVENT\r\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{event}END:VCALENDAR\r\n"
            staged, _ = read_staging(
                self._import_text(workspace, root, content, timezone_name="Asia/Tokyo")
            )
            self.assertEqual(staged.semester.courses[0].weekday, 1)

        mixed = (
            "BEGIN:VEVENT\r\nUID:mixed\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500Z\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{mixed}END:VCALENDAR\r\n"
            with self.assertRaises(ContractError) as caught:
                self._import_text(workspace, root, content, timezone_name="UTC")
            self.assertIn("UID mixed.DTEND", caught.exception.path)

    def test_period_boundary_failures_are_aggregated_and_never_staged(self) -> None:
        events = "".join(
            f"BEGIN:VEVENT\r\nUID:bad-{day}\r\n"
            f"DTSTART:20260907T{start}\r\nDTEND:20260907T{end}\r\n"
            "SUMMARY:Math\r\nEND:VEVENT\r\n"
            for day, start, end in (
                (1, "080100", "084500"), (2, "080000", "084600"),
                (3, "080200", "084700"),
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{events}END:VCALENDAR\r\n"
            with self.assertRaises(ContractError) as caught:
                self._import_text(workspace, root, content)
            message = str(caught.exception)
            for uid in ("bad-1", "bad-2", "bad-3"):
                self.assertIn(uid, message)
            self.assertIn("DTSTART", message)
            self.assertIn("DTEND", message)
            self.assertFalse(list((root / "fixture" / "staging").rglob("*.yaml")))

    def test_invalid_override_shapes_and_empty_import_do_not_publish(self) -> None:
        invalid_sets = (
            "BEGIN:VEVENT\r\nUID:orphan\r\nRECURRENCE-ID:20260907T080000\r\n"
            "DTSTART:20260907T080000\r\nDTEND:20260907T084500\r\nEND:VEVENT\r\n",
            "BEGIN:VEVENT\r\nUID:range\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nRRULE:FREQ=WEEKLY;COUNT=2\r\n"
            "SUMMARY:Math\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:range\r\n"
            "RECURRENCE-ID;RANGE=THISANDFUTURE:20260914T080000\r\n"
            "DTSTART:20260914T080000\r\nEND:VEVENT\r\n",
            "BEGIN:VEVENT\r\nUID:duplicate\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nRRULE:FREQ=WEEKLY;COUNT=2\r\n"
            "SUMMARY:Math\r\nEND:VEVENT\r\n"
            "BEGIN:VEVENT\r\nUID:duplicate\r\nRECURRENCE-ID:20260914T080000\r\n"
            "DTSTART:20260914T080000\r\nEND:VEVENT\r\n"
            "BEGIN:VEVENT\r\nUID:duplicate\r\nRECURRENCE-ID:20260914T080000\r\n"
            "DTSTART:20260914T080000\r\nEND:VEVENT\r\n",
            "BEGIN:VEVENT\r\nUID:ex-conflict\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nRRULE:FREQ=WEEKLY;COUNT=2\r\n"
            "EXDATE:20260914T080000\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
            "BEGIN:VEVENT\r\nUID:ex-conflict\r\nRECURRENCE-ID:20260914T080000\r\n"
            "DTSTART:20260914T080000\r\nEND:VEVENT\r\n",
        )
        for index, event in enumerate(invalid_sets):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                workspace, _, _ = _workspace(root / "fixture")
                content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{event}END:VCALENDAR\r\n"
                with self.assertRaises(ContractError):
                    self._import_text(workspace, root, content)
                self.assertFalse(list((root / "fixture" / "staging").rglob("*.yaml")))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            excluded = (
                "BEGIN:VEVENT\r\nUID:only-all-day\r\nDTSTART;VALUE=DATE:20260907\r\n"
                "DTEND;VALUE=DATE:20260908\r\nSUMMARY:Ignored\r\nEND:VEVENT\r\n"
            )
            content = f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{excluded}END:VCALENDAR\r\n"
            with self.assertRaises(ContractError):
                self._import_text(workspace, root, content)
            self.assertFalse(list((root / "fixture" / "staging").rglob("*.yaml")))

    def test_export_marks_event_transparency_categories_and_floating_times(self) -> None:
        from icalendar import Calendar
        from ky.timetable_io import export_ics

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, _ = _workspace(root / "fixture")
            output = root / "marked.ics"
            config = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
            with patch("ky.timetable_io.ics_export.inspect_isolation", _detached_isolation):
                export_ics(
                    workspace, date(2026, 9, 7), date(2026, 9, 8), config, output,
                )
            events = Calendar.from_ical(output.read_bytes()).walk("VEVENT")
            by_summary = {str(item.get("SUMMARY")): item for item in events}
            self.assertEqual(str(by_summary["Math"].get("TRANSP")), "OPAQUE")
            self.assertIsNone(by_summary["Math"].get("CATEGORIES"))
            self.assertIsNone(by_summary["Math"].get("DTSTART").dt.tzinfo)
            free = next(item for item in events if str(item.get("TRANSP")) == "TRANSPARENT")
            self.assertEqual(free.get("CATEGORIES").to_ical(), b"STUDY")
            self.assertIsNone(free.get("DTSTART").dt.tzinfo)

    def test_pdf_import_reuses_loaded_school_for_preview(self) -> None:
        from ky.timetable_io import Isolation
        from ky.timetable_io.zfsoft_pdf import import_zfsoft_pdf

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, _, school_path = _workspace(root / "fixture")
            school = yaml.safe_load(school_path.read_bytes())
            school["system"] = "zfsoft"
            school["periods"][1]["unconfirmed"] = True
            school_path.write_text(
                yaml.safe_dump(school, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            from tests.contract.test_timetable_io_zfsoft_pdf import _valid

            original_read_bytes = Path.read_bytes
            reads = []

            def counted(path):
                if path == school_path:
                    reads.append(path)
                return original_read_bytes(path)

            with patch.object(Path, "read_bytes", counted), \
                    patch("ky.timetable_io.zfsoft_pdf.extract_fragments", return_value=_valid()), \
                    redirect_stdout(io.StringIO()):
                result = import_zfsoft_pdf(
                    b"synthetic pdf bytes", workspace,
                    Isolation("B", workspace.root, None),
                    school_id="demo", label="candidate", week1="2026-09-07",
                )
            self.assertEqual(len(reads), 1)
            self.assertTrue(any(line.startswith(" 1* ") for line in result.grid))


class TimetableIOBaseResolverTests(unittest.TestCase):
    """Preview and export resolve the M8 base per day once M28b made it phase-dependent."""

    def test_base_resolver_uses_the_route_phase_then_the_config(self) -> None:
        from datetime import date as day_type

        from ky.models import load_config
        from ky.schedule.planning import Phase, RoutePlan
        from ky.storage.route_store import RoutePlanStore
        from ky.timetable_io import base_resolver

        config_path = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
        config = load_config(config_path)
        start, end = day_type(2026, 9, 7), day_type(2026, 9, 14)
        minutes = {subject.subject_id: 10 for subject in config.active_subjects()}
        route = RoutePlan(
            route_id="base-resolver", revision=1, start_date=start, target_exam_date=end,
            policy_version="policy-v1", stage1_input_hash="0" * 64,
            phases=(Phase(0, start, end, "phase", minutes, base_daily_minutes=210),),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            workspace, _, _ = _workspace(root)
            registry = yaml.safe_load(workspace.source.read_bytes())
            registry["state"]["routes"] = "data/routes"
            workspace.source.write_text(yaml.safe_dump(registry), encoding="utf-8")
            workspace = load_workspace(workspace.source)
            RoutePlanStore(workspace.write_target("state.routes")).write_route_plan(route)
            base_for = base_resolver(workspace, config)
            self.assertEqual(base_for(day_type(2026, 9, 8)), 210)
            self.assertEqual(base_for(day_type(2026, 9, 20)), config.default_daily_minutes)

    def test_base_resolver_uses_registered_pacing_initial_after_the_route(self) -> None:
        from datetime import date as day_type

        from ky.models import load_config
        from ky.schedule.planning import Phase, RoutePlan
        from ky.storage.route_store import RoutePlanStore
        from ky.timetable_io import base_resolver

        config_path = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
        config = load_config(config_path)
        start, end = day_type(2026, 9, 7), day_type(2026, 9, 14)
        minutes = {subject.subject_id: 10 for subject in config.active_subjects()}
        route = RoutePlan(
            route_id="base-resolver", revision=1, start_date=start, target_exam_date=end,
            policy_version="policy-v1", stage1_input_hash="0" * 64,
            phases=(Phase(0, start, end, "phase", minutes, base_daily_minutes=210),),
        )
        settings = {
            "schema_version": 1, "start": "2026-09-01", "exam_date": "2028-12-23",
            "base_daily_minutes": {"min": 120, "max": 240, "initial": 195},
            "max_step_minutes": 30, "cadence": [{"kind": "month"}],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            workspace, _, _ = _workspace(root)
            (root / "settings").mkdir()
            (root / "settings" / "pacing.yaml").write_text(
                yaml.safe_dump(settings), encoding="utf-8",
            )
            registry = yaml.safe_load(workspace.source.read_bytes())
            registry["state"]["routes"] = "data/routes"
            registry.setdefault("settings", {})["pacing"] = "settings/pacing.yaml"
            workspace.source.write_text(yaml.safe_dump(registry), encoding="utf-8")
            workspace = load_workspace(workspace.source)
            RoutePlanStore(workspace.write_target("state.routes")).write_route_plan(route)
            base_for = base_resolver(workspace, config)
            # M8 order (contracts/pacing_review.md §5): route phase > pacing initial > config.
            self.assertEqual(base_for(day_type(2026, 9, 8)), 210)
            self.assertEqual(base_for(day_type(2026, 9, 20)), 195)
            self.assertEqual(base_for(day_type(2026, 8, 20)), config.default_daily_minutes)

    def test_preview_resolves_each_route_phase_and_reads_the_route_once(self) -> None:
        from datetime import date as day_type

        from ky.models import load_config
        from ky.schedule.planning import Phase, RoutePlan
        from ky.storage.route_store import RoutePlanStore
        from ky.timetable import load_referenced_schools
        from ky.timetable_io import preview_lines

        config_path = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
        config = load_config(config_path)
        start, middle, end = (
            day_type(2026, 9, 7), day_type(2026, 9, 10), day_type(2026, 9, 21)
        )
        minutes = {subject.subject_id: 10 for subject in config.active_subjects()}
        route = RoutePlan(
            route_id="preview-phases", revision=1, start_date=start, target_exam_date=end,
            policy_version="policy-v1", stage1_input_hash="0" * 64,
            phases=(
                Phase(0, start, middle, "phase-one", minutes, base_daily_minutes=210),
                Phase(1, middle, end, "phase-two", minutes, base_daily_minutes=120),
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _, school_path = _workspace(Path(temporary) / "workspace")
            school = yaml.safe_load(school_path.read_bytes())
            school["periods"][1]["unconfirmed"] = True
            school_path.write_text(
                yaml.safe_dump(school, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            registry = yaml.safe_load(workspace.source.read_bytes())
            registry["state"]["routes"] = "data/routes"
            registry_path = workspace.source
            registry_path.write_text(
                yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            workspace = load_workspace(registry_path)
            RoutePlanStore(workspace.write_target("state.routes")).write_route_plan(route)
            schools = load_referenced_schools(workspace, ("demo",))
            calls = []
            original_current = RoutePlanStore.current

            def counted_current(store):
                calls.append(store.root)
                return original_current(store)

            with patch.object(RoutePlanStore, "current", counted_current):
                lines = preview_lines(workspace, _staged().semester, config_path, schools=schools)
            self.assertEqual(len(calls), 1)
            self.assertTrue(any(line.startswith(" 1* ") for line in lines))
            self.assertEqual(lines[-1], "minutes            : 160 210 210 120 120 120 120")


class TimetableIORound249Tests(unittest.TestCase):
    """sol round 249 N1: shape checks apply to skipped events too, next to a valid course."""

    def test_skipped_events_still_fail_shape_checks(self) -> None:
        from contextlib import redirect_stdout
        from datetime import date as day_type

        from ky.timetable_io import import_ics

        valid = (
            "BEGIN:VEVENT\r\nUID:valid\r\nDTSTART:20260907T080000\r\n"
            "DTEND:20260907T084500\r\nSUMMARY:Math\r\nEND:VEVENT\r\n"
        )
        cases = {
            "mixed-types": (
                "BEGIN:VEVENT\r\nUID:mismatch\r\nDTSTART;VALUE=DATE:20260907\r\n"
                "DTEND:20260907T084500\r\nSUMMARY:Ignore\r\nEND:VEVENT\r\n"
            ),
            "cancelled-both": (
                "BEGIN:VEVENT\r\nUID:cancel-both\r\nDTSTART:20260907T080000\r\n"
                "DTEND:20260907T084500\r\nDURATION:PT45M\r\n"
                "STATUS:CANCELLED\r\nSUMMARY:Ignore\r\nEND:VEVENT\r\n"
            ),
        }
        for name, bad in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                workspace, _, _ = _workspace(root / "fixture")
                source = root / "input.ics"
                source.write_bytes(
                    ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + valid + bad
                     + "END:VCALENDAR\r\n").encode("utf-8")
                )
                with patch("ky.timetable_io.ics_import.inspect_isolation", _detached_isolation), \
                        redirect_stdout(io.StringIO()):
                    with self.assertRaises(ContractError):
                        import_ics(workspace, source, school="demo", label="candidate",
                                   week1=day_type(2026, 9, 7))
                self.assertFalse((root / "fixture" / "staging" / "timetables").exists()
                                 and any((root / "fixture" / "staging" / "timetables").iterdir()))
