from __future__ import annotations

import os
import random
import unittest
from pathlib import Path

from ky.models import ContractError
from ky.timetable import semester_from_mapping
from ky.timetable_io.zfsoft_pdf import (
    Fragment,
    Page,
    ZFSOFT_ROTATED_V1,
    maximum_written_week,
    parse_zfsoft_fragments,
)

_PAGE_SIZE = (2000.0, 1000.0)
_LABEL_X = 1000.0
_SPACING = 50.0
_OFFSET = 5.0
_DETAIL = "(1-2节)1-16周(单)/教师/学分:3"


def _pages(count: int = 1) -> tuple[Page, ...]:
    return tuple(Page(number, *_PAGE_SIZE, 90) for number in range(1, count + 1))


def _labels(page: int = 1) -> list[Fragment]:
    return [
        Fragment(page, _LABEL_X, 400 + (weekday - 1) * _SPACING, 12, label, weekday)
        for weekday, label in enumerate(
            ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"),
            1,
        )
    ]


def _course_fragments(
    *,
    weekday: int = 1,
    page: int = 1,
    name: str = "数学",
    detail: str = _DETAIL,
    name_y: float | None = None,
    detail_y: float | None = None,
    name_x: float = 1100,
    detail_x: float = 1200,
    index: int = 20,
    split: tuple[str, ...] | None = None,
) -> list[Fragment]:
    anchor = 400 + (weekday - 1) * _SPACING - _OFFSET
    name_y = anchor if name_y is None else name_y
    detail_y = anchor if detail_y is None else detail_y
    rows = [Fragment(page, name_x, name_y, 9, name, index)]
    if split is None:
        rows.append(Fragment(page, detail_x, detail_y, 8, detail, index + 1))
    else:
        for part_index, part in enumerate(split):
            rows.append(
                Fragment(page, detail_x + part_index, detail_y, 8, part, index + 1 + part_index)
            )
    return rows


def _valid(*, pages: tuple[Page, ...] | None = None) -> tuple[tuple[Page, ...], list[Fragment]]:
    return _pages() if pages is None else pages, [*_labels(), *_course_fragments()]


class ZfsoftPdfContractTests(unittest.TestCase):
    def test_normal_mapping_single_period_type_marker_and_parity(self) -> None:
        pages, fragments = _valid()
        fragments.extend(
            _course_fragments(
                weekday=3,
                name="物理★",
                detail="(3节)1-16周(双)/教师/学分:2.5",
                index=40,
            )
        )
        courses = parse_zfsoft_fragments(pages, fragments, ZFSOFT_ROTATED_V1)
        self.assertEqual(
            courses,
            [
                {"name": "数学", "weekday": 1, "periods": "1-2", "weeks": "1-16周(单)"},
                {"name": "物理", "weekday": 3, "periods": "3", "weeks": "1-16周(双)"},
            ],
        )

    def test_cross_page_detail_continues_only_to_next_page(self) -> None:
        pages = _pages(2)
        first, second = _DETAIL[:18], _DETAIL[18:]
        fragments = [
            *_labels(),
            *_course_fragments(split=(first,), detail_x=1200),
            Fragment(2, 1200, 395, 8, second, 1),
        ]
        parsed = parse_zfsoft_fragments(pages, fragments)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["weeks"], "1-16周(单)")

        pages_with_gap = _pages(3)
        fragments_with_gap = [
            *_labels(),
            *_course_fragments(split=(first,)),
            Fragment(3, 1200, 395, 8, second, 1),
        ]
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages_with_gap, fragments_with_gap)

    def test_type_marker_as_separate_name_fragment_and_order_independence(self) -> None:
        pages, fragments = _valid()
        fragments.extend(
            [
                Fragment(1, 1300, 595, 9, "英语", 50),
                Fragment(1, 1301, 595, 9, "☆", 51),
                Fragment(1, 1400, 595, 8, "(4节)1-16周/教师/学分:1", 52),
            ]
        )
        expected = parse_zfsoft_fragments(pages, fragments)
        shuffled = fragments[:]
        random.Random(7).shuffle(shuffled)
        self.assertEqual(parse_zfsoft_fragments(pages, shuffled), expected)
        self.assertEqual(expected[-1]["name"], "英语")

    def test_labels_and_page_geometry_are_strict(self) -> None:
        pages, fragments = _valid()
        reverse_y = [
            Fragment(item.page, item.x, 700 - (index * 50), item.font_size, item.text, item.index)
            if item.text.startswith("星期")
            else item
            for index, item in enumerate(fragments)
        ]
        for variant in (reverse_y, [item for item in fragments if item.text != "星期日"]):
            with self.subTest(variant=variant[:1]), self.assertRaises(ContractError):
                parse_zfsoft_fragments(pages, variant)

        uneven = [
            Fragment(item.page, item.x + (1 if item.text == "星期日" else 0), item.y,
                     item.font_size, item.text, item.index)
            for item in fragments
        ]
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, uneven)
        uneven_y = [
            Fragment(
                item.page,
                item.x,
                item.y + (2 if item.text == "星期日" else 0),
                item.font_size,
                item.text,
                item.index,
            )
            for item in fragments
        ]
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, uneven_y)

        repeat_pages = _pages(2)
        repeated = [*_labels(), *_course_fragments(), *_labels(page=2)]
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(repeat_pages, repeated)
        different_size = (pages[0], Page(2, 1900, 1000, 90))
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(different_size, [*_labels(), *_course_fragments()])
        different_rotate = (pages[0], Page(2, 2000, 1000, 0))
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(different_rotate, [*_labels(), *_course_fragments()])

    def test_unknown_fragments_anchor_outliers_and_header_rules_reject(self) -> None:
        pages, fragments = _valid()
        fragments.append(Fragment(1, 1100, 800, 10, "unknown", 80))
        with self.assertRaises(ContractError) as caught:
            parse_zfsoft_fragments(pages, fragments)
        self.assertNotIn("unknown", str(caught.exception))
        self.assertIn("page=1", str(caught.exception))
        self.assertIn("stage=classification", str(caught.exception))

        pages, fragments = _valid()
        fragments.extend(_course_fragments(weekday=2, index=40))
        fragments[7] = Fragment(1, 1100, 380, 9, "数学", 20)
        fragments[8] = Fragment(1, 1200, 380, 8, _DETAIL, 21)
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, fragments)

        pages, fragments = _valid()
        fragments.append(Fragment(1, 999, 695, 9, "页眉", 90))
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, fragments)

        pages, fragments = _valid()
        fragments.extend(
            _course_fragments(weekday=2, name_y=625, detail_y=625, index=40)
        )
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, fragments)

        pages, fragments = _valid()
        fragments.extend(
            _course_fragments(weekday=2, name_y=625, detail_y=625, index=40)
        )
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, fragments)

    def test_record_structure_incomplete_or_orphaned_rows_reject(self) -> None:
        invalid_details = (
            "(1-2节)1-16周(单)/教师/学分:",
            "(1-2节)1-16周(单)/(3节)/学分:3",
        )
        for detail in invalid_details:
            pages, fragments = _valid()
            fragments[-1] = Fragment(1, 1200, 695, 8, detail, 21)
            with self.subTest(detail=detail), self.assertRaises(ContractError):
                parse_zfsoft_fragments(pages, fragments)

        pages = _pages(2)
        orphan = [*_labels(), Fragment(2, 1200, 695, 8, _DETAIL, 1)]
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, orphan)

        pages, fragments = _valid()
        fragments.extend(_course_fragments(name="另一门", index=40))
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, fragments)

    def test_non_course_fragment_with_structure_and_split_header_detail_reject(self) -> None:
        pages, fragments = _valid()
        fragments.append(Fragment(1, 800, 650, 12, "节)", 90))
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, fragments)

        pages, fragments = _valid()
        split = ("(1-2节)1-16", "周(单)/教师/学分:3")
        fragments.extend(
            _course_fragments(weekday=2, split=split, name_x=800, detail_x=850, index=40)
        )
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, fragments)

        control = parse_zfsoft_fragments(*_valid())
        self.assertEqual(len(control), 1)

    def test_same_day_same_x_and_missing_anchor_differences_reject(self) -> None:
        pages, fragments = _valid()
        fragments.extend(
            _course_fragments(name="重复", name_x=1100, detail_x=1100, index=40)
        )
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, fragments)

    def test_fragments_reject_newline_and_nonfinite_coordinates(self) -> None:
        pages, fragments = _valid()
        fragments[7] = Fragment(1, 1100, 395, 9, "數學\n課", 20)
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, fragments)

        pages, fragments = _valid()
        fragments[7] = Fragment(1, float("inf"), 395, 9, "数学", 20)
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(pages, fragments)

    def test_written_week_upper_bound_precedes_parity_filtering(self) -> None:
        courses = [{"weeks": "1-16周(单)"}]
        self.assertEqual(maximum_written_week(courses), 16)
        semester = {
            "label": "synthetic",
            "school": "sample",
            "week1_monday": "2026-09-07",
            "weeks": 16,
            "courses": [
                {"name": "数学", "weekday": 1, "periods": "1-2", "weeks": "1-16周(单)"}
            ],
        }
        with self.assertRaises(ContractError) as too_short:
            semester_from_mapping({**semester, "weeks": 15}, "semester")
        self.assertEqual(too_short.exception.path, "semester.courses[0].weeks")
        self.assertEqual(semester_from_mapping(semester, "semester").weeks, 16)

    @unittest.skipUnless(os.environ.get("KY_TIMETABLE_PDF"), "个人 PDF 只在本机提供")
    def test_local_pdf_extracts_and_parses_without_writing(self) -> None:
        source = Path(os.environ["KY_TIMETABLE_PDF"])
        data = source.read_bytes()
        from ky.timetable_io.zfsoft_pdf import extract_fragments

        pages, fragments = extract_fragments(data)
        self.assertTrue(parse_zfsoft_fragments(pages, fragments))


class ZfsoftPdfRound241Tests(unittest.TestCase):
    """Regression cases from sol round 241."""

    def test_unknown_week_qualifiers_and_repeated_fields_are_rejected(self) -> None:
        # R1: the whole field is the expression; no valid-looking substring is salvaged.
        for expression in ("1-16周(双周)", "1-4周 1-4周", "1-16周(单),17周(奇)"):
            detail = f"(1-2节){expression}/教师/学分:3"
            fragments = [*_labels(), *_course_fragments(name="Synthetic", detail=detail)]
            with self.subTest(expression=expression):
                with self.assertRaises(ContractError):
                    parse_zfsoft_fragments(_pages(), fragments)

    def test_name_may_continue_onto_the_next_page_but_not_past_it(self) -> None:
        # R2: a record with no detail yet may continue its name on the adjacent page only.
        y = 400 - 5
        adjacent = [
            *_labels(),
            Fragment(1, 1100, y, 9, "Course", 20),
            Fragment(2, 1100, y, 9, "Name", 1),
            Fragment(2, 1200, y, 8, "(1-2节)1-16周(单)/教师/学分:3", 2),
        ]
        courses = parse_zfsoft_fragments(_pages(2), adjacent)
        self.assertEqual(
            courses,
            [{"name": "CourseName", "weekday": 1, "periods": "1-2", "weeks": "1-16周(单)"}],
        )
        skipped = [
            *_labels(),
            Fragment(1, 1100, y, 9, "Course", 20),
            Fragment(3, 1100, y, 9, "Name", 1),
            Fragment(3, 1200, y, 8, "(1-2节)1-16周(单)/教师/学分:3", 2),
        ]
        with self.assertRaises(ContractError):
            parse_zfsoft_fragments(_pages(3), skipped)

    def test_non_string_adapter_is_a_contract_error(self) -> None:
        # R3: a list typed into the adapter field must not raise TypeError.
        import yaml
        from pathlib import Path

        from tests.contract.test_timetable_io_port import _staged
        from ky.timetable_io import parse_staging_bytes, staged_to_bytes

        raw = yaml.safe_load(staged_to_bytes(_staged()))
        raw["source"]["adapter"] = ["zfsoft_pdf"]
        with self.assertRaises(ContractError) as caught:
            parse_staging_bytes(yaml.safe_dump(raw).encode("utf-8"), Path("synthetic.yaml"))
        self.assertEqual(caught.exception.path, "source.adapter")


if __name__ == "__main__":
    unittest.main()
