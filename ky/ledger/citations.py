"""M3 citation gate from ``contracts/citation_gate.md``.

Public interfaces: :func:`check_knowledge_point_citations`,
:func:`check_ledger_citations`, and :func:`check_material_map`.

Cross-contract checks: can this knowledge point's sources actually hold up?

``ky.knowledge`` validates a knowledge point in isolation and ``ky.ledger``
validates a material in isolation. Neither can answer the question that
actually matters: *is the material this claim cites one the project is allowed
to derive claims from, and does it still hash to what was recorded?*

That is what this module does. Without it, the two contracts are independently
correct and jointly useless -- a knowledge point can cite a path that appears
in no ledger row, or in a row whose rights forbid structuring, and both files
pass their own checks.

Rules enforced here:

1. Every source path in a knowledge point must resolve to exactly one ledger
   entry. A dangling citation is a broken chain, not a warning.
2. That entry must ``may_be_structured()``: rights clear, structuring allowed,
   bytes held locally, and not withdrawn.
3. If the ledger records a digest, the citation's digest must match it exactly.
   A citation with its own invented hash is how a "verified provenance" claim
   becomes decorative.
4. In strict mode the cited file's bytes are re-read and hashed, so a changed
   file cannot be cited as intact. Strict mode is for the moment a claim moves
   from ``extracted`` to ``reviewed``; the cheap mode is for bulk preflight.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from ky.knowledge import KnowledgePoint, validate_knowledge_point

# Import from the sibling module, not from ``ky.ledger`` itself: the package
# ``__init__`` re-exports this module, so importing the package here would be a
# circular import.
from ky.ledger.material import LedgerError, Material, load_ledger, sha256_file

__all__ = [
    "CitationProblem",
    "CitationReport",
    "check_knowledge_point_citations",
    "check_material_map",
]


@dataclass(frozen=True)
class CitationProblem:
    """One reason a citation cannot support the claim that makes it."""

    knowledge_point_id: str
    source_index: int
    path: str
    reason: str


@dataclass(frozen=True)
class CitationReport:
    checked_points: int
    checked_citations: int
    problems: tuple[CitationProblem, ...]

    @property
    def ok(self) -> bool:
        return not self.problems

    def raise_for_problems(self) -> None:
        """Fail closed with a single located error naming every problem."""
        if self.ok:
            return
        detail = "; ".join(
            f"{p.knowledge_point_id}.sources[{p.source_index}] ({p.path}): {p.reason}"
            for p in self.problems
        )
        raise LedgerError(f"unsupported citations: {detail}", "sources")

    def summary(self) -> dict[str, object]:
        return {
            "checked_points": self.checked_points,
            "checked_citations": self.checked_citations,
            "ok": self.ok,
            "problems": [
                {
                    "knowledge_point_id": p.knowledge_point_id,
                    "source_index": p.source_index,
                    "path": p.path,
                    "reason": p.reason,
                }
                for p in self.problems
            ],
        }


def check_material_map(materials: Sequence[Material]) -> dict[str, Material]:
    """Index materials by storage path.

    Paths are normalised to POSIX form so a citation written with either
    separator resolves the same way.
    """
    index: dict[str, Material] = {}
    for material in materials:
        if material.storage.mode != "local_file" or material.storage.path is None:
            continue
        key = _normalise(material.storage.path)
        # The ledger already rejects duplicate resource_ids, but two rows may
        # still point at the same file. That is ambiguous, so refuse it here
        # rather than picking one silently.
        if key in index and index[key].resource_id != material.resource_id:
            raise LedgerError(
                f"storage path {key!r} is claimed by both "
                f"{index[key].resource_id!r} and {material.resource_id!r}; a citation "
                "must resolve to exactly one material",
                key,
            )
        index[key] = material
    return index


def _normalise(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _citation_rejection(
    point: KnowledgePoint,
    index: int,
    raw_path: str,
    cited_digest: str,
    material: Material | None,
    *,
    strict: bool,
    root: str | Path | None,
) -> CitationProblem | None:
    if material is None:
        reason = (
            "no ledger entry stores this path; register the material before "
            "citing it"
        )
    elif material.review_status == "withdrawn":
        reason = f"material {material.resource_id!r} is withdrawn"
    elif not material.rights.is_clear():
        reason = (
            f"material {material.resource_id!r} has rights.status="
            f"{material.rights.status!r}; an unclear right cannot authorise a claim"
        )
    elif not material.rights.may_be_structured:
        reason = (
            f"material {material.resource_id!r} does not permit structuring "
            "(may_be_structured: false)"
        )
    elif cited_digest != material.storage.sha256:
        reason = (
            f"cited sha256 does not match the ledger digest for "
            f"{material.resource_id!r}"
        )
    elif strict and not material.verify_bytes(root):
        reason = (
            f"stored bytes for {material.resource_id!r} are missing or no longer "
            "hash to the recorded digest"
        )
    else:
        return None
    return CitationProblem(point.knowledge_point_id, index, raw_path, reason)


def check_knowledge_point_citations(
    points: Iterable[KnowledgePoint | dict],
    materials: Sequence[Material],
    *,
    root: str | Path | None = None,
    strict: bool = False,
) -> CitationReport:
    """Verify that every citation resolves to a structurable, intact material.

    ``strict=True`` re-reads and hashes each cited file. Leave it off for bulk
    checks and turn it on at the transition that creates a real claim.
    """
    material_by_path = check_material_map(materials)
    problems: list[CitationProblem] = []
    checked_points = 0
    checked_citations = 0

    for entry in points:
        point = entry if isinstance(entry, KnowledgePoint) else validate_knowledge_point(entry)
        checked_points += 1
        for index, source in enumerate(point.sources):
            checked_citations += 1
            raw_path = str(source.get("path", ""))
            key = _normalise(raw_path)
            cited_digest = str(source.get("sha256", ""))
            rejection = _citation_rejection(
                point, index, raw_path, cited_digest, material_by_path.get(key),
                strict=strict, root=root,
            )
            if rejection is not None:
                problems.append(rejection)

    return CitationReport(
        checked_points=checked_points,
        checked_citations=checked_citations,
        problems=tuple(problems),
    )


def check_ledger_citations(
    ledger_path: str | Path,
    points: Iterable[KnowledgePoint | dict],
    *,
    root: str | Path | None = None,
    strict: bool = False,
) -> CitationReport:
    """Convenience wrapper: load the ledger, then check the citations."""
    return check_knowledge_point_citations(
        points, load_ledger(ledger_path), root=root, strict=strict
    )
