"""M18 week-expression parser from ``contracts/timetable.md`` §3.3."""

from __future__ import annotations

import re

from ky.models import ContractError

_WEEK_ITEM_RE = re.compile(r"^([0-9]+)(?:-([0-9]+))?周?(?:\((单|双)\))?$")


def _parse_week_item(value: str, path: str) -> tuple[int, int, str | None]:
    match = _WEEK_ITEM_RE.fullmatch(value)
    if match is None:
        raise ContractError("invalid week item", path)
    first = int(match.group(1))
    last = int(match.group(2) or match.group(1))
    parity = match.group(3)
    return first, last, parity


def _check_week_bounds(
    items: list[tuple[int, int, str | None]], total_weeks: int, path: str
) -> None:
    for first, last, _ in items:
        if first < 1 or last < first or last > total_weeks:
            raise ContractError("week range is outside this semester", path)


def _filter_parity(first: int, last: int, parity: str | None) -> frozenset[int]:
    values = range(first, last + 1)
    if parity == "单":
        return frozenset(value for value in values if value % 2 == 1)
    if parity == "双":
        return frozenset(value for value in values if value % 2 == 0)
    return frozenset(values)


def _reject_empty_items(items: list[frozenset[int]], path: str) -> None:
    if any(not item for item in items):
        raise ContractError("week item expands to an empty set", path)


def _reject_overlapping_items(items: list[frozenset[int]], path: str) -> None:
    seen: set[int] = set()
    for item in items:
        if seen.intersection(item):
            raise ContractError("week items overlap", path)
        seen.update(item)


def parse_week_expression(value: object, total_weeks: int, path: str) -> frozenset[int]:
    """Expand one week expression after validating syntax, bounds, and overlap."""
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ContractError("expected a week expression without whitespace", path)
    raw_items = value.split(",")
    parsed = [_parse_week_item(item, path) for item in raw_items]
    _check_week_bounds(parsed, total_weeks, path)
    expanded = [_filter_parity(first, last, parity) for first, last, parity in parsed]
    _reject_empty_items(expanded, path)
    _reject_overlapping_items(expanded, path)
    return frozenset().union(*expanded)
