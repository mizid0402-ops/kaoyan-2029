"""Build or query the read-only projection with ``py -3.12 -m ky.projection``."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from ky.knowledge import KnowledgePointError
from ky.models import ContractError, load_config
from ky.projection import build_projection
from ky.projection.status import status_as_of, status_to_mapping
from ky.workspace import load_workspace


def _status_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="py -3.12 -m ky.projection status")
    parser.add_argument("--date", required=True, help="date evaluated against the latest rebuild")
    parser.add_argument("--config", help="exam configuration (overrides workspace setting)")
    parser.add_argument("--workspace", help="workspace registry (otherwise discovered)")
    parser.add_argument("--json", action="store_true", help="emit the status JSON shape")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    try:
        day = date.fromisoformat(args.date)
        if day.isoformat() != args.date:
            raise ValueError("not a strict ISO date")
    except ValueError:
        print("--date must be a valid ISO date (YYYY-MM-DD)", file=sys.stderr)
        return 3
    try:
        workspace = load_workspace(args.workspace)
        config_path = Path(args.config) if args.config else workspace.exam_config
        if config_path is None:
            raise ContractError(
                "provide --config PATH or register settings.exam_config in the workspace",
                "settings.exam_config",
            )
        config = load_config(config_path)
        status = status_as_of(workspace.projection, day, config)
    except (ContractError, KnowledgePointError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    mapping = status_to_mapping(status)
    if args.json:
        print(json.dumps(mapping, ensure_ascii=False, indent=2))
    else:
        print(f"Projection snapshot for {day.isoformat()} from the latest successful rebuild")
        for subject in status.subjects:
            print(
                f"{subject.subject_id}: queue={subject.counts.in_review_queue}, "
                f"due={subject.counts.due_today_count} "
                f"({subject.counts.due_today_minutes} min), "
                f"backlog={subject.counts.backlog_minutes} min"
            )
        print(f"frozen: {status.freeze.frozen}")
    return 0


def main(argv: list[str] | None = None) -> int:
    candidate_args = sys.argv[1:] if argv is None else argv
    if candidate_args and candidate_args[0] == "status":
        return _status_main(candidate_args[1:])
    ap = argparse.ArgumentParser(
        prog="py -m ky.projection",
        description="Rebuild the read-only SQLite projection from the structured materials. "
                    "Writes only the projection file; never touches the trees, indexes or the "
                    "vocabulary database.",
    )
    ap.add_argument(
        "--workspace", help="workspace registry (otherwise KY_WORKSPACE or upward discovery)"
    )
    ap.add_argument(
        "--out", help="where to write the projection (default: workspace projection path)"
    )
    ap.add_argument("--json", action="store_true", help="emit the summary as JSON")
    args = ap.parse_args(argv)

    try:
        workspace = load_workspace(args.workspace)
        summary = build_projection(workspace, Path(args.out) if args.out else None)
    except (ContractError, KnowledgePointError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        return 2
    if args.json:
        import json
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("projection rebuilt")
        for k, v in summary.items():
            print(f"  {k:28} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
