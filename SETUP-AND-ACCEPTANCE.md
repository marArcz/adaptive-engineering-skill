# Adaptive Engineering v0.4 — Setup and acceptance checklist

## 0. Scope

- One shared `.agents/skills/adaptive-engineering/SKILL.md` for Codex and Antigravity.
- Project-first, stack-agnostic, **Economy** default. Zero automatic sub-agents.
- Local Obsidian vault + optional Git repository, consulted only on fallback.
- Candidate GitHub catalog, not an automatic code-fetcher.
- No guaranteed savings in the Codex five-hour allowance: benchmark.

## 1. Create vault

In the extracted distribution folder, replace the paths:

**Windows PowerShell**

```powershell
py init_vault.py --path "C:\Dev\engineering-vault" --git-init
py configure.py --vault "C:\Dev\engineering-vault"
```

**macOS/Linux**

```bash
python3 init_vault.py --path "$HOME/Dev/engineering-vault" --git-init
python3 configure.py --vault "$HOME/Dev/engineering-vault"
```

Open the folder in Obsidian (`Open folder as vault`). Initialize a private GitHub repository if desired, check all files for secrets, add your own `git remote add origin <YOUR_PRIVATE_REPO_URL>`, and commit/push manually. `--git-init` only creates a local `.git` directory, no remote and no push.

## 2. Install skill in a real project

**Windows**

```powershell
py install.py --target repo --repo "C:\Dev\my-project" --with-agents --dry-run
py install.py --target repo --repo "C:\Dev\my-project" --with-agents
```

**macOS/Linux**

```bash
python3 install.py --target repo --repo "$HOME/Dev/my-project" --with-agents
```

If `AGENTS.md` exists, it is preserved. Merge the relevant project-first policy from `AGENTS.example.md` yourself. Old v0.3 skill `web-engineering` is not removed, so disable it separately after validation to avoid duplicate activations.

## 3. Verify local scripts

```bash
python3 -m unittest discover -s tests -v
# Or: py -m unittest discover -s tests -v
```

After installing skill to an existing project:

```bash
python3 .agents/skills/adaptive-engineering/scripts/inspect_project.py .
python3 .agents/skills/adaptive-engineering/scripts/find_patterns.py --repo . --query "controller" --limit 5
```

If the second query finds no matches, choose a term applicable to your codebase.

Check vault retrieval from the extracted distribution (not the project if skill not installed yet):

```bash
python3 .agents/skills/adaptive-engineering/scripts/search_vault.py --query "architecture maintainability" --limit 3
python3 .agents/skills/adaptive-engineering/scripts/search_catalog.py --query "laravel" --limit 3
```

Expected: short JSON containing file paths, status and source metadata. No web requests.

## 4. Test the workflow in Codex and Antigravity

Open a **new agent session in the actual repository**. Invoke `$adaptive-engineering` in Codex or `/adaptive-engineering` where supported in Antigravity (or say "Use the adaptive-engineering skill").

**Test A — local precedence** (run in an existing project with a comparable implementation):

> Inspect the closest existing form or controller and explain exactly how you'd create another. No edits. Cite matching local paths. Don't use external references.

Pass: only local inspection, no vault, GitHub, web or sub-agents. The reported paths actually exist.

**Test B — knowledge fallback:**

> Propose a first implementation of a feature that does not yet exist in this repository. Inspect local precedents first. If there isn't one, check the configured vault and catalog before version-specific official documentation. Do not edit files.

Pass: scans locally first, consults only relevant vault/catalog files, treats `candidate` references as unverified, does not invent content.

**Test C — explicit research:**

> Compare the project's existing approach to current official guidance for its installed framework version. Research externally and report trade-offs; do not modify files.

Pass: local project inspection **and** appropriate current official verification.

**Test D — unknown stack:** Repeat A/B in Laravel, Go or another non-React project. Must not assume frontend conventions.

**Test E — cost:** Repeat a straightforward coding task with and without the skill using the same starting snapshot/model. Record usage information exposed by Codex/Antigravity, number of files read, research calls, tests and rework. The success measure is cost per correctly completed, validated task, not fewest tokens at any cost.

See `.agents/skills/adaptive-engineering/evals/scenarios.md` for ten acceptance scenarios. Unit tests validate scripts only; they do **not** validate live agent decisions.

## 5. Vault access if agents run sandboxed

The vault is deliberately **outside** your project. If an agent cannot read sibling directories, adjust its workspace/permission policy or make an explicit read-only copy available. Do not disable sandboxing globally just to make retrieval easier, and do not add the vault as an automatic context directory. Local config is per OS/user: Windows and WSL need separate setup.

## 6. After it works

- Remove/disable v0.3 to prevent conflicting instructions, after backing it up.
- Install v0.4 globally only if you want it available in all projects (`--target codex-global` and `--target antigravity-global` (or `antigravity-cli-global` for CLI) run separately).
- Add approved vault notes incrementally and record sources/framework versions.
- Keep sub-agents disabled until measurements show a clear benefit on large independent tasks.
