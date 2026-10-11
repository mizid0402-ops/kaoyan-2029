"""M4 hierarchy queries from ``contracts/knowledge_tree.md``.

Public interfaces are :func:`parent_id`, :func:`nearest_ancestor_with_scope`,
:func:`tree_parent`, and :func:`learnable_tree`. The shared ordered outline
serves M17 and M30; the existing prefix and scope queries retain M6 behavior.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Sequence
from typing import Any

from .knowledge_point import KnowledgePoint
from .tree_grammar import select_tree_grammar


@dataclass(frozen=True)
class LearnableTree:
    """Ordered outline after non-learnable subject trackers are removed."""

    points_by_id: Mapping[str, KnowledgePoint]
    parents: Mapping[str, str | None]
    children: Mapping[str, tuple[str, ...]]
    roots: tuple[str, ...]
    leaves: tuple[str, ...]
    trackers: tuple[str, ...]


def parent_id(point_id: str, tree_ids: Collection[str]) -> str | None:
    """Return the longest strict dot-separated prefix found in ``tree_ids``."""
    parts = point_id.split(".")
    for stop in range(len(parts) - 1, 0, -1):
        candidate = ".".join(parts[:stop])
        if candidate in tree_ids:
            return candidate
    return None


def nearest_ancestor_with_scope(
    point_id: str,
    points_by_id: Mapping[str, Any],
    scope: str,
) -> str | None:
    """Return the closest node at ``scope``, including ``point_id`` itself."""
    current = point_id
    tree_ids = points_by_id.keys()
    while current in points_by_id:
        point = points_by_id[current]
        if point.scope == scope:
            return current
        ancestor = parent_id(current, tree_ids)
        if ancestor is None:
            return None
        current = ancestor
    return None


def tree_parent(
    point_id: str,
    points_by_id: Mapping[str, Any],
    grammar: str,
) -> str | None:
    """Return the syllabus parent using the registered tree grammar."""
    selected = select_tree_grammar(grammar)
    if point_id not in points_by_id:
        raise ValueError(f"{point_id!r} is not a node of this tree")

    if selected.name == "named_chapters":
        for suffix in (".content", ".requirements"):
            if point_id.endswith(suffix):
                chapter = point_id[:-len(suffix)] + ".chapter"
                if chapter in points_by_id:
                    return chapter

    parent = parent_id(point_id, points_by_id.keys())
    if parent is not None:
        return parent

    parts = point_id.split(".")
    if len(parts) >= 2:
        subject = f"{parts[0]}.{parts[1]}.subject"
        if subject in points_by_id and subject != point_id:
            return subject
    return None


def learnable_tree(points: Sequence[KnowledgePoint], grammar: str) -> LearnableTree:
    """Build the shared ordered M17/M30 outline and identify subject trackers."""
    if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
        raise ValueError("points must be a sequence of KnowledgePoint")
    if any(not isinstance(point, KnowledgePoint) for point in points):
        raise ValueError("points must contain KnowledgePoint values")
    if not isinstance(grammar, str):
        raise ValueError("grammar must be a string")
    select_tree_grammar(grammar)
    points_by_id = {point.knowledge_point_id: point for point in points}
    if len(points_by_id) != len(points):
        raise ValueError("points contains duplicate knowledge_point_id")
    parents = {
        point_id: tree_parent(point_id, points_by_id, grammar)
        for point_id in points_by_id
    }
    descendants: dict[str, list[str]] = {point_id: [] for point_id in points_by_id}
    for point_id, parent in parents.items():
        if parent is not None:
            descendants[parent].append(point_id)
    trackers = tuple(
        point_id for point_id, point in points_by_id.items()
        if point.scope == "subject" and not any(
            points_by_id[descendant].scope != "subject"
            for descendant in _tree_descendants(point_id, descendants)
        )
    )
    tracker_set = set(trackers)
    active = set(points_by_id) - tracker_set
    children: dict[str, list[str]] = {point_id: [] for point_id in active}
    for point_id in points_by_id:
        if point_id not in active:
            continue
        parent = parents[point_id]
        if parent in active:
            children[parent].append(point_id)
    roots = tuple(
        point_id for point_id in points_by_id
        if point_id in active and parents[point_id] not in active
    )
    leaves = tuple(
        point_id for point_id in points_by_id
        if point_id in active and not children[point_id]
    )
    return LearnableTree(
        points_by_id, parents,
        {point_id: tuple(children[point_id]) for point_id in points_by_id if point_id in active},
        roots, leaves, trackers,
    )


def _tree_descendants(root: str, children: Mapping[str, Sequence[str]]) -> set[str]:
    found: set[str] = set()
    pending = list(children[root])
    while pending:
        current = pending.pop()
        found.add(current)
        pending.extend(children[current])
    return found
