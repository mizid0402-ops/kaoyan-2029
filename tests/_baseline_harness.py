"""Shared fixed-baseline test mechanics (AGENTS.md 12 and 12a).

This module resolves immutable commit sources, checks caller-supplied legacy identity,
loads baseline modules in isolation, and compares raw process and output-tree bytes.
It contains no port-specific fixture data.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable


@dataclass(frozen=True)
class ProcessResult:
    """Raw command outcome required for byte-for-byte baseline comparison."""

    returncode: int
    stdout: bytes
    stderr: bytes


def fixed_source(
    repository: Path,
    commit: str,
    relative_path: str,
    identity: Callable[[bytes], bool],
) -> bytes:
    """Read a source from a fixed commit and reject mutable refs or wrong identities."""
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit):
        raise ValueError("baseline must be a fixed commit hash")
    kind = subprocess.run(
        ["git", "cat-file", "-t", f"{commit}^{{commit}}"],
        cwd=repository,
        check=True,
        capture_output=True,
    ).stdout.strip()
    if kind != b"commit":
        raise ValueError("baseline hash does not resolve to a commit")
    source = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=repository,
        check=True,
        capture_output=True,
    ).stdout
    if not identity(source):
        raise AssertionError(f"baseline identity check failed: {relative_path}")
    return source


def load_isolated(source: bytes, name: str) -> ModuleType:
    """Execute source in a uniquely named module so its imports do not collide."""
    module_name = f"_baseline_{name}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    if spec is None:
        raise ImportError(f"cannot create isolated module: {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        exec(compile(source, f"<{module_name}>", "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def output_tree(root: Path) -> dict[str, bytes]:
    """Return every file under root as relative POSIX path to original bytes."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def compare_results(
    old: ProcessResult,
    new: ProcessResult,
    old_files: dict[str, bytes] | None = None,
    new_files: dict[str, bytes] | None = None,
) -> None:
    """Raise an assertion on any raw process or generated-file difference."""
    if old != new:
        raise AssertionError(f"process bytes differ: old={old!r}; new={new!r}")
    if old_files != new_files:
        raise AssertionError("written file tree bytes differ")


def compare_runs(
    old_run: Callable[[], tuple[ProcessResult, dict[str, bytes]]],
    new_run: Callable[[], tuple[ProcessResult, dict[str, bytes]]],
) -> tuple[ProcessResult, dict[str, bytes]]:
    """Run both prepared sides and compare process and generated-file bytes."""
    old_result, old_files = old_run()
    new_result, new_files = new_run()
    compare_results(old_result, new_result, old_files, new_files)
    return new_result, new_files
