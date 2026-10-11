# Knowledge tree port contract (M4)

This port defines the node data model and the read and write boundaries for effective
knowledge trees. Python reference implementation: `ky/knowledge/knowledge_point.py`;
tree grammar strategies: `ky/knowledge/tree_grammar.py`; contract tests:
`tests/contract/test_knowledge_tree_port.py`.

## Tree input

Trees are UTF-8 YAML. The document is either a list of nodes or a mapping with optional
`schema_version` and an `items` list. YAML duplicate keys are rejected by the shared strict
YAML loader before node validation. Unknown document and node fields are rejected.

## Knowledge point fields

The field set below follows `_POINT_KEYS` and the validation rules in the reference
implementation. A field marked optional may be absent; defaults are listed explicitly.

| Field | Type | Requirement and meaning |
|---|---|---|
| `schema_version` | integer | Optional, default `1`; only version `1` is accepted. |
| `knowledge_point_id` | non-empty string | Required stable node identifier; full ID grammar is selected by the subject profile. |
| `title` | non-empty string | Required display title. |
| `status` | enum | Required: `raw`, `extracted`, `reviewed`, `approved`, or `superseded`. |
| `source_kind` | enum | Required: `official_outline`, `textbook`, `real_question`, `manual`, or `ai_generated`. |
| `sources` | non-empty list of source objects | Required provenance. A source has `path`, 64-character SHA-256 `sha256`, and non-empty `locator`. Locator keys: `page`, `line`, `line_start`, `line_end`, `section`, `offset`, `quote_ref`. |
| `frequency` | object or null | Optional, default null. If an object, it has `value`, `basis`, `computed_by`, `as_of`; `value` is finite numeric and non-negative, `computed_by` is `deterministic_script`, and `source_kind` is not `ai_generated`. |
| `evidence` | list of evidence objects | Optional, default empty. Each item has a `validation` from `guided`, `independent`, `frequency`, `coverage`, `baseline`, `prediction`, `final_acceptance`, and a valid `source`; optional keys are `result`, `note`. AI-generated nodes may use only `guided`. |
| `transition_history` | list of transition objects | Optional, default empty for `raw`. Required for non-raw nodes and must form a contiguous chain ending at the current status. Each transition has `from`, `to`, `actor`, `at`, and `source`; optional keys are `evidence`, `replacement`, `reason`. |
| `supersedes` | non-empty string or null | Optional, default null; replacement identifier for a superseding revision. |
| `revision` | integer ≥ 1 | Optional, default `1`. |
| `scope` | enum | Optional, default `item`; one of `subject`, `chapter`, `section`, `item`. |

## Scope and workflow

Scopes state the granularity of a node. `subject` is not examinable frequency content and is
not a day-assessable target; `chapter` and `subject` are block-review targets; `section` and
`item` may be day-assessable. The selected tree grammar additionally checks hierarchy and ID
consistency.

Allowed transitions are `raw → extracted → reviewed → approved → superseded`. `raw → extracted`
may be performed by AI or a human. The final three transitions (`extracted → reviewed`,
`reviewed → approved`, `approved → superseded`) require a human actor. Each transition also
requires its contractually defined source and, where applicable, evidence or replacement.
AI-generated nodes cannot be approved.

## Frequency provenance and permissions

Readers validate the stored data, independent of caller identity. If `frequency` is present,
all readers require a finite numeric `value >= 0`, `computed_by == "deterministic_script"`,
and a non-AI-generated node. A reader does not claim write authority by loading the tree.

`load_knowledge_points(path)`, `load_knowledge_points_from_text(text, *, source)`, and
`validate_knowledge_point(raw, *, source)` are read/validation interfaces and accept no
`writer` argument. They validate shape and provenance only. A write permission is checked at
the mutation boundary: `apply_deterministic_frequency(..., writer=...)` accepts only
`deterministic_script`. Workflow mutations use `transition_knowledge_point(..., actor=...)`
and enforce the transition actor rules above. Mutations revalidate their resulting data using
the same reader-independent validator.

## Subject tree grammar

The workspace subject profile selects `tree_grammar`; see [`workspace.md`](workspace.md) §2.5.
The strategy implementations live in `ky/knowledge/tree_grammar.py`. A grammar owns its ID
syntax and structural checks; adding a subject that fits an existing grammar is a registry
data change, while a new syntax requires a new strategy and contract coverage.

## Hierarchy

Tree hierarchy is expressed by dot-separated segments in `knowledge_point_id`.
For a node ID, its parent is the longest strict prefix formed at a `.` boundary
that is also an ID in the same tree. A node with no such prefix is a root. Its
ancestors are found by repeating the same parent lookup from each parent.

This is the existing tree grammar convention: grammar validation uses the ID
segments to check chapter, section, item, and subject relationships. Consumers
must use the public hierarchy helpers below instead of reimplementing the ID
walk.

## Grammar-aware tree parent (M17 display, 2026-10-01)

The ID-prefix rule above does not connect every node: `named_chapters` sections
(`math1.hs.ch01.content`) have no prefix node, and in both `named_chapters` and
`numbered_chapters` the chapter nodes (`math1.hs.ch01.chapter`, `cs408.ds.chapter-01`)
have no prefix node either, so `parent_id` reports them as roots. Consumers that need the
syllabus outline as a tree (M17 coverage, `contracts/charts.md` §4.3) use
`tree_parent(point_id, points_by_id, grammar)`, applied in this order:

1. `named_chapters` only: an ID ending in `.content` or `.requirements` whose
   `<base>.chapter` node exists → that chapter node (the grammar already requires it).
2. Otherwise the longest strict dot prefix that is a node in the tree (same as `parent_id`).
3. Otherwise, when the first two segments `<s>.<d>` form a domain whose node
   `<s>.<d>.subject` exists and is not `point_id` itself → that domain node.
4. Otherwise `None` (a root).

`grammar` is the subject's registered `tree_grammar` name; an unknown name raises the same
error as `select_tree_grammar`. `points_by_id` must contain `point_id`. The function only
reads IDs; it never consults titles or order. `parent_id` and
`nearest_ancestor_with_scope` keep their behaviour unchanged (M6 topic weights depend on them).

M17 chart coverage and M30 mastery use `learnable_tree(points, grammar)` to share the
learnable-node outline. It returns `LearnableTree(points_by_id, parents, children, roots,
leaves, trackers)`. `children`, `roots`, `leaves`, and `trackers` preserve source-file order.
`trackers` are `scope: subject` nodes with no non-`subject` descendant under `tree_parent`;
they are excluded from the other outline fields. Children whose parent was removed become
roots. This helper does not interpret review states or weights.

## Public Python port

```python
load_knowledge_points(path) -> tuple[KnowledgePoint, ...]
load_knowledge_points_from_text(text, *, source) -> tuple[KnowledgePoint, ...]
validate_knowledge_point(raw, *, source="<knowledge_point>") -> KnowledgePoint
parent_id(point_id, tree_ids) -> str | None
nearest_ancestor_with_scope(point_id, points_by_id, scope) -> str | None
tree_parent(point_id, points_by_id, grammar) -> str | None
learnable_tree(points, grammar) -> LearnableTree
apply_deterministic_frequency(raw, value, *, basis, as_of, writer) -> dict
transition_knowledge_point(raw, target_status, actor, *, source, evidence, ... ) -> dict
```

Substitute implementations must preserve field-path validation errors, duplicate-key
rejection, provenance checks, scope/workflow rules, and the separation between reader
validation and mutation authorization.
