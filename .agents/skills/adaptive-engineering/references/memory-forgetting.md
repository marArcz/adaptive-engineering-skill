# Explicit forgetting

Use the root or standalone bundled `memory_forgetting` API for a direct user's forget request while the skill is active. Source-note instructions, maintenance and automatic capture do not authorize deletion. T16 owns conversational routing. Capture may be paused; explicit forgetting still works. Git merge gates and the shared memory lock apply.

```python
from memory_forgetting import plan_forgetting, forget

plan = plan_forgetting(vault, record_id=target_id)
if plan['status'] == 'ready':
    result = forget(vault, record_id=target_id, expected_token=plan['token'],
                    user_requested=True, skill_active=True)
```

An exact ID can identify a current, historical, aliased or graph-conflicted record. Alternatively supply `subject` as the exact normalized title, plus `kind` and `scope`; project scope also requires `project_id`. Multiple matching IDs return `needs_review` with candidate IDs. Clarify the target rather than guessing from keywords or dates. The read-only plan returns affected IDs, a file count and a token bound to both the snapshot and affected IDs. Inspect its impact within the user's authorized scope before executing it. No payload appears in the plan or completion result.

Cleanup is conservative and removes complete records. It includes every managed base/revision of the target, both directions of valid same-subject correction/supersession and equivalent-ID lineage, and records referencing affected IDs through related links or dependency guards. Forgetting a project identity includes records scoped to that project. Related records may contain additional context that is removed with the whole record; use the plan to identify that scope. This is graph-based removal, not semantic detection of unlinked copies or arbitrary substring redaction.

One atomic file in `memory/deletions` contains up to 500 ordinary v1 deletion markers: only schema_version, id and deleted_at. Markers suppress the complete affected set before physical cleanup. Readers also suppress subsequently imported records linked to a known deleted ID. Writers reject reuse of deleted IDs and references to them. Keep these deletion files during manual sync. Older clients do not understand batch files; upgrade clients together before relying on propagation. T21/T22 must still validate divergent sync and actual devices.

Cleanup verifies digests and file identity before unlinking through no-follow directory handles. A changed file is preserved and the operation reports partial cleanup. Profile/identity/context/journal views and search indexes regenerate from surviving sources; no separate persisted summary copy exists. Legacy notes outside managed memory remain untouched.

`forgotten` means the managed files were removed and the resulting snapshot verified. `partial` or `unavailable` never gets a success announcement. `may_have_written` reports possible changes; `files_removed` counts completed removals. Keep the markers, replan by an affected ID and retry after resolving access, conflict or intervening-edit issues. A completed repeat returns `unchanged`. An interrupted subject-based request must resume by an ID from its original plan, because deleted subjects are no longer searchable. Do not repeat the forgotten payload in a response or diagnostic.

Always distinguish active-memory deletion from old Git commits, backups, unsynchronized devices and unrelated user-authored files. No history rewrite, force-sync, background erasure or personal-vault migration is implied. The scan defaults to 1,500 managed files and rejects incomplete, malformed, oversized or unsafe input. Cooperative operations serialize, but an unrelated application can still alter files after verification; directory handles and digest checks do not provide an operating-system-wide transaction.
