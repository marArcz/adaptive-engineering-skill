# No-project-path boundary

All new managed memory proposals must pass `validate_memory_content` from
`memory_boundary.py` before a writer persists them. Pass the whole JSON-compatible
proposal, including the body, title, sources, nested summaries and metadata.
Corrections, consolidation, identity/profile summaries, journal entries and
imported learning use the same boundary. Supply known workspace roots, relative
project paths and machine/device identifiers as runtime-only arguments. Never
save those arguments in the vault or a location registry.

The boundary rejects known runtime values, location-bearing fields, recognizable
Linux/macOS/Windows paths, relative paths with separators, and common source or
configuration filenames. Rejection requires a new summary; it does not silently
redact or save the proposal. Errors contain a generic reason, never the rejected
text or metadata key. Do not attach the original proposal to error logs.

Describe the component and outcome instead of a checkout location. Summarize
pasted logs and quotations rather than copying their prompts or working
directories. Evidence can say "the user described the queue component" when
that is accurate; do not invent a URL to replace an excluded source path.

Credential-free HTTP(S) URLs are allowed, subject to known-runtime checks and
checks of their query/fragment content. Explicit Markdown and wiki links into
`memory/profile`, `memory/identity`, `memory/experiences`, `memory/projects`, and
`memory/knowledge` ending in `.md` are permitted. Traversal is rejected and
visible labels are still checked. Bare project paths are not exempt simply
because they resemble links. Numeric fractions and slash-separated dates remain
usable. The boundary deliberately errs toward rejection of ambiguous path-like
text; rephrase it instead of disabling the check.

The existing project serializer and T01 reference contract validator call this
boundary. Production memory writers do not exist yet: T06 and subsequent writer
tasks must integrate it. The skill guidance also requires it for new managed
memory derived from learning. Existing legacy vault notes are not migrated.

This is a deterministic boundary, not a semantic proof. Unknown device names,
unusual encodings, and arbitrary prose may require agent judgment. It is not a
general secret detector. Live-agent capture quality and actual cross-device
behavior need separate acceptance checks.
