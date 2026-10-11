"""M18 school-profile loader; see ``contracts/timetable.md`` §2.

Public interface: :func:`load_school`.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from ky.models import ContractError
from ky.timetable._common import (
    check_date,
    check_integer,
    check_keys,
    check_mapping,
    check_string,
    check_time,
    identifier,
    read_yaml_file,
)
from ky.timetable._models import Period, SchoolProfile

_ROOT_KEYS = frozenset(
    {"schema_version", "school_id", "name", "aliases", "system", "source", "periods", "blocks"}
)
_REQUIRED_ROOT_KEYS = frozenset(
    {"schema_version", "school_id", "name", "system", "source", "periods", "blocks"}
)
_SOURCE_KEYS = frozenset({"kind", "recorded_on"})
_PERIOD_KEYS = frozenset({"start", "end", "unconfirmed"})


def _school_aliases(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ContractError("expected a list", "aliases")
    aliases: list[str] = []
    for index, item in enumerate(value):
        alias = check_string(item, f"aliases[{index}]")
        if alias in aliases:
            raise ContractError("duplicate alias", f"aliases[{index}]")
        aliases.append(alias)
    return tuple(aliases)


def _periods(value: object) -> tuple[dict[int, Period], tuple[int, ...]]:
    raw = check_mapping(value, "periods")
    if not raw:
        raise ContractError("periods must not be empty", "periods")
    numbered: dict[int, object] = {}
    for key, item in raw.items():
        if isinstance(key, bool) or not isinstance(key, int):
            raise ContractError("period number must be an integer", f"periods.{key}")
        numbered[key] = item
    numbers = tuple(sorted(numbered))
    for expected, number in enumerate(numbers, start=1):
        if expected != number:
            raise ContractError("period numbers must be continuous from 1", f"periods.{number}")

    periods: dict[int, Period] = {}
    previous_end = -1
    for number in numbers:
        path = f"periods.{number}"
        item = check_mapping(numbered[number], path)
        check_keys(item, frozenset({"start", "end"}), _PERIOD_KEYS, path)
        start = check_time(item["start"], f"{path}.start")
        end = check_time(item["end"], f"{path}.end")
        if start >= end:
            raise ContractError("period start must precede end", path)
        if start < previous_end:
            raise ContractError("period times overlap or are out of order", f"{path}.start")
        unconfirmed = item.get("unconfirmed", False)
        if not isinstance(unconfirmed, bool):
            raise ContractError("expected a boolean", f"{path}.unconfirmed")
        periods[number] = Period(start, end, unconfirmed)
        previous_end = end
    return periods, numbers


def _blocks(value: object, periods: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
    if not isinstance(value, list) or not value:
        raise ContractError("blocks must be a non-empty list", "blocks")
    blocks: list[tuple[int, ...]] = []
    flattened: list[int] = []
    for block_index, raw_block in enumerate(value):
        path = f"blocks[{block_index}]"
        if not isinstance(raw_block, list) or not raw_block:
            raise ContractError("block must be a non-empty list", path)
        block = tuple(
            check_integer(period, f"{path}[{index}]", minimum=1)
            for index, period in enumerate(raw_block)
        )
        if any(right != left + 1 for left, right in zip(block, block[1:])):
            raise ContractError("periods in a block must be adjacent", path)
        if flattened and block[0] <= flattened[-1]:
            raise ContractError("blocks must be ordered and non-overlapping", path)
        blocks.append(block)
        flattened.extend(block)
    if tuple(flattened) != periods:
        raise ContractError("blocks must cover all periods in order", "blocks")
    return tuple(blocks)


def _school_from_mapping(raw: object) -> SchoolProfile:
    root = check_mapping(raw, "")
    check_keys(root, _REQUIRED_ROOT_KEYS, _ROOT_KEYS, "")
    version = check_integer(root["schema_version"], "schema_version")
    if version != 1:
        raise ContractError("unsupported schema_version", "schema_version")
    school_id = identifier(root["school_id"], "school_id")
    name = check_string(root["name"], "name")
    system = identifier(root["system"], "system")
    source = check_mapping(root["source"], "source")
    check_keys(source, _SOURCE_KEYS, _SOURCE_KEYS, "source")
    kind = check_string(source["kind"], "source.kind")
    if kind not in {"official", "user_statement"}:
        raise ContractError("invalid source kind", "source.kind")
    recorded_on = check_date(source["recorded_on"], "source.recorded_on")
    aliases = _school_aliases(root.get("aliases", []))
    periods, period_numbers = _periods(root["periods"])
    blocks = _blocks(root["blocks"], period_numbers)
    return SchoolProfile(
        school_id,
        name,
        aliases,
        system,
        recorded_on,
        MappingProxyType(periods),
        blocks,
    )


def load_school(path: str | Path) -> SchoolProfile:
    """Read and validate one schema-version-1 school profile."""
    source = Path(path)
    raw, _ = read_yaml_file(source)
    return _school_from_mapping(raw)
