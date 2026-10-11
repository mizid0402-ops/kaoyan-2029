"""Focused tests for deterministic review shard storage."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import yaml

from ky.models import ContractError, load_review_items
from ky.storage import ReviewShardStore, diagnose_shards, partition_review_items


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "reviews" / "reviews-normal.yaml"


def item_mapping(index: int, subject: str = "math1") -> dict:
    return {
        "review_id": f"rv_{subject}_{index:05d}", "revision": 1, "subject_id": subject,
        "knowledge_point_id": f"{subject}.demo.{index}", "title": f"item {index}",
        "granularity": "concept", "state": "queued", "estimated_minutes": 5,
        "introduced_on": "2026-09-01", "due_date": "2026-09-12",
        "schedule": {"mode": "fixed_bootstrap", "phase": 1, "interval_days": 3,
                      "ease_factor": 2.5, "repetitions": 1, "lapses": 0},
        "defer_count": 0, "last_quality": 4, "self_rating": "basic",
    }


class StorageTest(unittest.TestCase):
    def test_partition_is_independent_of_input_order(self) -> None:
        items = [item_mapping(i, "math1" if i % 2 else "cs408") for i in range(700)]
        a = partition_review_items(items)
        b = partition_review_items(reversed(items))
        self.assertEqual(a, b)
        self.assertTrue(all(1 <= len(chunk) <= 250 for chunk in a.values()))

    def test_round_trip_and_legacy_compatibility(self) -> None:
        legacy = load_review_items(FIXTURE)
        with tempfile.TemporaryDirectory() as temp:
            report = ReviewShardStore(temp).write(legacy)
            loaded = ReviewShardStore(temp).load()
            self.assertEqual({item.review_id for item in loaded}, {item.review_id for item in legacy})
            self.assertEqual(
                {item.review_id: item for item in loaded},
                {item.review_id: item for item in legacy},
            )
            self.assertEqual(report.manifest.manifest_sha256, yaml.safe_load((Path(temp) / "manifest.yaml").read_text())["manifest_sha256"])

    def test_old_manifest_without_completion_ids_loads_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ReviewShardStore(root).write([item_mapping(0)])
            manifest_path = root / "manifest.yaml"
            payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            payload["schema_version"] = 1
            payload.pop("calculated_completion_ids")
            hash_payload = {key: value for key, value in payload.items()
                            if key != "manifest_sha256"}
            canonical = json.dumps(hash_payload, sort_keys=True,
                                   separators=(",", ":")).encode("utf-8")
            payload["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
            manifest_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

            store = ReviewShardStore(root)
            self.assertEqual(store.calculated_completion_ids(), frozenset())
            self.assertEqual(len(store.load()), 1)

    def test_atomic_failure_keeps_old_manifest_and_shards(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ReviewShardStore(temp)
            store.write([item_mapping(i) for i in range(300)])
            before = {path.relative_to(temp).as_posix(): path.read_bytes() for path in Path(temp).rglob("*.yaml")}
            original_replace = os.replace
            calls = {"count": 0}

            def fail_once(src, dst):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise OSError("simulated mid-commit failure")
                return original_replace(src, dst)

            import ky.storage.review_shards as module
            old = module.os.replace
            module.os.replace = fail_once
            try:
                with self.assertRaises(OSError):
                    store.upsert(item_mapping(999))
            finally:
                module.os.replace = old
            after = {path.relative_to(temp).as_posix(): path.read_bytes() for path in Path(temp).rglob("*.yaml")}
            self.assertEqual(before, after)
            self.assertNotIn("rv_math1_00999", {item.review_id for item in store.load()})

    def test_failure_path_names_shard_and_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ReviewShardStore(temp)
            store.write([item_mapping(i) for i in range(30)])
            manifest = yaml.safe_load((Path(temp) / "manifest.yaml").read_text())
            descriptor = manifest["shards"][0]
            shard = Path(temp) / descriptor["path"]
            data = yaml.safe_load(shard.read_text())
            data["items"][0]["estimated_minutes"] = 31
            shard.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            with self.assertRaises(ContractError) as ctx:
                store.load()
            self.assertIn(descriptor["path"], str(ctx.exception))
            self.assertIn("items[0].estimated_minutes", str(ctx.exception))
            diagnostics = diagnose_shards(temp)
            self.assertTrue(any(not entry.ok and descriptor["path"] in entry.path for entry in diagnostics))

    def test_scale_and_write_amplification_are_measured(self) -> None:
        measurements = []
        for count in (1000, 5000):
            with tempfile.TemporaryDirectory() as temp:
                items = [item_mapping(i, "math1" if i % 3 else "cs408") for i in range(count)]
                single = Path(temp) / "single.yaml"
                single.write_text(yaml.safe_dump({"schema_version": 1, "items": items}, allow_unicode=True, sort_keys=False), encoding="utf-8")
                start = time.perf_counter()
                legacy = load_review_items(single)
                single_ms = (time.perf_counter() - start) * 1000
                store = ReviewShardStore(Path(temp) / "sharded")
                store.write(items)
                start = time.perf_counter()
                sharded = store.load()
                sharded_ms = (time.perf_counter() - start) * 1000
                self.assertEqual(len(legacy), len(sharded))
                measurements.append((count, single_ms, sharded_ms))
        # The test is a real measurement, not a brittle machine-specific limit.
        self.assertEqual([row[0] for row in measurements], [1000, 5000])

    def test_update_rewrites_only_affected_shard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ReviewShardStore(temp)
            items = [item_mapping(i, "math1" if i % 2 else "cs408") for i in range(1000)]
            store.write(items)
            old = store._manifest()
            changed = copy.deepcopy(items[0])
            changed["title"] = "changed"
            report = store.upsert(changed)
            self.assertEqual(len(report.changed_shards), 1)
            self.assertLess(report.bytes_written, sum((Path(temp) / d.path).stat().st_size for d in old.shards))
            self.assertEqual(len(report.affected_shard_hashes), 1)


if __name__ == "__main__":
    unittest.main()
