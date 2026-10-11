"""Deterministic verifier for a knowledge tree and its sources.

This is the tool the project's rules demand before any tree is called "done":

  1. Every node validates against the real contract (`ky.knowledge.knowledge_point`),
     not against a private re-implementation of it.
  2. Every `sources[i].sha256` equals the SHA-256 of the bytes actually on disk.
  3. Every `locator.quote_ref` can be located in the source file it points at,
     after comment stripping and whitespace normalisation (the same normalisation
     the extractor used).
  4. The tree grammar is selected from the registered subject profile, while
     `scope` is only consistency evidence. Chapter ids and scopes agree in both
     directions, a `chapter` node's id is an ancestor of its sections, ids are
     unique, and no language bans appear (subject nodes must be `subject`, etc.).
  5. Extracted nodes carry no validation evidence.

It prints a per-check summary and exits non-zero on the first category of failure
with concrete examples, so it can be used as a mutation-test oracle: break the
tree or a source file, and this must go red.

Usage:
    py -3.12 tools/verify_tree.py <tree.yaml> --workspace <registry.yaml>
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ky.knowledge.knowledge_point import (  # noqa: E402
    KnowledgePointError,
    load_knowledge_points,
)
from ky.knowledge.tree_grammar import (  # noqa: E402
    TreeGrammarError as TreeShapeError,
    check_namespace,
    check_syntax,
    chapter_scope_failures,
    select_tree_grammar,
)
from ky.models import ContractError  # noqa: E402
from ky.workspace import load_workspace  # noqa: E402

def norm(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", text)


def source_text(path: Path) -> str:
    """Source text the way the extractor sees it: tags stripped, comments removed."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    raw = re.sub(r"<script.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style.*?</style>", " ", raw, flags=re.I | re.S)
    return html.unescape(re.sub(r"<[^>]+>", "\n", raw))


def _registered_subject(workspace, tree_path: Path) -> tuple[str, str] | None:
    """Return (subject, registry key) for any registered knowledge tree."""
    for subject, registered in workspace.knowledge_trees.items():
        if registered.resolve() == tree_path:
            return subject, f"reference.knowledge_trees.{subject}"
    for subject, record in workspace.syllabus_versions.items():
        for version, registered in record.versions.items():
            if registered.resolve() == tree_path:
                return subject, f"reference.syllabus_versions.{subject}.versions.{version}"
    for name, view in workspace.supplementary.items():
        registered = view.files.get("tree")
        if registered is not None and registered.resolve() == tree_path:
            return view.subject, f"supplementary.{name}.files.tree"
    return None


def _resolve_subject(workspace, tree_path: Path, explicit: str | None) -> str:
    """Decide which subject profile (and so which tree grammar) validates this tree.

    Order: the tree's registration (effective or supplementary view), else an explicit
    --subject. The explicit form exists for D5's replacement workflow -- a candidate tree
    (e.g. a new syllabus year) must pass this verifier *before* it is registered.
    """
    registered = _registered_subject(workspace, tree_path)
    if registered is not None:
        subject, key = registered
        if explicit is not None and explicit != subject:
            raise ContractError(
                f"tree is registered under {subject!r} but --subject says {explicit!r}", "subject"
            )
        workspace.require(key)
        return subject
    if explicit is None:
        raise ContractError(
            "tree is not registered in the selected workspace; pass --subject <id> to verify "
            "a candidate tree before registering it",
            "tree",
        )
    if explicit not in workspace.subjects:
        raise ContractError(f"unknown subject {explicit!r}", "subject")
    return explicit


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("tree", type=Path)
    ap.add_argument("--workspace", type=Path, default=None)
    ap.add_argument("--subject", default=None,
                    help="subject ID for a tree not (yet) registered in the workspace")
    ap.add_argument("--require-scopes", default=None,
                    help="comma-separated scopes that must each appear at least once")
    ap.add_argument("--root", type=Path, default=None)
    return ap.parse_args(argv)


def _load_tree_context(args: argparse.Namespace):
    workspace = load_workspace(args.workspace)
    tree_path = args.tree.resolve()
    subject_id = _resolve_subject(workspace, tree_path, args.subject)
    grammar_name = workspace.subject_profiles[subject_id].tree_grammar
    if grammar_name is None:
        raise ContractError(
            "tree grammar is not configured",
            f"subjects.{subject_id}.tree_grammar",
        )
    grammar = select_tree_grammar(grammar_name)
    source_root = args.root or workspace.root
    return workspace, tree_path, subject_id, grammar, source_root


def _load_tree_points(path: Path) -> list:
    return load_knowledge_points(path)


def _check_source_hash(
    point, source: dict, resolved: Path, text_cache: dict[str, str],
    hash_cache: dict[str, str], failures: list[str]
) -> str | None:
    if not resolved.is_file():
        failures.append(
            f"{point.knowledge_point_id}: source file missing: {source['path']}"
        )
        return None
    key = resolved.as_posix()
    if key not in hash_cache:
        hash_cache[key] = hashlib.sha256(resolved.read_bytes()).hexdigest()
        text_cache[key] = norm(source_text(resolved))
    if hash_cache[key] != source["sha256"]:
        failures.append(
            f"{point.knowledge_point_id}: sha256 mismatch for {source['path']} "
            f"(tree={source['sha256'][:16]} disk={hash_cache[key][:16]})"
        )
    return key


def _check_quote_ref(
    point, source: dict, key: str, text_cache: dict[str, str],
    unresolved: list[tuple[str, str, str]], failures: list[str]
) -> None:
    quote = source["locator"].get("quote_ref")
    if not quote:
        failures.append(f"{point.knowledge_point_id}: locator has no quote_ref")
        return
    if norm(quote) not in text_cache[key]:
        unresolved.append((point.knowledge_point_id, source["path"], quote))


def _check_sources(points: list, source_root: Path):
    failures: list[str] = []
    text_cache: dict[str, str] = {}
    hash_cache: dict[str, str] = {}
    source_roster: set[str] = set()
    unresolved: list[tuple[str, str, str]] = []
    for point in points:
        for source in point.sources:
            path = Path(source["path"])
            source_roster.add(path.as_posix())
            resolved = path if path.is_absolute() else source_root / path
            key = _check_source_hash(
                point, source, resolved, text_cache, hash_cache, failures
            )
            if key is None:
                continue
            _check_quote_ref(point, source, key, text_cache, unresolved, failures)
    return failures, hash_cache, source_roster, unresolved


def _print_source_summary(source_roster: set[str], hash_cache: dict[str, str]) -> None:
    print(f"sources         : {len(source_roster)} distinct files, "
          f"{len(hash_cache)} hashed")


def _print_failures(failures: list[str]) -> None:
    print("\nFAILURES:")
    for failure in failures[:20]:
        print("  -", failure)


def _report_source_failures(failures: list[str]) -> int:
    if not failures:
        return 0
    _print_failures(failures)
    return 1


def _report_quote_refs(unresolved: list[tuple[str, str, str]]) -> int:
    if unresolved:
        print(f"quote_ref       : FAIL ({len(unresolved)} unresolved)")
        for pid, path, quote in unresolved[:10]:
            print(f"  - {pid}: {quote!r} not found in {path}")
        return 1
    print("quote_ref       : OK (every quote_ref locates in its declared source)")
    return 0


def _check_structure(points: list, subject_id: str, grammar):
    failures: list[str] = []
    ids = [point.knowledge_point_id for point in points]
    dupes = [pid for pid, count in Counter(ids).items() if count > 1]
    if dupes:
        failures.append(f"duplicate knowledge_point_id: {dupes[:5]}")
    try:
        check_namespace(points, subject_id)
        check_syntax(points, grammar)
        tree_shape = subject_id
        print(f"tree shape      : {tree_shape}")
    except TreeShapeError as exc:
        tree_shape = None
        failures.append(f"tree shape: {exc}")
        print("tree shape      : INVALID")
    if tree_shape is not None:
        failures.extend(chapter_scope_failures(points, grammar))
        for point in points:
            if "." not in point.knowledge_point_id:
                failures.append(f"{point.knowledge_point_id}: id must be <subject>.<...>")
        failures.extend(grammar.structural_failures(points))
    return failures


def _check_provenance(
    points: list, failures: list[str], notes: list[str]
) -> None:
    for point in points:
        if point.evidence:
            failures.append(
                f"{point.knowledge_point_id}: extracted node must not carry evidence"
            )
        if point.status != "extracted":
            notes.append(f"{point.knowledge_point_id}: status={point.status} (expected extracted)")


def _check_required_scopes(args: argparse.Namespace, points: list, failures: list[str]):
    scopes = Counter(point.scope for point in points)
    print(f"structure       : {dict(scopes)}")
    if args.require_scopes:
        required = [scope.strip() for scope in args.require_scopes.split(",") if scope.strip()]
        for scope in required:
            if scopes.get(scope, 0) == 0:
                failures.append(f"required scope {scope!r} not present in the tree")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        workspace, tree_path, subject_id, grammar, source_root = _load_tree_context(args)
    except (ContractError, TreeShapeError) as exc:
        print(f"CONTRACT FAILURE: {exc}")
        return 2

    failures: list[str] = []
    notes: list[str] = []
    try:
        points = _load_tree_points(args.tree)
    except KnowledgePointError as exc:
        print(f"CONTRACT FAILURE: {exc}")
        return 2
    print(f"contract        : OK ({len(points)} nodes validated by ky.knowledge.knowledge_point)")
    if not points:
        print("CONTRACT FAILURE: empty tree")
        return 2

    failures, hash_cache, source_roster, unresolved = _check_sources(points, source_root)
    _print_source_summary(source_roster, hash_cache)
    source_result = _report_source_failures(failures)
    if source_result:
        return source_result
    print("hashes          : OK (every sources[i].sha256 matches the bytes on disk)")
    quote_result = _report_quote_refs(unresolved)
    if quote_result:
        return quote_result

    failures.extend(_check_structure(points, subject_id, grammar))
    _check_provenance(points, failures, notes)
    _check_required_scopes(args, points, failures)
    if failures:
        _print_failures(failures)
        return 1
    for note in notes:
        print(f"note            : {note}")
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
