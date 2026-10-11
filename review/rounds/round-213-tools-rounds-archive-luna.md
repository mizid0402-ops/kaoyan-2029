# Round 213 — tools rounds archive and fixed paths

## Files and status

| Before | After | Status |
|---|---|---|
| `tools/round22_extract.py` | `tools/archive/round22_extract.py` | `pinned_reproducer`; replay wrapper imports extraction helpers from `tools/cs408_outline_extract.py` |
| `tools/round24_build_weighted_tree.py` | `tools/archive/round24_build_weighted_tree.py` | `pinned_reproducer`; imports outline extraction helpers from the active module |
| `tools/round29_build_tree_split.py` | `tools/archive/round29_build_tree_split.py` | `pinned_reproducer`; its historical dependency remains in archive and quote location comes from the active helper |
| `tools/round29_quote_locate.py` | `tools/archive/round29_quote_locate.py` | `pinned_reproducer` entrypoint; imports active quote-location functions |
| `tools/round24_validate_weighted_tree.py` | `tools/validate_weighted_tree.py` | `validation` |
| `tools/round29_validate_agreement.py` | `tools/validate_supplementary_agreement.py` | `validation` |
| shared round22 functions | `tools/cs408_outline_extract.py` | `active`, M4 outline extraction and normalization |
| shared round29 quote functions | `tools/cs408_quote_locate.py` | `active`, M4 verbatim quote location |

The new functional names distinguish normalization/extraction from quote matching. Both helpers document M4, their contract, and public interfaces. No compatibility stubs remain under the former active filenames.

## Dependency graph after the move

```text
cs408_outline_extract ──> cs408_quote_locate
          │                         │
          ├──> validate_weighted_tree
          └──> archived round22/24/29 replay scripts
                                    └──> archived round29 split builder
validate_supplementary_agreement ──> workspace-registered supplementary tree/agreement
```

The round29 historical builder still imports the archived round24 generator because it reuses its historical alignment engine. Active top-level `tools/` and `ky/` code does not import the archive.

## Fixed path handling

| Path/use | Handling |
|---|---|
| Outline extraction library | Input paths are explicit function arguments (`extract_2022(pdf_path)`, `extract_2026(html_path)`, `tree_reverse_check(data, tree_path)`). No machine cache or machine-specific output path remains in the active module. |
| Weighted-tree validator | The weighted tree is a required `--tree` CLI argument because it has no `kaoyan.workspace.yaml` registry key. Baseline tree comes from the workspace registry; source B comes from the weighted tree's `sources_registry` record. |
| Supplementary-agreement validator | Tree and agreement paths come from `supplementary.cs408_multisource.files` via `load_workspace`. |
| Archived round22/24 scripts | Original machine-specific scratch paths are retained as historical replay details. They are not active defaults. |
| `tools/migrations/register_round2_sources.py` | Original machine-specific attachment path is retained; its README row now identifies this as a historical migration. |

The current materials ledger records the 2022 CS408 book as `remote_reference`, not a local file, and does not register the historical question-bank JSON. Therefore those historical raw files cannot be resolved as local paths from `data/materials.yaml`; no new registration was invented. Tests that require those files use the existing `tests._resources.require_path` behavior.

## README and source checks

`tools/README.md` now catalogs the two active helpers, the renamed validators, and the archived scripts. It marks the weighted validator as validation of the historical artifact, describes the active dependency graph, and notes the preserved archive/migration paths.

The fixed-commit assertion in `tests/test_cs408_lecture_pipeline.py:89` was exercised by the acceptance command and still passes. Its source remains pinned to the historical commit, independent of the active script relocation.

`git grep -n -E 'round[0-9]{2}_|round2[249]_' -- tools/*.py ky` returned only archive paths:

```text
tools/archive/round22_format.py:11:DATA = Path(r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\round22_results.json")
tools/archive/round22_format.py:12:OUT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\round22_lists.md")
tools/archive/round22_probe.py:43:    (TMP / "round22_raw_lines.txt").write_text("\n".join(raw_lines), encoding="utf-8")
tools/archive/round22_verify.py:10:from round22_extract import PDF
tools/archive/round22_verify.py:14:OUT = Path(r"C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\round22_verify.txt")
```

`git grep -n -E 'tools/archive|archive import' -- tools/*.py ky` returned only usage strings in already archived scripts. Excluding `tools/archive/**`, both searches have no hits in active `tools/` and `ky/` code.

## Output comparison

The one-off comparison used `tests/_baseline_harness.py` and fixed baseline `ab56529` (resolved commit `ab56529b3fa90244f4febe305338e5414ef197b3`). The harness asserted old source identity before execution. Raw UTF-8 JSON bytes matched for `key`, `clean_display`, and `subject_chunks` sample outputs. The validators' serialized error lists matched byte-for-byte against the same committed weighted-tree and agreement inputs.

Source-backed full PDF/HTML extraction and quote-location replay were not run because the registered local historical source files are absent. The targeted tests skipped those cases through `require_path`; the comparison establishes helper and validator equivalence only, not full raw-source replay equivalence.

Comparison result:

```text
PASS: outline helpers, weighted validator, and agreement validator outputs match baseline bytes
```

## Acceptance output

Command:

```text
py -3.12 -m unittest tests.test_tools_catalog tests.test_round24_weighted_tree tests.test_round29_quote_locate tests.test_round29_tree_split tests.test_cs408_lecture_pipeline tests.test_tool_exit_paths
```

Result:

```text
Ran 50 tests in 35.620s
OK (skipped=5)
```

All five skips were source-dependent checks where registered historical raw files were not present locally.

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）
