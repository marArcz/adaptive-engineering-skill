# Derived profile and working-style summaries

The root or standalone bundled `memory_summaries.build_summaries` API regenerates bounded views from one validated current T07 snapshot. Summaries are not persisted as new records, are marked is_source false, and cannot become independent evidence. Calling again after a revision, supersession or deletion marker re-evaluates the sources; there is no stale summary cache to synchronize. T13/T15 still own actual correction/forgetting operations and cleanup of forgotten material in other source bodies.

```python
views = build_summaries(vault)
scoped_views = build_summaries(vault, project_id=project_id)
profile = build_summaries(vault, profile_only=True)
```

Only text is intended for model context. It is limited to 3,000 Unicode code points and eight entries, including labels, pointers, notices and separators. Smaller budgets are allowed; if mandatory labels cannot fit, text is empty and truncated true. Long source descriptions, titles, supporting pointer lists and bodies are explicitly shortened. items and source_ids are inspection diagnostics, not another copy to append to bounded context.

User-profile entries come from current user_fact/preference records. Assistant working-style entries come from assistant_identity records and structured collaboration-feedback journal entries. The stable view keys are user and assistant across contexts; they are labels for one assistant and one profile, not invented biographies. Missing sources produce empty views, without onboarding or seeded traits. A project ID adds a separately labelled project_adjustment view for that project; project evidence never becomes global or a separate persona. General-only profile inspection does not include project or assistant identity content.

Direct/source-supported working-style records remain literal recorded guidance with their original basis. Inferred assistant_identity records require at least two current related collaboration-feedback records in the same scope. Support must describe distinct events and have disjoint source descriptions; identical normalized event text or a reused source cannot inflate the count. Unsupported inferred identities are omitted from summary and startup task excerpts. A single collaboration-feedback event may remain an explicitly labelled feedback_not_trait account, but its tentative lesson is not promoted to a trait.

Matching tentative lesson text across at least two independent collaboration-feedback events can produce an inferred working-style entry. It quotes the recorded lesson rather than generating new psychology or feelings. It remains tentative regardless of the number of repetitions or sources; only explicit source evidence can be user-stated. Independence is a conservative structural check, not semantic proof of independent conversations or of a lesson's truth. The trusted workflow must select actual supporting evidence; T20 owns live semantic evaluation. Ordinary decision/outcome journal lessons are not automatically identity evidence.

Every item retains source record IDs, current revision IDs/digests, sources, basis and scope. Rendered text shows inspectable pointers and missing/excluded links. Current unresolved/superseded/deleted/conflicted/invalid sources follow T07 exclusions. Correction means correcting a source via the relevant operation and rebuilding the view, not editing a second summary copy. Inferred source deletion or loss of independent support removes the derived trait on the next read.

T08 startup context now uses these summaries within its existing bootstrap and total-character budgets. General bootstrap remains general-only; selected project preferences continue through explicitly scoped task recall. Current user instructions and tool permissions take precedence over all memory text. No summary authorizes tools or initiates capture. T16 owns automatic workflow invocation; live-agent behavior and actual two-device continuity remain later validation tasks.
