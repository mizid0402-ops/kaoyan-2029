"""M9 daily review clipping port; see ``contracts/review_clip.md``.

Pins the documented rules of ``ky.schedule.review_clip`` against the current code. Configs and
review items are derived from ``tests/fixtures/``; no repository data counts are hard-coded.
Rules already asserted by ``tests/test_review_scheduler.py`` are not repeated here.
"""

from __future__ import annotations

import copy
import json
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ky.models import (
    ContractError,
    KaoyanConfig,
    ReviewItem,
    load_config,
    load_review_items,
    load_yaml_text,
    validate_config,
)
from ky.schedule.budget import allocate_new_content
from ky.schedule.review_clip import (
    ReviewPolicy,
    preflight_to_mapping,
    select_daily_reviews,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_SOURCE = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
REVIEWS_SOURCE = ROOT / "tests" / "fixtures" / "reviews" / "reviews-normal.yaml"
DAY = date(2026, 9, 15)

SUMMARY_KEYS = {
    "date", "selected", "deferred", "unschedulable", "scheduled_ahead", "unreachable",
    "review_minutes", "new_learning_minutes", "soft_target_minutes", "hard_cap_minutes",
    "backlog_minutes", "over_capacity",
}
QUOTA_KEYS = {"subject_review_quotas", "subject_review_minutes"}
ITEM_KEYS = {"review_id", "subject_id", "estimated_minutes", "overdue_days", "defer_count", "state"}


def _config(total: int, reserve: float, hard: float, *, subjects: int = 1) -> KaoyanConfig:
    """The first ``subjects`` active fixture subjects, equal weights, no floors."""
    document = copy.deepcopy(load_yaml_text(CONFIG_SOURCE.read_text(encoding="utf-8")))
    active = [subject for subject in document["subjects"] if subject["active"]][:subjects]
    for subject in active:
        subject.update(weight=1.0 / len(active), min_daily_minutes=0)
    document.update(
        default_daily_minutes=total, review_reserve_ratio=reserve, hard_max_ratio=hard,
        subjects=active,
    )
    return validate_config(document)


class ReviewClipPortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = load_review_items(REVIEWS_SOURCE)[0]
        self.fixture_config = load_config(CONFIG_SOURCE)

    def item(self, review_id: str, **fields: Any) -> ReviewItem:
        """A fixture item with an explicit ID; ``overdue`` sets the due date relative to DAY."""
        overdue = fields.pop("overdue", 0)
        fields.setdefault("subject_id", self.fixture_config.active_subjects()[0].subject_id)
        fields.setdefault("estimated_minutes", 5)
        fields.setdefault("defer_count", 0)
        fields.setdefault("state", "queued")
        due = DAY - timedelta(days=overdue)
        return replace(
            self.template, review_id=review_id, due_date=due,
            introduced_on=min(self.template.introduced_on, due), **fields,
        )

    # -- entry checks ---------------------------------------------------------

    def test_entry_checks_run_in_documented_order(self) -> None:
        config = self.fixture_config
        ghost = self.item("ghost", subject_id="-".join(s.subject_id for s in config.subjects))
        with self.assertRaises(ContractError):
            select_daily_reviews(config, [ghost], DAY, daily_minutes_override=-1)
        active_id = config.active_subjects()[0].subject_id
        with self.assertRaises(ValueError) as caught:
            select_daily_reviews(
                config, [], DAY, daily_minutes_override=-1,
                subject_review_quotas={active_id: -1},
            )
        self.assertIs(type(caught.exception), ValueError)

    def test_quota_keys_must_be_active_and_values_plain_integers(self) -> None:
        config = self.fixture_config
        active_id = config.active_subjects()[0].subject_id
        inactive = [subject.subject_id for subject in config.subjects if not subject.active]
        cases = [({active_id: True}, active_id), ({active_id: -1}, active_id)]
        cases += [({subject_id: 0}, subject_id) for subject_id in inactive]
        for quotas, subject_id in cases:
            with self.subTest(quotas=quotas):
                with self.assertRaises(ContractError) as caught:
                    select_daily_reviews(config, [], DAY, subject_review_quotas=quotas)
                self.assertEqual(caught.exception.path, f"subject_review_quotas.{subject_id}")

    # -- selection without quotas ---------------------------------------------

    def test_a_miss_does_not_stop_smaller_lower_ranked_items(self) -> None:
        config = _config(20, 1.0, 1.0)
        first = self.item("zz-first", overdue=2, estimated_minutes=15)
        miss = self.item("zz-miss", overdue=1, estimated_minutes=10)
        small = self.item("aa-small", overdue=0, estimated_minutes=5)
        result = select_daily_reviews(config, [small, miss, first], DAY)
        self.assertEqual(result.selected_ids, ("zz-first", "aa-small"))
        self.assertEqual(result.deferred_ids, ("zz-miss",))

    def test_urgent_items_do_not_jump_ahead_without_quotas(self) -> None:
        config = _config(10, 1.0, 1.0)
        policy = ReviewPolicy()
        regular = self.item("zz-regular", overdue=policy.urgent_overdue_days - 1,
                            estimated_minutes=10)
        urgent = self.item("aa-urgent", defer_count=policy.urgent_defer_count,
                           estimated_minutes=10)
        result = select_daily_reviews(config, [urgent, regular], DAY, policy=policy)
        self.assertEqual(result.selected_ids, ("zz-regular",))
        self.assertEqual(result.deferred_ids, ("aa-urgent",))

    def test_overdue_threshold_is_inclusive(self) -> None:
        config = _config(20, 0.5, 1.0)
        threshold = ReviewPolicy().urgent_overdue_days
        filler = self.item("filler", overdue=threshold + 1, estimated_minutes=10)
        target = self.item("target", overdue=threshold, estimated_minutes=10)
        at_threshold = select_daily_reviews(config, [target, filler], DAY)
        self.assertEqual(at_threshold.selected_ids, ("filler", "target"))
        above = ReviewPolicy(urgent_overdue_days=threshold + 1)
        below = select_daily_reviews(config, [target, filler], DAY, policy=above)
        self.assertEqual(below.deferred_ids, ("target",))

    def test_type_and_self_rating_levels_including_their_defaults(self) -> None:
        # A zero-minute day defers every due item, and deferred keeps priority order.
        config = self.fixture_config
        by_type = [
            self.item("e-concept", granularity="concept"),
            self.item("d-procedure", granularity="procedure"),
            self.item("c-pattern", granularity="question_pattern"),
            self.item("b-error", granularity="error_pattern"),
            self.item("a-vocab", granularity="vocabulary_batch"),
        ]
        result = select_daily_reviews(config, by_type, DAY, daily_minutes_override=0)
        self.assertEqual(
            result.deferred_ids,
            ("d-procedure", "e-concept", "c-pattern", "b-error", "a-vocab"),
        )
        by_rating = [
            self.item("e-unknown", last_self_rating="unknown"),
            self.item("d-vague", last_self_rating="vague"),
            self.item("c-basic", last_self_rating="basic"),
            self.item("b-fluent", last_self_rating="fluent"),
            self.item("a-none", last_self_rating=None),
        ]
        result = select_daily_reviews(config, by_rating, DAY, daily_minutes_override=0)
        self.assertEqual(
            result.deferred_ids, ("e-unknown", "d-vague", "c-basic", "b-fluent", "a-none"),
        )

    def test_ranking_reads_the_configured_total_not_the_override(self) -> None:
        # Deficit decides; with a zero override a ranking read from the override would see no
        # deficit at all and fall back to review_id.
        config = _config(20, 1.0, 1.0, subjects=2)
        neglected, busy = (subject.subject_id for subject in config.active_subjects())
        usage = {neglected: 0, busy: config.default_daily_minutes}
        items = [
            self.item("a-busy", subject_id=busy),
            self.item("z-neglected", subject_id=neglected),
        ]
        result = select_daily_reviews(
            config, items, DAY, seven_day_usage=usage, daily_minutes_override=0,
        )
        self.assertEqual(result.deferred_ids, ("z-neglected", "a-busy"))

    def test_new_learning_minutes_is_the_resolved_total_minus_review(self) -> None:
        config = self.fixture_config
        override = config.default_daily_minutes + 17
        items = [self.item(f"item-{n}", overdue=n) for n in range(4)]
        result = select_daily_reviews(config, items, DAY, daily_minutes_override=override)
        self.assertEqual(result.review_minutes, sum(i.estimated_minutes for i in result.selected))
        self.assertEqual(result.new_learning_minutes, override - result.review_minutes)

    # -- selection with quotas ------------------------------------------------

    def test_quota_mode_reports_every_quota_key_and_omitted_subjects_get_zero(self) -> None:
        config = self.fixture_config
        quota_id, omitted_id = (s.subject_id for s in config.active_subjects()[:2])
        policy = ReviewPolicy()
        regular = self.item("regular", subject_id=omitted_id)
        urgent = self.item("urgent", subject_id=omitted_id, defer_count=policy.urgent_defer_count)
        result = select_daily_reviews(
            config, [regular, urgent], DAY, subject_review_quotas={quota_id: 10},
        )
        self.assertEqual(result.soft_target_minutes, 10)
        self.assertEqual(result.selected_ids, ("urgent",))
        self.assertEqual(result.deferred_ids, ("regular",))
        self.assertEqual(
            result.subject_review_minutes,
            {quota_id: 0, omitted_id: urgent.estimated_minutes},
        )

    # -- buckets and deferral -------------------------------------------------

    def test_scheduled_item_due_today_is_unreachable(self) -> None:
        item = self.item("scheduled-today", state="scheduled")
        result = select_daily_reviews(self.fixture_config, [item], DAY)
        self.assertEqual(result.unreachable_ids, ("scheduled-today",))
        self.assertEqual(result.scheduled_ahead, ())
        self.assertTrue(result.over_capacity)

    def test_scheduled_buckets_keep_input_order(self) -> None:
        items = [
            self.item("b-ahead", state="scheduled", overdue=-3),
            self.item("z-late", state="scheduled", overdue=1),
            self.item("a-ahead", state="scheduled", overdue=-9),
            self.item("c-late", state="scheduled", overdue=4),
        ]
        result = select_daily_reviews(self.fixture_config, items, DAY)
        self.assertEqual(result.scheduled_ahead_ids, ("b-ahead", "a-ahead"))
        self.assertEqual(result.unreachable_ids, ("z-late", "c-late"))

    def test_deferral_changes_nothing_but_defer_count(self) -> None:
        original = self.item("deferred", overdue=2, defer_count=1, last_self_rating="vague")
        result = select_daily_reviews(
            self.fixture_config, [original], DAY, daily_minutes_override=0,
        )
        self.assertEqual(result.deferred, (replace(original, defer_count=2),))
        self.assertEqual(result.backlog_minutes, original.estimated_minutes)

    # -- JSON shape -----------------------------------------------------------

    def test_summary_and_preflight_mapping_have_exactly_the_documented_keys(self) -> None:
        config = self.fixture_config
        cap = config.review_hard_cap_minutes()
        items = [
            self.item("selected"),
            # Fits the hard cap but not the soft quota, and is not urgent: deferred.
            self.item("deferred", overdue=1, estimated_minutes=cap),
            self.item("oversized", estimated_minutes=cap + 1),
            self.item("ahead", state="scheduled", overdue=-2),
            self.item("late", state="scheduled", overdue=2),
        ]
        result = select_daily_reviews(config, items, DAY)
        summary = result.summary()
        self.assertEqual(set(summary), SUMMARY_KEYS)
        self.assertEqual(summary["date"], DAY.isoformat())
        for bucket in ("selected", "deferred", "scheduled_ahead", "unreachable"):
            with self.subTest(bucket=bucket):
                self.assertEqual(len(summary[bucket]), 1)
                self.assertEqual(set(summary[bucket][0]), ITEM_KEYS)
        self.assertEqual(summary["unschedulable"], ["oversized"])
        self.assertEqual(summary["deferred"][0]["defer_count"], items[1].defer_count + 1)
        self.assertEqual(summary["unreachable"][0]["overdue_days"], 2)
        self.assertEqual(summary["scheduled_ahead"][0]["overdue_days"], -2)

        allocations = allocate_new_content(config, result.new_learning_minutes)
        payload = preflight_to_mapping(config, result, allocations)
        json.dumps(payload)
        self.assertEqual(set(payload), SUMMARY_KEYS | {"subject_allocation", "config"})
        self.assertEqual(
            payload["subject_allocation"],
            [
                {"subject_id": a.subject_id, "display_name": a.display_name,
                 "weight": a.weight, "new_content_minutes": a.minutes}
                for a in allocations
            ],
        )
        self.assertEqual(payload["config"], {
            "project_id": config.project_id,
            "default_daily_minutes": config.default_daily_minutes,
            "review_reserve_ratio": config.review_reserve_ratio,
            "hard_max_ratio": config.hard_max_ratio,
        })

        quotas = {subject.subject_id: 0 for subject in config.active_subjects()}
        with_quotas = select_daily_reviews(config, items, DAY, subject_review_quotas=quotas)
        self.assertEqual(set(with_quotas.summary()), SUMMARY_KEYS | QUOTA_KEYS)


if __name__ == "__main__":
    unittest.main()
