"""Temporary-workspace contract checks for the CS408 PPT data pipeline."""

from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from ky.knowledge import load_knowledge_points
from ky.workspace import load_workspace
from tools.build_408_deck_scaffold import LEGACY_MARKER, build_scaffold
from tools.extract_cs408_bundle import build_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = REPO_ROOT / "kaoyan.workspace.yaml"
PRE_MIGRATION_COMMIT = "762786f"
# HEAD changes with the worktree and can point at the migrated code under test.
ALLOWED_ADDED_OUTPUTS: set[str] = set()
TEXT_OUTPUT_SUFFIXES = frozenset({".md", ".csv", ".json", ".yaml", ".yml", ".txt"})


def _copy_registered_file(source: Path, root: Path, relative: str) -> str:
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return relative


def _fixture_workspace(root: Path):
    original = load_workspace(REGISTRY)
    view = next(iter(original.supplementary.values()))
    subject = view.subject
    document = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    effective_rel = f"data/structured_materials/{subject}/knowledge_tree.yaml"
    tree_rel = f"data/structured_materials/{subject}/knowledge_tree_multisource.yaml"
    agreement_rel = f"data/structured_materials/{subject}/knowledge_tree_agreement.yaml"
    _copy_registered_file(
        original.require(f"reference.knowledge_trees.{subject}"), root, effective_rel
    )
    _copy_registered_file(view.files["tree"], root, tree_rel)
    _copy_registered_file(view.files["agreement"], root, agreement_rel)
    index_relatives = []
    for index, path in enumerate(original.require_all(
        f"reference.exam_indexes.{subject}"
    )):
        relative = f"data/exam_questions/408_index_{index}.json"
        _copy_registered_file(path, root, relative)
        index_relatives.append(relative)

    document["reference"]["knowledge_trees"] = {subject: effective_rel}
    document["reference"].pop("syllabus_versions", None)
    document["reference"]["exam_indexes"] = {subject: index_relatives}
    document["supplementary"] = {
        view.name: {
            "kind": view.kind,
            "subject": view.subject,
            "description": view.description,
            "files": {"tree": tree_rel, "agreement": agreement_rel},
        }
    }
    product_rel = "review/408知识点树与真题"
    document["products"]["cs408_lecture_workspace"] = product_rel
    (root / product_rel).mkdir(parents=True, exist_ok=True)
    registry = root / "kaoyan.workspace.yaml"
    registry.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )
    return load_workspace(registry), root / product_rel


def _head_script(relative_path: str, destination: Path) -> None:
    result = subprocess.run(
        ["git", "show", f"{PRE_MIGRATION_COMMIT}:{relative_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    source = result.stdout.decode("utf-8")
    if 'Path(r"F:\\workspace\\kaoyan-ai-system")' not in source:
        raise AssertionError(f"{relative_path} is not the pre-migration source")
    lines = source.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("ROOT = Path("):
            lines[index] = "ROOT = Path(__file__).resolve().parents[1]"
            break
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def _drop_csv_columns(raw: bytes, columns: set[str]) -> bytes:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    original_fields = reader.fieldnames or []
    if set(original_fields) & columns != columns:
        raise AssertionError("expected CSV columns were not added")
    fieldnames = [name for name in original_fields if name not in columns]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(
        {name: row[name] for name in fieldnames}
        for row in reader
    )
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def _drop_tree_json_columns(raw: bytes, columns: set[str]) -> bytes:
    rows = json.loads(raw.decode("utf-8"))
    for row in rows:
        if set(row) & columns != columns:
            raise AssertionError("expected JSON columns were not added")
        for column in columns:
            row.pop(column)
    serialized = json.dumps(rows, ensure_ascii=False, indent=1).encode("utf-8")
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    return serialized.replace(b"\n", newline)


def _row_node_id(line: str) -> str | None:
    parts = line.split("`", 2)
    if len(parts) < 3:
        return None
    return parts[1]


def _strip_outline_markers(raw: bytes, legacy_ids: set[str]) -> bytes:
    lines = raw.decode("utf-8").splitlines(keepends=True)
    cleaned = []
    for line in lines:
        if (
            LEGACY_MARKER in line
            and line.lstrip().startswith("- `")
            and _row_node_id(line) in legacy_ids
        ):
            line = line.replace(LEGACY_MARKER, "")
        cleaned.append(line)
    return "".join(cleaned).encode("utf-8")


def _strip_deck_additions(
    raw: bytes, relative: str, legacy_ids: set[str], view_line: str
) -> bytes:
    """Remove only the authorised additions; anything else must survive and fail the compare.

    Only the one exact supplementary-view line is removed (sol round 50, T4): a second line with
    the same prefix is unauthorised text and must stay in, so the byte comparison catches it.
    """
    lines = raw.decode("utf-8").splitlines(keepends=True)
    cleaned = []
    skip_blank = False
    for line in lines:
        if line.rstrip("\r\n") == view_line:
            skip_blank = True
            continue
        if skip_blank and line.rstrip("\r\n") == "":
            skip_blank = False
            continue
        skip_blank = False
        if LEGACY_MARKER in line and (
            (line.startswith("# ") and Path(relative).stem in legacy_ids)
            or (
                line.lstrip().startswith("- `")
                and _row_node_id(line) in legacy_ids
            )
        ):
            line = line.replace(LEGACY_MARKER, "")
        cleaned.append(line)
    return "".join(cleaned).encode("utf-8")


def _remove_manifest_addition(raw: bytes) -> bytes:
    lines = raw.splitlines(keepends=True)
    key_line = b'  "supplementary_view": {'
    start = next(
        (sum(map(len, lines[:index])) for index, line in enumerate(lines)
         if line.startswith(key_line)),
        None,
    )
    if start is None:
        raise AssertionError("supplementary_view manifest key is missing")
    value_start = raw.index(b"{", start)
    depth = 0
    in_string = False
    escaped = False
    value_end = None
    for index in range(value_start, len(raw)):
        byte = raw[index]
        if in_string:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == ord('"'):
                in_string = False
            continue
        if byte == ord('"'):
            in_string = True
        elif byte == ord("{"):
            depth += 1
        elif byte == ord("}"):
            depth -= 1
            if depth == 0:
                value_end = index + 1
                break
    if value_end is None:
        raise AssertionError("supplementary_view manifest value is incomplete")
    newline_end = raw.find(b"\n", value_end)
    if newline_end == -1 or raw[value_end:newline_end].strip() != b",":
        raise AssertionError("supplementary_view manifest field has unexpected format")
    return raw[:start] + raw[newline_end + 1:]


def _assert_output_bytes_match(test: unittest.TestCase, old: Path, current: Path) -> None:
    old_files = {path.relative_to(old).as_posix() for path in old.rglob("*") if path.is_file()}
    current_files = {
        path.relative_to(current).as_posix() for path in current.rglob("*") if path.is_file()
    }
    test.assertEqual(current_files - old_files, ALLOWED_ADDED_OUTPUTS)
    test.assertEqual(old_files - current_files, set())

    extra_columns = {"is_effective", "view_name"}
    with (current / "tree_flat.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    legacy_ids = {
        row["knowledge_point_id"] for row in rows if row["is_effective"].lower() != "true"
    }
    view = json.loads((current / "manifest.json").read_text(encoding="utf-8"))[
        "supplementary_view"
    ]
    for relative in sorted(old_files):
        old_raw = (old / relative).read_bytes()
        current_raw = (current / relative).read_bytes()
        if Path(relative).suffix in TEXT_OUTPUT_SUFFIXES:
            # C3 / WP-G1: some writers in this pipeline now emit LF while the pinned baseline
            # wrote CRLF on Windows (others, like the deck scaffold, still write CRLF: their
            # products are not tracked data). Line endings are the only difference allowed.
            old_raw = old_raw.replace(b"\r\n", b"\n")
            current_raw = current_raw.replace(b"\r\n", b"\n")
        if relative == "tree_flat.csv":
            # The csv module re-serializes with CRLF; compare line endings the same way (C3).
            dropped = _drop_csv_columns(current_raw, extra_columns).replace(b"\r\n", b"\n")
            test.assertEqual(dropped, old_raw)
        elif relative == "tree_flat.json":
            test.assertEqual(_drop_tree_json_columns(current_raw, extra_columns), old_raw)
        elif relative == "tree_outline.md":
            test.assertEqual(_strip_outline_markers(current_raw, legacy_ids), old_raw)
        elif relative == "coverage.md":
            test.assertEqual(current_raw, old_raw)
        elif relative == "manifest.json":
            old_manifest = json.loads(old_raw.decode("utf-8"))
            current_manifest = json.loads(current_raw.decode("utf-8"))
            test.assertEqual(set(current_manifest) - set(old_manifest), {"supplementary_view"})
            test.assertEqual(set(old_manifest) - set(current_manifest), set())
            test.assertEqual(
                set(current_manifest["supplementary_view"]),
                {"view_name", "kind", "description"},
            )
            test.assertEqual(_remove_manifest_addition(current_raw), old_raw)
        elif relative.startswith("deck/") and relative.endswith(".md"):
            current_lines = current_raw.decode("utf-8").splitlines()
            view_line = (
                f"补充视图：`{view['view_name']}` — {view['description']}"
            )
            test.assertEqual(current_lines.count(view_line), 1, msg=relative)
            test.assertEqual(
                _strip_deck_additions(current_raw, relative, legacy_ids, view_line), old_raw,
                msg=relative,
            )
        else:
            test.assertEqual(current_raw, old_raw, msg=relative)


class Cs408LecturePipelineTest(unittest.TestCase):
    def test_bundle_and_scaffold_use_registered_paths_and_mark_legacy_nodes(self) -> None:
        original = load_workspace(REGISTRY)
        source = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "portable-workspace"
            root.mkdir()
            product = root / "products" / "lecture"
            product.mkdir(parents=True)

            effective_relative = _copy_registered_file(
                original.require("reference.knowledge_trees.cs408"),
                root,
                "registered/live-tree/source.yaml",
            )
            supplementary = original.supplementary["cs408_multisource"]
            tree_relative = _copy_registered_file(
                original.require("supplementary.cs408_multisource.files.tree"),
                root,
                "registered/supplementary/tree.yaml",
            )
            agreement_relative = _copy_registered_file(
                original.require("supplementary.cs408_multisource.files.agreement"),
                root,
                "registered/supplementary/notes.yaml",
            )
            index_relatives = []
            for index_path in original.require_all("reference.exam_indexes.cs408"):
                relative = f"registered/indexes/{index_path.name}"
                index_relatives.append(
                    _copy_registered_file(index_path, root, relative)
                )

            source["reference"]["knowledge_trees"]["cs408"] = effective_relative
            source["reference"].pop("syllabus_versions", None)
            source["reference"]["exam_indexes"]["cs408"] = index_relatives
            source["supplementary"]["cs408_multisource"]["files"] = {
                "tree": tree_relative,
                "agreement": agreement_relative,
            }
            source["products"]["cs408_lecture_workspace"] = "products/lecture"
            registry_path = root / "kaoyan.workspace.yaml"
            registry_path.write_text(
                yaml.safe_dump(source, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
                newline="\n",
            )
            workspace = load_workspace(registry_path)
            effective_ids = {
                point.knowledge_point_id
                for point in load_knowledge_points(
                    workspace.require("reference.knowledge_trees.cs408"),
                )
            }
            supplementary_points = load_knowledge_points(
                workspace.require("supplementary.cs408_multisource.files.tree"),
            )
            supplementary_ids = {
                point.knowledge_point_id for point in supplementary_points
            }
            legacy_ids = supplementary_ids - effective_ids

            result = build_bundle(workspace)
            deck_files = build_scaffold(workspace)
            with (product / "tree_flat.csv").open(
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                tree_rows = list(csv.DictReader(stream))
            by_id = {row["knowledge_point_id"]: row for row in tree_rows}
            self.assertEqual(set(by_id), supplementary_ids)
            for point_id, row in by_id.items():
                self.assertEqual(
                    row["is_effective"].lower() == "true",
                    point_id in effective_ids,
                )
                self.assertEqual(row["view_name"], supplementary.name)

            manifest = json.loads((product / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["supplementary_view"]["view_name"], supplementary.name)
            self.assertEqual(
                manifest["supplementary_view"]["description"],
                supplementary.description,
            )
            self.assertEqual(
                manifest["generated_from"]["tree"],
                tree_relative,
            )
            self.assertEqual(result["output"], product)

            for point_id in legacy_ids:
                row = by_id[point_id]
                deck_path = product / "deck" / f"{row['parent_id']}.md"
                self.assertIn(deck_path, deck_files)
                content = deck_path.read_text(encoding="utf-8")
                self.assertIn(point_id, content)
                self.assertIn(LEGACY_MARKER, content)

    def test_outputs_match_pre_migration_templates_with_only_allowed_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            old_root = base / "pre-migration"
            current_root = base / "current"
            _, old_product = _fixture_workspace(old_root)
            current_workspace, current_product = _fixture_workspace(current_root)
            old_tools = old_root / "tools"
            old_bundle = old_tools / "extract_cs408_bundle.py"
            old_scaffold = old_tools / "build_408_deck_scaffold.py"
            _head_script("tools/extract_cs408_bundle.py", old_bundle)
            _head_script("tools/build_408_deck_scaffold.py", old_scaffold)

            old_result = subprocess.run(
                [sys.executable, str(old_bundle)],
                cwd=old_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(old_result.returncode, 0, old_result.stdout + old_result.stderr)
            build_bundle(current_workspace)
            old_scaffold_result = subprocess.run(
                [sys.executable, str(old_scaffold)],
                cwd=old_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(
                old_scaffold_result.returncode,
                0,
                old_scaffold_result.stdout + old_scaffold_result.stderr,
            )
            build_scaffold(current_workspace)
            _assert_output_bytes_match(self, old_product, current_product)

            source_view = next(iter(current_workspace.supplementary.values()))
            current_manifest = json.loads(
                (current_product / "manifest.json").read_text(encoding="utf-8")
            )
            view_meta = current_manifest["supplementary_view"]
            self.assertEqual(
                view_meta,
                {
                    "view_name": source_view.name,
                    "kind": source_view.kind,
                    "description": source_view.description,
                },
            )

            # Sol's deletion probe: removing the practice-heading line must break comparison.
            with (current_product / "tree_flat.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                legacy_ids = {
                    row["knowledge_point_id"]
                    for row in csv.DictReader(stream)
                    if row["is_effective"].lower() != "true"
                }
            deck_name = next(
                path.name
                for path in current_product.glob("deck/*.md")
                if path.stem not in legacy_ids
            )
            current_deck = current_product / "deck" / deck_name
            old_deck = old_product / "deck" / deck_name
            probe_deck = base / "probe" / deck_name
            probe_deck.parent.mkdir(parents=True)
            probe_lines = current_deck.read_bytes().splitlines(keepends=True)
            removed = [line for line in probe_lines if b"### \xe7\xbb\x83\xe4\xb9\xa0\xe6\x8c\x87\xe5\x90\x91" in line]
            self.assertEqual(len(removed), 1)
            probe_deck.write_bytes(b"".join(line for line in probe_lines if line not in removed))
            probe_view_lines = [
                line
                for line in current_deck.read_text(encoding="utf-8").splitlines()
                if line.startswith("补充视图：")
            ]
            self.assertEqual(len(probe_view_lines), 1)
            with self.assertRaises(AssertionError):
                self.assertEqual(
                    _strip_deck_additions(
                        probe_deck.read_bytes(), f"deck/{deck_name}", legacy_ids,
                        probe_view_lines[0],
                    ),
                    _strip_deck_additions(
                        old_deck.read_bytes(), f"deck/{deck_name}", legacy_ids,
                        probe_view_lines[0],
                    ),
                )


class StripDeckAdditionsTest(unittest.TestCase):
    def test_an_unauthorised_line_with_the_view_prefix_is_not_stripped(self) -> None:
        view_line = "补充视图：`v` — d"
        original = "# t\n\n正文\n".encode("utf-8")
        with_view = f"# t\n\n{view_line}\n\n正文\n".encode("utf-8")
        self.assertEqual(
            _strip_deck_additions(with_view, "deck/x.md", set(), view_line), original
        )
        smuggled = f"# t\n\n{view_line}\n\n补充视图：unauthorized text\n正文\n".encode("utf-8")
        self.assertNotEqual(
            _strip_deck_additions(smuggled, "deck/x.md", set(), view_line), original
        )


if __name__ == "__main__":
    unittest.main()
