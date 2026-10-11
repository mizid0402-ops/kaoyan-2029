# Port contract: real-question index

Module: M5 (see `docs/模块地图.md`); implementation: `tools/verify_408_index.py`;
contract tests: `tests/contract/test_exam_index_port.py`.

This language-independent specification defines each JSON file registered in
`reference.exam_indexes.<subject>`. The index records question metadata and provenance; question
content is not an index field. Question count, section types, mark facts, and permitted answer
letters are checked against the registered paper shape described by
`contracts/paper_shape.md`.

## 1. Object shape

The top-level object requires every key below except the optional `paper_source`,
`content_policy`, `verified_facts` and `unverified_facts`, and rejects all other keys.
`kind` and `calibration` must be present with one of their enumerated values; null is rejected
(a null `calibration` would otherwise bypass the official-answer gate in §2):

`schema_version`, `kind`, `exam_year`, `subject_id`, `question_count`, `marks_total`,
`answer_source_coverage`, `calibration`, `provenance`, `content_policy`, `verified_facts`,
`unverified_facts`, `entries`, `paper_source`.

`paper_source` defaults to `national`. A source code matches `^[a-z][a-z0-9]*$`.
`question_id` is `<subject>-<year>-<two-digit-number>` for `national`, and
`<subject>-<paper_source>-<year>-<two-digit-number>` otherwise. Each entry's `subject_id` and
`exam_year` must equal the top-level values.

The following enums and fixed values are accepted:

- `kind`: `exam_question_index`; `schema_version` is an integer (current indexes use `1`).
- `calibration`: `awaiting_official_book` or `calibrated`.
- `question_type`: `single_choice`, `fill_blank`, `comprehensive_application`, `translation`,
  `writing`.
- `answer_kind`: null or `letter`; `answer_confidence`: `unverified`, `cross_checked`, `official`.
- `knowledge_point_status`: `not_assigned`, `assigned_multi_model`, `assigned_unreviewed`,
  `assigned_reviewed`.
- `source_tier`: `official`, `official_publisher`, `university`, `trusted_reprint`,
  `community_archive`.
- `rights_status`: `official_public`, `officially_published`, `unknown`, `personal_use`,
  `restricted`.

Unknown keys are failures at every object level. `notes` is null. The descriptive fields
`content_policy`, `verified_facts`, `unverified_facts`, provenance `note`, and answer-source
`cross_checked_with` retain their existing string/list shapes; they do not hold question stems,
options, or explanations. Existing field sets are:

- `answer_source_coverage`: `choice_answered`, `choice_total`, `cross_checked`,
  `cross_checked_numbers`. It must be an object with no other keys. The number of entries with
  `answer_kind: letter` equals `choice_total`.
- Each `provenance` record: `resource_id`, `sha256`, `source_tier`, `rights_status`, `note`.
- Each `answer_sources` item: `resource_id`, `sha256`, `cross_checked_with`.
- `locator`: `paper_sha256`, `page`, `line`.
- Each entry: `question_id`, `exam_year`, `subject_id`, `number`, `question_type`, `marks`,
  `answer`, `answer_kind`, `answer_confidence`, `answer_sources`, `locator`,
  `knowledge_point_id`, `knowledge_point_status`, `notes`, optional `knowledge_point_weights`.

## 2. Value and consistency rules

- `subject_id` must be a subject in the selected workspace registry. `exam_year` is a four digit
  year; question `number` is an integer from 1 through 99. Entries are non-empty and in exact
  continuous numeric order starting at 1. `question_count` equals entry count.
- `marks` is null or a positive number. `marks_total` equals the sum when all entry marks are
  numeric; if any mark is null, `marks_total` is null. Mark comparisons and sums use decimal
  values, avoiding binary floating-point rounding.
- `answer` is null or one uppercase letter A-G. Shape `answer_letters` narrows this set per
  section. Every entry with `answer_kind: letter` has an answer. Entries with
  `question_type: comprehensive_application` have a null answer.
- Provenance `resource_id` matches `^[a-z0-9][a-z0-9-]*$`; provenance and answer-source digests
  are 64 lowercase hexadecimal characters. Locator page and line are non-negative integers. Each
  locator paper digest equals the top-level paper provenance digest.
- Every provenance resource exists in the material ledger. If it has a local file path, that file
  exists and its bytes hash to the recorded digest; a pathless record must be a remote reference.
- `knowledge_point_id` and all `knowledge_point_weights` keys exist in the subject's registered
  effective tree. A present distribution is non-empty, contains only positive numeric weights,
  sums to 1.0 within `0.005`, and its maximum-weight node equals `knowledge_point_id`. A
  distribution requires a non-null `knowledge_point_id`.
- `not_assigned` has no knowledge-point id or distribution. `assigned_multi_model` requires an
  id and, when a distribution exists, exactly one node. `assigned_unreviewed` requires an id and,
  when a distribution exists, more than one node. `assigned_reviewed` cannot carry a model
  distribution.
- With `calibration: awaiting_official_book`, an unsupported bare knowledge-point id and an
  `official` answer-confidence claim are rejected.
- `content_policy`, when present, is a string; `verified_facts` and `unverified_facts`, when
  present, are lists. The verifier does not constrain their item text.
- The verifier checks the index's subject/year/source identity and every shape constraint against
  the exact `(subject_id, exam_year, paper_source)` record. A missing registration or paper record
  fails. When `answer_reader` is registered on that paper, its question-number set must exactly
  equal the shape's `answer_letters` ranges, and each answer must match the independent read.

## 3. Weight rounding

Knowledge-point attribution weights are rounded to three decimal places when written. Their sum
may differ from 1.0 by at most `0.005`, preserving the existing tolerance for accumulated rounding
while rejecting missing or altered attribution.
