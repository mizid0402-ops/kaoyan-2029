"""Mutation-test the knowledge_point_weights contract in tools/verify_408_index.py.

Round 15 added the `knowledge_point_weights` schema (weighted, multi-node knowledge-point
attribution) and touched three other things in the same file: the weight-sum tolerance,
node-id validity (now checked against the real knowledge tree, not a regex), and the
"no knowledge point before calibration" gate (now evidence-aware). Six mutations, each one
a mistake that would matter if it slipped through:

  1. knowledge_point_weights sums to something far from 1.0
  2. knowledge_point_id disagrees with the argmax of knowledge_point_weights
  3. knowledge_point_weights is set but knowledge_point_id is null
  4. a knowledge_point_weights key names a node that doesn't exist in the cs408 tree
  5. a bare (evidence-free) knowledge_point_id is set with no knowledge_point_weights,
     while calibration is still awaiting_official_book
  6. knowledge_point_status says not_assigned while a knowledge point is actually set

Every mutation is applied to a temp copy; the real index (408_index_2024.json, already
written by tools/apply_knowledge_weights.py) is never modified. Its sha256 is printed
before and after to prove that.

Usage:  py -3.12 tools/mutation_test_knowledge_weights.py
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

# entries[0] (cs408-2024-01) is a single-node distribution after the round-15 write-back:
# {"cs408.ds.chapter-02.section-02.item-02": 1.0}. A real, different node in the same tree,
# used to prove the argmax check fires on a genuine (not made-up) id.
OTHER_REAL_NODE = "cs408.ds.chapter-02.section-02.item-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mutate_sum(d: dict) -> None:
    entry = d["entries"][0]
    entry["knowledge_point_weights"] = {entry["knowledge_point_id"]: 0.5}


def mutate_argmax(d: dict) -> None:
    d["entries"][0]["knowledge_point_id"] = OTHER_REAL_NODE


def mutate_null_id(d: dict) -> None:
    d["entries"][0]["knowledge_point_id"] = None


def mutate_fake_node(d: dict) -> None:
    entry = d["entries"][0]
    entry["knowledge_point_weights"] = {"cs408.made-up.not-a-real-node": 1.0}


def mutate_bare_id_before_calibration(d: dict) -> None:
    entry = d["entries"][0]
    entry["knowledge_point_weights"] = None
    # knowledge_point_id stays set -- that's the point: an id with no evidence behind it.


def mutate_status_disagrees(d: dict) -> None:
    d["entries"][0]["knowledge_point_status"] = "not_assigned"


MUTATIONS = [
    ("weights-sum-not-1.0", mutate_sum, "weights sum to"),
    ("argmax-mismatch", mutate_argmax, "is not the argmax"),
    ("weights-present-id-null", mutate_null_id, "knowledge_point_weights present but knowledge_point_id is null"),
    ("fake-node-not-in-tree", mutate_fake_node, "not in the cs408 tree"),
    ("bare-id-before-calibration", mutate_bare_id_before_calibration, "knowledge point set before calibration"),
    ("status-disagrees-with-id", mutate_status_disagrees, "not_assigned but a knowledge point is set"),
]


def main() -> int:
    original = INDEX.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    base = json.loads(original.decode("utf-8"))

    # Sanity check the fixture this whole script leans on: entries[0] must actually carry a
    # single-node distribution, or every mutation below is testing something else by accident.
    fixture = base["entries"][0]
    if not fixture.get("knowledge_point_weights") or len(fixture["knowledge_point_weights"]) != 1:
        print("FIXTURE CHANGED: entries[0] is no longer a single-node distribution; "
              "this script's mutations need to be re-picked against the current data.")
        return 2

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="kw-mut-") as tmp:
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
            print(f"{'RED as expected' if ok else 'NOT DETECTED  '}  {name:<28} {expect!r}")
            if not ok:
                failures.append(name)
                print(f"      output tail: {out.strip().splitlines()[-1] if out.strip() else '(none)'}")

    after = sha(INDEX)
    print(f"\nreal index sha256 before={before[:16]} after={after[:16]} "
          f"{'UNCHANGED' if before == after else '*** CHANGED ***'}")
    if failures or before != after:
        print(f"FAILED: {failures or 'real index modified'}")
        return 1
    print(f"all {len(MUTATIONS)} mutations rejected; real index untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
