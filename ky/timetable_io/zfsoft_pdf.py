"""M29 ZFSoft PDF import adapter; see ``contracts/timetable_import_zfsoft_pdf.md``.

Public interfaces: :class:`Page`, :class:`Fragment`, :class:`ZfsoftTemplate`,
:data:`ZFSOFT_ROTATED_V1`, :func:`extract_fragments`,
:func:`parse_zfsoft_fragments`, :func:`maximum_written_week`,
:func:`import_zfsoft_pdf`, and :class:`PdfImportResult`.
"""

from __future__ import annotations

import hashlib
import io
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from pypdf import PdfReader

from ky.models import ContractError
from ky.timetable import (
    Semester,
    load_referenced_schools,
    semester_from_mapping,
    validate_semester_references,
)
from ky.timetable_io import (
    Isolation,
    StagedSemester,
    publish_staging,
    staging_hash12,
)
from ky.timetable_io.preview import preview_lines
from ky.workspace import Workspace

_WEEKDAY_TEXT = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
_WEEK_ITEM = re.compile(r"^(\d+)(?:-(\d+))?周?(?:\((单|双)\))?$")
_DETAIL = re.compile(
    r"^\((\d+)(?:-(\d+))?节\)([^/]+)/.*学分:\d+(?:\.\d+)?$"
)
_PERIOD_MARKER = re.compile(r"\(\d+(?:-\d+)?节\)")
_DIGITS = re.compile(r"^[0-9]+$")
_TYPE_MARKERS = frozenset("★☆○●◆◇")


@dataclass(frozen=True)
class Page:
    number: int
    width: float
    height: float
    rotate: int


@dataclass(frozen=True)
class Fragment:
    page: int
    x: float
    y: float
    font_size: float
    text: str
    index: int


@dataclass(frozen=True)
class ZfsoftTemplate:
    name: str
    name_size: float
    detail_size: float
    metadata_size: float
    label_x_tolerance: float
    label_spacing_ratio: float
    anchor_delta_range: float
    anchor_tolerance: float
    metadata_texts: frozenset[str]
    metadata_prefixes: tuple[str, ...]
    header_forbidden: frozenset[str]


ZFSOFT_ROTATED_V1 = ZfsoftTemplate(
    name="zfsoft_rotated_v1",
    name_size=9,
    detail_size=8,
    metadata_size=12,
    label_x_tolerance=0.5,
    label_spacing_ratio=0.02,
    anchor_delta_range=1.0,
    anchor_tolerance=0.5,
    metadata_texts=frozenset({"时间段", "节次", "上午", "下午", "晚上"}),
    metadata_prefixes=(": 理论", "打印时间:"),
    header_forbidden=frozenset({"节", "周", "学分", "(", ")"}),
)


@dataclass(frozen=True)
class _Location:
    page: int
    x: float
    y: float
    index: int


@dataclass
class _Record:
    weekday: int
    name_parts: list[str]
    detail_parts: list[str]
    fragments: list[Fragment]
    last_page: int


@dataclass(frozen=True)
class PdfImportResult:
    staging_path: Path
    published: bool
    summary: tuple[str, ...]
    grid: tuple[str, ...]


def _location(fragment: Fragment | None, stage: str) -> str:
    if fragment is None:
        return f"page=1,x=0,y=0,index=0,stage={stage}"
    return (
        f"page={fragment.page},x={fragment.x:g},y={fragment.y:g},"
        f"index={fragment.index},stage={stage}"
    )


def _fail(stage: str, fragment: Fragment | None = None) -> None:
    raise ContractError("unrecognized Zfsoft timetable PDF", _location(fragment, stage))


def _finite(values: Sequence[float]) -> bool:
    return all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for value in values
    )


def _matrix_origin(cm: Sequence[float], tm: Sequence[float]) -> tuple[float, float]:
    if len(cm) != 6 or len(tm) != 6:
        raise ValueError("invalid PDF text matrix")
    x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
    y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
    if not _finite((x, y)):
        raise ValueError("non-finite PDF coordinates")
    return x, y


def extract_fragments(data: bytes) -> tuple[tuple[Page, ...], tuple[Fragment, ...]]:
    """Extract positioned text from one in-memory PDF byte string."""
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        pages: list[Page] = []
        fragments: list[Fragment] = []
        for page_number, source_page in enumerate(reader.pages, 1):
            box = source_page.mediabox
            page = Page(
                page_number,
                float(box.width),
                float(box.height),
                int(source_page.get("/Rotate", 0)) % 360,
            )
            pages.append(page)
            page_index = 0

            def visit(text, cm, tm, font_dict, font_size):
                nonlocal page_index
                cleaned = text.strip()
                if not cleaned:
                    return
                try:
                    x, y = _matrix_origin(cm, tm)
                    size = float(font_size)
                except (TypeError, ValueError, IndexError, OverflowError):
                    _fail(
                        "extract",
                        Fragment(page_number, 0, 0, 0, "", page_index),
                    )
                if not math.isfinite(size) or "\n" in cleaned or "\r" in cleaned:
                    _fail(
                        "extract",
                        Fragment(page_number, x, y, size, "", page_index),
                    )
                fragments.append(
                    Fragment(page_number, x, y, size, cleaned, page_index)
                )
                page_index += 1

            source_page.extract_text(visitor_text=visit)
    except ContractError:
        raise
    except Exception as exc:
        raise ContractError(
            "cannot extract PDF text", _location(None, "extract")
        ) from exc
    return tuple(pages), tuple(fragments)


def _check_pages(pages: Sequence[Page], fragments: Sequence[Fragment]) -> None:
    if not isinstance(pages, Sequence) or not pages:
        _fail("pages")
    if not isinstance(fragments, Sequence):
        _fail("pages")
    if any(not isinstance(page, Page) for page in pages):
        _fail("pages")
    if any(not isinstance(fragment, Fragment) for fragment in fragments):
        _fail("pages")
    if tuple(page.number for page in pages) != tuple(range(1, len(pages) + 1)):
        _fail("pages")
    if any(type(page.number) is not int or type(page.rotate) is not int for page in pages):
        _fail("pages")
    first = pages[0]
    if not _finite((first.width, first.height)) or first.width <= 0 or first.height <= 0:
        _fail("pages")
    for page in pages[1:]:
        if not _finite((page.width, page.height)) or page.width <= 0 or page.height <= 0:
            _fail("pages")
        if (page.width, page.height, page.rotate) != (
            first.width,
            first.height,
            first.rotate,
        ):
            _fail("pages")
    valid_pages = {page.number for page in pages}
    indexes: dict[int, set[int]] = {page.number: set() for page in pages}
    for fragment in fragments:
        if fragment.page not in valid_pages:
            _fail("pages", fragment)
        if (
            not _finite((fragment.x, fragment.y, fragment.font_size))
            or not fragment.text.strip()
            or "\n" in fragment.text
            or "\r" in fragment.text
            or type(fragment.index) is not int
            or fragment.index < 0
            or fragment.index in indexes[fragment.page]
        ):
            _fail("pages", fragment)
        indexes[fragment.page].add(fragment.index)


def _weekday_labels(
    pages: Sequence[Page], fragments: Sequence[Fragment], template: ZfsoftTemplate
) -> tuple[float, float, dict[int, Fragment]]:
    labels = [
        fragment
        for fragment in fragments
        if fragment.text in _WEEKDAY_TEXT
    ]
    if any(fragment.page != 1 for fragment in labels):
        _fail("labels", next(fragment for fragment in labels if fragment.page != 1))
    if any(fragment.font_size != template.metadata_size for fragment in labels):
        _fail(
            "labels",
            next(item for item in labels if item.font_size != template.metadata_size),
        )
    if len(labels) != 7 or {item.text for item in labels} != set(_WEEKDAY_TEXT):
        _fail("labels", fragments[0] if fragments else None)
    by_day = {_WEEKDAY_TEXT.index(item.text) + 1: item for item in labels}
    xs = [item.x for item in by_day.values()]
    if max(xs) - min(xs) > template.label_x_tolerance:
        _fail("labels", by_day[1])
    ys = [by_day[day].y for day in range(1, 8)]
    gaps = [right - left for left, right in zip(ys, ys[1:])]
    spacing = sum(gaps) / len(gaps)
    if spacing <= 0 or any(gap <= 0 for gap in gaps):
        _fail("labels", by_day[1])
    if any(
        abs(gap - spacing) > spacing * template.label_spacing_ratio
        for gap in gaps
    ):
        _fail("labels", by_day[1])
    return (min(xs) + max(xs)) / 2, spacing, by_day


def _on_anchor(fragment: Fragment, anchors: Mapping[int, float], tolerance: float) -> bool:
    return any(abs(fragment.y - anchor) <= tolerance for anchor in anchors.values())


def _anchors(
    fragments: Sequence[Fragment],
    labels: Mapping[int, Fragment],
    spacing: float,
    left_edge: float,
    template: ZfsoftTemplate,
) -> dict[int, float]:
    differences: list[float] = []
    for fragment in fragments:
        if fragment.page == 1 and fragment.x < left_edge - template.label_x_tolerance:
            continue
        if fragment.font_size != template.name_size:
            continue
        later = [item.y for item in labels.values() if item.y > fragment.y]
        if not later:
            continue
        difference = min(later) - fragment.y
        if 0 < difference < spacing / 2:
            differences.append(difference)
    if not differences:
        _fail("anchors", fragments[0] if fragments else None)
    low, high = min(differences), max(differences)
    if high - low > template.anchor_delta_range:
        _fail("anchors", fragments[0] if fragments else None)
    distance = (low + high) / 2
    return {weekday: label.y - distance for weekday, label in labels.items()}


def _body_whitelist(fragment: Fragment, template: ZfsoftTemplate) -> bool:
    if fragment.font_size == template.metadata_size:
        return (
            fragment.text in template.metadata_texts
            or _DIGITS.fullmatch(fragment.text) is not None
            or fragment.text in _WEEKDAY_TEXT
        )
    if fragment.font_size == template.detail_size:
        return fragment.text.startswith(template.metadata_prefixes)
    return False


def _classify(
    pages: Sequence[Page],
    fragments: Sequence[Fragment],
    labels: Mapping[int, Fragment],
    left_edge: float,
    anchors: Mapping[int, float],
    template: ZfsoftTemplate,
) -> dict[int, dict[int, list[Fragment]]]:
    courses: dict[int, dict[int, list[Fragment]]] = {
        weekday: {page.number: [] for page in pages} for weekday in range(1, 8)
    }
    label_indexes = {item.index for item in labels.values()}
    for fragment in fragments:
        if fragment.page == 1 and fragment.index in label_indexes:
            if _on_anchor(fragment, anchors, template.anchor_tolerance):
                _fail("classification", fragment)
            continue
        header = fragment.page == 1 and fragment.x < (
            left_edge - template.label_x_tolerance
        )
        if header:
            if fragment.font_size in (template.name_size, template.detail_size) and (
                _on_anchor(fragment, anchors, template.anchor_tolerance)
            ):
                _fail("classification", fragment)
            continue
        aligned = _on_anchor(fragment, anchors, template.anchor_tolerance)
        if fragment.font_size in (template.name_size, template.detail_size) and aligned:
            weekday = min(
                anchors,
                key=lambda day: abs(fragment.y - anchors[day]),
            )
            courses[weekday][fragment.page].append(fragment)
            continue
        if _body_whitelist(fragment, template) and not aligned:
            continue
        _fail("classification", fragment)
    return courses


def _check_structure_coverage(
    fragments: Sequence[Fragment],
    left_edge: float,
    template: ZfsoftTemplate,
) -> None:
    for fragment in fragments:
        header = fragment.page == 1 and fragment.x < (
            left_edge - template.label_x_tolerance
        )
        if header and any(char in fragment.text for char in template.header_forbidden):
            _fail("structure", fragment)


def _detail_match(record: _Record) -> re.Match[str] | None:
    return _DETAIL.fullmatch("".join(record.detail_parts))


def _week_expression(schedule_text: str, fragment: Fragment) -> str:
    # The whole field between "节)" and the first "/" is the week expression (spec section 3);
    # searching it for a valid-looking substring silently dropped qualifiers such as "(双周)"
    # (sol round 241 R1). Every item must match the zfsoft week syntax, else reject.
    if not schedule_text or any(
        _WEEK_ITEM.fullmatch(item) is None for item in schedule_text.split(",")
    ):
        _fail("verification", fragment)
    return schedule_text


def _record_mapping(record: _Record) -> dict[str, object]:
    name = "".join(record.name_parts)
    if name and name[-1] in _TYPE_MARKERS:
        name = name[:-1]
    name = name.strip()
    if not name or _PERIOD_MARKER.search(name):
        _fail("verification", record.fragments[0])
    detail = "".join(record.detail_parts)
    match = _DETAIL.fullmatch(detail)
    if match is None or len(_PERIOD_MARKER.findall(detail)) != 1:
        _fail("verification", record.fragments[-1])
    schedule_text = match.group(3)
    period_first = int(match.group(1))
    period_last = int(match.group(2) or match.group(1))
    if period_last < period_first:
        _fail("verification", record.fragments[-1])
    weeks = _week_expression(schedule_text, record.fragments[-1])
    return {
        "name": name,
        "weekday": record.weekday,
        "periods": (
            str(period_first)
            if period_first == period_last
            else f"{period_first}-{period_last}"
        ),
        "weeks": weeks,
    }


def _record_complete(record: _Record) -> bool:
    return bool(record.detail_parts) and _detail_match(record) is not None


def _start_record(weekday: int, fragment: Fragment) -> _Record:
    return _Record(weekday, [fragment.text], [], [fragment], fragment.page)


def _add_detail(record: _Record, fragment: Fragment) -> None:
    record.detail_parts.append(fragment.text)
    record.fragments.append(fragment)
    record.last_page = fragment.page


def _parse_weekday(
    weekday: int,
    page_courses: Mapping[int, list[Fragment]],
    page_count: int,
    template: ZfsoftTemplate,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    pending: _Record | None = None
    for page_number in range(1, page_count + 1):
        rows = sorted(page_courses[page_number], key=lambda item: (item.x, item.index))
        same_x = [
            right
            for left, right in zip(rows, rows[1:])
            if left.x == right.x
        ]
        if same_x:
            _fail("records", same_x[0])
        if not rows:
            if pending is not None:
                _fail("continuation", pending.fragments[-1])
            continue
        if pending is not None:
            # A record may continue only onto the next page; while it has no detail yet its
            # name may continue there too (sol round 241 R2).
            detail_stage = bool(pending.detail_parts)
            if pending.last_page != page_number - 1 or (
                detail_stage and rows[0].font_size != template.detail_size
            ):
                _fail("continuation", rows[0])
        for fragment in rows:
            if fragment.font_size == template.name_size:
                if pending is None:
                    pending = _start_record(weekday, fragment)
                elif pending.detail_parts:
                    if not _record_complete(pending):
                        _fail("records", fragment)
                    results.append(_record_mapping(pending))
                    pending = _start_record(weekday, fragment)
                else:
                    pending.name_parts.append(fragment.text)
                    pending.fragments.append(fragment)
                    pending.last_page = fragment.page
            else:
                if pending is None:
                    _fail("continuation", fragment)
                _add_detail(pending, fragment)
        if pending is not None and _record_complete(pending):
            results.append(_record_mapping(pending))
            pending = None
    if pending is not None:
        _fail("records", pending.fragments[-1])
    return results


def parse_zfsoft_fragments(
    pages: Sequence[Page],
    fragments: Sequence[Fragment],
    template: ZfsoftTemplate = ZFSOFT_ROTATED_V1,
) -> list[dict[str, object]]:
    """Classify and assemble synthetic or extracted fragments without file I/O."""
    if not isinstance(template, ZfsoftTemplate):
        _fail("template")
    _check_pages(pages, fragments)
    left_edge, spacing, labels = _weekday_labels(pages, fragments, template)
    anchors = _anchors(fragments, labels, spacing, left_edge, template)
    by_weekday = _classify(
        pages, fragments, labels, left_edge, anchors, template
    )
    _check_structure_coverage(fragments, left_edge, template)
    courses: list[dict[str, object]] = []
    for weekday in range(1, 8):
        courses.extend(
            _parse_weekday(weekday, by_weekday[weekday], len(pages), template)
        )
    if not courses:
        _fail("verification", fragments[0] if fragments else None)
    courses.sort(
        key=lambda item: (
            item["weekday"],
            int(str(item["periods"]).split("-", 1)[0]),
            int(str(item["periods"]).split("-")[-1]),
            item["name"],
        )
    )
    return courses


def maximum_written_week(courses: Sequence[Mapping[str, object]]) -> int:
    """Return the largest written upper bound before odd/even filtering."""
    maximum = 0
    for index, course in enumerate(courses):
        value = course.get("weeks")
        if not isinstance(value, str) or not value:
            raise ContractError("invalid PDF week expression", f"courses[{index}].weeks")
        for item in value.split(","):
            match = _WEEK_ITEM.fullmatch(item)
            if match is None:
                raise ContractError(
                    "invalid PDF week expression", f"courses[{index}].weeks"
                )
            maximum = max(maximum, int(match.group(2) or match.group(1)))
    if maximum < 1:
        raise ContractError("PDF has no course weeks", "courses")
    return maximum


def _candidate_semester(
    courses: list[dict[str, object]],
    school_id: str,
    label: str,
    week1: str,
    weeks: int | None,
) -> Semester:
    try:
        upper = maximum_written_week(courses) if weeks is None else weeks
        raw = {
            "label": label,
            "school": school_id,
            "week1_monday": week1,
            "weeks": upper,
            "courses": courses,
            "exceptions": [],
        }
        return semester_from_mapping(raw, "semester")
    except ContractError as exc:
        raise ContractError(
            "PDF candidate violates timetable rules",
            _location(None, "semester"),
        ) from exc


def import_zfsoft_pdf(
    data: bytes,
    workspace: Workspace,
    isolation: Isolation,
    *,
    school_id: str,
    label: str,
    week1: str,
    weeks: int | None = None,
    config_path: str | Path | None = None,
) -> PdfImportResult:
    """Validate one PDF byte string and publish its candidate through M29 staging."""
    schools = load_referenced_schools(workspace, (school_id,))
    loaded = schools[school_id]
    if loaded.profile.system != "zfsoft":
        raise ContractError(
            "school does not use the Zfsoft system",
            f"reference.timetable_schools.{school_id}",
        )
    pages, fragments = extract_fragments(data)
    courses = parse_zfsoft_fragments(pages, fragments)
    semester = _candidate_semester(courses, school_id, label, week1, weeks)
    validate_semester_references(semester, loaded.profile, "semester")
    digest = hashlib.sha256(data).hexdigest()
    staged = StagedSemester("zfsoft_pdf", digest, semester, ())
    path, published = publish_staging(workspace, staged, isolation)
    return PdfImportResult(
        path,
        published,
        (
            f"学期：{semester.label}",
            f"课程：{len(semester.courses)} 门；周数：{semester.weeks}",
            f"暂存文件：{path}",
        ),
        # Same preview as import-ics: grid, plus daily minutes when a base can be resolved.
        preview_lines(workspace, semester, config_path, schools=schools),
    )
