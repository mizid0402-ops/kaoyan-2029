# Projection contract (schema version 5)

The SQLite projection is a read-only, rebuildable view of the workspace inputs. It is not a
source of truth and does not prescribe study priorities or recommendations. In particular,
`DoesNotPrescribeTest` remains a constraint: counts and weights are descriptive input data and
must not be interpreted as an instruction about what a learner should study.

## Inputs and precedence

`build_projection(workspace, out=None)` receives a loaded `Workspace`; the library function never
discovers a registry. It requires and reads exactly:

| Registry field | Use |
|---|---|
| `reference.knowledge_trees.<subject>` | Effective tree for that subject. |
| `supplementary.<name>.files.tree` | Each registered `cross_year_tree` supplementary tree. |
| `supplementary.<name>.files.agreement` | Per-node attributes for that supplementary tree. |
| `reference.exam_indexes.<subject>[]` | Only the explicitly registered index files; directories are never globbed. |
| `reference.topic_weights` | Topic weight JSON. |
| `reference.vocabulary_db` | Required vocabulary input dependency; its content is fingerprinted. |

The workspace registry is the source of defaults. There are no path constants in the projection
module. `out` explicitly overrides `workspace.projection`; without it, the registry's projection
target is used. CLI discovery follows `contracts/workspace.md` §3.1 (`--workspace`,
`KY_WORKSPACE`, then upward search). Once an explicit source is selected, failure does not fall
back. All registered inputs are resolved with `Workspace.require()` or `require_all()`.

The effective trees are parsed by `ky.knowledge.load_knowledge_points`. Agreement YAML is read
with the strict `ky.models` YAML reader, which rejects repeated mapping keys. Every registered
input must exist as a file and resolve inside the workspace. Failure raises `ContractError` (or
`KnowledgePointError` for a malformed knowledge tree). Inputs are validated before output is
created, and a completed temporary database replaces the old file atomically; an input failure
leaves the prior projection byte-for-byte unchanged.

## Effective and supplementary knowledge

`knowledge_points` contains only nodes from `reference.knowledge_trees`. Its `tree_source` is the
registry key `reference.knowledge_trees.<subject>`. The table does not contain
`source_support`, `source_count`, or `evidence_tag`.

Each `cross_year_tree` produces one `supplementary_views` row and all its nodes in
`supplementary_knowledge_points`. The supplementary tree must include every effective ID for its
subject, and agreement IDs must exactly equal supplementary tree IDs. Agreement attributes are
stored only alongside the supplementary nodes. `is_effective` is 1 when a node ID is present in
the same subject's effective tree, otherwise 0. For this repository, that means 403 effective
CS408 nodes and 410 supplementary rows, of which 7 are not effective.

| Table | Columns |
|---|---|
| `knowledge_points` | `knowledge_point_id TEXT PK`, `subject_id TEXT`, `domain TEXT NULL`, `scope TEXT`, `title TEXT NULL`, `parent_id TEXT NULL` (按 `contracts/knowledge_tree.md` 层级定义), `depth INTEGER`（ID 点分段数 − 1，不是沿 `parent_id` 到根的边数）, `tree_status TEXT`, `tree_source TEXT` |
| `supplementary_views` | `view_name TEXT PK`, `kind TEXT`, `subject_id TEXT`, `description TEXT` |
| `supplementary_knowledge_points` | `view_name TEXT`, `knowledge_point_id TEXT`, `subject_id TEXT`, `domain TEXT NULL`, `scope TEXT`, `title TEXT NULL`, `parent_id TEXT NULL` (按 `contracts/knowledge_tree.md` 层级定义), `depth INTEGER`（ID 点分段数 − 1，不是沿 `parent_id` 到根的边数）, `tree_status TEXT`, `is_effective INTEGER (0/1)`, `source_support REAL NULL`, `source_count INTEGER NULL`, `evidence_tag TEXT NULL`; PK (`view_name`, `knowledge_point_id`) |
| `exam_questions` | `question_id TEXT PK`, `exam_year INTEGER`, `number INTEGER`, `subject_id TEXT`, `question_type TEXT`, `marks INTEGER NULL`, `answer TEXT NULL`, `answer_confidence TEXT NULL`, `knowledge_point_id TEXT NULL`, `knowledge_point_status TEXT NULL`, `n_knowledge_points INTEGER`, `locator_page INTEGER NULL`, `paper_sha256 TEXT NULL`, `paper_source TEXT` |
| `question_knowledge_weights` | `question_id TEXT`, `knowledge_point_id TEXT`, `weight REAL`; PK (`question_id`, `knowledge_point_id`) |
| `topic_weights` | `subject_id TEXT`, `knowledge_point_id TEXT`, `topic_weight REAL`; PK (`subject_id`, `knowledge_point_id`) |
| `projection_meta` | `key TEXT PK`, `value TEXT` |

`v_knowledge_points_by_subject` groups only effective `knowledge_points` rows. The view
`v_supplementary_not_effective` selects supplementary rows where `is_effective = 0`. The
`v_question_coverage` view describes index link counts; it is not a recommendation.

## Exam questions

`exam_questions.paper_source` is the top-level `paper_source` of the index file that holds the
entry; an index without the key records `national`, the default defined in
[`exam_index.md`](exam_index.md) §1. A present value must be a source code matching
`^[a-z][a-z0-9]*$`, otherwise the build fails with `ContractError` at
`reference.exam_indexes.<subject>.paper_source`. The column is never null.

`question_id` is unique across all registered index files of all subjects. When two registered
entries carry the same `question_id` (in two files, or twice in one file), the build fails with
`ContractError` whose message names the colliding ID and both files by their POSIX path relative
to `Workspace.root`; the error path is
`reference.exam_indexes.<subject>.entries[<i>].question_id` of the later entry. The check runs
before output is created, so the prior projection stays byte-for-byte unchanged.

Schema 5 differs from schema 4 by the three nullable FSRS columns in `review_items`, as specified
in `learning_state_projection.md`. Schema 4 differs from schema 3 by `paper_source` and the
collision rule: for the same inputs, every other table, view, and metadata value except
`projection_schema_version` is identical.

## Metadata, determinism, and write boundary

`projection_meta.projection_schema_version` is `5`. It is the only version the projection
records, and it covers meaning as well as shape: it increases whenever a table, column, view, or
metadata key is added, removed, or retyped, **and** whenever the rule that fills an existing
column changes for the same inputs. (The `parent_id` hierarchy rule once changed inside schema 2
without a bump, sol round 83 P2; this rule is what keeps that from recurring.)
A reader may therefore rely on one schema number meaning one set of tables and one set of fill
rules; there is no separate rules version. Each schema bump is described in this contract by
what differs from the previous number, as the schema 4 paragraph above does.

Learning-state tables, their source ports,
and the `state_inputs` and `freeze_events_latched` metadata are specified in
[`learning_state_projection.md`](learning_state_projection.md).

`inputs` is a JSON object whose keys are the
POSIX paths relative to `Workspace.root` and whose values are SHA-256 hashes of the exact bytes
read. It contains exactly the registered input files used for the projection build. The separate
`workspace_registry_sha256` value is the registry's raw-byte digest. `kp_effective_by_subject`
records effective row counts by subject; `supplementary_views` is a JSON array of registered view
names.

The build order and row ordering are stable. Repeating a build from unchanged input bytes yields
identical table and metadata content; no build timestamp is stored. The builder reads but never
modifies trees, indexes, weights, agreement files, the vocabulary database, or the registry.
Only the projection output is written.

The content notice records that supplementary nodes and their agreement attributes describe
cross-year source support and do not belong to the current-year effective scope. Extracted tree
counts do not establish coverage or learner capability.
