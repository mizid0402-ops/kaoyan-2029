"""Rebuild or check the M6 confidence-weighted topic-weight artifact."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ky.exam.topic_weights import aggregate_topic_weights
from ky.knowledge import KnowledgePointError, load_knowledge_points
from ky.models import ContractError, load_yaml_text
from ky.storage.atomic import replace_bytes
from ky.workspace import Workspace, load_workspace


def _relative_input(workspace: Workspace, value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ContractError("expected a workspace-relative path", field)
    parts = PurePosixPath(value).parts
    segments = value.split("/")
    if (
        "\\" in value
        or value.startswith("/")
        or ":" in value
        or any(part in {"", ".", ".."} for part in segments)
    ):
        raise ContractError("invalid workspace-relative path", field)
    path = workspace.root.joinpath(*parts)
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(workspace.root.resolve(strict=True))
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError("input path is missing or outside the workspace", field) from exc
    if not resolved.is_file():
        raise ContractError("expected a file", field)
    return resolved


def _read_json(path: Path, field: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read JSON: {exc}", field) from exc
    if not isinstance(value, Mapping):
        raise ContractError("expected a JSON object", field)
    return value


def _load_inputs(
    workspace: Workspace, *, read_current: bool
) -> tuple[Mapping[str, Any], dict, dict, Mapping[str, Any] | None]:
    manifest_path = workspace.require("reference.weight_batches")
    manifest = load_yaml_text(
        manifest_path.read_text(encoding="utf-8"), source=manifest_path.as_posix()
    )
    if not isinstance(manifest, Mapping):
        raise ContractError("expected a YAML mapping", "reference.weight_batches")
    raw_batches = manifest.get("batches")
    if not isinstance(raw_batches, list):
        raise ContractError("expected a batch list", "batches")

    coder_outputs: dict[str, Mapping[str, Any]] = {}
    for batch_index, batch in enumerate(raw_batches):
        if not isinstance(batch, Mapping):
            raise ContractError("expected a batch mapping", f"batches[{batch_index}]")
        outputs = batch.get("coders")
        if not isinstance(outputs, Mapping):
            raise ContractError("expected a coder path mapping", f"batches[{batch_index}].coders")
        for coder, relative in outputs.items():
            field = f"batches[{batch_index}].coders.{coder}"
            if not isinstance(relative, str):
                raise ContractError("expected a workspace-relative path", field)
            if relative in coder_outputs:
                continue
            path = _relative_input(workspace, relative, field)
            coder_outputs[relative] = _read_json(path, field)

    subjects = {
        batch.get("subject_id")
        for batch in raw_batches
        if isinstance(batch, Mapping) and isinstance(batch.get("subject_id"), str)
    }
    trees = {}
    for subject in subjects:
        tree_path = workspace.require(f"reference.knowledge_trees.{subject}")
        points = load_knowledge_points(tree_path)
        points_by_id = {point.knowledge_point_id: point for point in points}
        if len(points_by_id) != len(points):
            raise ContractError(
                "duplicate knowledge point ID",
                f"reference.knowledge_trees.{subject}",
            )
        trees[subject] = points_by_id
    current = None
    if read_current:
        current = _read_json(
            workspace.require("reference.topic_weights"), "reference.topic_weights"
        )
    return manifest, coder_outputs, trees, current


def _write_target(workspace: Workspace) -> Path:
    """Resolve the registered output while allowing the file to be absent."""
    key = "reference.topic_weights"
    root = workspace.root.resolve(strict=True)
    try:
        target = workspace.topic_weights.resolve(strict=False)
        target.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError("resolves outside the workspace", key) from exc
    if target.exists() and not target.is_file():
        raise ContractError("expected a file", key)
    return target


def _differences(expected: Any, actual: Any, path: str = "$") -> list[str]:
    if type(expected) is not type(actual):
        return [
            f"{path}: JSON types differ "
            f"({type(expected).__name__} != {type(actual).__name__})"
        ]
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        differences: list[str] = []
        for key in sorted(set(expected) | set(actual), key=str):
            field = f"{path}.{key}"
            if key not in expected:
                differences.append(f"{field}: unexpected {actual[key]!r}")
            elif key not in actual:
                differences.append(f"{field}: missing (expected {expected[key]!r})")
            else:
                differences.extend(_differences(expected[key], actual[key], field))
        return differences
    if isinstance(expected, list) and isinstance(actual, list):
        differences = []
        for index, (left, right) in enumerate(zip(expected, actual)):
            differences.extend(_differences(left, right, f"{path}[{index}]"))
        if len(expected) != len(actual):
            differences.append(f"{path}: list lengths differ ({len(expected)} != {len(actual)})")
        return differences
    if expected != actual:
        return [f"{path}: expected {expected!r}, got {actual!r}"]
    return []


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--write", action="store_true")
    parser.add_argument("--workspace", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        workspace = load_workspace(args.workspace)
        manifest, coder_outputs, trees, current = _load_inputs(
            workspace, read_current=args.check
        )
        rebuilt = aggregate_topic_weights(manifest, coder_outputs, trees)
        if args.check:
            assert current is not None
            differences = _differences(current, rebuilt)
            if differences:
                print("topic_weights.json differs from aggregation:", file=sys.stderr)
                for difference in differences:
                    print(f"- {difference}", file=sys.stderr)
                return 1
            print(
                "topic_weights.json matches registered batches "
                "(numeric equality, no tolerance; 0.0 == -0.0)"
            )
            return 0
        output = _write_target(workspace)
        text = json.dumps(rebuilt, ensure_ascii=False, indent=2) + "\n"
        # C3 / WP-G1: tracked data uses LF so its bytes and recorded hashes stay portable.
        replace_bytes(output, text.encode("utf-8"))
        print(f"wrote {output}")
        return 0
    except (ContractError, KnowledgePointError, OSError, UnicodeError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
