"""Durable, deterministic storage for review queues.

The storage layer is deliberately separate from :mod:`ky.models`: the latter
continues to own the single-file compatibility format and item semantics,
while this package owns manifests, shards, atomic commits and diagnostics.
"""

from .review_shards import (
    DEFAULT_BUCKET_COUNT,
    DEFAULT_SHARD_SIZE,
    Manifest,
    ReviewShardStore,
    ShardDescriptor,
    StorageDiagnostic,
    StorageError,
    WriteReport,
    diagnose_shards,
    load_review_queue,
    load_sharded_reviews,
    partition_review_items,
    write_review_queue,
)

__all__ = [
    "DEFAULT_BUCKET_COUNT",
    "DEFAULT_SHARD_SIZE",
    "Manifest",
    "ReviewShardStore",
    "ShardDescriptor",
    "StorageDiagnostic",
    "StorageError",
    "WriteReport",
    "diagnose_shards",
    "load_review_queue",
    "load_sharded_reviews",
    "partition_review_items",
    "write_review_queue",
]
