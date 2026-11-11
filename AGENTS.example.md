# Repository engineering instructions

- Use the `adaptive-engineering` skill for coding, review and refactoring.
- Search this project's relevant source code and tests first; follow safe, applicable local conventions.
- Only consult the local engineering vault, curated GitHub catalog or external web when no applicable local precedent exists, or I explicitly request research.
- Keep source inspection focused, prefer existing dependencies, and avoid speculative refactoring.
- Read and follow the skill's `.agents/skills/adaptive-engineering/references/code-simplicity.md` policy for coding, debugging, refactoring, and review.
- Use one primary agent by default. Do not spawn sub-agents for routine tasks.
- Run appropriate checks, be truthful about results, and cite the local file patterns followed.
- Never modify the engineering vault without explicit authorization.
- An explicit `learn <topic>`, `learn from <URL>`, or `learn this` request authorizes relevant candidate notes and GitHub catalog updates; follow the skill's learning route. Approval, commits, and pushes require separate authorization.

## Project specifics (fill in only known values)

- Language/framework: [detect from project]
- Preferred package manager: [detect from lockfiles]
- Test/lint commands: [inspect project scripts]
- Feature-specific conventions: [optional]

## Optional knowledge vault

Configure the vault once per machine using `python configure.py --vault <path>` from the v0.4 bundle. Do not commit machine-specific absolute paths into this repository. Vault lookup occurs on fallback or an explicit learning request.
