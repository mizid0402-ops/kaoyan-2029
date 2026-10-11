"""M29 restage and apply workflows for ``contracts/timetable_import.md`` §§3 and 5.

Public interfaces: :class:`RestageResult`, :class:`ApplyResult`, :func:`restage`, and
:func:`apply_staging`.
"""

from __future__ import annotations

import hashlib
import re
import os
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Mapping

import yaml

from ky.models import ContractError
from ky.storage.atomic import replace_bytes
from ky.timetable import (
    Semester,
    Timetable,
    TimetableCalendar,
    build_calendar,
    load_referenced_schools,
    semester_to_mapping,
    timetable_for_workspace,
    timetable_from_mapping,
    timetable_to_mapping,
)
from ky.timetable_io.isolation import Isolation, check_isolated_path
from ky.timetable_io.staging import (
    StagedSemester,
    publish_staging,
    read_staging,
    staging_hash12,
)
from ky.workspace import Workspace

_STAGE_NAME_RE = re.compile(r"^import--([0-9a-f]{12})\.yaml$")


@dataclass(frozen=True)
class RestageResult:
    path: Path
    published: bool
    changes: tuple[str, ...]


@dataclass(frozen=True)
class ApplyResult:
    status: str
    backup: Path | None
    changes: tuple[str, ...]


def _mapping_yaml(data: bytes, source: Path) -> object:
    try:
        text = data.decode("utf-8")
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        if node is not None:
            _check_duplicate_nodes(node, "")
        return yaml.load(text, Loader=yaml.SafeLoader)
    except UnicodeError as exc:
        raise ContractError(f"invalid UTF-8: {exc}", source.as_posix()) from exc
    except yaml.YAMLError as exc:
        raise ContractError(f"invalid YAML: {exc}", source.as_posix()) from exc


def _check_duplicate_nodes(node: yaml.Node, path: str) -> None:
    if isinstance(node, yaml.MappingNode):
        seen: set[str] = set()
        for key_node, value_node in node.value:
            key = key_node.value if isinstance(key_node, yaml.ScalarNode) else None
            field = f"{path}.{key}" if path else str(key)
            if key is not None and key in seen:
                raise ContractError("duplicate field", field)
            if key is not None:
                seen.add(key)
            _check_duplicate_nodes(value_node, field)
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            _check_duplicate_nodes(item, f"{path}[{index}]")


def _read_current_timetable(workspace: Workspace) -> tuple[Timetable, bytes, Path]:
    if workspace.timetable is None:
        raise ContractError("not registered", "state.timetable")
    path = workspace.write_target("state.timetable")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"cannot read timetable: {exc}", "state.timetable") from exc
    timetable = timetable_from_mapping(_mapping_yaml(data, path))
    return timetable, data, path


def _courses(semester: Semester) -> dict[tuple[object, ...], set[int]]:
    result: dict[tuple[object, ...], set[int]] = {}
    for course in semester.courses:
        identity = (
            course.name,
            course.weekday,
            course.first_period,
            course.last_period,
        )
        weeks = result.setdefault(identity, set())
        weeks.update(course.weeks)
    return result


def _week_list(weeks: set[int]) -> str:
    return ",".join(map(str, sorted(weeks)))


def _exception_rows(semester: Semester) -> list[object]:
    mapping = semester_to_mapping(semester)
    return list(mapping["exceptions"])


def _course_changes(old: Semester | None, new: Semester) -> list[str]:
    current = {} if old is None else _courses(old)
    candidate = _courses(new)
    result: list[str] = []
    for key in sorted(candidate.keys() - current.keys()):
        result.append(f"新增课程 {key}: 周次 {_week_list(candidate[key])}")
    for key in sorted(current.keys() - candidate.keys()):
        result.append(f"删除课程 {key}: 周次 {_week_list(current[key])}")
    for key in sorted(candidate.keys() & current.keys()):
        if candidate[key] != current[key]:
            result.append(
                f"课程周次变化 {key}: {_week_list(current[key])} -> "
                f"{_week_list(candidate[key])}"
            )
    return result


def _exception_changes(old: Semester | None, new: Semester) -> list[str]:
    before = [] if old is None else _exception_rows(old)
    after = _exception_rows(new)
    return [f"新增例外 {item}" for item in after if item not in before] + [
        f"删除例外 {item}" for item in before if item not in after
    ]


def _semester_changes(old: Semester | None, new: Semester) -> tuple[str, ...]:
    if old is None:
        return (
            f"新增学期：{new.label}，学校 {new.school}，"
            f"第 1 周 {new.week1_monday.isoformat()}，共 {new.weeks} 周，"
            f"课程 {len(new.courses)} 门，例外 {len(new.exceptions)} 项",
            *_course_changes(None, new),
            *_exception_changes(None, new),
        )
    changes = _course_changes(old, new) + _exception_changes(old, new)
    if old.school != new.school:
        changes.append(f"学校变化：{old.school} -> {new.school}")
    if old.week1_monday != new.week1_monday:
        changes.append(
            f"第 1 周变化：{old.week1_monday.isoformat()} -> {new.week1_monday.isoformat()}"
        )
    if old.weeks != new.weeks:
        changes.append(f"周数变化：{old.weeks} -> {new.weeks}")
    return tuple(changes or ["无差异"])


def _label_semester(timetable: Timetable | None, label: str) -> Semester | None:
    if timetable is None:
        return None
    return next((item for item in timetable.semesters if item.label == label), None)


def restage(
    workspace: Workspace, source: str | Path, isolation: Isolation
) -> RestageResult:
    candidate_path = Path(source)
    staged, _ = read_staging(candidate_path)
    digest = staging_hash12(staged)
    current_calendar = timetable_for_workspace(workspace)
    current = None if current_calendar is None else current_calendar.timetable
    old = _label_semester(current, staged.semester.label)
    changes = _semester_changes(old, staged.semester)
    match = _STAGE_NAME_RE.fullmatch(candidate_path.name)
    if match is not None and match.group(1) == digest:
        return RestageResult(candidate_path, False, changes)
    target, published = publish_staging(workspace, staged, isolation)
    return RestageResult(target, published, changes)


def _staging_path(workspace: Workspace, value: str | Path) -> Path:
    staging_root = workspace.write_target("staging").resolve(strict=True)
    if not staging_root.is_dir():
        raise ContractError("staging path is not a directory", "staging")
    staging_dir = staging_root / "timetables"
    try:
        resolved_dir = staging_dir.resolve(strict=True)
        resolved_dir.relative_to(staging_root)
    except (OSError, ValueError) as exc:
        raise ContractError("staging timetables directory is invalid", "staging") from exc
    if not resolved_dir.is_dir():
        raise ContractError("staging timetables path is not a directory", "staging")
    source = Path(value)
    if not source.is_absolute():
        source = Path.cwd() / source
    try:
        resolved_file = source.resolve(strict=True)
        resolved_file.relative_to(resolved_dir)
    except (OSError, ValueError) as exc:
        raise ContractError("staging file is outside timetables staging", "staging") from exc
    if not resolved_file.is_file():
        raise ContractError("staging path is not a file", "staging")
    if _STAGE_NAME_RE.fullmatch(resolved_file.name) is None:
        raise ContractError("invalid staging filename", "staging")
    return resolved_file


def _validated_staging(
    workspace: Workspace, value: str | Path, isolation: Isolation
) -> tuple[StagedSemester, Path]:
    path = _staging_path(workspace, value)
    check_isolated_path(isolation, path)
    staged, data = read_staging(path)
    match = _STAGE_NAME_RE.fullmatch(path.name)
    if match is None or match.group(1) != staging_hash12(staged):
        raise ContractError("staging hash does not match filename", "hash12")
    return staged, path


def _merge_semester(current: Timetable, candidate: Semester) -> Timetable:
    semesters = list(current.semesters)
    existing_index = next(
        (index for index, item in enumerate(semesters) if item.label == candidate.label),
        None,
    )
    if existing_index is None:
        semesters.append(candidate)
    else:
        semesters[existing_index] = candidate
    return timetable_from_mapping(
        {
            "schema_version": 1,
            "rules": timetable_to_mapping(current)["rules"],
            "semesters": [semester_to_mapping(item) for item in semesters],
        }
    )


def _validate_merged(workspace: Workspace, merged: Timetable) -> TimetableCalendar:
    school_ids = tuple(dict.fromkeys(item.school for item in merged.semesters))
    schools = load_referenced_schools(workspace, school_ids)
    return build_calendar(merged, schools)


def _find_old(current: Timetable, label: str) -> Semester | None:
    return next((item for item in current.semesters if item.label == label), None)


def _same_semester(left: Semester, right: Semester) -> bool:
    return semester_to_mapping(left) == semester_to_mapping(right)


def _backup_path(timetable_path: Path, original: bytes) -> Path:
    digest = hashlib.sha256(original).hexdigest()[:12]
    return timetable_path.with_name(f"{timetable_path.stem}.previous-{digest}.yaml")


def _publish_backup(path: Path, original: bytes, isolation: Isolation) -> None:
    check_isolated_path(isolation, path)
    if path.exists():
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise ContractError(f"cannot read backup: {exc}", path.as_posix()) from exc
        if existing == original:
            return
        raise ContractError("backup already exists with different content", path.as_posix())
    path.parent.mkdir(parents=True, exist_ok=True)
    _publish_bytes_once(path, original, isolation)


def _publish_bytes_once(path: Path, data: bytes, isolation: Isolation) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    check_isolated_path(isolation, temporary)
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
        if temporary.read_bytes() != data:
            raise ContractError("backup temporary bytes changed", temporary.as_posix())
        check_isolated_path(isolation, temporary)
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise
        except OSError as exc:
            raise ContractError(f"cannot publish backup: {exc}", path.as_posix()) from exc
    finally:
        temporary.unlink(missing_ok=True)


def _first_week_grid(
    calendar: TimetableCalendar, semester: Semester
) -> tuple[str, ...]:
    monday = semester.week1_monday
    schedules = [calendar.day(monday + timedelta(days=offset), 0) for offset in range(7)]
    weekdays = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    rows = ["第 1 周课程网格：" + " | ".join(weekdays)]
    school = calendar.schools[semester.school]
    for number, period in school.periods.items():
        cells = []
        for schedule in schedules:
            names = [
                name
                for name, first, last, _start, _end in schedule.classes
                if first <= number <= last
            ]
            cells.append("/".join(names) or "-")
        marker = "*" if period.unconfirmed else ""
        rows.append(f"{number}{marker} | " + " | ".join(cells))
    return tuple(rows)


def _apply_changes(
    old: Semester | None,
    new: Semester,
    calendar: TimetableCalendar,
) -> tuple[str, ...]:
    if old is None:
        title = _semester_changes(None, new)
    else:
        title = (f"替换学期：{new.label}", *_semester_changes(old, new))
    return (*title, *_first_week_grid(calendar, new))


def apply_staging(
    workspace: Workspace,
    source: str | Path,
    isolation: Isolation,
    *,
    replace: bool = False,
    dry_run: bool = False,
) -> ApplyResult:
    staged, _ = _validated_staging(workspace, source, isolation)
    current, original, timetable_path = _read_current_timetable(workspace)
    merged = _merge_semester(current, staged.semester)
    calendar = _validate_merged(workspace, merged)
    old = _find_old(current, staged.semester.label)
    if old is not None and _same_semester(old, staged.semester):
        return ApplyResult("already_applied", None, ("已应用",))
    if old is not None and not replace:
        raise ContractError("label already exists; pass --replace", "semester.label")
    changes = _apply_changes(old, staged.semester, calendar)
    backup = _backup_path(timetable_path, original)
    changes = (*changes, f"备份：{backup.name}", "规范写出会去掉原文件注释")
    if dry_run:
        return ApplyResult("dry_run", None, changes)
    check_isolated_path(isolation, timetable_path)
    _publish_backup(backup, original, isolation)
    try:
        timetable_bytes = yaml.safe_dump(
            timetable_to_mapping(merged),
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).encode("utf-8")
        replace_bytes(
            timetable_path, timetable_bytes,
            check_temporary=lambda temporary: check_isolated_path(isolation, temporary),
        )
    except OSError as exc:
        raise ContractError(f"cannot replace timetable: {exc}", "state.timetable") from exc
    return ApplyResult("applied", backup, changes)
