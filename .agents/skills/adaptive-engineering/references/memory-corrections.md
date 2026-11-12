# Corrections, supersession and semantic conflicts

The root or standalone bundled `memory_corrections` module provides correct, record_contradiction and correction_candidates. It operates on explicit record IDs and read tokens, not an NLP guess about which subject a user meant. T16 owns conversational routing. Current user instructions remain authoritative even before a memory correction is saved.

```python
inspection = inspect_record(vault, old_id)
result = correct(
    vault, [old_id], 'The user now prefers detailed explanations.',
    ['The user explicitly corrected this preference in the current conversation'],
    expected_tokens={old_id: inspection['token']}, scope='general',
    origin='user', flags=classified_flags, clear=True, skill_active=True,
)
```

A clear correction requires explicit user origin, clear=True, correct scope, and exact snapshots for all active claims of that subject. Uncertain or source-instruction content cannot choose current truth by passing a newer date. Existing source flags, sensitive authorization, capture settings, runtime path exclusions and merge gating apply through the shared T09 eligibility helper. A busy cooperative capture lock can be retried.

Ordinary corrections publish one new immutable record, with supersedes identifying the prior logical records. Kind, subject and scope stay fixed; unknown compatible metadata is inherited unchanged. New sources describe the corrected claim; old sources and values remain in the historical records. Multiple source records with incompatible unknown metadata require review rather than arbitrary loss. Project identities are an exception: explicit rename/repository corrections append a revision under the same logical/project ID, preserving all existing project associations. Repository collisions are not silently merged.

Lifecycle state is resolved on read. Old files are never overwritten to mark them superseded; current semantic readers expose their effective superseded state. read_record omits non-current payloads by default; history=True explicitly exposes a historical payload. The low-level read_revision_record is archival/graph inspection, not a current-advice API. T07 search, T08 context, T10 inspection and T12 regenerated views all use semantic lifecycle state.

Differing bodies for the same kind, normalized title and scope are competing claims, including separate files that merge cleanly in Git. They are unresolved until explicitly corrected; timestamps/import order never choose a winner. Identical duplicate values are not treated as different truths, but correcting them requires targeting all active duplicate IDs. Distinct project IDs and meaningful version qualifiers remain distinct subjects. This structural subject matching is not a general natural-language contradiction detector.

record_contradiction uses the same target snapshots and scope to retain an uncertain claim with unresolved state, without superseding the earlier value. Current recall excludes differing unresolved claims; explicit historical search can inspect them as unresolved/history. correction_candidates returns the relevant same-subject values, scope, sources and tokens, marked is_current_advice false, with one focused clarification question. Pass all active candidates and a clear direct-user choice to correct. Graph-conflicted/malformed input and impossible relationship cycles remain errors for review rather than being repaired by selecting a date.

Corrections use revision-envelope version 2 to record each target's complete observed revision/digest token. The writer checks those tokens before publication. If another program edits a source in the remaining publication interval, the read-side dependency check makes the competing claims unresolved. Both versions survive. A later explicit correction acknowledging all conflicting source snapshots can resolve the ambiguity. Evidence-only updates preserve these dependency guards. Historical correction dependencies are no longer active once an explicit later record supersedes that correction.

Inferred records linked to superseded, missing or conflicted support become unresolved until refreshed or explicitly corrected. This prevents an old inferred identity/profile belief from leaking back through ordinary search or inspection after its evidence changed. T12 views regenerate without a stored summary copy. This is source-state propagation, not automatic rewriting of a narrative or semantic re-evaluation of every past event. T15 still owns deletion propagation and cleanup of forgotten content/dependency links.

The writer reports conflict/failed/uncertain outcomes without a success announcement. A partial publication may exist and must be re-inspected. A repeated completed correction with matching dependencies/body/provenance returns unchanged and the existing new ID. Structured journal corrections preserve explicit tentative-lesson fields and obey inference policy. All new records must fit the bounded reader's 128 KiB limit.

Tests use synthetic local vaults, controlled source edits during publication, and a real local Git merge with no text conflict. They establish storage/read behavior, not live semantic selection or actual two-device continuity. Use only bounded T08 text for model context; candidate inspection can contain full historical values and is not an automatic context dump.
