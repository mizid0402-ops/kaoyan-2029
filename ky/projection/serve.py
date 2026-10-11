"""Serve the projection locally through Datasette in explicit immutable mode.

One-command entry point::

    py -3.12 -m ky.projection.serve
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ky.models import ContractError
from ky.workspace import load_workspace


def datasette_args(
    database: Path,
    host: str = "127.0.0.1",
    port: int = 8001,
    metadata: Path | None = None,
) -> list[str]:
    """Return the Datasette CLI arguments, with the database always immutable."""
    args = [
        "serve",
        "--immutable",
        str(database),
        "--host",
        host,
        "--port",
        str(port),
    ]
    if metadata is not None:
        args.extend(["--metadata", str(metadata)])
    return args


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="py -3.12 -m ky.projection.serve",
        description="Serve the rebuildable SQLite projection locally in immutable mode.",
    )
    parser.add_argument(
        "--workspace", help="workspace registry (otherwise KY_WORKSPACE or upward discovery)"
    )
    parser.add_argument(
        "--database", type=Path, help="projection database (default: workspace projection path)"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args(argv)

    if args.database is not None:
        database = args.database.resolve()
    else:
        try:
            database = load_workspace(args.workspace).projection.resolve()
        except ContractError as exc:
            print(f"contract violation: {exc}", file=sys.stderr)
            return 2
    if not database.is_file():
        parser.error(
            f"projection does not exist: {database}; rebuild it first with "
            "`py -3.12 -m ky.projection`"
        )

    display_host = f"[{args.host}]" if ":" in args.host else args.host
    # Flush: Datasette keeps this process running, so a redirected (block-buffered) stdout
    # would otherwise hold the address until exit (sol round 130, M2).
    print(
        f"database: {database} | serving: http://{display_host}:{args.port}/ "
        "| Ctrl+C 停止",
        flush=True,
    )

    from datasette.cli import cli

    try:
        cli.main(
            args=datasette_args(database, args.host, args.port, args.metadata),
            prog_name="datasette",
            standalone_mode=False,
        )
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
