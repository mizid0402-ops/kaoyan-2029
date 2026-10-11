"""M4 validation for the CS408 weighted knowledge tree.

Contract: ``contracts/knowledge_tree.md``. Public interfaces: ``load_doc``,
``validate``, ``validate_alias_provenance`` and ``main``.

Deliberately does not import the builder's internal state --
it only reads the emitted YAML plus the three raw source files, so a bug in
the builder cannot also hide from the checks that are meant to catch it.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from ky.workspace import load_workspace  # noqa: E402
from cs408_outline_extract import extract_2022, key as base_key  # noqa: E402

WORKSPACE = load_workspace(ROOT / "kaoyan.workspace.yaml")
BASELINE_TREE_PATH = WORKSPACE.knowledge_trees["cs408"]

EXPECTED_WEIGHT = {
    "dual_source_exact": {1.0},
    "structural_equivalent": {0.75},
    "candidate_recent_new": {0.75},
    "legacy_only_pending": {0.5},
    "single_source_unverified": {0.5},
    # OCR-risk items inherit whatever weight their underlying match kind
    # earned (an exact match with an OCR-glitched character is still 1.00;
    # a containment/fuzzy match is 0.75) -- see the historical report section 2.
    "text_layer_ocr_risk": {0.75, 1.0},
}
VALID_STATUS = {"extracted", "reviewed"}
VALID_SCOPES = {"subject", "chapter", "section", "item"}


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_doc(path: Path) -> dict:
    doc = load_yaml(path)
    if not isinstance(doc, dict) or "items" not in doc:
        raise ValueError("weighted tree must be a mapping with an 'items' list")
    return doc


def _validate_node_identity(
    idx: int, node: dict, seen_ids: set[str], errors: list[str]
) -> str | None:
    path = f"items[{idx}]"
    pid = node.get("knowledge_point_id")
    if not pid:
        errors.append(f"{path}: missing knowledge_point_id")
        return None
    path = f"items[{pid}]"
    if pid in seen_ids:
        errors.append(f"{path}: duplicate knowledge_point_id")
    seen_ids.add(pid)
    return path


def _validate_node_status_and_scope(path: str, node: dict, errors: list[str]) -> None:
    status = node.get("status")
    if status not in VALID_STATUS:
        errors.append(f"{path}: status {status!r} not in {sorted(VALID_STATUS)}")
    if status == "approved":
        errors.append(f"{path}: status=approved is forbidden for AI-generated trees")

    scope = node.get("scope")
    if scope not in VALID_SCOPES:
        errors.append(f"{path}: scope {scope!r} not in {sorted(VALID_SCOPES)}")


def _validate_node_sources(path: str, node: dict, errors: list[str]) -> None:
    sources = node.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{path}: sources must be a non-empty list")
        sources = []
    source_count = node.get("source_count")
    if source_count != len(sources):
        errors.append(f"{path}: source_count={source_count} != len(sources)={len(sources)}")


def _validate_node_weight(path: str, node: dict, errors: list[str]) -> None:
    tag = node.get("evidence_tag")
    weight = node.get("weight")
    if tag not in EXPECTED_WEIGHT:
        errors.append(f"{path}: unknown evidence_tag {tag!r}")
    elif weight not in EXPECTED_WEIGHT[tag]:
        errors.append(
            f"{path}: weight={weight!r} not allowed for evidence_tag={tag!r} "
            f"(expected one of {sorted(EXPECTED_WEIGHT[tag])})"
        )


def _validate_node_aliases(path: str, node: dict, errors: list[str]) -> None:
    aliases = node.get("aliases")
    if aliases is None:
        errors.append(f"{path}: aliases must be a list (may be empty)")
    elif not isinstance(aliases, list):
        errors.append(f"{path}: aliases must be a list")
    else:
        for ai, alias in enumerate(aliases):
            if not isinstance(alias, dict) or "text" not in alias or "source" not in alias:
                errors.append(f"{path}.aliases[{ai}]: must be a mapping with text/source")


def _validate_baseline_ids(seen_ids: set[str], errors: list[str]) -> None:
    baseline_ids = {n["knowledge_point_id"] for n in load_yaml(BASELINE_TREE_PATH)}
    missing = baseline_ids - seen_ids
    if missing:
        errors.append(
            f"weighted tree is missing {len(missing)} baseline ids, e.g. {sorted(missing)[:3]}"
        )


def _validate_sources_registry(doc: dict, errors: list[str]) -> None:
    registry = doc.get("sources_registry", {})
    for tag_name in ("A", "B"):
        entry = registry.get(tag_name, {})
        path = Path(entry.get("path", ""))
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            errors.append(f"sources_registry.{tag_name}.path does not exist: {path}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry.get("sha256"):
            errors.append(
                f"sources_registry.{tag_name}.sha256 mismatch: recorded={entry.get('sha256')} "
                f"actual={actual}"
            )


def validate(doc: dict) -> list[str]:
    """Return a list of human-readable errors; empty means the tree is valid."""
    errors: list[str] = []
    items = doc.get("items")
    if not isinstance(items, list) or not items:
        return ["items must be a non-empty list"]

    seen_ids: set[str] = set()
    for idx, node in enumerate(items):
        path = _validate_node_identity(idx, node, seen_ids, errors)
        if path is None:
            continue
        _validate_node_status_and_scope(path, node, errors)
        _validate_node_sources(path, node, errors)
        _validate_node_weight(path, node, errors)
        _validate_node_aliases(path, node, errors)

    _validate_baseline_ids(seen_ids, errors)
    _validate_sources_registry(doc, errors)
    return errors


def validate_alias_provenance(doc: dict) -> list[str]:
    """Every alias tagged source=B must actually occur in the 2022 PDF text
    (matched via the same key() normalization the builder used, so a
    genuinely-fabricated alias -- text nowhere in the source -- fails)."""
    errors: list[str] = []
    source_path = Path(doc["sources_registry"]["B"]["path"])
    if not source_path.is_absolute():
        source_path = ROOT / source_path
    d22 = extract_2022(source_path)
    full_key = base_key(d22["normalized_source_text"])
    for node in doc.get("items", []):
        pid = node.get("knowledge_point_id")
        for ai, alias in enumerate(node.get("aliases") or []):
            if alias.get("source") != "B":
                continue
            k = base_key(alias["text"])
            if k and k not in full_key:
                errors.append(
                    f"items[{pid}].aliases[{ai}]: alias text not found in source B full text: "
                    f"{alias['text']!r}"
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a CS408 weighted tree")
    parser.add_argument("--tree", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = load_doc(args.tree)
    errors = validate(doc) + validate_alias_provenance(doc)
    if errors:
        print(f"INVALID: {len(errors)} error(s)")
        for e in errors:
            print(" -", e)
        return 1
    print(f"VALID: {len(doc['items'])} nodes, 0 errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
