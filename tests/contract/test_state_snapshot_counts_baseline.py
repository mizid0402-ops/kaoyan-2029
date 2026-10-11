from __future__ import annotations

import json
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from ky.models import load_config, load_review_items
from ky.schedule.state_snapshot import build_snapshot, snapshot_to_mapping
from tests._baseline_harness import (
    ProcessResult,
    compare_runs,
    fixed_source,
    load_isolated,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "b867ae7"
CONFIG = ROOT / "tests/fixtures/config/config-minimal.yaml"
REVIEWS = ROOT / "tests/fixtures/reviews/reviews-normal.yaml"


class StateSnapshotCountsBaselineTests(unittest.TestCase):
    def test_snapshot_json_matches_pinned_m12_with_date_boundaries(self) -> None:
        source = fixed_source(
            ROOT,
            BASELINE,
            "ky/schedule/state_snapshot.py",
            lambda raw: (
                b"subject_items =" in raw
                and b"count_review_items_by_subject" not in raw
            ),
        )
        self.assertIn("subject_items =", source.decode("utf-8"))
        self.assertNotIn("count_review_items_by_subject", source.decode("utf-8"))

        config = load_config(CONFIG)
        subjects = config.active_subjects()
        subject_id = subjects[0].subject_id
        base_items = load_review_items(REVIEWS)
        today = date.today()
        cases = (
            ("queued", today - timedelta(days=1)),
            ("queued", today),
            ("queued", today + timedelta(days=1)),
            ("scheduled", today),
        )
        items = tuple(
            replace(
                base_items[index % len(base_items)],
                review_id=f"baseline-{index}",
                subject_id=subject_id,
                due_date=due,
                state=state,
            )
            for index, (state, due) in enumerate(cases)
        )

        module = load_isolated(source, "state_snapshot")

        def old_run():
            old = module.build_snapshot(config, items, today=today, tree_paths={})
            payload = json.dumps(
                module.snapshot_to_mapping(old), ensure_ascii=False, indent=2,
            ).encode("utf-8")
            return ProcessResult(0, payload, b""), {}

        def new_run():
            new = build_snapshot(config, items, today=today, tree_paths={})
            payload = json.dumps(
                snapshot_to_mapping(new), ensure_ascii=False, indent=2,
            ).encode("utf-8")
            return ProcessResult(0, payload, b""), {}

        new_result, _ = compare_runs(old_run, new_run)
        new = build_snapshot(config, items, today=today, tree_paths={})
        new_json = new_result.stdout
        old_json = json.dumps(
            module.snapshot_to_mapping(
                module.build_snapshot(config, items, today=today, tree_paths={})
            ),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        self.assertEqual(old_json, new_json)
        self.assertEqual(
            [row["subject_id"] for row in snapshot_to_mapping(new)["subjects"]],
            [subject.subject_id for subject in config.subjects],
        )
        empty_subject = next(subject.subject_id for subject in subjects[1:])
        self.assertEqual(new.subject(empty_subject).in_review_queue, 0)
        self.assertEqual(new.subject(subject_id).in_review_queue, len(cases))


if __name__ == "__main__":
    unittest.main()
