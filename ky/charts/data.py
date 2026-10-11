"""M17 chart data mappings; see ``contracts/charts.md`` §§4.5, 8.

Public interfaces: ``week_chart_data``, ``progress_chart_data``, and
``ability_chart_data``. Inputs are loaded domain objects; these pure functions own the
stable mapping consumed by render.py.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable, Mapping

from ky.knowledge import LearnableTree, KnowledgePoint, learnable_tree
from ky.models import ContractError, KaoyanConfig, ReviewItem
from ky.schedule.completion import CompletionEvent
from ky.schedule.longitudinal import DayPlan
from ky.schedule.planning import RoutePlan


def week_chart_data(semester_label: str, week: int, days: Iterable[Any]) -> dict[str, Any]:
    """Map seven ``(day, schedule, base_minutes)`` rows to the stable contract."""
    # M17 / sol 282 M1: the mapping contract requires seven loaded day rows.
    if days is None:
        raise ContractError("expected seven day rows", "week.days")
    rows = []
    endpoints: list[int] = []
    for day, schedule, base_minutes in days:
        if schedule is None:
            rows.append({
                "date": day.isoformat(), "weekday": day.isoweekday(),
                "covered": False, "no_class": None,
                "followed": None, "classes": [], "free_segments": [], "free_minutes": None,
                "blocks": None, "base_minutes": None, "minutes": None,
            })
            continue
        day = schedule.day
        classes = [
            {
                "name": name, "first_period": first, "last_period": last,
                "start": start, "end": end,
                "unconfirmed": bool(set(range(first, last + 1))
                                     .intersection(schedule.unconfirmed_periods)),
            }
            for name, first, last, start, end in schedule.classes
        ]
        for _name, _first, _last, start, end in schedule.classes:
            endpoints.extend((_clock_minutes(start), _clock_minutes(end)))
        for start, end in schedule.free_segments:
            endpoints.extend((_clock_minutes(start), _clock_minutes(end)))
        rows.append({
            "date": day.isoformat(), "weekday": day.isoweekday(), "covered": True,
            "no_class": schedule.no_class,
            "followed": schedule.followed.isoformat() if schedule.followed else None,
            "classes": classes, "free_segments": [list(segment)
                                                      for segment in schedule.free_segments],
            "free_minutes": schedule.free_minutes, "blocks": schedule.blocks,
            "base_minutes": base_minutes, "minutes": schedule.minutes,
        })
    low, high = (min(endpoints), max(endpoints)) if endpoints else (480, 1320)
    return {
        "kind": "week", "semester": semester_label, "week": week, "days": rows,
        "time_range": [f"{low // 60:02d}:00", f"{((high + 59) // 60):02d}:00"],
    }


def _clock_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":"))
    return hour * 60 + minute


def _as_day(value: date | str) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _weekly_plan(start: date, end: date, plans: Iterable[DayPlan], subjects: tuple[str, ...]):
    plan_rows = tuple(plans)
    if not any(start <= plan.day <= end for plan in plan_rows):
        return []
    buckets: dict[date, dict[str, int]] = defaultdict(lambda: dict.fromkeys(subjects, 0))
    cursor = start
    while cursor <= end:
        monday = cursor - timedelta(days=cursor.weekday())
        buckets[monday]
        cursor += timedelta(days=1)
    for plan in plan_rows:
        if start <= plan.day <= end:
            monday = plan.day - timedelta(days=plan.day.weekday())
            for subject in subjects:
                buckets[monday][subject] += plan.subject_minutes.get(subject, 0)
    return [
        {
            "week_start": monday.isoformat(),
            "from": max(start, monday).isoformat(),
            "to": min(end, monday + timedelta(days=6)).isoformat(),
            "minutes": dict(buckets[monday]),
        }
        for monday in sorted(buckets)
    ]


def _coverage(
    subjects: tuple[str, ...], subject_names: Mapping[str, str],
    trees: Mapping[str, tuple[KnowledgePoint, ...] | None],
    tree_grammars: Mapping[str, str], queue_items: tuple[ReviewItem, ...],
) -> list[dict[str, Any]]:
    refs: dict[str, list[str]] = defaultdict(list)
    for item in queue_items:
        refs[item.subject_id].append(item.knowledge_point_id)
    result = []
    for subject in subjects:
        points = trees[subject]
        if points is None:
            result.append({
                "subject_id": subject, "name": subject_names[subject],
                "covered": None, "total": None, "unknown_refs": [],
                "tracker_refs": [], "tree": None,
            })
            continue
        outline = learnable_tree(points, tree_grammars[subject])
        points_by_id = outline.points_by_id
        trackers = set(outline.trackers)
        active = set(points_by_id) - trackers
        children = outline.children
        leaves = set(outline.leaves)
        covered: set[str] = set()
        unknown: list[str] = []
        tracker_refs: list[str] = []
        for ref in dict.fromkeys(refs[subject]):
            if ref in trackers:
                tracker_refs.append(ref)
            elif ref not in active:
                unknown.append(ref)
            elif ref in leaves:
                covered.add(ref)
            else:
                covered.update(_descendant_leaves(ref, children, leaves))
        node_tree = {
            "id": subject, "title": subject_names[subject], "lit": len(covered),
            "leaves": len(leaves),
            "children": [_node(root, points_by_id, children, covered)
                         for root in outline.roots],
        }
        result.append({
            "subject_id": subject, "name": subject_names[subject],
            "covered": len(covered), "total": len(leaves),
            "unknown_refs": unknown, "tracker_refs": tracker_refs, "tree": node_tree,
        })
    return result


def _node(
    point_id: str, points_by_id: Mapping[str, KnowledgePoint],
    children: Mapping[str, list[str]], covered: set[str],
) -> dict[str, Any]:
    leaves = _descendant_leaves(point_id, children, {
        node_id for node_id in children if not children[node_id]
    })
    return {
        "id": point_id, "title": points_by_id[point_id].title,
        "lit": len(leaves & covered), "leaves": len(leaves),
        "children": [_node(child, points_by_id, children, covered)
                     for child in children[point_id]],
    }


def _descendant_leaves(
    root: str, children: Mapping[str, tuple[str, ...]], leaves: set[str],
) -> set[str]:
    if root in leaves:
        return {root}
    found, pending = set(), list(children[root])
    while pending:
        node = pending.pop()
        if node in leaves:
            found.add(node)
        else:
            pending.extend(children[node])
    return found


def _route_mapping(route: RoutePlan | None, today: date) -> dict[str, Any] | None:
    if route is None:
        return None
    return {
        "route_id": route.route_id, "revision": route.revision,
        "target_exam_date": route.target_exam_date.isoformat(),
        "days_to_exam": (route.target_exam_date - today).days,
        "phases": [
            {"index": phase.index, "start": phase.start.isoformat(),
             "end_exclusive": phase.end_exclusive.isoformat(), "label": phase.label,
             "base_daily_minutes": phase.base_daily_minutes,
             "review_minutes": dict(phase.review_minutes)}
            for phase in route.phases
        ],
    }


def progress_chart_data(
    *, start: date, end: date, today: date, config: KaoyanConfig,
    subject_names: Mapping[str, str], reference_minutes: Mapping[date | str, int],
    plans: Iterable[DayPlan], completions: Iterable[CompletionEvent],
    queue_items: Iterable[ReviewItem],
    knowledge_trees: Mapping[str, tuple[KnowledgePoint, ...] | None],
    tree_grammars: Mapping[str, str], route: RoutePlan | None,
) -> dict[str, Any]:
    """Build daily, weekly, grammar-aware coverage, and route values."""
    # M17 / sol 282 M1: start is a required date boundary for this pure port.
    if start is None:
        raise ContractError("expected a date", "progress.start")
    first, last, current = map(_as_day, (start, end, today))
    references = {_as_day(day): minutes for day, minutes in reference_minutes.items()}
    events = {event.day: event for event in completions}
    plan_rows = tuple(plans)
    queue_rows = tuple(queue_items)
    subjects = tuple(subject.subject_id for subject in config.active_subjects())
    daily, recorded_actual, recorded_reference = [], [], []
    cursor = first
    while cursor <= last:
        event = events.get(cursor)
        actual = None if event is None else event.study_minutes
        reference = references[cursor]
        daily.append({"date": cursor.isoformat(), "actual": actual, "reference": reference})
        if actual is not None:
            recorded_actual.append(actual)
            recorded_reference.append(reference)
        cursor += timedelta(days=1)
    return {
        "kind": "progress", "from": first.isoformat(), "to": last.isoformat(),
        "today": current.isoformat(), "daily": daily,
        "daily_totals": {"recorded_days": len(recorded_actual),
                         "actual_sum": sum(recorded_actual),
                         "reference_sum_on_recorded_days": sum(recorded_reference)},
        "weekly_plan": _weekly_plan(first, last, plan_rows, subjects),
        "coverage": _coverage(subjects, subject_names, knowledge_trees,
                              tree_grammars, queue_rows),
        "route": _route_mapping(route, current),
    }


def _chapter_title(outline: LearnableTree, point_id: str) -> str | None:
    current = outline.parents[point_id]
    while current is not None:
        point = outline.points_by_id[current]
        if point.scope == "chapter":
            return point.title
        current = outline.parents[current]
    return None


def _mastery_node(
    point_id: str, outline: LearnableTree, mastery: Mapping[str, Any],
) -> dict[str, Any]:
    children = outline.children[point_id]
    leaf_results = mastery["leaves"]
    if not children:
        result = leaf_results[point_id]
        return {
            "id": point_id, "title": outline.points_by_id[point_id].title,
            "level": result["level"], "weak": result["weak"],
            "lapses": result["lapses"], "chapter": _chapter_title(outline, point_id),
            "counts": {level: int(result["level"] == level)
                       for level in ("unlearned", "learned", "progressing", "consolidated")},
            "leaves": 1, "children": [],
        }
    nodes = [_mastery_node(child, outline, mastery) for child in children]
    counts = {level: sum(node["counts"][level] for node in nodes)
              for level in ("unlearned", "learned", "progressing", "consolidated")}
    return {
        "id": point_id, "title": outline.points_by_id[point_id].title,
        "counts": counts, "leaves": sum(node["leaves"] for node in nodes),
        "children": nodes,
    }


def ability_chart_data(
    *, today: date, subjects: Iterable[str], subject_names: Mapping[str, str],
    masteries: Mapping[str, Mapping[str, Any] | None], gap: Mapping[str, Any],
    knowledge_trees: Mapping[str, tuple[KnowledgePoint, ...] | None],
    tree_grammars: Mapping[str, str], weighted_subjects: Iterable[str],
) -> dict[str, Any]:
    """Combine M30 results with ordered display trees for the ability page."""
    # M17 / sol 282 M1: today is required to produce the mapping's ISO date.
    if today is None:
        raise ContractError("expected a date", "ability.today")
    weighted = set(weighted_subjects)
    gap_by_subject = {row["subject_id"]: row for row in gap["subjects"]}
    rows, weak_items = [], []
    for subject in subjects:
        mastery = masteries[subject]
        points = knowledge_trees[subject]
        outline = (None if points is None else
                   learnable_tree(points, tree_grammars[subject]))
        if mastery is None or outline is None:
            rows.append({
                "subject_id": subject, "name": subject_names[subject],
                "weighted": subject in weighted, "covered": None, "ability": None,
                "gap_covered": gap_by_subject[subject]["gap_covered"],
                "gap_consolidated": gap_by_subject[subject]["gap_consolidated"],
                "counts": None, "shares": None, "unweighted_leaves": [],
                "unknown_refs": [], "tracker_refs": [], "excluded_refs": [], "tree": None,
            })
            continue
        children = [
            _mastery_node(root, outline, mastery) for root in outline.roots
        ]
        rows.append({
            "subject_id": subject, "name": subject_names[subject],
            "weighted": subject in weighted, "covered": mastery["covered"],
            "ability": mastery["ability"],
            "gap_covered": gap_by_subject[subject]["gap_covered"],
            "gap_consolidated": gap_by_subject[subject]["gap_consolidated"],
            "counts": mastery["counts"],
            "shares": mastery["shares"], "unweighted_leaves": mastery["unweighted_leaves"],
            "unknown_refs": mastery["unknown_refs"],
            "tracker_refs": mastery["tracker_refs"],
            "excluded_refs": mastery["excluded_refs"],
            "tree": {"id": subject, "title": subject_names[subject],
                     "counts": mastery["counts"], "leaves": len(outline.leaves),
                     "children": children},
        })
        for leaf_id in mastery["weak_leaves"]:
            leaf = mastery["leaves"][leaf_id]
            weak_items.append({
                "subject_id": subject, "subject_name": subject_names[subject],
                "knowledge_point_id": leaf_id,
                "chapter": _chapter_title(outline, leaf_id) or "—",
                "title": outline.points_by_id[leaf_id].title,
                "lapses": leaf["lapses"], "level": leaf["level"],
            })
    return {
        "kind": "ability", "today": today.isoformat(), "status": gap["status"],
        "expected": gap["expected"], "subjects": rows, "weak_items": weak_items,
    }
