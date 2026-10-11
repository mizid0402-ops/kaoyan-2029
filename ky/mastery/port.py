"""M30 mastery calculations; see ``contracts/mastery.md`` §§2–6.

Public interfaces: ``item_level``, ``subject_mastery``, ``mastery_gap``, and
``LEARNED_MAX_DAYS``, ``CONSOLIDATED_MIN_DAYS``, ``WEAK_MIN_LAPSES``.
All inputs are loaded values; this module has no file or state access.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from datetime import date, datetime
from fractions import Fraction
from typing import Any

from ky.knowledge import KnowledgePoint, LearnableTree, learnable_tree
from ky.knowledge.tree_grammar import TreeGrammarError
from ky.models import ContractError, ReviewItem, ReviewSchedule
from ky.schedule.planning import RoutePlan, RoutePlanError, validate_route_plan


LEARNED_MAX_DAYS = 7
CONSOLIDATED_MIN_DAYS = 30
WEAK_MIN_LAPSES = 2

LEVELS = ("unlearned", "learned", "progressing", "consolidated")
_ITEM_LEVELS = ("learned", "progressing", "consolidated")


def _contract(message: str, path: str) -> ContractError:
    return ContractError(message, path)


def item_level(item: ReviewItem, past_question_passed: bool) -> str | None:
    """Return the memory-state tier for an active review item."""
    if not isinstance(item, ReviewItem):
        raise _contract("expected ReviewItem", "item")
    if not isinstance(past_question_passed, bool):
        raise _contract("expected a boolean", "past_question_passed")
    if item.state not in {"queued", "scheduled"}:
        return None
    schedule = item.schedule
    if not isinstance(schedule, ReviewSchedule):
        raise _contract("expected ReviewSchedule", "item.schedule")
    if schedule.mode == "fsrs":
        days = schedule.stability
        path = "item.schedule.stability"
        if isinstance(days, bool) or not isinstance(days, (int, float)):
            raise _contract("FSRS stability must be a number", path)
        if not math.isfinite(days) or days < 0:
            raise _contract("FSRS stability must be finite and non-negative", path)
    else:
        days = schedule.interval_days
        path = "item.schedule.interval_days"
        if isinstance(days, bool) or not isinstance(days, int) or days < 0:
            raise _contract("interval_days must be a non-negative integer", path)
    if days < LEARNED_MAX_DAYS:
        return "learned"
    if days < CONSOLIDATED_MIN_DAYS:
        return "progressing"
    if not past_question_passed:
        return "progressing"
    return "consolidated"


def _sequence(value: object, path: str, item_type: type | None = None) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _contract("expected a sequence", path)
    if item_type is not None:
        for index, item in enumerate(value):
            if not isinstance(item, item_type):
                raise _contract(f"expected {item_type.__name__}", f"{path}[{index}]")
    return value


def _weights(value: object) -> Mapping[str, Fraction] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise _contract("expected a mapping or null", "weights")
    result = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not key:
            raise _contract("weight keys must be non-empty strings", "weights")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise _contract("weights must be numbers", f"weights.{key}")
        if not math.isfinite(raw) or raw < 0:
            raise _contract("weights must be finite and non-negative", f"weights.{key}")
        result[key] = Fraction(str(raw))
    return result


def _past_question_ids(value: object) -> Collection[str]:
    if (not isinstance(value, Collection) or isinstance(value, (str, bytes))):
        raise _contract("expected a collection of review IDs", "past_question_passed")
    for index, review_id in enumerate(value):
        if not isinstance(review_id, str) or not review_id:
            raise _contract("review IDs must be non-empty strings",
                            f"past_question_passed[{index}]")
    return value


def _outline(points: object, grammar: object) -> LearnableTree:
    _sequence(points, "points", KnowledgePoint)
    if not isinstance(grammar, str):
        raise _contract("expected a string", "grammar")
    try:
        return learnable_tree(points, grammar)
    except (ValueError, TreeGrammarError) as exc:
        raise _contract(str(exc), "grammar") from exc


def _leaf_sets(outline: LearnableTree) -> dict[str, tuple[str, ...]]:
    leaves = set(outline.leaves)
    result = {}
    for point_id in outline.points_by_id:
        if point_id not in outline.children:
            continue
        if point_id in leaves:
            result[point_id] = (point_id,)
            continue
        pending = list(outline.children[point_id])
        found = []
        while pending:
            child = pending.pop()
            if child in leaves:
                found.append(child)
            else:
                pending.extend(outline.children[child])
        result[point_id] = tuple(
            leaf for leaf in outline.leaves if leaf in set(found)
        )
    return result


def _weights_by_leaf(
    outline: LearnableTree, weights: Mapping[str, Fraction] | None,
) -> tuple[dict[str, Fraction], list[str]]:
    if weights is None:
        return {leaf: Fraction(1) for leaf in outline.leaves}, []
    subtree_leaves = _leaf_sets(outline)
    result: dict[str, Fraction] = {}
    unweighted = []
    for leaf in outline.leaves:
        current: str | None = leaf
        while current is not None and current not in weights:
            current = outline.parents[current]
        if current is None:
            result[leaf] = Fraction(0)
            unweighted.append(leaf)
        else:
            denominator = len(subtree_leaves[current])
            result[leaf] = weights[current] / denominator
    return result, unweighted


def _nearest_items(
    leaf: str, parents: Mapping[str, str | None],
    items_by_node: Mapping[str, list[ReviewItem]],
) -> tuple[ReviewItem, ...]:
    current: str | None = leaf
    while current is not None:
        group = items_by_node.get(current)
        if group:
            return tuple(group)
        current = parents[current]
    return ()


def _format_fraction(value: Fraction, places: int = 4, *, signed: bool = False) -> str:
    scale = 10 ** places
    numerator = abs(value.numerator) * scale
    quotient, remainder = divmod(numerator, value.denominator)
    if remainder * 2 > value.denominator or (
        remainder * 2 == value.denominator and quotient % 2
    ):
        quotient += 1
    sign = "-" if value < 0 else "+" if signed else ""
    return f"{sign}{quotient // scale}.{quotient % scale:0{places}d}"


def _share_mapping(
    leaf_weights: Mapping[str, Fraction], leaves: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, str | None], str | None, str | None]:
    totals = {level: Fraction(0) for level in LEVELS}
    for leaf_id, data in leaves.items():
        totals[data["level"]] += leaf_weights[leaf_id]
    denominator = sum(leaf_weights.values(), Fraction(0))
    if denominator == 0:
        return {level: None for level in LEVELS}, None, None
    shares = {level: _format_fraction(totals[level] / denominator) for level in LEVELS}
    covered = sum((totals[level] for level in LEVELS if level != "unlearned"), Fraction(0))
    return shares, _format_fraction(covered / denominator), shares["consolidated"]


def subject_mastery(
    subject_id: str, points: Sequence[KnowledgePoint], grammar: str,
    items: Sequence[ReviewItem], weights: Mapping[str, float] | None,
    past_question_passed: Collection[str],
) -> dict[str, Any]:
    """Calculate ordered leaf tiers, lapse weakness, and weighted ability."""
    if not isinstance(subject_id, str) or not subject_id:
        raise _contract("expected a non-empty string", "subject_id")
    outline = _outline(points, grammar)
    _sequence(items, "items", ReviewItem)
    converted_weights = _weights(weights)
    passed_ids = _past_question_ids(past_question_passed)
    tracker_ids = set(outline.trackers)
    unknown_refs: list[str] = []
    tracker_refs: list[str] = []
    excluded_refs: list[str] = []
    items_by_node: dict[str, list[ReviewItem]] = defaultdict(list)
    for item in items:
        if item.subject_id != subject_id:
            continue
        point_id = item.knowledge_point_id
        if point_id not in outline.points_by_id:
            if point_id not in unknown_refs:
                unknown_refs.append(point_id)
            continue
        if point_id in tracker_ids:
            if point_id not in tracker_refs:
                tracker_refs.append(point_id)
            continue
        level = item_level(item, item.review_id in passed_ids)
        if level is None:
            excluded_refs.append(item.review_id)
        else:
            items_by_node[point_id].append(item)

    leaf_results: dict[str, dict[str, Any]] = {}
    counts = dict.fromkeys(LEVELS, 0)
    for leaf in outline.leaves:
        selected = _nearest_items(leaf, outline.parents, items_by_node)
        if selected:
            item_tiers = [
                item_level(item, item.review_id in passed_ids) for item in selected
            ]
            level = min(item_tiers, key=_ITEM_LEVELS.index)
            lapses = max(item.schedule.lapses for item in selected)
        else:
            level, lapses = "unlearned", 0
        counts[level] += 1
        leaf_results[leaf] = {
            "level": level, "lapses": lapses, "weak": lapses >= WEAK_MIN_LAPSES,
        }

    leaf_weights, unweighted = _weights_by_leaf(outline, converted_weights)
    for leaf, data in leaf_results.items():
        data["weight"] = _format_fraction(leaf_weights[leaf])
    shares, covered, ability = _share_mapping(leaf_weights, leaf_results)
    return {
        "subject_id": subject_id,
        "leaves": leaf_results,
        "counts": counts,
        "shares": shares,
        "covered": covered,
        "ability": ability,
        "weak_leaves": [leaf for leaf in outline.leaves if leaf_results[leaf]["weak"]],
        "unweighted_leaves": unweighted,
        "unknown_refs": unknown_refs,
        "tracker_refs": tracker_refs,
        "excluded_refs": excluded_refs,
    }


def _subject_rows(subjects: object) -> Sequence[Mapping[str, Any]]:
    rows = _sequence(subjects, "subjects")
    for index, row in enumerate(rows):
        path = f"subjects[{index}]"
        if not isinstance(row, Mapping):
            raise _contract("expected a mapping", path)
        if not isinstance(row.get("subject_id"), str) or not row["subject_id"]:
            raise _contract("expected a non-empty string", f"{path}.subject_id")
        for field in ("covered", "ability"):
            value = row.get(field)
            if value is None:
                continue
            if not isinstance(value, str):
                raise _contract("expected a decimal string or null", f"{path}.{field}")
            try:
                parsed = Fraction(value)
            except (ValueError, ZeroDivisionError) as exc:
                raise _contract("expected a decimal fraction", f"{path}.{field}") from exc
            if not 0 <= parsed <= 1:
                raise _contract(f"{field} must be between 0 and 1", f"{path}.{field}")
    return rows


def mastery_gap(
    subjects: Sequence[Mapping[str, Any]], today: date, route: RoutePlan | None,
) -> dict[str, Any]:
    """Compare current subject values with interpolated route-stage targets."""
    rows = _subject_rows(subjects)
    if isinstance(today, datetime) or not isinstance(today, date):
        raise _contract("expected a date", "today")
    if route is not None and not isinstance(route, RoutePlan):
        raise _contract("expected RoutePlan or null", "route")
    if route is None:
        status = "missing_route"
        expected = None
        expected_fractions = None
    else:
        try:
            validate_route_plan(route)
        except RoutePlanError as exc:
            raise _contract(str(exc), "route") from exc
        targets = [
            (phase.end_exclusive, Fraction(phase.targets["covered"], 100),
             Fraction(phase.targets["consolidated"], 100))
            for phase in route.phases if phase.targets is not None
        ]
        if not targets:
            status = "no_targets"
            expected = None
            expected_fractions = None
        else:
            status = "ok"
            expected_fractions = _expected_targets(route.start_date, targets, today)
            expected = {key: _format_fraction(value) for key, value in
                        zip(("covered", "consolidated"), expected_fractions)}
    subject_gaps = []
    for row in rows:
        gaps = {"gap_covered": None, "gap_consolidated": None}
        if status == "ok":
            for field, expected_value in zip(("covered", "ability"), expected_fractions):
                value = row[field]
                if value is not None:
                    key = "gap_covered" if field == "covered" else "gap_consolidated"
                    gaps[key] = _format_fraction(Fraction(value) - expected_value, signed=True)
        subject_gaps.append({
            "subject_id": row["subject_id"], "covered": row["covered"],
            "ability": row["ability"], **gaps,
        })
    return {"status": status, "expected": expected, "subjects": subject_gaps}


def _expected_targets(
    start: date, targets: Sequence[tuple[date, Fraction, Fraction]], today: date,
) -> tuple[Fraction, Fraction]:
    previous_date = start
    previous_values = (Fraction(0), Fraction(0))
    for target_date, covered, consolidated in targets:
        values = (covered, consolidated)
        if today < target_date:
            if today <= previous_date:
                return previous_values
            elapsed = (today - previous_date).days
            duration = (target_date - previous_date).days
            portion = Fraction(elapsed, duration)
            return tuple(
                before + (after - before) * portion
                for before, after in zip(previous_values, values)
            )
        previous_date = target_date
        previous_values = values
    return previous_values
