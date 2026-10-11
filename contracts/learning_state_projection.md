# Learning-state projection contract (M15, schema version 3 and later)

The SQLite projection adds read-only, rebuildable learning-state tables. M15 reads state only
through the M13/M26 source ports and stores facts supplied by those ports. The projection is not
the source of truth and does not calculate study recommendations.

## Source interfaces

`read_learning_state(workspace: Workspace) -> LearningState` in
`ky.projection.learning_state` reads:

- `ReviewShardStore.read_state_sources()` for review items;
- `DayPlanStore.read_state_sources()` for current day plans, completion events, and freeze events;
- `RoutePlanStore.read_state_sources()` for the current route, when `state.routes` is registered;
- `load_availability_with_source(path)` for registered availability.

`write_learning_state(connection: sqlite3.Connection, state: LearningState) -> None` creates and
fills the learning-state tables in the projection's temporary SQLite database. M15 does not parse
state YAML or reopen a source file to compute its hash.

`projection_meta.state_inputs` is a JSON object. Each key is
`<registry-key>/<path-relative-to-that-store-root>` with POSIX separators, and each value is the
SHA-256 supplied by the source port. Keys are sorted before serialization. Store keys include
`state.review_queue`, `state.plans`, and `state.routes`; the single availability file is named
`state.availability/<file-name>` relative to its parent directory. A path is represented only once.

`projection_meta.freeze_events_latched` is `"1"` or `"0"`, calculated by M27
`latch_active(freeze_events)`. It reports whether the append-only event history currently has an
unresolved freeze latch. It is not a statement that any particular day is frozen. Whether a day is
frozen depends on the query date and queue and belongs to F-c.

## Table schemas and source mapping

All dates are stored as strict ISO `YYYY-MM-DD` text. Rows are inserted in deterministic key order.
Nullable values remain SQL `NULL`.

| Table | Columns and types | Source |
|---|---|---|
| `review_items` | `review_id TEXT PK`, `revision INTEGER`, `subject_id TEXT`, `knowledge_point_id TEXT`, `title TEXT`, `granularity TEXT`, `state TEXT`, `estimated_minutes INTEGER`, `introduced_on TEXT`, `due_date TEXT`, `last_reviewed_on TEXT NULL`, `schedule_mode TEXT`, `schedule_phase INTEGER`, `interval_days INTEGER`, `ease_factor REAL`, `repetitions INTEGER`, `lapses INTEGER`, `stability REAL NULL`, `difficulty REAL NULL`, `fsrs_reviewed_on TEXT NULL`, `defer_count INTEGER`, `last_quality INTEGER NULL`, `last_self_rating TEXT NULL` | Every public `ReviewItem` fact from the review-queue source port; `schedule_*` columns map to its `schedule` fields. |
| `day_plans` | `day TEXT PK`, `available_minutes INTEGER`, `knowledge_minutes INTEGER`, `vocab_minutes INTEGER`, `vocab_new_items INTEGER`, `phrase_minutes INTEGER`, `backlog_minutes INTEGER`, `notes TEXT`, `version INTEGER`, `actor TEXT`, `input_hash TEXT NULL` | Current `DayPlanRecord` only: all `DayPlan` scalar fields plus M13 version and provenance. `backlog_minutes` and other allocations are the stored plan values at write time, not amounts recalculated for a query date. |
| `day_plan_subject_minutes` | `day TEXT`, `subject_id TEXT`, `minutes INTEGER`, PK (`day`, `subject_id`) | `DayPlan.subject_minutes` mapping, one row per subject allocation. |
| `completion_events` | `event_day TEXT PK`, `review_count INTEGER`, `delivered_word_count INTEGER`, `practiced_word_count INTEGER` | One row per `CompletionEvent`; counts describe its child review and vocabulary facts. |
| `completion_reviews` | `event_day TEXT`, `ordinal INTEGER`, `completion_id TEXT NULL`, `review_id TEXT`, `completed_on TEXT`, `check_method TEXT`, `outcome TEXT NULL`, `question_ref TEXT NULL`, `self_rating TEXT NULL`, PK (`event_day`, `ordinal`) | Each `ReviewCompletion` in event order. `check_method` is `ReviewCompletion.check`. |
| `completion_vocab_words` | `event_day TEXT`, `vocab_kind TEXT` (`delivered` or `practiced`), `ordinal INTEGER`, `word TEXT`, PK (`event_day`, `vocab_kind`, `ordinal`) | `VocabProgress.delivered_words` and `practiced_words` remain separate facts. |
| `freeze_events` | `sequence INTEGER PK`, `kind TEXT`, `day TEXT` | All M13 `FreezeEvent` values in sequence order. |
| `route_phases` | `phase INTEGER PK`, `route_id TEXT`, `revision INTEGER`, `label TEXT`, `start TEXT`, `end_exclusive TEXT` | Phases from the current `RoutePlan`. |
| `route_phase_review_minutes` | `phase INTEGER`, `subject_id TEXT`, `minutes INTEGER`, PK (`phase`, `subject_id`) | Each current route phase's `review_minutes` mapping. |
| `availability_days` | `day TEXT PK`, `minutes INTEGER` | Registered M26 availability values. |

`completion_events` counts are summaries of the event's own child facts; they are not estimates.
The schema has no per-task day-plan table because `DayPlan` contains no individual task records.

## Missing, invalid, and unchanged-output behavior

`state.review_queue` and `state.plans` are mandatory registry entries. A missing queue manifest
produces an empty `review_items` table and contributes no queue file to `state_inputs`. A missing
day-plan store root produces empty plan, completion, and freeze tables. The ports reject invalid
manifests, shard digests, plan digests, misplaced event files, and malformed records; M15 lets
those `ContractError` failures abort the build.

An unregistered `state.routes` produces empty `route_phases` and
`route_phase_review_minutes` tables. A registered route store without a manifest has no current
route and no route sources; invalid route state aborts the build. An unregistered availability
file produces an empty `availability_days` table. A registered availability file must exist and
validate; absence or invalid content aborts the build.

Every source digest in `state_inputs` is the digest returned alongside the object parsed from the
same byte sequence. State loading and validation complete before the final output is replaced.
Failure preserves an existing projection byte-for-byte. Successful builds use the same temporary
database and atomic replacement process as the reference tables.

## Determinism and read boundary

For identical registered input bytes, all table rows and metadata values are identical across
builds. Rows and JSON object keys have stable ordering; no build time, current date, or query-time
state is persisted. Names in the learning schema do not encode a recommendation or next action.

After a write command commits a state fact, running `build_projection(workspace)` rebuilds the
database so that the fact can be read from SQLite. A running `serve --immutable` process does not
automatically switch to a newly built database. W2 owns the front-end refresh flow. Writes made
with explicit `--store` or `--items` paths outside the registered workspace stores are not part
of the registered projection inputs and therefore are not projected.

F-c owns queries that interpret these facts for a particular date. This schema does not store
"today", due status, live backlog, or whether a specific day is frozen.
