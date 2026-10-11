# M6 topic-weight aggregation port

This contract defines how registered coder batches produce
`data/review_weights/topic_weights.json`. Python reference implementation:
`ky/exam/topic_weights.py`; CLI: `tools/aggregate_topic_weights.py`; contract
tests: `tests/contract/test_topic_weights_port.py`.

## Inputs and batch manifest

The workspace optionally registers a UTF-8 YAML manifest at
`reference.weight_batches`. The manifest contains:

```yaml
coders: [sol, luna, claude]
confidence_weights: {high: 1.0, medium: 0.6, low: 0.3}
topic_rollup:
  cs408: chapter
  math1: none
  eng1: none
meta:
  policy: "..."
  caveat: "..."
batches:
  - subject_id: cs408
    exam_year: 2024
    paper_source: national # optional; this is the default
    coders:
      sol: data/review_weights/coder_outputs/map-sol.json
      luna: data/review_weights/coder_outputs/map-luna.json
      claude: data/review_weights/coder_outputs/map-claude.json
```

The coder names and confidence-weight values are data in this manifest; they
are copied from the existing artifact's `meta`. Each batch identifies its
subject, year, optional paper source, and one workspace-relative output path
per registered coder. `exam_year` is a four-digit integer from 1000 through
9999. `paper_source` defaults to `national`; every source code matches
`^[a-z][a-z0-9]*$`. The coder output's `meta.node_table_sha256` is retained
as provenance only. The source node table files are not in the repository and
the recorded hashes can differ between coders, so this value is not validated.

Every subject used by a batch must have a `topic_rollup` entry. Values are
`chapter` or `none`; unknown values are contract violations. `chapter` maps
each coded node to its nearest ancestor whose effective-tree `scope` is
`chapter`. `none` retains the encoded node ID. The mapping is data, not a
subject-specific code branch.

## Coder entries and validation

Each coder document contains `meta` and an `entries` list. Every entry has a
positive integer `number` and `nodes` (a list of node IDs; null or empty means
no vote). An entry with non-empty `nodes` must have a registered `confidence`;
an entry with empty or null `nodes` may omit `confidence` because it contributes
no vote. Question numbers must be unique and contiguous from 1, and all coders
in one batch must cover the same numbers. Batch identity is
the tuple `(subject_id, exam_year, paper_source)`; duplicate identities are
rejected. A custom paper source is included in the question key.

Every coded node must exist in that subject's registered effective tree.
Unknown IDs raise `ContractError` identifying the coder, question number, and
node ID. If a batch uses `chapter` rollup but a coded node has no chapter
ancestor, aggregation fails and identifies the node.

## Aggregation

For each question, each coder distributes its confidence weight equally over
the nodes it listed. Empty node lists contribute no votes. The combined node
votes are normalized to sum to 1.0. The `per_question` distribution is rounded
to three decimal places; it is separate from the unrounded normalized values
used for `topic_weight`.

`topic_weight` sums the unrounded normalized question distributions after
applying the subject's configured rollup. Addition order is deterministic:
manifest batch order, question order from the first registered coder's output,
then node insertion order from coder and node order. This operation order fixes
the recomputed floating-point values. Comparisons require the same JSON type at every
position (an integer never equals a float, e.g. `1` vs `1.0`) and then numeric equality
with no tolerance: `0.0 == -0.0` is equal, while any other unequal floating-point values
differ regardless of how small the difference is.

The question key for a national paper is
`<subject_id>-<exam_year>-<number>`, for example `cs408-2023-1`. Question
numbers are not zero-padded; this key is distinct from exam-index `question_id`.
For a custom paper source the key is
`<subject_id>-<paper_source>-<exam_year>-<number>`.

## Output format

The output is a JSON object with four fields:

| Field | Meaning |
|---|---|
| `meta` | `policy`, `confidence_weights`, `coders`, computed `batches`, and `caveat` |
| `batch_stats` | Per manifest batch: `subject`, `year`, `questions`, `single_node`, and `spread` counts |
| `topic_weight` | Subject → summary node ID → sum of unrounded question weight |
| `per_question` | Question key → `{distribution: {node_id: rounded_weight}}` |

`single_node` counts questions whose rounded per-question distribution has one
node; `spread` counts distributions with more than one node. The JSON object
shape and existing field names remain stable for consumers.

## CLI

`py -3.12 tools/aggregate_topic_weights.py --check` recomputes the artifact
from the registered manifest, coder outputs, and effective trees. It exits 0
on numeric field equality with no tolerance, 1 on differences and lists
differing paths, and 2 on contract or input errors. `--check` is the only mode
that reads the current artifact. `--write` recomputes from the manifest,
coder outputs, and effective trees without reading the previous artifact, then
writes JSON to the registered `reference.topic_weights` path; that file may be
absent, but the resolved target must remain inside the workspace. Exactly one
mode is required.

The pure function is:

```python
aggregate_topic_weights(manifest, coder_outputs, knowledge_trees) -> dict
```

It accepts the parsed manifest, coder documents keyed by manifest path, and
effective trees keyed by subject and node ID. It does not read files or mutate
its inputs.
