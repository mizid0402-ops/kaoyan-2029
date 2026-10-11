"""M18 YAML and scalar validation helpers for ``contracts/timetable.md``."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Mapping

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from ky.models import ContractError, load_yaml_text

_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_TIME_RE = re.compile(r"^[0-9]{2}:[0-9]{2}$")
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _child_path(path: str, key: object) -> str:
    part = str(key)
    return f"{path}.{part}" if path else part


def _node_key(node: Node) -> tuple[str, str] | tuple[str, int, int]:
    if isinstance(node, ScalarNode):
        return node.tag, node.value
    return node.tag, node.start_mark.index, node.end_mark.index


def _check_duplicate_keys(node: Node, path: str, ancestors: frozenset[int]) -> None:
    if id(node) in ancestors:
        return
    nested = ancestors | {id(node)}
    if isinstance(node, MappingNode):
        seen: set[object] = set()
        for key_node, value_node in node.value:
            identity = _node_key(key_node)
            key = key_node.value if isinstance(key_node, ScalarNode) else identity
            field = _child_path(path, key)
            if identity in seen:
                raise ContractError("duplicate field", field)
            seen.add(identity)
            _check_duplicate_keys(value_node, field, nested)
    elif isinstance(node, SequenceNode):
        for index, value_node in enumerate(node.value):
            _check_duplicate_keys(value_node, f"{path}[{index}]", nested)


def parse_yaml_bytes(data: bytes, source: Path) -> object:
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise ContractError(f"cannot decode UTF-8 YAML: {exc}", source.as_posix()) from exc
    try:
        node = yaml.compose(text)
    except yaml.YAMLError:
        node = None
    if node is not None:
        _check_duplicate_keys(node, "", frozenset())
    return load_yaml_text(text, source=source.as_posix())


def read_yaml_file(path: Path, *, error_path: str | None = None) -> tuple[object, bytes]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ContractError(
            f"cannot read timetable file: {exc}", error_path or path.as_posix()
        ) from exc
    return parse_yaml_bytes(data, path), data


def check_mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("expected a mapping", path)
    return value


def check_string(value: object, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        message = "expected a non-empty string" if nonempty else "expected a string"
        raise ContractError(message, path)
    return value


def check_integer(value: object, path: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError("expected an integer", path)
    if minimum is not None and value < minimum:
        raise ContractError(f"must be at least {minimum}", path)
    return value


def check_date(value: object, path: str) -> date:
    if isinstance(value, datetime):
        raise ContractError("datetime is not a date", path)
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise ContractError("expected a strict ISO date", path)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("expected a valid ISO date", path) from exc
    if parsed.isoformat() != value:
        raise ContractError("expected a strict ISO date", path)
    return parsed


def check_time(value: object, path: str) -> int:
    if not isinstance(value, str) or not _TIME_RE.fullmatch(value):
        raise ContractError("expected HH:MM string", path)
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("expected valid HH:MM time", path) from exc
    if parsed.isoformat(timespec="minutes") != value:
        raise ContractError("expected strict HH:MM time", path)
    return parsed.hour * 60 + parsed.minute


def format_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def check_keys(
    value: Mapping[object, object],
    required: frozenset[str],
    allowed: frozenset[str],
    path: str,
) -> Mapping[str, Any]:
    for key in value:
        if not isinstance(key, str) or key not in allowed:
            raise ContractError("unknown field", _child_path(path, key))
    for key in sorted(required):
        if key not in value:
            raise ContractError("missing field", _child_path(path, key))
    return value  # type: ignore[return-value]


def identifier(value: object, path: str) -> str:
    name = check_string(value, path)
    if not _IDENTIFIER_RE.fullmatch(name):
        raise ContractError("invalid identifier", path)
    return name
