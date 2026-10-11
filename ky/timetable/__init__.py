"""M18 timetable port; see ``contracts/timetable.md`` §§2–7.

Public interfaces: mapping validators and serializers, school-reference validation/loading,
:func:`build_calendar`, :func:`load_school`, :func:`load_timetable`,
:func:`timetable_for_workspace`, :class:`LoadedSchool`, :class:`TimetableCalendar`,
:class:`DaySchedule`, and the timetable data models.
"""

from ky.timetable._models import (
    DaySchedule,
    LoadedSchool,
    SchoolProfile,
    Semester,
    Timetable,
    TimetableRules,
)
from ky.timetable.calendar import (
    TimetableCalendar,
    build_calendar,
    load_referenced_schools,
    timetable_for_workspace,
    validate_semester_references,
)
from ky.timetable.school import load_school
from ky.timetable.timetable import (
    load_timetable,
    semester_from_mapping,
    semester_to_mapping,
    timetable_from_mapping,
    timetable_to_mapping,
)

__all__ = [
    "DaySchedule",
    "LoadedSchool",
    "Semester",
    "SchoolProfile",
    "Timetable",
    "TimetableRules",
    "TimetableCalendar",
    "build_calendar",
    "load_referenced_schools",
    "load_school",
    "load_timetable",
    "semester_from_mapping",
    "semester_to_mapping",
    "timetable_from_mapping",
    "timetable_to_mapping",
    "timetable_for_workspace",
    "validate_semester_references",
]
