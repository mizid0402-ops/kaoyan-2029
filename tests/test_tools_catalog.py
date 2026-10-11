from __future__ import annotations

import re
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tools" / "README.md"
CATALOG_START = "## Script catalog"
CATALOG_END = "## Reconstruction dependency graph"
SCRIPT_ROW = re.compile(r"^\| `(tools/(?:migrations/|archive/)?[^`]+\.py)` \|", re.MULTILINE)


class ToolsCatalogTests(unittest.TestCase):
    def test_catalog_matches_tracked_tool_directories(self) -> None:
        document = CATALOG.read_text(encoding="utf-8")
        start = document.index(CATALOG_START)
        end = document.index(CATALOG_END, start)
        catalog_section = document[start:end]
        listed = SCRIPT_ROW.findall(catalog_section)

        self.assertEqual(len(listed), len(set(listed)), "catalog contains duplicate script rows")
        listed_paths = {ROOT / path.replace("/", "\\") for path in listed}
        disk_paths = {
            path
            for directory in (
                ROOT / "tools",
                ROOT / "tools" / "migrations",
                ROOT / "tools" / "archive",
            )
            for path in directory.glob("*.py")
        }

        self.assertEqual(
            listed_paths,
            disk_paths,
            "tools catalog and direct Python files differ; check missing or stale rows",
        )

    def test_moved_archive_modules_load_in_fresh_process(self) -> None:
        scripts = (
            "round24_build_weighted_tree.py",
            "round29_build_tree_split.py",
            "round22_verify.py",
        )
        loader = (
            "import runpy, sys\n"
            "from pathlib import Path\n"
            "loaded = runpy.run_path(sys.argv[1], run_name='review_load')\n"
            "root = Path(sys.argv[2]).resolve()\n"
            "if 'ROOT' in loaded:\n"
            "    assert Path(loaded['ROOT']).resolve() == root\n"
        )
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        for name in scripts:
            script = ROOT / "tools" / "archive" / name
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, "-B", "-c", loader, str(script), str(ROOT)],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
