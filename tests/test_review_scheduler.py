"""Review capacity clipping tests — the core guarantee of phase 1.

The selector must never exceed the hard cap, must be replayable, and must make
overflow visible instead of hiding it. Run with:

    py -m unittest -v tests.test_review_scheduler
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(REPO_ROOT))

from ky.models import (  # noqa: E402
    ContractError,
    KaoyanConfig,
    SubjectBudget,
    load_config,
    load_review_items,
    validate_review_item,
)
from ky.schedule.review_clip import (  # noqa: E402
    ReviewPolicy,
    select_daily_reviews,
)

FIXTURES = REPO_ROOT / "tests" / "fixtures"
CONFIG_PATH = FIXTURES / "config" / "config-minimal.yaml"
REVIEW_DIR = FIXTURES / "reviews"
TODAY = date(2026, 9, 12)


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
        "due_date": "2026-09-12",
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


def _single_subject_config(total_minutes: int, soft_ratio: float, hard_ratio: float) -> KaoyanConfig:
    """A one-subject config with an explicit soft/hard split.

    Unlike ``_tiny_single_subject_config`` (soft == hard == the whole day),
    this leaves room between the soft quota and the hard cap so tests can
    show an item being admitted *because* it is urgent, not merely because
    there happened to be room for it.
    """
    subject = SubjectBudget(
        subject_id="math1", display_name="数学一", weight=1.0, active=True, min_daily_minutes=0
    )
    return KaoyanConfig(
        schema_version=1,
        project_id="tiny",
        default_daily_minutes=total_minutes,
        review_reserve_ratio=soft_ratio,
        hard_max_ratio=hard_ratio,
        subjects=(subject,),
    )


def _two_subject_config(total_minutes: int, soft_ratio: float, hard_ratio: float) -> KaoyanConfig:
    subjects = (
        SubjectBudget(
            subject_id="math1", display_name="数学一", weight=0.5, active=True, min_daily_minutes=0
        ),
        SubjectBudget(
            subject_id="eng1", display_name="英语一", weight=0.5, active=True, min_daily_minutes=0
        ),
    )
    return KaoyanConfig(
        schema_version=1,
        project_id="tiny-two",
        default_daily_minutes=total_minutes,
        review_reserve_ratio=soft_ratio,
        hard_max_ratio=hard_ratio,
        subjects=subjects,
    )


def _tiny_single_subject_config(total_minutes: int) -> KaoyanConfig:
    """A one-subject config where soft quota == hard cap == the whole day.

    Used to isolate one level of the tie-break tuple at a time: with two
    equal-cost items that exhaust the day, whichever ranks first is selected
    and the other is deferred, so the outcome names the winning tie-break
    level directly instead of only bounding totals.
    """
    subject = SubjectBudget(
        subject_id="math1", display_name="数学一", weight=1.0, active=True, min_daily_minutes=0
    )
    return KaoyanConfig(
        schema_version=1,
        project_id="tiny",
        default_daily_minutes=total_minutes,
        review_reserve_ratio=1.0,
        hard_max_ratio=1.0,
        subjects=(subject,),
    )


class ReviewClippingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    # -- basic capacity guarantees ---------------------------------------

    def test_small_queue_fits_entirely_and_uses_only_the_soft_quota(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-normal.yaml")
        result = select_daily_reviews(self.config, items, TODAY)
        # 8 + 10 = 18 min due; the third item is not due until 2026-09-14.
        self.assertEqual(len(result.selected), 2)
        self.assertEqual(result.review_minutes, 18)
        self.assertEqual(result.new_learning_minutes, 102)
        self.assertEqual(result.deferred, ())
        self.assertFalse(result.over_capacity)
        self.assertLessEqual(result.review_minutes, result.soft_target_minutes)
        self.assertNotIn("rv_eng1_vocab_0003", result.selected_ids)

    def test_review_minutes_never_exceed_the_hard_cap(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        result = select_daily_reviews(self.config, items, TODAY)
        self.assertLessEqual(result.review_minutes, result.hard_cap_minutes)
        self.assertLessEqual(result.hard_cap_minutes, self.config.default_daily_minutes)
        self.assertEqual(result.review_minutes + result.new_learning_minutes, 120)

    def test_selected_cost_equals_reported_review_minutes(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        result = select_daily_reviews(self.config, items, TODAY)
        self.assertEqual(
            sum(item.estimated_minutes for item in result.selected),
            result.review_minutes,
        )

    def test_overloaded_queue_reports_backlog_instead_of_hiding_it(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        result = select_daily_reviews(self.config, items, TODAY)
        self.assertTrue(result.over_capacity)
        self.assertGreater(result.backlog_minutes, 0)
        self.assertGreater(len(result.deferred), 0)
        self.assertEqual(
            result.backlog_minutes,
            sum(item.estimated_minutes for item in result.deferred),
        )

    # -- priority rules --------------------------------------------------

    def test_longest_overdue_item_is_selected_first(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        result = select_daily_reviews(self.config, items, TODAY)
        # rv_math1_hard_0002 is 10 days overdue; nothing else is close.
        self.assertEqual(result.selected[0].review_id, "rv_math1_hard_0002")

    def test_borrowing_to_the_hard_cap_only_happens_for_urgent_items(self) -> None:
        # total=20, soft=10, hard=20. "filler" (overdue 2d, not urgent) is
        # ranked ahead of "urgent" (overdue 0d, defer_count 2 -> urgent) by
        # the overdue-days tie-break level, so filler fills the soft quota
        # first. "urgent" then only fits because it is urgent; "spillover"
        # (also not urgent) cannot fit even though the hard cap alone would
        # have room, because non-urgent items may never cross the soft quota.
        # Deleting the urgency check (treating every item as non-urgent)
        # would move "urgent" from selected to deferred, so this test fails
        # under that regression.
        config = _single_subject_config(20, soft_ratio=0.5, hard_ratio=1.0)
        filler = make_item("rv_filler", due_date="2026-09-10", defer_count=0, estimated_minutes=10)
        urgent = make_item("rv_urgent", due_date="2026-09-12", defer_count=2, estimated_minutes=10)
        spillover = make_item(
            "rv_spillover", due_date="2026-09-12", defer_count=0, estimated_minutes=10
        )
        result = select_daily_reviews(config, [urgent, filler, spillover], TODAY)
        self.assertEqual(result.selected_ids, ("rv_filler", "rv_urgent"))
        self.assertEqual(result.deferred_ids, ("rv_spillover",))
        self.assertEqual(result.review_minutes, 20)

    def test_defer_count_two_makes_an_item_urgent(self) -> None:
        # total=20, soft=10, hard=20. "filler" (overdue 1d) always outranks
        # and exhausts the soft quota by itself; "target" (overdue 0d,
        # defer_count 2) can then only be admitted because defer_count >= 2
        # makes it urgent. Without that rule it would be deferred: it needs
        # 20 total minutes, which is over the 10-minute soft quota.
        config = _single_subject_config(20, soft_ratio=0.5, hard_ratio=1.0)
        filler = make_item("rv_filler", due_date="2026-09-11", defer_count=0, estimated_minutes=10)
        target = make_item(
            "rv_math1_urgent_0013", due_date="2026-09-12", defer_count=2, estimated_minutes=10
        )
        result = select_daily_reviews(config, [target, filler], TODAY)
        self.assertEqual(result.selected_ids, ("rv_filler", "rv_math1_urgent_0013"))
        self.assertEqual(result.deferred_ids, ())

    def test_subject_deficit_breaks_ties_towards_the_neglected_subject(self) -> None:
        # total=20, soft=hard=10: capacity for exactly one 10-minute item.
        # Both items are otherwise identical (same overdue/defer/lapses/type)
        # so the outcome is decided purely by the subject-deficit tie-break.
        # The neglected item's review_id ("rv_zzz_eng") sorts *after* the
        # heavily-used item's ("rv_aaa_math") alphabetically, so a pass here
        # cannot be explained by the final review_id tie-break -- only by
        # deficit ranking actually outranking it.
        config = _two_subject_config(20, soft_ratio=0.5, hard_ratio=0.5)
        math_item = make_item("rv_aaa_math", subject_id="math1")
        eng_item = make_item("rv_zzz_eng", subject_id="eng1")
        result = select_daily_reviews(
            config,
            [math_item, eng_item],
            TODAY,
            seven_day_usage={"math1": 400, "eng1": 0},
        )
        self.assertEqual(result.selected_ids, ("rv_zzz_eng",))
        self.assertEqual(result.deferred_ids, ("rv_aaa_math",))

    # -- deferral semantics ----------------------------------------------

    def test_deferred_items_keep_due_date_and_advance_defer_count(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        result = select_daily_reviews(self.config, items, TODAY)
        original = {item.review_id: item for item in items}
        for deferred in result.deferred:
            before = original[deferred.review_id]
            self.assertEqual(deferred.due_date, before.due_date)
            self.assertEqual(deferred.defer_count, before.defer_count + 1)
            self.assertEqual(deferred.revision, before.revision)

    def test_deferral_does_not_mutate_the_input_items(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        snapshot = [(item.review_id, item.defer_count, item.due_date) for item in items]
        select_daily_reviews(self.config, items, TODAY)
        self.assertEqual(
            snapshot, [(item.review_id, item.defer_count, item.due_date) for item in items]
        )

    def test_a_deferred_item_gains_priority_on_a_later_day(self) -> None:
        # Day 1: a 50-minute day, single subject. Five 10-minute fillers plus
        # "rv_zzz_crowd" (also 10 min, lexically largest review_id) add up to
        # 60 minutes, so the fillers (ranked first by review_id, everything
        # else tied) fill the day and "rv_zzz_crowd" is deferred.
        day_one_config = _single_subject_config(50, soft_ratio=1.0, hard_ratio=1.0)
        fillers = [make_item(f"rv_crowd_{i:02d}") for i in range(5)]
        crowd = make_item("rv_zzz_crowd")
        day_one = select_daily_reviews(day_one_config, [*fillers, crowd], TODAY)
        self.assertEqual(day_one.deferred_ids, ("rv_zzz_crowd",))

        # Day 2: only 10 minutes of capacity, competing against a brand-new
        # item "rv_aaa_fresh" whose review_id sorts *before* the carried-over
        # item alphabetically. If review_id decided the outcome (the fallback
        # this test guards against), the fresh item would win. It doesn't:
        # the carried-over item is now 1 day overdue and one defer_count
        # higher -- both raised purely by having been deferred, with
        # due_date never rewritten -- and that outranks the fresh item on
        # both of the two higher-priority tie-break levels.
        later = date(2026, 9, 13)
        day_two_config = _single_subject_config(10, soft_ratio=1.0, hard_ratio=1.0)
        fresh = make_item("rv_aaa_fresh", due_date="2026-09-13")
        day_two = select_daily_reviews(
            day_two_config, [fresh, *day_one.deferred], later
        )
        self.assertEqual(day_two.selected_ids, ("rv_zzz_crowd",))
        self.assertEqual(day_two.deferred_ids, ("rv_aaa_fresh",))

    # -- filters ---------------------------------------------------------

    def test_retired_and_not_yet_due_items_are_ignored(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        result = select_daily_reviews(self.config, items, TODAY)
        every_id = set(result.selected_ids) | set(result.deferred_ids) | {
            item.review_id for item in result.unschedulable
        }
        self.assertNotIn("rv_cs408_retired_0015", every_id)
        self.assertNotIn("rv_math1_future_0014", every_id)

    def test_no_due_items_yields_a_fully_free_day(self) -> None:
        result = select_daily_reviews(self.config, [], TODAY)
        self.assertEqual(result.selected, ())
        self.assertEqual(result.review_minutes, 0)
        self.assertEqual(result.new_learning_minutes, 120)
        self.assertFalse(result.over_capacity)

    def test_suspended_items_are_not_due(self) -> None:
        item = make_item("rv_suspended", state="suspended")
        result = select_daily_reviews(self.config, [item], TODAY)
        self.assertEqual(result.selected, ())
        self.assertEqual(result.deferred, ())

    def test_a_future_scheduled_item_is_reported_not_dropped(self) -> None:
        """``scheduled`` items are classified instead of disappearing.

        ``state: scheduled`` is a declared-valid value in
        ``ky.models.VALID_REVIEW_STATES`` while ``ReviewItem.is_due`` admits
        only ``queued``. The selector therefore has to say *something* about
        these items or they vanish from the plan with no diagnostic -- the one
        outcome this module exists to prevent.

        Semantics settled here: a ``scheduled`` item whose due date is still in
        the future is planned work, so it is reported in ``scheduled_ahead`` and
        consumes no budget. It must not raise ``over_capacity``, because nothing
        is owed yet.
        """
        item = make_item("rv_scheduled_ahead", state="scheduled", due_date="2026-10-01")
        result = select_daily_reviews(self.config, [item], TODAY)
        self.assertEqual(result.selected, ())
        self.assertEqual(result.deferred, ())
        self.assertEqual(result.unschedulable, ())
        self.assertEqual(result.unreachable, ())
        self.assertEqual(result.scheduled_ahead_ids, ("rv_scheduled_ahead",))
        self.assertFalse(result.over_capacity)
        self.assertIn("rv_scheduled_ahead", str(result.summary()))
        # Reporting it must not silently consume any of the day's budget.
        self.assertEqual(result.review_minutes, 0)
        self.assertEqual(result.new_learning_minutes, self.config.default_daily_minutes)

    def test_a_past_due_scheduled_item_is_unreachable_and_flags_capacity(self) -> None:
        """The genuinely broken case: overdue but unselectable by construction.

        A past-due ``scheduled`` item can never be selected, so it is neither
        work nor backlog. Deferring it would be a lie (it was never eligible)
        and dropping it hides a real stall. It is reported in ``unreachable``
        and raises ``over_capacity``, so the operator sees an item that needs a
        state fix rather than an item that quietly stopped existing.
        """
        item = make_item("rv_scheduled_overdue", state="scheduled", due_date="2026-09-01")
        result = select_daily_reviews(self.config, [item], TODAY)
        self.assertEqual(result.selected, ())
        self.assertEqual(result.deferred, ())
        self.assertEqual(result.unschedulable, ())
        self.assertEqual(result.scheduled_ahead, ())
        self.assertEqual(result.unreachable_ids, ("rv_scheduled_overdue",))
        self.assertTrue(result.over_capacity)
        self.assertIn("rv_scheduled_overdue", str(result.summary()))

    def test_no_input_item_is_ever_silently_dropped(self) -> None:
        """The accounting invariant, asserted rather than trusted.

        Every item that is not deliberately parked must appear in exactly one
        bucket. This is the check that would have caught the ``scheduled`` gap
        at the moment it was introduced.
        """
        items = [
            make_item("rv_q_due", state="queued", due_date="2026-09-12"),
            make_item("rv_q_future", state="queued", due_date="2026-12-01"),
            make_item("rv_s_future", state="scheduled", due_date="2026-12-01"),
            make_item("rv_s_past", state="scheduled", due_date="2026-09-01"),
            make_item("rv_susp", state="suspended", due_date="2026-09-12"),
            make_item("rv_ret", state="retired", due_date="2026-09-12"),
        ]
        result = select_daily_reviews(self.config, items, TODAY)
        visible = result.visible_ids
        # No duplicates: each id appears in exactly one bucket.
        self.assertEqual(len(visible), len(set(visible)))
        # Deliberately parked states stay out, as documented.
        self.assertNotIn("rv_susp", visible)
        self.assertNotIn("rv_ret", visible)
        # Not-yet-due queued work is future work, so it is legitimately absent.
        self.assertNotIn("rv_q_future", visible)
        # Everything else must be accounted for.
        for expected in ("rv_q_due", "rv_s_future", "rv_s_past"):
            self.assertIn(expected, visible)

    # -- unbounded inputs --------------------------------------------------

    def test_an_astronomically_large_seven_day_usage_does_not_crash(self) -> None:
        """Regression: the subject-deficit tie-break used to overflow.

        ``_deficit_ratio`` returned ``float((target - actual) / target)``. The
        contract puts no upper bound on ``seven_day_usage`` (the CLI only
        checks each value is a non-negative int), so a large enough ``actual``
        made ``float(Fraction)`` raise ``OverflowError`` from inside ``sorted``
        -- escaping ``select_daily_reviews`` as an uncaught traceback rather
        than a ContractError or a clean result. 10**400 is past the float range
        that 10**308 still fits inside, which is why both are exercised.
        """
        items = [make_item("rv_a"), make_item("rv_b")]
        for usage in (10**308, 10**400, 10**1000):
            with self.subTest(usage_digits=len(str(usage))):
                result = select_daily_reviews(
                    self.config, items, TODAY, seven_day_usage={"math1": usage}
                )
                self.assertEqual(result.selected_ids, ("rv_a", "rv_b"))
                self.assertEqual(result.review_minutes, 20)

    def test_the_deficit_tiebreak_stays_exact_for_near_identical_subjects(self) -> None:
        """Two subjects whose deficits differ far below float resolution.

        ``float`` would collapse both ratios to the same value and hand the
        decision down to the ``review_id`` tie-break; exact ``Fraction``
        arithmetic keeps them distinct, so the more neglected subject wins even
        though its ``review_id`` sorts last.
        """
        # 1e-24 of a 10**25-minute day is a 10-minute cap: room for exactly one
        # of the two 10-minute items, while the deficit target stays huge.
        config = _two_subject_config(10**25, soft_ratio=1e-24, hard_ratio=1e-24)
        self.assertEqual(config.review_hard_cap_minutes(), 10)

        # Both deficits are 1 - k/target with target = 3.5e25, so they differ by
        # ~3e-26 -- far below the ~2.2e-16 resolution of a float near 1.0.
        # float() would round both to exactly 1.0 and hand the decision to the
        # review_id tie-break, which favours "rv_aaa_math".
        target = Fraction("0.5") * 10**25 * 7
        self.assertEqual(float((target - 1) / target), float((target - 2) / target))

        math_item = make_item("rv_aaa_math", subject_id="math1")
        eng_item = make_item("rv_zzz_eng", subject_id="eng1")
        result = select_daily_reviews(
            config,
            [math_item, eng_item],
            TODAY,
            # eng1 has used one minute less, so it is the more neglected one.
            seven_day_usage={"math1": 2, "eng1": 1},
        )
        self.assertEqual(result.selected_ids, ("rv_zzz_eng",))
        self.assertEqual(result.deferred_ids, ("rv_aaa_math",))

    # -- oversized items -------------------------------------------------

    def test_item_larger_than_the_hard_cap_is_flagged_not_starved(self) -> None:
        # 30 minutes is the import cap. On a 120-minute day the hard cap is 72
        # minutes, so it fits; on a deliberately tiny day the hard cap drops
        # below the item cost and the selector must report it as
        # unschedulable instead of deferring it forever.
        item = validate_review_item(
            {
                "review_id": "rv_tiny_over",
                "revision": 1,
                "subject_id": "math1",
                "knowledge_point_id": "math1.demo.over",
                "title": "over",
                "granularity": "error_pattern",
                "state": "queued",
                "estimated_minutes": 30,
                "introduced_on": "2026-09-01",
                "due_date": "2026-09-12",
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
        )

        fits = select_daily_reviews(self.config, [item], TODAY)
        self.assertIn("rv_tiny_over", fits.selected_ids)
        self.assertEqual(fits.unschedulable, ())

        shrunk = KaoyanConfig(
            schema_version=self.config.schema_version,
            project_id=self.config.project_id,
            default_daily_minutes=40,
            review_reserve_ratio=0.30,
            hard_max_ratio=0.50,  # hard cap = 20 min, below the 30-minute item
            subjects=self.config.subjects,
        )
        too_big = select_daily_reviews(shrunk, [item], TODAY)
        self.assertEqual(too_big.selected, ())
        self.assertEqual(len(too_big.unschedulable), 1)
        self.assertEqual(too_big.deferred, ())
        self.assertTrue(too_big.over_capacity)

    # -- exact boundaries --------------------------------------------------

    def test_item_cost_exactly_equal_to_the_hard_cap_is_schedulable(self) -> None:
        # 20 minutes is exactly the hard cap, not one minute over it; it must
        # be selected, not flagged unschedulable (that is only for costs
        # strictly greater than the hard cap).
        config = _single_subject_config(20, soft_ratio=1.0, hard_ratio=1.0)
        item = make_item("rv_exact_hard_cap", estimated_minutes=20)
        result = select_daily_reviews(config, [item], TODAY)
        self.assertEqual(result.selected_ids, ("rv_exact_hard_cap",))
        self.assertEqual(result.unschedulable, ())
        self.assertEqual(result.review_minutes, 20)

    def test_soft_quota_equal_to_hard_cap_never_needs_urgency(self) -> None:
        # When review_reserve_ratio == hard_max_ratio, soft == hard, so the
        # "borrow past soft" branch never triggers -- everything that fits at
        # all fits inside the soft quota. A non-urgent item exactly at the
        # shared boundary must still be selected.
        config = _single_subject_config(30, soft_ratio=1.0, hard_ratio=1.0)
        self.assertEqual(config.review_target_minutes(), config.review_hard_cap_minutes())
        item = make_item("rv_at_shared_boundary", estimated_minutes=30, defer_count=0)
        result = select_daily_reviews(config, [item], TODAY)
        self.assertEqual(result.selected_ids, ("rv_at_shared_boundary",))

    # -- determinism -----------------------------------------------------

    def test_repeated_selection_is_byte_identical(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        first = select_daily_reviews(self.config, items, TODAY).summary()
        for _ in range(99):
            self.assertEqual(
                first,
                select_daily_reviews(self.config, items, TODAY).summary(),
            )

    def test_input_order_does_not_change_the_outcome(self) -> None:
        items = list(load_review_items(REVIEW_DIR / "reviews-overloaded.yaml"))
        baseline = select_daily_reviews(self.config, items, TODAY).summary()
        reversed_result = select_daily_reviews(self.config, list(reversed(items)), TODAY).summary()
        self.assertEqual(baseline, reversed_result)

    # -- policy knobs ----------------------------------------------------

    def test_stricter_policy_defers_more(self) -> None:
        # total=20, soft=10, hard=20. "filler" (overdue 1d, defer 0) always
        # outranks "target" (overdue 0d, defer 2) and fills the soft quota by
        # itself. "target" can only cross the soft quota if its defer_count
        # of 2 counts as urgent -- true under the lenient threshold (>= 1),
        # false under the strict one (>= 30). Using ">="/"<=" on aggregate
        # counts (as the old version of this test did) would pass even if
        # the policy parameter were ignored entirely; asserting the exact
        # review_id split does not.
        config = _single_subject_config(20, soft_ratio=0.5, hard_ratio=1.0)
        filler = make_item("rv_filler", due_date="2026-09-11", defer_count=0, estimated_minutes=10)
        target = make_item("rv_target", due_date="2026-09-12", defer_count=2, estimated_minutes=10)
        lenient = select_daily_reviews(
            config, [target, filler], TODAY,
            policy=ReviewPolicy(urgent_overdue_days=1, urgent_defer_count=1),
        )
        strict = select_daily_reviews(
            config, [target, filler], TODAY,
            policy=ReviewPolicy(urgent_overdue_days=30, urgent_defer_count=30),
        )
        self.assertEqual(lenient.selected_ids, ("rv_filler", "rv_target"))
        self.assertEqual(lenient.deferred_ids, ())
        self.assertEqual(strict.selected_ids, ("rv_filler",))
        self.assertEqual(strict.deferred_ids, ("rv_target",))

    def test_invalid_policy_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ReviewPolicy(urgent_overdue_days=0)
        with self.assertRaises(ValueError):
            ReviewPolicy(urgent_defer_count=0)

    def test_shrinking_the_budget_never_reduces_the_backlog(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        wide = select_daily_reviews(self.config, items, TODAY)
        narrow_config = KaoyanConfig(
            schema_version=self.config.schema_version,
            project_id=self.config.project_id,
            default_daily_minutes=60,
            review_reserve_ratio=self.config.review_reserve_ratio,
            hard_max_ratio=self.config.hard_max_ratio,
            subjects=self.config.subjects,
        )
        narrow = select_daily_reviews(narrow_config, items, TODAY)
        self.assertGreaterEqual(len(narrow.deferred), len(wide.deferred))
        self.assertLessEqual(narrow.review_minutes, wide.review_minutes)

    # -- full-order tie-break coverage -------------------------------------
    #
    # The declared sort key is a tuple of eight levels. The tests above only
    # exercise the first two (overdue age, defer count) and the fourth
    # (subject deficit). Each test below holds every earlier level equal
    # between two items and gives the *later* one an alphabetically smaller
    # review_id, so a pass only proves something if the level under test --
    # not the final review_id tie-break -- actually decided the outcome.

    def test_lapses_break_ties_when_overdue_defer_and_deficit_are_equal(self) -> None:
        config = _tiny_single_subject_config(10)
        high_lapses = make_item(
            "rv_zzz_high_lapses",
            schedule={
                "mode": "fixed_bootstrap", "phase": 1, "interval_days": 3,
                "ease_factor": 2.5, "repetitions": 1, "lapses": 3,
            },
        )
        low_lapses = make_item(
            "rv_aaa_low_lapses",
            schedule={
                "mode": "fixed_bootstrap", "phase": 1, "interval_days": 3,
                "ease_factor": 2.5, "repetitions": 1, "lapses": 0,
            },
        )
        result = select_daily_reviews(config, [low_lapses, high_lapses], TODAY)
        self.assertEqual(result.selected_ids, ("rv_zzz_high_lapses",))
        self.assertEqual(result.deferred_ids, ("rv_aaa_low_lapses",))

    def test_item_type_priority_breaks_ties_when_lapses_are_equal(self) -> None:
        config = _tiny_single_subject_config(10)
        concept_item = make_item("rv_zzz_concept", granularity="concept")
        error_item = make_item("rv_aaa_error", granularity="error_pattern")
        result = select_daily_reviews(config, [error_item, concept_item], TODAY)
        self.assertEqual(result.selected_ids, ("rv_zzz_concept",))
        self.assertEqual(result.deferred_ids, ("rv_aaa_error",))

    def test_self_rating_is_the_final_tiebreak_only(self) -> None:
        config = _tiny_single_subject_config(10)
        unknown_rated = make_item("rv_zzz_unknown", self_rating="unknown")
        fluent_rated = make_item("rv_aaa_fluent", self_rating="fluent")
        result = select_daily_reviews(config, [fluent_rated, unknown_rated], TODAY)
        # An item the learner already rated "fluent" yields to one rated
        # "unknown" once every higher-priority key is tied, but self_rating
        # must not have touched due_date, defer_count, or the schedule.
        self.assertEqual(result.selected_ids, ("rv_zzz_unknown",))
        self.assertEqual(result.deferred_ids, ("rv_aaa_fluent",))
        deferred = result.deferred[0]
        self.assertEqual(deferred.due_date, fluent_rated.due_date)
        self.assertEqual(deferred.schedule, fluent_rated.schedule)
        self.assertEqual(deferred.defer_count, fluent_rated.defer_count + 1)

    # -- referential integrity with the config ----------------------------

    def test_select_daily_reviews_rejects_an_unrecognised_subject_id(self) -> None:
        # select_daily_reviews() must not trust the caller to have already
        # run validate_items_against_config() -- it validates on its own
        # entry, so a ghost subject_id fails closed instead of quietly
        # getting a neutral 0.0 subject-deficit ratio and a free pass into
        # the plan.
        item = make_item("rv_unknown_subject", subject_id="phantom_subject")
        with self.assertRaises(ContractError) as ctx:
            select_daily_reviews(self.config, [item], TODAY)
        self.assertIn("phantom_subject", str(ctx.exception))

    def test_select_daily_reviews_rejects_an_inactive_subject_id(self) -> None:
        item = make_item("rv_inactive_subject", subject_id="politics")
        with self.assertRaises(ContractError) as ctx:
            select_daily_reviews(self.config, [item], TODAY)
        self.assertIn("politics", str(ctx.exception))
        self.assertIn("inactive", str(ctx.exception))


class DailyMinutesOverrideTest(unittest.TestCase):
    """round-37 §3: the daily budget must be an override the caller can supply per day, not a
    single scalar loaded once from config.default_daily_minutes (阶段2决议 §1/C6)."""

    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def test_omitting_the_override_is_byte_identical_to_today(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        without_kwarg = select_daily_reviews(self.config, items, TODAY).summary()
        with_none = select_daily_reviews(
            self.config, items, TODAY, daily_minutes_override=None
        ).summary()
        self.assertEqual(without_kwarg, with_none)

    def test_override_changes_the_hard_cap_and_soft_quota(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        baseline = select_daily_reviews(self.config, items, TODAY)
        # config-minimal.yaml: total=120, review_reserve_ratio=0.45, hard_max_ratio=0.60.
        self.assertEqual(baseline.soft_target_minutes, 54)
        self.assertEqual(baseline.hard_cap_minutes, 72)

        overridden = select_daily_reviews(
            self.config, items, TODAY, daily_minutes_override=240
        )
        self.assertEqual(overridden.soft_target_minutes, 108)
        self.assertEqual(overridden.hard_cap_minutes, 144)
        self.assertGreater(overridden.hard_cap_minutes, baseline.hard_cap_minutes)
        self.assertGreaterEqual(overridden.review_minutes, baseline.review_minutes)

    def test_override_matches_an_equivalent_config_total(self) -> None:
        # The override must feed the exact same arithmetic config.default_daily_minutes does:
        # overriding to 240 must equal loading a config whose default_daily_minutes is 240.
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        via_override = select_daily_reviews(
            self.config, items, TODAY, daily_minutes_override=240
        ).summary()
        equivalent_config = KaoyanConfig(
            schema_version=self.config.schema_version,
            project_id=self.config.project_id,
            default_daily_minutes=240,
            review_reserve_ratio=self.config.review_reserve_ratio,
            hard_max_ratio=self.config.hard_max_ratio,
            subjects=self.config.subjects,
        )
        via_config = select_daily_reviews(equivalent_config, items, TODAY).summary()
        self.assertEqual(via_override, via_config)

    def test_override_shrinking_the_day_never_reduces_the_backlog(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        wide = select_daily_reviews(self.config, items, TODAY, daily_minutes_override=240)
        narrow = select_daily_reviews(self.config, items, TODAY, daily_minutes_override=60)
        self.assertGreaterEqual(len(narrow.deferred), len(wide.deferred))
        self.assertLessEqual(narrow.review_minutes, wide.review_minutes)

    def test_negative_override_is_rejected(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-normal.yaml")
        with self.assertRaises(ValueError):
            select_daily_reviews(self.config, items, TODAY, daily_minutes_override=-1)

    def test_zero_override_is_a_fully_new_content_day(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        result = select_daily_reviews(self.config, items, TODAY, daily_minutes_override=0)
        self.assertEqual(result.soft_target_minutes, 0)
        self.assertEqual(result.hard_cap_minutes, 0)
        self.assertEqual(result.review_minutes, 0)
        self.assertEqual(result.new_learning_minutes, 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
