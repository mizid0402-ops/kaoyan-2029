# Vocabulary reference port contract

The vocabulary SQLite file is replaceable reference data. Consumers must receive its path
explicitly (normally from `workspace.require("reference.vocabulary_db")`); library functions do
not locate a default database from their source file or the current directory. Every database
connection is opened read-only with SQLite URI `mode=ro`.

## Supported schemas

The adapter selects `v_top_words` when present, otherwise `words`. Either relation may be a table
or a view. At minimum, the selected relation must expose:

| Column | Required | Meaning |
|---|---:|---|
| `word_id` | yes | Stable identifier used when counting pool rows. |
| `word_form` | yes | Word form returned by `preview_batch`. |

These optional columns are used only when available:

| Column | Use |
|---|---|
| `is_stopword` | Excluded when `exclude_stopwords=True`. |
| `in_directions` | Excluded when `exclude_directions=True`. |
| `lemma` | Used to report distinct lemma-family count; otherwise `word_form` is the fallback. |
| `family_total_count`, `year_count` | Each available count column adds a descending sort key (`family_total_count`, then `year_count`); `word_form ASC` is always the final tie-breaker. |

Unknown additional columns are ignored. The adapter must work with either supported relation and
must not require the presence of a particular builder, auxiliary table, or source-specific schema.

## Reader behavior

`remaining_pool(db, ..., delivered=...)` counts eligible rows except the supplied delivered word
forms. `preview_batch(count, db=..., delivered=...)` returns at most the requested rows in
relation order, excluding the same set, and never chooses `count` itself. `delivered` defaults to
an empty set; both functions require an explicit database path and use the selected vocabulary
relation and optional filtering columns above. Missing databases or unsupported relation shapes
raise `VocabChannelError`; registered callers obtain the path with `Workspace.require`, which
raises `ContractError` for a missing or invalid registered file.

When `count == 0`, `preview_batch` returns an empty batch before opening the database. This permits
a zero-sized request even when the supplied database path is missing.

`delivery_log` is frozen legacy learner state retained in the reference database for historical
compatibility. Ordinary readers never inspect it. `import_delivery_baseline_with_dates(db)` is a
read-only migration input that returns `(delivered_on, word_form)` rows; active delivery state is
read from M13 completion events and supplied to the reader by callers.

The reader is read-only: it must not create, update, or delete tables or rows in the vocabulary
database. Replacement is supported by copying a compatible database elsewhere, changing only
`reference.vocabulary_db` in the registry, and passing the newly required path to the reader.
