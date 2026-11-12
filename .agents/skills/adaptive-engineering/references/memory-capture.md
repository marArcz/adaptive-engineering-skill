# Selective capture policy and deduplication

The root or bundled `memory_capture.capture` API accepts a structured proposal from an active, trusted conversation workflow. T16 owns automatically invoking that workflow. This API does not parse a conversation, classify secrets semantically, activate background capture, or treat source documents as instructions. The caller must classify evidence from the actual conversation and honor current user instructions before proposing capture. T20 owns live-agent selection-quality evaluation.

```python
proposal = {
    'category': 'durable_preferences_goals_decisions',
    'origin': 'user',
    'kind': 'preference',
    'title': 'Response length for technical explanations',
    'body': 'The user prefers concise technical explanations.\n',
    'scope': 'general',
    'sources': ['The user stated this preference in the current conversation'],
    'flags': {'temporary': False, 'do_not_remember': False,
              'sensitive': False, 'secret': False, 'third_party_private': False},
}
result = capture(vault, proposal, skill_active=True)
```

Supply `project_id` only for project scope and use optional `related_ids` for accurate relationships. Use descriptive stable subject titles; include a meaningful version/subject qualifier when two versions should remain separate. Titles must contain searchable words under T07's matching rules. Do not copy local paths into the title, body or provenance. Runtime `project_roots`, `project_paths` and `device_identifiers` are passed separately to the boundary and never stored.

Origins are user, observation, source and inference. They produce user-stated, source-supported, source-supported and inferred basis respectively. Hypothetical and source_instruction origins are excluded. Source-origin proposals can create knowledge, not assertions about the user. Inferred records stay inferred when repeated or when provenance is expanded; confirming or correcting a fact is later lifecycle work, not implicit promotion.

Categories match the capture-settings boundary keys. Durable preferences/goals/decisions, useful progress/commitments/questions, significant shared experiences and tentative inferences are eligible within their configured boundaries. Temporary/do-not-remember material, credentials, third-party private data and project filesystem paths are excluded. All five flags are required booleans, so missing classifications fail rather than defaulting to eligible. Flags are independent of category: an otherwise eligible preference flagged temporary or secret is still excluded.

Sensitive proposals require a direct user origin and `retain_sensitive=True` supplied by the trusted caller after a specific user retain request. A source cannot authorize retention by including this flag in its text or in proposal fields. `skill_active` and retention permission are separate call arguments; missing activation excludes capture. These arguments must never be copied from an untrusted document or hypothetical example. This is a caller trust boundary, not an automatic detector of falsely classified source content.

The saved v1 policy must contain all supported boundary keys. Users may pause capture or tighten eligible categories to exclude. Required exclusions and sensitive/inference constraints cannot be relaxed through malformed settings. A missing or invalid policy/vault returns unavailable. Paused capture does not create a capture lock or write a memory. Policy is rechecked under the lock and before writing; checks are snapshots, not a transaction with arbitrary external settings editors.

Capture searches historical and current subject/scope matches through T07 before creating anything. Exact normalized title, kind and general/project identity define a candidate subject; different titles or project IDs do not silently merge. Exact statement repetitions (ignoring whitespace) retain their original body and basis, merge distinct provenance and related IDs, and publish a revision only when evidence changes. No-change repeats are quiet. Different statements, historical/superseded subjects and multiple candidate IDs return needs_review; they do not automatically overwrite an old belief. An explicit match_id can disambiguate an existing matching subject, but cannot bypass scope, body or lifecycle checks. T10/T13 provide explicit changes and corrections; use the memory-corrections guide.

Incomplete, invalid or conflicted vault evidence and truncated subject searches stop capture rather than risk duplication. The helper holds a nonblocking cooperative lock across matching and writing. A concurrent capture call returns busy and can retry; retries after a successful write match the existing record. The empty `memory/.capture.lock` contains no personal data and is not a memory. It must not be deleted/replaced while capture is running. This lock coordinates this API's callers on one filesystem, not independent editors, direct low-level writers or different devices. T06 still preserves revisions against competing edits.

Statuses include excluded, paused, unavailable, busy, needs_review, created, updated, unchanged, conflict and failed. The compact trace contains reason codes and candidate IDs, never rejected proposal text. Only verified created/updated results have an announcement. Unchanged, ambiguous, rejected, conflicted and uncertain writes must not be announced as successful saves. Writer failures propagate may_have_written so callers can re-inspect uncertain results. Path exclusion and merge gating are applied before persistence. No Git publication or personal-vault writes are authorized by this documentation.
