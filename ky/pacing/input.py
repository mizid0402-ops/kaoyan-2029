"""M28 pacing planner inputs; see ``contracts/pacing_review.md`` section 4.

Public interfaces: :func:`pacing_input_data`, :func:`pacing_input_from_snapshot`,
and :func:`create_pacing_input`. This adapter assembles one saved report and M8 snapshot.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from ky.availability import Availability, DerivedDailyMinutes, availability_for_workspace
from ky.models import ContractError, KaoyanConfig, config_to_mapping, load_config
from ky.pacing.port import PacingSettings, cycle_for_date, settings_for_workspace
from ky.pacing.storage import read_report, report_path
from ky.planner.port import canonical_json_bytes
from ky.schedule.budget import resolve_day_budget
from ky.schedule.planning import RoutePlan, route_plan_to_mapping
from ky.storage.route_store import RoutePlanStore
from ky.timetable import timetable_for_workspace
from ky.workspace import Workspace, load_workspace


def _settings_mapping(settings: PacingSettings) -> dict[str, Any]:
    value = asdict(settings)
    value["start"] = settings.start.isoformat()
    value["exam_date"] = settings.exam_date.isoformat()
    value["cadence"] = [
        {"kind": item.kind, **({"until": item.until.isoformat()}
                                if item.until is not None else {})}
        for item in settings.cadence
    ]
    return value


def pacing_input_data(
    cycle_end: date,
    today: date,
    *,
    config_path: str | Path | None,
    workspace: Workspace,
) -> tuple[dict[str, Any], str]:
    """Build a canonical M19 pacing input package without writing it."""
    settings = settings_for_workspace(workspace)
    if settings is None:
        raise ContractError("settings.pacing is not registered", "settings.pacing")
    config = load_config(config_path or workspace.require("settings.exam_config"))
    availability = availability_for_workspace(workspace)
    timetable = timetable_for_workspace(workspace)
    route_store = (RoutePlanStore(workspace.write_target("state.routes"))
                   if workspace.routes is not None else None)
    route = route_store.current() if route_store is not None else None
    return pacing_input_from_snapshot(
        cycle_end, today, workspace=workspace, settings=settings, config=config,
        availability=availability, timetable=timetable, route=route,
    )


def pacing_input_from_snapshot(
    cycle_end: date,
    today: date,
    *,
    workspace: Workspace,
    settings: PacingSettings,
    config: KaoyanConfig,
    availability: Availability | None,
    timetable: DerivedDailyMinutes | None,
    route: RoutePlan | None,
) -> tuple[dict[str, Any], str]:
    """Build a package from caller-owned source objects without rereading them."""
    cycle = cycle_for_date(settings, cycle_end)
    if cycle is None or cycle.end != cycle_end:
        raise ContractError("date is not a cycle end", "--cycle-end")
    if cycle_end >= today:
        raise ContractError("cycle end must be earlier than today", "--cycle-end")
    report_file = report_path(workspace.plans, cycle_end.isoformat())
    report = read_report(report_file)
    if report["cycle"]["end"] != cycle_end.isoformat():
        raise ContractError("saved report cycle does not match", report_file.as_posix())
    budget = resolve_day_budget(
        today, config, availability, route, timetable, pacing_initial=settings,
    )
    package = {
        "schema_version": 1,
        "kind": "pacing_input",
        "as_of": today.isoformat(),
        "report": report,
        "settings": _settings_mapping(settings),
        "config": config_to_mapping(config),
        "current_route": route_plan_to_mapping(route) if route is not None else None,
        "base_at": {
            "date": today.isoformat(),
            "minutes": budget.base_minutes,
            "source": budget.base_source,
        },
    }
    return package, hashlib.sha256(canonical_json_bytes(package)).hexdigest()


def create_pacing_input(
    cycle_end: date,
    today: date,
    *,
    config_path: str | Path | None = None,
    workspace_path: str | Path | None = None,
) -> tuple[Path, str]:
    """Write a hashed pacing input below registered staging/inputs."""
    workspace = load_workspace(workspace_path)
    package, digest = pacing_input_data(
        cycle_end, today, config_path=config_path, workspace=workspace,
    )
    staging = workspace.write_target("staging")
    inputs = staging / "inputs"
    target = inputs / f"pacing--{cycle_end.isoformat()}--{digest[:12]}.json"
    try:
        staging_resolved = staging.resolve(strict=False)
        inputs_resolved = inputs.resolve(strict=False)
        inputs_resolved.relative_to(staging_resolved)
        target_resolved = target.resolve(strict=False)
        target_resolved.relative_to(inputs_resolved)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError("pacing input path resolves outside staging/inputs",
                            target.as_posix()) from exc
    inputs.mkdir(parents=True, exist_ok=True)
    from ky.storage.atomic import replace_bytes
    replace_bytes(target, canonical_json_bytes(package))
    return target, digest
