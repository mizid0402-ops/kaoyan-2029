"""Regression locks for the read-only state snapshot (round-37 §4.2).

Two hard requirements from the task book:

  1. ``build_snapshot`` must never write a file (verified with a filesystem-mtime sandbox check
     on the real, committed knowledge trees and vocabulary database).
  2. Every number derived from a knowledge tree must carry ``tree_status`` -- honest, because all
     three committed trees are currently 100% ``status="extracted"`` (none ``approved``), and the
     contract forbids treating ``extracted`` counts as coverage.
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(REPO_ROOT))

from ky.models import load_config, validate_review_item  # noqa: E402
from ky.schedule.state_snapshot import build_snapshot  # noqa: E402
from ky.workspace import load_workspace  # noqa: E402

CONFIG_PATH = REPO_ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
WORKSPACE = load_workspace(REPO_ROOT / "kaoyan.workspace.yaml")
VOCAB_DB = WORKSPACE.vocabulary_db
TODAY = date(2026, 9, 15)
HAVE_TREES = all(
    subject in WORKSPACE.knowledge_trees and WORKSPACE.knowledge_trees[subject].is_file()
    for subject in ("math1", "eng1", "cs408")
)
HAVE_VOCAB_DB = VOCAB_DB.is_file()


def make_item(review_id: str, **overrides):
    mapping = {
        "review_id": review_id,
        "revision": 1,
        "subject_id": "math1",
        "knowledge_point_id": f"math1.demo.{review_id}",
        "title": review_id,
        "granularity": "concept",
        "state": "queued",
        "estimated_minutes": 10,
        "introduced_on": "2026-09-01",
        "due_date": "2026-09-15",
        "schedule": {
            "mode": "fixed_bootstrap",
            "phase": 1,
            "interval_days": 3,
            "ease_factor": 2.5,
            "repetitions": 1,
            "lapses": 0,
        },
        "defer_count": 0,
        "last_quality": 4,
    }
    mapping.update(overrides)
    return validate_review_item(mapping)


class SandboxReadOnlyTest(unittest.TestCase):
    """Proves build_snapshot never writes: every file it can reach is snapshotted by mtime
    before and after, over every subject and the vocab database."""

    @unittest.skipUnless(HAVE_TREES and HAVE_VOCAB_DB, "committed trees/vocab db not present")
    def test_zero_filesystem_writes(self) -> None:
        config = load_config(CONFIG_PATH)
        items = (make_item("rv1"), make_item("rv2", subject_id="eng1"))

        watched = [
            WORKSPACE.require(f"reference.knowledge_trees.{s.subject_id}")
            for s in config.subjects
            if s.subject_id in WORKSPACE.knowledge_trees
        ] + [WORKSPACE.require("reference.vocabulary_db")]
        before = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched}

        build_snapshot(
            config, items, today=TODAY, target_exam_date=date(2028, 12, 20), workspace=WORKSPACE
        )

        after = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched}
        self.assertEqual(before, after)

    @unittest.skipUnless(HAVE_TREES and HAVE_VOCAB_DB, "committed trees/vocab db not present")
    def test_no_new_files_appear_in_data_directories(self) -> None:
        config = load_config(CONFIG_PATH)
        watched_dirs = [
            WORKSPACE.knowledge_trees[s.subject_id].parent
            for s in config.subjects
            if s.subject_id in WORKSPACE.knowledge_trees
        ] + [VOCAB_DB.parent]
        before = {d: sorted(os.listdir(d)) for d in watched_dirs}

        build_snapshot(config, (), today=TODAY, workspace=WORKSPACE)

        after = {d: sorted(os.listdir(d)) for d in watched_dirs}
        self.assertEqual(before, after)


@unittest.skipUnless(HAVE_TREES, "committed knowledge trees not present")
class TreeStatusHonestyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def test_every_tree_number_carries_tree_status(self) -> None:
        snapshot = build_snapshot(self.config, (), today=TODAY, workspace=WORKSPACE)
        for subject in snapshot.subjects:
            if subject.subject_id == "politics":
                continue  # no committed tree for this subject
            self.assertIsNotNone(subject.tree_total, subject.subject_id)
            self.assertGreater(subject.tree_total.count, 0)
            self.assertTrue(subject.tree_total.tree_status)

    def test_tree_status_is_not_silently_reported_as_approved(self) -> None:
        # All three committed trees are currently entirely status=extracted; the snapshot must
        # say so honestly rather than defaulting to a label that implies review happened.
        snapshot = build_snapshot(self.config, (), today=TODAY, workspace=WORKSPACE)
        for subject in snapshot.subjects:
            if subject.tree_total is None:
                continue
            self.assertIn("extracted", subject.tree_total.tree_status)

    def test_subject_without_a_committed_tree_reports_none_not_zero(self) -> None:
        snapshot = build_snapshot(self.config, (), today=TODAY, workspace=WORKSPACE)
        politics = snapshot.subject("politics")
        self.assertIsNone(politics.tree_total)


class ReviewQueueDerivedNumbersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def test_due_today_and_backlog_are_split_correctly(self) -> None:
        items = (
            make_item("rv_due_today", subject_id="math1", due_date="2026-09-15"),
            make_item("rv_overdue", subject_id="math1", due_date="2026-09-01"),
            make_item("rv_future", subject_id="math1", due_date="2026-09-20", state="scheduled"),
            make_item("rv_suspended", subject_id="math1", due_date="2026-09-01", state="suspended"),
        )
        snapshot = build_snapshot(self.config, items, today=TODAY, workspace=WORKSPACE)
        math1 = snapshot.subject("math1")
        self.assertEqual(math1.due_today_count, 1)
        self.assertEqual(math1.due_today_minutes, 10)
        self.assertEqual(math1.backlog_minutes, 10)  # only rv_overdue: queued and due_date<today
        # scheduled + suspended still count toward the review-queue footprint per spec (queued or
        # scheduled), but suspended does not.
        self.assertEqual(math1.in_review_queue, 3)  # due_today + overdue + future(scheduled)

    def test_items_are_partitioned_by_subject(self) -> None:
        items = (
            make_item("rv_math", subject_id="math1"),
            make_item("rv_eng", subject_id="eng1", knowledge_point_id="eng1.demo.rv_eng"),
        )
        snapshot = build_snapshot(self.config, items, today=TODAY, workspace=WORKSPACE)
        self.assertEqual(snapshot.subject("math1").due_today_count, 1)
        self.assertEqual(snapshot.subject("eng1").due_today_count, 1)
        self.assertEqual(snapshot.subject("cs408").due_today_count, 0)

    def test_days_to_exam_is_none_without_a_target_date(self) -> None:
        snapshot = build_snapshot(self.config, (), today=TODAY, workspace=WORKSPACE)
        self.assertIsNone(snapshot.days_to_exam)

    def test_days_to_exam_is_computed_when_given(self) -> None:
        snapshot = build_snapshot(
            self.config, (), today=TODAY, target_exam_date=date(2026, 9, 25), workspace=WORKSPACE
        )
        self.assertEqual(snapshot.days_to_exam, 10)


@unittest.skipUnless(HAVE_VOCAB_DB, "vocabulary database not built")
class VocabSnapshotTest(unittest.TestCase):
    def test_delivered_plus_remaining_is_reported(self) -> None:
        config = load_config(CONFIG_PATH)
        snapshot = build_snapshot(config, (), today=TODAY, workspace=WORKSPACE)
        self.assertIsNotNone(snapshot.vocab)
        self.assertGreaterEqual(snapshot.vocab.delivered, 0)
        self.assertGreaterEqual(snapshot.vocab.remaining, 0)

    def test_vocab_snapshot_does_not_write_the_delivery_log(self) -> None:
        import sqlite3

        config = load_config(CONFIG_PATH)
        con = sqlite3.connect(f"file:{VOCAB_DB}?mode=ro", uri=True)
        before = con.execute("SELECT COUNT(*) FROM delivery_log").fetchone()[0]
        con.close()

        build_snapshot(config, (), today=TODAY, workspace=WORKSPACE)

        con = sqlite3.connect(f"file:{VOCAB_DB}?mode=ro", uri=True)
        after = con.execute("SELECT COUNT(*) FROM delivery_log").fetchone()[0]
        con.close()
        self.assertEqual(before, after)


class DoesNotPrescribeTest(unittest.TestCase):
    """Mirrors monthly_close's test_close_does_not_prescribe_next_month, replicated per round-37
    §1: no public name in this read-only module may look like a recommendation/suggestion/
    default/optimum, or a next-month prescription."""

    def test_no_prescriptive_public_names(self) -> None:
        import ky.schedule.state_snapshot as module

        banned_prefixes = ("recommend", "suggest", "default", "optimal", "next_month_")
        names = list(dir(module))
        for cls in (module.StateSnapshot, module.SubjectSnapshot, module.VocabSnapshot, module.TreeCount):
            names.extend(cls.__dataclass_fields__)
        for name in names:
            if name.startswith("_"):
                continue
            lowered = name.lower()
            for prefix in banned_prefixes:
                self.assertFalse(
                    lowered.startswith(prefix), f"{name} looks prescriptive (matches {prefix!r})"
                )


if __name__ == "__main__":
    unittest.main()
