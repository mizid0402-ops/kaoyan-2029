"""M14 CLI; route commands implement ``contracts/route_plan.md`` (D10 timeline display).

Public interfaces include :func:`main`, :func:`day_plan_main`, :func:`route_main`, and
:func:`timetable_main` (M18 CLI in ``contracts/timetable.md`` §8).

Read-only preflight: validate contracts and clip one day's reviews.

This command intentionally performs **no writes**. It exists to prove the
contract and the clipping algorithm before anything is allowed to touch real
study state.

Usage:

    py -m ky preflight --config <config.yaml> --items <flat-yaml|shard-dir|\
manifest.yaml> --date 2026-09-12

Exit codes:

    0  contracts valid and the day clipped successfully
    1  unexpected internal error (should never happen for contract-valid
       config + items; see the ValueError handler in main())
    2  contract violation (the message carries the exact field path)
    3  usage error
"""

from __future__ import annotations

import argparse
from itertools import combinations
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from ky.ledger import (
    LEDGER_SUBJECT_CATEGORIES,
    LedgerError,
    evidence_capable_materials,
    integrity_report,
    ledger_summary,
    load_ledger,
    structurable_materials,
)
from ky.availability import availability_for_workspace
from ky.freeze import (
    FreezePolicy, FreezeStatus, assess_freeze, latch_active, unresolved_freezes,
)
from ky.freeze.resume import plan_resume, resume_plan_to_mapping
from ky.planner.port import (
    apply_human_plan,
    apply_human_route_plan,
    apply_staged_proposal,
    apply_staged_route_proposal,
    create_planner_input,
    create_route_planner_input,
    reject_staging_plan_path,
)
from ky.models import (
    ContractError,
    KaoyanConfig,
    ReviewItem,
    load_config,
    validate_items_against_config,
)
from ky.knowledge import KnowledgePointError
from ky.knowledge.knowledge_point import load_knowledge_points
from ky.knowledge.syllabus_mapping import load_syllabus_mapping
from ky.review.syllabus_migration import (
    MigrationPlan,
    check_queue_references,
    plan_queue_migration,
    resolve_mapping_chain,
)
from ky.workspace import WORKSPACE_ENV, Workspace, find_workspace, load_workspace
from ky.review.check_questions import candidate_check_questions
from ky.schedule.budget import (
    allocate_new_content,
    daily_base_minutes,
    resolve_day_budget,
)
from ky.schedule.completion import (
    CompletionError,
    create_review_algorithm,
    parse_completion_event,
)
from ky.schedule.monthly_close import close_month
from ky.schedule.planning import RoutePlan, RoutePlanError, route_plan_to_mapping
from ky.schedule.review_clip import ReviewPolicy, preflight_to_mapping, select_daily_reviews
from ky.schedule.state_snapshot import build_snapshot, snapshot_to_mapping
from ky.storage.day_plan_store import (
    DayPlanStore,
    StorageError,
    advance_review_queue,
    preflight_review_queue,
)
from ky.storage.review_shards import ReviewShardStore, load_review_queue
from ky.storage.route_store import RoutePlanStore
from ky.timetable import load_school, timetable_for_workspace
from ky.timetable_io.zfsoft_pdf import import_zfsoft_pdf
from ky.timetable_io import apply_staging, inspect_isolation, restage
from ky.timetable_io import export_ics, import_ics
from ky.pacing.cli import pacing_main
from ky.pacing.port import settings_for_workspace, cycle_for_date
from ky.pacing.storage import report_path as pacing_report_path, read_report as read_pacing_report
from ky.pacing.input import create_pacing_input
from ky.charts.cli import chart_main
from ky.question_bank import (
    adapted_question_group_all_retired,
    create_adapted_question_input,
    load_question_bank,
    question_id_from_ref,
    question_ref,
    retire_question,
    select_adapted_question,
    submit_staged_question,
)
from ky.mastery import item_level
from ky.knowledge import learnable_tree, load_knowledge_points
from ky.review_intake import DEFAULT_REVIEW_MINUTES, new_review_items
from ky.today.compute import build_review_questions, calculate_preflight
from ky.today.record import (
    RecordPipelineError, advance_loaded_event, latch_freeze_if_needed, record_loaded_event,
    record_report_mapping,
)

__all__ = [
    "build_parser",
    "main",
    "ledger_main",
    "snapshot_main",
    "day_plan_main",
    "planner_input_main",
    "month_close_main",
    "route_main",
    "timetable_main",
]


class _CliExit(Exception):
    """Carry an existing CLI exit code through named processing steps."""

    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code


def _load_workspace_for_default(workspace_arg: str | None, alternative: str) -> Workspace:
    """Load the registry for a CLI data source that has no explicit override."""
    try:
        return load_workspace(workspace_arg)
    except ContractError as exc:
        if workspace_arg is not None:
            raise
        raise ContractError(f"{exc}; add {alternative} or --workspace", "--workspace") from exc


def _discovered_workspace(workspace_arg: str | None) -> Workspace | None:
    """Load the registry if one is named or discoverable; ``None`` only when none exists.

    Used where the registry is optional (--plan staging check, availability): a registry that
    is found but invalid still fails closed (sol round 102, B2).
    """
    try:
        registry_path = find_workspace(explicit=workspace_arg)
    except ContractError:
        if workspace_arg is not None or os.environ.get(WORKSPACE_ENV):
            raise
        return None
    return load_workspace(registry_path)


def _optional_workspace(workspace_arg: str | None) -> tuple[Workspace | None, str | None, bool]:
    """Resolve an optional registry once, as ``(workspace, error, not_found)``.

    ``find_workspace`` failing means no registry exists; ``load_workspace`` failing means one
    exists but is invalid. Callers branch on that flag, never on error text (AGENTS.md defect 3).
    """
    try:
        registry_path = find_workspace(explicit=workspace_arg)
    except ContractError as exc:
        return None, str(exc), True
    try:
        return load_workspace(registry_path), None, False
    except ContractError as exc:
        return None, str(exc), False


def _freeze_status_for_workspace(
    day: date, config: KaoyanConfig, workspace: Workspace,
    queue: tuple[ReviewItem, ...] | None = None,
) -> FreezeStatus:
    """Derive M27 status from the registered queue and append-only M13 records."""
    queue_store = ReviewShardStore(workspace.write_target("state.review_queue"))
    if queue is None:
        queue = queue_store.load() if queue_store.manifest_path.exists() else ()
    plans_store = DayPlanStore(workspace.write_target("state.plans"))
    latched = latch_active(plans_store.freeze_events())
    return assess_freeze(day, config, queue, FreezePolicy(), latched=latched)


def _freeze_submission_if_needed(day: date, config: KaoyanConfig, workspace: Workspace) -> None:
    """Reject an already frozen submission after persisting a new latch when needed."""
    if latch_freeze_if_needed(workspace, day, config)[0].frozen:
        raise StorageError("已冻结，请先运行 ky resume")


def _plans_store_path(args: argparse.Namespace) -> Path:
    """``--store`` if given, else the registry's ``state.plans`` write target (WP-E1)."""
    if args.store is not None:
        return Path(args.store)
    return _load_workspace_for_default(args.workspace, "--store").write_target("state.plans")


def _routes_store_path(args: argparse.Namespace) -> Path:
    """Resolve an explicit route store or the registered ``state.routes`` target."""
    if args.store is not None:
        return Path(args.store)
    workspace = _load_workspace_for_default(args.workspace, "--store")
    try:
        return workspace.write_target("state.routes")
    except ContractError as exc:
        raise ContractError(f"{exc}; add --store or register state.routes", "state.routes") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="py -m ky preflight",
        description=(
            "Validate the kaoyan exam configuration and review queue, then compute "
            "one day's review selection. Writes nothing."
        ),
    )
    parser.add_argument("--config", required=True, help="path to kaoyan_config.yaml")
    parser.add_argument(
        "--items", default=None,
        help="flat review-items YAML file, review-shard directory, or shard manifest.yaml",
    )
    parser.add_argument("--workspace", default=None, help="workspace registry (otherwise discover)")
    parser.add_argument(
        "--date",
        default=None,
        help="the day to plan for, ISO YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--usage",
        default=None,
        help="optional JSON file mapping subject_id -> minutes studied in the last 7 days",
    )
    parser.add_argument(
        "--urgent-overdue-days",
        type=int,
        default=3,
        help="an item this many days overdue may borrow up to the hard cap (default: 3)",
    )
    parser.add_argument(
        "--urgent-defer-count",
        type=int,
        default=2,
        help="an item deferred this many times may borrow up to the hard cap (default: 2)",
    )
    parser.add_argument(
        "--freeze-backlog-days",
        type=int,
        default=3,
        help=(
            "freeze when overdue queued or scheduled reviews reach this many "
            "configured review-cap days"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of the human summary",
    )
    return parser


def _preflight_main(args_in: list[str]) -> int:
    args = build_parser().parse_args(args_in)
    today = _preflight_parse_date(args)
    if today is None:
        return 3
    usage = _preflight_read_usage(args)
    if usage is None:
        return 3
    try:
        (
            config, items, workspace, route, timetable, day_budget, pacing_settings,
        ) = _preflight_load_context(args, today)
    except (ContractError, StorageError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    try:
        policy, freeze_policy = _preflight_policies(args)
    except ValueError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 3
    freeze = _preflight_freeze(today, config, items, workspace, freeze_policy)
    try:
        result, allocations, payload = calculate_preflight(
            config, items, today, usage, policy, freeze, day_budget,
        )
    except ContractError as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        # A contract-valid config plus contract-valid items should never
        # reach this: validate_config's floor-vs-hard-cap check (see
        # ky/models.py) guarantees floor_total <= new_content_minutes for
        # every review outcome up to the hard cap. Surface any residual
        # bug as a controlled failure instead of a raw traceback.
        print(f"internal error: {exc}", file=sys.stderr)
        return 1
    try:
        reminder = _pacing_reminder(workspace, pacing_settings, today)
    except (ContractError, StorageError, OSError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        if reminder:
            print(reminder, file=sys.stderr)
        return 0
    _preflight_print_summary(config, result, freeze, day_budget, route, timetable)
    _preflight_print_review_lists(result, freeze)
    _preflight_print_allocations(result, allocations)
    if reminder:
        print(reminder)
    return 0


def _preflight_parse_date(args: argparse.Namespace) -> date | None:
    if not args.date:
        return date.today()
    try:
        return date.fromisoformat(args.date)
    except ValueError:
        print(f"--date must be an ISO date (YYYY-MM-DD), got {args.date!r}", file=sys.stderr)
        return None


def _preflight_read_usage(args: argparse.Namespace) -> dict[str, int] | None:
    usage: dict[str, int] = {}
    if not args.usage:
        return usage
    usage_path = Path(args.usage)
    try:
        raw_usage = json.loads(usage_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"--usage file does not exist: {usage_path}", file=sys.stderr)
        return None
    except json.JSONDecodeError as exc:
        print(f"--usage file is not valid JSON: {exc}", file=sys.stderr)
        return None
    if not isinstance(raw_usage, dict):
        print("--usage JSON must be an object mapping subject_id to minutes", file=sys.stderr)
        return None
    for key, value in raw_usage.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            print(f"--usage[{key!r}] must be a non-negative integer", file=sys.stderr)
            return None
    return dict(raw_usage)


def _preflight_load_context(
    args: argparse.Namespace, today: date, *, workspace_override: Workspace | None = None,
):
    config = load_config(args.config)
    workspace: Workspace | None = workspace_override
    items_path = args.items
    if items_path is None:
        if workspace is None:
            workspace = _load_workspace_for_default(args.workspace, "--items")
        items_path = workspace.write_target("state.review_queue")
    items = load_review_queue(items_path)
    validate_items_against_config(config, items)
    if workspace is None:
        workspace = _discovered_workspace(args.workspace)
    availability = availability_for_workspace(workspace) if workspace is not None else None
    timetable = timetable_for_workspace(workspace) if workspace is not None else None
    route_store = (
        RoutePlanStore(workspace.write_target("state.routes"))
        if workspace is not None and workspace.routes is not None else None
    )
    route = route_store.current() if route_store is not None else None
    pacing_settings = settings_for_workspace(workspace) if workspace is not None else None
    day_budget = resolve_day_budget(
        today, config, availability, route, timetable, pacing_initial=pacing_settings,
    )
    return config, items, workspace, route, timetable, day_budget, pacing_settings


def _pacing_reminder(workspace, settings, today: date) -> str | None:
    if workspace is None or settings is None:
        return None
    current = cycle_for_date(settings, today)
    if current is None:
        return None
    cursor = settings.start
    while cursor < current.start:
        cycle = cycle_for_date(settings, cursor)
        if cycle is None:
            return None
        if cycle.end < today:
            path = pacing_report_path(workspace.plans, cycle.end.isoformat())
            if not path.exists():
                return (
                    f"复盘提醒：周期 {cycle.start.isoformat()} 至 "
                    f"{cycle.end.isoformat()} 尚无报告；请运行 "
                    f"ky pacing report --cycle-end {cycle.end.isoformat()}"
                )
            read_pacing_report(path)
        cursor = cycle.end_exclusive
    return None


def _preflight_policies(args: argparse.Namespace) -> tuple[ReviewPolicy, FreezePolicy]:
    policy = ReviewPolicy(
        urgent_overdue_days=args.urgent_overdue_days,
        urgent_defer_count=args.urgent_defer_count,
    )
    freeze_policy = FreezePolicy(backlog_days=args.freeze_backlog_days)
    return policy, freeze_policy


def _preflight_freeze(
    today: date, config: KaoyanConfig, items: tuple, workspace: Workspace | None,
    freeze_policy: FreezePolicy,
) -> FreezeStatus:
    latched = False
    if workspace is not None:
        plans_store = DayPlanStore(workspace.write_target("state.plans"))
        latched = latch_active(plans_store.freeze_events())
    return assess_freeze(today, config, items, freeze_policy, latched=latched)


def _preflight_calculate(
    config: KaoyanConfig, items: tuple, today: date, usage: dict[str, int],
    policy: ReviewPolicy, freeze: FreezeStatus, day_budget,
):
    result, allocations, _ = calculate_preflight(
        config, items, today, usage, policy, freeze, day_budget,
    )
    return result, allocations


def _preflight_print_summary(
    config, result, freeze, day_budget, route, timetable
) -> None:
    print(f"project            : {config.project_id}")
    if freeze.frozen:
        print(
            f"FROZEN             : 积压 {freeze.overdue_minutes} 分钟 ≥ "
            f"{freeze.backlog_days} 天复习上限 {freeze.threshold_minutes} 分钟；"
            "今天不排任务，准备好后运行 ky resume"
        )
    overdue_scheduled = [
        item for item in result.unreachable
        if item.state == "scheduled" and item.due_date < result.today
    ]
    if freeze.overdue_count and overdue_scheduled:
        minutes = sum(item.estimated_minutes for item in overdue_scheduled)
        print(
            f"其中 {len(overdue_scheduled)} 项（{minutes} 分钟）为已过期的 scheduled "
            "（M9 列为 unreachable），已计入冻结积压；"
            "deferred -> backlog 一行只计本次裁剪延期。"
        )
    print(f"date               : {result.today.isoformat()}")
    print(f"daily budget       : {day_budget.total_minutes} min")
    if day_budget.total_source == "timetable":
        _preflight_print_timetable(result.today, day_budget.base_minutes, timetable)
    # With phase quotas the soft figure is their sum, not the configured ratio (sol round 114).
    soft_source = (
        "timeline quotas" if day_budget.subject_review_quotas is not None
        else f"ratio {config.review_reserve_ratio}"
    )
    if freeze.frozen:
        print("review soft / hard : 冻结期间不生效")
    else:
        print(
            f"review soft / hard : {result.soft_target_minutes} / {result.hard_cap_minutes} min "
            f"({soft_source} / {config.hard_max_ratio})"
        )
    if not freeze.frozen and day_budget.subject_review_quotas is not None:
        phase = next(
            phase for phase in route.phases if phase.index == day_budget.phase_index
        )
        quotas = " ".join(
            f"{subject_id}={minutes}"
            for subject_id, minutes in sorted(day_budget.subject_review_quotas.items())
        )
        print(f"timeline phase     : {phase.index} {phase.label} ({quotas})")
    print()


def _preflight_print_timetable(day, base_minutes: int, timetable) -> None:
    schedule = timetable.day(day, base_minutes)
    weekday = schedule.weekday_used or day.isoweekday()
    weekday_name = "一二三四五六日"[weekday - 1]
    detail = (
        f"timetable          : {schedule.semester} 第 {schedule.week} 周 星期{weekday_name}"
    )
    if schedule.followed is not None:
        detail += f"（按 {schedule.followed.isoformat()} 的课）"
    detail += f"；大节 {schedule.blocks}；空闲 {schedule.free_minutes} 分钟"
    if schedule.unconfirmed_periods:
        periods = ",".join(map(str, schedule.unconfirmed_periods))
        detail += f"；含待确认节次 {periods}"
    print(detail)


def _preflight_print_review_lists(result, freeze: FreezeStatus) -> None:
    due_count = len(result.selected) + len(result.deferred) + len(result.unschedulable)
    print(f"due items          : {due_count}")
    print(f"selected           : {len(result.selected)}  -> {result.review_minutes} min")
    for item in result.selected:
        print(
            f"  - {item.review_id:<24} {item.subject_id:<10} {item.estimated_minutes:>2} min  "
            f"overdue {item.overdue_days(result.today):>3}d  defers {item.defer_count}"
        )
    print(f"deferred           : {len(result.deferred)}  -> backlog {result.backlog_minutes} min")
    for item in result.deferred:
        print(
            f"  - {item.review_id:<24} {item.subject_id:<10} {item.estimated_minutes:>2} min  "
            f"overdue {item.overdue_days(result.today):>3}d  defers {item.defer_count} "
            f"(was {item.defer_count - 1})"
        )
    if result.unschedulable:
        print(
            f"unschedulable      : {len(result.unschedulable)} "
            "(single pass exceeds the hard cap)"
        )
        for item in result.unschedulable:
            print(f"  - {item.review_id:<24} {item.estimated_minutes:>2} min -- split this item")
    if result.scheduled_ahead:
        # Not owed yet, so it consumes no budget -- but it must be visible, or
        # a planned item looks like a missing one.
        print(
            f"scheduled ahead    : {len(result.scheduled_ahead)} "
            "(planned, not due; consumes no budget)"
        )
        for item in result.scheduled_ahead:
            print(f"  - {item.review_id:<24} due {item.due_date.isoformat()}")
    if result.unreachable:
        # M9 does not select these states; expired scheduled work still counts for M27.
        print(
            f"UNREACHABLE        : {len(result.unreachable)} "
            "(state makes them unselectable -- fix the state)"
        )
        for item in result.unreachable:
            print(
                f"  - {item.review_id:<24} state={item.state} due {item.due_date.isoformat()} "
                f"overdue {item.overdue_days(result.today)}d"
            )
    print()


def _preflight_print_allocations(result, allocations) -> None:
    print(f"new content budget : {result.new_learning_minutes} min")
    for allocation in allocations:
        print(
            f"  - {allocation.display_name:<10} {allocation.minutes:>3} min "
            f"(weight {allocation.weight:.2f})"
        )
    print()
    print(f"over capacity      : {'YES' if result.over_capacity else 'no'}")


def _resume_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py -m ky resume")
    parser.add_argument("--date", required=True, help="resume day, ISO YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--config", default=None)
    parser.add_argument("--workspace", default=None)
    return parser


def _learn_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py -m ky learn")
    parser.add_argument("--date", required=True, help="day learning was completed, ISO YYYY-MM-DD")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--knowledge-point", action="append", dest="knowledge_point_ids")
    selection.add_argument("--leaves-under")
    parser.add_argument("--minutes", type=int, default=DEFAULT_REVIEW_MINUTES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workspace", default=None)
    return parser


def learn_main(argv: list[str]) -> int:
    parser = _learn_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code)
    day = _parse_iso_date(args.date, "--date")
    if day is None:
        return 3
    requested_ids = args.knowledge_point_ids
    if requested_ids is not None and len(requested_ids) != len(set(requested_ids)):
        print("usage error: duplicate --knowledge-point ID", file=sys.stderr)
        return 3

    try:
        workspace = load_workspace(args.workspace)
        config = load_config(workspace.require("settings.exam_config"))
        queue_store = ReviewShardStore(workspace.write_target("state.review_queue"))
        existing_items = queue_store.read_state_sources().items
        subject_ids = (
            {args.leaves_under.split(".", 1)[0]}
            if args.leaves_under is not None
            else {point_id.split(".", 1)[0] for point_id in requested_ids}
        )
        active_subjects = {
            subject.subject_id for subject in config.active_subjects()
        }
        added: list[ReviewItem] = []
        skipped: list[tuple[str, str]] = []
        for subject_id in sorted(subject_ids):
            if subject_id not in workspace.knowledge_trees:
                raise ContractError(
                    "knowledge tree is not registered",
                    f"reference.knowledge_trees.{subject_id}",
                )
            if subject_id not in active_subjects:
                raise ContractError("subject is not active in the exam", subject_id)
            profile = workspace.subject_profiles.get(subject_id)
            if profile is None or profile.tree_grammar is None:
                raise ContractError("tree grammar is not registered", f"subjects.{subject_id}")
            points = load_knowledge_points(
                workspace.require(f"reference.knowledge_trees.{subject_id}")
            )
            new_items, skipped_items = new_review_items(
                points,
                profile.tree_grammar,
                (*existing_items, *added),
                knowledge_point_ids=(
                    tuple(point_id for point_id in requested_ids
                          if point_id.split(".", 1)[0] == subject_id)
                    if requested_ids is not None else None
                ),
                leaves_under=args.leaves_under,
                day=day,
                minutes=args.minutes,
            )
            if args.leaves_under is not None and not new_items:
                _print_learn_result((), skipped_items)
                raise ContractError("no learnable leaves can be added", args.leaves_under)
            added.extend(new_items)
            skipped.extend(skipped_items)
        if args.dry_run:
            _print_learn_result(added, skipped)
            return 0
        queue_store.write((*existing_items, *added))
    except (ContractError, KnowledgePointError, StorageError, OSError, ValueError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    _print_learn_result(added, skipped)
    return 0


def _print_learn_result(items: tuple[ReviewItem, ...] | list[ReviewItem], skipped) -> None:
    for point_id, review_id in skipped:
        print(f"已在复习队列，跳过 {point_id}（{review_id}）")
    for item in items:
        print(f"{item.review_id} {item.title} first_review={item.due_date.isoformat()}")


def _resume_context(args, day):
    workspace = _load_workspace_for_default(args.workspace, "--workspace")
    config_path = (
        Path(args.config) if args.config is not None
        else workspace.require("settings.exam_config")
    )
    config = load_config(config_path)
    queue_store = ReviewShardStore(workspace.write_target("state.review_queue"))
    items = queue_store.load() if queue_store.manifest_path.exists() else ()
    validate_items_against_config(config, items)
    availability = availability_for_workspace(workspace)
    timetable = timetable_for_workspace(workspace)
    route_store = (
        RoutePlanStore(workspace.write_target("state.routes"))
        if workspace.routes is not None else None
    )
    route = route_store.current() if route_store is not None else None
    pacing_settings = settings_for_workspace(workspace)
    plan = plan_resume(
        day,
        config,
        items,
        availability=availability,
        route=route,
        timetable=timetable,
        pacing_initial=pacing_settings,
    )
    mapping = resume_plan_to_mapping(plan)
    plans_store = DayPlanStore(workspace.write_target("state.plans"))
    unresolved = unresolved_freezes(plans_store.freeze_events())
    latest_freeze = max((event.day for event in unresolved), default=None)
    if latest_freeze is not None and latest_freeze > day:
        # Refuse back-filled dates before any write; they cannot clear a later latch (sol 125).
        raise StorageError(
            f"冻结发生在 {latest_freeze.isoformat()}，恢复日期不能早于它；"
            f"请用 --date {latest_freeze.isoformat()} 或更晚"
        )
    return queue_store, plans_store, plan, mapping, bool(unresolved)


def _resume_without_backlog(args, plans_store, day, mapping, latched) -> int:
    if latched and not args.dry_run:
        plans_store.write_resume_record(day, mapping)
        message = "积压已清空，已解除冻结"
    elif latched:
        message = "积压已清空；正式执行将解除冻结"
    else:
        message = "没有需要重排的积压"
    if args.json:
        print(json.dumps(mapping, ensure_ascii=False, indent=2))
    else:
        print(message)
    return 0


def _resume_write_plan(args, queue_store, plans_store, day, plan, mapping) -> None:
    if not args.dry_run:
        queue_store.write(plan.updated_items)
        plans_store.write_resume_record(day, mapping)


def _resume_print_plan(args, mapping) -> None:
    if args.json:
        print(json.dumps(mapping, ensure_ascii=False, indent=2))
    else:
        _print_resume_plan(mapping, dry_run=args.dry_run)


def _print_scheduled_conversion(mapping: dict[str, object], *, dry_run: bool) -> None:
    converted = mapping.get("scheduled_to_queued_count", 0)
    if converted:
        action = "将由" if dry_run else "已由"
        print(f"其中 {converted} 项{action} scheduled 转为 queued")


def resume_main(argv: list[str]) -> int:
    """Replan the registered overdue review queue and append its resume record (D11)."""
    _reconfigure_streams_utf8()
    try:
        args = _resume_parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    day = _parse_iso_date(args.date, "--date")
    if day is None:
        return 3

    try:
        queue_store, plans_store, plan, mapping, latched = _resume_context(args, day)
        if not plan.entries:
            # Empty backlog needs only its resume record to clear an existing latch (D11).
            return _resume_without_backlog(args, plans_store, day, mapping, latched)
        _resume_write_plan(args, queue_store, plans_store, day, plan, mapping)
    except (ContractError, StorageError, OSError, ValueError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2

    _resume_print_plan(args, mapping)
    if not args.json:
        _print_scheduled_conversion(mapping, dry_run=args.dry_run)
    return 0


def _print_resume_plan(mapping: dict[str, object], *, dry_run: bool) -> None:
    action = "重排预览" if dry_run else "重排完成"
    print(f"{action}：{mapping['day']}")
    print(f"可能遗忘：{mapping['possible_forgetting_count']} 项")
    print(f"逾期不久：{mapping['recent_overdue_count']} 项")
    print(f"最后分配日：{mapping['last_assigned_day'] or '无'}")
    unschedulable = mapping["unschedulable_review_ids"]
    print(f"放不下：{', '.join(unschedulable) if unschedulable else '无'}")


def _ledger_sources(args: argparse.Namespace) -> tuple[Path, Path, frozenset[str]]:
    """Resolve the ledger path, the root for embedded paths, and the allowed subject ids.

    Standalone mode with explicit subjects needs no registry. The legacy ``--ledger`` plus
    ``--root`` form discovers subjects from cwd, then from the ledger directory (section 3.2).
    Other registry paths use ``require`` and embedded paths resolve against ``Workspace.root``
    unless ``--root`` overrides it (sections 2.3 and 3.2).
    """
    categories = LEDGER_SUBJECT_CATEGORIES
    if args.ledger and args.root and args.subjects and not args.workspace:
        subjects = frozenset(s.strip() for s in args.subjects.split(",") if s.strip())
        return Path(args.ledger), Path(args.root), subjects | categories
    if args.ledger and args.root and not args.subjects and not args.workspace:
        try:
            registry = find_workspace(start=Path.cwd())
        except ContractError:
            try:
                registry = find_workspace(start=Path(args.ledger).absolute().parent)
            except ContractError as exc:
                # Keep the discovery error: it names the source that failed, e.g. a
                # KY_WORKSPACE pointing at a missing file (sol round 60, L1 suggestion).
                raise ContractError(
                    f"workspace registry not found ({exc}); add --subjects or --workspace"
                ) from exc
        workspace = load_workspace(registry)
        return Path(args.ledger), Path(args.root), frozenset(workspace.subjects) | categories
    workspace = load_workspace(args.workspace)
    ledger_path = Path(args.ledger) if args.ledger else workspace.require("reference.ledger")
    root = Path(args.root) if args.root else workspace.root
    if args.subjects:
        subjects = frozenset(s.strip() for s in args.subjects.split(",") if s.strip())
    else:
        subjects = frozenset(workspace.subjects)
    return ledger_path, root, subjects | categories


def _ledger_reconfigure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _ledger_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="py -m ky ledger",
        description=(
            "Report the material ledger: provenance, rights posture, byte integrity, "
            "and which materials may authorise derived claims. Writes nothing."
        ),
    )
    parser.add_argument("--ledger", default=None, help="path to the material ledger YAML")
    parser.add_argument(
        "--workspace",
        default=None,
        help="workspace registry (otherwise discover)",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="root used to resolve relative storage paths for integrity checks "
        "(default: the workspace root)",
    )
    parser.add_argument(
        "--subject",
        default=None,
        help="only report materials covering this subject id (e.g. cs408)",
    )
    parser.add_argument(
        "--subjects",
        default=None,
        help="comma-separated exam subject ids; with --ledger and --root this runs without "
        "a workspace registry",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def _ledger_load_materials(args):
    ledger_path, root, subject_ids = _ledger_sources(args)
    materials = load_ledger(ledger_path, subject_ids=subject_ids)
    return ledger_path, root, materials


def _ledger_measure(materials, root):
    integrity = dict(integrity_report(materials, root=root))
    structurable = {m.resource_id for m in structurable_materials(materials)}
    evidence_capable = {m.resource_id for m in evidence_capable_materials(materials)}
    summary = ledger_summary(materials)
    return integrity, structurable, evidence_capable, summary


def _ledger_print_json(ledger_path, root, materials, integrity, summary) -> None:
    payload = {
        "ledger": ledger_path.as_posix(),
        "root": root.as_posix(),
        "summary": summary,
        "materials": [
            {
                "resource_id": m.resource_id,
                "title": m.title,
                "material_kind": m.material_kind,
                "subjects": list(m.subjects),
                "acquisition": m.acquisition,
                "rights_status": m.rights.status,
                "rights_clear": m.rights.is_clear(),
                "storage_mode": m.storage.mode,
                "review_status": m.review_status,
                "bytes_verified": integrity.get(m.resource_id, False),
                "can_back_evidence": m.can_back_evidence(),
                "may_be_structured": m.may_be_structured(),
                "source_url": m.provenance.source_url,
                "publisher": m.provenance.publisher,
            }
            for m in materials
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _ledger_print_header(ledger_path, root, summary) -> None:
    print(f"ledger             : {ledger_path.as_posix()}")
    print(f"integrity root     : {root.as_posix()}")
    print(f"materials          : {summary['total']}")
    print(f"  by kind          : {summary['by_kind']}")
    print(f"  by rights        : {summary['by_rights_status']}")
    print(f"  by review        : {summary['by_review_status']}")
    print()


def _ledger_print_rights_and_capabilities(summary, structurable, evidence_capable) -> None:
    print(f"rights unclear     : {len(summary['unclear_rights'])}")
    for resource_id in summary["unclear_rights"]:
        print(f"  - {resource_id}")
    print(f"may be structured  : {len(structurable)}")
    for resource_id in summary["structurable"]:
        print(f"  - {resource_id}")
    print(f"can back evidence  : {len(evidence_capable)}")
    for resource_id in summary["evidence_capable"]:
        print(f"  - {resource_id}")
    print()


def _ledger_print_integrity(materials, integrity) -> None:
    checked = [m for m in materials if m.storage.mode == "local_file"]
    if checked:
        count = sum(1 for m in checked if integrity.get(m.resource_id))
        print(f"byte integrity     : {count}/{len(checked)} verified")
        for material in checked:
            state = "ok" if integrity.get(material.resource_id) else "MISMATCH or MISSING"
            print(f"  - {material.resource_id:<40} {state}")
    else:
        print("byte integrity     : no locally stored materials to check")


def ledger_main(argv: list[str]) -> int:
    """Read-only view of the material ledger.

    Exit codes match the rest of the CLI: 0 = reported, 2 = ledger invalid.

    This command never writes. Mutating the ledger is a deliberate, audited act
    and does not belong behind a status command.
    """
    _ledger_reconfigure_utf8()
    args = _ledger_parser().parse_args(argv)

    try:
        ledger_path, root, materials = _ledger_load_materials(args)
    except (ContractError, LedgerError) as exc:
        print(f"ledger violation: {exc}", file=sys.stderr)
        return 2

    if args.subject:
        materials = tuple(m for m in materials if args.subject in m.subjects)

    integrity, structurable, evidence_capable, summary = _ledger_measure(materials, root)

    if args.json:
        _ledger_print_json(ledger_path, root, materials, integrity, summary)
        return 0

    _ledger_print_header(ledger_path, root, summary)
    _ledger_print_rights_and_capabilities(summary, structurable, evidence_capable)
    _ledger_print_integrity(materials, integrity)
    return 0


def _reconfigure_streams_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _parse_iso_date(value: str, flag: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        print(f"{flag} must be an ISO date (YYYY-MM-DD), got {value!r}", file=sys.stderr)
        return None


def _snapshot_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="py -m ky snapshot",
        description="Print today's read-only state snapshot. Writes nothing.",
    )
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--items", default=None,
        help="flat review-items YAML file, review-shard directory, or shard manifest.yaml",
    )
    parser.add_argument("--date", default=None, help="ISO date to snapshot as-of (default: today)")
    parser.add_argument("--target-exam-date", default=None, help="ISO date; enables days_to_exam")
    parser.add_argument(
        "--vocab-db", default=None, help="override path to the vocabulary sqlite db",
    )
    parser.add_argument(
        "--workspace", default=None,
        help="workspace registry path (default: discover)",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def _snapshot_parse_dates(args) -> tuple[date, date | None] | None:
    today = date.today()
    if args.date:
        parsed = _parse_iso_date(args.date, "--date")
        if parsed is None:
            return None
        today = parsed
    target_exam_date = None
    if args.target_exam_date:
        target_exam_date = _parse_iso_date(args.target_exam_date, "--target-exam-date")
        if target_exam_date is None:
            return None
    return today, target_exam_date


def _snapshot_items(args):
    workspace = (
        _load_workspace_for_default(args.workspace, "--items")
        if args.items is None
        else load_workspace(args.workspace)
    )
    items_path = (
        args.items if args.items is not None else workspace.write_target("state.review_queue")
    )
    items = load_review_queue(items_path)
    vocab_db = Path(args.vocab_db) if args.vocab_db else None
    return workspace, items, vocab_db


def _snapshot_print_text(snapshot) -> None:
    print(f"as of              : {snapshot.as_of.isoformat()}")
    days_to_exam = snapshot.days_to_exam if snapshot.days_to_exam is not None else "n/a"
    print(f"days to exam       : {days_to_exam}")
    print()
    for s in snapshot.subjects:
        tree_desc = (
            f"{s.tree_total.count} items (tree_status={s.tree_total.tree_status})"
            if s.tree_total is not None else "no committed tree"
        )
        print(f"{s.subject_id:<10} tree: {tree_desc}")
        print(
            f"{'':<10} queue {s.in_review_queue:>4}  due-today {s.due_today_count:>3} "
            f"({s.due_today_minutes} min)  backlog {s.backlog_minutes} min"
        )
    if snapshot.vocab is not None:
        print()
        print(f"vocab delivered    : {snapshot.vocab.delivered}")
        print(f"vocab remaining    : {snapshot.vocab.remaining}")


def snapshot_main(argv: list[str]) -> int:
    """``py -m ky snapshot``: read-only dashboard. Writes nothing.

    Usage: ``py -m ky snapshot --config <config.yaml> --items
    <flat-yaml|shard-dir|manifest.yaml> [--workspace <registry.yaml>]``.
    ``--items`` accepts a flat review-items YAML file, a review-shard directory,
    or its ``manifest.yaml`` file.

    Exit codes: 0 = printed, 2 = contract violation in --config/--items, 3 = usage error.
    """
    _reconfigure_streams_utf8()
    args = _snapshot_parser().parse_args(argv)
    parsed_dates = _snapshot_parse_dates(args)
    if parsed_dates is None:
        return 3
    today, target_exam_date = parsed_dates

    try:
        config = load_config(args.config)
        workspace, items, vocab_db = _snapshot_items(args)
        snapshot = build_snapshot(
            config,
            items,
            today=today,
            target_exam_date=target_exam_date,
            vocab_db=vocab_db,
            workspace=workspace,
        )
    except (ContractError, KnowledgePointError, CompletionError) as exc:
        # A registered tree, or a stored completion event, that fails its own contract is a
        # contract violation, not a crash (sol round 86, M2).
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2

    payload = snapshot_to_mapping(snapshot)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    _snapshot_print_text(snapshot)
    return 0


def planner_input_main(argv: list[str]) -> int:
    """Write one M19 planner input package; exit 2 on workspace or data violations."""
    _reconfigure_streams_utf8()
    parser = argparse.ArgumentParser(prog="py -m ky planner-input")
    parser.add_argument(
        "--kind", choices=("day", "route", "pacing", "adapted-questions"), default="day"
    )
    parser.add_argument("--knowledge-point", default=None)
    parser.add_argument("--date", help="planning day, ISO YYYY-MM-DD")
    parser.add_argument("--cycle-end", help="pacing report cycle end, ISO YYYY-MM-DD")
    parser.add_argument("--today", help="pacing input as-of day, ISO YYYY-MM-DD")
    parser.add_argument("--config", default=None, help="exam configuration (default: workspace)")
    parser.add_argument("--workspace", default=None, help="workspace registry (otherwise discover)")
    args = parser.parse_args(argv)
    if args.kind == "adapted-questions":
        if not args.knowledge_point:
            print("usage error: --knowledge-point is required", file=sys.stderr)
            return 3
        try:
            path, digest = create_adapted_question_input(
                args.knowledge_point, workspace_path=args.workspace,
            )
        except (ContractError, StorageError, OSError, ValueError) as exc:
            print(f"contract violation: {exc}", file=sys.stderr)
            return 2
        print(f"input: {path}")
        print(f"input_hash: {digest}")
        return 0
    if args.kind == "pacing":
        cycle_end = _parse_iso_date(args.cycle_end, "--cycle-end")
        if cycle_end is None:
            return 3
        today = _parse_iso_date(args.today, "--today") if args.today else date.today()
        if today is None:
            return 3
        try:
            path, digest = create_pacing_input(
                cycle_end, today, config_path=args.config, workspace_path=args.workspace,
            )
        except (ContractError, StorageError, OSError, ValueError) as exc:
            print(f"contract violation: {exc}", file=sys.stderr)
            return 2
        print(f"input: {path}")
        print(f"input_hash: {digest}")
        return 0
    if not args.date:
        print("usage error: --date is required", file=sys.stderr)
        return 3
    day = _parse_iso_date(args.date, "--date")
    if day is None:
        return 3
    try:
        create_input = create_route_planner_input if args.kind == "route" else create_planner_input
        path, digest = create_input(day, config_path=args.config, workspace_path=args.workspace)
    except (ContractError, KnowledgePointError, CompletionError, StorageError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    print(f"input: {path}")
    print(f"input_hash: {digest}")
    return 0


def question_bank_main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"submit", "retire"}:
        print("usage: py -m ky question-bank submit --from-staging FILE [--dry-run]",
              file=sys.stderr)
        return 3
    if argv[0] == "submit":
        parser = argparse.ArgumentParser(prog="py -m ky question-bank submit")
        parser.add_argument("--from-staging", required=True)
        parser.add_argument("--workspace", default=None)
        parser.add_argument("--dry-run", action="store_true")
        try:
            args = parser.parse_args(argv[1:])
        except SystemExit as exc:
            return 0 if exc.code == 0 else 3
        try:
            target, question = submit_staged_question(
                args.from_staging, dry_run=args.dry_run, workspace_path=args.workspace,
            )
        except (ContractError, StorageError, OSError, ValueError) as exc:
            print(f"contract violation: {exc}", file=sys.stderr)
            return 2
        if args.dry_run:
            print(f"valid: {question['id']}")
        else:
            print(f"question: {target}")
        return 0
    parser = argparse.ArgumentParser(prog="py -m ky question-bank retire")
    parser.add_argument("--question", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--dry-run", action="store_true")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    retired_on = _parse_iso_date(args.date, "--date")
    if retired_on is None:
        return 3
    if retired_on.isoformat() != args.date:
        print("--date must be an ISO date (YYYY-MM-DD)", file=sys.stderr)
        return 3
    try:
        workspace = load_workspace(args.workspace)
        target = retire_question(
            workspace.write_target("state.question_bank"), args.question, args.reason,
            retired_on, dry_run=args.dry_run,
        )
    except (ContractError, StorageError, OSError, ValueError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"valid: {args.question}")
    else:
        print(f"retired: {target}")
    return 0


def review_questions_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="py -m ky review-questions")
    parser.add_argument("--date", default=None)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    today = _parse_iso_date(args.date, "--date") if args.date else date.today()
    if today is None:
        return 3
    try:
        workspace = load_workspace(args.workspace)
        config_path = workspace.require("settings.exam_config")
        preflight_args = argparse.Namespace(
            config=config_path, items=None, workspace=args.workspace, date=today.isoformat(),
            usage=None, urgent_overdue_days=3, urgent_defer_count=2,
            freeze_backlog_days=3,
        )
        config, items, workspace, route, timetable, day_budget, _ = _preflight_load_context(
            preflight_args, today, workspace_override=workspace,
        )
        policy, freeze_policy = _preflight_policies(preflight_args)
        plans = DayPlanStore(workspace.write_target("state.plans"))
        plan_state = plans.read_state_sources()
        freeze = assess_freeze(
            today, config, items, freeze_policy,
            latched=latch_active(plan_state.freeze_events),
        )
        selected, _ = _preflight_calculate(
            config, items, today, {}, policy, freeze, day_budget,
        )
        bank_path = (
            workspace.write_target("state.question_bank")
            if workspace.question_bank is not None else None
        )
        bank = load_question_bank(bank_path) if bank_path is not None else ()
        output = build_review_questions(
            workspace, selected.selected, bank_path, bank, plan_state.completions,
        )
    except (ContractError, StorageError, KnowledgePointError, ValueError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    payload = {"date": today.isoformat(), "reviews": output}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for record in output:
            status = record.get("status", record.get("question_level", "缺题"))
            check = record.get("check", "-")
            question_ref = record.get("question_ref", "-")
            print(
                f"{record['review_id']} {record['title']} [{record['level']}] {status} "
                f"check={check} question_ref={question_ref}"
            )
            if "question" in record:
                print(json.dumps(record["question"], ensure_ascii=False, sort_keys=True))
                if record.get("question_level") == "adapted":
                    question_id = question_id_from_ref(record["question_ref"])
                    # Copy-paste ready like the generation command (e2e run 2026-10-02, sol 272).
                    # sol 282 M2: keep the placeholder quoted for PowerShell parsing.
                    print(
                        "有问题可停用：py -3.12 -m ky question-bank retire --question "
                        f'{question_id} --reason "替换为原因" --date {today.isoformat()}'
                    )
            elif "generation_command" in record:
                print(record["generation_command"])
    return 0


def _route_submit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py -m ky route submit")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--plan")
    source.add_argument("--from-staging")
    parser.add_argument("--config", default=None)
    parser.add_argument("--store", default=None)
    parser.add_argument("--workspace", default=None)
    return parser


def _route_show_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py -m ky route show")
    parser.add_argument("--revision", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--store", default=None)
    parser.add_argument("--workspace", default=None)
    return parser


def _route_submit(rest: list[str]) -> int:
    try:
        args = _route_submit_parser().parse_args(rest)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    # A missing input remains a usage error regardless of workspace state (sol 99 C2).
    if args.plan is not None and not Path(args.plan).is_file():
        print(f"--plan file does not exist: {args.plan}", file=sys.stderr)
        return 3
    try:
        store_path = _routes_store_path(args)
        store = RoutePlanStore(store_path)
        if args.plan is None:
            report = apply_staged_route_proposal(
                args.from_staging, store=store, config_path=args.config,
                workspace_path=args.workspace,
            )
        else:
            workspace = _discovered_workspace(args.workspace)
            reject_staging_plan_path(args.plan, workspace)
            report = apply_human_route_plan(args.plan, store=store)
        print(
            f"written: {report.path} (revision {report.version}, "
            f"sha256 {report.sha256})"
        )
        return 0
    except (
        ContractError, RoutePlanError, StorageError, OSError, UnicodeError, ValueError
    ) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2


def _route_show(rest: list[str]) -> int:
    try:
        args = _route_show_parser().parse_args(rest)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    try:
        store_path = _routes_store_path(args)
        store = RoutePlanStore(store_path)
        plan = store.current() if args.revision is None else store.load_revision(args.revision)
        if plan is None:
            print("null" if args.json else "\u5c1a\u65e0\u8def\u7ebf")
            return 0
        actor, input_hash = store.provenance(plan.revision)
        if args.json:
            payload = {
                "route_plan": route_plan_to_mapping(plan),
                "actor": actor,
                "input_hash": input_hash,
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        _route_print_plan(plan, actor, input_hash)
        return 0
    except (
        ContractError, RoutePlanError, StorageError, OSError, UnicodeError, ValueError
    ) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2


def _route_print_plan(plan, actor, input_hash) -> None:
    print(f"route_id          : {plan.route_id}")
    print(f"revision          : {plan.revision}")
    print(f"start_date        : {plan.start_date.isoformat()}")
    print(f"end_exclusive     : {plan.end_exclusive.isoformat()}")
    print(f"target_exam_date  : {plan.target_exam_date.isoformat()}")
    print(f"policy_version    : {plan.policy_version}")
    print(f"source            : actor={actor}, input_hash={input_hash}")
    for phase in plan.phases:
        subjects = " ".join(
            f"{subject_id}={minutes}"
            for subject_id, minutes in sorted(phase.review_minutes.items())
        )
        print(
            f"{phase.index:02d} {phase.start.isoformat()}\u2013{phase.end_exclusive.isoformat()} "
            f"[\u53f3\u5f00] {phase.label} {subjects}"
        )


def route_main(argv: list[str]) -> int:
    """``py -m ky route submit|show`` (M14, ``contracts/route_plan.md``)."""
    _reconfigure_streams_utf8()
    if not argv or argv[0] not in {"submit", "show"}:
        print("usage: py -m ky route {submit,show} ...", file=sys.stderr)
        return 3
    if argv[0] == "submit":
        return _route_submit(argv[1:])
    return _route_show(argv[1:])


def day_plan_main(argv: list[str]) -> int:
    """Run the submit or record CLI branch."""
    _reconfigure_streams_utf8()
    if not argv or argv[0] not in ("submit", "record", "advance"):
        print("usage: py -m ky day-plan {submit,record,advance} ...", file=sys.stderr)
        return 3
    if argv[0] == "submit":
        return _day_plan_submit(argv[1:])
    if argv[0] == "advance":
        return _day_plan_advance(argv[1:])
    return _day_plan_record(argv[1:])


def _day_plan_advance(rest: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="py -3.12 -m ky day-plan advance")
    parser.add_argument("--date", required=True)
    parser.add_argument("--store", default=None)
    parser.add_argument("--review-store", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--workspace", default=None)
    try:
        args = parser.parse_args(rest)
        day = date.fromisoformat(args.date)
        if day.isoformat() != args.date:
            raise ValueError("date must be YYYY-MM-DD")
        store_path, workspace, _workspace_error, _workspace_not_found = (
            _day_plan_record_workspace(args)
        )
        config_path = _day_plan_record_config_path(args, workspace)
        if args.review_store is None:
            if workspace is None:
                raise ContractError("workspace registry required for default --review-store",
                                    "--review-store")
            review_path = workspace.write_target("state.review_queue")
        else:
            review_path = Path(args.review_store)
        config = load_config(config_path)
        event = DayPlanStore(store_path).load_completion_event(day)
        if event is None:
            raise ContractError("no completion event for date", f"day.{day.isoformat()}")
        report = advance_loaded_event(event, config, ReviewShardStore(review_path))
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    except (ContractError, StorageError, ValueError, OSError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    print(f"review queue advanced: {len(report.advanced_review_ids)} completion(s) "
          f"(replayed: {len(report.replayed_review_ids)}; late: {len(report.late_review_ids)}; "
          f"needs check: {len(report.needs_check_review_ids)})")
    return 0


def _day_plan_submit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py -m ky day-plan submit")
    parser.add_argument("--config", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--plan", help="path to a human-authored day-plan YAML file")
    source.add_argument("--from-staging", help="path to a staged day-plan proposal")
    parser.add_argument("--store", default=None,
                        help="day-plan store directory (default: workspace state.plans)")
    parser.add_argument("--workspace", default=None,
                        help="workspace registry (otherwise discover)")
    parser.add_argument(
        "--max-single-item-minutes", type=int, default=None,
        help="optional per-pass minute bound (see check_invariants); the system does not "
             "default this -- omit it to skip the check",
    )
    return parser


def _day_plan_submit(rest: list[str]) -> int:
    args = _day_plan_submit_parser().parse_args(rest)
    try:
        store_path = _plans_store_path(args)
        workspace = _discovered_workspace(args.workspace)
        availability = availability_for_workspace(workspace) if workspace is not None else None
    except ContractError as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    try:
        config = load_config(args.config)
    except ContractError as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    weights = {s.subject_id: s.weight for s in config.active_subjects()}
    freeze_gate = None
    if workspace is not None:
        freeze_gate = lambda day: _freeze_submission_if_needed(day, config, workspace)
    store = DayPlanStore(
        store_path, subject_weights=weights,
        max_single_item_minutes=args.max_single_item_minutes,
        availability=availability, freeze_gate=freeze_gate,
    )
    return _day_plan_submit_apply(args, store, workspace)


def _day_plan_submit_apply(args, store: DayPlanStore, workspace: Workspace | None) -> int:
    if args.plan and not Path(args.plan).is_file():
        print(f"--plan file does not exist: {args.plan}", file=sys.stderr)
        return 3
    try:
        if args.from_staging:
            report = apply_staged_proposal(
                args.from_staging, store=store, config_path=args.config,
                workspace_path=args.workspace,
            )
        else:
            reject_staging_plan_path(args.plan, workspace)
            report = apply_human_plan(args.plan, store=store)
    except (ContractError, StorageError, OSError, UnicodeError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    print(f"written: {report.path} (version {report.version}, sha256 {report.sha256})")
    return 0


def _day_plan_record_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py -m ky day-plan record")
    parser.add_argument("--config", default=None,
                        help="exam config (default: the registry's settings.exam_config)")
    parser.add_argument("--done", required=True, help="path to a completion-event YAML file")
    parser.add_argument("--store", default=None,
                        help="day-plan store directory (default: workspace state.plans)")
    parser.add_argument(
        "--review-store", default=None,
        help="review-queue store directory (a ky.storage.review_shards.ReviewShardStore root); "
             "when given, every completed review in --done is advanced (due_date, interval, "
             "ease) and written back to this queue. Omitting it only records the completion "
             "event only; it does not advance the review queue.",
    )
    parser.add_argument("--workspace", default=None,
                        help="workspace registry (otherwise discover)")
    parser.add_argument("--json", action="store_true")
    return parser


def _day_plan_record_config_path(args, workspace) -> str | Path:
    # Same rule as `ky resume`: an explicit --config wins, else the registered config,
    # so the AI driving the loop does not have to repeat the path every day.
    if args.config is not None:
        return args.config
    if workspace is None:
        raise ContractError("no workspace registry found; pass --config", "--config")
    return workspace.require("settings.exam_config")


def _day_plan_record(rest: list[str]) -> int:
    args = _day_plan_record_parser().parse_args(rest)
    try:
        store_path, workspace, workspace_error, workspace_not_found = (
            _day_plan_record_workspace(args)
        )
        try:
            config_path = _day_plan_record_config_path(args, workspace)
            config = load_config(config_path)
        except ContractError as exc:
            print(f"contract violation: {exc}", file=sys.stderr)
            raise _CliExit(2) from exc
        event = _day_plan_record_event(args.done)
        review_store = ReviewShardStore(args.review_store) if args.review_store else None
        try:
            report, queue_report = record_loaded_event(
                workspace, event, config, store_path, review_store,
                advance_handler=advance_review_queue,
            )
        except RecordPipelineError as exc:
            if exc.stage == "event_written":
                print(f"guardrail violation: completion event written to {exc.record_path}, "
                      f"but the review queue was not advanced: {exc}", file=sys.stderr)
                print(_day_plan_advance_command(
                    event.day, store_path, review_store, config_path, workspace,
                ), file=sys.stderr)
            else:
                print(f"guardrail violation: {exc}", file=sys.stderr)
            raise _CliExit(2) from exc
        candidates: list[dict] = []
        skip_reason = None
        if queue_report is not None and queue_report.needs_check_review_ids:
            candidates, skip_reason = _day_plan_record_query_candidates(
                review_store, queue_report, workspace, workspace_error,
            )
    except _CliExit as exc:
        return exc.exit_code
    return _day_plan_record_output(
        args, report, workspace, workspace_not_found, queue_report, candidates,
        skip_reason,
    )


def _day_plan_advance_command(day, store_path, review_store, config_path, workspace) -> str:
    """Pin recovery to the resolved inputs used by the failed record attempt."""
    parts = ["py", "-3.12", "-m", "ky", "day-plan", "advance", "--date",
             day.isoformat(), "--store", str(store_path)]
    if review_store is not None:
        parts.extend(("--review-store", str(review_store.root)))
    parts.extend(("--config", str(config_path)))
    if workspace is not None:
        parts.extend(("--workspace", str(workspace.source)))
    return subprocess.list2cmdline(parts)


def _day_plan_record_workspace(args):
    # Without --store, the registry is required; otherwise it is optional and read once.
    if args.store is None:
        try:
            workspace = _load_workspace_for_default(args.workspace, "--store")
            return workspace.write_target("state.plans"), workspace, None, False
        except ContractError as exc:
            print(f"contract violation: {exc}", file=sys.stderr)
            raise _CliExit(2) from exc
    store_path = Path(args.store)
    workspace, error, not_found = _optional_workspace(args.workspace)
    return store_path, workspace, error, not_found


def _day_plan_record_event(done: str):
    done_path = Path(done)
    if not done_path.is_file():
        print(f"--done file does not exist: {done_path}", file=sys.stderr)
        raise _CliExit(3)
    if yaml is None:  # pragma: no cover
        print("PyYAML is required", file=sys.stderr)
        raise _CliExit(3)
    try:
        raw = yaml.safe_load(done_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"--done is not valid YAML: {exc}", file=sys.stderr)
        raise _CliExit(3) from exc
    try:
        return parse_completion_event(raw, source=done_path.as_posix())
    except CompletionError as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        raise _CliExit(2) from exc


def _day_plan_record_query_candidates(review_store, queue_report, workspace, workspace_error):
    if workspace is None:
        return [], workspace_error
    candidates: list[dict] = []
    try:
        queue_items = {item.review_id: item for item in review_store.load()}
        for review_id in queue_report.needs_check_review_ids:
            item = queue_items[review_id]
            result = candidate_check_questions(workspace, item.knowledge_point_id, limit=3)
            candidates.append({
                "review_id": review_id,
                "knowledge_point_id": item.knowledge_point_id,
                **result,
            })
    except ContractError as exc:
        # Keep groups found before the failing review; b867ae7 did (sol round 150, G3c-M5).
        return candidates, str(exc)
    return candidates, None


def _day_plan_record_output(
    args, report, workspace, workspace_not_found, queue_report, candidates, skip_reason,
) -> int:
    if args.json:
        payload = record_report_mapping(
            report, workspace, queue_report, candidates, skip_reason,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"written: {report.path} (sha256 {report.sha256})")
    if workspace is None:
        _day_plan_record_print_no_workspace()
    _day_plan_record_print_queue(queue_report, candidates, skip_reason, workspace_not_found)
    return 0


def _day_plan_record_print_no_workspace() -> None:
    print(
        "\u672a\u627e\u5230\u53ef\u7528\u7684\u5de5\u4f5c\u533a"
        "\u6ce8\u518c\u8868\uff0c\u672a\u68c0\u67e5\u51bb\u7ed3\u9501\u5b58"
    )


def _day_plan_record_print_queue(
    queue_report, candidates, skip_reason, workspace_not_found,
) -> None:
    if queue_report is None:
        return
    print(
        f"review queue advanced: {len(queue_report.advanced_review_ids)} completion(s) "
        f"(replayed: {len(queue_report.replayed_review_ids)}; "
        f"late: {len(queue_report.late_review_ids)}; "
        f"needs check: {len(queue_report.needs_check_review_ids)})"
    )
    for late in queue_report.fsrs_late_checks:
        print(
            "晚到的核对未被 FSRS 采用："
            f"{late.review_id} {late.completion_id} ({late.completed_on})，"
            f"FSRS 时钟为 {late.fsrs_reviewed_on}"
        )
    if skip_reason is not None:
        if workspace_not_found:
            _day_plan_record_print_registry_missing()
        else:
            _day_plan_record_print_skip_reason(skip_reason)
        return
    for suggestion in candidates:
        _day_plan_record_print_suggestion(suggestion)


def _day_plan_record_print_registry_missing() -> None:
    print("\u672a\u627e\u5230\u5de5\u4f5c\u533a\u6ce8\u518c\u8868\uff0c\u8df3\u8fc7\u51fa\u9898")


def _day_plan_record_print_skip_reason(skip_reason: str) -> None:
    print(f"\u51fa\u9898\u67e5\u8be2\u5931\u8d25\uff0c\u5df2\u8df3\u8fc7\uff1a{skip_reason}")


def _day_plan_record_print_suggestion(suggestion) -> None:
    if not suggestion["candidates"]:
        if suggestion["fallback"] == "ai_generated_allowed":
            print(
                f"{suggestion['review_id']} "
                "\u8be5\u77e5\u8bc6\u70b9\u65e0\u771f\u9898\uff0c"
                "\u53ef\u7528 AI \u5de9\u56fa\u9898"
                "\uff08\u4ec5 guided \u8bc1\u636e\uff09"
            )
        return
    for candidate in suggestion["candidates"]:
        page = candidate["locator"].get("page")
        where = (
            f"\u5377\u9762\u7b2c {page} \u9875"
            if page else "\u9875\u7801\u672a\u77e5"
        )
        print(
            f"{suggestion['review_id']} "
            f"\u9700\u8981\u6838\u5bf9\uff1a{candidate['question_id']}"
            f"\uff08{candidate['exam_year']} \u7b2c {candidate['number']} "
            f"\u9898\uff0c{where}\uff09"
        )


def _month_close_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py -m ky month-close")
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--store", default=None,
        help="day-plan store directory (default: workspace state.plans)",
    )
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--month", required=True, type=int)
    parser.add_argument(
        "--max-single-item-minutes", type=int, default=None,
        help="optional per-pass minute bound, same meaning as day-plan submit's flag",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--workspace", default=None, help="workspace registry (otherwise discover)")
    return parser


def _month_close_load_inputs(args):
    store_path = _plans_store_path(args)
    config = load_config(args.config)
    return store_path, config


def _month_close_compute(args, config, store_path):
    weights = {s.subject_id: s.weight for s in config.active_subjects()}
    store = DayPlanStore(
        store_path, subject_weights=weights, max_single_item_minutes=args.max_single_item_minutes
    )
    plans = list(store.load_month(args.year, args.month))
    completions = list(store.load_month_completions(args.year, args.month))
    return close_month(
        args.year, args.month, plans, subject_weights=weights,
        max_single_item_minutes=args.max_single_item_minutes,
        completions=completions,
    )


def _month_close_to_mapping(mc) -> dict:
    return {
        "year": mc.year, "month": mc.month, "days_in_month": mc.days_in_month,
        "days_planned": mc.days_planned, "days_unplanned": mc.days_unplanned,
        "available_minutes": mc.available_minutes, "allocated_minutes": mc.allocated_minutes,
        "by_channel": mc.by_channel, "vocab_items_introduced": mc.vocab_items_introduced,
        "overshoot_days": mc.overshoot_days, "overshoot_minutes": mc.overshoot_minutes,
        "unused_minutes": mc.unused_minutes, "backlog_minutes": mc.backlog_minutes,
        "backlog_days": mc.backlog_days, "utilisation": mc.utilisation,
        "actual_data_available": mc.actual_data_available,
        "days_with_completion_events": mc.days_with_completion_events,
        "actual_reviews_completed": mc.actual_reviews_completed,
        "actual_vocab_delivered_words": mc.actual_vocab_delivered_words,
        "actual_vocab_practiced_words": mc.actual_vocab_practiced_words,
        "vocab_delivered_vs_planned": mc.vocab_delivered_vs_planned,
        "ok": mc.ok, "violations": list(mc.violations), "notes": mc.notes,
    }


def _month_close_print_text(mc) -> None:
    print(f"month              : {mc.year:04d}-{mc.month:02d}")
    print(
        f"days planned/total : {mc.days_planned}/{mc.days_in_month} "
        f"({mc.days_unplanned} unplanned)"
    )
    print(f"available/allocated: {mc.available_minutes}/{mc.allocated_minutes} min "
          f"(utilisation {mc.utilisation:.1%})  -- PLANNED, not actual")
    print(f"by channel         : {mc.by_channel}")
    print(f"vocab introduced   : {mc.vocab_items_introduced}  -- PLANNED new items")
    print(f"overshoot          : {mc.overshoot_days} day(s), {mc.overshoot_minutes} min")
    print(f"unused / backlog   : {mc.unused_minutes} / {mc.backlog_minutes} min "
          f"({mc.backlog_days} backlog day(s))")
    if mc.actual_data_available:
        print(f"actual reviews done: {mc.actual_reviews_completed}  "
              f"({mc.days_with_completion_events} day(s) with a completion event)")
        print(f"actual vocab       : delivered {mc.actual_vocab_delivered_words}, "
              f"practiced {mc.actual_vocab_practiced_words}  (kept separate, not summed)")
        print(f"delivered vs planned new-items: {mc.vocab_delivered_vs_planned:+d}")
    else:
        print("actual outcomes    : no completion-event data was requested for this close")
    for note in mc.notes:
        print(f"  note: {note}")
    print(f"ok                 : {mc.ok}")
    for violation in mc.violations:
        print(f"  violation: {violation}")


def month_close_main(argv: list[str]) -> int:
    """``py -m ky month-close``: read-only. Computes the close live from the day plans already in
    the store and prints it -- it never calls ``DayPlanStore.write_month_close`` itself. Turning
    a month-close into unwritable history is a deliberate, separate, later act (see round-37 §8).

    Exit codes: 0 = printed, 3 = usage error.
    """
    _reconfigure_streams_utf8()
    args = _month_close_parser().parse_args(argv)

    try:
        store_path, config = _month_close_load_inputs(args)
    except ContractError as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2

    if not 1 <= args.month <= 12:
        print(f"--month must be 1..12, got {args.month}", file=sys.stderr)
        return 3

    mc = _month_close_compute(args, config, store_path)

    if args.json:
        payload = _month_close_to_mapping(mc)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    _month_close_print_text(mc)
    return 0


def _timetable_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py -3.12 -m ky timetable")
    commands = parser.add_subparsers(dest="action", required=True)
    show = commands.add_parser("show")
    selector = show.add_mutually_exclusive_group(required=True)
    selector.add_argument("--week", type=int)
    selector.add_argument("--date")
    show.add_argument("--semester")
    show.add_argument("--config", required=True)
    show.add_argument("--workspace")
    check = commands.add_parser("check")
    check.add_argument("--school")
    check.add_argument("--config")
    check.add_argument("--workspace")
    restage_parser = commands.add_parser("restage")
    restage_parser.add_argument("file")
    restage_parser.add_argument("--workspace")
    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("--from-staging", required=True)
    apply_parser.add_argument("--replace", action="store_true")
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.add_argument("--workspace")
    import_pdf = commands.add_parser("import-pdf")
    import_pdf.add_argument("file")
    import_pdf.add_argument("--school", required=True)
    import_pdf.add_argument("--label", required=True)
    import_pdf.add_argument("--week1", required=True)
    import_pdf.add_argument("--weeks", type=int)
    import_pdf.add_argument("--config")
    import_pdf.add_argument("--workspace")
    import_parser = commands.add_parser("import-ics")
    import_parser.add_argument("file")
    import_parser.add_argument("--school", required=True)
    import_parser.add_argument("--label", required=True)
    import_parser.add_argument("--week1", required=True)
    import_parser.add_argument("--weeks", type=int)
    import_parser.add_argument("--timezone")
    import_parser.add_argument("--config")
    import_parser.add_argument("--workspace")
    export_parser = commands.add_parser("export-ics")
    export_parser.add_argument("--from", dest="from_date", required=True)
    export_parser.add_argument("--to", dest="to_date", required=True)
    export_parser.add_argument("--config", required=True)
    export_parser.add_argument("--out", required=True)
    export_filter = export_parser.add_mutually_exclusive_group()
    export_filter.add_argument("--free-only", action="store_true")
    export_filter.add_argument("--classes-only", action="store_true")
    export_parser.add_argument("--workspace")
    return parser


def _timetable_import_pdf(args, workspace: Workspace | None) -> int:
    if workspace is None:
        raise ContractError("workspace registry not found", "--workspace")
    try:
        data = Path(args.file).read_bytes()
    except OSError as exc:
        raise ContractError("cannot read PDF input", "source") from exc
    isolation = inspect_isolation(workspace.root)
    result = import_zfsoft_pdf(
        data,
        workspace,
        isolation,
        school_id=args.school,
        label=args.label,
        week1=args.week1,
        weeks=args.weeks,
        config_path=args.config,
    )
    for line in (*result.summary, *result.grid):
        print(line)
    return 0


def timetable_main(argv: list[str]) -> int:
    _reconfigure_streams_utf8()
    try:
        args = _timetable_parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    if args.action == "check" and args.school is not None:
        return _timetable_check_school(Path(args.school))
    if args.action == "show" and args.date is not None and args.semester is not None:
        print("--semester is only valid with --week", file=sys.stderr)
        return 3
    if args.action in {"import-ics", "export-ics"}:
        return _timetable_ics_command(args)
    try:
        workspace = _discovered_workspace(args.workspace)
        if args.action == "import-pdf":
            return _timetable_import_pdf(args, workspace)
        if args.action in {"restage", "apply"}:
            if workspace is None:
                raise ContractError("workspace registry not found", "--workspace")
            isolation = inspect_isolation(workspace.root)
            if args.action == "restage":
                result = restage(workspace, args.file, isolation)
                for line in result.changes:
                    print(line)
                print(f"暂存文件：{result.path}")
                return 0
            result = apply_staging(
                workspace,
                args.from_staging,
                isolation,
                replace=args.replace,
                dry_run=args.dry_run,
            )
            for line in result.changes:
                print(line)
            # "already_applied" carries its own line in ``changes``; do not print it twice.
            if result.status == "dry_run":
                print("dry-run：未写入")
            elif result.status == "applied":
                print("已写入")
            return 0
        if args.action == "check":
            return _timetable_check_workspace(workspace)
        config = load_config(args.config)
        timetable = timetable_for_workspace(workspace) if workspace is not None else None
        route_store = (
            RoutePlanStore(workspace.write_target("state.routes"))
            if workspace is not None and workspace.routes is not None else None
        )
        route = route_store.current() if route_store is not None else None
        pacing_settings = settings_for_workspace(workspace) if workspace is not None else None
    except (ContractError, StorageError, OSError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    if args.week is not None:
        return _timetable_show_week(args, timetable, config, route, pacing_settings)
    return _timetable_show_date(args, timetable, config, route, pacing_settings)


def _iso_argument(value: str, field: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must be an ISO date")
    return parsed


def _timetable_ics_command(args) -> int:
    try:
        workspace = _discovered_workspace(args.workspace)
        if workspace is None:
            raise ContractError("workspace registry not found", "--workspace")
        if args.action == "import-ics":
            week1 = _iso_argument(args.week1, "--week1")
            if args.weeks is not None and args.weeks < 1:
                print("--weeks must be >= 1", file=sys.stderr)
                return 3
            import_ics(
                workspace, args.file, school=args.school, label=args.label,
                week1=week1, weeks=args.weeks, timezone_name=args.timezone,
                config_path=args.config,
            )
            return 0
        start = _iso_argument(args.from_date, "--from")
        end = _iso_argument(args.to_date, "--to")
        if end <= start:
            print("--from must precede --to", file=sys.stderr)
            return 3
        export_ics(
            workspace, start, end, args.config, args.out,
            free_only=args.free_only, classes_only=args.classes_only,
        )
        return 0
    except (ContractError, StorageError, OSError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3


def _timetable_check_school(path: Path) -> int:
    try:
        profile = load_school(path)
    except ContractError as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    print(f"OK school profile: {profile.school_id}")
    return 0


def _timetable_check_workspace(workspace: Workspace | None) -> int:
    try:
        _timetable_validate_workspace(workspace)
    except (ContractError, OSError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    print("OK timetable")
    return 0


def _timetable_validate_workspace(workspace: Workspace | None) -> None:
    if workspace is None:
        return
    calendar = timetable_for_workspace(workspace)
    loaded = set(calendar.schools) if calendar is not None else set()
    for school_id in workspace.timetable_schools:
        if school_id in loaded:
            continue
        registry_key = f"reference.timetable_schools.{school_id}"
        profile = load_school(workspace.require(registry_key))
        if profile.school_id != school_id:
            raise ContractError("school_id does not match registration", registry_key)
    if calendar is not None:
        _timetable_print_conflicts(calendar)
        _timetable_print_unconfirmed(calendar)


def _timetable_print_conflicts(calendar) -> None:
    for semester in calendar.timetable.semesters:
        for left, right in combinations(semester.courses, 2):
            if left.weekday != right.weekday or not left.weeks.intersection(right.weeks):
                continue
            overlaps = (
                left.first_period <= right.last_period
                and right.first_period <= left.last_period
            )
            if overlaps:
                weeks = ",".join(map(str, sorted(left.weeks & right.weeks)))
                print(
                    f"course overlap: {semester.label} weekday {left.weekday} "
                    f"weeks {weeks} {left.name} / {right.name}"
                )


def _timetable_print_unconfirmed(calendar) -> None:
    for semester in calendar.timetable.semesters:
        school = calendar.schools[semester.school]
        numbers = {
            number
            for course in semester.courses
            for number in range(course.first_period, course.last_period + 1)
            if number in school.periods and school.periods[number].unconfirmed
        }
        if numbers:
            listed = ",".join(map(str, sorted(numbers)))
            print(f"unconfirmed periods: {semester.label} {listed}")


def _timetable_select_semester(args, timetable):
    if timetable is None or not timetable.timetable.semesters:
        print("没有可显示的学期", file=sys.stderr)
        return None, 3
    semesters = timetable.timetable.semesters
    if args.semester is not None:
        semester = next((item for item in semesters if item.label == args.semester), None)
        if semester is None:
            print(f"unknown semester: {args.semester}", file=sys.stderr)
            return None, 3
        return semester, None
    if len(semesters) != 1:
        print("多个学期时必须指定 --semester", file=sys.stderr)
        return None, 3
    return semesters[0], None


def _timetable_show_week(
    args: argparse.Namespace, timetable, config: KaoyanConfig, route: RoutePlan | None,
    pacing_initial=None,
) -> int:
    if args.week < 1:
        print("--week must be >= 1", file=sys.stderr)
        return 3
    semester, exit_code = _timetable_select_semester(args, timetable)
    if exit_code is not None:
        return exit_code
    if args.week > semester.weeks:
        print(f"--week must be 1..{semester.weeks}", file=sys.stderr)
        return 3
    monday = semester.week1_monday + timedelta(days=(args.week - 1) * 7)
    # Each column is that date's resolved schedule, so no_class and follow exceptions show in the
    # grid exactly as they do in the minutes row (sol round 224 R1).
    schedules = []
    for index in range(7):
        day = monday + timedelta(days=index)
        base_minutes, _ = daily_base_minutes(
            day, config, route, pacing_initial=pacing_initial,
        )
        schedules.append(timetable.day(day, base_minutes))
    _timetable_print_grid(timetable.schools[semester.school], schedules)
    print("minutes            : " + " ".join(str(item.minutes) for item in schedules))
    return 0


def _timetable_print_grid(school, schedules) -> None:
    weekdays = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    for number, period in school.periods.items():
        marker = "*" if period.unconfirmed else ""
        cells = [
            "/".join(
                name for name, first, last, _start, _end in schedule.classes
                if first <= number <= last
            ) or "-"
            for schedule in schedules
        ]
        row = " | ".join(f"{day} {cell}" for day, cell in zip(weekdays, cells))
        print(
            f"{number:>2}{marker} {_format_period_time(period.start)}-"
            f"{_format_period_time(period.end)} | {row}"
        )


def _timetable_show_date(
    args: argparse.Namespace, timetable, config: KaoyanConfig, route: RoutePlan | None,
    pacing_initial=None,
) -> int:
    try:
        day = date.fromisoformat(args.date)
    except ValueError:
        print(f"--date must be an ISO date, got {args.date!r}", file=sys.stderr)
        return 3
    if day.isoformat() != args.date:
        print(f"--date must be an ISO date, got {args.date!r}", file=sys.stderr)
        return 3
    base_minutes, _ = daily_base_minutes(day, config, route, pacing_initial=pacing_initial)
    schedule = timetable.day(day, base_minutes) if timetable is not None else None
    if schedule is None:
        print("课表不覆盖此日")
        return 0
    print(f"date               : {day.isoformat()}")
    for name, first, last, start, end in schedule.classes:
        print(f"class              : {name} {first}-{last} {start}-{end}")
    print(f"free segments      : {schedule.free_segments}")
    print(f"blocks             : {schedule.blocks}")
    print(f"cap                : {schedule.cap}")
    print(f"minutes            : {schedule.minutes}")
    if schedule.unconfirmed_periods:
        print(f"unconfirmed        : {schedule.unconfirmed_periods}")
    return 0


def _format_period_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _review_queue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py -m ky review-queue")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("check")
    migrate_parser = commands.add_parser("migrate")
    migrate_parser.add_argument("--subject", required=True)
    migrate_parser.add_argument("--from", dest="from_version", required=True)
    migrate_parser.add_argument("--to", dest="to_version")
    for child in commands.choices.values():
        child.add_argument("--workspace")
        child.add_argument("--store")
    migrate_parser.add_argument("--apply", action="store_true")
    return parser


def _review_queue_check(workspace, items) -> int:
    tree_ids = _effective_tree_ids(workspace)
    problems = check_queue_references(items, tree_ids)
    if problems:
        for problem in problems:
            print(f"ERROR {problem}", file=sys.stderr)
        return 2
    print(f"OK queue references ({len(items)} items)")
    return 0


def _review_queue_migrate(args, workspace, store, items) -> int:
    subject_id = args.subject
    target_version = args.to_version or workspace.effective_version(subject_id)
    if target_version is None:
        raise ContractError("subject has no effective syllabus version", "--to")
    mapping_key = f"reference.syllabus_versions.{subject_id}.mappings"
    mapping_paths = workspace.require_all(mapping_key)
    mappings = tuple(
        load_syllabus_mapping(path, workspace, subject_id=subject_id)
        for path in mapping_paths
    )
    chain = resolve_mapping_chain(mappings, args.from_version, target_version)
    plan = plan_queue_migration(items, chain, subject_id=subject_id)
    print(_migration_summary(plan))
    if args.apply:
        target_key = f"reference.syllabus_versions.{subject_id}.versions.{target_version}"
        target_ids = _tree_ids_for_cli(workspace.require(target_key), target_key)
        problems = check_queue_references(
            plan.items, {**_effective_tree_ids(workspace), subject_id: target_ids}
        )
        if problems:
            for problem in problems:
                print(f"ERROR {problem}", file=sys.stderr)
            return 2
        # Validate even when the chain is empty (sol round 77, N1); skip only the write.
        if not chain:
            print("\u65e0\u9700\u8fc1\u79fb\uff08from == to\uff09")
            return 0
        store.write(plan.items)
        print("Applied")
    return 0


def review_queue_main(argv: list[str]) -> int:
    """Check queue references or plan/apply one subject's syllabus migration (M25)."""
    try:
        args = _review_queue_parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    try:
        workspace_path = find_workspace(explicit=args.workspace)
        workspace = load_workspace(workspace_path)
        store_path = (
            Path(args.store)
            if args.store is not None
            else workspace.write_target("state.review_queue")
        )
        store = ReviewShardStore(store_path)
        items = store.load() if store.manifest_path.exists() else load_review_queue(store_path)
        if args.action == "check":
            return _review_queue_check(workspace, items)
        return _review_queue_migrate(args, workspace, store, items)
    except (ContractError, KnowledgePointError, OSError, ValueError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2


def _effective_tree_ids(workspace: Workspace) -> dict[str, frozenset[str]]:
    result: dict[str, frozenset[str]] = {}
    for subject_id in workspace.subjects:
        if subject_id in workspace.knowledge_trees:
            key = f"reference.knowledge_trees.{subject_id}"
            result[subject_id] = _tree_ids_for_cli(workspace.require(key), key)
    return result


def _tree_ids_for_cli(path: Path, field: str) -> frozenset[str]:
    try:
        return frozenset(point.knowledge_point_id for point in load_knowledge_points(path))
    except (OSError, ValueError, KnowledgePointError) as exc:
        raise ContractError(f"cannot load registered tree: {exc}", field) from exc


def _migration_summary(plan: MigrationPlan) -> str:
    groups = ("unchanged", "renamed", "split", "retired", "merged")
    lines = [
        f"Migration plan: {len(plan.items)} items",
        "分类可重叠：一项可同时属于 renamed、merged 和 retired。",
    ]
    for group in groups:
        review_ids = getattr(plan, group)
        lines.append(f"{group}: {', '.join(review_ids) if review_ids else '-'}")
    return "\n".join(lines)


SUBCOMMANDS = {
    "preflight": (
        _preflight_main,
        "Validate the exam configuration and review queue, then select one day's reviews.",
    ),
    "ledger": (
        ledger_main,
        "Report material provenance, rights, integrity, and claim authorization.",
    ),
    "snapshot": (snapshot_main, "Print today's read-only state snapshot."),
    "planner-input": (
        planner_input_main,
        "Write one planner input package from the registered workspace.",
    ),
    "day-plan": (day_plan_main, "Submit a day plan or record a completion event."),
    "month-close": (month_close_main, "Print a read-only monthly close from recorded day plans."),
    "route": (route_main, "Submit or show a route plan."),
    "review-queue": (review_queue_main, "Check queue references or migrate a subject syllabus."),
    "review-questions": (review_questions_main, "Select today's review questions by mastery tier."),
    "learn": (learn_main, "Add completed knowledge points to the review queue."),
    "question-bank": (question_bank_main, "Submit or retire adapted questions."),
    "resume": (resume_main, "Replan the registered overdue review queue."),
    "timetable": (timetable_main, "Show, validate, stage, or apply timetable data."),
    "pacing": (pacing_main, "Generate a deterministic pacing review report."),
    "chart": (chart_main, "Generate offline timetable and study-progress charts."),
    "web": (__import__("ky.web.cli", fromlist=["web_main"]).web_main,
            "Run the local today view in a browser."),
}


def _print_top_level_help() -> None:
    print("usage: py -3.12 -m ky <子命令> [参数]")
    print("不写子命令即 preflight。可用子命令：")
    for name, (_, description) in SUBCOMMANDS.items():
        print(f"  {name:<14} {description}")
    print("使用 py -3.12 -m ky <子命令> -h 查看各自参数。")


def main(argv: list[str] | None = None) -> int:
    _reconfigure_streams_utf8()
    args_in = list(sys.argv[1:] if argv is None else argv)
    if args_in and args_in[0] in {"-h", "--help"}:
        _print_top_level_help()
        return 0
    if args_in and args_in[0] in SUBCOMMANDS:
        return SUBCOMMANDS[args_in[0]][0](args_in[1:])
    # No subcommand: the arguments belong to preflight, the default command. Taking its entry
    # from the table keeps explicit and implicit preflight identical (sol round 130, G3).
    return SUBCOMMANDS["preflight"][0](args_in)


if __name__ == "__main__":  # pragma: no cover - exercised via the CLI
    raise SystemExit(main())
