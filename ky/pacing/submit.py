"""M28 pacing proposal validation, intent recovery, and route publication; see §6–§7 of
``contracts/pacing_review.md``.

Public interface: :func:`pacing_submit_main`. The module owns submission guardrails and recovery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml

from ky.availability import availability_for_workspace
from ky.freeze import FreezePolicy, assess_freeze, latch_active
from ky.models import ContractError, load_config, load_yaml_text
from ky.pacing.input import pacing_input_from_snapshot
from ky.pacing.port import PacingSettings, apply_pacing, load_settings_source
from ky.pacing.storage import report_path
from ky.planner.port import canonical_json_bytes
from ky.schedule.budget import daily_base_minutes, hard_review_cap_minutes
from ky.schedule.planning import RoutePlan, parse_route_plan, route_plan_to_mapping
from ky.storage.day_plan_store import DayPlanStore, StorageError
from ky.storage.route_store import RoutePlanStore
from ky.storage.review_shards import load_review_queue
from ky.timetable import timetable_for_workspace
from ky.workspace import load_workspace

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ACTOR_RE = re.compile(r"^ai:[a-z0-9][a-z0-9._-]*$")
_PROPOSAL_REQUIRED_KEYS = {
    "schema_version", "kind", "actor", "input_hash", "effective_from",
    "base_daily_minutes", "review_minutes", "rationale",
}
_PROPOSAL_KEYS = _PROPOSAL_REQUIRED_KEYS | {"notes"}
_INTENT_KEYS = {
    "schema_version", "report_hash", "input_hash", "actor", "proposal",
    "proposal_sha256", "base_revision", "target_revision", "b0", "route",
    "route_sha256",
}


def _digest(value: object, path: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ContractError("expected lowercase SHA-256", path)
    return value


def _read_yaml_mapping(path: Path, kind: str) -> dict[str, Any]:
    try:
        raw = load_yaml_text(path.read_text(encoding="utf-8"), source=path.as_posix())
    except (OSError, UnicodeError, ContractError) as exc:
        raise ContractError(f"cannot read {kind}: {exc}", path.as_posix()) from exc
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise ContractError("expected a string-key mapping", path.as_posix())
    return raw


def _proposal(path: Path) -> dict[str, Any]:
    value = _read_yaml_mapping(path, "pacing proposal")
    if not _PROPOSAL_REQUIRED_KEYS <= set(value) or set(value) - _PROPOSAL_KEYS:
        raise ContractError("proposal fields do not match schema", path.as_posix())
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ContractError("schema_version must be integer 1", "schema_version")
    if value["kind"] != "pacing_proposal":
        raise ContractError("expected kind pacing_proposal", path.as_posix())
    actor = value["actor"]
    if actor != "human" and (not isinstance(actor, str) or not _ACTOR_RE.fullmatch(actor)):
        raise ContractError("invalid actor", "actor")
    _digest(value["input_hash"], "input_hash")
    # AI proposals follow the spec example and write an unquoted YAML date; normalise it
    # once here so hashing, the intent and recovery all see the same ISO string.
    if type(value["effective_from"]) is date:
        value["effective_from"] = value["effective_from"].isoformat()
    _iso_date(value["effective_from"], "effective_from")
    _nonnegative_int(value["base_daily_minutes"], "base_daily_minutes")
    reviews = value["review_minutes"]
    if not isinstance(reviews, dict) or any(not isinstance(k, str) for k in reviews):
        raise ContractError("review_minutes must be a mapping", "review_minutes")
    for subject, minutes in reviews.items():
        _nonnegative_int(minutes, f"review_minutes.{subject}")
    if not isinstance(value["rationale"], list) or not value["rationale"]:
        raise ContractError("rationale must be a non-empty list", "rationale")
    for index, item in enumerate(value["rationale"]):
        if (not isinstance(item, dict) or not isinstance(item.get("claim"), str)
                or not item["claim"]):
            raise ContractError("rationale claim is required", f"rationale[{index}].claim")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence or any(
            not isinstance(path, str) for path in evidence
        ):
            raise ContractError("evidence must be a non-empty path list",
                                f"rationale[{index}].evidence")
    if "notes" in value and not isinstance(value["notes"], str):
        raise ContractError("notes must be a string", "notes")
    return value


def _iso_date(value: object, path: str) -> date:
    if not isinstance(value, str):
        raise ContractError("expected ISO date", path)
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("expected ISO date", path) from exc
    if result.isoformat() != value:
        raise ContractError("expected ISO date", path)
    return result


def _nonnegative_int(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ContractError("expected non-negative integer", path)
    return value


def _find_input(staging: Path, input_hash: str) -> tuple[Path, dict[str, Any], date]:
    candidates = sorted((staging / "inputs").glob(f"pacing--*--{input_hash[:12]}.json"))
    for path in candidates:
        try:
            import json
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        if not isinstance(value, Mapping):
            continue
        actual = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
        if actual != input_hash:
            continue
        report = value.get("report")
        if not isinstance(report, Mapping) or not isinstance(report.get("cycle"), Mapping):
            continue
        end = _iso_date(report["cycle"].get("end"), "report.cycle.end")
        if path.name != f"pacing--{end.isoformat()}--{input_hash[:12]}.json":
            continue
        return path, dict(value), end
    raise ContractError("matching pacing input package does not exist or is invalid",
                        "input_hash")


def _staging_proposal(path: Path, staging: Path) -> None:
    try:
        root = staging.resolve(strict=False)
        category = (staging / "pacing").resolve(strict=False)
        category.relative_to(root)
        target = path.resolve(strict=True)
        target.relative_to(category)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError("proposal must be under staging/pacing", path.as_posix()) from exc
    if not target.is_file():
        raise ContractError("proposal must be a file", path.as_posix())


def _intent_path(workspace, end: date) -> Path:
    return workspace.plans / "pacing" / f"applied--{end.isoformat()}.yaml"


def _intent_mapping(raw: object, path: Path) -> tuple[dict[str, Any], RoutePlan]:
    if not isinstance(raw, dict) or set(raw) != _INTENT_KEYS:
        raise ContractError("intent fields do not match schema", path.as_posix())
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ContractError("schema_version must be integer 1", path.as_posix())
    _digest(raw["report_hash"], "report_hash")
    input_hash = _digest(raw["input_hash"], "input_hash")
    actor = raw["actor"]
    if actor != "human" and (not isinstance(actor, str) or not _ACTOR_RE.fullmatch(actor)):
        raise ContractError("invalid actor", "actor")
    if not isinstance(raw["proposal"], dict):
        raise ContractError("proposal must be a mapping", "proposal")
    proposal = raw["proposal"]
    if proposal.get("actor") != actor or proposal.get("input_hash") != input_hash:
        raise ContractError("outer actor/input_hash differs from proposal", path.as_posix())
    proposal_sha = hashlib.sha256(canonical_json_bytes(proposal)).hexdigest()
    if _digest(raw["proposal_sha256"], "proposal_sha256") != proposal_sha:
        raise ContractError("proposal_sha256 mismatch", "proposal_sha256")
    base = _nonnegative_int(raw["base_revision"], "base_revision")
    target = _nonnegative_int(raw["target_revision"], "target_revision")
    if target != base + 1:
        raise ContractError("target_revision must equal base_revision + 1", "target_revision")
    _nonnegative_int(raw["b0"], "b0")
    route = parse_route_plan(raw["route"], f"{path.as_posix()}.route")
    if route.revision != target:
        raise ContractError("route.revision differs from target_revision", "route.revision")
    if route.stage1_input_hash != input_hash:
        raise ContractError("route.stage1_input_hash differs from input_hash", "route")
    route_sha = hashlib.sha256(canonical_json_bytes(route_plan_to_mapping(route))).hexdigest()
    if _digest(raw["route_sha256"], "route_sha256") != route_sha:
        raise ContractError("route_sha256 mismatch", "route_sha256")
    return raw, route


def _publish_intent(path: Path, intent: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(dict(intent), allow_unicode=True, sort_keys=False).encode("utf-8")
    fd, name = tempfile.mkstemp(prefix=".pacing-intent-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        checked, _ = _intent_mapping(_read_yaml_mapping(temporary, "intent"), temporary)
        if checked != dict(intent):
            raise ContractError("temporary intent changed during YAML round-trip",
                                temporary.as_posix())
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise ContractError("submission intent already exists", path.as_posix())
    finally:
        temporary.unlink(missing_ok=True)


def _workspace_snapshot(workspace, config_path: Path | None, settings: PacingSettings, day: date):
    config = load_config(config_path or workspace.require("settings.exam_config"))
    availability = availability_for_workspace(workspace)
    timetable = timetable_for_workspace(workspace)
    route_store = RoutePlanStore(workspace.write_target("state.routes"))
    route_read = route_store.read_state_sources()
    route = route_read.route
    plans = DayPlanStore(workspace.write_target("state.plans"))
    queue = load_review_queue(workspace.write_target("state.review_queue"))
    return config, availability, timetable, route_store, route, plans, queue


def _check_evidence(proposal: Mapping[str, Any], package: Mapping[str, Any]) -> None:
    report = package.get("report")
    if not isinstance(report, Mapping):
        raise ContractError("input report is invalid", "report")
    for index, row in enumerate(proposal["rationale"]):
        for evidence in row["evidence"]:
            if not evidence.startswith("report."):
                raise ContractError("evidence must address the input report",
                                    f"rationale[{index}].evidence")
            cursor: Any = package
            for component in evidence.split("."):
                if not isinstance(cursor, Mapping) or component not in cursor:
                    raise ContractError("evidence path does not exist in input package",
                                        f"rationale[{index}].evidence")
                cursor = cursor[component]


def _validate_guardrails(proposal, settings, package, cycle_end, today, snapshot):
    config, availability, timetable, route_store, route, plans, queue = snapshot
    report = package["report"]
    report_hash = report.get("report_hash")
    _digest(report_hash, "report.report_hash")
    effective = _iso_date(proposal["effective_from"], "effective_from")
    b0, _ = daily_base_minutes(effective, config, route, settings)
    candidate_base = proposal["base_daily_minutes"]
    if not settings.minimum <= candidate_base <= settings.maximum:
        raise ContractError("base_daily_minutes outside configured range", "base_daily_minutes")
    if abs(candidate_base - b0) > settings.max_step_minutes:
        raise ContractError("base change exceeds max_step_minutes", "base_daily_minutes")
    expected_subjects = {subject.subject_id for subject in config.active_subjects()}
    reviews = proposal["review_minutes"]
    if set(reviews) != expected_subjects:
        raise ContractError("review_minutes keys must match active subjects", "review_minutes")
    if sum(reviews.values()) > hard_review_cap_minutes(
        candidate_base, config.hard_max_ratio
    ):
        raise ContractError("review_minutes exceed the hard daily cap", "review_minutes")
    if effective <= cycle_end or effective < today or effective >= settings.exam_date:
        raise ContractError("effective_from must be > D, >= T, and < exam_date",
                            "effective_from")
    if route is not None and effective >= route.target_exam_date:
        raise ContractError("effective_from must precede route target exam date",
                            "effective_from")
    frozen = assess_freeze(today, config, queue, FreezePolicy(),
                           latched=latch_active(plans.freeze_events()))
    if frozen.frozen:
        raise ContractError("pacing proposal is not accepted while frozen", "freeze")
    return report_hash, b0, route


def _route_state(store: RoutePlanStore, intent_path: Path,
                 raw_proposal: Mapping[str, Any], package: Mapping[str, Any],
                 today: date, *, dry_run: bool) -> int:
    intent_raw = _read_yaml_mapping(intent_path, "intent")
    intent, intent_route = _intent_mapping(intent_raw, intent_path)
    saved_proposal = _proposal_mapping(intent["proposal"], intent_path)
    if saved_proposal != intent["proposal"]:
        raise ContractError("stored proposal shape is invalid", intent_path.as_posix())
    if package["report"].get("report_hash") != intent["report_hash"]:
        raise ContractError("intent report_hash differs from input package", "report_hash")
    context = store.read_revision_context(intent["target_revision"])
    applied = (
        context.route is not None
        and context.input_hash == intent["input_hash"]
        and hashlib.sha256(canonical_json_bytes(
            route_plan_to_mapping(context.route))).hexdigest() == intent["route_sha256"]
    )
    if applied:
        suffix = "（dry-run）" if dry_run else ""
        print(f"本报告已有提交（修订 {intent['target_revision']}），实际应用如下；"
              f"不发布{suffix}")
        if context.current_revision > intent["target_revision"]:
            print(f"这是历史应用：当前路线已是修订 {context.current_revision}，以当前路线为准")
        _print_change_summary(
            intent["proposal"], intent["b0"], _package_route(package), intent_route,
            package["settings"], package,
        )
        actual_hash = hashlib.sha256(canonical_json_bytes(raw_proposal)).hexdigest()
        if actual_hash != intent["proposal_sha256"]:
            print("本次文件未被采用")
        return 0
    if context.current_revision == intent["base_revision"]:
        if dry_run:
            print("dry-run：将恢复提交（不写任何文件）")
        else:
            print("正在恢复提交")
        _print_change_summary(
            intent["proposal"], intent["b0"], _package_route(package), intent_route,
            package["settings"], package,
        )
        if dry_run:
            print(yaml.safe_dump(route_plan_to_mapping(intent_route),
                                 allow_unicode=True, sort_keys=False), end="")
        else:
            try:
                store.write_route_plan(intent_route, actor=intent["actor"],
                                       input_hash=intent["input_hash"])
            except (StorageError, ContractError, OSError) as exc:
                _print_publish_failure(exc)
                return 2
            print("已完成上次中断的提交")
        _past_effective_warning(intent["proposal"], today)
        return 0
    print("历史应用；不发布。若需调整，请手动使用 ky route submit --plan。", file=sys.stderr)
    return 2


def _proposal_mapping(raw: object, path: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ContractError("proposal must be a mapping", path.as_posix())
    # A stored intent keeps the already validated proposal mapping as an immutable record.
    if not _PROPOSAL_REQUIRED_KEYS <= set(raw) or set(raw) - _PROPOSAL_KEYS:
        raise ContractError("proposal fields do not match schema", path.as_posix())
    return raw


def _past_effective_warning(proposal: Mapping[str, Any], today: date) -> None:
    effective = _iso_date(proposal["effective_from"], "effective_from")
    if effective < today:
        print("生效日已过，过去的日子按新路线重算的只是参考值，已落盘的日计划与记录不变")


def _package_route(package: Mapping[str, Any]) -> RoutePlan | None:
    raw = package.get("current_route")
    return None if raw is None else parse_route_plan(raw, "current_route")


def _evidence_value(package: Mapping[str, Any], path: str) -> Any:
    value: Any = package
    for component in path.split("."):
        if not isinstance(value, Mapping) or component not in value:
            raise ContractError("evidence path does not exist", path)
        value = value[component]
    return value


def _old_review_minutes(route: RoutePlan | None, effective: date) -> Mapping[str, int]:
    if route is None:
        return {}
    phase = next((item for item in route.phases
                  if item.start <= effective < item.end_exclusive), None)
    return {} if phase is None else phase.review_minutes


def _print_change_summary(
    proposal: Mapping[str, Any], b0: int, old_route: RoutePlan | None,
    candidate: RoutePlan, settings: Mapping[str, Any], package: Mapping[str, Any],
) -> None:
    effective = _iso_date(proposal["effective_from"], "effective_from")
    print(f"effective_from: {effective.isoformat()}")
    print(f"base: {b0} -> {proposal['base_daily_minutes']}")
    old_minutes = _old_review_minutes(old_route, effective)
    subjects = sorted(set(old_minutes) | set(proposal["review_minutes"]))
    for subject in subjects:
        old_value = old_minutes.get(subject, "-")
        new_value = proposal["review_minutes"].get(subject, "-")
        print(f"review_minutes.{subject}: {old_value} -> {new_value}")
    phase = next((item for item in candidate.phases
                  if item.start <= effective < item.end_exclusive), None)
    if phase is None:
        raise ContractError("candidate route has no affected phase", "route")
    print(f"调整在 {phase.end_exclusive.isoformat()} 日阶段结束后失效")
    settings_exam_date = _iso_date(settings.get("exam_date"), "settings.exam_date")
    if old_route is None or settings_exam_date <= old_route.target_exam_date:
        limit, source = settings_exam_date, "设置 exam_date"
    else:
        limit, source = old_route.target_exam_date, "路线 target_exam_date"
    print(f"生效日上限：{limit.isoformat()}（取自{source}）")
    print("有课表的日子，M8 仍会按当日容量缩放复习配额")
    for row in proposal["rationale"]:
        print(f"rationale: {row['claim']}")
        for evidence_path in row["evidence"]:
            value = json.dumps(_evidence_value(package, evidence_path), ensure_ascii=False)
            print(f"evidence: {evidence_path} = {value}")


def _print_publish_failure(exc: Exception) -> None:
    print(f"contract violation: {exc}", file=sys.stderr)
    print("提交意图已保存：重跑同一命令完成提交", file=sys.stderr)


def _submit_new(path: Path, proposal: Mapping[str, Any], package: Mapping[str, Any],
                input_path: Path, end: date, today: date, workspace, *, dry_run: bool) -> int:
    if workspace.pacing is None:
        raise ContractError("settings.pacing is not registered", "settings.pacing")
    settings, _ = load_settings_source(str(workspace.pacing))
    _check_evidence(proposal, package)
    snapshot = _workspace_snapshot(workspace, None, settings, today)
    fresh, digest = pacing_input_from_snapshot(
        end, today, workspace=workspace, settings=settings, config=snapshot[0],
        availability=snapshot[1], timetable=snapshot[2], route=snapshot[4],
    )
    if digest != proposal["input_hash"]:
        raise ContractError("input is stale; regenerate the pacing package", path.as_posix())
    if canonical_json_bytes(package) != canonical_json_bytes(fresh):
        raise ContractError("input package is no longer current", input_path.as_posix())
    report_hash, b0, route = _validate_guardrails(
        proposal, settings, package, end, today, snapshot,
    )
    proposed_route = apply_pacing(route, proposal, settings, end)
    route_mapping = route_plan_to_mapping(proposed_route)
    base_revision = route.revision if route is not None else 0
    intent = {
        "schema_version": 1,
        "report_hash": report_hash,
        "input_hash": proposal["input_hash"],
        "actor": proposal["actor"],
        "proposal": dict(proposal),
        "proposal_sha256": hashlib.sha256(canonical_json_bytes(proposal)).hexdigest(),
        "base_revision": base_revision,
        "target_revision": base_revision + 1,
        "b0": b0,
        "route": route_mapping,
        "route_sha256": hashlib.sha256(canonical_json_bytes(route_mapping)).hexdigest(),
    }
    if dry_run:
        print("new submission (dry-run; no files written)")
    _print_change_summary(proposal, b0, route, proposed_route,
                          package["settings"], package)
    if dry_run:
        print(yaml.safe_dump(route_mapping, allow_unicode=True, sort_keys=False), end="")
        return 0
    intent_path = _intent_path(workspace, end)
    _publish_intent(intent_path, intent)
    try:
        snapshot[3].write_route_plan(proposed_route, actor=proposal["actor"],
                                     input_hash=proposal["input_hash"])
    except (StorageError, ContractError, OSError) as exc:
        _print_publish_failure(exc)
        return 2
    print(f"submitted: {proposed_route.route_id} revision {proposed_route.revision}")
    _past_effective_warning(proposal, today)
    return 0


def pacing_submit_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="py -m ky pacing submit")
    parser.add_argument("--from-staging", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--today")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    try:
        today = _iso_date(args.today, "--today") if args.today else date.today()
        workspace = load_workspace(None)
        staging = workspace.write_target("staging")
        proposal_path = Path(args.from_staging)
        _staging_proposal(proposal_path, staging)
        proposal = _proposal(proposal_path)
        input_path, package, end = _find_input(staging, proposal["input_hash"])
        intent_path = _intent_path(workspace, end)
        route_store = RoutePlanStore(workspace.write_target("state.routes"))
        if intent_path.exists():
            return _route_state(route_store, intent_path, proposal, package, today,
                                dry_run=args.dry_run)
        return _submit_new(proposal_path, proposal, package, input_path, end, today,
                           workspace, dry_run=args.dry_run)
    except (ContractError, StorageError, OSError, UnicodeError, ValueError,
            yaml.YAMLError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
