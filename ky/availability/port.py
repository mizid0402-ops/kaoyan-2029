"""M26 availability port; see ``contracts/availability.md`` and
``contracts/state_sources.md``.

Public interfaces: :class:`Availability`, :class:`AvailabilitySource`, :class:`DailyMinutes`,
:class:`DerivedDailyMinutes`,
:func:`load_availability`, :func:`load_availability_with_source`, :func:`resolve_daily_minutes`, and
:func:`availability_for_workspace`, and :func:`availability_source_for_workspace`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Protocol

from ky.models import ContractError, load_yaml_text
from ky.workspace import Workspace
from ky.storage.atomic import replace_bytes

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_ROOT_KEYS = frozenset({"schema_version", "days"})


@dataclass(frozen=True)
class Availability:
    """Validated per-day minute values loaded from a registered YAML file."""

    days: Mapping[date, int]


@dataclass(frozen=True)
class AvailabilitySource:
    """Validated availability and the hash of the exact file bytes parsed."""

    availability: Availability
    sha256: str


@dataclass(frozen=True)
class DailyMinutes:
    """Resolved daily capacity and its auditable source."""

    minutes: int
    source: Literal["availability", "timetable", "config"]


class DerivedDailyMinutes(Protocol):
    """M26-compatible provider for a derived daily base (M18 implements this port)."""

    def minutes_for(self, day: date, base_minutes: int) -> int | None:
        """Return a derived value, or ``None`` when this provider has no value."""


def _day_key(value: object, path: str) -> date:
    if isinstance(value, datetime):
        raise ContractError("datetime keys are not allowed", path)
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise ContractError("day key must be a YAML date or strict ISO date", path)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("day key must be a valid ISO date", path) from exc
    if parsed.isoformat() != value:
        raise ContractError("day key must be a strict ISO date", path)
    return parsed


def load_availability(path: str | Path) -> Availability:
    """Read and validate schema version 1 per-day availability YAML."""
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
        return _availability_from_text(text, source)
    except (OSError, UnicodeError, ContractError) as exc:
        if isinstance(exc, ContractError) and exc.path:
            raise
        raise ContractError(f"cannot read availability: {exc}", source.as_posix()) from exc


def load_availability_with_source(path: str | Path) -> AvailabilitySource:
    """Read and validate availability, hashing the same bytes used for parsing."""
    source = Path(path)
    try:
        data = source.read_bytes()
        text = data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"cannot read availability: {exc}", source.as_posix()) from exc
    return AvailabilitySource(
        _availability_from_text(text, source), hashlib.sha256(data).hexdigest()
    )


def _availability_from_text(text: str, source: Path) -> Availability:
    raw = load_yaml_text(text, source=source.as_posix())
    if not isinstance(raw, Mapping):
        raise ContractError("expected a mapping", source.as_posix())
    non_string_keys = [key for key in raw if not isinstance(key, str)]
    if non_string_keys:
        key = non_string_keys[0]
        raise ContractError("top-level field names must be strings", str(key))
    unknown = sorted(set(raw) - _ROOT_KEYS)
    if unknown:
        raise ContractError("unknown field", unknown[0])
    version = raw.get("schema_version")
    if type(version) is not int or version != 1:
        raise ContractError("schema_version must be integer 1", "schema_version")
    days_raw = raw.get("days")
    if not isinstance(days_raw, Mapping):
        raise ContractError("expected a mapping", "days")

    days: dict[date, int] = {}
    for raw_day, minutes in days_raw.items():
        day_path = f"days.{raw_day}"
        day = _day_key(raw_day, day_path)
        if day in days:
            raise ContractError("duplicate day after date normalization", day_path)
        if type(minutes) is not int or minutes < 0:
            raise ContractError("minutes must be a non-negative integer", day_path)
        days[day] = minutes
    return Availability(MappingProxyType(days))


def resolve_daily_minutes(
    day: date,
    base_minutes: int,
    availability: Availability | None,
    timetable: DerivedDailyMinutes | None = None,
) -> DailyMinutes:
    """Choose hand-entered, derived, or caller-provided base minutes in that order."""
    if availability is not None and day in availability.days:
        return DailyMinutes(availability.days[day], "availability")
    if timetable is not None:
        minutes = timetable.minutes_for(day, base_minutes)
        if minutes is not None:
            return DailyMinutes(minutes, "timetable")
    return DailyMinutes(base_minutes, "config")


def availability_for_workspace(workspace: Workspace) -> Availability | None:
    """Load the registered availability file; unregistered means no override."""
    source = availability_source_for_workspace(workspace)
    return None if source is None else source.availability


def availability_source_for_workspace(workspace: Workspace) -> AvailabilitySource | None:
    """Load one registered file and retain the digest of its exact bytes."""
    if workspace.availability is None:
        return None
    path = workspace.write_target("state.availability")
    if not path.is_file():
        raise ContractError(
            f"registered file does not exist: {path}", "state.availability",
        )
    return load_availability_with_source(path)


def set_day_minutes(path: str | Path, day: date, minutes: int | None) -> None:
    """Replace one M26 day entry using the canonical file representation (M33 §5)."""
    if not isinstance(path, (str, Path)):
        raise ContractError("expected a path", "path")
    if type(day) is not date:
        raise ContractError("expected a date", "day")
    if minutes is not None and (type(minutes) is not int or not 0 <= minutes <= 1440):
        raise ContractError("minutes must be an integer from 0 to 1440 or null", "minutes")
    source = Path(path)
    try:
        data = source.read_bytes()
        text = data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"cannot read availability: {exc}", source.as_posix()) from exc
    loaded = _availability_from_text(text, source)
    days = dict(loaded.days)
    if minutes is None:
        if day not in days:
            raise ContractError("day entry does not exist", f"days.{day.isoformat()}")
        del days[day]
    else:
        days[day] = minutes
    if yaml is None:  # pragma: no cover
        raise ContractError("PyYAML is required", source.as_posix())
    payload = {
        "schema_version": 1,
        "days": {key.isoformat(): value for key, value in sorted(days.items())},
    }
    encoded = yaml.safe_dump(
        payload, allow_unicode=True, sort_keys=False, default_flow_style=False,
    ).encode("utf-8")
    replace_bytes(source, encoded)
