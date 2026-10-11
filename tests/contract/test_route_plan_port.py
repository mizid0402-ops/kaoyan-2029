"""M11/M13/M14 route-plan format, immutable storage, and CLI contract tests."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import yaml

from ky.models import load_yaml_text
from ky.schedule.planning import (
    Phase,
    RoutePlan,
    RoutePlanError,
    parse_route_plan,
    route_plan_to_mapping,
)
from ky.storage.day_plan_store import StorageError
from ky.storage.route_store import RoutePlanStore


START = date(2026, 9, 15)
INPUT_HASH = "a" * 64
TARGET = START + timedelta(days=60)


def make_route(
    revision: int = 1, *, start: date = START, target: date = TARGET,
    boundaries: tuple[date, ...] = (),
) -> RoutePlan:
    points = (start, *boundaries, target)
    phases = tuple(
        Phase(
            index=index,
            start=phase_start,
            end_exclusive=phase_end,
            label=f"phase-{index}",
            review_minutes={"math1": 30, "eng1": 20},
        )
        for index, (phase_start, phase_end) in enumerate(zip(points, points[1:]))
    )
    return RoutePlan(
        route_id="route-alpha",
        revision=revision,
        start_date=start,
        target_exam_date=target,
        policy_version="policy-v1",
        stage1_input_hash=INPUT_HASH,
        phases=phases,
    )


def directory_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class TestRoutePlanFormat(unittest.TestCase):
    def test_optional_base_uses_v3_and_v2_rejects_the_field(self) -> None:
        v2 = route_plan_to_mapping(make_route())
        self.assertEqual(v2["schema_version"], 2)
        self.assertEqual(parse_route_plan(v2), make_route())
        phase = replace(make_route().phases[0], base_daily_minutes=0)
        v3_plan = replace(make_route(), phases=(phase,))
        v3 = route_plan_to_mapping(v3_plan)
        self.assertEqual(v3["schema_version"], 3)
        self.assertEqual(v3["phases"][0]["base_daily_minutes"], 0)
        self.assertEqual(parse_route_plan(v3), v3_plan)
        v2_with_field = {**v3, "schema_version": 2}
        with self.assertRaises(RoutePlanError):
            parse_route_plan(v2_with_field)
        invalid = {**v3, "phases": [dict(v3["phases"][0], base_daily_minutes=True)]}
        with self.assertRaises(RoutePlanError):
            parse_route_plan(invalid)

    def test_round_trip_and_unquoted_yaml_dates(self) -> None:
        plan = make_route()
        mapping = route_plan_to_mapping(plan)
        self.assertEqual(parse_route_plan(mapping), plan)
        quoted = yaml.safe_dump(mapping, sort_keys=False)
        start = START.isoformat()
        # Unquote the start date so YAML yields a `date`; assert it happened (sol round 112).
        text = quoted.replace(f"'{start}'", start)
        self.assertNotEqual(text, quoted)
        raw = load_yaml_text(text)
        self.assertIsInstance(raw["start_date"], date)
        self.assertEqual(parse_route_plan(raw), plan)

    def test_v4_targets_round_trip_and_rules(self) -> None:
        route = make_route(boundaries=(START + timedelta(days=20),))
        phases = (
            replace(route.phases[0], base_daily_minutes=180,
                    targets={"covered": 50, "consolidated": 25}),
            replace(route.phases[1], targets={"covered": 75, "consolidated": 50}),
        )
        plan = replace(route, phases=phases)
        mapping = route_plan_to_mapping(plan)
        self.assertEqual(mapping["schema_version"], 4)
        self.assertEqual(mapping["phases"][0]["base_daily_minutes"], 180)
        self.assertEqual(parse_route_plan(mapping), plan)

        invalid = replace(phases[0], targets={"covered": 50, "consolidated": 51})
        with self.assertRaises(RoutePlanError) as caught:
            parse_route_plan({**mapping, "phases": [
                {**mapping["phases"][0], "targets": dict(invalid.targets)},
                mapping["phases"][1],
            ]})
        self.assertEqual(caught.exception.path, "phases[0].targets.consolidated")

        decreasing = [dict(phase) for phase in mapping["phases"]]
        decreasing[1]["targets"] = {"covered": 49, "consolidated": 24}
        with self.assertRaises(RoutePlanError) as caught:
            parse_route_plan({**mapping, "phases": decreasing})
        self.assertEqual(caught.exception.path, "phases[1].targets.covered")

        for schema in (2, 3):
            phases_for_schema = [dict(phase) for phase in mapping["phases"]]
            if schema == 2:
                for phase in phases_for_schema:
                    phase.pop("base_daily_minutes", None)
            legacy = {**mapping, "schema_version": schema, "phases": phases_for_schema}
            with self.subTest(schema=schema), self.assertRaises(RoutePlanError) as caught:
                parse_route_plan(legacy)
            self.assertEqual(caught.exception.path, "route_plan.phases[0].targets")

    def test_legacy_v2_v3_without_targets_keep_serialized_bytes(self) -> None:
        v2_plan = make_route()
        v3_plan = replace(
            v2_plan,
            phases=(replace(v2_plan.phases[0], base_daily_minutes=0),),
        )
        for plan in (v2_plan, v3_plan):
            original = yaml.safe_dump(route_plan_to_mapping(plan), sort_keys=False,
                                      allow_unicode=True).encode("utf-8")
            parsed = parse_route_plan(load_yaml_text(original.decode("utf-8")))
            rebuilt = yaml.safe_dump(route_plan_to_mapping(parsed), sort_keys=False,
                                     allow_unicode=True).encode("utf-8")
            with self.subTest(schema=route_plan_to_mapping(plan)["schema_version"]):
                self.assertEqual(original, rebuilt)

    def test_rejects_invalid_shape_types_and_closure_with_paths(self) -> None:
        mapping = route_plan_to_mapping(make_route())
        with self.subTest("unknown top-level key"):
            raw = {**mapping, "extra": 1}
            self.assert_path(raw, "route_plan.extra")
        with self.subTest("missing phase key"):
            raw = json.loads(json.dumps(mapping))
            del raw["phases"][0]["label"]
            self.assert_path(raw, "route_plan.phases[0].label")
        with self.subTest("boolean revision"):
            raw = {**mapping, "revision": True}
            self.assert_path(raw, "route_plan.revision")
        with self.subTest("datetime"):
            raw = {**mapping, "start_date": datetime(2026, 9, 15, 8)}
            self.assert_path(raw, "route_plan.start_date")
        with self.subTest("schema string"):
            raw = {**mapping, "schema_version": "2"}
            self.assert_path(raw, "route_plan.schema_version")
        with self.subTest("closure violation"):
            raw = json.loads(json.dumps(mapping))
            raw["phases"][0]["review_minutes"]["math1"] = -1
            self.assert_path(raw, "phases[0].review_minutes.math1")

    def test_rejects_schema_version_one_with_d10_migration_message(self) -> None:
        # A real old file: 24-month shape with `months`, no `phases`.
        raw = route_plan_to_mapping(make_route())
        raw["schema_version"] = 1
        raw["months"] = raw.pop("phases")
        with self.assertRaises(RoutePlanError) as caught:
            parse_route_plan(raw)
        self.assertEqual(caught.exception.path, "route_plan.schema_version")
        self.assertIn("D10", str(caught.exception))

    def assert_path(self, raw: object, path: str) -> None:
        with self.assertRaises(RoutePlanError) as caught:
            parse_route_plan(raw)
        self.assertEqual(caught.exception.path, path)


class TestRoutePlanStore(unittest.TestCase):
    def test_revision_context_for_an_empty_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            context = RoutePlanStore(temporary).read_revision_context(1)
            self.assertEqual(context.current_revision, 0)
            self.assertIsNone(context.actor)
            self.assertIsNone(context.input_hash)
            self.assertIsNone(context.route)

    def test_versions_keep_bytes_sources_and_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = RoutePlanStore(temporary)
            first = store.write_route_plan(make_route(), actor="human", input_hash=None)
            first_bytes = Path(first.path).read_bytes()
            second = store.write_route_plan(
                make_route(2), actor="agent", input_hash=INPUT_HASH
            )
            self.assertEqual(Path(first.path).read_bytes(), first_bytes)
            self.assertEqual(store.current(), make_route(2))
            self.assertEqual(store.load_revision(1), make_route())
            self.assertEqual(store.provenance(1), ("human", None))
            self.assertEqual(store.provenance(2), ("agent", INPUT_HASH))
            context = store.read_revision_context(2)
            self.assertEqual(context.current_revision, 2)
            self.assertEqual((context.actor, context.input_hash), ("agent", INPUT_HASH))
            self.assertEqual(context.route, make_route(2))
            pending = store.read_revision_context(3)
            self.assertEqual(pending.current_revision, 2)
            self.assertIsNone(pending.route)
            manifest = load_yaml_text((Path(temporary) / "routes_manifest.yaml").read_text())
            self.assertEqual(
                [entry["actor"] for entry in manifest["revisions"]], ["human", "agent"]
            )
            self.assertEqual(
                [entry["input_hash"] for entry in manifest["revisions"]], [None, INPUT_HASH]
            )

    def test_compare_and_swap_rejections_write_no_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = RoutePlanStore(root)
            store.write_route_plan(make_route(), actor="human")
            before = directory_bytes(root)
            invalid = (
                replace(make_route(), revision=3),
                replace(make_route(), revision=1),
                replace(make_route(2), route_id="route-other"),
            )
            paths = ("revision", "revision", "route_id")
            for plan, path in zip(invalid, paths):
                with self.subTest(path=path, revision=plan.revision):
                    with self.assertRaises(StorageError) as caught:
                        store.write_route_plan(plan)
                    self.assertEqual(caught.exception.path, path)
                    self.assertEqual(directory_bytes(root), before)

    def test_tampered_revision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = RoutePlanStore(temporary)
            report = store.write_route_plan(make_route(), actor="human")
            Path(report.path).write_bytes(Path(report.path).read_bytes() + b"# altered\n")
            with self.assertRaisesRegex(StorageError, "SHA-256 mismatch"):
                store.current()

    def test_manifest_rejects_invalid_shape_order_and_route_identity(self) -> None:
        mutations = (
            (
                "boolean schema",
                lambda manifest, root: manifest.update(schema_version=True),
                "routes_manifest.yaml.schema_version",
            ),
            (
                "string revision",
                lambda manifest, root: manifest["revisions"][0].update(revision="1"),
                "routes_manifest.yaml.revisions[0].revision",
            ),
            (
                "non-mapping revision",
                lambda manifest, root: manifest.update(revisions=["x"]),
                "routes_manifest.yaml.revisions[0]",
            ),
            (
                "path traversal",
                self._set_manifest_path_outside_root,
                "routes_manifest.yaml.revisions[0].path",
            ),
            (
                "revision gap",
                self._set_manifest_revision_gap,
                "routes_manifest.yaml.revisions[0].revision",
            ),
            (
                "route identity mismatch",
                self._set_route_identity_mismatch,
                "route--r1.yaml.route_id",
            ),
        )
        for label, mutate, expected_path in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "store"
                store = RoutePlanStore(root)
                store.write_route_plan(make_route())
                manifest_path = root / "routes_manifest.yaml"
                manifest = load_yaml_text(manifest_path.read_text(encoding="utf-8"))
                mutate(manifest, Path(temporary))
                manifest_path.write_text(
                    yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
                )
                with self.assertRaises(StorageError) as caught:
                    store.current()
                self.assertTrue(caught.exception.path.endswith(expected_path))

    @staticmethod
    def _set_manifest_path_outside_root(manifest: dict, temporary: Path) -> None:
        outside = temporary / "outside.yaml"
        outside.write_bytes((temporary / "store" / "route--r1.yaml").read_bytes())
        manifest["revisions"][0]["path"] = "../outside.yaml"

    @staticmethod
    def _set_manifest_revision_gap(manifest: dict, temporary: Path) -> None:
        source = temporary / "store" / "route--r1.yaml"
        target = temporary / "store" / "route--r2.yaml"
        target.write_bytes(source.read_bytes())
        manifest["revisions"][0]["revision"] = 2
        manifest["revisions"][0]["path"] = "route--r2.yaml"

    @staticmethod
    def _set_route_identity_mismatch(manifest: dict, temporary: Path) -> None:
        route_path = temporary / "store" / "route--r1.yaml"
        route = load_yaml_text(route_path.read_text(encoding="utf-8"))
        route["route_id"] = "route-other"
        route_bytes = yaml.safe_dump(route, sort_keys=False).encode("utf-8")
        route_path.write_bytes(route_bytes)
        manifest["revisions"][0]["sha256"] = hashlib.sha256(route_bytes).hexdigest()

    def test_manifest_write_failure_rolls_back_version_and_allows_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = RoutePlanStore(root)
            with patch(
                "ky.storage.route_store.replace_bytes",
                side_effect=OSError("manifest unavailable"),
            ):
                with self.assertRaisesRegex(OSError, "manifest unavailable"):
                    store.write_route_plan(make_route())
            self.assertFalse((root / "route--r1.yaml").exists())
            store.write_route_plan(make_route())
            self.assertEqual(store.current(), make_route())

    def test_manifest_failure_preserves_replaced_external_version_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            final_path = root / "route--r1.yaml"
            external_bytes = b"external replacement"

            def replace_after_external_write(path: Path, data: bytes) -> None:
                final_path.unlink()
                final_path.write_bytes(external_bytes)
                raise OSError("manifest unavailable")

            with patch(
                "ky.storage.route_store.replace_bytes",
                side_effect=replace_after_external_write,
            ):
                with self.assertRaisesRegex(OSError, "manifest unavailable"):
                    RoutePlanStore(root).write_route_plan(make_route())
            self.assertEqual(final_path.read_bytes(), external_bytes)

    def test_rollback_keeps_file_swapped_in_right_after_publish(self) -> None:
        # sol round 105, A1: the swap happens between os.link and any later stat of the target.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            final_path = root / "route--r1.yaml"
            external_bytes = b"external replacement"
            real_link = os.link

            def link_then_swap(source: object, target: object) -> None:
                real_link(source, target)
                final_path.unlink()
                final_path.write_bytes(external_bytes)

            with patch("ky.storage.route_store.os.link", side_effect=link_then_swap), patch(
                "ky.storage.route_store.replace_bytes",
                side_effect=OSError("manifest unavailable"),
            ):
                with self.assertRaisesRegex(OSError, "manifest unavailable"):
                    RoutePlanStore(root).write_route_plan(make_route())
            self.assertTrue(final_path.exists(), "rollback deleted the swapped-in file")
            self.assertEqual(final_path.read_bytes(), external_bytes)

    def test_invalid_provenance_is_rejected_before_any_file_is_written(self) -> None:
        invalid_sources = (
            ("x", "human", "input_hash"),
            ("A" * 64, "human", "input_hash"),
            (None, None, "actor"),
        )
        for input_hash, actor, field in invalid_sources:
            with self.subTest(input_hash=input_hash, actor=actor):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    before = directory_bytes(root)
                    with self.assertRaises(StorageError) as caught:
                        RoutePlanStore(root).write_route_plan(
                            make_route(), actor=actor, input_hash=input_hash,
                        )
                    self.assertEqual(caught.exception.path, field)
                    self.assertEqual(directory_bytes(root), before)

    def test_unregistered_version_file_requires_manual_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            orphan = root / "route--r1.yaml"
            orphan.write_bytes(b"unregistered")
            with patch("ky.storage.route_store.os.link") as link:
                with self.assertRaisesRegex(StorageError, "未登记的版本文件") as caught:
                    RoutePlanStore(root).write_route_plan(make_route())
                link.assert_not_called()
            self.assertEqual(caught.exception.path, orphan.as_posix())
            self.assertEqual(orphan.read_bytes(), b"unregistered")

    def test_publish_does_not_replace_a_racing_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            final_path = root / "route--r1.yaml"
            external_bytes = b"external writer"
            real_link = os.link

            def create_target_then_link(source: str | Path, target: str | Path) -> None:
                Path(target).write_bytes(external_bytes)
                real_link(source, target)

            with patch("ky.storage.route_store.os.link", side_effect=create_target_then_link):
                with self.assertRaisesRegex(StorageError, "未登记的版本文件"):
                    RoutePlanStore(root).write_route_plan(make_route())
            self.assertEqual(final_path.read_bytes(), external_bytes)


class TestRoutePlanCli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        return subprocess.run(
            [sys.executable, "-m", "ky", "route", *args],
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def test_submit_then_show_json_and_invalid_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan_path = root / "route.yaml"
            plan_path.write_text(
                yaml.safe_dump(route_plan_to_mapping(make_route()), sort_keys=False),
                encoding="utf-8",
            )
            submitted = self.run_cli(
                "submit", "--plan", str(plan_path), "--store", str(root / "store")
            )
            self.assertEqual(submitted.returncode, 0, submitted.stderr)
            shown = self.run_cli("show", "--json", "--store", str(root / "store"))
            self.assertEqual(shown.returncode, 0, shown.stderr)
            payload = json.loads(shown.stdout)
            self.assertEqual(payload["route_plan"], route_plan_to_mapping(make_route()))
            self.assertEqual(payload["actor"], "human")
            self.assertIsNone(payload["input_hash"])

            shown_text = self.run_cli("show", "--store", str(root / "store"))
            self.assertEqual(shown_text.returncode, 0, shown_text.stderr)
            self.assertIn("2026-09-15–2026-11-14 [右开] phase-0", shown_text.stdout)
            self.assertIn("eng1=20 math1=30", shown_text.stdout)

            invalid = route_plan_to_mapping(make_route())
            invalid["revision"] = True
            plan_path.write_text(yaml.safe_dump(invalid), encoding="utf-8")
            store_before = directory_bytes(root / "store")
            rejected = self.run_cli(
                "submit", "--plan", str(plan_path), "--store", str(root / "store")
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(directory_bytes(root / "store"), store_before)

    def test_unregistered_state_routes_requires_override_or_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "kaoyan.workspace.yaml"
            source = (Path(__file__).resolve().parents[2] / "kaoyan.workspace.yaml").read_text(
                encoding="utf-8"
            )
            registry = yaml.safe_load(source)
            del registry["state"]["routes"]
            workspace.write_text(
                yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            result = self.run_cli("show", "--workspace", str(workspace))
            self.assertEqual(result.returncode, 2)
            self.assertIn("--store", result.stderr)
            self.assertIn("state.routes", result.stderr)


if __name__ == "__main__":
    unittest.main()
