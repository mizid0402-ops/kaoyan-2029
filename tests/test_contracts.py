"""Contract-layer tests: shape, semantics, and budget arithmetic.

These run without touching the study workspace. Run with:

    py -m unittest -v tests.test_contracts
"""

from __future__ import annotations

import copy
import random
import sys
import tempfile
import unittest
from datetime import timedelta
from fractions import Fraction
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(REPO_ROOT))

from ky.models import (  # noqa: E402
    ContractError,
    MAX_SINGLE_PASS_MINUTES,
    REVIEW_ITEM_KEYS,
    SCHEDULE_KEYS,
    scale_minutes,
    load_config,
    load_review_items,
    validate_config,
    validate_items_against_config,
    validate_review_item,
    validate_review_items,
)
from tests._fixtures import cross_section_error_pairs, set_nested_value
from ky.schedule.budget import allocate_new_content  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures"
CONFIG_DIR = FIXTURES / "config"
REVIEW_DIR = FIXTURES / "reviews"


def base_config_mapping() -> dict:
    return {
        "schema_version": 1,
        "project_id": "kaoyan-2029",
        "default_daily_minutes": 120,
        "review_reserve_ratio": 0.45,
        "hard_max_ratio": 0.60,
        "subjects": [
            {"subject_id": "math1", "display_name": "数学一", "weight": 0.40, "active": True},
            {"subject_id": "eng1", "display_name": "英语一", "weight": 0.20, "active": True},
            {"subject_id": "cs408", "display_name": "408", "weight": 0.40, "active": True},
        ],
    }


def base_review_mapping(**overrides) -> dict:
    item = {
        "review_id": "rv_test_0001",
        "revision": 1,
        "subject_id": "math1",
        "knowledge_point_id": "math1.limit.demo",
        "title": "测试条目",
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
    item.update(overrides)
    return item


def _review_variants(seed: dict) -> list[tuple[str, object, bool]]:
    """Generate the former ReviewItem matrix as current contract inputs."""
    variants: list[tuple[str, object, bool]] = []

    def add(name: str, path: tuple[object, ...], value: object) -> None:
        document = copy.deepcopy(seed)
        set_nested_value(document, path, value)
        variants.append((name, document, False))

    optional = {"last_reviewed_on", "last_quality", "self_rating"}
    for key in sorted(REVIEW_ITEM_KEYS):
        if key in seed:
            document = copy.deepcopy(seed)
            del document[key]
            variants.append((f"review-missing-{key}", document, key in optional))
    for key in sorted(SCHEDULE_KEYS):
        if key not in seed["schedule"]:
            continue
        document = copy.deepcopy(seed)
        del document["schedule"][key]
        variants.append((f"review-schedule-missing-{key}", document, False))

    type_cases = {
        "review_id": 1, "revision": True, "subject_id": 1, "knowledge_point_id": None,
        "title": True, "granularity": [], "state": [], "estimated_minutes": True,
        "introduced_on": "not-a-date", "due_date": "not-a-date",
        "last_reviewed_on": "not-a-date", "schedule": [], "defer_count": True,
        "last_quality": True, "self_rating": [],
    }
    for key, value in type_cases.items():
        add(f"review-type-{key}", (key,), value)
    unknown = copy.deepcopy(seed)
    unknown["unexpected"] = True
    variants.append(("review-unknown-key", unknown, False))
    schedule_unknown = copy.deepcopy(seed)
    schedule_unknown["schedule"]["unexpected"] = True
    variants.append(("review-schedule-unknown-key", schedule_unknown, False))

    for name, path, value in (
        ("review-phase-bool-int", ("schedule", "phase"), True),
        ("review-phase-out-of-range", ("schedule", "phase"), 6),
        ("review-interval-lower-bound", ("schedule", "interval_days"), 0),
        ("review-ease-nan", ("schedule", "ease_factor"), float("nan")),
        ("review-ease-out-of-range", ("schedule", "ease_factor"), 1.0),
        ("review-repetitions-bool-int", ("schedule", "repetitions"), True),
        ("review-lapses-negative", ("schedule", "lapses"), -1),
        ("review-mode-invalid", ("schedule", "mode"), "other"),
        ("review-state-invalid", ("state",), "other"),
        ("review-granularity-invalid", ("granularity",), "other"),
        ("review-estimated-over-cap", ("estimated_minutes",), MAX_SINGLE_PASS_MINUTES + 1),
        ("review-last-quality-over-range", ("last_quality",), 6),
        ("review-self-rating-invalid", ("self_rating",), "other"),
        ("review-due-before-introduced", ("due_date",), seed["introduced_on"] - timedelta(days=1)),
        ("review-last-before-introduced", ("last_reviewed_on",),
         seed["introduced_on"] - timedelta(days=1)),
    ):
        add(name, path, value)
    vocab = copy.deepcopy(seed)
    vocab["granularity"] = "vocabulary_batch"
    vocab["estimated_minutes"] = 6
    variants.append(("review-vocabulary-batch-too-long", vocab, False))

    category_order = copy.deepcopy(seed)
    category_order["granularity"] = "invalid-granularity"
    category_order["state"] = "invalid-state"
    variants.append(("review-category-order-probe", category_order, False))
    date_order = copy.deepcopy(seed)
    date_order["due_date"] = date_order["introduced_on"] - timedelta(days=1)
    date_order["last_reviewed_on"] = date_order["introduced_on"] - timedelta(days=2)
    variants.append(("review-date-order-probe", date_order, False))
    identity_order = copy.deepcopy(seed)
    identity_order["review_id"] = 7
    identity_order["revision"] = True
    variants.append(("review-identity-order-probe", identity_order, False))
    sections = [
        ("unknown", [(("unexpected",), True)]),
        ("identity", [(("review_id",), 7)]),
        ("category", [(("state",), "other")]),
        ("minutes", [(("estimated_minutes",), MAX_SINGLE_PASS_MINUTES + 1)]),
        ("dates", [(("due_date",), seed["introduced_on"] - timedelta(days=1))]),
        ("schedule", [(("schedule",), [])]),
        ("defer", [(("defer_count",), True)]),
        ("feedback", [(("last_quality",), 6)]),
        ("vocabulary", [(("granularity",), "vocabulary_batch"),
                         (("estimated_minutes",), 6)]),
    ]
    variants.extend(cross_section_error_pairs(seed, sections, "review"))
    variants.append(("review-root-not-mapping", [], False))
    return variants


def _review_seed() -> dict:
    document = yaml.safe_load((REVIEW_DIR / "reviews-normal.yaml").read_text(encoding="utf-8"))
    return document["items"][0]


class ConfigContractTest(unittest.TestCase):
    def test_minimal_config_loads(self) -> None:
        config = load_config(CONFIG_DIR / "config-minimal.yaml")
        self.assertEqual(config.project_id, "kaoyan-2029")
        self.assertEqual(config.default_daily_minutes, 120)
        self.assertEqual(config.review_target_minutes(), 54)
        self.assertEqual(config.review_hard_cap_minutes(), 72)
        self.assertEqual(len(config.active_subjects()), 3)
        self.assertEqual(config.weight_of("math1"), 0.40)

    def test_review_algorithm_defaults_to_ladder_and_accepts_fsrs(self) -> None:
        default = validate_config(base_config_mapping())
        self.assertEqual(default.review_policy.algorithm, "ladder")
        mapping = base_config_mapping()
        mapping["review_policy"] = {"algorithm": "fsrs", "self_rating_mode": "lenient"}
        selected = validate_config(mapping)
        self.assertEqual(selected.review_policy.algorithm, "fsrs")
        self.assertEqual(selected.review_policy.self_rating_mode, "lenient")

    def test_invalid_review_algorithm_has_policy_path(self) -> None:
        mapping = base_config_mapping()
        mapping["review_policy"] = {"algorithm": "sm2"}
        with self.assertRaises(ContractError) as caught:
            validate_config(mapping)
        self.assertEqual(caught.exception.path, "review_policy.algorithm")

    def test_inactive_subject_weight_must_be_zero(self) -> None:
        mapping = base_config_mapping()
        mapping["subjects"].append(
            {"subject_id": "politics", "display_name": "政治", "weight": 0.10, "active": False}
        )
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertIn("inactive subject must have weight 0", str(ctx.exception))

    def test_inactive_subject_min_daily_minutes_must_be_zero(self) -> None:
        # allocate_new_content() only ever looks at active subjects, so a
        # floor declared on an inactive one would silently never be honoured.
        mapping = base_config_mapping()
        mapping["subjects"].append(
            {
                "subject_id": "politics",
                "display_name": "政治",
                "weight": 0.0,
                "active": False,
                "min_daily_minutes": 10,
            }
        )
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertIn("min_daily_minutes 0", str(ctx.exception))
        self.assertEqual(ctx.exception.path, "subjects[3].min_daily_minutes")

    def test_active_weight_sum_must_be_one(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            load_config(CONFIG_DIR / "config-weights-not-closed.yaml")
        self.assertIn("must sum to 1.0", str(ctx.exception))
        self.assertEqual(ctx.exception.path, "subjects")

    def test_hard_cap_must_not_be_below_soft_quota(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            load_config(CONFIG_DIR / "config-ratio-inverted.yaml")
        self.assertEqual(ctx.exception.path, "hard_max_ratio")

    def test_duplicate_subject_id_rejected(self) -> None:
        mapping = base_config_mapping()
        mapping["subjects"][1] = copy.deepcopy(mapping["subjects"][0])
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertIn("duplicate subject_id", str(ctx.exception))

    def test_unsupported_schema_version_rejected(self) -> None:
        mapping = base_config_mapping()
        mapping["schema_version"] = 2
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertEqual(ctx.exception.path, "schema_version")

    def test_empty_subject_list_rejected(self) -> None:
        mapping = base_config_mapping()
        mapping["subjects"] = []
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertEqual(ctx.exception.path, "subjects")

    def test_min_daily_minutes_cannot_exceed_total(self) -> None:
        mapping = base_config_mapping()
        mapping["subjects"][1]["min_daily_minutes"] = 200
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertIn("exceeds default_daily_minutes", str(ctx.exception))

    def test_error_messages_carry_the_field_path(self) -> None:
        mapping = base_config_mapping()
        mapping["subjects"][2]["weight"] = "0.4"
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertEqual(ctx.exception.path, "subjects[2].weight")
        self.assertIn("subjects[2].weight", str(ctx.exception))

    # -- M1: unknown / misspelled keys must fail closed, not default silently

    def test_unknown_root_key_rejected(self) -> None:
        mapping = base_config_mapping()
        mapping["totle_daily_minutes"] = 120  # typo for default_daily_minutes
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertIn("totle_daily_minutes", str(ctx.exception))

    def test_misspelled_subject_field_is_not_silently_defaulted(self) -> None:
        mapping = base_config_mapping()
        mapping["subjects"][1]["min_daily_minute"] = 15  # typo, missing 's'
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertIn("min_daily_minute", ctx.exception.path)

    def test_non_string_keys_are_contract_errors_with_a_text_path(self) -> None:
        # WP-R3 (round 151 §5): YAML ``1: x`` next to a typo'd field used to raise TypeError
        # from sorting int and str keys together; a lone one left an int in ``.path``.
        root_mixed = base_config_mapping()
        root_mixed.update({1: "x", "zz": 1})
        subject_mixed = base_config_mapping()
        subject_mixed["subjects"][1].update({2: "x", "zz": 1})
        root_alone = base_config_mapping()
        root_alone[1] = "x"
        for mapping, field_path in (
            (root_mixed, "1"),
            (subject_mixed, "subjects[1].2"),
            (root_alone, "1"),
        ):
            with self.subTest(field_path=field_path):
                with self.assertRaises(ContractError) as ctx:
                    validate_config(mapping)
                self.assertEqual(ctx.exception.path, field_path)
                self.assertIsInstance(ctx.exception.path, str)

    def test_unknown_schedule_field_rejected(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            validate_review_item(
                base_review_mapping(
                    schedule={
                        "mode": "fixed_bootstrap",
                        "phase": 1,
                        "interval_days": 3,
                        "ease_factor": 2.5,
                        "repetitions": 1,
                        "lapses": 0,
                        "extra_field": True,
                    }
                )
            )
        with self.assertRaises(ContractError):
            validate_review_item(
                base_review_mapping(
                    schedule={
                        "mode": "sm2_lite",
                        "phase": 1,
                        "interval_days": 30,
                        "ease_factor": 2.5,
                        "repetitions": 5,
                        "lapses": 0,
                    }
                )
            )
        self.assertIn("extra_field", ctx.exception.path)

    def test_unknown_review_item_field_rejected(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            validate_review_item(base_review_mapping(bogus_field="x"))
        self.assertIn("bogus_field", ctx.exception.path)

    # -- M4: NaN/Inf must be rejected explicitly, not by range-check accident

    def test_non_finite_weight_rejected(self) -> None:
        for bad in (float("nan"), float("inf"), float("-inf")):
            mapping = base_config_mapping()
            mapping["subjects"][0]["weight"] = bad
            with self.assertRaises(ContractError) as ctx:
                validate_config(mapping)
            self.assertEqual(ctx.exception.path, "subjects[0].weight", msg=f"weight={bad}")

    def test_non_finite_review_reserve_ratio_rejected(self) -> None:
        for bad in (float("nan"), float("inf"), float("-inf")):
            mapping = base_config_mapping()
            mapping["review_reserve_ratio"] = bad
            with self.assertRaises(ContractError) as ctx:
                validate_config(mapping)
            self.assertEqual(ctx.exception.path, "review_reserve_ratio", msg=f"ratio={bad}")

    def test_non_finite_ease_factor_rejected(self) -> None:
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ContractError):
                validate_review_item(
                    base_review_mapping(
                        schedule={
                            "mode": "fixed_bootstrap",
                            "phase": 1,
                            "interval_days": 3,
                            "ease_factor": bad,
                            "repetitions": 1,
                            "lapses": 0,
                        }
                    )
                )

    # -- M3: a floor commitment and the review hard cap must both fit

    def test_floors_that_would_starve_the_review_hard_cap_are_rejected_at_config_time(
        self,
    ) -> None:
        # total=120, hard_max_ratio=0.60 -> review hard cap 72; floors sum to
        # 60, leaving only 48 for new content out of the 48 the hard cap
        # would demand at worst. A contract-valid config must never be able
        # to reach this collision at runtime (see ky/schedule/budget.py).
        mapping = base_config_mapping()
        mapping["subjects"] = [
            {"subject_id": "math1", "display_name": "数学一", "weight": 0.5, "active": True,
             "min_daily_minutes": 30},
            {"subject_id": "cs408", "display_name": "408", "weight": 0.5, "active": True,
             "min_daily_minutes": 30},
        ]
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertEqual(ctx.exception.path, "subjects")

    def test_floors_exactly_at_the_boundary_are_accepted(self) -> None:
        # total=120, hard cap=72 -> exactly 48 minutes are guaranteed for new
        # content even in the worst case. Floors summing to exactly 48 must
        # be accepted, not rejected off-by-one.
        mapping = base_config_mapping()
        mapping["subjects"] = [
            {"subject_id": "math1", "display_name": "数学一", "weight": 0.5, "active": True,
             "min_daily_minutes": 24},
            {"subject_id": "cs408", "display_name": "408", "weight": 0.5, "active": True,
             "min_daily_minutes": 24},
        ]
        config = validate_config(mapping)
        self.assertEqual(sum(s.min_daily_minutes for s in config.active_subjects()), 48)


class BudgetAllocationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_DIR / "config-minimal.yaml")

    def test_allocation_sums_to_new_content_budget(self) -> None:
        # Anything below the sum of the declared floors cannot be allocated.
        for minutes in range(15, 121):
            allocations = allocate_new_content(self.config, minutes)
            self.assertEqual(
                sum(a.minutes for a in allocations),
                minutes,
                msg=f"allocation lost minutes at budget {minutes}",
            )

    def test_budget_below_the_declared_floors_is_refused(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            allocate_new_content(self.config, 10)
        self.assertIn("min_daily_minutes sum", str(ctx.exception))

    def test_floor_then_weight_split_when_the_floor_binds(self) -> None:
        # 66 minutes: floor 15 to eng1, then 51 split 40/20/40 -> 20.4/10.2/20.4.
        # Largest remainder keeps 20/10/20 and gives the one spare minute to
        # cs408 (the tied remainder of 0.4 breaks on subject_id), so eng1 ends
        # at 25 while math1 and cs408 land at 20 and 21. Asserted explicitly
        # because this is the regime where English's floor lifts it above its
        # nominal 20% share.
        allocations = {a.subject_id: a.minutes for a in allocate_new_content(self.config, 66)}
        self.assertEqual(allocations["eng1"], 25)
        self.assertEqual(allocations["math1"], 20)
        self.assertEqual(allocations["cs408"], 21)
        self.assertEqual(sum(allocations.values()), 66)

    def test_floor_rides_on_top_of_the_weight_split_at_a_large_remainder(self) -> None:
        # 115 free-content minutes: the 15-minute eng1 floor is granted in
        # full, then the 100-minute remainder is split 40/20/40. The result
        # is 40/35/40, NOT the nominal 40/20/40 -- the floor never "stops
        # binding" in this algorithm, it always rides on top of the weighted
        # remainder. eng1 ends at 35/115 (~30.4%), well above its declared
        # 20% share, however large the budget gets.
        allocations = {a.subject_id: a.minutes for a in allocate_new_content(self.config, 115)}
        self.assertEqual(allocations["math1"], 40)
        self.assertEqual(allocations["eng1"], 35)  # 15 floor + 20
        self.assertEqual(allocations["cs408"], 40)
        self.assertEqual(sum(allocations.values()), 115)

    def test_weight_sum_within_tolerance_never_overspends_the_budget(self) -> None:
        # validate_config accepts active weights within 1e-6 of 1.0. A large
        # enough budget used to turn that tiny slack into a real overspend
        # (allocate_new_content(..., 2_000_000) handed out 2_000_001) because
        # the split divided by the *declared* weights instead of normalising
        # them first.
        mapping = base_config_mapping()
        mapping["default_daily_minutes"] = 2_000_000
        mapping["subjects"] = [
            {"subject_id": "math1", "display_name": "数学一", "weight": 0.5, "active": True},
            {"subject_id": "cs408", "display_name": "408", "weight": 0.5000009, "active": True},
        ]
        config = validate_config(mapping)
        allocations = allocate_new_content(config, 2_000_000)
        self.assertEqual(sum(a.minutes for a in allocations), 2_000_000)

    def test_exact_rational_split_never_over_or_under_spends_at_large_budgets(self) -> None:
        # Regression for round-3-fix2 finding B: binary-float normalisation
        # in _proportional_split lost precision once default_daily_minutes grew
        # past roughly 2**53 (a double's mantissa width), which let the
        # largest-remainder split over- or under-spend the budget by several
        # minutes -- e.g. 10**17 with weights 0.5 / 0.5000009 used to hand
        # out 100_000_000_000_000_006, six minutes over. allocate_new_content
        # now normalises with fractions.Fraction, which is exact for
        # arbitrarily large integers, so every budget below is asserted to
        # sum back exactly with no negative minutes.
        two_53 = 2**53
        ten_17 = 10**17
        budgets = {
            ten_17 - 1,
            ten_17,
            ten_17 + 1,
            two_53 - 1,
            two_53,
            two_53 + 1,
            10**18,
            10**20,
        }
        rng = random.Random(20260912)
        budgets.update(rng.randint(10**15, 10**21) for _ in range(20))

        for budget in sorted(budgets):
            mapping = base_config_mapping()
            mapping["default_daily_minutes"] = budget
            mapping["subjects"] = [
                {"subject_id": "math1", "display_name": "数学一", "weight": 0.5, "active": True},
                {"subject_id": "cs408", "display_name": "408", "weight": 0.5000009, "active": True},
            ]
            config = validate_config(mapping)
            with self.subTest(budget=budget):
                allocations = allocate_new_content(config, budget)
                minutes = [a.minutes for a in allocations]
                self.assertEqual(sum(minutes), budget)  # no overspend, no underspend
                self.assertTrue(all(m >= 0 for m in minutes))

    def test_a_full_free_day_reproduces_the_declared_weights_plus_the_floor(self) -> None:
        allocations = {a.subject_id: a.minutes for a in allocate_new_content(self.config, 120)}
        self.assertEqual(allocations["math1"], 42)  # 0.40 * 105 = 42
        self.assertEqual(allocations["eng1"], 36)  # 15 floor + 0.20 * 105 = 21
        self.assertEqual(allocations["cs408"], 42)
        self.assertEqual(sum(allocations.values()), 120)

    def test_min_daily_minutes_is_honoured(self) -> None:
        allocations = {a.subject_id: a.minutes for a in allocate_new_content(self.config, 20)}
        self.assertGreaterEqual(allocations["eng1"], 15)

    def test_allocation_is_deterministic(self) -> None:
        first = allocate_new_content(self.config, 97)
        for _ in range(50):
            self.assertEqual(first, allocate_new_content(self.config, 97))

    def test_zero_budget_is_refused_while_floors_are_declared(self) -> None:
        with self.assertRaises(ValueError):
            allocate_new_content(self.config, 0)

    def test_negative_budget_rejected(self) -> None:
        with self.assertRaises(ValueError):
            allocate_new_content(self.config, -1)


class ReviewItemContractTest(unittest.TestCase):
    def test_single_error_variant_table(self) -> None:
        variants = _review_variants(_review_seed())
        retired_order_probes = {
            "review-category-order-probe", "review-date-order-probe",
            "review-identity-order-probe",
        }
        cases = [
            row for row in variants
            if row[0] not in retired_order_probes and "-cross-" not in row[0]
        ]
        self.assertEqual(len({name for name, _, _ in cases}), len(cases))
        for name, document, expected_success in cases:
            with self.subTest(variant=name):
                if expected_success:
                    validate_review_item(document, index=0, source=f"variant:{name}")
                else:
                    with self.assertRaises(ContractError):
                        validate_review_item(document, index=0, source=f"variant:{name}")

    def test_normal_fixture_loads(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-normal.yaml")
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].review_id, "rv_math1_limit_0001")
        self.assertIsNone(items[2].last_self_rating)

    def test_overloaded_fixture_loads(self) -> None:
        items = load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")
        self.assertEqual(len(items), 15)

    def test_single_pass_cap_rejects_oversized_item(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            validate_review_item(base_review_mapping(estimated_minutes=40))
        self.assertIn("single-pass cap", str(ctx.exception))

    def test_vocabulary_batch_cost_is_bounded(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            validate_review_item(
                base_review_mapping(granularity="vocabulary_batch", estimated_minutes=12)
            )
        self.assertIn("batched flashcards", str(ctx.exception))

    def test_due_before_introduced_rejected(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            validate_review_item(base_review_mapping(due_date="2026-08-01"))
        self.assertTrue(ctx.exception.path.endswith("due_date"))
        self.assertIn("must not precede introduced_on", str(ctx.exception))

    def test_unknown_state_rejected(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            validate_review_item(base_review_mapping(state="done"))
        self.assertIn("state must be one of", str(ctx.exception))

    def test_unknown_granularity_rejected(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            validate_review_item(base_review_mapping(granularity="vibes"))
        self.assertIn("granularity must be one of", str(ctx.exception))

    def test_phase_mode_consistency_enforced(self) -> None:
        with self.assertRaises(ContractError):
            validate_review_item(
                base_review_mapping(
                    schedule={
                        "mode": "fixed_bootstrap",
                        "phase": 5,
                        "interval_days": 30,
                        "ease_factor": 2.5,
                        "repetitions": 5,
                        "lapses": 0,
                    }
                )
            )
        with self.assertRaises(ContractError):
            validate_review_item(
                base_review_mapping(schedule={
                    "mode": "sm2_lite", "phase": 1, "interval_days": 30,
                    "ease_factor": 2.5, "repetitions": 5, "lapses": 0,
                })
            )

    def test_fsrs_schedule_requires_valid_memory_state(self) -> None:
        schedule = {
            "mode": "fsrs", "phase": 5, "interval_days": 30, "ease_factor": 2.5,
            "repetitions": 2, "lapses": 1, "stability": 18.5, "difficulty": 4.2,
            "fsrs_reviewed_on": "2026-10-01",
        }
        item = validate_review_item(base_review_mapping(schedule=schedule))
        self.assertEqual(item.schedule.stability, 18.5)
        self.assertEqual(item.schedule.fsrs_reviewed_on.isoformat(), "2026-10-01")
        for field in ("stability", "difficulty", "fsrs_reviewed_on"):
            invalid = dict(schedule)
            invalid.pop(field)
            with self.subTest(missing=field), self.assertRaises(ContractError) as caught:
                validate_review_item(base_review_mapping(schedule=invalid), index=0)
            self.assertEqual(caught.exception.path, f"items[0].schedule.{field}")
        for field, value in (
            ("stability", 0.0), ("stability", float("inf")),
            ("difficulty", 10.1), ("difficulty", 0.9),
            ("fsrs_reviewed_on", "10-01-2026"), ("fsrs_reviewed_on", "20261001"),
        ):
            invalid = dict(schedule, **{field: value})
            with self.subTest(field=field, value=value), self.assertRaises(ContractError) as caught:
                validate_review_item(base_review_mapping(schedule=invalid), index=0)
            self.assertEqual(caught.exception.path, f"items[0].schedule.{field}")

    def test_fsrs_memory_fields_are_rejected_for_ladder_mode(self) -> None:
        schedule = dict(base_review_mapping()["schedule"])
        schedule["stability"] = 5.0
        with self.assertRaises(ContractError) as caught:
            validate_review_item(base_review_mapping(schedule=schedule), index=0)
        self.assertEqual(caught.exception.path, "items[0].schedule.stability")

    def test_ease_factor_range_enforced(self) -> None:
        with self.assertRaises(ContractError):
            validate_review_item(
                base_review_mapping(
                    schedule={
                        "mode": "fixed_bootstrap",
                        "phase": 1,
                        "interval_days": 3,
                        "ease_factor": 9.0,
                        "repetitions": 1,
                        "lapses": 0,
                    }
                )
            )

    def test_unknown_self_rating_rejected(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            validate_review_item(base_review_mapping(self_rating="很熟练"))
        self.assertIn("self_rating must be one of", str(ctx.exception))

    def test_duplicate_review_id_rejected(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            validate_review_items([base_review_mapping(), base_review_mapping()])
        self.assertIn("duplicate review_id", str(ctx.exception))


class CrossContractTest(unittest.TestCase):
    """Checks that span both files: config subjects vs. review item subject_id."""

    def test_unknown_subject_id_in_review_item_is_rejected(self) -> None:
        config = validate_config(base_config_mapping())
        items = validate_review_items([base_review_mapping(subject_id="math2")])
        with self.assertRaises(ContractError) as ctx:
            validate_items_against_config(config, items)
        self.assertIn("not declared in config.subjects", str(ctx.exception))
        self.assertEqual(ctx.exception.path, "items[0].subject_id")

    def test_inactive_subject_id_in_review_item_is_rejected(self) -> None:
        mapping = base_config_mapping()
        mapping["subjects"].append(
            {"subject_id": "politics", "display_name": "政治", "weight": 0.0, "active": False}
        )
        config = validate_config(mapping)
        items = validate_review_items([base_review_mapping(subject_id="politics")])
        with self.assertRaises(ContractError) as ctx:
            validate_items_against_config(config, items)
        self.assertIn("inactive", str(ctx.exception))
        self.assertEqual(ctx.exception.path, "items[0].subject_id")

    def test_known_subject_id_passes(self) -> None:
        config = validate_config(base_config_mapping())
        items = validate_review_items([base_review_mapping(subject_id="math1")])
        validate_items_against_config(config, items)  # must not raise


class ReviewsFileContractTest(unittest.TestCase):
    """Checks on the reviews-file root mapping: schema_version and shape."""

    def test_unsupported_reviews_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviews.yaml"
            path.write_text("schema_version: 99\nitems: []\n", encoding="utf-8")
            with self.assertRaises(ContractError) as ctx:
                load_review_items(path)
        self.assertIn("schema_version", ctx.exception.path)

    def test_unknown_reviews_root_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviews.yaml"
            path.write_text("schema_version: 1\nitems: []\nnotes: hi\n", encoding="utf-8")
            with self.assertRaises(ContractError) as ctx:
                load_review_items(path)
        self.assertIn("notes", ctx.exception.path)


class DuplicateYamlKeyTest(unittest.TestCase):
    """A field declared twice must fail closed, not resolve to "the last one".

    This is the same failure class as the unknown-key check (a value the author
    wrote being silently discarded), but ``_reject_unknown_keys`` structurally
    cannot catch it: YAML collapses the duplicate before Python ever sees the
    mapping, so by then there is nothing left to reject.
    """

    def test_duplicate_key_in_a_review_item_is_rejected(self) -> None:
        # Written as 999 then 10. Plain safe_load returns 10 and the 999 --
        # which the single-pass cap would have rejected -- vanishes silently.
        body = base_review_mapping()
        lines = ["schema_version: 1", "items:", f"  - review_id: {body['review_id']}"]
        for key, value in body.items():
            if key in ("review_id", "schedule"):
                continue
            lines.append(f"    {key}: {value}")
            if key == "estimated_minutes":
                lines.append(f"    {key}: 10")
        lines.append("    schedule:")
        for key, value in body["schedule"].items():
            lines.append(f"      {key}: {value}")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviews.yaml"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(ContractError) as ctx:
                load_review_items(path)
        self.assertIn("duplicate field", str(ctx.exception))
        self.assertIn("estimated_minutes", str(ctx.exception))

    def test_duplicate_key_in_the_config_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "schema_version: 1\n"
                "project_id: kaoyan-2029\n"
                "default_daily_minutes: 120\n"
                "default_daily_minutes: 30\n"
                "review_reserve_ratio: 0.45\n"
                "hard_max_ratio: 0.60\n"
                "subjects:\n"
                "  - subject_id: math1\n"
                "    display_name: 数学一\n"
                "    weight: 1.0\n"
                "    active: true\n",
                encoding="utf-8",
            )
            with self.assertRaises(ContractError) as ctx:
                load_config(path)
        self.assertIn("duplicate field", str(ctx.exception))
        self.assertIn("default_daily_minutes", str(ctx.exception))

    def test_duplicate_key_in_a_nested_schedule_block_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviews.yaml"
            path.write_text(
                "schema_version: 1\n"
                "items:\n"
                "  - review_id: rv_dup_nested\n"
                "    revision: 1\n"
                "    subject_id: math1\n"
                "    knowledge_point_id: math1.k\n"
                "    title: nested\n"
                "    granularity: concept\n"
                "    state: queued\n"
                "    estimated_minutes: 10\n"
                "    introduced_on: 2026-09-01\n"
                "    due_date: 2026-09-12\n"
                "    schedule:\n"
                "      mode: fixed_bootstrap\n"
                "      phase: 1\n"
                "      interval_days: 3\n"
                "      interval_days: 9\n"
                "      ease_factor: 2.5\n"
                "      repetitions: 1\n"
                "      lapses: 0\n"
                "    defer_count: 0\n"
                "    last_quality: 4\n",
                encoding="utf-8",
            )
            with self.assertRaises(ContractError) as ctx:
                load_review_items(path)
        self.assertIn("interval_days", str(ctx.exception))

    def test_the_shipped_fixtures_still_load(self) -> None:
        # The strict loader must not be stricter than intended: every fixture
        # the project ships has to keep parsing unchanged.
        self.assertEqual(len(load_review_items(REVIEW_DIR / "reviews-overloaded.yaml")), 15)
        self.assertEqual(load_config(CONFIG_DIR / "config-minimal.yaml").default_daily_minutes, 120)


class RatioBoundTest(unittest.TestCase):
    """The weight tolerance must not leak onto the two ratio fields.

    ``WEIGHT_TOLERANCE`` exists because decimal weights do not close exactly in
    binary floating point. A ratio outside ``[0, 1]`` is a different thing: it
    is meaningless, not imprecise.
    """

    def test_a_negative_review_reserve_ratio_is_rejected(self) -> None:
        # -1e-6 used to be accepted (it sits exactly on the weight tolerance)
        # and produced review_target_minutes() == -1: a negative duration
        # reported straight into the preflight summary and its JSON payload.
        mapping = base_config_mapping()
        mapping["review_reserve_ratio"] = -1e-6
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertEqual(ctx.exception.path, "review_reserve_ratio")

    def test_a_hard_max_ratio_above_one_is_rejected(self) -> None:
        mapping = base_config_mapping()
        mapping["hard_max_ratio"] = 1.000001
        with self.assertRaises(ContractError) as ctx:
            validate_config(mapping)
        self.assertEqual(ctx.exception.path, "hard_max_ratio")

    def test_the_exact_bounds_are_still_accepted(self) -> None:
        for soft, hard in ((0.0, 1.0), (1.0, 1.0), (0.45, 0.60)):
            mapping = base_config_mapping()
            mapping["review_reserve_ratio"] = soft
            mapping["hard_max_ratio"] = hard
            with self.subTest(soft=soft, hard=hard):
                config = validate_config(mapping)
                self.assertGreaterEqual(config.review_target_minutes(), 0)
                self.assertGreaterEqual(
                    config.review_hard_cap_minutes(), config.review_target_minutes()
                )

    def test_weights_keep_their_tolerance(self) -> None:
        # The tolerance was narrowed on the ratios only; weights still have to
        # tolerate decimals that do not close (round-3 finding B).
        mapping = base_config_mapping()
        mapping["subjects"] = [
            {"subject_id": "math1", "display_name": "数学一", "weight": 0.5, "active": True},
            {"subject_id": "cs408", "display_name": "408", "weight": 0.5000009, "active": True},
        ]
        config = validate_config(mapping)
        self.assertEqual(sum(a.minutes for a in allocate_new_content(config, 120)), 120)


class RatioScalingTest(unittest.TestCase):
    """The review quotas must not depend on binary float multiplication.

    ``int(total * ratio)`` overflows once ``total`` passes roughly 1e308, which
    would escape the CLI as a traceback instead of the documented exit code 2.
    The contract sets no upper bound on ``default_daily_minutes``, so the scaling
    is done with exact rational arithmetic instead.

    The frozen contract is ``floor(total x Fraction(str(ratio)))`` and nothing
    else. Every general test below asserts against that exact rational value.
    The float product is the artifact that was *replaced*, so it is never the
    basis of comparison -- with exactly one deliberate exception, the narrow
    migration regression at the bottom of this class, which is scoped to the
    two ratios this project actually ships and says so in its own name.
    """

    # Ratios whose shortest decimal form is what the config author writes.
    TERMINATING_RATIOS = (0.45, 0.60, 0.05, 0.99, 0.01, 1.0, 0.75, 0.125)
    ALL_RATIOS = TERMINATING_RATIOS + (0.3333333333333333,)

    def assert_exact_contract(self, total: int, ratio: float) -> None:
        """``scale_minutes`` == ``floor(total x Fraction(str(ratio)))``, plus
        the three invariants that follow from the definition of ``floor``."""
        product = total * Fraction(str(ratio))
        actual = scale_minutes(total, ratio)
        self.assertEqual(actual, product // 1, msg=f"total={total} ratio={ratio}")
        self.assertLessEqual(actual, product, msg=f"total={total} ratio={ratio}")
        self.assertLess(product, actual + 1, msg=f"total={total} ratio={ratio}")
        self.assertTrue(0 <= actual <= total, msg=f"total={total} ratio={ratio}")

    def test_exact_contract_holds_across_the_everyday_range(self) -> None:
        """Every ratio x every budget in 1..5000 against the exact rational.

        This used to compare against ``int(total * ratio)`` and fail with
        "exact scaling diverged from the float product", which installed the
        replaced implementation as the authority over its replacement. The
        domain is unchanged; only the basis of comparison is corrected, so this
        is strictly stronger: it now also fails if ``scale_minutes`` and the
        float product drift *together*.
        """
        failures: list[tuple[int, float, int, int]] = []
        for total in range(1, 5001):
            for ratio in self.TERMINATING_RATIOS:
                product = total * Fraction(str(ratio))
                actual = scale_minutes(total, ratio)
                if actual != product // 1 or not (0 <= actual <= total):
                    failures.append((total, ratio, actual, int(product // 1)))
        self.assertEqual(
            failures,
            [],
            msg=f"exact-rational contract violated in the everyday range: {failures[:5]}",
        )

    def test_exact_contract_holds_at_realistic_daily_budgets(self) -> None:
        for total in (60, 90, 120, 180, 240, 300, 480, 600, 720, 1440):
            for ratio in self.TERMINATING_RATIOS:
                with self.subTest(total=total, ratio=ratio):
                    self.assert_exact_contract(total, ratio)

    def test_exact_contract_holds_for_repeating_decimals(self) -> None:
        """The frozen contract: ``floor(total x Fraction(str(ratio)))`` exactly.

        ``0.3333333333333333`` is a truncated 1/3, not 1/3. The float product
        rounds it up (``int(3 * 0.3333333333333333) == 1``) while exact scaling
        honours the decimal that was written
        (``3 * 0.3333333333333333 == 0.9999999999999998889... -> 0``).

        The comparison is against the *exact rational* product, deliberately
        not against the float product: the float product is the artifact being
        replaced, so it must not be treated as the authority here.
        """
        from fractions import Fraction

        ratio = 0.3333333333333333
        rational = Fraction(str(ratio))
        for total in (3, 6, 53, 999, 10**9, 10**17):
            product = total * rational
            exact = scale_minutes(total, ratio)
            with self.subTest(total=total):
                self.assertEqual(exact, product // 1)
                self.assertLessEqual(exact, product)
                self.assertLess(product, exact + 1)
                self.assertGreaterEqual(exact, 0)
                self.assertLessEqual(exact, total)

    def test_float_multiplication_rounding_artifact_is_documented(self) -> None:
        """A case where exact scaling intentionally differs from ``int(t * r)``.

        Pinned because it is the only known class of divergence and it used to
        be invisible. With ``ratio = 1/53`` stored as the float
        ``0.018867924528301886`` and ``total = 53``:

        * the decimal that was written is ``9433962264150943/5e17``, which is
          *less* than ``1/53``, so ``53 * ratio`` is just under 1;
        * the binary float actually stored is also just under ``1/53``;
        * both exact readings therefore floor to **0**;
        * ``int(53 * ratio)`` returns **1** purely because the double
          multiplication rounds ``53 * ratio`` up to exactly 1.0.

        Exact scaling is the correct reading of the contract's ``floor(total x
        ratio)``; the float product was the artifact. The review-boundary
        consequence is real and deliberate: a 1/53 reserve of a 53-minute day
        is zero minutes, not one.
        """
        ratio = 1 / 53
        total = 53
        self.assertEqual(scale_minutes(total, ratio), 0)
        self.assertEqual(int(total * ratio), 1, "the old artifact must stay visible in this test")

        from fractions import Fraction

        decimal_exact = (total * Fraction(str(ratio))) // 1
        binary_exact = (total * Fraction(ratio)) // 1
        self.assertEqual(decimal_exact, 0)
        self.assertEqual(binary_exact, 0, "both exact readings agree; only float mul rounds up")

    def test_migration_regression_shipped_ratios_match_the_old_float_product(self) -> None:
        """Migration regression, NOT a contract: ``ratio in {0.45, 0.60}`` and
        ``total in 1..20000`` inclusive -- exactly the domain asserted below.

        This is the only test in the file that compares against
        ``int(total * ratio)``, and it exists for one narrow reason: to show
        that swapping ``int(total * ratio)`` for exact rational arithmetic
        changed **no** number the shipped config can actually produce
        (``default_daily_minutes: 120``, ratios ``0.45`` / ``0.60``).

        Read a failure here as "investigate the migration", never as
        "``scale_minutes`` is wrong" -- where the two disagree, the exact
        value is correct by definition of the contract and the float product is
        the rounding artifact. The agreement is bounded and measured, not
        universal:

        * measured over ``total = 1..200000``: zero divergences for both ratios;
        * both ratios already differ by one at ``total = 9007199254740973``
          (``0.45`` -> 4053239664633437 exact vs 4053239664633438 float;
          ``0.60`` -> 5404319552844583 exact vs 5404319552844584 float);
        * past roughly ``1e308`` ``int(total * ratio)`` raises ``OverflowError``
          and cannot be compared at all.

        See ``test_float_multiplication_rounding_artifact_is_documented`` for a
        divergence inside the everyday range with a non-terminating ratio.
        """
        for ratio in (0.45, 0.60):
            for total in range(1, 20001):
                with self.subTest(ratio=ratio, total=total):
                    self.assertEqual(scale_minutes(total, ratio), int(total * ratio))

    def test_the_shipped_ratios_float_agreement_is_bounded_not_universal(self) -> None:
        """Pins the counter-example that bounds the test above.

        Without this, "0.45 and 0.60 agree with the float product" reads as a
        universal claim. It is not one, and the boundary must stay visible so
        nobody widens the migration regression back into a general guarantee.
        """
        total = 9007199254740973
        self.assertEqual(scale_minutes(total, 0.45), 4053239664633437)
        self.assertEqual(int(total * 0.45), 4053239664633438)
        self.assertEqual(scale_minutes(total, 0.60), 5404319552844583)
        self.assertEqual(int(total * 0.60), 5404319552844584)

        # ...and past ~1e308 the float product cannot even be computed, while
        # the exact path keeps returning an integer inside [0, total].
        huge = 10**309
        with self.assertRaises(OverflowError):
            int(huge * 0.45)
        self.assert_exact_contract(huge, 0.45)

    def test_exact_contract_holds_across_a_cross_product(self) -> None:
        """The general frozen contract, asserted without reference to floats.

        For every accepted ``(total, ratio)`` the result must be exactly
        ``floor(total x Fraction(str(ratio)))``, which pins the three derived
        invariants in one place: it never exceeds the true product, it is within
        one minute below it, and it stays inside ``[0, total]``.
        """
        from fractions import Fraction

        ratios = (
            0.45, 0.60, 0.05, 0.99, 0.01, 1.0, 0.75, 0.125,
            1 / 53, 2 / 53, 3 / 53, 1 / 3, 0.3333333333333333, 1e-9, 0.999999999,
        )
        totals = (1, 2, 53, 60, 106, 120, 159, 1440, 10**6, 10**17, 2**53 + 1, 10**100)

        failures: list[tuple[int, float, int, int]] = []
        for ratio in ratios:
            rational = Fraction(str(ratio))
            for total in totals:
                product = total * rational
                expected = product // 1
                actual = scale_minutes(total, ratio)
                if (
                    actual != expected
                    or actual > product
                    or not (actual <= product < actual + 1)
                    or not (0 <= actual <= total)
                ):
                    failures.append((total, ratio, actual, expected))
        self.assertEqual(
            failures,
            [],
            msg=f"exact-rational contract violated: {failures[:5]}",
        )

    def test_astronomically_large_budgets_stay_finite_and_positive(self) -> None:
        for digits in (308, 309, 400, 3000):
            total = 10**digits
            for ratio in self.ALL_RATIOS:
                quota = scale_minutes(total, ratio)
                with self.subTest(digits=digits, ratio=ratio):
                    self.assertIsInstance(quota, int)
                    self.assertGreaterEqual(quota, 0)
                    self.assertLessEqual(quota, total)

    def test_large_budget_config_validates_and_builds_a_plan(self) -> None:
        mapping = base_config_mapping()
        mapping["default_daily_minutes"] = 10**400
        config = validate_config(mapping)
        self.assertGreater(config.review_target_minutes(), 0)
        self.assertGreater(config.review_hard_cap_minutes(), 0)
        self.assertGreaterEqual(
            config.review_hard_cap_minutes(), config.review_target_minutes()
        )

    def test_deficit_ratio_stays_finite_at_astronomical_budgets(self) -> None:
        from datetime import date as _date

        from ky.schedule.review_clip import select_daily_reviews

        mapping = base_config_mapping()
        mapping["default_daily_minutes"] = 10**400
        config = validate_config(mapping)
        item = validate_review_item(
            {
                "review_id": "rv_huge_0001",
                "revision": 1,
                "subject_id": "math1",
                "knowledge_point_id": "math1.demo.huge",
                "title": "巨大预算下的排序键",
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
        )
        result = select_daily_reviews(
            config, [item], _date(2026, 9, 12), seven_day_usage={"math1": 0}
        )
        self.assertEqual(result.selected_ids, ("rv_huge_0001",))
        self.assertEqual(result.review_minutes, 10)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
