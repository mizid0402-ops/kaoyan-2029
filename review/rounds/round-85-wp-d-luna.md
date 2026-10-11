# Round 85 — WP-D vocabulary delivery state migration

## Changed files

- `ky/storage/day_plan_store.py`
- `ky/schedule/vocab_channel.py`
- `ky/schedule/state_snapshot.py`
- `tools/migrate_vocab_delivery.py` (new)
- `tools/daily_words.py`
- `contracts/vocabulary.md`
- `contracts/state_snapshot.md`
- `docs/模块地图.md`
- `docs/阶段2.5-接缝收口.md`
- `tests/test_day_plan_store.py`
- `tests/contract/test_vocabulary_port.py`
- `tests/test_migrate_vocab_delivery.py` (new)
- `tests/test_eng1_vocabulary.py`
- `tests/contract/test_state_snapshot_port.py`
- `tests/test_monthly_close.py` (updated its migration-reader caller)
- `review/rounds/round-85-wp-d-luna.md` (this report)

## Design placement

1. **M13 truth source:** `DayPlanStore.delivered_words()` reads stored completion events and
   returns the `word_form` union from `vocab.delivered_words`. Missing plan directories return an
   empty set. No second state file was added.
2. **One-time migration:** `import_delivery_baseline_with_dates()` is read-only and returns dated
   word forms. `tools/migrate_vocab_delivery.py` groups them by date, keeps their delivery order,
   writes `reviews: []` events only with `--apply`, and refuses every occupied date before writing
   any event. Its destination is `workspace.plans`, without `require()`.
3. **M7 reader:** `remaining_pool` and `preview_batch` accept `delivered`, defaulting to an empty
   set. Both filter by `word_form`; ordinary reads no longer inspect `delivery_log`. The old
   undated baseline reader and `_legacy_delivered_word_ids` were removed.
4. **M12 snapshot:** `delivered` is the unique state-store word-form count; `remaining` is computed
   from the same set. With no workspace/state store, or an absent `state.plans` directory, the
   delivered set is empty. An explicitly missing vocabulary override still gives `vocab: null`;
   a missing registered vocabulary file still fails through `Workspace.require`.
5. **Daily tool:** the reference database opens with SQLite `mode=ro`; its default path comes from
   `reference.vocabulary_db`, with hidden `--db` retained. It excludes stored word families using
   the existing `lemma_confidence == "rule"` grouping rule and appends a pasteable
   `vocab.delivered_words` YAML fragment. It records nothing, so rerunning before a completion
   event is saved returns the same batch.

`tools/build_eng1_vocabulary.py` still creates an empty `delivery_log` table, and
`tools/verify_eng1_vocabulary.py` still requires that table to exist. Neither has a row-level
delivery write; both files were left unchanged as requested.

## Removed user-visible behavior

- Removed the `--reset` option from `tools/daily_words.py` and its `delivery_log reset` confirmation.
- Kept the “已投递完，剩余 N 个” pool-exhaustion hint. The YAML completion fragment is the permitted
  new stdout text.

## Fixed-baseline comparison and immutability

The regression test retrieves `tools/daily_words.py` from commit `162a9e1`, verifies its Git blob
hash, and runs it against a temporary reference copy seeded with the same delivered forms. The new
tool runs against a matching copy with an empty `delivery_log` and those forms in temporary
completion state. For default output, `--show-evidence`, and `--include-stopwords`, the stdout bytes
before the newly appended YAML fragment compare equal. The appended fragment is parsed as YAML.
The SHA-256 of each new-tool reference copy is checked unchanged before and after execution.

The real reference database SHA-256 was:

| Check | SHA-256 |
|---|---|
| Before real-workspace dry-run | `839D48BE37D7716B1A12DA04E3E2293868EE379B6E09A13DD198DAE5498D0E2C` |
| After real-workspace dry-run | `839D48BE37D7716B1A12DA04E3E2293868EE379B6E09A13DD198DAE5498D0E2C` |

## Real-workspace migration dry-run

Command: `py -3.12 tools/migrate_vocab_delivery.py`

```text
DRY RUN: 1 completion event(s)
2026-09-13: 15 word(s)
No state was written. Use --apply after review.
```

The count and date above are from the current read-only `delivery_log`. No `--apply` was run on
the repository's real `state.plans`.

## Acceptance

Ran the exact task-book command:

```text
py -3.12 -m unittest tests.contract.test_vocabulary_port tests.test_day_plan_store tests.test_migrate_vocab_delivery tests.test_eng1_vocabulary tests.contract.test_state_snapshot_port tests.test_state_snapshot tests.test_monthly_close
```

Result: 87 tests ran; 86 passed. The single failure is the pre-existing
`test_verifier_deterministic_check_and_mutations` environment failure: the builder cannot find
`%TEMP%\kaoyan-probe\claude2\dl\bv_e1_2024.pdf`, as noted in the task book. The fixed-baseline
comparison, migration, M13 store, vocabulary port, and snapshot assertions passed.

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。

## Suggestions

- After review, the decision maker can run the migration tool with `--apply` against the real
  workspace. It will still refuse to merge or overwrite any date that already has a completion
  event.
