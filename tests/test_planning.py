"""Regression locks for M11 variable route timelines (D10)."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from ky.schedule.planning import Phase, RoutePlan, RoutePlanError, validate_route_plan

START = date(2026, 9, 15)
TARGET = START + timedelta(days=60)
STAGE1_HASH = "a" * 64


def _phase(index: int, start: date, end: date, **updates: object) -> Phase:
    fields: dict[str, object] = {
        "index": index,
        "start": start,
        "end_exclusive": end,
        "label": f"phase-{index}",
        "review_minutes": {"math1": 30, "eng1": 20},
    }
    fields.update(updates)
    return Phase(**fields)


def _plan(phases: tuple[Phase, ...] | None = None, **overrides: object) -> RoutePlan:
    fields: dict[str, object] = {
        "route_id": "route-2029",
        "revision": 1,
        "start_date": START,
        "target_exam_date": TARGET,
        "policy_version": "v1",
        "stage1_input_hash": STAGE1_HASH,
        "phases": phases if phases is not None else (_phase(0, START, TARGET),),
    }
    fields.update(overrides)
    return RoutePlan(**fields)


class TestValidRoutePlan(unittest.TestCase):
    def test_well_formed_timeline_validates(self) -> None:
        plan = _plan()
        self.assertIs(validate_route_plan(plan), plan)
        self.assertEqual(plan.end_exclusive, TARGET)

    def test_first_phase_must_start_at_route_start(self) -> None:
        phase = _phase(0, START + timedelta(days=1), TARGET)
        with self.assertRaises(RoutePlanError) as caught:
            validate_route_plan(_plan((phase,)))
        self.assertEqual(caught.exception.path, "phases[0].start")

    def test_adjacent_phases_must_be_contiguous_and_non_overlapping(self) -> None:
        boundary = START + timedelta(days=30)
        cases = (
            _phase(1, boundary + timedelta(days=1), TARGET),
            _phase(1, boundary - timedelta(days=1), TARGET),
        )
        for second in cases:
            with self.subTest(start=second.start):
                with self.assertRaises(RoutePlanError) as caught:
                    validate_route_plan(_plan((_phase(0, START, boundary), second)))
                self.assertEqual(caught.exception.path, "phases[1].start")

    def test_last_phase_must_end_at_exam_date(self) -> None:
        phase = _phase(0, START, TARGET - timedelta(days=1))
        with self.assertRaises(RoutePlanError) as caught:
            validate_route_plan(_plan((phase,)))
        self.assertEqual(caught.exception.path, "phases[0].end_exclusive")

    def test_empty_phases_are_rejected(self) -> None:
        with self.assertRaises(RoutePlanError) as caught:
            validate_route_plan(_plan(()))
        self.assertEqual(caught.exception.path, "phases")

    def test_phase_end_must_follow_start(self) -> None:
        phase = _phase(0, START, START)
        with self.assertRaises(RoutePlanError) as caught:
            validate_route_plan(_plan((phase,)))
        self.assertEqual(caught.exception.path, "phases[0].end_exclusive")

    def test_review_minutes_require_subjects_and_non_negative_integers(self) -> None:
        invalid_maps = (
            {},
            {"math1": -1},
            {"math1": True},
            {"math1": 1.5},
            {"": 1},
        )
        for minutes in invalid_maps:
            with self.subTest(minutes=minutes), self.assertRaises(RoutePlanError):
                validate_route_plan(_plan((_phase(0, START, TARGET, review_minutes=minutes),)))

    def test_revision_must_be_positive_integer(self) -> None:
        for revision in (0, True, 1.5):
            with self.subTest(revision=revision), self.assertRaises(RoutePlanError) as caught:
                validate_route_plan(_plan(revision=revision))
            self.assertEqual(caught.exception.path, "revision")

    def test_empty_route_id_is_rejected(self) -> None:
        with self.assertRaises(RoutePlanError) as caught:
            validate_route_plan(_plan(route_id=""))
        self.assertEqual(caught.exception.path, "route_id")

    def test_malformed_stage1_hash_is_rejected(self) -> None:
        with self.assertRaises(RoutePlanError) as caught:
            validate_route_plan(_plan(stage1_input_hash="not-a-hash"))
        self.assertEqual(caught.exception.path, "stage1_input_hash")

    def test_target_exam_date_before_start_is_rejected(self) -> None:
        with self.assertRaises(RoutePlanError) as caught:
            validate_route_plan(_plan(target_exam_date=START))
        self.assertEqual(caught.exception.path, "target_exam_date")

    def test_wrong_phase_index_is_rejected(self) -> None:
        phase = _phase(4, START, TARGET)
        with self.assertRaises(RoutePlanError) as caught:
            validate_route_plan(_plan((phase,)))
        self.assertEqual(caught.exception.path, "phases[0].index")


class TestDoesNotPrescribeNumbers(unittest.TestCase):
    """The timeline validates caller inputs without recommending allocations."""

    def test_no_prescriptive_public_names_on_the_module(self) -> None:
        import ky.schedule.planning as planning_module

        banned_prefixes = ("recommend", "suggest", "default", "optimal", "next_phase_")
        for name in dir(planning_module):
            if name.startswith("_"):
                continue
            for prefix in banned_prefixes:
                self.assertFalse(name.lower().startswith(prefix), name)

    def test_no_prescriptive_fields_on_route_types(self) -> None:
        banned_prefixes = ("recommend", "suggest", "default", "optimal", "next_phase_")
        for cls in (RoutePlan, Phase):
            for name in cls.__dataclass_fields__:
                for prefix in banned_prefixes:
                    self.assertFalse(name.lower().startswith(prefix), f"{cls.__name__}.{name}")


if __name__ == "__main__":
    unittest.main()
