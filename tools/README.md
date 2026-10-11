# Tools catalog and reconstruction guide

This catalog describes the tracked Python scripts directly under `tools/`, plus the scripts in
`tools/migrations/` and `tools/archive/`. `tools/dispatch/` is listed separately as M20 developer
workflow tooling; it is excluded from the data-tool catalog. `__pycache__` is generated output.

## Script catalog

| Script | Status | Module | Input | Writes | When to run; rerun range and prerequisites |
| --- | --- | --- | --- | --- | --- |
| `tools/aggregate_topic_weights.py` | active | M6 | Registered weight batches, coder outputs, trees | Registered topic weights when `--write` | Recompute/check M6 weights; rerunnable from all registered batches and source files. |
| `tools/apply_knowledge_weights.py` | active | M6 | Topic weights and registered exam indexes | Exam-index assignment fields | Apply the current reviewed mapping; rerun after the registered mapping changes. |
| `tools/render_weight_manual.py` | active | M6 | Topic weights and workspace metadata | Markdown manual at `--out` | Refresh the human-readable weight guide; needs a valid workspace and weights. |
| `tools/classify_questions.py` | active | M6 | Exam PDF, question map, and tree | Candidate question-to-node map at `--out` (`year` / `paper` / `questions` / `rows`) | Helper for coders only: its output is **not** a coder document (`contracts/topic_weights.md` requires `meta` + `entries`) and cannot be aggregated as is. Requires the PDF and the selected tree. |
| `tools/verify_408_index.py` | validation | M5 | Registered 408 index files and paper-shape data | None | Validate current 408 indexes after registration or edits; needs registered files. |
| `tools/verify_tree.py` | validation | M4 | Knowledge-tree YAML and optional workspace | None | Check a tree, sources, or scopes; rerunnable when the tree and cited materials exist. |
| `tools/tree_source_support.py` | validation | M4 | CS408 tree and source evidence | None | Calculate source support for current tree review; needs referenced local sources. |
| `tools/cs408_outline_extract.py` | active | M4 | Explicit source PDF/HTML/tree paths | Extracted and normalized outline structures | Reusable extraction and normalization library; callers supply paths because historical inputs are not registered as local files. |
| `tools/cs408_quote_locate.py` | active | M4 | CS408 source text and quote candidates | Verbatim quote locations | Reusable keymap locator; human review remains required. |
| `tools/validate_weighted_tree.py` | validation | M4 | `--tree` weighted tree and its source B path | None | Validate the historical weighted artifact; raw-source provenance validation reads the source B path recorded in the artifact. |
| `tools/validate_supplementary_agreement.py` | validation | M4 | Registered supplementary tree and agreement | None | Validate current registered supplementary files. |
| `tools/archive/round22_extract.py` | archived | M4 | Fixed 2022 PDF, 2026 HTML, current tree | Historical comparison JSON at `C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\round22_results.json` | Historical replay only; its machine-specific path is preserved from the original script. |
| `tools/archive/round24_build_weighted_tree.py` | archived | M4 | Fixed CS408 sources and prior comparison | Historical weighted tree | Historical replay only; machine-specific temp paths are preserved unchanged. |
| `tools/archive/round29_build_tree_split.py` | archived | M4 | Fixed 2022/2026 CS408 sources and round24 artifacts | Supplementary tree and agreement artifacts | Historical replay only; depends on the archived round24 generator and active helper libraries. |
| `tools/archive/round29_quote_locate.py` | archived | M4 | Fixed CS408 outline and quote candidates | Quote-location results | Historical replay only; replaced for active reuse by `cs408_quote_locate.py`. |
| `tools/daily_words.py` | active | M7 | Vocabulary database and workspace state | Optional delivery/completion state via its CLI | Daily vocabulary use; requires the registered database and valid state store. |
| `tools/build_eng1_vocabulary.py` | pinned_reproducer | M7 | Six local English-I vocabulary PDFs | Vocabulary SQLite database | Rebuild the currently supported source set; all PDFs and expected hashes must be available. |
| `tools/verify_eng1_vocabulary.py` | validation | M7 | Vocabulary database | None (mutation mode is an explicit test operation) | Verify database integrity; requires the database and its registered sources. |
| `tools/import_netem_source.py` | active | M7 | NETEM raw JSON and retrieval date | Registered NETEM source rows and output artifact | Import a newly reviewed source snapshot; requires its source record and database. |
| `tools/verify_netem_source.py` | validation | M7 | NETEM source database | None (mutation mode is an explicit test operation) | Verify NETEM source integrity after import; requires the database. |
| `tools/netem_cross_validate.py` | validation | M7 | NETEM database and exam-derived vocabulary | Cross-validation report at `--out` | Compare independent vocabulary sources; requires both current datasets. |
| `tools/build_408_deck_scaffold.py` | active | M21 | Workspace tree bundle, indexes, and question materials | Ignored `deck/` scaffold files | Build or refresh 408 lesson scaffolds; requires registered bundle inputs and local output directory. |
| `tools/extract_cs408_bundle.py` | active | M21 | Supplementary tree, agreement, and 408 indexes | Bundle files under its configured output | Prepare M21 source bundle; independent of projection, requires all three inputs. |
| `tools/extract_408_question_text.py` | active | M21 | Registered 408 paper PDF | Extracted question text under configured output | Extract text from supported 408 PDFs; requires local PDFs and output permissions. |
| `tools/extract_408_questions_from_html.py` | active | M21 | HTML question source | Extracted question data | Parse an available HTML source; requires a compatible page snapshot. |
| `tools/verify_408_question_extraction.py` | validation | M21 | Extracted questions and source records | None | Verify M21 extraction after changes; requires extracted data and source evidence. |
| `tools/fetch_evidence.py` | acquisition | M1 | URL list | Evidence cache and index | Fetch explicitly selected permitted URLs; network and valid URL list required. It does not restore all raw materials from the ledger. |
| `tools/fetch_all_from_ledger.py` | acquisition | M1 | Registered ledger `local_file` rows | Missing raw-material files only, after exact size and SHA-256 checks | Restore missing verifiable bytes from each row's `storage.url`; `--check` is offline. Existing files are never replaced; remote references only appear in the report. See `contracts/material_restore.md`. |
| `tools/probe_exam_pdf.py` | acquisition | M1/M5 | Candidate PDF URL | Downloaded candidate PDF and probe report | Inspect an explicitly selected candidate; network and source review required. |
| `tools/probe_outline.py` | validation | M4 | Outline transcription | Printed feature counts | Compare a supplied transcription with anchors; input file required. |
| `tools/probe_pdf_text.py` | validation | M1 | PDF files in `--dir` | Printed text-layer report | Diagnose local PDFs; input directory and optional image dependencies required. |
| `tools/render_pdf_pages.py` | acquisition | M1 | Scanned PDF | Extracted page images in cache | Extract selected embedded page images; local PDF required. |
| `tools/render_staged_page.py` | acquisition | M1 | Staged PDF and page number | Page images in cache | Inspect a staged PDF page; local PDF and valid page required. |
| `tools/extract_exam_skeleton.py` | validation | M5 | Text-layer exam PDF | Optional JSON skeleton at `--json` | Inspect 408-style question structure; text layer and human format review required. |
| `tools/list_tree_vocab.py` | validation | M4/M6 | Current CS408 effective tree | Printed item vocabulary | Prepare classification patterns for the current CS408 tree; not generic across registered trees. |
| `tools/mutation_test_408_index.py` | validation | M22 | 408 index verifier and temporary fixtures | Temporary mutated copies only | Prove the verifier rejects bad indexes; run as a test tool with writable temp storage. |
| `tools/mutation_test_knowledge_weights.py` | validation | M22 | Weight verifier and temporary fixtures | Temporary mutated copies only | Prove weight validation rejects mutations; requires test dependencies. |
| `tools/mutation_test_suite.py` | validation | M22 | Tree-integrity tests and temporary fixtures | Temporary mutated copies only | Prove selected contract tests fail under mutation; requires test dependencies. |
| `tools/mutation_test_verify_tree.py` | validation | M22 | Tree verifier and temporary fixtures | Temporary mutated copies only | Prove tree validation rejects malformed trees; requires test dependencies. |
| `tools/migrations/apply_round2_fixes.py` | migration | M2 | Fixed round-2 ledger inputs and hash guards | Material ledger and related records | Historical one-time migration/check; only run against the intended fixture/state after reviewing its guard. |
| `tools/migrations/fix_eng1_provenance.py` | migration | M2/M3 | Fixed English-I source evidence and ledger | Material ledger and registered source records | Historical one-time provenance correction; requires the pinned source bytes and reviewed ledger. |
| `tools/migrations/register_round2_sources.py` | migration | M2 | Fixed round-2 source files and ledger | Material ledger | Historical registration/check only; not a general source-registration command. Its original machine-specific attachment path is preserved. |
| `tools/migrations/register_408_source.py` | migration | M2/M5 | Fixed 2024 408 source files and ledger | Material ledger and source files | Historical 2024 registration/check only; not for 2027. |
| `tools/migrations/register_408_quiz_pages.py` | migration | M2/M5 | Fixed 2023–2026 quiz-page evidence | Material ledger and source files | Historical page registration/check only; not a 2027 registrar. |
| `tools/migrations/remove_408_reprints.py` | migration | M2 | Fixed reprint records and files | Ledger and selected files | Historical removal/check; only replay with the exact pinned state and explicit review. |
| `tools/migrations/restore_408_papers.py` | migration | M2/M5 | Fixed 408 paper rows and source bytes | Ledger and paper files | Historical restoration/check; requires the exact source files and reviewed target state. |
| `tools/archive/build_408_index.py` | archived | M5 | Fixed 2024 source facts | 2024 index JSON | Superseded by v2 because its essay marks are distributed incorrectly; historical replay only. |
| `tools/archive/migrate_vocab_delivery.py` | retired | M7/M13 | Vocabulary `delivery_log` and workspace state | Completion events/state files with `--apply` | Retired, never executed, and explicitly declined migration. **Never run `--apply` against real state.** |
| `tools/archive/audit_attachment.py` | archived | M22 | Fetched attachment evidence index | Timestamped audit report under `review/` | Replay the fixed attachment audit; requires the historical evidence cache. |
| `tools/archive/build_evidence_bundle.py` | archived | M22 | Fixed attachment audit evidence | Self-contained review bundle | Replay only with the historical attachment inputs; no network fetch. |
| `tools/archive/verify_evidence_bundle.py` | archived | M22 | Historical evidence bundle | None | Verify an existing historical bundle; requires that bundle. |
| `tools/archive/verify_round3_findings.py` | archived | M22 | Fixed round-3 claims and repository state | None | Historical independent review check; use only for its original findings. |
| `tools/archive/inspect_repos.py` | archived | M22 | Cached repository metadata | Printed inspection | Inspect only the existing local cache; does not query the network. |
| `tools/archive/probe_quiz_page.py` | archived | M1/M5 | Cached 2023–2026 quiz-page evidence | Optional JSON and probe artifacts | Historical page probe; requires cache and supported page formats. |
| `tools/archive/round22_format.py` | archived | M4 | Fixed round22 comparison JSON | Markdown comparison in local probe temp path | Historical formatting replay; requires round22 output and the original temp location. |
| `tools/archive/round22_probe.py` | archived | M4 | Fixed 2022/2026 outlines and local tree | Historical comparison probe files | Replay only with original inputs and temp paths. |
| `tools/archive/round22_verify.py` | archived | M4 | Fixed 2022/2026 outline sources | Verification report in local probe temp path | Historical verification only; requires the original source and temp paths. |
| `tools/archive/audit_round6.py` | archived | M4 | Fixed 2026 outline and round6 tree | Printed audit / temporary comparison | Historical source audit only. |
| `tools/archive/generate_tree_round6.py` | archived | M4 | Fixed 2026 CS408 outline HTML | **Writes straight to the registered** `data/structured_materials/cs408/knowledge_tree.yaml` | Historical generator of the round-6 base tree. Its output is **not** the registered tree (checked 2026-09-27: 255,213 vs 291,692 bytes; the registered file has a header and later `scope` / `frequency` / status-transition / `supersedes` fields). **Never run it against the repository**; replay only in a temporary copy. |
| `tools/archive/build_408_index_v2.py` | archived | M5 | Registered 408 source facts for 2023–2026 (`--year` accepts only these) | Index JSON; **defaults to the registered** `data/exam_questions/408_index_<year>.json` | Historical generator of the 408 base indexes. Its output differs from all four registered indexes (checked 2026-09-27 with `--out` to a temp file; the registered files carry `knowledge_point_weights` written later by `apply_knowledge_weights.py`). **Never run it without `--out` pointing outside the repository.** |
| `tools/archive/build_exam_indexes.py` | archived | M5 | Hard-coded Math I (2023–2026) and English I (2024–2026) sources and answer tables | **Always writes the registered** `data/exam_questions/<subject>_index_<year>.json` (no `--out`) | Historical generator of the Math I / English I base indexes; the registered files carry `knowledge_point_weights` written later. **Never run it in the repository.** |
| `tools/archive/build_math1_tree.py` | archived | M4 | Two registered Math I transcripts | Math I tree/report with `--write` (registered path) | Historical generator of the Math I base tree. The dry run (no `--write`) prints a SHA-256 that differs from the registered tree (checked 2026-09-27), so **never use `--write`** on the repository. Since 2026-10-02 `--write` refuses when the registered tree exists (it only knows the old 69 nodes; the tree now has the 123 requirement items). |
| `tools/archive/build_eng1_tree.py` | archived | M4 | English I transcript and registered contents page | English I tree/report with `--write` (registered path) | Historical generator of the English I structure tree; same situation as the Math I builder: the dry-run hash differs from the registered tree, **never use `--write`** on the repository. |

Run the current CS408 validators from the repository root:

```powershell
py -3.12 tools/validate_weighted_tree.py --tree data/structured_materials/cs408/knowledge_tree_weighted.yaml
py -3.12 tools/validate_supplementary_agreement.py
```

The weighted-tree validator requires `--tree`; provide the weighted-tree file to validate.

The catalog is checked bidirectionally by `tests.test_tools_catalog`: every listed path must exist,
and every direct `.py` file in these three catalog directories must have one row.

## Reconstruction dependency graph

The active CS408 helpers are `cs408_outline_extract.py` and
`cs408_quote_locate.py`. Current validators import those helpers as needed;
archived round scripts may depend on archived generators, while no active
`tools/` or `ky/` module imports from `tools/archive/`.

```text
cs408_outline_extract ──> cs408_quote_locate
          │                         │
          ├──> validate_weighted_tree
          └──> archived round22/24/29 replay scripts
                                    └──> archived round29 split builder
validate_supplementary_agreement ──> registered supplementary tree/agreement
```

The arrows describe data prerequisites. The two middle branches can be prepared independently after
source confirmation; M21 is a separate output branch and does not consume the projection.

```text
source confirmation and ledger registration
  ├─> effective and supplementary trees ─┐
  └─> paper shape and exam indexes ──────┴─> coding batches and topic weights ─> projection
                 supplementary tree + agreement + 408 index ────────────────> M21 lesson bundle
```

1. **Confirm/register sources (M1–M3).** Fetch a specifically reviewed URL with
   `py -3.12 tools/fetch_evidence.py <url-list> --out <cache-dir> --index <index.json>`, then
   review and register source records through the applicable M2/M3 workflow. To inspect all
   registered local bytes offline, run `py -3.12 tools/fetch_all_from_ledger.py --check`; omit
   `--check` to attempt restoration of missing `local_file` bytes from their recorded storage
   URLs. The latter only publishes exact size and SHA-256 matches; remote references and changed
   source bytes require human review. Historical migration scripts above are pinned to old
   sources and are not a general registrar.
2. **Check trees and paper indexes (M4/M5).** The registered trees and exam indexes are the source
   of truth and **cannot be rebuilt by any script**: each carries edits made after its generator
   ran (see the five archived builders above). Verify them instead:
   `py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml --workspace kaoyan.workspace.yaml`
   (one tree per run) and `py -3.12 tools/verify_408_index.py --workspace kaoyan.workspace.yaml`
   (the registered 408 indexes). A new year's paper is added by M5 registration (paper shape,
   index file, registry line; see `contracts/paper_shape.md` and `contracts/exam_index.md`),
   not by rerunning an archived builder.
3. **Prepare coding batches and weights (M6).** A batch is one independent coder document per
   coder registered in `data/review_weights/batches.yaml` (currently three; `meta` + `entries`,
   see `contracts/topic_weights.md`) plus one `batches` entry in that file. **No script produces the
   coder documents**: they are written by the coders (people or models) and reviewed; the helper
   `py -3.12 tools/classify_questions.py --pdf <paper.pdf> --year <year> --out <candidates.json> --workspace kaoyan.workspace.yaml`
   only writes a candidate map a coder may consult. Aggregate the registered batches with `py -3.12 tools/aggregate_topic_weights.py --check`
   (add `--write` only for an intentional update of the registered weights). Apply the mapping
   to the registered indexes with `py -3.12 tools/apply_knowledge_weights.py --check` first;
   without `--check` it **writes the registered index files**. Then rerun the step-2 verifiers.
4. **Build projection (M15).** Once effective trees, supplementary tree/agreement, registered
   exam indexes, weights, vocabulary database, and workspace registry entries are complete, run
   `py -3.12 -m ky.projection`. The required registry inputs are specified in
   `contracts/projection.md`; the projection writes only its registered SQLite target.
5. **Build M21 independently.** After the supplementary tree, agreement, and 408 index are ready,
   `py -3.12 tools/extract_cs408_bundle.py --workspace kaoyan.workspace.yaml` builds the lesson
   input bundle, and `py -3.12 tools/build_408_deck_scaffold.py --workspace kaoyan.workspace.yaml`
   builds the deck scaffold under the registered (git-ignored) product directory. This branch
   does not require or read the M15 projection.

## Current gaps and limits

- No script reproduces the registered exam indexes. The archived 408 v2 builder accepts only
  2023–2026 (`--year 2027` is rejected) and `build_exam_indexes.py` hard-codes Math I 2023–2026
  and English I 2024–2026 paths and answer tables; both write the registered index paths by default. New 2027 papers go through
  M5 source confirmation, paper-shape registration, indexing, and validation.
- There is no general builder for a newly published syllabus, and no script reproduces any of the
  three registered trees (CS408, Math I, English I): the archived generators only produce the
  base trees they started from, and they write to the registered paths. A new syllabus version is
  added by the M4 / M25 registration flow, not by rerunning an old generator.
- `fetch_all_from_ledger.py` visits every ledger row, but can restore only missing `local_file`
  bytes with a usable storage URL that still serves the registered exact bytes. It cannot
  recover `remote_reference` content or bytes that have no direct storage URL (including
  user-supplied or purchased copies when no such URL is registered).
- `tools/migrations/` and `tools/archive/` are physical organization only. The C2
  `tools/pipeline/` split was **not done**: current generator paths and documented commands are
  compatibility surfaces, and the generator identities/ports are not yet stable enough to move
  that entry layer.
- `tools/archive/migrate_vocab_delivery.py` is retired. Running `--apply` against real state is
  prohibited because the user decided not to migrate the existing vocabulary delivery rows.
- Round22/24/29 tools replay fixed historical inputs, and timestamped outputs or deleted local
  caches prevent a claim of general, byte-identical reconstruction.

## Excluded tools

`tools/dispatch/` contains the M20 developer dispatch scripts. They do not build or validate
learning data and are intentionally outside the per-script data-tool catalog.
