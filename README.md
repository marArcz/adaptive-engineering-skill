# Adaptive Engineering v0.4 — Codex + Antigravity + Obsidian/Git

An **implementable, stack-agnostic, project-first, cost-aware Agent Skill**. It replaces the direction of v0.3 without overwriting or automatically removing the older skill. No sub-agent is bundled: single-agent Economy is the default.

## Contents

- `.agents/skills/adaptive-engineering/SKILL.md`: compact project-first workflow
- `references/`: conditional fallback, project discovery, validation, cost/delegation
- `scripts/inspect_project.py`: bounded root-manifest detection
- `scripts/find_patterns.py`: targeted, bounded source search
- `scripts/search_vault.py`: local Obsidian Markdown search (compact results)
- `scripts/search_catalog.py`: GitHub metadata lookup **without network access**
- `vault-template/`: Obsidian Markdown template, candidate repo catalog and `.gitignore`
- `init_vault.py`, `configure.py`, `install.py`: non-overwriting setup tools
- `tests/`: stdlib deterministic tests; `evals/`: manual live-agent acceptance tests

## Requirements

Python 3.9+ (standard library only); Git and Obsidian optional for actual versioning/editing. The agent must have filesystem access to the relevant repo and vault; in sandboxed environments, allow access explicitly. No shell scripts download or execute code from the internet.

## Quick start (Windows PowerShell)

Extract ZIP and `cd` into extracted `adaptive-engineering-v0.4` folder. Adjust paths:

```powershell
# Preview then create the Obsidian vault (optional Git init; no push)
py init_vault.py --path "C:\Dev\engineering-vault" --dry-run
py init_vault.py --path "C:\Dev\engineering-vault" --git-init

# Configure local vault path in your user profile (not the project repo)
py configure.py --vault "C:\Dev\engineering-vault"
py configure.py --show

# Preview then install into an EXISTING project for both Codex and Antigravity
py install.py --target repo --repo "C:\Dev\my-project" --with-agents --dry-run
py install.py --target repo --repo "C:\Dev\my-project" --with-agents

# Test deterministic scripts
py -m unittest discover -s tests -v
```

In Obsidian: **Open folder as vault** → select `C:\Dev\engineering-vault`. The `.obsidian/` directory will be created by Obsidian. `init_vault.py --git-init` performs `git init` only: create a private GitHub repository/remote yourself and review files for secrets before committing or pushing.

If the project already has `AGENTS.md`, the installer preserves it; manually merge the short project-first policy from `AGENTS.example.md`. If the skill destination already exists it refuses to overwrite. If v0.3 `web-engineering` is installed, disable/remove that separately **after** checking v0.4 to avoid conflicting skill activations.

## macOS/Linux

Use `python3` instead of `py`, and change paths, for example:

```bash
python3 init_vault.py --path "$HOME/Dev/engineering-vault" --git-init
python3 configure.py --vault "$HOME/Dev/engineering-vault"
python3 install.py --target repo --repo "$HOME/Dev/my-project" --with-agents
python3 -m unittest discover -s tests -v
```

## Global installation (after repository tests)

```bash
python install.py --target codex-global
python install.py --target antigravity-global
# For the separate Antigravity CLI global location, instead use:
python install.py --target antigravity-cli-global
```

The installer targets `~/.agents/skills/adaptive-engineering/` for Codex , `~/.gemini/config/skills/adaptive-engineering/` for Antigravity App/IDE, and `~/.gemini/antigravity-cli/skills/adaptive-engineering/` for Antigravity CLI. Repository-local `my-project/.agents/skills/adaptive-engineering/` is recommended as a shared path. Agents may need a restarted/new session for discovery. Paths depend on environment: Windows and WSL have different home directories.

## Try it

Open the existing project in each coding agent and explicitly invoke the skill:

- Codex: `$adaptive-engineering Find the closest existing validation pattern and report paths only. Do not edit code.`
- Antigravity: `/adaptive-engineering Find the closest existing validation pattern and report paths only. Do not edit code.` (if available in your Antigravity interface; you can also explicitly say "Use the adaptive-engineering skill")

First test local-only behavior, then a missing-pattern case that requires the vault, then explicit current-doc research. See `.agents/skills/adaptive-engineering/evals/scenarios.md`.

## Script examples

```bash
python .agents/skills/adaptive-engineering/scripts/inspect_project.py .
python .agents/skills/adaptive-engineering/scripts/find_patterns.py --repo . --scope app --query "store" --limit 5
python .agents/skills/adaptive-engineering/scripts/search_vault.py --query "validation" --limit 3
python .agents/skills/adaptive-engineering/scripts/search_catalog.py --query "laravel project structure" --limit 3
```

Search scripts return compact local JSON. `--scope app` assumes that directory exists; use an appropriate directory for your project. The vault is discovered from `ENGINEERING_VAULT_PATH` environment variable or from `~/.adaptive-engineering/config.json` (or explicitly via `--vault`). Without those configurations, lookup reports an error rather than guessing.

## Design constraints

- Not automatically using web; the agent controls official-doc browsing only when allowed by the fallback policy.
- No automatic vault writes, Git commits or GitHub cloning/fetching.
- The repository catalog includes *candidate* URLs only; commits and versions are not pre-verified.
- Python unit tests verify local tools/installer. Agent selection and true Codex allowance savings need live testing; see evals.

## Official documentation references

- Codex skills: https://learn.chatgpt.com/docs/build-skills
- Antigravity skills: https://antigravity.google/docs/skills
- Obsidian help: https://help.obsidian.md/
