"""M1 CLI for contracts/material_restore.md; restore missing ledger bytes only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ky.acquisition.ledger_restore import restore_materials
from ky.ledger.material import LEDGER_SUBJECT_CATEGORIES, LedgerError, load_ledger
from ky.models import ContractError
from ky.workspace import load_workspace


_GOOD = {"already_verified", "restored", "reference_only"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, help="workspace registry; otherwise discover it")
    parser.add_argument("--check", action="store_true", help="inspect without downloading")
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    args = parser.parse_args(argv)
    try:
        workspace = load_workspace(args.workspace)
        ledger_path = workspace.require("reference.ledger")
        allowed_subjects = set(workspace.subjects) | LEDGER_SUBJECT_CATEGORIES
        materials = load_ledger(ledger_path, subject_ids=allowed_subjects)
    except (ContractError, LedgerError) as exc:
        print(f"material restore violation: {exc}", file=sys.stderr)
        return 2

    results = restore_materials(
        materials, root=workspace.root, raw_root=workspace.raw_root, check_only=args.check,
    )
    if args.json:
        rows = [result.__dict__ for result in results]
        print(json.dumps(rows, ensure_ascii=False, sort_keys=True))
    else:
        for result in results:
            detail = f" ({result.detail})" if result.detail else ""
            print(f"{result.resource_id}: {result.status}{detail}")
    failed = any(result.status not in _GOOD for result in results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
