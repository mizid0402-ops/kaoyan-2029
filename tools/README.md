# Framework tools

Reusable tools are listed below. Historical one-off migrations, audit replays and
agent dispatch scripts stay in the private development workspace.
Most tools need user-provided local source data; the default public demo contains none.

## Script catalog

| Script | Status | Module | Input | Writes | Usage and prerequisites |
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

## Reconstruction dependency graph

`cs408_outline_extract` and `cs408_quote_locate` provide reusable parsing helpers.
Validators consume registered local inputs. Builders produce outputs only after
their own data and path checks; registration does not grant redistribution rights.

Start from the root README and the relevant `contracts/` specification.
Real materials and historical process outputs are not part of the public demo.
