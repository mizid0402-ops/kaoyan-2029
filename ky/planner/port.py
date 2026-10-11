"""M19 planner port; see ``contracts/planner_port.md`` (D10 route timeline fields).

Public interface: day/route input builders and staged/human apply functions. This module owns
input hashing, proposal validation, staging-path checks, and the shared M13 apply paths; it does
not call a planner model.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from ky.availability import availability_for_workspace
from ky.freeze import FreezePolicy, assess_freeze, freeze_to_mapping, latch_active
from ky.models import (
    ContractError, KaoyanConfig, config_to_mapping, load_config, load_yaml_text,
)
from ky.schedule.budget import DayBudget, allocate_new_content, resolve_day_budget
from ky.schedule.planning import RoutePlan, parse_route_plan, route_plan_to_mapping
from ky.schedule.review_clip import ReviewPolicy, preflight_to_mapping, select_daily_reviews
from ky.schedule.state_snapshot import build_snapshot, snapshot_to_mapping
from ky.storage.atomic import replace_bytes
from ky.storage.day_plan_store import DayPlanStore, StorageError, parse_day_plan
from ky.storage.route_store import RoutePlanStore
from ky.storage.review_shards import load_review_queue
from ky.timetable import timetable_for_workspace
from ky.workspace import Workspace, load_workspace

_ACTOR_RE = re.compile(r"^ai:[a-z0-9][a-z0-9._-]*$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize JSON for input hashing using the M19 byte-level contract."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _build_input_data(day: date, config: KaoyanConfig, workspace: Workspace) -> dict[str, Any]:
    from ky.pacing.port import settings_for_workspace

    review_items = load_review_queue(workspace.write_target("state.review_queue"))
    availability = availability_for_workspace(workspace)
    timetable = timetable_for_workspace(workspace)
    pacing_settings = settings_for_workspace(workspace)
    route_store = _registered_route_store(workspace)
    route = route_store.current() if route_store is not None else None
    day_budget = resolve_day_budget(
        day, config, availability, route, timetable, pacing_initial=pacing_settings,
    )
    plans_store = DayPlanStore(workspace.write_target("state.plans"))
    latched = latch_active(plans_store.freeze_events())
    freeze = assess_freeze(day, config, review_items, FreezePolicy(), latched=latched)
    snapshot = build_snapshot(config, review_items, today=day, workspace=workspace)
    clip_kwargs, allocation_kwargs = _day_clip_parameters(day_budget, freeze.frozen)
    if not freeze.frozen and day_budget.subject_review_quotas is not None:
        clip_kwargs["subject_review_quotas"] = day_budget.subject_review_quotas
    clip = select_daily_reviews(config, review_items, day, policy=ReviewPolicy(), **clip_kwargs)
    preflight_payload = preflight_to_mapping(
        config,
        clip,
        allocate_new_content(config, clip.new_learning_minutes, **allocation_kwargs),
    )
    preflight_payload.pop("config")
    if freeze.frozen:
        preflight_payload["freeze"] = freeze_to_mapping(freeze)
    return {
        "schema_version": 1,
        "kind": "planner_input",
        "day": day.isoformat(),
        "config": config_to_mapping(config),
        "state_snapshot": snapshot_to_mapping(snapshot),
        "review_clip": preflight_payload,
        "vocab": (
            {"delivered": snapshot.vocab.delivered, "remaining": snapshot.vocab.remaining}
            if snapshot.vocab is not None else None
        ),
        "default_daily_minutes": config.default_daily_minutes,
        "availability": (
            _availability_mapping(
                day_budget, settings_pacing_registered=pacing_settings is not None
            )
            if (availability is not None or timetable is not None
                or pacing_settings is not None) else None
        ),
        # The same RoutePlan object feeds the quotas above and this field: reading the store
        # twice could mix two revisions into one package (sol round 114).
        "route_plan": _route_plan_for_day(day, route),
    }


def _availability_mapping(
    day_budget: DayBudget, *, settings_pacing_registered: bool,
) -> dict[str, Any]:
    result = {"minutes": day_budget.total_minutes, "source": day_budget.total_source}
    if settings_pacing_registered:
        result["base_minutes"] = day_budget.base_minutes
        result["base_source"] = day_budget.base_source
    return result


def _day_clip_parameters(
    day_budget: DayBudget, frozen: bool,
) -> tuple[dict[str, Any], dict[str, str]]:
    if frozen:
        return {"daily_minutes_override": 0}, {"floor_policy": "drop_when_short"}
    if day_budget.total_source in {"availability", "timetable", "base"}:
        return (
            {"daily_minutes_override": day_budget.total_minutes},
            {"floor_policy": "drop_when_short"},
        )
    return {}, {}


def _route_plan_for_day(day: date, plan: RoutePlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    mapping = route_plan_to_mapping(plan)
    for phase in plan.phases:
        if phase.start <= day < phase.end_exclusive:
            return {
                "route_id": plan.route_id,
                "revision": plan.revision,
                "phase": mapping["phases"][phase.index],
            }
    return None


def _registered_route_store(workspace: Workspace) -> RoutePlanStore | None:
    # state.routes is optional (contracts/workspace.md); unregistered means "no route".
    if workspace.routes is None:
        return None
    return RoutePlanStore(workspace.write_target("state.routes"))


def route_planner_input_data(
    day: date, *, config_path: str | Path | None, workspace: Workspace,
) -> tuple[dict[str, Any], str]:
    """Build the deterministic route input package without writing it."""
    config = _workspace_config(config_path, workspace)
    review_items = load_review_queue(workspace.write_target("state.review_queue"))
    snapshot = build_snapshot(config, review_items, today=day, workspace=workspace)
    route_store = _registered_route_store(workspace)
    current = route_store.current() if route_store is not None else None
    data = {
        "schema_version": 1,
        "kind": "route_planner_input",
        "day": day.isoformat(),
        "config": config_to_mapping(config),
        "state_snapshot": snapshot_to_mapping(snapshot),
        "current_route": route_plan_to_mapping(current) if current is not None else None,
    }
    return data, hashlib.sha256(canonical_json_bytes(data)).hexdigest()


def _workspace_config(
    config_path: str | Path | None, workspace: Workspace,
) -> KaoyanConfig:
    if config_path is None:
        try:
            config_path = workspace.require("settings.exam_config")
        except ContractError as exc:
            raise ContractError(
                f"{exc}; pass --config or register settings.exam_config", "--config",
            ) from exc
    return load_config(config_path)


def planner_input_data(
    day: date, *, config_path: str | Path | None, workspace: Workspace,
) -> tuple[dict[str, Any], str]:
    """Build the package and return its full SHA-256 without writing it."""
    config = _workspace_config(config_path, workspace)
    data = _build_input_data(day, config, workspace)
    return data, hashlib.sha256(canonical_json_bytes(data)).hexdigest()


def create_planner_input(
    day: date, *, config_path: str | Path | None = None, workspace_path: str | Path | None = None,
) -> tuple[Path, str]:
    """Write today's deterministic package into the registered staging inputs directory."""
    workspace = load_workspace(workspace_path)
    data, digest = planner_input_data(day, config_path=config_path, workspace=workspace)
    target = workspace.write_target("staging") / "inputs" / f"{day.isoformat()}--{digest[:12]}.json"
    _resolve_staging_path(target, workspace.write_target("staging"), "inputs")
    target.parent.mkdir(parents=True, exist_ok=True)
    replace_bytes(target, canonical_json_bytes(data))
    return target, digest


def create_route_planner_input(
    day: date, *, config_path: str | Path | None = None,
    workspace_path: str | Path | None = None,
) -> tuple[Path, str]:
    """Write a deterministic route input package below registered staging/inputs."""
    workspace = load_workspace(workspace_path)
    data, digest = route_planner_input_data(
        day, config_path=config_path, workspace=workspace,
    )
    staging_root = workspace.write_target("staging")
    target = staging_root / "inputs" / f"route--{day.isoformat()}--{digest[:12]}.json"
    _resolve_staging_path(target, staging_root, "inputs")
    target.parent.mkdir(parents=True, exist_ok=True)
    replace_bytes(target, canonical_json_bytes(data))
    return target, digest


def _resolve_staging_path(
    path: Path, staging_root: Path, category: str, *, strict: bool = False,
    failure: str | None = None,
) -> Path:
    try:
        staging = staging_root.resolve(strict=False)
        category_root = (staging_root / category).resolve(strict=False)
        category_root.relative_to(staging)
        target = path.resolve(strict=strict)
        target.relative_to(category_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError(
            failure or f"planner {category} path resolves outside staging/{category}",
            path.as_posix(),
        ) from exc
    return target


def _proposal_header(
    raw: Mapping[str, Any], *, path: Path, kind: str, payload_key: str,
) -> tuple[str, str, object]:
    expected = {"schema_version", "kind", "actor", "input_hash", payload_key}
    if set(raw) != expected:
        unknown = sorted(set(raw) - expected)
        missing = sorted(expected - set(raw))
        detail = f"unknown field {unknown[0]!r}" if unknown else f"missing field {missing[0]!r}"
        raise ContractError(detail, path.as_posix())
    schema_version = raw["schema_version"]
    if type(schema_version) is not int or schema_version != 1:
        raise ContractError("schema_version must be integer 1", "schema_version")
    if raw["kind"] != kind:
        raise ContractError(f"expected kind {kind}", path.as_posix())
    actor = raw["actor"]
    if actor != "human" and (not isinstance(actor, str) or not _ACTOR_RE.fullmatch(actor)):
        raise ContractError("actor must be human or match ^ai:[a-z0-9][a-z0-9._-]*$", "actor")
    digest = raw["input_hash"]
    if not isinstance(digest, str) or not _HASH_RE.fullmatch(digest):
        raise ContractError("staged proposal requires a 64-character input_hash", "input_hash")
    return actor, digest, raw[payload_key]


def _load_proposal_mapping(path: Path) -> Mapping[str, Any]:
    try:
        raw = load_yaml_text(path.read_text(encoding="utf-8"), source=path.as_posix())
    except (OSError, UnicodeError, ContractError) as exc:
        raise ContractError(f"cannot read proposal: {exc}", path.as_posix()) from exc
    if not isinstance(raw, Mapping):
        raise ContractError("expected a mapping", path.as_posix())
    return raw


def _read_proposal(path: Path) -> tuple[dict[str, Any], Any]:
    raw = _load_proposal_mapping(path)
    _proposal_header(raw, path=path, kind="day_plan_proposal", payload_key="plan")
    plan = parse_day_plan(raw["plan"], f"{path.as_posix()}.plan")
    return dict(raw), plan


def _validate_staging_path(path: Path, staging_root: Path, category: str) -> None:
    target = _resolve_staging_path(
        path, staging_root, category, strict=True,
        failure=f"proposal must be under staging/{category}",
    )
    if not target.is_file():
        raise ContractError("proposal must be a file", path.as_posix())


def _validate_input_package(
    digest: str, plan_day: date, staging_root: Path,
) -> None:
    candidate = staging_root / "inputs" / f"{plan_day.isoformat()}--{digest[:12]}.json"
    outside = "input package must resolve under staging/inputs"
    _resolve_staging_path(staging_root / "inputs", staging_root, "inputs", failure=outside)
    if not candidate.is_file():
        raise ContractError("input package does not exist", candidate.as_posix())
    _resolve_staging_path(candidate, staging_root, "inputs", strict=True, failure=outside)
    package = _read_hashed_package(candidate, digest)
    if not isinstance(package, Mapping) or package.get("day") != plan_day.isoformat():
        raise ContractError("input package day does not match plan.day", candidate.as_posix())


def _read_hashed_package(path: Path, digest: str) -> object:
    try:
        package = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid input package: {exc}", path.as_posix()) from exc
    actual = hashlib.sha256(canonical_json_bytes(package)).hexdigest()
    if actual != digest:
        raise ContractError("input package hash mismatch", path.as_posix())
    return package


def _apply(
    plan: Any, *, actor: str, input_hash: str | None, store: DayPlanStore,
) -> Any:
    return store.write_day_plan(plan, actor=actor, input_hash=input_hash)


def apply_human_plan(path: str | Path, *, store: DayPlanStore) -> Any:
    """Wrap a legacy plan YAML as a human proposal and use the shared apply function."""
    proposal_path = Path(path)
    try:
        raw = load_yaml_text(
            proposal_path.read_text(encoding="utf-8"), source=proposal_path.as_posix(),
        )
    except (OSError, UnicodeError, ContractError) as exc:
        raise ContractError(f"cannot read plan: {exc}", proposal_path.as_posix()) from exc
    plan = parse_day_plan(raw, proposal_path.as_posix())
    return _apply(plan, actor="human", input_hash=None, store=store)


def apply_staged_proposal(
    path: str | Path, *, store: DayPlanStore, config_path: str | Path | None = None,
    workspace_path: str | Path | None = None,
) -> Any:
    """Validate staging provenance, reject stale inputs, then apply through M13."""
    workspace = load_workspace(workspace_path)
    staging_root = workspace.write_target("staging")
    proposal_path = Path(path)
    _validate_staging_path(proposal_path, staging_root, "day_plans")
    proposal, plan = _read_proposal(proposal_path)
    digest = proposal["input_hash"]
    if digest is not None:
        _validate_input_package(digest, plan.day, staging_root)
        _, current_digest = planner_input_data(
            plan.day, config_path=config_path, workspace=workspace,
        )
        if current_digest != digest:
            raise ContractError("输入已变化，请基于新输入包重新提案", proposal_path.as_posix())
    return _apply(plan, actor=proposal["actor"], input_hash=digest, store=store)


def reject_staging_plan_path(path: str | Path, workspace: Workspace | None) -> None:
    """Reject the human-plan shortcut when a registered staging path identifies it."""
    if workspace is None:
        return
    try:
        target = Path(path).resolve(strict=True)
        staging = workspace.write_target("staging").resolve(strict=False)
        target.relative_to(staging)
    except (OSError, RuntimeError, ValueError):
        return
    raise ContractError("--plan path must not be under staging", Path(path).as_posix())


def _apply_route_plan(
    plan: RoutePlan, *, actor: str, input_hash: str | None, store: RoutePlanStore,
) -> Any:
    return store.write_route_plan(plan, actor=actor, input_hash=input_hash)


def apply_human_route_plan(path: str | Path, *, store: RoutePlanStore) -> Any:
    """Parse a human route and use the same M19 route apply function as staging."""
    plan_path = Path(path)
    try:
        raw = load_yaml_text(plan_path.read_text(encoding="utf-8"), source=plan_path.as_posix())
    except (OSError, UnicodeError, ContractError) as exc:
        raise ContractError(f"cannot read route plan: {exc}", plan_path.as_posix()) from exc
    plan = parse_route_plan(raw, plan_path.as_posix())
    return _apply_route_plan(plan, actor="human", input_hash=None, store=store)


def _route_input_package(digest: str, staging_root: Path) -> tuple[Path, Mapping[str, Any]]:
    inputs_root = staging_root / "inputs"
    _resolve_staging_path(inputs_root, staging_root, "inputs")
    candidates = sorted(inputs_root.glob(f"route--*--{digest[:12]}.json"))
    matches: list[tuple[Path, Mapping[str, Any]]] = []
    for candidate in candidates:
        _resolve_staging_path(candidate, staging_root, "inputs", strict=True)
        try:
            package = json.loads(candidate.read_text(encoding="utf-8"))
            actual = hashlib.sha256(canonical_json_bytes(package)).hexdigest()
        except (
            OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, RecursionError,
        ):
            continue
        if actual != digest:
            continue
        if not isinstance(package, Mapping):
            raise ContractError("input package must be a mapping", candidate.as_posix())
        if package.get("kind") != "route_planner_input":
            raise ContractError("expected kind route_planner_input", candidate.as_posix())
        matches.append((candidate, package))
    if not matches:
        raise ContractError("route input package does not exist", inputs_root.as_posix())
    if len(matches) != 1:
        raise ContractError("route input package is ambiguous", inputs_root.as_posix())
    return matches[0]


def apply_staged_route_proposal(
    path: str | Path, *, store: RoutePlanStore, config_path: str | Path | None = None,
    workspace_path: str | Path | None = None,
) -> Any:
    """Validate route proposal provenance/freshness, then append through M13."""
    workspace = load_workspace(workspace_path)
    staging_root = workspace.write_target("staging")
    proposal_path = Path(path)
    _validate_staging_path(proposal_path, staging_root, "routes")
    raw = _load_proposal_mapping(proposal_path)
    actor, digest, route_raw = _proposal_header(
        raw, path=proposal_path, kind="route_proposal", payload_key="route",
    )
    plan = parse_route_plan(route_raw, f"{proposal_path.as_posix()}.route")
    if plan.stage1_input_hash != digest:
        raise ContractError("route.stage1_input_hash must equal input_hash", "stage1_input_hash")

    input_path, package = _route_input_package(digest, staging_root)
    day_value = package.get("day")
    if not isinstance(day_value, str):
        raise ContractError("route input package day must be an ISO date", input_path.as_posix())
    try:
        input_day = date.fromisoformat(day_value)
    except ValueError as exc:
        raise ContractError(
            "route input package day must be an ISO date", input_path.as_posix(),
        ) from exc
    if input_day.isoformat() != day_value:
        raise ContractError("route input package day must be an ISO date", input_path.as_posix())
    _, current_digest = route_planner_input_data(
        input_day, config_path=config_path, workspace=workspace,
    )
    if current_digest != digest:
        raise ContractError("输入已变化，请基于新输入包重新提案", proposal_path.as_posix())

    return _apply_route_plan(plan, actor=actor, input_hash=digest, store=store)
