# State source read ports (M13 / M26)

These ports provide parsed learning state together with SHA-256 digests of the exact bytes used
to parse each registered source file. M15 may consume these interfaces without parsing state YAML
or reopening a file to calculate its digest.

## M13 day plans and recorded events

`DayPlanStore.read_state_sources() -> DayPlanStateSources` returns a frozen result with:

- `plans: tuple[DayPlanRecord, ...]`, ordered by plan date. Each record contains `plan: DayPlan`,
  `version: int`, `actor: str`, and `input_hash: str | None`. Only the version named by each
  month's manifest is returned. Legacy entries expose `actor="unknown"` and
  `input_hash=None`, matching `day_plan_provenance()`.
- `completions: tuple[CompletionEvent, ...]`, ordered by event date. Completion files are checked
  against the path derived from their own event date, as in `delivered_words()`.
- `freeze_events: tuple[FreezeEvent, ...]`, ordered by global sequence, with the same location,
  sequence, and duplicate checks as `freeze_events()`.
- `sources: Mapping[str, str]`, a read-only mapping from POSIX paths relative to the day-plan
  store root to lowercase SHA-256 digests. It includes each discovered month manifest, each
  manifest's current plan file, each completion event, and each freeze event. It excludes prior
  plan versions, month closes, and unreferenced files.

An absent store root returns empty tuples and empty `sources`. A month manifest is read once per
call. A current plan whose bytes do not match its manifest digest raises `StorageError`; malformed
or misplaced event files also fail with the existing storage contract errors. Every digest is
computed from the same byte string passed to that file's parser.

## M13 review queue

`ReviewShardStore.read_state_sources() -> ReviewQueueStateSources` returns a frozen result with
`items: tuple[ReviewItem, ...]`, read-only `sources: Mapping[str, str]`,
`schema_version: int | None`, and `calculated_completion_ids: frozenset[str]`. Item values and order
match `ReviewShardStore.load()`. Source keys are POSIX paths relative to the queue store root and
cover `manifest.yaml` plus every shard listed by that manifest. The schema version and calculated
IDs come from the same parsed manifest bytes as the item list.

When the manifest is absent, the result contains an empty queue and empty `sources`, matching the
CLI's established optional-queue behavior. An existing invalid manifest, invalid shard, or shard
digest mismatch raises `StorageError`, as for `load()`. Digests use the exact manifest and shard
bytes parsed during the call.

## M13 current route

`RoutePlanStore.read_state_sources() -> RoutePlanReadResult` returns a frozen result with
`route: RoutePlan | None` and a read-only `sources: Mapping[str, str]`. Paths are POSIX and relative
to the route store root. With a current route, the mapping contains `routes_manifest.yaml` and only
the current revision file. With no manifest, the route is `None` and `sources` is empty. An existing
empty manifest returns `route=None` and includes the manifest. Invalid manifests, missing or invalid
current revisions, and digest mismatches raise `StorageError`, as for `current()`.

The manifest and current revision are each read once; their digests are calculated from the bytes
used by their parsers.

## M26 availability

`load_availability_with_source(path) -> AvailabilitySource` returns the validated
`availability: Availability` and `sha256: str` for that file. The digest is computed from the same
bytes decoded and parsed by the function. File absence and malformed content are errors with the
same contract behavior as `load_availability()`; registration continues to require the file to
exist.
