"""Contract tests for fixed source identity and raw baseline comparison."""

from __future__ import annotations

import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
from pathlib import Path

from tests._baseline_harness import (
    ProcessResult,
    compare_results,
    fixed_source,
    load_isolated,
)

ROOT = Path(__file__).resolve().parents[1]


class BaselineHarnessTest(unittest.TestCase):
    def test_head_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixed commit hash"):
            fixed_source(ROOT, "HEAD", "AGENTS.md", lambda _source: True)

    def test_legacy_identity_failure_is_reported(self) -> None:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True
        ).stdout.decode("ascii").strip()
        with self.assertRaisesRegex(AssertionError, "identity check failed"):
            fixed_source(ROOT, commit, "AGENTS.md", lambda _source: False)

    def test_byte_difference_is_reported(self) -> None:
        old = ProcessResult(0, b"out", b"")
        new = ProcessResult(0, b"OUT", b"")
        with self.assertRaisesRegex(AssertionError, "process bytes differ"):
            compare_results(old, new)
        with self.assertRaisesRegex(AssertionError, "file tree bytes differ"):
            compare_results(old, old, {"result": b"a"}, {"result": b"b"})

    def test_equal_process_and_tree_pass(self) -> None:
        result = ProcessResult(0, b"out", b"")
        compare_results(result, result, {"result": b"file"}, {"result": b"file"})

    def test_state_snapshot_mutations_trip_original_and_harness_instance(self) -> None:
        test_path = ROOT / "tests/contract/test_state_snapshot_counts_baseline.py"
        original_test = fixed_source(
            ROOT,
            "f52b8f6",
            "tests/contract/test_state_snapshot_counts_baseline.py",
            lambda raw: b"test_snapshot_json_matches_pinned_m12_with_date_boundaries" in raw,
        ).decode("utf-8")
        rewritten_test = test_path.read_text(encoding="utf-8")
        implementation_path = ROOT / "ky/schedule/state_snapshot.py"
        implementation = implementation_path.read_text(encoding="utf-8")
        mutations = (
            (
                "in_review_queue=counts.in_review_queue,",
                "in_review_queue=counts.in_review_queue + 1,",
            ),
            (
                "due_today_count=counts.due_today_count,",
                "due_today_count=counts.due_today_count + 1,",
            ),
        )

        def run_test(test_source: str, build_snapshot, should_fail: bool) -> None:
            module = types.ModuleType("_snapshot_baseline_probe")
            module.__file__ = str(test_path)
            module.__package__ = "tests.contract"
            with patch(
                "ky.schedule.state_snapshot.build_snapshot", build_snapshot
            ):
                exec(compile(test_source, str(test_path), "exec"), module.__dict__)
                case = module.StateSnapshotCountsBaselineTests(
                    "test_snapshot_json_matches_pinned_m12_with_date_boundaries"
                )
                result = unittest.TestResult()
                case.run(result)
            failed = bool(result.failures or result.errors)
            self.assertEqual(failed, should_fail, result.errors + result.failures)

        from ky.schedule.state_snapshot import build_snapshot as current_build

        run_test(original_test, current_build, should_fail=False)
        run_test(rewritten_test, current_build, should_fail=False)
        for index, (before, after) in enumerate(mutations):
            self.assertEqual(implementation.count(before), 1, before)
            mutated = implementation.replace(before, after, 1)
            with tempfile.TemporaryDirectory() as temporary:
                source_path = Path(temporary) / "state_snapshot.py"
                source_path.write_text(mutated, encoding="utf-8")
                module = load_isolated(
                    source_path.read_bytes(), f"state_snapshot_mutation_{index}"
                )
                run_test(original_test, module.build_snapshot, should_fail=True)
                run_test(rewritten_test, module.build_snapshot, should_fail=True)


if __name__ == "__main__":
    unittest.main()
