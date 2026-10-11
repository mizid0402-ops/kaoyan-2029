"""M29 write isolation for ``contracts/timetable_import.md`` §1.

Public interfaces: :class:`Isolation`, :func:`inspect_isolation`, and
:func:`check_isolated_path`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ky.models import ContractError


@dataclass(frozen=True)
class Isolation:
    state: str
    workspace_root: Path
    worktree_root: Path | None


def _has_git_marker(root: Path) -> bool:
    current = root
    while True:
        marker = current / ".git"
        if marker.exists():
            return True
        if current.parent == current:
            return False
        current = current.parent


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=False,
    )


def _confirmed_worktree(root: Path) -> Path | None:
    inside = _run_git(root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != b"true":
        return None
    top = _run_git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or not top.stdout.strip():
        return None
    try:
        worktree = Path(top.stdout.decode("utf-8").strip()).resolve(strict=True)
    except (OSError, UnicodeError):
        return None
    return worktree if worktree.is_dir() else None


def inspect_isolation(workspace_root: str | Path) -> Isolation:
    root = Path(workspace_root).resolve(strict=True)
    if not _has_git_marker(root):
        return Isolation("B", root, None)
    try:
        worktree = _confirmed_worktree(root)
    except OSError:
        worktree = None
    if worktree is None:
        return Isolation("C", root, None)
    return Isolation("A", root, worktree)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _query_path_git(isolation: Isolation, target: Path, *args: str) -> int:
    assert isolation.worktree_root is not None
    result = _run_git(
        isolation.worktree_root,
        *args,
        "--",
        str(target),
    )
    return result.returncode


def check_isolated_path(isolation: Isolation, target: str | Path) -> Path:
    path = Path(target).resolve(strict=False)
    if isolation.state == "B":
        return path
    if isolation.state != "A" or isolation.worktree_root is None:
        raise ContractError("无法确认个人数据不会进仓库", path.as_posix())
    root = isolation.worktree_root.resolve(strict=True)
    if not _inside(path, root):
        return path
    try:
        ignored = _query_path_git(isolation, path, "check-ignore", "-q")
        tracked = _query_path_git(
            isolation, path, "ls-files", "--error-unmatch"
        )
    except OSError as exc:
        raise ContractError("无法确认个人数据不会进仓库", path.as_posix()) from exc
    if ignored != 0 or tracked != 1:
        raise ContractError("无法确认个人数据不会进仓库", path.as_posix())
    return path
