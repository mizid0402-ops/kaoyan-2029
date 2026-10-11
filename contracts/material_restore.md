# Material restoration port (M1)

Module: M1 (`ky/acquisition/ledger_restore.py`); CLI:
`py -3.12 tools/fetch_all_from_ledger.py [--workspace R] [--check] [--json]`;
contract tests: `tests/contract/test_material_restore_port.py`.

## Purpose and boundary

The workspace registry supplies `reference.ledger` and `materials.raw_root`. M2 validates the
entire ledger before this port inspects or writes any file. The command visits every ledger row
in ledger order. Every `local_file` has a recorded path, byte size and SHA-256; only a missing
`local_file` with an HTTP(S) `storage.url` and `rights.may_store: true` can be fetched. The
`provenance.source_url` may identify a landing page and is never used as a download fallback.
`remote_reference` rows are reported as `reference_only`: they have no recorded local bytes and
cannot be restored from a hash. The command never changes the ledger.

The result is one `RestoreResult(resource_id, status, path, detail)` per row. `path` is the
resolved local target for `local_file` and `null` for `remote_reference`. Existing files are
verified against the ledger. A valid file is `already_verified`; an invalid existing file is
`existing_mismatch` and is never overwritten. A missing file with no URL is `missing_url`; an
unsupported URL is `invalid_url`; a rights denial is `storage_not_permitted`. `--check` returns
`needs_download` for an eligible missing file without contacting the network. A path resolving
outside the registered raw-material root is `invalid_path`. A file that cannot be read for
verification is `existing_unreadable` and is not replaced.

## Download and publication

A fetch must return HTTP 200. Network or read errors are `download_failed`; other status codes
are `http_error`. The response is streamed into the system temporary directory with a strict
upper bound of the ledger's `byte_size`. A different byte count is `byte_size_mismatch`; a
different digest is `sha256_mismatch`. No target directory or file is created on these failures.
The tool does not update the ledger when a remote site changes its bytes: the user must review
the source and explicitly register a new hash if appropriate.

Verified bytes are copied to a short-lived sibling temporary file on the destination volume,
rehashed, then published with `os.link` so a target that appeared in the meantime cannot be
replaced. The sibling is removed in `finally`. `target_conflict` and `publish_failed` report
publication failures; rerunning the command is safe after an interruption. This destination
sibling is the only operational exception to keeping temporary downloads and test fixtures in
the system temporary directory, because atomic publication requires a same-volume source.

`restore_materials(materials, *, root, raw_root, check_only=False, open_url=urlopen)` is the
library port. `open_url` is injectable for offline tests. Each material's result is independent:
a failure does not prevent later rows from being inspected or restored.

## CLI result

`--json` prints a list of result objects in ledger order, each with exactly `resource_id`,
`status`, `path`, and `detail`. Text mode prints one line per row. Exit 0 means every local file
was verified or restored; `reference_only` rows do not affect it. Exit 1 means at least one
local file remains missing, invalid, or unrestored. Exit 2 means arguments, workspace registry
or ledger validation failed before restoration. This command does not promise that every
historical URL will still serve the exact registered bytes.
