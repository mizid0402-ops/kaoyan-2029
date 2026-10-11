"""Black-box evidence that the projection service rejects HTTP writes."""

from __future__ import annotations

import json
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

from ky.projection import PROJECTION_SCHEMA_VERSION, build_projection
from ky.projection.serve import datasette_args, main as serve_main
from ky.workspace import load_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = load_workspace(REPO_ROOT / "kaoyan.workspace.yaml")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_ready(port: int, process: subprocess.Popen[str]) -> None:
    url = f"http://127.0.0.1:{port}/"
    for _ in range(100):
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(
                f"projection service exited before becoming ready\nstdout={stdout}\nstderr={stderr}"
            )
        try:
            with urllib.request.urlopen(url, timeout=0.2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.05)
    raise AssertionError("projection service did not become ready")


class ProjectionServiceTest(unittest.TestCase):
    def test_command_marks_database_immutable(self) -> None:
        args = datasette_args(Path("projection.sqlite"))
        self.assertIn("--immutable", args)
        self.assertNotIn("--create", args)

    def test_serve_prints_database_and_ipv4_address_before_starting(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            database = Path(td) / "projection.sqlite"
            database.touch()
            output = StringIO()
            with patch("datasette.cli.cli.main") as datasette_main:
                with redirect_stdout(output):
                    result = serve_main([
                        "--database", str(database), "--host", "127.0.0.1", "--port", "8123",
                    ])

            self.assertEqual(result, 0)
            self.assertEqual(
                output.getvalue(),
                f"database: {database.resolve()} | serving: http://127.0.0.1:8123/ "
                "| Ctrl+C 停止\n",
            )
            datasette_main.assert_called_once()

    def test_serve_brackets_ipv6_host_in_printed_address(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            database = Path(td) / "projection.sqlite"
            database.touch()
            output = StringIO()
            with patch("datasette.cli.cli.main"):
                with redirect_stdout(output):
                    result = serve_main([
                        "--database", str(database), "--host", "::1", "--port", "8123",
                    ])

            self.assertEqual(result, 0)
            self.assertIn(f"http://[::1]:8123/", output.getvalue())

    def test_address_is_flushed_before_datasette_takes_over(self) -> None:
        # sol round 130, M2: a redirected stdout is block-buffered and Datasette never returns
        # while serving, so the address must already be in the underlying bytes when it starts.
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            database = Path(td) / "projection.sqlite"
            database.touch()
            raw = io.BytesIO()
            buffered = io.TextIOWrapper(io.BufferedWriter(raw), encoding="utf-8")
            seen_at_start: list[bytes] = []

            def datasette_started(*args, **kwargs):
                seen_at_start.append(raw.getvalue())

            with patch("datasette.cli.cli.main", side_effect=datasette_started):
                with redirect_stdout(buffered):
                    serve_main(["--database", str(database), "--port", "8123"])

            self.assertIn(b"http://127.0.0.1:8123/", seen_at_start[0])

    def test_authorized_canned_write_is_rejected_over_http(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            database = root / "projection.sqlite"
            metadata = root / "metadata.json"
            build_projection(WORKSPACE, database)
            metadata.write_text(
                json.dumps(
                    {
                        "databases": {
                            database.stem: {
                                "queries": {
                                    "mutation_probe": {
                                        "sql": (
                                            "UPDATE projection_meta SET value='MUTATED' "
                                            "WHERE key='projection_schema_version'"
                                        ),
                                        "write": True,
                                    }
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            port = _free_port()
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "ky.projection.serve",
                    "--database",
                    str(database),
                    "--metadata",
                    str(metadata),
                    "--port",
                    str(port),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            try:
                _wait_until_ready(port, process)
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/{database.stem}/mutation_probe",
                    data=b"{}",
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(request, timeout=3)
                body = caught.exception.read().decode("utf-8")
                caught.exception.close()
                self.assertEqual(caught.exception.code, 403)
                self.assertIn("Database is immutable", body)

                with closing(sqlite3.connect(f"file:{database}?mode=ro", uri=True)) as con:
                    value = con.execute(
                        "SELECT value FROM projection_meta "
                        "WHERE key='projection_schema_version'"
                    ).fetchone()[0]
                self.assertEqual(value, str(PROJECTION_SCHEMA_VERSION))
            finally:
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=5)
