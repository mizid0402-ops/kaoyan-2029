"""Mutation test for tools/verify_tree.py — prove the verifier can actually fail.

A green verifier proves nothing until it has been shown to go red on a broken tree.
Each case mutates a copy of a tree (and, where needed, a copy of a source file),
runs the verifier, and asserts the expected failure prefix appears. Sources are
restored/never touched in place; every mutation happens inside a temporary copy of
the whole project data slice, and original file hashes are printed before and after
to prove nothing in the real tree changed.

Usage:  py -3.12 tools/mutation_test_verify_tree.py
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


CASES = [
    # (name, expected substring in verifier output, mutator)
    ("tamper-sha256", "sha256", lambda t, s: t.replace(
        "sha256: 199b8f9de93207cf3147dc12583026b027c1db9033b5e28ca58ece12f4d1841a",
        "sha256: " + "a" * 64, 1)),
    ("delete-quote_ref", "not found", lambda t, s: t.replace("      quote_ref: 一、函数、极限、连续",
                                                             "      quote_ref: 一、函数极限连续不存在", 1)),
    ("drop-a-chapter", "no ancestor", lambda t, s: re.sub(
        r"- schema_version: 1\n  knowledge_point_id: math1\.hs\.ch05\.chapter\n(?:.*?\n)*?  revision: 1\n",
        "", t, count=1)),
    ("scope-not-in-enum", "scope must be one of", lambda t, s: t.replace("  scope: section", "  scope: banana", 1)),
    ("duplicate-id", "duplicate knowledge_point_id", lambda t, s: t.replace(
        "  knowledge_point_id: math1.la.ch09.chapter", "  knowledge_point_id: math1.hs.ch01.chapter", 1)),
    # mutate the SOURCE bytes: the stored sha256 no longer matches the file
    ("break-source-file", "sha256 mismatch", None),
]


def run_case(name: str, expect: str, mutate, tmp: Path) -> tuple[bool, str]:
    work = tmp / name
    (work / "data" / "structured_materials" / "math1").mkdir(parents=True)
    (work / "data" / "raw_materials").mkdir(parents=True)
    shutil.copytree(ROOT / "data" / "raw_materials", work / "data" / "raw_materials",
                    dirs_exist_ok=True)
    original = (ROOT / "data" / "structured_materials" / "math1" / "knowledge_tree.yaml").read_text(
        encoding="utf-8")
    mutated = mutate(original, work) if mutate else original
    if mutated == original and name != "break-source-file":
        return False, "MUTATION WAS A NO-OP (test would have been vacuous)"
    if name == "break-source-file":
        victim = work / "data" / "raw_materials" / "transcripts" / "eol_cn" / "math_outline_2022_fulltext.html"
        text = victim.read_text(encoding="utf-8")
        # change visible content (not a comment): the recorded sha256 must stop matching
        victim.write_text(text.replace("函数的概念及表示法", "函数的概念及其表示法", 1), encoding="utf-8")
    target = work / "data" / "structured_materials" / "math1" / "knowledge_tree.yaml"
    target.write_text(mutated, encoding="utf-8")

    proc = subprocess.run(
        [PY, str(ROOT / "tools" / "verify_tree.py"), str(target), "--root", str(work),
         "--subject", "math1"],  # the mutated copy is an unregistered candidate (WP-H2)
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    hit = expect in out
    return (proc.returncode != 0 and hit), (out.strip().splitlines()[-1] if out.strip() else "(no output)")


def main() -> int:
    tree_path = ROOT / "data" / "structured_materials" / "math1" / "knowledge_tree.yaml"
    src = ROOT / "data" / "raw_materials" / "transcripts" / "eol_cn" / "math_outline_2022_fulltext.html"
    before = (sha(tree_path), sha(src))

    failures = []
    with tempfile.TemporaryDirectory(prefix="verify-tree-mut-") as td:
        tmp = Path(td)
        for name, expect, mutate in CASES:
            ok, last = run_case(name, expect, mutate, tmp)
            print(f"{'RED as expected' if ok else 'NOT DETECTED  '}  {name:<20} expect={expect:<11} {last}")
            if not ok:
                failures.append(name)

    after = (sha(tree_path), sha(src))
    print(f"\nreal tree sha256  before={before[0][:16]} after={after[0][:16]} "
          f"{'UNCHANGED' if before[0] == after[0] else '*** CHANGED ***'}")
    print(f"real source sha256 before={before[1][:16]} after={after[1][:16]} "
          f"{'UNCHANGED' if before[1] == after[1] else '*** CHANGED ***'}")

    if failures or before != after:
        print(f"\nFAILED: {failures or 'real files were modified'}")
        return 1
    print("\nall mutations detected; no real file was modified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
