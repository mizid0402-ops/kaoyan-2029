"""M22 test helper for external resources.

Missing external files skip their dependent tests by default and identify the
missing path plus its recovery source. Set ``KY_REQUIRE_RESOURCES=1`` to turn
the same condition into a failure when checking a complete resource checkout.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path


def require_path(
    testcase_or_none: unittest.TestCase | None,
    path: str | Path,
    why: str,
) -> None:
    """Require a resource path or skip/fail with its location and recovery hint."""
    resource = Path(path)
    if resource.exists():
        return

    reason = f"missing resource: {resource}; {why}"
    if os.environ.get("KY_REQUIRE_RESOURCES") == "1":
        raise AssertionError(reason)
    if testcase_or_none is None:
        raise unittest.SkipTest(reason)
    testcase_or_none.skipTest(reason)
