# Portable memory contract, version 1 (draft)

This contract implements the data-model portion of the accepted Personal Memory
Plugin MVP. It does not itself implement capture, recall, validation, deletion,
project matching, or synchronization. Legacy engineering notes retain their
existing format and approval semantics.

## Encoding

Each record is a UTF-8 Markdown document. Its frontmatter is delimited by lines
containing `---`; each metadata line is `key: JSON-value`. JSON values are a
restricted, standard-library-readable subset of YAML. Keys are unique; reject
unknown keys, malformed JSON, missing delimiters, and unknown schema versions.
The Markdown after the closing delimiter is the nonempty body. Preserve its text
on a parse/serialize round trip. Do not parse legacy notes as memory records.

| Field | Required | Representation and constraints |
| --- | --- | --- |
| schema_version | yes | integer `1` |
| id | yes | lowercase UUID v4 string, generated once and never reused |
| kind | yes | `user_fact`, `preference`, `assistant_identity`, `experience`, `project`, or `knowledge` |
| title | yes | nonempty JSON string |
| scope | yes | `general` or `project` |
| project_id | project scope | UUID v4 string identifying a project independently of checkout location; omitted for general scope |
| basis | yes | `user-stated`, `inferred`, or `source-supported` |
| state | yes | `current`, `superseded`, or `unresolved` |
| created_at, updated_at | yes | UTC timestamp in `YYYY-MM-DDTHH:MM:SSZ`; updated_at must not precede created_at |
| sources | yes | nonempty array of nonempty strings describing available conversation context or source URLs; no invented sources |
| related_ids | yes | array of distinct memory UUIDs, possibly empty, excluding this record |
| supersedes | yes | array of distinct memory UUIDs, possibly empty, excluding this record |

An inferred record remains inferred even if repeated. A correction is a new
current record whose `supersedes` identifies the old record; mark the old record
superseded. A contradiction that cannot be resolved is marked unresolved, not
silently promoted to current. Validation of the relationships across files,
duplicate IDs, and deletion markers requires a vault-wide check. References to
missing or deleted records must be reported, not silently treated as evidence.

Project records have project scope and use their own `id` as `project_id`.
Their body provides a readable name and, optionally, a repository URL. Match
using the stable ID or an unambiguous repository identity; similar names alone
never establish identity. Ask when ambiguous. Obtain the checkout location at
runtime only. Project filesystem paths, machine IDs, and location mappings must
not appear in any stored record, including body and sources. Vault-relative
links between notes are permitted. Content checks alone cannot reliably detect
every path; capture and write boundaries must enforce this rule.

Experience bodies describe context, significance, observed outcome, and any
inferred lesson separately. Link related decisions using `related_ids`. Profile
and assistant identity summaries are derived views of their source records,
not independent evidence; retain source IDs and refresh summaries on correction
or forgetting. An empty vault implies no invented identity history. Summary
storage and refresh are deferred to T12.

## Forgetting

A deletion marker is separate from a memory record and contains only
`schema_version`, `id` (the deleted UUID), and `deleted_at` (UTC timestamp in
the format above). It must contain no title, body, source, relationship, project
identity, or other forgotten content. IDs are never reused. Deletion propagation,
summary cleanup, and synchronization conflict handling belong to T15 and T21;
Git history and backups are outside active-memory deletion.

## Compatibility and validation boundary

Legacy `status: candidate` and `status: approved` remain legacy knowledge review
states, independent of memory `basis` and `state`. No migration or rewrite is
implied. T06 must reject unsupported versions, invalid fields and duplicate IDs
with actionable errors, preserve values on serialization, and implement
recoverable writes. T07 must distinguish these records from legacy search.
T03 and T04 implement project identification and path exclusion. The contract
alone does not satisfy the end-to-end A03, A06, A10, or A13 checks.

## Revision storage

T06 adds a separate versioned revision envelope around complete v1 records,
without changing their fields. See [Memory revision storage](memory-revisions-design.md)
for publication, graph resolution, compatibility and conflict outcomes. The
logical record UUID stays stable across revisions. Revision-aware consumers
must resolve the graph before using a current record; repeated logical IDs in
recognized revisions are not duplicate records. Standalone duplicate v1 records
remain invalid. Corrections between distinct logical memories still use
`supersedes`, independently of revision history.

## Effective lifecycle

T13 derives superseded/unresolved state from valid same-subject links, source
snapshot dependencies and competing claims. The original immutable record bytes
retain their historical metadata; semantic readers expose effective current
state. Correction records have fresh logical IDs, except project identity
changes that retain the stable project ID and preserve prior revision history.
See the bundled memory-corrections guide and revision storage contract.
