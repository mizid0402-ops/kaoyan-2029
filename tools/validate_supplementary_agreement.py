"""M4 validation for the registered supplementary agreement table.

Contract: ``contracts/knowledge_tree.md``. Public interfaces: ``load_agreement``,
``load_main_source_counts``, ``validate`` and ``main``.

Deliberately does not import the historical split builder's internal state --
it only reads the two emitted YAML files plus tree_source_support.py's public
lookup table, so a bug in the builder cannot also hide from the checks meant
to catch it (same design principle as the weighted-tree validator).

Checks:
  1. Own small schema: every item has the expected keys, no more, no less;
     types and value sets are checked directly (not delegated to the
     knowledge-point contract -- this file is declared to NOT go through it).
  2. Every knowledge_point_id in the agreement table exists in the main
     table.
  3. Every knowledge_point_id in the main table exists in the agreement
     table (the two are meant to be in lockstep, 1:1).
  4. source_support is independently re-derived from
     tools/tree_source_support.derive_source_support() and must match the
     stored value exactly.
  5. source_count matches len(sources) for that same node in the main table
     (catches the split producing an agreement entry that claims more/fewer
     sources than the main table actually cites).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from ky.workspace import load_workspace  # noqa: E402
from tree_source_support import (  # noqa: E402
    KNOWN_COMBINATIONS,
    UnknownSourceSupportCombination,
    derive_source_support,
)

WORKSPACE = load_workspace(ROOT / "kaoyan.workspace.yaml")
SUPPLEMENTARY = WORKSPACE.supplementary["cs408_multisource"]
MAIN_TREE_PATH = SUPPLEMENTARY.files["tree"]
AGREEMENT_PATH = SUPPLEMENTARY.files["agreement"]

_ITEM_KEYS = {
    "knowledge_point_id", "source_support", "source_count", "evidence_tag",
    "match_kind", "baseline_relation", "aliases", "review_note",
}
_REQUIRED_ITEM_KEYS = _ITEM_KEYS - {"review_note"}
_VALID_BASELINE_RELATION = {"kept", "new_vs_baseline"}
_VALID_SOURCE_SUPPORT = {0.5, 0.75, 1.0}
_VALID_EVIDENCE_TAGS = {tag for tag, _, _ in KNOWN_COMBINATIONS}


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_agreement(path: Path = AGREEMENT_PATH) -> dict:
    doc = load_yaml(path)
    if not isinstance(doc, dict) or "items" not in doc:
        raise ValueError("agreement table must be a mapping with an 'items' list")
    return doc


def load_main_source_counts(path: Path = MAIN_TREE_PATH) -> dict[str, int]:
    items = load_yaml(path)
    return {n["knowledge_point_id"]: len(n["sources"]) for n in items}


def _validate_identity(
    idx: int, node: dict, seen_ids: set[str], errors: list[str]
) -> tuple[str | None, str]:
    path = f"items[{idx}]"
    pid = node.get("knowledge_point_id")
    if not pid:
        errors.append(f"{path}: missing knowledge_point_id")
        return None, path
    path = f"items[{pid}]"
    if pid in seen_ids:
        errors.append(f"{path}: duplicate knowledge_point_id")
    seen_ids.add(pid)
    return pid, path


def _validate_item_schema(path: str, node: dict, errors: list[str]) -> bool:
    extra = set(node) - _ITEM_KEYS
    if extra:
        errors.append(f"{path}: unknown field(s) {sorted(extra)}")
    missing = _REQUIRED_ITEM_KEYS - set(node)
    if missing:
        errors.append(f"{path}: missing field(s) {sorted(missing)}")
        return False
    return True


def _validate_item_values(
    path: str, node: dict, pid: str, main_source_counts: dict[str, int], errors: list[str]
) -> None:
    baseline_relation = node.get("baseline_relation")
    if baseline_relation not in _VALID_BASELINE_RELATION:
        errors.append(
            f"{path}: baseline_relation {baseline_relation!r} "
            f"not in {sorted(_VALID_BASELINE_RELATION)}"
        )

    evidence_tag = node.get("evidence_tag")
    if evidence_tag not in _VALID_EVIDENCE_TAGS:
        errors.append(f"{path}: unknown evidence_tag {evidence_tag!r}")

    source_support = node.get("source_support")
    if source_support not in _VALID_SOURCE_SUPPORT:
        errors.append(
            f"{path}: source_support {source_support!r} not in {sorted(_VALID_SOURCE_SUPPORT)}"
        )

    source_count = node.get("source_count")
    actual_source_count = main_source_counts[pid]
    if source_count != actual_source_count:
        errors.append(
            f"{path}: source_count={source_count!r} != main table's actual "
            f"len(sources)={actual_source_count}"
        )

    _validate_derived_support(path, node, evidence_tag, source_count, source_support, errors)
    _validate_aliases(path, node, errors)


def _validate_derived_support(
    path: str, node: dict, evidence_tag: str, source_count: object,
    source_support: object, errors: list[str],
) -> None:
    match_kind = node.get("match_kind")
    try:
        derived = derive_source_support(evidence_tag, source_count, match_kind)
    except UnknownSourceSupportCombination as exc:
        errors.append(f"{path}: {exc}")
    else:
        if derived != source_support:
            errors.append(
                f"{path}: source_support={source_support!r} does not match "
                f"derive_source_support(...)={derived!r}"
            )


def _validate_aliases(path: str, node: dict, errors: list[str]) -> None:
    aliases = node.get("aliases")
    if not isinstance(aliases, list):
        errors.append(f"{path}: aliases must be a list")
    else:
        for ai, alias in enumerate(aliases):
            if not isinstance(alias, dict) or "text" not in alias or "source" not in alias:
                errors.append(f"{path}.aliases[{ai}]: must be a mapping with text/source")


def _validate_missing_agreement_ids(
    main_source_counts: dict[str, int], seen_ids: set[str], errors: list[str]
) -> None:
    missing_from_agreement = set(main_source_counts) - seen_ids
    if missing_from_agreement:
        errors.append(
            f"agreement table is missing {len(missing_from_agreement)} id(s) present in the main "
            f"table, e.g. {sorted(missing_from_agreement)[:3]}"
        )


def validate(doc: dict, main_source_counts: dict[str, int]) -> list[str]:
    errors: list[str] = []
    items = doc.get("items")
    if not isinstance(items, list) or not items:
        return ["items must be a non-empty list"]

    seen_ids: set[str] = set()
    for idx, node in enumerate(items):
        pid, path = _validate_identity(idx, node, seen_ids, errors)
        if pid is None or not _validate_item_schema(path, node, errors):
            continue
        if pid not in main_source_counts:
            errors.append(
                f"{path}: knowledge_point_id not found in main table {MAIN_TREE_PATH.name}"
            )
            continue
        _validate_item_values(path, node, pid, main_source_counts, errors)

    _validate_missing_agreement_ids(main_source_counts, seen_ids, errors)
    return errors


def main() -> int:
    doc = load_agreement()
    main_source_counts = load_main_source_counts()
    errors = validate(doc, main_source_counts)
    if errors:
        print(f"INVALID: {len(errors)} error(s)")
        for e in errors:
            print(" -", e)
        return 1
    print(f"VALID: {len(doc['items'])} agreement entries, 0 errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
