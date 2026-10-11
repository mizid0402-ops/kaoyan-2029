"""M4 tree ID grammar strategies (workspace contract §2.5).

The verifier selects one registered strategy from a subject profile. Strategies
own ID patterns and profile-specific structural checks; subject IDs stay in data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

NUMBERED_CHAPTER_RE = re.compile(r"^[^.]+\.[^.]+\.chapter-[0-9]{2}$")
NUMBERED_SECTION_RE = re.compile(r"^.+\.chapter-[0-9]{2}\.section-[0-9]{2}$")
NAMED_CHAPTER_RE = re.compile(r"^.+\.chapter$")
NAMED_REQUIREMENT_ITEM_RE = re.compile(r"^.+\.requirements\.item-[0-9]{2}$")


@dataclass(frozen=True)
class TreeGrammar:
    name: str
    chapter_pattern: re.Pattern[str] | None
    structural_validator: Callable[[Sequence[object]], list[str]]

    def structural_failures(self, points: Sequence[object]) -> list[str]:
        return self.structural_validator(points)


SCOPE_RANK = {"subject": 0, "chapter": 1, "section": 2, "item": 3}


def _parent_id(point_id: str) -> str:
    return point_id.rsplit(".", 1)[0] if "." in point_id else ""


def subject_scope_failures(points: Iterable[object]) -> list[str]:
    failures: list[str] = []
    for point in points:
        if point.scope != "subject":
            continue
        family_prefix = _parent_id(point.knowledge_point_id) + "."
        related = [
            candidate
            for candidate in points
            if candidate.knowledge_point_id.startswith(family_prefix)
            and candidate.knowledge_point_id != point.knowledge_point_id
        ]
        if not related:
            failures.append(f"{point.knowledge_point_id}: subject node has no descendants")
        for candidate in related:
            candidate_rank = SCOPE_RANK[candidate.scope]
            if candidate_rank < SCOPE_RANK["subject"]:
                failures.append(
                    f"{candidate.knowledge_point_id}: scope {candidate.scope} "
                    "must be narrower than subject"
                )
                continue
            if candidate.scope != point.scope:
                continue
            if _parent_id(candidate.knowledge_point_id) == _parent_id(point.knowledge_point_id):
                continue
            if _parent_id(candidate.knowledge_point_id) == point.knowledge_point_id:
                failures.append(
                    f"{candidate.knowledge_point_id}: scope {candidate.scope} "
                    "must be narrower than subject"
                )
    return failures


def _numbered_failures(points: Sequence[object]) -> list[str]:
    failures: list[str] = []
    by_id = {point.knowledge_point_id: point for point in points}
    for point in points:
        if point.scope != "section":
            continue
        ancestor = _parent_id(point.knowledge_point_id)
        if (
            not is_numbered_section(point.knowledge_point_id)
            or ancestor not in by_id
            or by_id[ancestor].scope != "chapter"
        ):
            failures.append(
                f"{point.knowledge_point_id}: section has no direct chapter-NN "
                f"ancestor {ancestor!r}"
            )
    failures.extend(subject_scope_failures(points))
    failures.extend(_chapter_descendant_failures(points))
    return failures


def _named_failures(points: Sequence[object]) -> list[str]:
    failures: list[str] = []
    by_id = {point.knowledge_point_id: point for point in points}
    for point in points:
        point_id = point.knowledge_point_id
        if point.scope == "item" or ".item-" in point_id:
            parent = _parent_id(point_id)
            if (
                point.scope != "item"
                or not NAMED_REQUIREMENT_ITEM_RE.fullmatch(point_id)
                or parent not in by_id
                or by_id[parent].scope != "section"
                or not parent.endswith(".requirements")
            ):
                failures.append(
                    f"{point_id}: item must be a direct child of a requirements section"
                )
        if point.scope == "section":
            parts = point.knowledge_point_id.split(".")
            ancestor = ".".join(parts[:-1]) + ".chapter"
            if ancestor not in by_id or by_id[ancestor].scope != "chapter":
                failures.append(
                    f"{point.knowledge_point_id}: section has no ancestor node "
                    f"{ancestor!r}"
                )
    chapter_ids = [point.knowledge_point_id for point in points if point.scope == "chapter"]
    for chapter_id in chapter_ids:
        base = chapter_id[: -len(".chapter")]
        for suffix in (".content", ".requirements"):
            section_id = base + suffix
            if section_id not in by_id:
                failures.append(f"{chapter_id}: missing {section_id}")
            elif by_id[section_id].scope != "section":
                failures.append(
                    f"{chapter_id}: required section {section_id} has "
                    f"scope={by_id[section_id].scope!r}"
                )
    failures.extend(subject_scope_failures(points))
    failures.extend(_chapter_descendant_failures(points))
    return failures


def _flat_failures(points: Sequence[object]) -> list[str]:
    failures: list[str] = []
    by_id = {point.knowledge_point_id: point for point in points}
    for point in points:
        if point.scope != "item":
            continue
        parts = point.knowledge_point_id.split(".")
        if len(parts) < 3:
            continue
        parent = ".".join(parts[:-1])
        if parent not in by_id and not any(
            candidate.knowledge_point_id.startswith(parent + ".")
            or candidate.knowledge_point_id == parent
            for candidate in points
        ):
            failures.append(
                f"{point.knowledge_point_id}: item has no parent node under {parent!r}"
            )
    return failures


def _chapter_descendant_failures(points: Sequence[object]) -> list[str]:
    failures: list[str] = []
    for point in points:
        if point.scope != "chapter":
            continue
        prefix = point.knowledge_point_id + "."
        for child in points:
            if (
                child.knowledge_point_id.startswith(prefix)
                and SCOPE_RANK[child.scope] <= SCOPE_RANK["chapter"]
            ):
                failures.append(
                    f"{child.knowledge_point_id}: scope {child.scope} "
                    "must be narrower than chapter"
                )
    return failures


TREE_GRAMMARS = {
    "numbered_chapters": TreeGrammar(
        "numbered_chapters", NUMBERED_CHAPTER_RE, _numbered_failures
    ),
    "named_chapters": TreeGrammar(
        "named_chapters", NAMED_CHAPTER_RE, _named_failures
    ),
    "flat": TreeGrammar("flat", None, _flat_failures),
}


class TreeGrammarError(ValueError):
    """A tree's complete ID set conflicts with its registered grammar."""


def select_tree_grammar(name: str) -> TreeGrammar:
    try:
        return TREE_GRAMMARS[name]
    except KeyError as exc:
        raise TreeGrammarError(f"unknown tree grammar {name!r}") from exc


def check_namespace(points: Iterable[object], subject_id: str) -> None:
    roots = {
        point.knowledge_point_id.split(".", 1)[0]
        for point in points
    }
    if roots != {subject_id}:
        raise TreeGrammarError(
            f"tree namespace must equal registered subject {subject_id!r}; "
            f"got {sorted(roots)!r}"
        )


def check_syntax(points: Iterable[object], grammar: TreeGrammar) -> None:
    ids = [point.knowledge_point_id for point in points]
    markers: set[str] = set()
    if any(
        NUMBERED_CHAPTER_RE.fullmatch(point_id)
        or NUMBERED_SECTION_RE.fullmatch(point_id)
        for point_id in ids
    ):
        markers.add("numbered_chapters")
    if any(NAMED_CHAPTER_RE.fullmatch(point_id) for point_id in ids):
        markers.add("named_chapters")

    if len(markers) > 1:
        raise TreeGrammarError(
            "ambiguous id syntax: both numbered and named chapter markers are present"
        )
    if markers and grammar.name not in markers:
        marker = next(iter(markers))
        raise TreeGrammarError(
            f"registered {grammar.name} grammar conflicts with {marker} id syntax"
        )


def chapter_scope_failures(points: Iterable[object], grammar: TreeGrammar) -> list[str]:
    failures: list[str] = []
    for point in points:
        point_id = point.knowledge_point_id
        is_chapter = bool(
            grammar.chapter_pattern
            and grammar.chapter_pattern.fullmatch(point_id)
        )
        if is_chapter and point.scope != "chapter":
            failures.append(
                f"{point_id}: id matches chapter pattern but scope={point.scope!r}"
            )
        if point.scope == "chapter" and not is_chapter:
            failures.append(
                f"{point_id}: scope='chapter' but id does not match "
                f"{grammar.name} chapter pattern"
            )
    return failures


def is_numbered_section(point_id: str) -> bool:
    return bool(NUMBERED_SECTION_RE.fullmatch(point_id))
