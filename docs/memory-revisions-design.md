# Memory revision storage, version 1

The repository-root `memory_store` API writes new files only. Run additive vault setup to create `memory/revisions`; resolve the vault through the existing explicit-path/environment/config resolver before calling the API. The API does not guess a destination or initiate capture, synchronization or Git mutations. Packaging this root API into installed skills remains T18.

## Encoding and identity

A revision is named `memory/revisions/<memory UUID>.<revision UUID>.md`. It begins with one line:

```text
<!-- memory-revision {"version": 1, "revision_id": "<UUID v4>", "parents": {"<revision UUID or base>": "<SHA-256>"}} -->
```

The remainder is a complete v1 Markdown record. The logical record ID and project ID retain their existing meaning. The envelope version is separate from the v1 record schema. Each parent digest covers the exact UTF-8 bytes of its complete file, including its envelope. New revisions use UUID v4 IDs; duplicate IDs, invalid envelopes, missing parents and cycles are errors. An existing v1 record in a managed memory area acts as revision `base`. Two such records with the same logical ID are still invalid duplicates. Templates are not records. Legacy candidate/approved engineering notes remain outside this store and are not rewritten.

Unknown metadata is rejected on new logical records. Compatible metadata from an existing record is validated by the path boundary and must be carried forward unchanged on ordinary updates. Core record fields retain their v1 validation. A deliberate conflict resolution chooses the resulting complete record; it must satisfy the same content boundary.

## Reading and resolution

`read_record(vault, id)` returns `None` for no record. Otherwise it returns a snapshot `token` mapping every revision ID to its digest, a list of graph tips and `status: current` or `conflict`. Current results include metadata and body; conflicts do not expose a current payload. Invalid graphs raise an error. The implementation currently inspects all managed records and fails closed on unreadable or invalid managed files.

A unique tip is current only if no unresolved parent digest mismatch exists. Multiple tips are branches; a changed ancestor is a conflict even with a unique tip. No timestamp chooses a winner. A later resolution acknowledges the current bytes of all observed revisions, including the edited ancestor and its child; this preserves the old edge as historical evidence while resolving the current disagreement. A further edit invalidates that acknowledgement.

`write_record(vault, metadata, body, expected_token=token)` publishes an ordinary update. To resolve a conflict, supply the conflict snapshot token and `resolve=True`. Each new revision references the entire observed snapshot, keeping resolution deterministic. This costs increasing metadata and is intended for the MVP's small records; future compaction must preserve graph semantics.

## Publication and outcomes

The writer validates content and runtime path exclusions, checks T05's merge gate before preparation and again before publication, and refuses a stale snapshot. It writes and flushes a temporary file, publishes a hard link with no replacement, flushes the directory and verifies both saved bytes and resolver output. Directory handles and no-follow opens anchor publication within the managed directory. Existing record bytes are never replaced. Local filesystems/platforms without the required directory-handle, no-follow, hard-link or flush operations fail explicitly; there is no weaker fallback.

Supply a stable `revision_id` for retries after a lost response. The same revision ID, expected snapshot and bytes return unchanged; different bytes at that ID fail. Outcomes are created, updated, unchanged, conflict or failed. A conflict after publication means the revision was saved alongside a competing edit. A failure includes `may_have_written` so callers can distinguish rejection before publication from an uncertain saved result. Recheck the record after uncertainty. Leftover `.memory-*` temporary files are ignored by readers.

The snapshot can become stale immediately after a successful response. Another application can edit or delete files, but the assistant's publication never overwrites them. There is no lock or mutable head file that hides branches. Directory moves and an independently destructive external program are outside the content-preservation guarantee.

## Search, forgetting and validation

T07 must use the resolver and exclude unresolved branches from current recall. Existing legacy search is not yet memory-aware. T15 must remove every revision containing forgotten content, including conflict branches, and propagate payload-free deletion markers. Revision retention is not yet an implementation of forgetting. Git history and backups remain outside active-memory deletion.

Synthetic tests exercise creation/update/retries, controlled concurrent publication, external edits immediately before publication and to ancestors afterward, explicit resolution, missing parents, stale tokens, permission failures, uncertain publication results, path exclusions, compatible fields and symlinks. No personal vault or external remote is used.

## Version 2 source dependencies (T13)

Version 1 envelopes remain supported. Version 2 adds required dependencies and
inherit_from fields. Dependencies map logical memory UUIDs to their complete
observed revision-ID/SHA-256 snapshot tokens; inherit_from is null or a key in
that map identifying the compatible metadata source for a new logical record.
The v1 inner record schema is unchanged. Ordinary evidence updates preserve an
existing dependency guard. The writer checks source snapshots before publishing;
semantic readers also validate active correction dependencies after publication.
This detects late source edits without replacing source files. Historical guards
are retired when a later explicit record supersedes their correction.

Read-side subject conflicts and effective supersession are resolved by the shared
memory snapshot. read_record exposes current semantic state; explicit history
can inspect non-current payloads. read_revision_record exposes only the lower
revision graph and must not be treated as current advice. New writes are limited
to 128 KiB so verification and bounded readers agree on supported record size.

Clients reading corrected vaults must support envelope version 2 and semantic
lifecycle resolution. Version 1 inner records and old revision files are not
rewritten. Older readers must be upgraded before relying on current recall;
actual mixed-client/two-device validation remains T21/T22.
