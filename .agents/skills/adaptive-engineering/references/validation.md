# Validation: right-sized, never fabricated

- Prefer the project's documented scripts/test suite and the package manager it already uses.
- Start with targeted tests for touched behavior, then relevant lint/typecheck/build checks. Expand for shared changes, migration effects, security and compatibility risks.
- Add or update focused tests when changed behavior or meaningful regression risk warrants them, following repository requirements. Avoid implementation-mirroring tests, unrelated coverage, and unnecessary scaffolding; see the required [code simplicity policy](code-simplicity.md).
- For unfamiliar stacks, inspect scripts and local CI workflows; never assume `npm`, `pytest`, `php artisan test`, etc. apply.
- Do not auto-install dependencies, contact external services, execute destructive database migrations, or run production commands without authorization.
- On a failure, investigate the cause once before retrying; don't rerun unchanged failing commands repeatedly.
- Distinguish `passed`, `failed`, `not run`, `blocked` and pre-existing failures. Never claim an unexecuted check passed.
- Keep reports short and actionable. Include changed files, local/fallback reference paths and validation outcome.
