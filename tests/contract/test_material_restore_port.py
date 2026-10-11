"""M1 contract tests for contracts/material_restore.md."""

from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch

from ky.acquisition.ledger_restore import restore_materials
from ky.ledger.material import validate_material


class _Response(io.BytesIO):
    status = 200


class _UnavailableResponse(_Response):
    status = 503


class _InterruptedResponse(_Response):
    def read(self, size: int = -1) -> bytes:
        raise IncompleteRead(b"partial", 2)


def _material(
    resource_id: str, data: bytes, *, url: str | None = "https://example.test/source",
    mode: str = "local_file",
):
    local = mode == "local_file"
    return validate_material(
        {
            "resource_id": resource_id,
            "title": resource_id,
            "material_kind": "past_exam_paper",
            "subjects": ["alpha"],
            "acquisition": "public_download",
            "rights": {
                "status": "official_public",
                "may_store": local,
                "may_display": False,
                "may_redistribute": False,
                "may_be_structured": False,
            },
            "storage": {
                "mode": mode,
                "path": f"raw/{resource_id}.pdf" if local else None,
                "sha256": hashlib.sha256(data).hexdigest() if local else None,
                "byte_size": len(data) if local else None,
                "url": url,
            },
            "provenance": {"source_url": "https://example.test/landing"},
        },
        subject_ids={"alpha"},
    )


def _restore_row(
    resource_id: str, relative_path: str, data: bytes, *,
    url: str | None = "https://example.invalid/file", may_store: bool = True,
    mode: str = "local_file",
):
    raw = {
        "resource_id": resource_id,
        "title": resource_id,
        "material_kind": "outline_structure",
        "subjects": ["alpha"],
        "acquisition": "public_download",
        "rights": {
            "status": "official_public",
            "may_store": may_store,
            "may_display": False,
            "may_redistribute": False,
            "may_be_structured": may_store,
        },
        "storage": {
            "mode": mode,
            "path": relative_path if mode == "local_file" else None,
            "sha256": hashlib.sha256(data).hexdigest() if mode == "local_file" else None,
            "byte_size": len(data) if mode == "local_file" else None,
            "url": url,
        },
        "provenance": {"source_url": "https://example.invalid/material"},
    }
    if mode == "remote_reference":
        raw["rights"].update(
            status="unknown", may_store=False, may_be_structured=False,
        )
        raw["storage"] = {"mode": mode, "url": url}
    return validate_material(raw, subject_ids={"alpha"})


class MaterialRestorePortTests(unittest.TestCase):
    def test_restores_only_missing_verified_bytes_and_reports_every_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            raw_root.mkdir()
            (raw_root / "present.pdf").write_bytes(b"present")
            (raw_root / "damaged.pdf").write_bytes(b"wrong")
            rows = (
                _material("present", b"present"),
                _material("damaged", b"expected"),
                _material("new", b"fresh"),
                _material("no-url", b"missing", url=None),
                _material("link-only", b"", mode="remote_reference"),
            )
            called: list[str] = []

            def open_url(url: str, *, timeout: int):
                called.append(url)
                return _Response(b"fresh")

            results = restore_materials(rows, root=root, raw_root=raw_root, open_url=open_url)
            self.assertEqual(
                [result.status for result in results],
                ["already_verified", "existing_mismatch", "restored", "missing_url",
                 "reference_only"],
            )
            self.assertEqual(called, ["https://example.test/source"])
            self.assertEqual((raw_root / "new.pdf").read_bytes(), b"fresh")
            self.assertEqual((raw_root / "damaged.pdf").read_bytes(), b"wrong")

    def test_check_is_read_only_and_never_calls_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            row = _material("missing", b"data")

            def forbidden(*args, **kwargs):
                self.fail("check_only contacted the network")

            with patch(
                "ky.acquisition.ledger_restore.tempfile.TemporaryDirectory",
                side_effect=OSError("temporary directory unavailable"),
            ):
                results = restore_materials(
                    (row,), root=root, raw_root=raw_root, check_only=True, open_url=forbidden,
                )
            self.assertEqual(results[0].status, "needs_download")
            self.assertFalse(raw_root.exists())

    def test_check_only_reports_all_eight_material_row_states(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            raw_root.mkdir()
            (raw_root / "present.txt").write_bytes(b"present")
            (raw_root / "damaged.txt").write_bytes(b"wrong")

            reference_only = _restore_row(
                "reference", "", b"", url="https://example.invalid/ref",
                may_store=False, mode="remote_reference",
            )
            rows = (
                _restore_row("present", "raw/present.txt", b"present"),
                _restore_row("damaged", "raw/damaged.txt", b"expected"),
                _restore_row("bad-url", "raw/bad-url.txt", b"bad", url="https://[bad"),
                _restore_row("no-store", "raw/no-store.txt", b"no", may_store=False),
                _restore_row("no-url", "raw/no-url.txt", b"missing", url=None),
                _restore_row("outside", "../outside.txt", b"outside"),
                reference_only,
                _restore_row("missing", "raw/missing.txt", b"download"),
            )

            def forbidden(*args, **kwargs):
                self.fail("check_only must not contact the network")

            with patch(
                "ky.acquisition.ledger_restore.tempfile.TemporaryDirectory",
                side_effect=OSError("check mode must not create a temporary directory"),
            ):
                results = restore_materials(
                    rows, root=root, raw_root=raw_root, check_only=True, open_url=forbidden,
                )

        self.assertEqual(
            [item.status for item in results],
            ["already_verified", "existing_mismatch", "invalid_url", "storage_not_permitted",
             "missing_url", "invalid_path", "reference_only", "needs_download"],
        )

    def test_bad_url_is_per_row_and_does_not_stop_later_restoration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            rows = (
                _material("bad-url", b"bad", url="https://[broken"),
                _material("next", b"next"),
            )
            results = restore_materials(
                rows, root=root, raw_root=raw_root,
                open_url=lambda url, timeout: _Response(b"next"),
            )
            self.assertEqual([result.status for result in results], ["invalid_url", "restored"])
            self.assertFalse((raw_root / "bad-url.pdf").exists())
            self.assertEqual((raw_root / "next.pdf").read_bytes(), b"next")

    def test_bad_downloads_do_not_publish_and_later_rows_continue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            rows = (_material("wrong-hash", b"expected"), _material("next", b"next"))
            responses = iter((b"altered!", b"next"))

            def open_url(url: str, *, timeout: int):
                return _Response(next(responses))

            results = restore_materials(rows, root=root, raw_root=raw_root, open_url=open_url)
            self.assertEqual([result.status for result in results], ["sha256_mismatch", "restored"])
            self.assertFalse((raw_root / "wrong-hash.pdf").exists())
            self.assertEqual((raw_root / "next.pdf").read_bytes(), b"next")

    def test_network_error_and_size_error_leave_no_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            row = _material("missing", b"one")

            def failing(url: str, *, timeout: int):
                raise OSError("offline")

            failed = restore_materials((row,), root=root, raw_root=raw_root, open_url=failing)
            oversized = restore_materials(
                (row,), root=root, raw_root=raw_root,
                open_url=lambda url, timeout: _Response(b"too long"),
            )
            self.assertEqual(failed[0].status, "download_failed")
            self.assertIn("offline", failed[0].detail)
            self.assertEqual(oversized[0].status, "byte_size_mismatch")
            self.assertFalse((raw_root / "missing.pdf").exists())

    def test_incomplete_response_is_per_row_and_does_not_stop_later_restoration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            rows = (_material("interrupted", b"expected"), _material("next", b"next"))
            responses = iter((_InterruptedResponse(), _Response(b"next")))

            def open_url(url: str, *, timeout: int):
                return next(responses)

            results = restore_materials(rows, root=root, raw_root=raw_root, open_url=open_url)
            self.assertEqual(
                [result.status for result in results], ["download_failed", "restored"],
            )
            self.assertIn("IncompleteRead", results[0].detail)
            self.assertFalse((raw_root / "interrupted.pdf").exists())
            self.assertEqual((raw_root / "next.pdf").read_bytes(), b"next")

    def test_http_failure_and_target_appearing_during_download_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            row = _material("missing", b"data")
            unavailable = restore_materials(
                (row,), root=root, raw_root=raw_root,
                open_url=lambda url, timeout: _UnavailableResponse(b"data"),
            )
            self.assertEqual(unavailable[0].status, "http_error")
            self.assertFalse((raw_root / "missing.pdf").exists())

            def competing_writer(url: str, *, timeout: int):
                raw_root.mkdir()
                (raw_root / "missing.pdf").write_bytes(b"someone else's data")
                return _Response(b"data")

            contested = restore_materials(
                (row,), root=root, raw_root=raw_root, open_url=competing_writer,
            )
            self.assertEqual(contested[0].status, "target_conflict")
            self.assertEqual((raw_root / "missing.pdf").read_bytes(), b"someone else's data")


if __name__ == "__main__":
    unittest.main()
