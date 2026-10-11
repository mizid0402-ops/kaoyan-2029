"""M26 hand-entered daily availability; see ``contracts/availability.md``.

Public interfaces: :func:`load_availability`, :func:`load_availability_with_source`,
:func:`resolve_daily_minutes`, :func:`availability_for_workspace`, and
:func:`availability_source_for_workspace`, and :func:`set_day_minutes`.
"""

from .port import (
    Availability,
    AvailabilitySource,
    DailyMinutes,
    DerivedDailyMinutes,
    availability_for_workspace,
    availability_source_for_workspace,
    load_availability,
    load_availability_with_source,
    resolve_daily_minutes,
    set_day_minutes,
)

__all__ = [
    "Availability",
    "AvailabilitySource",
    "DailyMinutes",
    "DerivedDailyMinutes",
    "availability_for_workspace",
    "availability_source_for_workspace",
    "load_availability",
    "load_availability_with_source",
    "resolve_daily_minutes",
    "set_day_minutes",
]
