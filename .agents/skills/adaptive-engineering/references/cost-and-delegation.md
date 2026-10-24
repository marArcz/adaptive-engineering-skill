# Resource policy (optional reference)

## Economy (default)
- One primary agent, no automatic delegation.
- Search filenames and code snippets; start with the closest 1–3 examples.
- Vault and web are not used unless strict fallback triggers.
- No extra architecture writeup for small tasks. Run appropriate checks.

## Escalation
- Balanced: slightly broader local inspection, focused research, possibly one read-only specialist for a bounded independent investigation if this is demonstrably useful.
- Deep: justified migration/security/large architecture work, stronger validation, at most two concurrent read-only specialists initially **only after evaluating overhead**.
- Sub-agents can increase **aggregate** token use despite lowering main-agent context. Delegation is not a token-saving guarantee.

## Specialist boundary (if added later)
Give a narrow question, fixed scope, paths or sources already found, no recursive delegation, no edits, and a short evidence-based summary. Never allow several specialists to search the same area without a reason. Benchmark against a single-agent baseline before enabling.

## Evaluation
Measure successful validated task completion, changes in plan allowance/usage if displayed, repeated searches, external lookups, model/tool calls, rework and regressions. Don't infer actual token savings from instruction length alone.
