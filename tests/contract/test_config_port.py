"""M8 exam configuration and budget split port; see ``contracts/config.md``.

Pins the documented rules of ``ky.models.validate_config`` / ``load_config`` and
``ky.schedule.budget`` against the current code. Subject IDs, weights and floors come from
``tests/fixtures/config/config-minimal.yaml``; no repository data counts are hard-coded.
Rules already asserted by ``tests/test_contracts.py`` are not repeated here.
"""

from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

from ky.availability import Availability
from ky.models import (
    SUBJECT_KEYS,
    WEIGHT_TOLERANCE,
    ContractError,
    load_config,
    load_yaml_text,
    scale_minutes,
    validate_config,
)
from tests._fixtures import cross_section_error_pairs, set_nested_value
from ky.schedule.budget import (
    allocate_new_content,
    hard_review_cap_minutes,
    idle_minutes,
    resolve_day_budget,
)
from ky.schedule.planning import Phase, RoutePlan

ROOT = Path(__file__).resolve().parents[2]
CONFIG_SOURCE = ROOT / "tests" / "fixtures" / "config" / "config-minimal.yaml"
DAY = date(2026, 9, 15)


def _document() -> dict[str, Any]:
    """A fresh, mutable copy of the fixture configuration mapping."""
    return copy.deepcopy(load_yaml_text(CONFIG_SOURCE.read_text(encoding="utf-8")))


def _active_indexes(document: dict[str, Any]) -> list[int]:
    return [index for index, subject in enumerate(document["subjects"]) if subject["active"]]


def _inactive_indexes(document: dict[str, Any]) -> list[int]:
    return [index for index, subject in enumerate(document["subjects"]) if not subject["active"]]


def _without_floors(document: dict[str, Any]) -> dict[str, Any]:
    for subject in document["subjects"]:
        subject["min_daily_minutes"] = 0
    return document


def _two_active(document: dict[str, Any], weights: tuple[Any, Any]) -> dict[str, Any]:
    """Keep the first two active fixture subjects, floorless, with the given weights."""
    first, second = (document["subjects"][index] for index in _active_indexes(document)[:2])
    first.update(weight=weights[0], min_daily_minutes=0)
    second.update(weight=weights[1], min_daily_minutes=0)
    document["subjects"] = [first, second]
    return document


def _config_variants(seed: dict[str, Any]) -> list[tuple[str, Any, bool]]:
    """Generate the former migration matrix as current config inputs."""
    variants: list[tuple[str, Any, bool]] = []

    def add(name: str, path: tuple[Any, ...], value: Any, success: bool = False) -> None:
        document = copy.deepcopy(seed)
        set_nested_value(document, path, value)
        variants.append((name, document, success))

    for key in seed:
        document = copy.deepcopy(seed)
        del document[key]
        variants.append((f"config-missing-{key}", document, key == "review_policy"))
    optional_policy_missing = copy.deepcopy(seed)
    optional_policy_missing["review_policy"] = {"self_rating_mode": "lenient"}
    del optional_policy_missing["review_policy"]
    variants.append(("config-missing-review_policy", optional_policy_missing, True))

    for name, path, value in (
        ("config-schema-bool-int", ("schema_version",), True),
        ("config-schema-unsupported", ("schema_version",), 2),
        ("config-project-id-type", ("project_id",), 12),
        ("config-total-bool-int", ("default_daily_minutes",), True),
        ("config-total-lower-bound", ("default_daily_minutes",), 0),
        ("config-review-ratio-bool", ("review_reserve_ratio",), True),
        ("config-review-ratio-nan", ("review_reserve_ratio",), float("nan")),
        ("config-hard-ratio-infinity", ("hard_max_ratio",), float("inf")),
        ("config-review-ratio-out-of-range", ("review_reserve_ratio",), -0.01),
        ("config-hard-ratio-out-of-range", ("hard_max_ratio",), 1.01),
        ("config-hard-ratio-zero", ("hard_max_ratio",), 0.0),
        ("config-hard-ratio-below-reserve", ("hard_max_ratio",), 0.2),
        ("config-subjects-type", ("subjects",), "not-a-list"),
        ("config-subjects-empty", ("subjects",), []),
        ("config-review-policy-type", ("review_policy",), []),
        ("config-review-policy-mode", ("review_policy", "self_rating_mode"), "other"),
    ):
        add(name, path, value)
    policy_mode_missing = copy.deepcopy(seed)
    policy_mode_missing["review_policy"] = {"self_rating_mode": "lenient"}
    del policy_mode_missing["review_policy"]["self_rating_mode"]
    variants.append(("config-policy-mode-missing", policy_mode_missing, True))
    policy_unknown = copy.deepcopy(seed)
    policy_unknown["review_policy"] = {"unexpected": True}
    variants.append(("config-policy-unknown-key", policy_unknown, False))

    unknown_root = copy.deepcopy(seed)
    unknown_root["unexpected_root_field"] = True
    variants.append(("config-unknown-root-field", unknown_root, False))
    unknown_subject = copy.deepcopy(seed)
    unknown_subject["subjects"][0]["unknown_subject_field"] = True
    variants.append(("config-unknown-subject-field", unknown_subject, False))

    for index, subject in enumerate(seed["subjects"]):
        for key in sorted(SUBJECT_KEYS):
            if key not in subject:
                continue
            document = copy.deepcopy(seed)
            del document["subjects"][index][key]
            variants.append((f"config-subject-{index}-missing-{key}", document,
                             key == "min_daily_minutes"))

    for name, path, value in (
        ("config-subject-id-type", ("subjects", 0, "subject_id"), True),
        ("config-display-name-type", ("subjects", 0, "display_name"), True),
        ("config-weight-type", ("subjects", 0, "weight"), "0.4"),
        ("config-subject-weight-nan", ("subjects", 0, "weight"), float("nan")),
        ("config-subject-weight-out-of-range", ("subjects", 0, "weight"), 1.01),
        ("config-subject-active-not-bool", ("subjects", 0, "active"), 1),
        ("config-subject-minutes-bool-int", ("subjects", 0, "min_daily_minutes"), True),
        ("config-subject-minutes-exceeds-total", ("subjects", 0, "min_daily_minutes"),
         seed["default_daily_minutes"] + 1),
    ):
        add(name, path, value)

    subject_id = seed["subjects"][0]["subject_id"]
    duplicate_index = next((i for i in range(len(seed["subjects"])) if i != 0), None)
    if duplicate_index is not None:
        duplicate = copy.deepcopy(seed)
        duplicate["subjects"][duplicate_index]["subject_id"] = subject_id
        variants.append(("config-duplicate-subject-id", duplicate, False))
    no_active = copy.deepcopy(seed)
    for subject in no_active["subjects"]:
        subject["active"] = False
        subject["weight"] = 0.0
        subject["min_daily_minutes"] = 0
    variants.append(("config-no-active-subject", no_active, False))
    active_index = next(i for i, subject in enumerate(seed["subjects"]) if subject["active"])
    altered_weight = copy.deepcopy(seed)
    altered_weight["subjects"][active_index]["weight"] *= 0.8
    variants.append(("config-active-weights-not-closed", altered_weight, False))
    floor_overflow = copy.deepcopy(seed)
    floor_overflow["subjects"][active_index]["min_daily_minutes"] = seed["default_daily_minutes"]
    variants.append(("config-floor-room-insufficient", floor_overflow, False))

    both_budget_errors = copy.deepcopy(seed)
    both_budget_errors["review_reserve_ratio"] = 0.4
    both_budget_errors["hard_max_ratio"] = 0.0
    variants.append(("config-hard-ratio-order-probe", both_budget_errors, False))
    zero_ratios = copy.deepcopy(seed)
    zero_ratios["review_reserve_ratio"] = 0.0
    zero_ratios["hard_max_ratio"] = 0.0
    variants.append(("config-hard-ratio-must-be-positive", zero_ratios, False))
    both_subject_errors = copy.deepcopy(seed)
    both_subject_errors["subjects"][0]["subject_id"] = ""
    both_subject_errors["subjects"][0]["weight"] = float("nan")
    variants.append(("config-subject-field-order-probe", both_subject_errors, False))

    section_errors = [
        ("root", [(("unexpected_root_field",), True)]),
        ("schema", [(("schema_version",), 2)]),
        ("policy", [(("review_policy", "self_rating_mode"), "other")]),
        ("project", [(("project_id",), 42)]),
        ("subject", [(("subjects", 0, "subject_id"), True)]),
    ]
    if duplicate_index is not None:
        section_errors.append(("unique", [(("subjects", duplicate_index, "subject_id"), subject_id)]))
    section_errors.append(("no-active", [
        edit for index in range(len(seed["subjects"]))
        for edit in ((("subjects", index, "active"), False),
                     (("subjects", index, "weight"), 0.0),
                     (("subjects", index, "min_daily_minutes"), 0))
    ]))
    section_errors.extend([
        ("weights", [(("subjects", active_index, "weight"),
                      seed["subjects"][active_index]["weight"] * 0.8)]),
        ("minimums", [(("subjects", active_index, "min_daily_minutes"),
                       seed["default_daily_minutes"] + 1)]),
        ("floor-room", [(("subjects", active_index, "min_daily_minutes"),
                         seed["default_daily_minutes"])]),
    ])
    variants.extend(cross_section_error_pairs(seed, section_errors, "config"))
    variants.append(("config-root-not-mapping", [], False))
    return variants


class ConfigFormatTests(unittest.TestCase):
    def rejected(self, document: Any) -> ContractError:
        with self.assertRaises(ContractError) as caught:
            validate_config(document)
        return caught.exception

    def test_single_error_variant_table(self) -> None:
        variants = _config_variants(_document())
        retired_order_probes = {
            "config-hard-ratio-order-probe", "config-subject-field-order-probe",
        }
        cases = [
            row for row in variants
            if row[0] not in retired_order_probes and "-cross-" not in row[0]
        ]
        self.assertEqual(len({name for name, _, _ in cases}), len(cases))
        for name, document, expected_success in cases:
            with self.subTest(variant=name):
                if expected_success:
                    validate_config(document, source=f"variant:{name}")
                else:
                    with self.assertRaises(ContractError):
                        validate_config(document, source=f"variant:{name}")

    def test_fixture_maps_field_by_field_with_documented_defaults(self) -> None:
        document = _document()
        config = validate_config(document)
        for key in ("schema_version", "project_id", "default_daily_minutes"):
            self.assertEqual(getattr(config, key), document[key])
        for key in ("review_reserve_ratio", "hard_max_ratio"):
            self.assertIsInstance(getattr(config, key), float)
            self.assertEqual(getattr(config, key), float(document[key]))
        expected_mode = document.get("review_policy", {}).get("self_rating_mode", "strict")
        self.assertEqual(config.review_policy.self_rating_mode, expected_mode)
        self.assertEqual(len(config.subjects), len(document["subjects"]))
        for subject, raw in zip(config.subjects, document["subjects"]):
            self.assertEqual(subject.subject_id, raw["subject_id"])
            self.assertEqual(subject.display_name, str(raw["display_name"]))
            self.assertEqual(subject.weight, float(raw["weight"]))
            self.assertIs(subject.active, raw["active"])
            self.assertEqual(subject.min_daily_minutes, raw.get("min_daily_minutes", 0))
        self.assertEqual(
            [subject.subject_id for subject in config.active_subjects()],
            [document["subjects"][index]["subject_id"] for index in _active_indexes(document)],
        )

    def test_renamed_legacy_key_is_rejected_with_migration_message(self) -> None:
        document = _document()
        document["total_daily_minutes"] = document.pop("default_daily_minutes")
        error = self.rejected(document)
        self.assertEqual(error.path, "total_daily_minutes")
        self.assertEqual(
            str(error),
            "total_daily_minutes: total_daily_minutes 已改名为 "
            "default_daily_minutes，请在配置文件里改名",
        )

    def test_renamed_legacy_key_is_rejected_even_with_new_key(self) -> None:
        document = _document()
        document["total_daily_minutes"] = document["default_daily_minutes"]
        error = self.rejected(document)
        self.assertEqual(error.path, "total_daily_minutes")
        self.assertIn("已改名为 default_daily_minutes", str(error))

    def test_each_missing_required_root_field_is_reported_at_its_path(self) -> None:
        for key in ("schema_version", "project_id", "default_daily_minutes",
                    "review_reserve_ratio", "hard_max_ratio", "subjects"):
            document = _document()
            del document[key]
            with self.subTest(field=key):
                self.assertEqual(self.rejected(document).path, key)
        document = _document()
        document.pop("review_policy", None)
        self.assertEqual(validate_config(document).review_policy.self_rating_mode, "strict")

    def test_integer_fields_reject_booleans_and_floats(self) -> None:
        document = _document()
        first = _active_indexes(document)[0]
        cases = (
            (("schema_version",), True, "schema_version"),
            (("schema_version",), 1.0, "schema_version"),
            (("default_daily_minutes",), True, "default_daily_minutes"),
            (("default_daily_minutes",), float(document["default_daily_minutes"]),
             "default_daily_minutes"),
            (("subjects", first, "min_daily_minutes"), False,
             f"subjects[{first}].min_daily_minutes"),
            (("subjects", first, "min_daily_minutes"), 0.0,
             f"subjects[{first}].min_daily_minutes"),
        )
        for field, value, path in cases:
            document = _document()
            node = document
            for key in field[:-1]:
                node = node[key]
            node[field[-1]] = value
            with self.subTest(field=path, value=value):
                self.assertEqual(self.rejected(document).path, path)

    def test_number_fields_reject_booleans_and_strings_but_accept_integers(self) -> None:
        for key in ("review_reserve_ratio", "hard_max_ratio"):
            for value in (True, "0.5"):
                document = _document()
                document[key] = value
                with self.subTest(field=key, value=value):
                    self.assertEqual(self.rejected(document).path, key)
        document = _without_floors(_document())
        document["review_reserve_ratio"] = 0
        document["hard_max_ratio"] = 1
        config = validate_config(document)
        self.assertEqual((config.review_reserve_ratio, config.hard_max_ratio), (0.0, 1.0))
        self.assertIsInstance(config.hard_max_ratio, float)
        integer_weights = _two_active(_document(), (1, 0.0))
        integer_weights["subjects"][1]["active"] = False
        self.assertEqual(validate_config(integer_weights).subjects[0].weight, 1.0)

    def test_weight_tolerance_applies_to_weights_only(self) -> None:
        slack = WEIGHT_TOLERANCE / 2
        single = _two_active(_document(), (1.0 + slack, 0.0))
        single["subjects"][1]["active"] = False
        self.assertEqual(validate_config(single).subjects[0].weight, 1.0 + slack)
        beyond = _two_active(_document(), (0.5, 0.5 + 2 * WEIGHT_TOLERANCE))
        error = self.rejected(beyond)
        self.assertEqual(error.path, "subjects")
        self.assertIn("must sum to 1.0", error.message)
        for key in ("review_reserve_ratio", "hard_max_ratio"):
            document = _document()
            document[key] = 1.0 + slack
            with self.subTest(field=key):
                self.assertEqual(self.rejected(document).path, key)

    def test_hard_ratio_may_equal_reserve_but_must_be_positive(self) -> None:
        document = _without_floors(_document())
        document["hard_max_ratio"] = document["review_reserve_ratio"]
        config = validate_config(document)
        self.assertEqual(config.review_target_minutes(), config.review_hard_cap_minutes())
        document["review_reserve_ratio"] = 0.0
        document["hard_max_ratio"] = 0.0
        error = self.rejected(document)
        self.assertEqual(error.path, "hard_max_ratio")
        self.assertIn("positive", error.message)

    def test_display_name_coerces_integral_numbers_only(self) -> None:
        document = _document()
        first = _active_indexes(document)[0]
        path = f"subjects[{first}].display_name"
        for value, expected in ((408, "408"), (408.0, "408")):
            document = _document()
            document["subjects"][first]["display_name"] = value
            with self.subTest(value=value):
                self.assertEqual(validate_config(document).subjects[first].display_name, expected)
        for value in (408.5, True, "", "   ", None):
            document = _document()
            document["subjects"][first]["display_name"] = value
            with self.subTest(value=value):
                self.assertEqual(self.rejected(document).path, path)

    def test_subject_id_allows_letters_digits_dash_and_underscore_only(self) -> None:
        document = _document()
        first = _active_indexes(document)[0]
        base = document["subjects"][first]["subject_id"]
        for value in (f"{base}-x_1", f"{base}数"):
            document = _document()
            document["subjects"][first]["subject_id"] = value
            with self.subTest(value=value):
                self.assertEqual(validate_config(document).subjects[first].subject_id, value)
        for value in (f"{base} x", f"{base}.x", f"{base}/x", "  "):
            document = _document()
            document["subjects"][first]["subject_id"] = value
            with self.subTest(value=value):
                self.assertEqual(self.rejected(document).path, f"subjects[{first}].subject_id")

    def test_review_policy_mode_values_and_shape(self) -> None:
        document = _document()
        document["review_policy"] = {"self_rating_mode": "lenient"}
        self.assertEqual(validate_config(document).review_policy.self_rating_mode, "lenient")
        cases = (
            (None, "review_policy"),
            ({"self_rating_mode": 1}, "review_policy.self_rating_mode"),
            ({"self_rating_mode": "LENIENT"}, "review_policy.self_rating_mode"),
            ({"extra": "strict"}, "review_policy.extra"),
        )
        for value, path in cases:
            document = _document()
            document["review_policy"] = value
            with self.subTest(value=value):
                self.assertEqual(self.rejected(document).path, path)

    def test_unknown_keys_report_the_first_in_sorted_order(self) -> None:
        document = _document()
        document["zz_unknown"] = 1
        document["aa_unknown"] = 1
        self.assertEqual(self.rejected(document).path, "aa_unknown")
        document = _document()
        first = _active_indexes(document)[0]
        document["subjects"][first]["zz_unknown"] = 1
        document["subjects"][first]["aa_unknown"] = 1
        self.assertEqual(self.rejected(document).path, f"subjects[{first}].aa_unknown")

    def test_subject_level_semantics_report_documented_paths(self) -> None:
        document = _document()
        active = _active_indexes(document)
        later = active[1]
        document["subjects"][later]["subject_id"] = document["subjects"][active[0]]["subject_id"]
        self.assertEqual(self.rejected(document).path, f"subjects[{later}].subject_id")

        document = _document()
        document["subjects"][active[0]]["weight"] = 0.0
        error = self.rejected(document)
        self.assertEqual(error.path, f"subjects[{active[0]}].weight")
        self.assertIn("positive weight", error.message)

        document = _document()
        for subject in document["subjects"]:
            subject.update(active=False, weight=0.0, min_daily_minutes=0)
        self.assertEqual(self.rejected(document).path, "subjects")

    def test_the_first_failing_check_in_documented_order_wins(self) -> None:
        # contracts/config.md §3: root keys, schema, policy, budget fields, subjects, cross-field.
        first = _active_indexes(_document())[0]
        edits = (
            ("unknown root key", lambda d: d.__setitem__("aa_unknown", 1), "aa_unknown"),
            ("schema", lambda d: d.__setitem__("schema_version", 2), "schema_version"),
            ("policy", lambda d: d.__setitem__("review_policy", None), "review_policy"),
            ("project", lambda d: d.__setitem__("project_id", ""), "project_id"),
            ("total", lambda d: d.__setitem__("default_daily_minutes", 0), "default_daily_minutes"),
            ("subjects", lambda d: d.__setitem__("subjects", []), "subjects"),
            ("subject field",
             lambda d: d["subjects"][first].__setitem__("active", "yes"),
             f"subjects[{first}].active"),
        )
        for position in range(len(edits) - 1):
            earlier, later = edits[position], edits[position + 1]
            document = _document()
            later[1](document)
            earlier[1](document)
            with self.subTest(earlier=earlier[0], later=later[0]):
                self.assertEqual(self.rejected(document).path, earlier[2])


class LoadConfigFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def _file(self, content: bytes) -> Path:
        path = self.root / "config.yaml"
        path.write_bytes(content)
        return path

    def _rejected(self, path: Path) -> ContractError:
        with self.assertRaises(ContractError) as caught:
            load_config(path)
        return caught.exception

    def test_file_read_errors_are_contract_errors_with_the_file_path(self) -> None:
        missing = self._rejected(self.root / "absent.yaml")
        self.assertEqual(missing.path, "")
        self.assertIn("file does not exist", missing.message)
        cases = (
            ("not a mapping", b"- 1\n- 2\n", "expected a mapping"),
            ("invalid yaml", b"schema_version: [1\n", "invalid YAML"),
            ("not utf-8", "project_id: 考研\n".encode("gbk"), "cannot read YAML"),
        )
        for label, content, message in cases:
            path = self._file(content)
            with self.subTest(case=label):
                error = self._rejected(path)
                self.assertEqual(error.path, path.as_posix())
                self.assertIn(message, error.message)

    def test_duplicate_key_inside_a_subject_is_rejected(self) -> None:
        text = CONFIG_SOURCE.read_text(encoding="utf-8")
        first_id = _document()["subjects"][0]["subject_id"]
        needle = f"subject_id: {first_id}\n"
        self.assertIn(needle, text)
        doubled = text.replace(needle, needle + "    weight: 0.0\n", 1)
        error = self._rejected(self._file(doubled.encode("utf-8")))
        self.assertIn("duplicate field 'weight'", error.message)

    def test_file_and_mapping_validation_agree(self) -> None:
        self.assertEqual(load_config(CONFIG_SOURCE), validate_config(_document()))


class ConfigViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = _document()
        self.config = validate_config(self.document)

    def test_subject_lookup_covers_inactive_subjects_and_rejects_unknown(self) -> None:
        for index in _inactive_indexes(self.document):
            subject_id = self.document["subjects"][index]["subject_id"]
            self.assertFalse(self.config.subject(subject_id).active)
            self.assertEqual(self.config.weight_of(subject_id), 0.0)
        unknown = "-".join(subject.subject_id for subject in self.config.subjects)
        with self.assertRaises(ContractError) as caught:
            self.config.subject(unknown)
        self.assertEqual(caught.exception.path, "subjects")

    def test_day_hard_cap_is_the_scaled_ratio_bounded_by_the_total(self) -> None:
        ratio = self.config.hard_max_ratio
        for total in range(0, 3 * self.config.default_daily_minutes):
            with self.subTest(total=total):
                self.assertEqual(hard_review_cap_minutes(total, ratio), scale_minutes(total, ratio))
        self.assertEqual(
            hard_review_cap_minutes(self.config.default_daily_minutes, ratio),
            self.config.review_hard_cap_minutes(),
        )
        self.assertEqual(hard_review_cap_minutes(10, 1.5), 10)


class NewContentSplitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = _document()
        self.config = validate_config(self.document)
        self.active = self.config.active_subjects()
        self.floor_total = sum(subject.min_daily_minutes for subject in self.active)

    def test_allocations_follow_active_config_order_and_carry_their_floors(self) -> None:
        budget = self.floor_total + self.config.default_daily_minutes
        allocations = allocate_new_content(self.config, budget)
        self.assertEqual(
            [allocation.subject_id for allocation in allocations],
            [subject.subject_id for subject in self.active],
        )
        for allocation, subject in zip(allocations, self.active):
            self.assertEqual(allocation.display_name, subject.display_name)
            self.assertEqual(allocation.weight, subject.weight)
            self.assertEqual(allocation.floor_minutes, subject.min_daily_minutes)
            self.assertEqual(
                allocation.floor_binding,
                allocation.floor_minutes > 0 and allocation.minutes == allocation.floor_minutes,
            )
        self.assertEqual(sum(allocation.minutes for allocation in allocations), budget)

    def test_each_weighted_share_is_the_floor_or_ceiling_of_its_exact_value(self) -> None:
        weights = {subject.subject_id: Fraction(str(subject.weight)) for subject in self.active}
        weight_total = sum(weights.values())
        for budget in range(self.floor_total, self.floor_total + 4 * len(self.active) * 25):
            remainder = budget - self.floor_total
            with self.subTest(budget=budget):
                allocations = allocate_new_content(self.config, budget)
                for allocation in allocations:
                    exact = remainder * weights[allocation.subject_id] / weight_total
                    extra = allocation.minutes - allocation.floor_minutes
                    self.assertIn(extra, (exact.numerator // exact.denominator,
                                          exact.numerator // exact.denominator + 1))
                self.assertEqual(sum(a.minutes for a in allocations), budget)
                self.assertEqual(idle_minutes(self.config, budget), 0)

    def test_largest_remainder_wins_and_only_ties_fall_back_to_subject_id(self) -> None:
        tied = _two_active(_document(), (0.5, 0.5))
        tied["subjects"].sort(key=lambda subject: subject["subject_id"], reverse=True)
        tied_config = validate_config(tied)
        smaller_id = min(subject.subject_id for subject in tied_config.subjects)
        minutes = {a.subject_id: a.minutes for a in allocate_new_content(tied_config, 3)}
        self.assertEqual(minutes[smaller_id], 2)

        # The later-sorting ID holds the larger remainder, so an ID-first rule would fail here.
        uneven = _two_active(_document(), (0.5, 0.5))
        uneven["subjects"].sort(key=lambda subject: subject["subject_id"])
        uneven["subjects"][0]["weight"] = 0.3
        uneven["subjects"][1]["weight"] = 0.7
        uneven_config = validate_config(uneven)
        larger_id = uneven_config.subjects[1].subject_id
        minutes = {a.subject_id: a.minutes for a in allocate_new_content(uneven_config, 1)}
        self.assertEqual(minutes[larger_id], 1)

    def test_argument_checks_and_waived_floors(self) -> None:
        with self.assertRaises(ValueError):
            allocate_new_content(self.config, self.floor_total, floor_policy="lenient")
        waived = allocate_new_content(self.config, 0, floor_policy="drop_when_short")
        self.assertEqual([a.minutes for a in waived], [0] * len(self.active))
        self.assertEqual([a.floor_minutes for a in waived], [0] * len(self.active))
        with self.assertRaises(ValueError):
            allocate_new_content(self.config, -1, floor_policy="drop_when_short")


class DayBudgetResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = _document()
        self.config = validate_config(self.document)
        self.active_ids = sorted(subject.subject_id for subject in self.config.active_subjects())
        self.inactive_ids = [
            subject.subject_id for subject in self.config.subjects if not subject.active
        ]

    def _route(self, review_minutes: dict[str, int], *, revision: int = 3) -> RoutePlan:
        end = DAY + timedelta(days=10)
        return RoutePlan(
            route_id="route-config-port", revision=revision, start_date=DAY,
            target_exam_date=end, policy_version="policy-v1", stage1_input_hash="0" * 64,
            phases=(Phase(index=0, start=DAY, end_exclusive=end, label="p",
                          review_minutes=review_minutes),),
        )

    def test_without_a_phase_the_budget_carries_only_the_total(self) -> None:
        budget = resolve_day_budget(DAY, self.config, None, None)
        self.assertEqual(
            (budget.total_minutes, budget.total_source, budget.subject_review_quotas,
             budget.phase_index, budget.route_revision),
            (self.config.default_daily_minutes, "config", None, None, None),
        )
        hand_entered = self.config.default_daily_minutes + 7
        availability = Availability({DAY: hand_entered})
        before = self._route({subject_id: 1 for subject_id in self.active_ids})
        budget = resolve_day_budget(DAY - timedelta(days=1), self.config, availability, before)
        self.assertEqual((budget.total_minutes, budget.total_source),
                         (self.config.default_daily_minutes, "config"))
        self.assertIsNone(budget.subject_review_quotas)
        budget = resolve_day_budget(DAY, self.config, availability, None)
        self.assertEqual((budget.total_minutes, budget.total_source),
                         (hand_entered, "availability"))

    def test_quotas_are_active_only_sorted_and_carry_phase_and_revision(self) -> None:
        if not self.inactive_ids:
            self.skipTest("fixture has no inactive subject")
        minutes = {subject_id: 1 for subject_id in reversed(self.active_ids)}
        minutes.update({subject_id: 0 for subject_id in self.inactive_ids})
        route = self._route(minutes, revision=5)
        budget = resolve_day_budget(DAY, self.config, None, route)
        self.assertEqual(list(budget.subject_review_quotas), self.active_ids)
        self.assertEqual(budget.phase_index, 0)
        self.assertEqual(budget.route_revision, route.revision)

    def test_oversized_quotas_scale_to_the_cap_by_exact_largest_remainder(self) -> None:
        cap = hard_review_cap_minutes(self.config.default_daily_minutes, self.config.hard_max_ratio)
        raw = {
            subject_id: cap * (position + 1) + position
            for position, subject_id in enumerate(self.active_ids)
        }
        quotas = resolve_day_budget(DAY, self.config, None, self._route(raw)).subject_review_quotas
        self.assertEqual(sum(quotas.values()), cap)
        raw_total = sum(raw.values())
        for subject_id, value in quotas.items():
            exact = Fraction(cap * raw[subject_id], raw_total)
            with self.subTest(subject=subject_id):
                self.assertIn(value, (exact.numerator // exact.denominator,
                                      exact.numerator // exact.denominator + 1))

        spread = len(self.active_ids)
        if spread < 2:
            self.skipTest("fixture has fewer than two active subjects; no tie to break")
        # Equal raw quotas give equal remainders; pick a hand-entered day whose cap leaves one.
        total = self.config.default_daily_minutes
        while hard_review_cap_minutes(total, self.config.hard_max_ratio) % spread == 0:
            total += 1
        cap = hard_review_cap_minutes(total, self.config.hard_max_ratio)
        tied = {subject_id: cap for subject_id in self.active_ids}
        quotas = resolve_day_budget(
            DAY, self.config, Availability({DAY: total}), self._route(tied),
        ).subject_review_quotas
        base = cap // spread
        extra = cap - base * spread
        self.assertEqual(
            [quotas[subject_id] for subject_id in self.active_ids],
            [base + 1] * extra + [base] * (spread - extra),
        )


if __name__ == "__main__":
    unittest.main()
