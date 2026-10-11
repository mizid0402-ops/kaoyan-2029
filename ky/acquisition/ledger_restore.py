"""M1 ledger-driven byte restoration (contracts/material_restore.md).

Public interface: ``restore_materials`` and ``RestoreResult``. M2 owns the ledger format;
this port only retrieves missing, verifiable bytes and never changes ledger records.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import urlopen

from ky.ledger.material import Material, sha256_file


@dataclass(frozen=True)
class RestoreResult:
    resource_id: str
    status: str
    path: str | None
    detail: str = ""


def _target(root: Path, raw_root: Path, material: Material) -> Path:
    recorded = Path(material.storage.path or "")
    target = recorded if recorded.is_absolute() else root / recorded
    try:
        resolved_root = raw_root.resolve(strict=False)
        resolved_target = target.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"cannot resolve storage.path: {exc}") from exc
    if resolved_target == resolved_root or not resolved_target.is_relative_to(resolved_root):
        raise ValueError("storage.path resolves outside materials.raw_root")
    return target


def _download(
    url: str,
    staged: Path,
    expected_size: int,
    expected_hash: str,
    open_url: Callable,
) -> tuple[str, str]:
    digest = hashlib.sha256()
    size = 0
    try:
        with open_url(url, timeout=30) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                return "http_error", f"HTTP {status}"
            with staged.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > expected_size:
                        return "byte_size_mismatch", f"download exceeds {expected_size} bytes"
                    output.write(chunk)
                    digest.update(chunk)
    except HTTPError as exc:
        return "http_error", f"HTTP {exc.code}"
    except (OSError, ValueError, HTTPException) as exc:
        return "download_failed", f"{type(exc).__name__}: {exc}"
    if size != expected_size:
        return "byte_size_mismatch", f"expected {expected_size} bytes, got {size}"
    actual_hash = digest.hexdigest()
    if actual_hash != expected_hash:
        return "sha256_mismatch", f"expected {expected_hash}, got {actual_hash}"
    return "verified_download", ""


def _publish(staged: Path, target: Path, expected_hash: str) -> tuple[str, str]:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
        )
        sibling = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as output, staged.open("rb") as source:
                shutil.copyfileobj(source, output)
            # The download lives in the system temp directory, possibly on another volume.
            # A verified sibling permits an atomic, no-overwrite publication on that volume.
            if sha256_file(sibling) != expected_hash:
                return "publish_failed", "staged copy changed before publication"
            try:
                os.link(sibling, target)
            except FileExistsError:
                return "target_conflict", "target appeared before publication; no file was replaced"
        finally:
            sibling.unlink(missing_ok=True)
    except OSError as exc:
        return "publish_failed", f"{type(exc).__name__}: {exc}"
    return "restored", ""


def _restore_missing(material: Material, target: Path, open_url: Callable) -> tuple[str, str]:
    storage = material.storage
    try:
        with tempfile.TemporaryDirectory(
            prefix="kaoyan-ledger-restore-", ignore_cleanup_errors=True,
        ) as temporary:
            staged = Path(temporary) / "download"
            status, detail = _download(
                storage.url, staged, storage.byte_size, storage.sha256, open_url,
            )
            if status == "verified_download":
                return _publish(staged, target, storage.sha256)
            return status, detail
    except OSError as exc:
        return "download_failed", f"{type(exc).__name__}: {exc}"


def _restore_material(
    material: Material,
    workspace_root: Path,
    raw_directory: Path,
    check_only: bool,
    open_url: Callable,
) -> RestoreResult:
    storage = material.storage
    if storage.mode != "local_file":
        return RestoreResult(material.resource_id, "reference_only", None)
    try:
        target = _target(workspace_root, raw_directory, material)
    except ValueError as exc:
        return RestoreResult(
            material.resource_id, "invalid_path", storage.path, str(exc),
        )
    display_path = target.as_posix()
    try:
        target_exists = target.exists()
        if target_exists:
            status = (
                "already_verified" if material.verify_bytes(workspace_root)
                else "existing_mismatch"
            )
            return RestoreResult(material.resource_id, status, display_path)
    except OSError as exc:
        return RestoreResult(
            material.resource_id, "existing_unreadable", display_path,
            f"{type(exc).__name__}: {exc}",
        )
    if not material.rights.may_store:
        return RestoreResult(material.resource_id, "storage_not_permitted", display_path)
    if not storage.url:
        return RestoreResult(material.resource_id, "missing_url", display_path)
    try:
        parsed_url = urlsplit(storage.url)
        valid_url = parsed_url.scheme in {"http", "https"} and bool(parsed_url.hostname)
    except ValueError:
        valid_url = False
    if not valid_url:
        return RestoreResult(material.resource_id, "invalid_url", display_path)
    if check_only:
        return RestoreResult(material.resource_id, "needs_download", display_path)
    status, detail = _restore_missing(material, target, open_url)
    return RestoreResult(material.resource_id, status, display_path, detail)


def restore_materials(
    materials: Iterable[Material],
    *,
    root: str | Path,
    raw_root: str | Path,
    check_only: bool = False,
    open_url: Callable = urlopen,
) -> tuple[RestoreResult, ...]:
    """Inspect every ledger row and restore only missing ``local_file`` bytes.

    ``open_url`` is injectable so contract tests never contact the network.
    Existing files are never replaced, including those with a wrong hash.
    """
    workspace_root = Path(root)
    raw_directory = Path(raw_root)
    return tuple(
        _restore_material(material, workspace_root, raw_directory, check_only, open_url)
        for material in materials
    )
