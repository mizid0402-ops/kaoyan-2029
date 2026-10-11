"""Mutation-test tools/verify_408_index.py — prove the contract check really rejects things.

Eight mutations, each one a mistake that would matter if it slipped through:

  1. question text smuggled into `notes`
  2. question text smuggled as a brand-new top-level field
  3. a made-up answer letter (E)
  4. `knowledge_point_id` filled in while still uncalibrated
  5. `answer_confidence` upgraded to `official` without the official book
  6. `marks_total` no longer equal to the sum of entries
  7. a locator hash that disagrees with the provenance hash
  8. a mangled sha256 in provenance

Every mutation is applied to a temp copy; the real index is never written. Its sha256 is
printed before and after to prove that.

Usage:  py -3.12 tools/mutation_test_408_index.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
INDEX = ROOT / "data" / "exam_questions" / "408_index_2024.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


MUTATIONS = [
    ("question-text-in-notes", lambda d: d["entries"][0].__setitem__(
        "notes", "已知带头结点的非空单链表的头指针为 h，结点结构为 data next"), "notes: must be null"),
    ("question-text-as-new-field", lambda d: d.__setitem__(
        "stem_preview", "二叉树的中序遍历序列为 p, v, q，则下列叙述中正确的是"), "unexpected key"),
    # Expect text below matches the verifier's actual message, not the old ~2024 wording --
    # confirmed by running this mutation directly against the current verify_408_index.py.
    ("invalid-answer-letter", lambda d: d["entries"][0].__setitem__("answer", "E"),
     "choice answers must be A-D"),
    # Round 15 gave entries[0] a real knowledge_point_weights distribution (see
    # tools/apply_knowledge_weights.py), so setting only knowledge_point_id no longer
    # reproduces "bare id, no evidence" -- knowledge_point_weights would still be present
    # and back it. The mutation now clears both, which is what "no evidence" actually means.
    ("kp-set-while-uncalibrated", lambda d: (
        d["entries"][0].__setitem__("knowledge_point_weights", None),
        d["entries"][0].__setitem__("knowledge_point_id", "cs408.ds.chapter-02.section-02"),
    ), "before calibration"),
    ("official-claim-without-book", lambda d: d["entries"][0].__setitem__(
        "answer_confidence", "official"), "claims official answer"),
    ("marks-total-mismatch", lambda d: d.__setitem__("marks_total", 149), "!= sum"),
    ("locator-hash-disagrees", lambda d: d["entries"][0]["locator"].__setitem__(
        "paper_sha256", "0" * 64), "locator hash != provenance hash"),
    ("mangled-provenance-hash", lambda d: d["provenance"]["paper"].__setitem__(
        "sha256", "not-a-digest"), "not a 64-char lowercase hex digest"),
]


def main() -> int:
    original = INDEX.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    base = json.loads(original.decode("utf-8"))

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="idx-mut-") as tmp:
        for name, mutate, expect in MUTATIONS:
            data = json.loads(json.dumps(base))  # deep copy
            mutate(data)
            target = Path(tmp) / f"{name}.json"
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            proc = subprocess.run(
                [PY, str(ROOT / "tools" / "verify_408_index.py"), str(target)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            red = proc.returncode != 0
            matched = expect in out
            ok = red and matched
            print(f"{'RED as expected' if ok else 'NOT DETECTED  '}  {name:<28} {expect}")
            if not ok:
                failures.append(name)
                print(f"      output tail: {out.strip().splitlines()[-1] if out.strip() else '(none)'}")

    after = sha(INDEX)
    print(f"\nreal index sha256 before={before[:16]} after={after[:16]} "
          f"{'UNCHANGED' if before == after else '*** CHANGED ***'}")
    if failures or before != after:
        print(f"FAILED: {failures or 'real index modified'}")
        return 1
    print("all 8 mutations rejected; real index untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
