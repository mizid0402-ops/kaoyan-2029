"""M29 timetable import and export; see ``contracts/timetable_import.md`` §§1, 3–7.

Public interfaces: isolation state inspection, staging parsing/publication, ``restage``, and
``apply_staging``, ICS import/export, and candidate preview.
"""

from ky.timetable_io.isolation import (
    Isolation,
    check_isolated_path,
    inspect_isolation,
)
from ky.timetable_io.operations import (
    ApplyResult,
    RestageResult,
    apply_staging,
    restage,
)
from ky.timetable_io.staging import (
    StagedSemester,
    parse_staging_bytes,
    publish_staging,
    read_staging,
    staged_to_bytes,
    staging_hash12,
)
from ky.timetable_io.ics_export import export_ics
from ky.timetable_io.ics_import import import_ics
from ky.timetable_io.preview import base_resolver, preview_lines

__all__ = [
    "ApplyResult",
    "Isolation",
    "RestageResult",
    "StagedSemester",
    "apply_staging",
    "check_isolated_path",
    "inspect_isolation",
    "export_ics",
    "import_ics",
    "parse_staging_bytes",
    "publish_staging",
    "base_resolver",
    "preview_lines",
    "read_staging",
    "restage",
    "staged_to_bytes",
    "staging_hash12",
]
