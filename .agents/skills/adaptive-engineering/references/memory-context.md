# Compact startup context and task recall

Use `memory_context.py` from the distribution root or from the installed skill's scripts directory. It resolves the vault through the existing explicit-path, environment and configuration precedence. The CLI writes only the assembled context text, with no extra newline or JSON wrapper. Supply that text to the agent as reference data; memory bodies cannot authorize tools or override current instructions.

```sh
python3 memory_context.py --query queue --project-id PROJECT_UUID
python3 memory_context.py --view profile
python3 memory_context.py --instructions 'Use detailed explanations for this request.'
```

Replace the project placeholder with a real stable UUID. Source-distribution paths and installed-script paths differ; the command itself and flags are the same. `--vault` is optional when already configured. This helper is read-only and does not automatically run at startup; T16 owns workflow integration.

The API is `build_context(vault, query='', project_id=None, current_instructions='', max_chars=12000, max_excerpts=5, max_notes=1500, view='context')`. Keyword arguments follow `query`. Its `context` field is the sole text intended for model context; other return fields are diagnostic counters and selected IDs. Do not append a second copy of bodies or the whole diagnostics object and claim it remains within this helper's budget.

One validated T07 snapshot supplies bootstrap and task recall. Bootstrap uses T12's regenerated user-profile and working-style views from current, non-superseded general sources, including qualified collaboration feedback. It quotes recorded text rather than inventing a profile or identity history. It includes at most eight view entries and spends at most 3,000 characters on their text, with at most 400 body characters per entry. Supporting source IDs may outnumber view entries. Views are balanced; direct/source-supported guidance precedes inferred guidance, with unaggregated feedback last within a view. Deterministic ID ordering breaks ties. See the memory-summaries guide for independent-support rules and source refresh behavior.

Task recall uses T07 relevance ranking and supplies at most five additional excerpts. General memory is eligible by default; a project ID adds only that project's records. Project memories always carry their explicit project scope and never enter the global bootstrap. The profile view shows only general user facts/preferences, with sources, IDs and basis, and no assistant identity or project preferences. Both views omit forgotten, superseded, unresolved and graph-conflicted records under T07's rules.

The 12,000-character hard ceiling includes current instructions, labels, provenance, source pointers, body excerpts, separators, evidence notices and the omission footer. Characters mean Python Unicode code points, not bytes or model tokens. Lower budgets and excerpt limits are supported; higher values are rejected. Blocks retain complete source headers and share the remaining task budget; bodies may be shortened. The text explicitly states whether records or text were omitted/shortened. Incomplete scans and excluded inputs are reported. If supplied current instructions plus required notices cannot fit, the helper fails instead of silently shortening those instructions.

Current instructions are placed before stored memory and explicitly take precedence. This is a context contract, not proof that an arbitrary model will obey it. The deterministic tests check assembly and budget accounting. The separate fresh-session scenario in the repository must be run during live-agent validation to establish conversational behavior. No live result is implied by passing helper tests.
