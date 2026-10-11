from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter


ROOT = Path(__file__).resolve().parents[1]


class ToolExitPathTests(unittest.TestCase):
    def test_tree_validators_start_without_pythonpath(self):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        commands = (
            ("validate_weighted_tree.py", "--help"),
            ("validate_supplementary_agreement.py",),
        )
        for command in commands:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools" / command[0]), *command[1:]],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)

    def test_unsupported_arguments_are_contract_exits(self):
        names = (
            "verify_408_question_extraction.py",
            "extract_408_questions_from_html.py",
            "render_weight_manual.py",
            "netem_cross_validate.py",
            "extract_exam_skeleton.py",
        )
        for name in names:
            with self.subTest(tool=name):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools" / name), "--unknown"],
                    cwd=ROOT,
                    capture_output=True,
                    timeout=20,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)

    def test_verifiers_reject_missing_databases(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing.sqlite"
            for name, expected in (
                ("verify_eng1_vocabulary.py", 1),
                ("verify_netem_source.py", 1),
            ):
                with self.subTest(tool=name):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(ROOT / "tools" / name),
                            "--db",
                            str(missing),
                        ],
                        cwd=ROOT,
                        capture_output=True,
                        timeout=20,
                    )
                    self.assertEqual(result.returncode, expected, result.stderr)
                    self.assertNotIn(b"Traceback", result.stderr)

    def test_skeleton_extractor_rejects_missing_pdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing.pdf"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "extract_exam_skeleton.py"),
                    "--pdf",
                    str(missing),
                ],
                cwd=ROOT,
                capture_output=True,
                timeout=20,
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_registered_weight_manual_writes_an_output_file(self):
        registry = ROOT / "kaoyan.workspace.yaml"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "manual.md"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "render_weight_manual.py"),
                    "--workspace",
                    str(registry),
                    "--out",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 0)

    def test_probe_success_and_non_pdf_failure(self):
        payload = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.write(payload)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                data = payload.getvalue() if self.path == "/valid.pdf" else b"not a PDF"
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, _format, *_args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        name = f"probe-{uuid.uuid4().hex}.pdf"
        target = ROOT / "cache" / "exam_probe" / name
        environment = os.environ.copy()
        environment["NO_PROXY"] = "127.0.0.1,localhost"
        environment["no_proxy"] = environment["NO_PROXY"]
        environment["PYTHONWARNINGS"] = "ignore::Warning:requests"
        try:
            for route, expected in (("/valid.pdf", 0), ("/invalid.pdf", 1)):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "tools" / "probe_exam_pdf.py"),
                        "--url",
                        f"http://127.0.0.1:{server.server_port}{route}",
                        "--name",
                        name,
                    ],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    timeout=20,
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertTrue(target.is_file())
                if expected == 0:
                    self.assertEqual(target.read_bytes(), payload.getvalue())
                else:
                    self.assertEqual(target.read_bytes(), b"not a PDF")
                target.unlink(missing_ok=True)
        finally:
            target.unlink(missing_ok=True)
            server.shutdown()
            server.server_close()

    def test_probe_connection_failure_is_a_contract_exit(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
        url = f"http://127.0.0.1:{port}/unreachable.pdf"
        name = f"exit-path-{uuid.uuid4().hex}.pdf"
        target = ROOT / "cache" / "exam_probe" / name
        env = os.environ.copy()
        env["NO_PROXY"] = "127.0.0.1,localhost"
        env["no_proxy"] = env["NO_PROXY"]
        # This isolates the contract line from the import-time environment warning; the
        # unfiltered case below confirms that the warning is passed through unchanged.
        env["PYTHONWARNINGS"] = "ignore::Warning:requests"
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "probe_exam_pdf.py"),
                    "--url",
                    url,
                    "--name",
                    name,
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(
                result.stderr,
                f"download failed: {url} (ConnectionError){os.linesep}".encode("utf-8"),
                result.stderr.decode("utf-8", errors="replace"),
            )
            self.assertFalse(target.exists())
        finally:
            target.unlink(missing_ok=True)

    def test_probe_connection_failure_passes_through_environment_warning(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
        url = f"http://127.0.0.1:{port}/unreachable.pdf"
        name = f"exit-path-unfiltered-{uuid.uuid4().hex}.pdf"
        target = ROOT / "cache" / "exam_probe" / name
        env = os.environ.copy()
        env["NO_PROXY"] = "127.0.0.1,localhost"
        env["no_proxy"] = env["NO_PROXY"]
        env.pop("PYTHONWARNINGS", None)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "probe_exam_pdf.py"),
                    "--url",
                    url,
                    "--name",
                    name,
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertFalse(target.exists())
            stderr = result.stderr.decode("utf-8", errors="replace")
            self.assertNotIn("Traceback", stderr)
            contract_line = f"download failed: {url} (ConnectionError)"
            nonempty_lines = [line for line in stderr.splitlines() if line.strip()]
            self.assertTrue(nonempty_lines, stderr)
            self.assertEqual(nonempty_lines[-1], contract_line, stderr)
            self.assertEqual(stderr.count(contract_line), 1, stderr)
        finally:
            target.unlink(missing_ok=True)

    def test_skeleton_json_outside_repository_uses_absolute_output_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "single-page.pdf"
            index = root / "structure.json"
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            with pdf.open("wb") as stream:
                writer.write(stream)

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "extract_exam_skeleton.py"),
                    "--pdf",
                    str(pdf),
                    "--json",
                    str(index),
                ],
                cwd=ROOT,
                capture_output=True,
                timeout=20,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, b"")
            payload = json.loads(index.read_text(encoding="utf-8"))
            self.assertEqual(
                payload,
                {
                    "pdf": str(pdf),
                    "pages": 1,
                    "question_start_count": 0,
                    "number_range": None,
                    "missing_numbers": [],
                    "duplicate_numbers": [],
                    "sections": [],
                    "question_lines": [],
                },
            )
            last_line = result.stdout.decode("utf-8").splitlines()[-1]
            self.assertEqual(
                last_line,
                f"index (structure only, no content) -> {index}",
            )
