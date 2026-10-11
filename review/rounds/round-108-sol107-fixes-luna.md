# Round 108: sol 107 WP-E4 Fix Report

## Changes

- **F1 / M26:** `ky/availability/port.py` rejects non-string top-level keys before sorting unknown
  keys. The `ContractError` path is the string form of the offending key. Mixed YAML key types no
  longer trigger cross-type comparison errors.
- **C1 / M8 and M19:** `ky/schedule/budget.py` adds `floor_policy`, defaulting to `strict`. Strict
  mode keeps the existing floor-conflict `ValueError`. `drop_when_short` waives all floors only
  when their sum exceeds the budget, proportionally allocates the full budget with the existing
  largest-remainder split, and reports zero applied `floor_minutes`. `ky/__main__.py` and
  `ky/planner/port.py` pass this policy only when the day's source is `availability`.
- **C2 / M9:** `ky/schedule/review_clip.py` uses `config.review_hard_cap_minutes()` to decide
  whether an item itself needs splitting. A smaller hand-entered daily limit defers an otherwise
  schedulable item for that day. The function docstring and contract record this rule.
- **T1:** The preflight text `daily budget` line now prints the resolved daily minutes. The
  contract test asserts that a hand-entered 60-minute day prints 60 and compares the no-override
  text stdout and stderr byte-for-byte with fixed baseline
  `79623ee630c49c74944413f43dab0032516c88c0`. The contract also documents upward registry
  discovery and exit status 2 when discovery finds an invalid registry.
- The policy and rationale are recorded in `contracts/availability.md`. Tests were added only to
  `tests/contract/test_availability_port.py`.

## Revert checks

For each item, I temporarily restored the corresponding faulty behavior, ran the focused test, and
restored the fix:

- **F1:** Restoring `sorted(...)` over mixed keys made
  `test_mixed_top_level_keys_are_contract_errors_in_preflight` fail with `TypeError`.
- **C1:** Forcing `drop_when_short` through the strict error branch made
  `test_short_availability_budget_drops_floors_in_preflight_and_input` fail for both hand-entered
  values, 0 and 30, because preflight exited 1.
- **C2:** Comparing item cost against the overridden daily hard cap made
  `test_zero_availability_defers_fit_items_but_keeps_oversized_unschedulable` fail because due
  items no longer entered `deferred`.
- **T1:** Printing configured minutes instead of resolved minutes made
  `test_preflight_uses_override_and_config_only_output_matches_baseline` fail: the 60-minute
  override displayed the configured 120 minutes.

## Acceptance

The requested command passed:

```text
py -3.12 -m unittest tests.contract.test_availability_port tests.test_review_scheduler tests.test_contracts tests.contract.test_planner_port tests.test_cli
Ran 182 tests in 23.456s
OK
```

After strengthening the C2 deferral-state and C1 below-floor assertions, the affected module was
rerun:

```text
py -3.12 -m unittest tests.contract.test_availability_port
Ran 11 tests in 3.450s
OK
```

`git diff --check` passed. No changed file has a repeated question-mark corruption marker. Full
suite: not run, per `AGENTS.md`; the decision maker runs it once before commit. No commit was
created.

## Recommendation

The T1 recommendation from sol round 107 was adopted. The hand-entered text display and fixed
no-override output baseline are covered. No further recommendation.
