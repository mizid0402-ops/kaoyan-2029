"""M13 shared atomic byte replacement for workspace artifacts.

Public interface: ``replace_bytes(path, data)``. Writing to a sibling temporary and replacing
the directory entry avoids writing through a hard link to an outside file.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable

__all__ = ["replace_bytes"]


def replace_bytes(
    path: str | Path,
    data: bytes,
    *,
    check_temporary: Callable[[Path], object] | None = None,
) -> None:
    """Atomically replace ``path`` with ``data`` using a temporary sibling file.

    The parent directory must already exist. ``os.replace`` swaps the target directory entry
    instead of opening the old inode, so other hard links keep their original bytes.
    ``check_temporary`` (optional) sees the temporary path after it is created and before any
    data is written; if it raises, the temporary is removed and nothing is replaced. M29 uses it
    so its personal-data isolation check covers this temporary too (sol round 236 R1).
    """
    target = Path(path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        if check_temporary is not None:
            try:
                check_temporary(temporary)
            except BaseException:
                os.close(descriptor)
                raise
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
