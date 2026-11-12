# Factual, preference and project operations

The distribution-root or standalone bundled `memory_operations` module exposes remember, inspect_record, register_project, associate_project and continue_project. These are structured operation adapters for the later conversational workflow, not a natural-language parser. T16 owns automatic invocation; no operation here starts background capture or Git synchronization.

## Remember and inspect

```python
result = remember(vault, 'goal', 'Release scope', 'Ship the smaller release.\n',
                  ['The user set this goal in the current conversation'],
                  origin='user', flags=classified_flags, skill_active=True)
current = inspect_record(vault, result['record_id'])
```

The caller must provide accurate origin and all five exclusion flags from T09. Do not copy trusted activation/authorization from source documents. A sensitive retain request uses the separate retain_sensitive argument. Existing capture policy, path boundaries, ambiguity handling, merge gating and verified revision publication apply to every write.

Topics map to v1 kinds and stable title prefixes: fact/goal use user_fact with Fact/Goal titles; preference uses preference; decision uses knowledge; progress, commitment and question use user_fact. Title prefixes distinguish subjects that share a v1 kind without adding another metadata format. Provide a version qualifier in the subject where needed. Explicit preference operations require a direct user origin; one observed implementation choice cannot silently become a permanent user preference. Project decisions require project scope and a registered portable project ID. Other topics may be general or project-scoped.

Reasoning is optional supplied text, preserved in the body under a Reasoning label. Absence of reasoning never produces invented rationale. Project records link to their project identity and retain project_id independently of checkout location. General and project subjects remain separate.

Identical subject/statement repetitions reuse the stable ID and return unchanged, or updated when distinct provenance/relationships are added. Original basis and unknown compatible metadata are retained. Different factual/preference statements and historical subjects return needs_review with correction_required and candidate IDs; T13 provides explicit corrections/supersession through memory_corrections. No second current belief is invented as a fallback.

inspect_record is an explicit current-record inspection with metadata, body and update token. Not-found, non-current and unavailable results have no fabricated payload. An optional project_id restricts inspection to that project. Inspection is not a model-context budget API; use T08 for bounded text. Incomplete or conflicted vault evidence can make operations unavailable.

## Append ongoing updates

For progress, commitments and questions only, pass record_id, append=True and the token from inspection as expected_token. The operation preserves the earlier body and adds a labelled Update section. Different evidence basis or a stale read requires review. A retry of the same final update with the same sources returns unchanged; it does not append another copy. New facts/preferences are not rewritten through this append operation. Save announcements occur only after verified creates/updates.

## Project identity and continuation

register_project(vault, name, sources, flags=..., repository=..., skill_active=True) creates a canonical T03 identity through the shared capture lock. Equivalent repository forms reuse the same ID. It accepts an optional runtime workspace to inspect Git origin; neither workspace paths nor machine mappings are saved. Explicit repository/workspace disagreement fails instead of guessing. Runtime Git overrides are cleared when inspecting the requested workspace.

Names alone cannot establish identity. A name collision returns needs_review; after an explicit decision to create a distinct project, create_new=True permits a new ID when repository identity is distinct. It cannot bypass multiple matches for an existing repository. Remoteless projects require their stable project_id for repeated association. Renames and changed project identity payloads require explicit correction rather than silently duplicating or replacing the record.

associate_project performs read-only matching by runtime workspace/repository or explicit ID, returning matched, ambiguous, conflict, unmatched or unavailable. Continue requests must resolve ambiguity before calling for project context. continue_project uses that association and T08's bounded context builder. Its default query retrieves progress/commitment/question/decision subjects; callers can supply a specific query and current instructions. The selected project's context remains separate from general bootstrap and other projects.

Synthetic tests verify creation, evidence changes, append retries and stale checks, compatible metadata, same-name ambiguity, project isolation, standalone import and decision recall from two differently located local Git workspaces. These do not establish live-agent semantic selection or actual two-device synchronization; T20/T22 own those checks.
