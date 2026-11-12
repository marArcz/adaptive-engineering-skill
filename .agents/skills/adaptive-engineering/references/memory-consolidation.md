# Bounded memory consolidation

Use the root or standalone bundled `memory_consolidation` API only while this skill is active. Supply the trusted privacy classification flags used by capture, runtime path exclusions, and explicit sensitive-retention authorization when applicable. Paused capture, merge gates and the shared capture lock also govern maintenance. T16 owns conversation workflow activation; there is no scheduler.

```python
from memory_consolidation import plan_consolidation, consolidate

plan = plan_consolidation(vault)  # Read-only; does not authorize persistence.
result = consolidate(vault, flags=flags, skill_active=True)
project_result = consolidate(vault, flags=flags, skill_active=True,
                             scope='project', project_id=project_id)
```

Default maintenance includes general memory only. A supplied project ID adds that project's records; scope='project' restricts it to that project. scope='all' explicitly includes all scopes, but never merges across projects or general/project boundaries. Project identity records are excluded. The default is three groups per run, configurable from one to ten, with at most thirty current records per group. The bounded scan defaults to 1,500 notes; an incomplete or unsafe scan cannot authorize consolidation. Oversized groups and conflicted records are skipped and reported.

Merge candidates must have identical kind, scope, project, title, body, basis, compatible extra metadata and equivalent related links. This is conservative exact matching, not semantic paraphrase detection. Shared keywords, distinct outcomes and mixed evidence bases do not justify a merge. The lexically smallest current logical UUID becomes canonical solely to make equivalent choices repeatable; dates never select truth. Sources, external relationships and existing correction dependencies are retained. Inferred lessons remain tentative, including lessons inside structured experiences.

The writer appends an envelope-v3 canonical revision with source snapshot guards, explicit supersedes links and equivalent_ids. Existing bytes and meaningful old experiences remain intact regardless of age. Ordinary inspection, recall, capture matching, linked journals and derived summaries resolve validated aliases; explicit history still exposes the original record. Summaries regenerate on reads, so there is no second persisted summary to rewrite. Alias validation checks equivalent content, provenance, compatible metadata and source snapshots. If the canonical claim later changes meaning, old equivalences do not automatically become evidence for the new claim.

Only verified groups produce the concise announcement. An unchanged repeat is quiet. A late edit, publication failure or failed verification is reported as conflict, partial or unavailable as appropriate; retain may_have_written and pending_record_id diagnostics when publication is uncertain. Reinspect before claiming completion. Repetition is reduced in active recall, not by deleting archive files or reducing Git history. T15 must account for all revisions, equivalent IDs and derived dependencies when forgetting; mixed-client/two-device validation remains T21/T22.
