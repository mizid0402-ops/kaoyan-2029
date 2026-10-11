# Port contract: paper shape registry

Module: M5′ (see `docs/模块地图.md`); implementation: `ky/exam/paper_shape.py`;
contract tests: `tests/contract/test_paper_shape_port.py`.

This language-independent port defines `data/paper_shapes/<subject>.yaml`, the source of
question numbering, type ranges, optional mark constraints, answer-letter rules, and independent
answer readers for a paper identified by `(subject_id, exam_year, paper_source)`.

## 1. File shape

UTF-8 YAML with exactly these top-level keys:

```yaml
schema_version: 1
kind: paper_shapes
subject_id: cs408
papers: []
```

Unknown keys at every level and duplicate YAML mapping keys are rejected with a field path.
`schema_version` is integer `1`; `kind` is `paper_shapes`. `subject_id` must equal the subject
whose file is registered. `papers` is a non-empty list.

## 2. Paper identity and coverage

Each paper has exactly `exam_year`, `paper_source`, `question_count`, `sections`, and `basis`,
with optional `answer_reader`.

- `exam_year` is an integer year; `question_count` is an integer from 1 through 99.
- `paper_source` matches `^[a-z][a-z0-9]*$`; `national` identifies a national examination.
- `(exam_year, paper_source)` is unique within the subject file.
- `basis` is a non-empty string recording where the registered facts came from.
- `answer_reader`, when present, is a non-empty reader name. Unknown names are a verifier error.
- `sections` is a non-empty list that covers each number in `1..question_count` exactly once,
  in ascending contiguous ranges. Each range uses `numbers: [start, end]` with positive integers.
- `question_type` is one of `single_choice`, `fill_blank`, `comprehensive_application`,
  `translation`, or `writing`.

## 3. Optional section constraints

A section may have `answer_letters`, only for `single_choice`. It is a non-empty string of unique
letters from A through G; indexed answers in the section must use one of those letters.

A section may specify at most one mark form:

- `marks_each`: a finite positive number (integer or float, not boolean) applied to each question;
- `marks`: a mapping with one finite positive number (integer or float, not boolean) for each
  question in that section;
- `marks: unverified`: each indexed mark in that section must be null.

If no mark form is present, the paper record does not constrain marks for that section. If every
section constrains numeric marks, the index total must equal their sum. Otherwise the existing
index rule remains: `marks_total` is null whenever any indexed mark is null.
Mark comparisons and sums use decimal values, so decimal fractions are compared without binary
floating-point rounding.

## 4. Python interface

`ky.exam.paper_shape.load_paper_shapes(path, *, subject_id)` returns `PaperShapes`.
`PaperShapes.get(exam_year, paper_source="national")` returns the matching `PaperRecord`; an
unregistered identity raises `ky.models.ContractError`. The loader validates only the shape file;
the workspace registry owns path registration and the index verifier owns cross-file checks.
