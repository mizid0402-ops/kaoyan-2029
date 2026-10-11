"""M28 pacing report, input, submit, and status CLI; see ``contracts/pacing_review.md``.

Public interfaces: ``pacing_main``, ``pacing_status_main``, and
``missing_report_cycles``. Report assembly reads each source once before publication.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Mapping

import yaml

from ky.models import ContractError, load_yaml_text, validate_config
from ky.availability import availability_source_for_workspace
from ky.timetable import timetable_for_workspace
from ky.storage.route_store import RoutePlanStore
from ky.pacing.port import (
    build_report, cycle_for_date, load_settings_source, missing_report_cycles,
    report_to_mapping,
)
from ky.pacing.storage import (
    read_report, read_report_with_digest, report_path, write_report_once,
)
from ky.schedule.completion import CompletionError
from ky.storage.day_plan_store import DayPlanStore, StorageError
from ky.storage.review_shards import ReviewShardStore
from ky.workspace import load_workspace
from ky.schedule.budget import resolve_day_budget
from ky.today.compute import pacing_status_result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py -3.12 -m ky pacing report")
    parser.add_argument("--cycle-end")
    parser.add_argument("--today")
    parser.add_argument("--config")
    parser.add_argument("--workspace")
    return parser


def _parse_date(value: str | None, field: str, default: date | None = None) -> date:
    if value is None:
        if default is not None:
            return default
        raise ContractError("required option is missing", field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("expected YYYY-MM-DD", field) from exc
    if parsed.isoformat() != value:
        raise ContractError("expected YYYY-MM-DD", field)
    return parsed


def _read_previous(settings, cycle, plans_root: Path):
    prior = cycle_for_date(settings, cycle.start.fromordinal(cycle.start.toordinal() - 1))
    if prior is None:
        return None
    path = report_path(plans_root, prior.end.isoformat())
    if not path.exists():
        return None
    return read_report_with_digest(path)


def _relative_path(workspace, source_path: Path) -> str:
    try:
        relative = source_path.resolve().relative_to(workspace.root.resolve()).as_posix()
    except ValueError:
        relative = f"external:{source_path.resolve().as_posix()}"
    return relative


def _add_store_sources(sources, workspace, root: Path, state_sources) -> None:
    for relative, digest in state_sources.items():
        source_path = root.joinpath(*PurePosixPath(relative).parts)
        sources[_relative_path(workspace, source_path)] = digest


def _resolve_cycle(args: argparse.Namespace, settings) -> tuple[date, date, Any]:
    today = _parse_date(args.today, "--today", date.today())
    end = _parse_date(args.cycle_end, "--cycle-end")
    cycle = cycle_for_date(settings, end)
    if cycle is None or cycle.end != end:
        raise ContractError("date is not a cycle end", "--cycle-end")
    if end >= today:
        raise ContractError("cycle end must be earlier than today", "--cycle-end")
    return today, end, cycle


def _load_config_source(args: argparse.Namespace, workspace) -> tuple[Any, Path, str]:
    if args.config:
        config_path = Path(args.config)
    elif workspace.exam_config is not None:
        config_path = workspace.exam_config
    else:
        raise ContractError(
            "pass --config explicitly or register settings.exam_config",
            "settings.exam_config",
        )
    try:
        config_bytes = config_path.read_bytes()
        config_raw = load_yaml_text(config_bytes.decode("utf-8"),
                                    source=config_path.as_posix())
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"cannot read config: {exc}", config_path.as_posix()) from exc
    if not isinstance(config_raw, Mapping):
        raise ContractError("config must be a mapping", config_path.as_posix())
    config = validate_config(config_raw, source=config_path.as_posix())
    return config, config_path, hashlib.sha256(config_bytes).hexdigest()


def _load_state(workspace, sources: dict[str, str]) -> dict[str, Any]:
    """Read every learning-state source once and record each digest (sol round 242 A3/A4)."""
    plans_state = DayPlanStore(workspace.plans).read_state_sources()
    queue_state = ReviewShardStore(workspace.review_queue).read_state_sources()
    _add_store_sources(sources, workspace, workspace.plans, plans_state.sources)
    _add_store_sources(sources, workspace, workspace.review_queue, queue_state.sources)
    availability = None
    availability_source = availability_source_for_workspace(workspace)
    if availability_source is not None:
        availability = availability_source.availability
        sources[_relative_path(workspace, workspace.availability)] = availability_source.sha256
    timetable = timetable_for_workspace(workspace)
    if timetable is not None:
        sources.update(timetable.sources)
    route = None
    if workspace.routes is not None:
        route_state = RoutePlanStore(workspace.routes).read_state_sources()
        route = route_state.route
        _add_store_sources(sources, workspace, workspace.routes, route_state.sources)
    return {
        "plans": plans_state.plans, "completions": plans_state.completions,
        "freeze_events": plans_state.freeze_events, "items": queue_state.items,
        "availability": availability, "timetable": timetable, "route": route,
    }


def _add_registry_sources(workspace, sources: dict[str, str], settings_digest: str) -> None:
    sources[_relative_path(workspace, workspace.source)] = workspace.sha256
    if workspace.local_sha256 is not None:
        local_source = workspace.source.with_name("kaoyan.workspace.local.yaml")
        sources[_relative_path(workspace, local_source)] = workspace.local_sha256
    sources[_relative_path(workspace, workspace.pacing)] = settings_digest


def _previous_report(workspace, settings, cycle, sources: dict[str, str]):
    previous_record = _read_previous(settings, cycle, workspace.plans)
    if previous_record is None:
        return None
    previous, previous_digest = previous_record
    previous_end = date.fromisoformat(previous["cycle"]["end"])
    previous_path = report_path(workspace.plans, previous_end.isoformat())
    sources[_relative_path(workspace, previous_path)] = previous_digest
    return previous


def _assemble(args: argparse.Namespace) -> tuple[dict[str, Any], Path, bool]:
    workspace = load_workspace(args.workspace)
    if workspace.pacing is None:
        raise ContractError("settings.pacing is not registered", "settings.pacing")
    settings, settings_digest = load_settings_source(str(workspace.pacing))
    today, end, cycle = _resolve_cycle(args, settings)
    config, config_path, config_digest = _load_config_source(args, workspace)
    sources: dict[str, str] = {}
    state = _load_state(workspace, sources)
    _add_registry_sources(workspace, sources, settings_digest)
    sources[_relative_path(workspace, config_path)] = config_digest
    previous = _previous_report(workspace, settings, cycle, sources)
    report = build_report(settings, config, cycle, today, sources=sources,
                          previous=previous, **state)
    path = report_path(workspace.plans, end.isoformat())
    existed = path.exists()
    stored = read_report(path) if existed else write_report_once(path, report)
    return stored, path, stored["sources"] != report["sources"]


def pacing_main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"report", "submit", "status"}:
        print("usage: py -3.12 -m ky pacing {report|submit|status}", file=sys.stderr)
        return 3
    if argv[0] == "status":
        return pacing_status_main(argv[1:])
    if argv[0] == "submit":
        from ky.pacing.submit import pacing_submit_main
        return pacing_submit_main(argv[1:])
    try:
        args = _parser().parse_args(argv[1:])
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    if not args.cycle_end:
        print("usage error: --cycle-end is required", file=sys.stderr)
        return 3
    try:
        report, path, changed = _assemble(args)
    except (ContractError, StorageError, CompletionError, OSError, yaml.YAMLError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    print(yaml.safe_dump(report_to_mapping(report), allow_unicode=True, sort_keys=False,
                         default_flow_style=False), end="")
    print(f"saved: {path}")
    if changed:
        print("报告生成后记录有变化，已保存的报告不变")
    return 0


def pacing_status_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="py -m ky pacing status")
    parser.add_argument("--today")
    parser.add_argument("--config")
    parser.add_argument("--workspace")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    try:
        workspace = load_workspace(args.workspace)
        if workspace.pacing is None:
            raise ContractError("settings.pacing is not registered", "settings.pacing")
        settings, _ = load_settings_source(str(workspace.pacing))
        today = _parse_date(args.today, "--today", date.today())
        if args.config:
            config_path = Path(args.config)
        elif workspace.exam_config is not None:
            config_path = workspace.exam_config
        else:
            raise ContractError("register settings.exam_config or pass --config",
                                "settings.exam_config")
        config_bytes = config_path.read_bytes()
        raw = load_yaml_text(config_bytes.decode("utf-8"), source=config_path.as_posix())
        if not isinstance(raw, Mapping):
            raise ContractError("config must be a mapping", config_path.as_posix())
        config = validate_config(raw, source=config_path.as_posix())
        availability_source = availability_source_for_workspace(workspace)
        availability = availability_source.availability if availability_source else None
        timetable = timetable_for_workspace(workspace)
        route_store = (RoutePlanStore(workspace.routes)
                       if workspace.routes is not None else None)
        route = route_store.current() if route_store is not None else None
        budget = resolve_day_budget(today, config, availability, route, timetable,
                                    pacing_initial=settings)
        cycle = cycle_for_date(settings, today)
        missing = missing_report_cycles(settings, today, workspace.plans)
    except (ContractError, StorageError, OSError, UnicodeError, yaml.YAMLError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    status = pacing_status_result(settings, budget, cycle, missing)
    next_review = status["next_review"] or "none"
    print(f"base: {budget.base_minutes} ({budget.base_source})")
    print(f"next_review: {next_review}")
    print("unreported_cycles: " + (", ".join(status["unreported_cycles"])
                                   if missing else "none"))
    return 0
