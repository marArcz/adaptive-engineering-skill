# Code simplicity and evidence rules

Apply these rules to coding, debugging, refactoring, and code review in any stack. Follow applicable user and repository instructions; simplicity must preserve required behavior, security, and correctness.

## 1. Principles of simplicity

- Apply YAGNI: implement the requested behavior, not speculative future use cases or configuration.
- Apply KISS: choose the simplest complete solution that fits the project. Do not introduce factories, dependency injection layers, interfaces, or other abstractions without a concrete need. Respect established architecture when it applies.
- Keep changes local. Avoid unrelated refactoring, dependency additions, boilerplate documentation, and explanatory comments that merely restate the code. Document non-obvious contracts or decisions when needed.
- Add or update focused tests for changed behavior or meaningful regression risk. Follow repository requirements; avoid trivial tests that mirror implementation, unrelated coverage, and unnecessary test scaffolding.

## 2. Avoid defensive coding bloat

- Inspect actual language, compiler settings, and local contracts. In TypeScript, do not assume `strict` or `strictNullChecks` is enabled.
- Trust established internal guarantees. Avoid redundant runtime type/null checks where types and actual data flow already establish the condition; do not add guards solely because a value could hypothetically be invalid.
- Validate untrusted data at its boundary, such as requests, files, storage, or third-party responses, using existing validators where available. Static types and type assertions do not validate external data. Preserve domain invariants and security checks.
- Use optional chaining (`?.`) and nullish coalescing (`??`) when absence is valid and the default has defined meaning. Do not use them to hide required data or broken invariants. Use equivalent idioms in other languages.
- Avoid repeated guards around consecutive operations when one boundary check establishes their preconditions. Retain checks for distinct conditions the behavior actually requires.

## 3. Control flow and errors

- Prefer flat, readable control flow. Use guard clauses for real failure states or invalid inputs where they remove nesting; do not invent validations just to add early returns.
- Avoid deeply nested branches and ternary chains. Choose straightforward conditionals when they express the behavior more clearly than compact syntax.
- Do not wrap ordinary mappings, string operations, or formatting in local catches that silently return fallback values. Propagate failures to the appropriate existing handler unless meaningful local recovery or error translation is needed.
- Preserve established recovery contracts. Never turn a failure into fabricated success, mock data, or an arbitrary default.

## 4. Reuse and context

- Inspect relevant utilities, components, hooks, types, and dependencies before creating equivalents. Reuse and compose safe, applicable implementations.
- Add a helper or abstraction only when it materially clarifies the requested change or removes meaningful duplication. Avoid wrapper layers that merely forward calls.

## 5. Execution and evidence

- Inspect the affected code and closest precedents before editing. Keep planning proportional to the task and patches limited to the smallest coherent change.
- Locate existing helpers and APIs before relying on them. Verify uncertain signatures, configuration, and version-specific behavior through local source/types or the skill's allowed fallback workflow. Do not assume a symbol or dependency exists because its name seems plausible.
- Distinguish observed facts from assumptions. If a necessary fact cannot be verified, state the limitation; ask for clarification when it prevents a safe implementation. Never claim searches, checks, or outcomes that did not occur.
- Before finishing, review the patch for unnecessary branches, duplication, abstractions, silent fallbacks, and unrelated edits. Remove excess introduced by the change; do not expand this into surrounding cleanup.
