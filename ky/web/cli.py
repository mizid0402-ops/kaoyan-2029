"""M16 server command-line adapter; see ``contracts/web.md``."""

from __future__ import annotations

import argparse
import sys
import webbrowser

from ky.models import ContractError
from ky.web.server import make_server
from ky.workspace import load_workspace


def web_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="py -3.12 -m ky web")
    parser.add_argument("--port", type=int, default=8730)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--workspace")
    try:
        args = parser.parse_args(argv)
        if not 0 <= args.port <= 65535:
            raise ContractError("port must be from 0 to 65535", "--port")
        workspace = load_workspace(args.workspace)
        server = make_server(workspace, args.port)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    except (ContractError, OSError) as exc:
        print(f"contract violation: {exc}", file=sys.stderr)
        error_code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
        if isinstance(exc, OSError) and error_code in {48, 98, 10013, 10048}:
            print("端口被占用，请使用 --port 更换端口", file=sys.stderr)
        return 2
    url = f"http://127.0.0.1:{server.server_port}/"
    print(url, flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
