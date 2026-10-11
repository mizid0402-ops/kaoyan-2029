"""M25 syllabus migration port (``contracts/syllabus_migration.md``).

Public interfaces are :func:`resolve_mapping_chain`, :func:`plan_queue_migration`,
and :func:`check_queue_references`. Mapping and tree I/O belongs to M4 consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Sequence

from ky.knowledge.syllabus_mapping import SyllabusMapping
from ky.models import ContractError, ReviewItem


@dataclass(frozen=True)
class MigrationPlan:
    """Complete replacement queue plus deterministic change classifications."""

    items: tuple[ReviewItem, ...]
    unchanged: tuple[str, ...]
    renamed: tuple[str, ...]
    split: tuple[str, ...]
    retired: tuple[str, ...]
    merged: tuple[str, ...]


def resolve_mapping_chain(
    mappings: Sequence[SyllabusMapping], from_version: str, to_version: str
) -> tuple[SyllabusMapping, ...]:
    """Resolve the unique directed version chain from ``from_version`` to ``to_version``."""
    edges: dict[str, list[SyllabusMapping]] = {}
    pairs: set[tuple[str, str]] = set()
    for mapping in mappings:
        pair = (mapping.from_version, mapping.to_version)
        if pair in pairs:
            raise ContractError(f"duplicate mapping edge {pair[0]} -> {pair[1]}", "mappings")
        pairs.add(pair)
        edges.setdefault(mapping.from_version, []).append(mapping)
    _reject_cycles(edges)
    if from_version == to_version:
        return ()
    paths = _find_paths(edges, from_version, to_version)
    if not paths:
        raise ContractError(f"no mapping path {from_version} -> {to_version}", "mappings")
    if len(paths) != 1:
        raise ContractError(f"multiple mapping paths {from_version} -> {to_version}", "mappings")
    return tuple(paths[0])


def _reject_cycles(edges: Mapping[str, Sequence[SyllabusMapping]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(version: str) -> None:
        if version in visiting:
            raise ContractError(f"mapping cycle includes version {version}", "mappings")
        if version in visited:
            return
        visiting.add(version)
        for mapping in edges.get(version, ()):
            visit(mapping.to_version)
        visiting.remove(version)
        visited.add(version)

    for version in edges:
        visit(version)


def _find_paths(
    edges: Mapping[str, Sequence[SyllabusMapping]], start: str, target: str
) -> list[list[SyllabusMapping]]:
    found: list[list[SyllabusMapping]] = []

    def walk(version: str, path: list[SyllabusMapping]) -> None:
        if len(found) == 2:
            return
        if version == target:
            found.append(path)
            return
        for mapping in edges.get(version, ()):
            walk(mapping.to_version, [*path, mapping])

    walk(start, [])
    return found


def plan_queue_migration(
    items: Sequence[ReviewItem], chain: Sequence[SyllabusMapping], *, subject_id: str
) -> MigrationPlan:
    """Apply each mapping to one subject while preserving queue history and other items."""
    current = list(items)
    renamed: set[str] = set()
    split: set[str] = set()
    retired: set[str] = set()
    merged: set[str] = set()
    for mapping in chain:
        current, renamed_step, split_step, retired_step = _apply_mapping(
            current, mapping, subject_id
        )
        renamed.update(renamed_step)
        split.update(split_step)
        retired.update(retired_step)
        current, merged_step = _merge_duplicates(current, subject_id)
        merged.update(merged_step)
        retired.update(merged_step)
    classified = renamed | split | retired | merged
    unchanged = {
        item.review_id for item in items if item.review_id not in classified
    }
    return MigrationPlan(
        tuple(sorted(current, key=lambda item: item.review_id)),
        tuple(sorted(unchanged)), tuple(sorted(renamed)), tuple(sorted(split)),
        tuple(sorted(retired)), tuple(sorted(merged)),
    )


def _apply_mapping(
    items: list[ReviewItem], mapping: SyllabusMapping, subject_id: str
) -> tuple[list[ReviewItem], set[str], set[str], set[str]]:
    output: list[ReviewItem] = []
    renamed: set[str] = set()
    split: set[str] = set()
    retired: set[str] = set()
    dangling: set[str] = set()
    generated_ids = {item.review_id for item in items}
    for item in items:
        if item.subject_id != subject_id or item.state == "retired":
            output.append(item)
            continue
        try:
            targets = mapping.targets(item.knowledge_point_id)
        except ContractError:
            dangling.add(item.review_id)
            output.append(item)
            continue
        if targets == (item.knowledge_point_id,):
            output.append(item)
        elif len(targets) == 1:
            renamed.add(item.review_id)
            output.append(replace(
                item, knowledge_point_id=targets[0], revision=item.revision + 1
            ))
        elif len(targets) > 1:
            split.add(item.review_id)
            retired.add(item.review_id)
            output.append(replace(item, state="retired", revision=item.revision + 1))
            for target in targets:
                review_id = f"{item.review_id}>{target}"
                if review_id in generated_ids:
                    raise ContractError(f"split review_id collision: {review_id}", "items")
                generated_ids.add(review_id)
                output.append(replace(
                    item, review_id=review_id, revision=1, knowledge_point_id=target,
                    defer_count=0,
                ))
        else:
            retired.add(item.review_id)
            output.append(replace(item, state="retired", revision=item.revision + 1))
    if dangling:
        ids = ", ".join(sorted(dangling))
        raise ContractError(f"source tree does not contain queue items: {ids}", "items")
    return output, renamed, split, retired


def _merge_duplicates(
    items: list[ReviewItem], subject_id: str
) -> tuple[list[ReviewItem], set[str]]:
    groups: dict[str, list[ReviewItem]] = {}
    for item in items:
        if item.subject_id == subject_id and item.state != "retired":
            groups.setdefault(item.knowledge_point_id, []).append(item)
    losers: set[str] = set()
    replaced: dict[str, ReviewItem] = {}
    for group in groups.values():
        if len(group) < 2:
            continue
        ordered = sorted(
            group,
            key=lambda item: (item.state != "queued", item.due_date, item.review_id),
        )
        for item in ordered[1:]:
            losers.add(item.review_id)
            replaced[item.review_id] = replace(
                item, state="retired", revision=item.revision + 1
            )
    return [replaced.get(item.review_id, item) for item in items], losers


def check_queue_references(
    items: Sequence[ReviewItem], tree_ids_by_subject: Mapping[str, frozenset[str] | set[str]]
) -> list[str]:
    """Report active queue references absent from each subject's effective tree."""
    problems: list[str] = []
    for item in items:
        if item.state == "retired":
            continue
        if item.subject_id not in tree_ids_by_subject:
            problems.append(f"{item.review_id}: 该科无生效树（{item.subject_id}）")
        elif item.knowledge_point_id not in tree_ids_by_subject[item.subject_id]:
            problems.append(
                f"{item.review_id}: 知识点 {item.knowledge_point_id} 不在科目 "
                f"{item.subject_id} 的生效树中"
            )
    return problems
