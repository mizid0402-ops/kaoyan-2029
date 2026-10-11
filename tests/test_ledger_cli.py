"""`ky ledger` data-source modes (gpt-6-sol round 52, M1 / M2 on WP-H2).

Standalone mode needs no registry when every source is explicit; registry mode resolves the
ledger through ``require`` and embedded paths against the workspace root.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER = REPO_ROOT / "data" / "materials.yaml"
REGISTRY = REPO_ROOT / "kaoyan.workspace.yaml"


def run_ledger(*args: str, cwd: Path, env: dict[str, str] | None = None
               ) -> subprocess.CompletedProcess:
    overrides = env or {}
    env = dict(os.environ)
    env.pop("KY_WORKSPACE", None)
    env.update(overrides)
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "ky", "ledger", *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=env,
    )


def test_subjects() -> str:
    """The subjects the real ledger uses, read from it so the test follows the data (D5/D6)."""
    import yaml

    from ky.ledger.material import LEDGER_SUBJECT_CATEGORIES

    document = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    used = {subject for item in document["items"] for subject in item["subjects"]}
    return ",".join(sorted(used - LEDGER_SUBJECT_CATEGORIES))


class LedgerCliSourcesTest(unittest.TestCase):
    def test_standalone_mode_runs_without_any_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_ledger(
                "--ledger", str(LEDGER), "--root", str(REPO_ROOT),
                "--subjects", test_subjects(), "--json",
                cwd=Path(tmp),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["root"], REPO_ROOT.as_posix())

    def test_legacy_paths_discover_subjects_from_ledger_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_ledger("--ledger", str(LEDGER), "--root", str(REPO_ROOT),
                                "--json", cwd=Path(tmp))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_paths_without_a_registry_require_subjects_or_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "materials.yaml"
            ledger.write_text("materials: []\n", encoding="utf-8")
            result = run_ledger("--ledger", str(ledger), "--root", str(root), cwd=root)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("add --subjects or --workspace", result.stderr)

    def test_broken_env_registry_keeps_its_source_in_the_error(self) -> None:
        # sol round 60, L1 suggestion: the fallback message used to hide why discovery failed.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "materials.yaml"
            ledger.write_text("materials: []\n", encoding="utf-8")
            env_registry = root / "missing.yaml"
            result = run_ledger("--ledger", str(ledger), "--root", str(root), cwd=root,
                                env={"KY_WORKSPACE": str(env_registry)})
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("KY_WORKSPACE", result.stderr)
        self.assertIn("missing.yaml", result.stderr)

    def test_a_non_utf8_ledger_exits_two_without_a_traceback(self) -> None:
        # WP-R3 (round 152 S1): a ledger re-saved as GBK used to end in UnicodeDecodeError.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "materials.yaml"
            ledger.write_bytes("items: []  # 资料台账\n".encode("gbk"))
            result = run_ledger("--ledger", str(ledger), "--root", str(root),
                                "--subjects", test_subjects(), cwd=root)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith("ledger violation: "), result.stderr)
        self.assertIn(ledger.as_posix(), result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_registry_mode_resolves_embedded_paths_against_the_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            elsewhere = Path(tmp) / "elsewhere" / "nested"
            elsewhere.mkdir(parents=True)
            ledger_copy = elsewhere / "materials.yaml"
            shutil.copyfile(LEDGER, ledger_copy)
            result = run_ledger(
                "--workspace", str(REGISTRY), "--ledger", str(ledger_copy), "--json",
                cwd=Path(tmp),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["root"], REPO_ROOT.as_posix())

    @unittest.skipUnless(os.name == "nt", "directory junctions are a Windows feature")
    def test_registered_ledger_escaping_the_workspace_is_a_violation(self) -> None:
        import _winapi

        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside"
            outside.mkdir()
            shutil.copyfile(LEDGER, outside / "materials.yaml")
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            registry = REGISTRY.read_text(encoding="utf-8")
            (workspace / "kaoyan.workspace.yaml").write_text(registry, encoding="utf-8")
            _winapi.CreateJunction(str(outside), str(workspace / "data"))
            result = run_ledger("--workspace", str(workspace / "kaoyan.workspace.yaml"),
                                cwd=Path(tmp))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("outside the workspace", result.stderr)


if __name__ == "__main__":
    unittest.main()
