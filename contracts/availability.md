# M26 daily availability contract

## File format

`state.availability` is an optional workspace registration. When registered, the file must exist.
It is UTF-8 YAML with exactly these top-level fields:

```yaml
schema_version: 1
days:
  2026-10-01: 90
```

`schema_version` must be the exact integer `1`. `days` maps a day to a non-negative integer number
of minutes. Keys may be YAML date scalars or strict `YYYY-MM-DD` strings. Datetime keys, invalid
dates, and duplicate dates after normalization are rejected. Boolean and floating-point minute
values are rejected. Unknown top-level fields and malformed YAML are contract errors. Errors include
the file or field path, such as `days.2026-10-01`.

Top-level field names must be strings. A non-string key is rejected as a contract error at that
key's path before unknown fields are sorted, so mixed YAML key types cannot cause a comparison
error.

## Interface

- `load_availability(path) -> Availability` reads and validates the file.
- `DerivedDailyMinutes` is a protocol with `minutes_for(day, base_minutes) -> int | None`.
  M26 does not import its implementations.
- `resolve_daily_minutes(day, base_minutes, availability, timetable=None) -> DailyMinutes` returns
  `minutes` and `source`, where source is `availability`, `timetable`, or `config`.
- `ky.models.scale_minutes(total_minutes, ratio) -> int` is the shared exact-rational floor used by
  M8 and M9 when deriving review caps; it avoids float rounding drift for large accepted budgets.
- `availability_for_workspace(workspace) -> Availability | None` returns `None` when the key is
  unregistered. When registered, it loads the file and rejects a missing file.
- `set_day_minutes(path, day, minutes) -> None` is the M33 write interface described in
  `contracts/today.md` §5.

An entry for the requested day wins, including an entry of zero. Otherwise, a non-`None` value from
the derived timetable wins, including zero; the provider receives the caller-resolved daily base.
When neither supplies a value, the result is the caller-provided base with source `config`.

When the source is `availability` or `timetable`, preflight and M19 input allocation use
`drop_when_short`: if
active-subject minimums exceed the day's new-content budget, all minimums are waived for that day
and the budget is split by the configured weights. The allocation reports zero applied floor for
each subject. If minimums fit, they apply as usual. The default allocator policy remains `strict`
and still rejects an insufficient budget. A hand-entered value records the learner's stated fact
about that day, so a short day is not treated as a configuration error.

M8 `resolve_day_budget()` combines this total-minute resolution with an optional RoutePlan phase.
The hand-entered total remains authoritative while that phase supplies M9 per-subject review
quotas; see `contracts/route_plan.md` for validation and clipping rules.

Preflight searches upward for a workspace registry when one is not specified. If discovery finds
an invalid registry, preflight exits with status 2 rather than treating it as absent and succeeding
with the configured capacity. This fail-closed behavior is intentional (sol round 107, item 2).

## Consumers

- M9 review clipping through `ky preflight` and M19 day planner input.
- M19 input packages expose `availability: null` when neither source is registered, or
  `{"minutes": N, "source": "availability" | "timetable" | "config"}` when either source is
  registered. Timetable and config values are reference bases; only `availability` is an M13 hard
  ceiling.
- M13 `DayPlanStore` rejects a plan whose `available_minutes` exceeds a hand-entered value for that
  day. Days without an entry have no additional ceiling.

For M9, `unschedulable` means an item needs to be split: its cost exceeds both the configured hard
review cap and the day's hard review cap. A day's smaller hand-entered capacity only defers an
otherwise schedulable item for that day; a larger hand-entered capacity may schedule an item that
would not fit a configured day. Without a hand-entered override, both limits are equal.

The contract covers per-day entries only. Weekly templates, ranges, and timetable imports are out of
scope.

M28b adds `base` to M8's `total_source` values. This source means M26 fell
back to a daily base selected from a route phase or an effective pacing
`initial`; `base_source` distinguishes that origin from exam configuration.
The three-step clipping order is freeze (`0`, `drop_when_short`), then
`availability`/`timetable`/`base` (resolved override,
`drop_when_short`), then `config` (legacy behavior).
