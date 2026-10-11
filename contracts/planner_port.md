# Planner port (M19)

M19 publishes deterministic day/route input packages and applies day-plan and RoutePlan proposals
through the existing M13 store guardrails. Human-authored YAML and staged proposals use the same
apply path for each artifact type. The system does not call a model.

## Trust boundary

This single-user installation has no caller authentication. Runtime permissions must limit an AI
process to writing under `staging/`; a user or a trusted orchestrator runs either submit command.
An AI process must not invoke submit. The `actor` in a proposal is a claim used for audit, not
authentication. `--plan` is the user's direct submission path and records `actor: human` with
`input_hash: null`. When a workspace registry is found, it must load and validate successfully before
M19 rejects `--plan` files whose resolved path is under `write_target("staging")`; a found but invalid
registry fails closed. Only when no registry can be found and `--workspace` was omitted is the path
check skipped. `KY_WORKSPACE` also counts as discovery. A trusted orchestrator must not route an
AI-writable file through this shortcut. An explicitly supplied but invalid `--workspace` remains
an error.

## Input package

`ky planner-input [--kind day] --date D [--config C] [--workspace W]` writes the existing day JSON
object under
`write_target("staging")/inputs/<D>--<input_hash[:12]>.json` and prints that path and the full hash.
The object contains `schema_version: 1`, `kind: planner_input`, `day`, the complete validated
`KaoyanConfig` data model, the M12 snapshot JSON payload, the M9 daily review clipping summary,
the snapshot vocabulary `delivered` and `remaining` values, and configured
`default_daily_minutes`. `availability` is `null` when neither `state.availability` nor
`state.timetable` is registered; when either is registered it contains the resolved day value and
source as specified in `contracts/availability.md`. A `timetable` source, like `config`, is a
reference base; only an `availability` source is an M13 hard ceiling. The day review clip uses M8
`resolve_day_budget()` to combine
hand-entered daily minutes with the registered route phase's per-subject review quotas. Without a
route phase it preserves the configured clipping behavior. `route_plan` is specified below. Snapshot
and clipping data use the same builders and payload shapes
as `ky snapshot --json` and `ky preflight --json`. `review_clip` includes the complete preflight
payload except its summary `config`; the complete validated configuration is included once at the
input package's top-level `config` field, avoiding two configuration objects with different shapes.
After resolving M8, M27 backlog freeze takes precedence over phase quotas and daily availability:
while frozen, review selection and new-content allocation are both zero, and `review_clip` adds the
derived `freeze` summary. See `contracts/freeze.md`.
Input package writes use M13 `replace_bytes`: a same-directory temporary file is replaced into
place, so an existing target inode (including a hard link) is never opened and overwritten.

The serialized input package does not contain its own `input_hash`: self-inclusion would make the
hash recursive. The hash is returned by the command and represented by the filename. Its input is
the complete package object serialized as UTF-8 JSON with Unicode left unescaped, keys sorted
lexicographically, separators `(',', ':')`, and no indentation or trailing newline. The SHA-256
is over exactly those bytes. Repeated generation from identical validated inputs produces identical
bytes and hash.

## Proposal format and apply

Proposal YAML is a mapping with exactly `schema_version: 1`, `kind: day_plan_proposal`, `actor`,
`input_hash`, and `plan`. `plan` is parsed by M13 `parse_day_plan` and has the same mapping fields
as a stored DayPlan. `schema_version` must be an integer exactly equal to 1; booleans are rejected.
`actor` is `human` or matches `^ai:[a-z0-9][a-z0-9._-]*$`. Every staged proposal, including
`actor: human`, must provide a lowercase 64-character SHA-256 `input_hash`.

Staged submissions must resolve under `write_target("staging")/day_plans/`; containment follows
existing symlinks and junctions. Before writing or looking up day or route packages, M19 requires
the resolved `staging/<category>` directory to remain under resolved `staging`, and the resolved
target to remain under that category directory. This rejects a category directory that is a junction
outside staging. The matching package must be in `staging/inputs/`, its canonical
hash must match the proposal, and its `day` must match `plan.day`. The current package is then
regenerated for that day; if its hash differs, apply fails with
`输入已变化，请基于新输入包重新提案`. Expiration means the planner-visible input package content
changed. Source changes that do not change package content do not expire a proposal; for example,
a review item's title is not present in the package, and YAML comments or formatting are discarded
when configuration and queue inputs are parsed.

Expiration is checked before the store write and is not part of the same transaction. A concurrent
change after the check can make the committed plan no longer match the newest input; the port does
not guarantee freshness at the instant of the write.

A successful apply calls `DayPlanStore.write_day_plan` and records the actor and input hash on its
M13 manifest entry. No proposal is applied before all checks pass.

`ky day-plan submit --from-staging FILE` uses staged apply and requires an input package even for a
human actor. The retained `ky day-plan submit --plan FILE` treats the YAML as a human plan with null
input hash and delegates to the same apply function without requiring a staging path.

## Route input package and proposal

`ky planner-input --kind route --date D [--config C] [--workspace W]` writes
`write_target("staging")/inputs/route--<D>--<input_hash[:12]>.json`. The package has exactly
`schema_version: 1`, `kind: route_planner_input`, `day`, the complete `asdict(config)`,
`state_snapshot` with the same shape as `snapshot_to_mapping`, and `current_route`. The latter is
`route_plan_to_mapping(store.current())`, or null when there is no registered/current route. Route
packages do not contain daily review clipping. The package uses the same canonical JSON bytes and
SHA-256 rules as day packages, and does not contain its own hash.

A route proposal YAML mapping has exactly `schema_version: 1`, `kind: route_proposal`, `actor`,
`input_hash`, and `route`. The route is parsed by M11 `parse_route_plan`; its
`stage1_input_hash` must equal the proposal's required lowercase 64-character `input_hash`. The
field records the exact route input package on which the proposal is based. The current route's
revision in `current_route` identifies the next revision to propose; M13's
`RoutePlanStore.write_route_plan` enforces exactly current revision plus one with its
compare-and-swap write.

`ky route submit --from-staging FILE [--config C] [--workspace W]` accepts only a real path under
`staging/routes/`. Exactly one
`staging/inputs/route--*--<input_hash[:12]>.json` candidates are checked by canonical hash; candidates
whose hash differs, including unreadable or invalid JSON files, are skipped. A matching hash with a
wrong kind is an error, multiple matching valid packages are ambiguous, and no matching package is
an error. M19 regenerates a route package for its `day`; a different hash rejects
the proposal with `输入已变化，请基于新输入包重新提案`. Successful apply calls
`RoutePlanStore.write_route_plan` with the proposal's actor and hash. `--plan` and `--from-staging`
are mutually exclusive; human `--plan` wraps `actor: human` and `input_hash: null` through the same
M19 route apply function.

For day packages, `route_plan` is null without a registered current route or when `day` lies outside
the route's `[start_date, target_exam_date)` horizon. Otherwise it is
`{"route_id": ..., "revision": ..., "phase": ...}` for the phase containing the day. A
route revision therefore changes day-package bytes and expires staged day proposals based on the
prior route version. Without a current route, the day package remains byte-for-byte unchanged.

## M13 provenance

When pacing settings are registered, a day package's non-null `availability`
mapping also contains `base_minutes` and `base_source` with the resolved
`DayBudget` values (including zero and the `config` source). M28b's assembly passes
no pacing settings. M8 clipping
uses resolved `base` sources with the same override and floor policy as
availability and timetable sources.

The day-plan manifest advances to schema version 2 on write. Its current entry adds `actor` and
`input_hash`; absent fields in legacy entries are exposed as `unknown` and null without rewriting
the old file. The replaceable M19 implementation is `ky/planner/port.py`.
`DayPlanStore.day_plan_provenance(day)` returns `(version, actor, input_hash)` for
the current plan, or `None` when no plan is stored for that day. It reports only the current
version's provenance; provenance for earlier versions is not retained, even though versioned plan
files remain on disk.
