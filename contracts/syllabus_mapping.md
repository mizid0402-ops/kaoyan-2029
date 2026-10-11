# Port contract: syllabus version mapping (M4)

This port maps stable knowledge point IDs between two registered syllabus versions. Python
reference implementation: `ky/knowledge/syllabus_mapping.py`; contract tests:
`tests/contract/test_syllabus_mapping_port.py`.

## Input format

UTF-8 YAML with exactly these top-level fields:

```yaml
schema_version: 1
kind: syllabus_mapping
subject_id: cs408
from_version: "2026"
to_version: "2027"
basis: "Compare both outline versions chapter by chapter."
changes:
  - from: cs408.ds.chapter-02.section-01
    to: [cs408.ds.chapter-02.section-01, cs408.ds.chapter-02.section-04]
  - from: cs408.os.chapter-05.section-03
    to: [cs408.os.chapter-05.section-02]
  - from: cs408.cn.chapter-01.section-06
    to: []
added: [cs408.co.chapter-03.section-07]
```

YAML duplicate keys and unknown fields are rejected. `schema_version` is the integer `1`;
`kind` is `syllabus_mapping`. `subject_id` must have a `reference.syllabus_versions` entry.
Version labels are quoted four-digit year strings and both must be registered for that subject;
the labels must differ. `basis` is required and non-empty.

## Mapping semantics

- The source and target trees are loaded through `load_knowledge_points()` from the knowledge
  tree port. Their ID sets are the authority for validating mapping references.
- A `changes[].from` must exist in the source tree and appear only once. Each `to` value must
  exist in the target tree. An empty `to` means the old ID was removed.
- Every source ID absent from the target tree must appear in `changes` (declared removal, rename,
  merge, or split).
- Every target ID must be reached by exactly one of: a `changes[].to` target, an implicit
  same-ID edge from an old ID omitted from `changes[].from`, or `added`. Explicit changes suppress
  the implicit same-ID edge; if a common ID is explicitly mapped elsewhere or to `[]`, that
  common target still needs another source or an `added` entry.
- An ID cannot be both a `changes[].to` target and `added`. Each `added` ID must be new and exist
  in the target. Repeating an ID inside one `to` list is rejected; sharing a target across
  different changes is allowed for merges. Merging `A` into a common ID `B` that survives
  therefore lists both edges, `{from: A, to: [B]}` and `{from: B, to: [B]}`: with only the first,
  `B` would be reached both explicitly and by its implicit same-ID edge, which is rejected as
  "multiple sources" so that every merge is written down rather than inferred.
- The workspace registry only records mapping paths. Mapping content is validated by this port.
  The caller passes the subject whose `mappings` list contains the file; `subject_id` in the
  document must match that registered position. The mapping path is admitted only if it matches
  a path returned by
  `workspace.require_all("reference.syllabus_versions.<subject>.mappings")`; source and target
  trees are obtained with
  `workspace.require("reference.syllabus_versions.<subject>.versions.<label>")`, including
  workspace-boundary checks.

## Public Python interface

```python
load_syllabus_mapping(path, workspace, *, subject_id) -> SyllabusMapping
SyllabusMapping.targets(old_id) -> tuple[str, ...]
```

`targets()` returns the declared target tuple, `(old_id,)` for unchanged IDs, and `()` for
deleted IDs. It raises `ContractError` at `old_id` if the ID is absent from the source tree.
The mapping retains the source tree ID set to make that membership check. Contract errors include
a field path. This port
does not mutate trees or migrate review queue state; queue migration and referential integrity
belong to the follow-up H4b work.
