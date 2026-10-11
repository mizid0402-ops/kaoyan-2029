"""Independent verification of Codex's round-3 findings M1-M4.

Run from the repository root:

    py -3.12 tools/archive/verify_round3_findings.py

This script deliberately does not import anything from tests/ so it stays an
independent check rather than a re-run of the same assertions.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ky.models import ContractError, validate_config, validate_review_items  # noqa: E402
from ky.schedule.budget import allocate_new_content  # noqa: E402
from ky.schedule.review_clip import select_daily_reviews  # noqa: E402

TODAY = date(2026, 9, 12)


def base_config(**overrides) -> dict:
    raw = {
        "schema_version": 1,
        "project_id": "kaoyan-2029",
        "total_daily_minutes": 120,
        "review_reserve_ratio": 0.45,
        "hard_max_ratio": 0.60,
        "subjects": [
            {"subject_id": "math1", "display_name": "数学一", "weight": 0.6, "active": True},
            {"subject_id": "cs408", "display_name": "408", "weight": 0.4, "active": True},
        ],
    }
    raw.update(overrides)
    return raw


def review_item(review_id: str, minutes: int, **overrides) -> dict:
    item = {
        "review_id": review_id,
        "revision": 1,
        "subject_id": "math1",
        "knowledge_point_id": f"math1.demo.{review_id}",
        "title": review_id,
        "granularity": "concept",
        "state": "queued",
        "estimated_minutes": minutes,
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


results: list[tuple[str, bool, str]] = []


def check(label: str, passed: bool, detail: str) -> None:
    results.append((label, passed, detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {label}: {detail}")


# --- M1: unknown / misspelled keys must be rejected ------------------------
def m1_unknown_key() -> None:
    raw = base_config()
    raw["subjects"][0]["min_daily_minute"] = 15  # typo for min_daily_minutes
    try:
        config = validate_config(raw)
        check(
            "M1 unknown key in subject",
            False,
            f"accepted; floor defaulted to {config.subjects[0].min_daily_minutes}",
        )
    except ContractError as exc:
        check("M1 unknown key in subject", True, str(exc))


def m1_unknown_root_key() -> None:
    raw = base_config()
    raw["totle_daily_minutes"] = 120  # typo for total_daily_minutes
    try:
        validate_config(raw)
        check("M1 unknown key at root", False, "accepted silently")
    except ContractError as exc:
        check("M1 unknown key at root", True, str(exc))


def m1_review_schema_version() -> None:
    """The *loaded* path must reject an unsupported reviews root schema_version.

    Note: this probes ``load_review_items`` rather than ``validate_review_items``.
    The latter takes a bare item list and therefore has no root mapping to
    inspect; asserting root-version handling there would be testing a contract
    the loader has not promised.
    """
    fixture = REPO_ROOT / "tests" / "fixtures" / "reviews" / "reviews-unsupported-schema-version.yaml"
    try:
        from ky.models import load_review_items

        items = load_review_items(fixture)
        check(
            "M1 reviews root schema_version",
            False,
            f"root schema_version ignored; {len(items)} items accepted",
        )
    except ContractError as exc:
        ok = "schema_version" in str(exc)
        check("M1 reviews root schema_version", ok, str(exc))


def m1_review_unknown_root_key() -> None:
    """A misspelled reviews root key must not be silently ignored."""
    from ky.models import load_review_items

    fixture = REPO_ROOT / "tests" / "fixtures" / "reviews" / "reviews-bad-schema-version.yaml"
    try:
        load_review_items(fixture)
        check("M1 reviews unknown root key", False, "accepted silently")
    except ContractError as exc:
        text = str(exc)
        ok = "schema_version" in text or "iten" in text
        check("M1 reviews unknown root key", ok, text)


# --- M2: review subject must exist and be active ---------------------------
def m2_unknown_subject() -> None:
    config = validate_config(base_config())
    items = validate_review_items([review_item("rv_ghost", 10, subject_id="ghost")])
    try:
        result = select_daily_reviews(config, items, TODAY)
        check(
            "M2 unknown subject rejected",
            not result.selected_ids,
            f"selected={result.selected_ids}",
        )
    except ContractError as exc:
        check("M2 unknown subject rejected", True, str(exc))


def m2_inactive_subject() -> None:
    raw = base_config()
    raw["subjects"].append(
        {"subject_id": "politics", "display_name": "政治", "weight": 0.0, "active": False}
    )
    config = validate_config(raw)
    items = validate_review_items([review_item("rv_pol", 10, subject_id="politics")])
    try:
        result = select_daily_reviews(config, items, TODAY)
        check(
            "M2 inactive subject rejected",
            not result.selected_ids,
            f"selected={result.selected_ids}",
        )
    except ContractError as exc:
        check("M2 inactive subject rejected", True, str(exc))


# --- M3: floor total vs review hard cap ------------------------------------
def m3_floor_conflict() -> None:
    raw = base_config()
    raw["subjects"] = [
        {"subject_id": "math1", "display_name": "数学一", "weight": 0.5, "active": True, "min_daily_minutes": 30},
        {"subject_id": "cs408", "display_name": "408", "weight": 0.5, "active": True, "min_daily_minutes": 30},
    ]
    try:
        config = validate_config(raw)
    except ContractError as exc:
        check("M3 floor-vs-hardcap conflict", True, f"rejected at contract stage: {exc}")
        return

    items = validate_review_items(
        [
            review_item("rv_u1", 30, defer_count=5),
            review_item("rv_u2", 30, defer_count=5),
            review_item("rv_u3", 12, defer_count=5),
        ]
    )
    result = select_daily_reviews(config, items, TODAY)
    try:
        allocation = allocate_new_content(config, result.new_learning_minutes)
    except Exception as exc:  # noqa: BLE001 - reporting any crash is the point
        check(
            "M3 floor-vs-hardcap conflict",
            False,
            f"crash on a contract-valid config: review={result.review_minutes} "
            f"new={result.new_learning_minutes} -> {type(exc).__name__}: {exc}",
        )
        return

    total = sum(a.minutes for a in allocation)
    check(
        "M3 floor-vs-hardcap conflict",
        total == result.new_learning_minutes,
        f"review={result.review_minutes} new={result.new_learning_minutes} allocated={total}",
    )


# --- M4: non-finite floats must be rejected --------------------------------
def m4_non_finite() -> None:
    for bad, label in (
        (float("nan"), "nan"),
        (float("inf"), "inf"),
        (float("-inf"), "-inf"),
    ):
        raw = base_config()
        raw["subjects"][0]["weight"] = bad
        try:
            validate_config(raw)
            check(f"M4 weight={label} rejected", False, "accepted")
        except ContractError as exc:
            check(f"M4 weight={label} rejected", True, str(exc))

    for bad, label in ((float("nan"), "nan"), (float("inf"), "inf")):
        raw = base_config()
        raw["review_reserve_ratio"] = bad
        try:
            validate_config(raw)
            check(f"M4 review_reserve_ratio={label} rejected", False, "accepted")
        except ContractError as exc:
            check(f"M4 review_reserve_ratio={label} rejected", True, str(exc))


# --- extras Codex flagged in section B -------------------------------------
def weight_sum_tolerance_never_overspends() -> None:
    raw = base_config(total_daily_minutes=2_000_000)
    raw["subjects"][0]["weight"] = 0.5
    raw["subjects"][1]["weight"] = 0.5000009
    try:
        config = validate_config(raw)
    except ContractError as exc:
        check("B tolerance-sum overspend", True, f"rejected: {exc}")
        return
    allocation = allocate_new_content(config, 2_000_000)
    total = sum(a.minutes for a in allocation)
    check(
        "B tolerance-sum overspend",
        total == 2_000_000,
        f"allocated {total} for a {2_000_000} budget",
    )


def main() -> int:
    m1_unknown_key()
    m1_unknown_root_key()
    m1_review_schema_version()
    m1_review_unknown_root_key()
    m2_unknown_subject()
    m2_inactive_subject()
    m3_floor_conflict()
    m4_non_finite()
    weight_sum_tolerance_never_overspends()

    failed = [label for label, passed, _ in results if not passed]
    print()
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("still failing: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
