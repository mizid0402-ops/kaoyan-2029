"""Prove tests/test_tree_integrity.py can actually fail — one mutation per family.

Method: back up the real file bytes, mutate in place, run the one test that should
catch it, restore, and verify the sha256 is byte-identical to before. If a mutation
does not turn its test red, the test is decorative and that is reported as a failure.

Usage:  py -3.12 tools/mutation_test_suite.py
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
MATH_TREE = ROOT / "data" / "structured_materials" / "math1" / "knowledge_tree.yaml"
LEDGER = ROOT / "data" / "materials.yaml"

SOURCE_SHA = "199b8f9de93207cf3147dc12583026b027c1db9033b5e28ca58ece12f4d1841a"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_test(name: str) -> tuple[int, str]:
    proc = subprocess.run(
        [PY, "-m", "unittest", f"tests.test_tree_integrity.{name}", "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or ""))


CASES = [
    (
        "TreeIntegrityTest.test_recorded_sha256_matches_the_source_bytes",
        MATH_TREE,
        lambda t: t.replace(
            "path: data/raw_materials/transcripts/eol_cn/math_outline_2022_fulltext.html",
            "path: data/raw_materials/transcripts/eol_cn/does_not_exist.html", 1),
        "declared source path no longer exists on disk",
    ),
    (
        "TreeIntegrityTest.test_every_quote_ref_locates_in_its_declared_source",
        MATH_TREE,
        lambda t: t.replace("quote_ref: 一、函数、极限、连续", "quote_ref: 一、不存在的章节名", 1),
        "quote_ref no longer locates",
    ),
    (
        "TreeIntegrityTest.test_ai_built_trees_stay_at_extracted",
        MATH_TREE,
        lambda t: t.replace("  status: extracted", "  status: reviewed", 1),
        "node promoted past the human-only gate",
    ),
    (
        "TreeIntegrityTest.test_math1_shape_is_locked",
        MATH_TREE,
        lambda t: t.replace("knowledge_point_id: math1.hs.ch01.chapter",
                            "knowledge_point_id: math1.hs.ch01.chapte", 1),
        "chapter id malformed -> structure assertion must fail",
    ),
    (
        "LedgerTierRegressionTest.test_bookseller_pages_may_not_define_syllabus",
        LEDGER,
        lambda t: t.replace("source_tier: trusted_reprint", "source_tier: official_publisher", 1),
        "bookseller page regains a syllabus-authoritative tier",
    ),
    (
        "LedgerTierRegressionTest.test_syllabus_authoritative_rows_are_official_only",
        LEDGER,
        lambda t: t.replace("source_tier: trusted_reprint", "source_tier: university", 1),
        "new tier enters the authoritative set",
    ),
]


def main() -> int:
    failures: list[str] = []
    for test_name, path, mutate, description in CASES:
        original = path.read_bytes()
        before = hashlib.sha256(original).hexdigest()
        text = original.decode("utf-8")
        mutated = mutate(text)
        if mutated == text:
            print(f"VACUOUS   {test_name}: mutation did not change the file")
            failures.append(f"{test_name} (vacuous mutation)")
            continue
        path.write_text(mutated, encoding="utf-8")
        code, out = run_test(test_name)
        path.write_bytes(original)
        after = sha(path)
        restored = before == after
        red = code != 0
        status = "RED as expected" if (red and restored) else "NOT DETECTED"
        print(f"{status:15} {test_name.split('.')[-1][:52]:<54} {description}")
        if not (red and restored):
            failures.append(test_name)
        if not restored:
            print(f"   *** RESTORE FAILED for {path}: {before[:16]} -> {after[:16]}")

    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s) did not behave: {failures}")
        return 1
    print("all mutations turned their test red; every file restored byte-identical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
