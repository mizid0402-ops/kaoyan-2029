"""Write the confidence-weighted knowledge-point distribution back into the exam indexes.

Source of truth: data/review_weights/topic_weights.json's `per_question`, produced by
three independent model coders whose per-node confidence was averaged and rounded to 3
decimal places (see that file's `meta`). This script only *transcribes* that distribution
into data/exam_questions/{subj}_index_{year}.json -- it never recomputes or rebalances a
weight itself. If the source says a distribution sums to 0.998, the index says 0.998.

For each entry this sets:
  * knowledge_point_weights = the distribution, verbatim, in its original key order
  * knowledge_point_id      = the argmax of that distribution (ties broken by first
                               occurrence in the source's own key order -- the same rule
                               `max(dict, key=...)` uses, and the same rule
                               tools/verify_408_index.py's argmax check uses, so the two
                               never disagree)
  * knowledge_point_status  = assigned_multi_model if the distribution has exactly one node
                               (all three coders converged on it independently -- "reviewed"
                               by a human is a different, stronger claim this script cannot
                               make, so it never writes assigned_reviewed), else
                               assigned_unreviewed

A question missing from `per_question` is left completely untouched (still null /
not_assigned) and reported separately -- this script does not guess a mapping for it.

A distribution whose weights don't sum to 1.0 within tools.verify_408_index's own
WEIGHT_SUM_TOLERANCE is refused for that entry (not silently renormalised) and reported;
every other entry in the same file still gets written.

Usage:
  py -3.12 tools/apply_knowledge_weights.py --check     # dry run, no files written
  py -3.12 tools/apply_knowledge_weights.py              # writes, then prints a summary
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from verify_408_index import WEIGHT_SUM_TOLERANCE  # noqa: E402
from ky.workspace import load_workspace  # noqa: E402

TOPIC_WEIGHTS = ROOT / "data" / "review_weights" / "topic_weights.json"

NATIONAL_QUESTION_KEY = re.compile(r"^([a-z][a-z0-9]*)-(\d{4})-(\d+)$")
PAPER_QUESTION_KEY = re.compile(
    r"^([a-z][a-z0-9]*)-([a-z][a-z0-9]*)-(\d{4})-(\d+)$"
)


def load_distributions() -> dict[tuple[str, str, str, int], dict[str, float]]:
    """Key by (subject, year, source, number), independent of question-ID padding."""
    raw = json.loads(TOPIC_WEIGHTS.read_text(encoding="utf-8"))
    out: dict[tuple[str, str, str, int], dict[str, float]] = {}
    for key, value in raw["per_question"].items():
        match = PAPER_QUESTION_KEY.fullmatch(key)
        if match:
            subject, paper_source, year, number = match.groups()
        else:
            match = NATIONAL_QUESTION_KEY.fullmatch(key)
            if not match:
                raise ValueError(f"unparseable per_question key: {key!r}")
            subject, year, number = match.groups()
            paper_source = "national"
        out[(subject, year, paper_source, int(number))] = value["distribution"]
    return out


def argmax(distribution: dict[str, float]) -> str:
    """First key achieving the maximum weight, in the distribution's own key order.

    95/432 real distributions have an exact tie for the top weight, so the tie-break rule
    is not a corner case here -- it has to match tools/verify_408_index.py's own
    `max(kpw, key=lambda k: kpw[k])` exactly, or the two would disagree on which entries
    are valid. Both use the same idiom over the same (insertion-ordered) dict, so they do.
    """
    return max(distribution, key=distribution.get)


def _distribution_rejection(distribution: dict[str, float]) -> str | None:
    if not distribution:
        return "empty distribution"
    bad_weights = [
        node
        for node, weight in distribution.items()
        if isinstance(weight, bool)
        or not isinstance(weight, (int, float))
        or weight <= 0
    ]
    if bad_weights:
        return f"non-positive weight(s) {bad_weights}"
    total = sum(distribution.values())
    if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
        return f"weights sum to {total:.6f}, not 1.0"
    return None


def _registered_indexes() -> list[Path]:
    workspace = load_workspace(ROOT / "kaoyan.workspace.yaml")
    paths = [
        path
        for subject in workspace.exam_indexes
        for path in workspace.require_all(f"reference.exam_indexes.{subject}")
    ]
    return sorted(paths)


def apply_to_index(
    path: Path,
    distributions: dict[tuple[str, str, str, int], dict[str, float]],
) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    subject = data["subject_id"]
    year = str(data["exam_year"])
    paper_source = data.get("paper_source", "national")

    written = 0
    unchanged = 0
    missing: list[str] = []
    rejected: list[tuple[str, str]] = []
    single = 0
    spread = 0

    for entry in data["entries"]:
        key = (subject, year, paper_source, entry["number"])
        distribution = distributions.get(key)
        if distribution is None:
            missing.append(entry["question_id"])
            continue

        rejection = _distribution_rejection(distribution)
        if rejection is not None:
            rejected.append((entry["question_id"], rejection))
            continue

        primary = argmax(distribution)
        status = "assigned_multi_model" if len(distribution) == 1 else "assigned_unreviewed"

        before = (
            entry.get("knowledge_point_id"),
            entry.get("knowledge_point_weights"),
            entry.get("knowledge_point_status"),
        )
        after = (primary, dict(distribution), status)
        if before == after:
            unchanged += 1
        else:
            written += 1
        entry["knowledge_point_id"] = primary
        entry["knowledge_point_weights"] = dict(distribution)
        entry["knowledge_point_status"] = status
        if len(distribution) == 1:
            single += 1
        else:
            spread += 1

    return {
        "data": data,
        "written": written,
        "unchanged": unchanged,
        "missing": missing,
        "rejected": rejected,
        "single": single,
        "spread": spread,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="dry run: report only, write nothing")
    args = ap.parse_args()

    distributions = load_distributions()
    targets = _registered_indexes()
    if not targets:
        print("no registered exam indexes", file=sys.stderr)
        return 2

    totals = {"written": 0, "unchanged": 0, "missing": 0, "rejected": 0, "single": 0, "spread": 0}
    any_rejected = False

    for path in targets:
        result = apply_to_index(path, distributions)
        totals["written"] += result["written"]
        totals["unchanged"] += result["unchanged"]
        totals["missing"] += len(result["missing"])
        totals["rejected"] += len(result["rejected"])
        totals["single"] += result["single"]
        totals["spread"] += result["spread"]

        print(
            f"{path.name}: write={result['written']} unchanged={result['unchanged']} "
            f"missing={len(result['missing'])} rejected={len(result['rejected'])} "
            f"single_node={result['single']} spread={result['spread']}"
        )
        for qid in result["missing"]:
            print(f"   - missing from topic_weights.json: {qid}")
        for qid, reason in result["rejected"]:
            print(f"   - REJECTED {qid}: {reason}")
            any_rejected = True

        if not args.check:
            path.write_text(
                json.dumps(result["data"], ensure_ascii=False, indent=2),
                encoding="utf-8",
                newline="\n",
            )

    print(
        f"\nTOTAL {'(dry run, nothing written) ' if args.check else ''}"
        f"write={totals['written']} unchanged={totals['unchanged']} "
        f"missing={totals['missing']} rejected={totals['rejected']} "
        f"single_node={totals['single']} spread={totals['spread']}"
    )
    return 1 if any_rejected else 0


if __name__ == "__main__":
    sys.exit(main())
