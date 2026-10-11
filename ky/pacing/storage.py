"""M28 write-once report storage; see ``contracts/pacing_review.md`` section 3.

Public interfaces: ``report_path``, ``read_report``,
``read_report_with_digest``, and ``write_report_once``.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml

from ky.models import ContractError, load_yaml_text
from ky.planner.port import canonical_json_bytes


def report_path(plans_root: str | Path, cycle_end: str) -> Path:
    """Return the registered location for a cycle report."""
    return Path(plans_root) / "pacing" / f"report--{cycle_end}.yaml"


def _require_mapping(value: object, expected: set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ContractError("invalid report mapping", path)
    return value


def _require_nonnegative(value: object, path: str) -> None:
    if type(value) is not int or value < 0:
        raise ContractError("expected a non-negative integer", path)


def _require_iso_date(value: object, path: str) -> date:
    if not isinstance(value, str):
        raise ContractError("expected an ISO date", path)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("expected an ISO date", path) from exc
    if parsed.isoformat() != value:
        raise ContractError("expected an ISO date", path)
    return parsed


def read_report(path: str | Path) -> dict[str, Any]:
    """Read one saved report and verify its closed outer shape and digest."""
    file = Path(path)
    try:
        data = file.read_bytes()
        value = load_yaml_text(data.decode("utf-8"), source=file.as_posix())
    except OSError as exc:
        raise ContractError(f"cannot read report: {exc}", file.as_posix()) from exc
    except UnicodeError as exc:
        raise ContractError(f"report is not UTF-8: {exc}", file.as_posix()) from exc
    return _validate_report(value, file)


def _validate_report(value: object, file: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("report must be a mapping", file.as_posix())
    _validate_report_shape(value, file)
    _validate_report_body(value, file)
    _validate_report_integrity(value, file)
    return value


def _validate_report_shape(value: Mapping[str, Any], file: Path) -> None:
    if not isinstance(value, dict):
        raise ContractError("report must be a mapping", file.as_posix())
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ContractError("unsupported report schema_version", f"{file}.schema_version")
    expected = {"schema_version", "cycle", "generated_on", "base", "reference_minutes",
        "reference_source_note", "declared_minutes", "recorded_event_days", "study_minutes",
        "reviews", "reviews_unattributed", "duplicate_completion_ids", "backlog_observed",
        "freeze", "due_next", "previous", "sources", "report_hash"}
    if set(value) != expected:
        raise ContractError("report fields do not match schema", file.as_posix())
    _validate_cycle(value["cycle"], file)
    _require_iso_date(value["generated_on"], f"{file}.generated_on")


def _validate_cycle(raw: object, file: Path) -> None:
    cycle = _require_mapping(raw, {"start", "end", "days"}, f"{file}.cycle")
    cycle_start = _require_iso_date(cycle["start"], f"{file}.cycle.start")
    cycle_end = _require_iso_date(cycle["end"], f"{file}.cycle.end")
    _require_nonnegative(cycle["days"], f"{file}.cycle.days")
    if cycle_end < cycle_start or (cycle_end - cycle_start).days + 1 != cycle["days"]:
        raise ContractError("cycle dates and days disagree", f"{file}.cycle")


def _validate_report_body(value: Mapping[str, Any], file: Path) -> None:
    base = _require_mapping(value["base"], {"min", "max", "mean", "source_note"},
                            f"{file}.base")
    for key in ("min", "max", "mean"):
        _require_nonnegative(base[key], f"{file}.base.{key}")
    if not isinstance(base["source_note"], str):
        raise ContractError("source_note must be a string", f"{file}.base.source_note")
    _require_nonnegative(value["reference_minutes"], f"{file}.reference_minutes")
    if not isinstance(value["reference_source_note"], str):
        raise ContractError("expected a string", f"{file}.reference_source_note")
    for key in ("declared_minutes", "study_minutes"):
        block = _require_mapping(value[key], {"days", "sum"}, f"{file}.{key}")
        for field in ("days", "sum"):
            _require_nonnegative(block[field], f"{file}.{key}.{field}")
    _validate_report_statistics(value, file)


def _validate_report_statistics(value: Mapping[str, Any], file: Path) -> None:
    for key in ("recorded_event_days", "reviews_unattributed", "duplicate_completion_ids"):
        _require_nonnegative(value[key], f"{file}.{key}")
    for key in ("reviews", "due_next", "sources"):
        if not isinstance(value[key], dict):
            raise ContractError("expected a mapping", f"{file}.{key}")
    for subject, minutes in value["due_next"].items():
        if not isinstance(subject, str):
            raise ContractError("subject IDs must be strings", f"{file}.due_next")
        _require_nonnegative(minutes, f"{file}.due_next.{subject}")
    for subject, counts in value["reviews"].items():
        entry = _require_mapping(counts, {"completed", "correct", "partial", "incorrect",
            "none", "miss_ratio"}, f"{file}.reviews.{subject}")
        for field in ("completed", "correct", "partial", "incorrect", "none"):
            _require_nonnegative(entry[field], f"{file}.reviews.{subject}.{field}")
        ratio = entry["miss_ratio"]
        if ratio is not None and (type(ratio) not in {float, int} or not 0 <= ratio <= 1):
            raise ContractError("invalid miss_ratio", f"{file}.reviews.{subject}.miss_ratio")
    backlog = _require_mapping(value["backlog_observed"],
        {"observed_on", "total", "by_subject"}, f"{file}.backlog_observed")
    _require_iso_date(backlog["observed_on"], f"{file}.backlog_observed.observed_on")
    _require_nonnegative(backlog["total"], f"{file}.backlog_observed.total")
    if not isinstance(backlog["by_subject"], dict):
        raise ContractError("by_subject must be a mapping", f"{file}.backlog_observed")
    freeze = _require_mapping(value["freeze"], {"events", "latched_at_end"},
                              f"{file}.freeze")
    _require_nonnegative(freeze["events"], f"{file}.freeze.events")
    if type(freeze["latched_at_end"]) is not bool:
        raise ContractError("expected a boolean", f"{file}.freeze.latched_at_end")
    previous = value["previous"]
    if previous is not None:
        _require_mapping(previous, {"reviews", "backlog_observed", "study_minutes", "cycle",
                                    "report_hash"}, f"{file}.previous")
    if not isinstance(value["reference_source_note"], str):
        raise ContractError("expected a string", f"{file}.reference_source_note")
    

def _validate_report_integrity(value: Mapping[str, Any], file: Path) -> None:
    for source, digest in value["sources"].items():
        if not isinstance(source, str) or not isinstance(digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", digest
        ):
            raise ContractError("invalid source digest", f"{file}.sources")
    digest = value.get("report_hash")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ContractError("invalid report_hash", f"{file}.report_hash")
    payload = dict(value)
    payload.pop("report_hash")
    actual = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    if digest != actual:
        raise ContractError("report_hash does not match content", f"{file}.report_hash")


def read_report_with_digest(path: str | Path) -> tuple[dict[str, Any], str]:
    """Return a validated report and digest of the exact bytes parsed."""
    file = Path(path)
    try:
        data = file.read_bytes()
        value = load_yaml_text(data.decode("utf-8"), source=file.as_posix())
    except OSError as exc:
        raise ContractError(f"cannot read report: {exc}", file.as_posix()) from exc
    except UnicodeError as exc:
        raise ContractError(f"report is not UTF-8: {exc}", file.as_posix()) from exc
    checked = _validate_report(value, file)
    return checked, hashlib.sha256(data).hexdigest()


def write_report_once(path: str | Path, report: Mapping[str, Any]) -> dict[str, Any]:
    """Publish YAML with reread validation and an atomic no-overwrite hard link."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = yaml.safe_dump(dict(report), allow_unicode=True, sort_keys=False,
                          default_flow_style=False).encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=".pacing-report-", suffix=".tmp",
                                     dir=target.parent)
    temporary = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        checked = read_report(temporary)
        if checked != dict(report):
            raise ContractError("temporary report changed during YAML round-trip",
                                temporary.as_posix())
        try:
            os.link(temporary, target)
        except FileExistsError:
            return read_report(target)
        return checked
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
