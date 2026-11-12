# Selective experience journal

The root or standalone bundled `memory_journal` module provides journal, inspect_experience and related_experiences. It captures short sourced accounts of meaningful shared experiences, not per-turn logs. The trusted active workflow classifies significance and evidence; T16 owns invocation and T20 owns live selection-quality checks.

```python
result = journal(
    vault, 'Smaller release scope agreement',
    significance='decision',
    context='The user and assistant planned the release.',
    happened='They chose a smaller scope.',
    why='The smaller scope fit the available time.',
    outcome='A release plan was selected.',
    lesson='Smaller releases may be easier to verify.',
    sources=['The current planning conversation'],
    origin='user', flags=classified_flags, skill_active=True,
    scope='project', project_id=project_id, related_ids=[decision_id],
)
```

Only use such content when the event and source are actually available. Do not invent feelings, dialogue or inaccessible history. Direct user reports use origin user; available observed events use observation. Inference-only, hypothetical, source-instruction and external source origins cannot establish a shared event. A lesson may be inferred from a reported/observed event, but it stays separately labelled inferred and tentative. An absent outcome/lesson remains null rather than being invented. An outcome classification requires an outcome; a lesson classification requires a tentative lesson.

Significance values are decision, outcome, lesson and collaboration_feedback. Routine exchanges use routine and produce no entry. The stable subject describes the particular episode; do not manufacture a fresh subject for every repeated status turn. Actual subject/significance selection remains a caller responsibility, not an NLP classifier in this API. Existing T10 progress records can be updated separately when useful; journaling does not automatically duplicate them.

Entries use experience-kind v1 records with a readable Experience title prefix. Their Markdown body contains human-editable JSON with journal_version 1, significance, context, what_happened, why_it_mattered, observed_outcome and inferred_lesson. The lesson is null or an object with text, basis inferred and tentative true. Event metadata basis describes the event's provenance, not the certainty of the inferred lesson. This does not extend v1 frontmatter or create a second record store.

Subjects are limited to 160 characters; context and significance explanation to 400 each, the event to 600, observed outcome to 500 and lesson to 400. Total body length, including JSON labels, must not exceed 2,400 characters. Oversized input is rejected for re-summary rather than silently truncating evidence. Entries have no expiration; later consolidation and explicit forgetting belong to T14/T15.

All persistence uses T09/T06: explicit activation, source/exclusion flags, sensitive retain permission, capture settings, path boundaries, merge gating, conservative matching, revision preservation and verified outcomes. Accounts containing a tentative lesson also check inference policy inside the shared capture gate. Identical accounts reuse their logical ID; new provenance updates evidence only. Changed accounts under the same subject require review and explicit T13 correction rather than creating a competing version silently. No-change/rejected/uncertain results have no save announcement.

Project scope requires a registered current project. Related IDs must resolve to current available records. A project account may reference general records and its own project's records; a general account cannot silently absorb project evidence, and cross-project links require explicit scope reconciliation. Unavailable, non-current or conflicting references stop the proposal. Sources remain as supplied truthful descriptions or safe URLs; runtime path exclusions apply to the whole account, including lessons and provenance.

inspect_experience returns current provenance, the update token and a validated structured event. Existing v1 Markdown experiences remain inspectable as literal Markdown without inventing structured fields. related_experiences delegates bounded scoped/relationship search to T07 and returns pointers. Both label accounts past_experience and is_instruction false. Explicit history may retrieve older pointers under T07's exclusions; inspect the indicated file for a particular historical revision. Do not treat a historical account or inferred lesson as a standing instruction or independent evidence of assistant identity.

The repository's prepared live examples contrast a significant release decision with repeated routine status chatter. Synthetic helper tests do not establish that an agent always classifies significance, private details or inferred feelings correctly.
