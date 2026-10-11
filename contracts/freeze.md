# M27 backlog freeze port (D11)

`ky.freeze.assess_freeze(day, config, items, policy, *, latched=False) -> FreezeStatus`
derives whether accumulated queued review work requires a temporary stop. The decision uses
the supplied date, validated configuration, queue, policy, and append-only latch state.

`FreezePolicy.backlog_days` is an integer of at least 1 and defaults to 3.
`FreezeStatus` exposes `frozen`, `overdue_minutes`, `overdue_count`, `threshold_minutes`,
`backlog_days`, and `latched`. Items with `state` equal to `queued` or `scheduled` and
`due_date < day` contribute. The threshold is `backlog_days * config.review_hard_cap_minutes()`; equality
freezes, but only when at least one item is overdue. Daily hand-entered availability does not
affect this threshold. Freeze is active when the threshold is reached or an unresolved freeze
event is latched. `unresolved_freezes(events)` returns the freeze events that have no later resume
event whose day is the same or later; `latch_active(events)` is true when that tuple is non-empty.
This rule affects the threshold only. Below the threshold, expired `scheduled` items remain
`unreachable` in M9 and can be replanned manually with `ky resume`; `ky resume` processes them even
when no latch is active.

M13 stores append-only records under `<state.plans>/freeze/`:

```yaml
schema_version: 1
sequence: 1
kind: freeze
day: YYYY-MM-DD
status: {overdue_minutes: 216, overdue_count: 1, threshold_minutes: 216,
  backlog_days: 3, latched: true, resume: "ky resume"}
```

The filename is `<sequence:06>-<kind>--<day>.yaml`, for example
`000001-freeze--2026-09-15.yaml`. A resume event uses `kind: resume` and has a `resume` mapping in
place of `status`. The sequence is a positive integer, globally increasing across both kinds;
the next sequence is one greater than the greatest existing sequence, starting at 1. Every
sequence file is written once. Writers reread and validate their temporary file, then publish it
with an atomic no-overwrite hard link. If another writer claims that sequence first, the write
fails with “序号已被占用，请重试”; publication never falls back to replacement, and no
cross-process lock is kept (single-user threat model, `AGENTS.md`). Readers return
`freeze_events() -> tuple[FreezeEvent, ...]` ordered by sequence and reject misplaced records,
duplicate sequences, or any mismatch among the filename's sequence, kind, date and content.

`day-plan record` and `day-plan submit` check the registered review queue before their action.
When the threshold is reached and no latch is active, they write a freeze event first.
`record` then proceeds normally so completed work remains truthful; when no registry is
available `record` writes no latch and still records, the same tolerance it has for check
questions, and prints “未找到可用的工作区注册表，未检查冻结锁存”. In that case, the manual
`ky resume` recovery guarantee does not apply because no freeze latch was checked or recorded.
`submit` is rejected. The
gate runs on the parsed `DayPlan` passed to M13 and again on its temporary-file reread, after
invariant and availability checks and before each file commit.

Preflight and M19 planner input only read freeze events; they never write them.
An active freeze stops review selection and new content, and its JSON payload adds a `freeze`
object including `latched`. Unfrozen payloads retain their previous JSON and text shape. Text
preflight marks review soft/hard as `冻结期间不生效` and omits the timeline phase while frozen.

`ky preflight --freeze-backlog-days N` overrides the default; values below one are usage errors
(exit 3). M19 uses the default policy. Both `day-plan submit --plan` and
`day-plan submit --from-staging` reject a frozen final plan with a contract error (exit 2) and
write no plan. If no workspace registry is discoverable, submission does not assess freeze.
When the registry exists but its registered review queue has no shard manifest yet, the queue
is treated as empty.

WP-R2 provides `ky resume`; it writes a resume event after replanning when a latch is active or
there are overdue entries to replan. A resume event clears a freeze event only when its sequence
is later and its day is equal to or later than that freeze event's day. A resume before a freeze
does not clear it. Multiple freeze and resume events on one day are valid and remain ordered by
their global sequence.

## `ky resume` (WP-R2, D11)

`ky resume --date D [--dry-run] [--json] [--config C] [--workspace W]` reads the queue registered
as `state.review_queue`; a missing shard manifest means an empty queue. The configuration defaults
to registered `settings.exam_config`. Availability and the current route come from their optional
workspace registrations and use M26/M11 loaders.

Only `queued` or `scheduled` items with `due_date < D` are replanned, using the same
`overdue_review_items()` predicate as `assess_freeze`. When `(D - due_date).days` is greater than
the current schedule interval, the item is in the possible-forgetting tier and its schedule is
reset with M10 `reset_for_relearning`; equality stays in the recent-overdue tier. Each tier sorts
by old due date and then `review_id`; possible-forgetting items go first.

Starting at D, each item takes the earliest day with enough remaining ordinary review capacity.
M8 stage quotas are independent per subject. On days outside a route phase, the shared capacity is
`scale_minutes(resolved daily minutes, review_reserve_ratio)`. Already queued, non-overdue items due
that day consume capacity first. A placed item's `due_date` changes and `defer_count` resets to 0.
An overdue scheduled item changes to `queued` without changing `revision`; other item fields
remain unchanged. The plan asserts that no schedule interval increases. Search
covers at most 366 days; an item that cannot fit in that horizon is assigned to D and listed in
`unschedulable_review_ids` so M9 can prompt the learner to split it.

`resume_plan_to_mapping()` is the sole JSON/YAML plan shape. If at least one scheduled item is
planned for conversion, the mapping adds `scheduled_to_queued_count`, the number converted in
this plan; the resume event stores that same plan mapping. Otherwise this field is absent. Human
output distinguishes planned conversion from completed conversion. `--dry-run` prints that plan without
writing. If an unresolved freeze event is dated after D, a resume on D could not clear it, so the
command (dry run included) exits 2 with “冻结发生在 <日期>，恢复日期不能早于它” before writing the
queue or any event (sol round 125). With no overdue items and no active latch the command prints
“没有需要重排的积压”, exits successfully and writes nothing. With no overdue items but an active
latch (the learner caught up while frozen, or an earlier run wrote the queue but not its record), a real run writes only the
resume event with the empty plan and prints “积压已清空，已解除冻结”; a dry run prints that the real
run would lift it. Otherwise a real run writes the complete queue through
`ReviewShardStore.write`, then appends a globally sequenced resume event through
`DayPlanStore.write_resume_record`; that event
clears earlier freeze latches on D or earlier. A second run on the same date with no latch and no
overdue items does not write an event. Existing unproven schema-1 history is rejected by the
queue writer. Multiple runs may write multiple same-day resume events when a later freeze occurs.

The queue commit precedes the audit record so the latch is not cleared before the queue is safely
replaced. If audit writing fails after the queue commit, the replanned queue remains, but an older
freeze latch may remain active; this storage API has no transaction spanning the two stores. The
failure is reported; running `ky resume` again then finds nothing overdue and, because the latch is
still active, writes the missing resume record.
