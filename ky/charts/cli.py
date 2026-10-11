"""M17 chart CLI; see ``contracts/charts.md`` §§2–5, 8 and M4/M30 ports.

Public interface: ``chart_main``. This adapter reads each registered source once, delegates
mapping and rendering, and writes only rebuildable output files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import webbrowser
from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path

import plotly.offline

from ky.availability import availability_source_for_workspace
from ky.charts.data import ability_chart_data, progress_chart_data, week_chart_data
from ky.charts.render import render_ability, render_progress, render_week
from ky.knowledge import load_knowledge_points
from ky.knowledge.knowledge_point import KnowledgePointError
from ky.mastery import mastery_gap, subject_mastery
from ky.models import ContractError, load_config
from ky.pacing import settings_for_workspace
from ky.schedule.budget import resolve_day_budget
from ky.schedule.completion import CompletionError
from ky.schedule.planning import RoutePlanError
from ky.storage.atomic import replace_bytes
from ky.storage.day_plan_store import DayPlanStore, StorageError
from ky.storage.review_shards import ReviewShardStore
from ky.storage.route_store import RoutePlanStore
from ky.timetable import timetable_for_workspace
from ky.timetable_io.preview import base_resolver
from ky.workspace import load_workspace


def _parser(action: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"py -3.12 -m ky chart {action}")
    parser.add_argument("--workspace")
    parser.add_argument("--config")
    parser.add_argument("--out")
    parser.add_argument("--open", action="store_true")
    if action == "week":
        parser.add_argument("--week", type=int, required=True)
        parser.add_argument("--semester")
    elif action == "progress":
        parser.add_argument("--from", dest="from_day")
        parser.add_argument("--to", dest="to_day")
        parser.add_argument("--today")
    else:
        parser.add_argument("--today")
    return parser


def _date_arg(value: str | None, field: str, default: date) -> date:
    if value is None:
        return default
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("expected YYYY-MM-DD", field) from exc
    if parsed.isoformat() != value:
        raise ContractError("expected YYYY-MM-DD", field)
    return parsed


def _config(workspace, explicit: str | None):
    path = Path(explicit) if explicit else workspace.exam_config
    if path is None:
        raise ContractError(
            "pass --config explicitly or register settings.exam_config", "settings.exam_config",
        )
    return load_config(path)


def _output_dir(workspace, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).absolute()
    output = workspace.products.get("charts")
    if output is None:
        raise ContractError("register products.charts or pass --out DIR", "products.charts")
    return output


def _write_page(directory: Path, filename: str, html: str, open_page: bool) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    library = plotly.offline.get_plotlyjs().encode("utf-8")
    library_path = directory / "plotly.min.js"
    if not library_path.exists() or library_path.read_bytes() != library:
        replace_bytes(library_path, library)
    page = directory / filename
    replace_bytes(page, html.encode("utf-8"))
    absolute = page.absolute()
    print(f"saved: {absolute}")
    print(absolute.as_uri())
    if open_page:
        webbrowser.open(absolute.as_uri())
    return 0


def _week(args) -> int:
    workspace = load_workspace(args.workspace)
    calendar = timetable_for_workspace(workspace)
    if calendar is None or not calendar.timetable.semesters:
        print("没有可显示的学期", file=sys.stderr)
        return 3
    semester = _select_semester(calendar, args.semester)
    if semester is None:
        return 3
    if args.week < 1 or args.week > semester.weeks:
        print(f"--week must be 1..{semester.weeks}", file=sys.stderr)
        return 3
    config = _config(workspace, args.config)
    output = _output_dir(workspace, args.out)
    base_for = base_resolver(workspace, config)
    monday = semester.week1_monday + timedelta(weeks=args.week - 1)
    days = []
    for offset in range(7):
        day = monday + timedelta(days=offset)
        base = base_for(day)
        days.append((day, calendar.day(day, base), base))
    data = week_chart_data(semester.label, args.week, days)
    safe_label = re.sub(r"[^A-Za-z0-9_-]", "_", semester.label)
    filename = f"week--{safe_label}--w{args.week:02d}.html"
    return _write_page(output, filename, render_week(data), args.open)


def _select_semester(calendar, label: str | None):
    semesters = calendar.timetable.semesters
    if label is not None:
        for semester in semesters:
            if semester.label == label:
                return semester
        print(f"unknown semester: {label}", file=sys.stderr)
        return None
    if len(semesters) != 1:
        print("多个学期时必须指定 --semester", file=sys.stderr)
        return None
    return semesters[0]


def _load_state(workspace):
    plans = DayPlanStore(workspace.plans).read_state_sources()
    queue = ReviewShardStore(workspace.review_queue).read_state_sources()
    route = None
    if workspace.routes is not None:
        route = RoutePlanStore(workspace.routes).read_state_sources().route
    return plans, queue, route


def _progress(args) -> int:
    workspace = load_workspace(args.workspace)
    config = _config(workspace, args.config)
    today = _date_arg(args.today, "--today", date.today())
    end = _date_arg(args.to_day, "--to", today - timedelta(days=1))
    start = _date_arg(args.from_day, "--from", end - timedelta(days=27))
    if start > end or end >= today:
        print("要求 --from <= --to < --today", file=sys.stderr)
        return 3
    output = _output_dir(workspace, args.out)

    plans, queue, route = _load_state(workspace)
    availability_source = availability_source_for_workspace(workspace)
    availability = None if availability_source is None else availability_source.availability
    timetable = timetable_for_workspace(workspace)
    pacing = settings_for_workspace(workspace)
    references = {}
    current = start
    while current <= end:
        references[current] = resolve_day_budget(
            current, config, availability, route, timetable, pacing_initial=pacing,
        ).total_minutes
        current += timedelta(days=1)
    profiles = workspace.subject_profiles
    subjects = tuple(subject.subject_id for subject in config.active_subjects())
    trees = {}
    for subject_id in subjects:
        trees[subject_id] = (
            None if subject_id not in workspace.knowledge_trees else
            load_knowledge_points(workspace.require(
                f"reference.knowledge_trees.{subject_id}"
            ))
        )
    subject_names = {subject_id: profiles[subject_id].name for subject_id in subjects}
    tree_grammars = {
        subject_id: profiles[subject_id].tree_grammar for subject_id in subjects
        if profiles[subject_id].tree_grammar is not None
    }
    data = progress_chart_data(
        start=start, end=end, today=today, config=config, reference_minutes=references,
        plans=plans.plans, completions=plans.completions, queue_items=queue.items,
        knowledge_trees=trees, tree_grammars=tree_grammars,
        subject_names=subject_names, route=route,
    )
    filename = f"progress--{start.isoformat()}--{end.isoformat()}.html"
    return _write_page(output, filename, render_progress(data, subjects, subject_names), args.open)


def _topic_weights(workspace, subjects: tuple[str, ...]) -> Mapping[str, Mapping[str, float]]:
    path = workspace.require("reference.topic_weights")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("invalid topic-weight document", "reference.topic_weights") from exc
    if not isinstance(document, Mapping):
        raise ContractError("expected an object", "reference.topic_weights")
    topics = document.get("topic_weight")
    if not isinstance(topics, Mapping):
        raise ContractError("missing topic_weight object", "reference.topic_weights.topic_weight")
    result = {}
    for subject in subjects:
        values = topics.get(subject)
        if not isinstance(values, Mapping):
            raise ContractError(
                "weighted mastery requires subject weights",
                f"reference.topic_weights.topic_weight.{subject}",
            )
        result[subject] = values
    return result


def _ability(args) -> int:
    workspace = load_workspace(args.workspace)
    config = _config(workspace, args.config)
    today = _date_arg(args.today, "--today", date.today())
    output = _output_dir(workspace, args.out)
    queue = ReviewShardStore(workspace.review_queue).read_state_sources()
    plans = DayPlanStore(workspace.plans).read_state_sources()
    past_question_passed = {
        review.review_id
        for event in plans.completions
        for review in event.reviews
        if review.check == "past_question" and review.outcome == "correct"
    }
    route = None
    if workspace.routes is not None:
        route = RoutePlanStore(workspace.routes).read_state_sources().route

    subjects = tuple(subject.subject_id for subject in config.active_subjects())
    profiles = workspace.subject_profiles
    names = {subject: profiles[subject].name for subject in subjects}
    weighted_subjects = tuple(
        subject for subject in subjects
        if "weighted_mastery" in profiles[subject].features
    )
    weights = _topic_weights(workspace, weighted_subjects) if weighted_subjects else {}
    points_by_subject = {}
    grammars = {}
    masteries = {}
    for subject in subjects:
        points = (
            None if subject not in workspace.knowledge_trees else
            load_knowledge_points(workspace.require(f"reference.knowledge_trees.{subject}"))
        )
        points_by_subject[subject] = points
        grammar = profiles[subject].tree_grammar
        if points is None:
            masteries[subject] = None
            continue
        if grammar is None:
            raise ContractError("knowledge tree requires tree_grammar",
                                f"subjects.{subject}.tree_grammar")
        grammars[subject] = grammar
        masteries[subject] = subject_mastery(
            subject, points, grammar, queue.items,
            weights[subject] if subject in weighted_subjects else None,
            past_question_passed,
        )
    gap_rows = [
        {"subject_id": subject,
         "covered": None if masteries[subject] is None else masteries[subject]["covered"],
         "ability": None if masteries[subject] is None else masteries[subject]["ability"]}
        for subject in subjects
    ]
    gap = mastery_gap(gap_rows, today, route)
    data = ability_chart_data(
        today=today, subjects=subjects, subject_names=names, masteries=masteries,
        gap=gap, knowledge_trees=points_by_subject, tree_grammars=grammars,
        weighted_subjects=weighted_subjects,
    )
    filename = f"ability--{today.isoformat()}.html"
    return _write_page(output, filename, render_ability(data), args.open)


def chart_main(argv: list[str]) -> int:
    """Run the week or progress chart command with contract/usage exit codes."""
    if not argv or argv[0] not in {"week", "progress", "ability"}:
        print("usage: py -3.12 -m ky chart {week|progress|ability}", file=sys.stderr)
        return 3
    action = argv[0]
    try:
        args = _parser(action).parse_args(argv[1:])
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    try:
        if action == "week":
            return _week(args)
        if action == "progress":
            return _progress(args)
        return _ability(args)
    except (ContractError, StorageError, CompletionError, RoutePlanError,
            KnowledgePointError, OSError, ValueError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
