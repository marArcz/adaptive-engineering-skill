# Adaptive Engineering — Codex + Antigravity + Obsidian/Git

An **implementable, stack-agnostic, project-first, cost-aware Agent Skill**. No sub-agent is bundled: single-agent Economy is the default.

Coding, debugging, refactoring, and review require the separate [code simplicity and evidence policy](.agents/skills/adaptive-engineering/references/code-simplicity.md): minimal changes, justified validation, reuse, and verified assumptions.

## Contents

- `.agents/skills/adaptive-engineering/SKILL.md`: compact project-first workflow
- `references/`: code simplicity, explicit learning, conditional fallback, project discovery, validation, cost/delegation
- `scripts/inspect_project.py`: bounded root-manifest detection
- `scripts/find_patterns.py`: targeted, bounded source search
- `scripts/search_vault.py`: local Obsidian Markdown search (compact results)
- `scripts/search_catalog.py`: GitHub metadata lookup **without network access**
- `vault-template/`: Obsidian Markdown template, candidate repo catalog and `.gitignore`
- `init_vault.py`, `configure.py`, `install.py`: non-overwriting setup tools
- `tests/`: stdlib deterministic tests; `evals/`: manual live-agent acceptance tests

## Requirements

Python 3.9+ (standard library only); Git and Obsidian optional for actual versioning/editing. The agent must have filesystem access to the relevant repo and vault; in sandboxed environments, allow access explicitly. No shell scripts download or execute code from the internet.

## Codex marketplace installation

Add this repository as a marketplace, then install its plugin:

```bash
codex plugin marketplace add marArcz/adaptive-engineering-skill
codex plugin add adaptive-engineering@adaptive-engineering
```

Start a new Codex session after installation. You can also browse the marketplace through `/plugins`. Access to a private repository requires Git credentials with permission to read it.

For local development, run `codex plugin marketplace add /absolute/path/to/adaptive-engineering-skill` instead of adding the GitHub source. The marketplace is named `adaptive-engineering`; its single plugin uses the same name. The supported `.codex-plugin/plugin.json` manifest points at the existing `.agents/skills/` directory, keeping one skill source for marketplace and standalone installation.

The plugin includes no MCP server, hooks, or service connection. Choose marketplace installation or the standalone installer for Codex to avoid loading duplicate copies of the skill. The standalone installer remains available for Antigravity and repository-local use.

### Guided vault setup after installation

Run **Setup** for Adaptive Engineering in the plugin interface where available, or ask Codex:

> Set up the Adaptive Engineering vault.

The bundled onboarding skill checks your current configuration, then offers to create a vault (suggested location: `~/Dev/engineering-vault`), connect an existing folder, or skip. It runs the setup tools from the installed plugin, so users do not need to clone this repository or find its cache directory. Choosing a destination authorizes setup without another confirmation. A working configuration is reused on later runs.

The vault stays outside the plugin cache, and its path is saved in `~/.adaptive-engineering/config.json`. An existing `ENGINEERING_VAULT_PATH` environment variable takes precedence; the flow reports conflicts. Obsidian is optional. Setup does not initialize Git or publish anything.

After setup, ask `Use Adaptive Engineering to learn this` or `learn <topic>`. If learning is requested before setup, the agent offers this flow and resumes once the vault is ready. Setup requires Python and local filesystem tools; it does not run automatically just because the plugin is installed.

To refresh a Git-backed installation:

```bash
codex plugin marketplace upgrade adaptive-engineering
codex plugin add adaptive-engineering@adaptive-engineering
```

Restart Codex afterward. Marketplace setup follows the [official plugin packaging guide](https://developers.openai.com/plugins/build/plugins); this repository marketplace is separate from the public plugin directory.

## Quick start (Windows PowerShell)

Download the release ZIP and `cd` into its extracted `adaptive-engineering-<tag>` folder. Adjust paths:

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

If the project already has `AGENTS.md`, the installer preserves it; manually merge the short project-first policy from `AGENTS.example.md`. If the skill destination already exists it refuses to overwrite. If the legacy `web-engineering` skill is installed, disable/remove it separately **after** validating Adaptive Engineering to avoid conflicting skill activations.

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

## Learn and save knowledge

After configuring an existing vault, ask the agent:

- `$adaptive-engineering learn this` — summarize relevant supplied material or conversation into a note.
- `$adaptive-engineering learn <topic>` — research authoritative sources and save bounded findings.
- `$adaptive-engineering learn from <GitHub URL>` — save findings plus a repository catalog entry.

These are natural-language requests, not shell commands. The agent follows [the learning workflow](.agents/skills/adaptive-engineering/references/learn.md). Your request authorizes relevant writes without another confirmation. Notes go to `research/candidates/` and remain unapproved, searchable candidates. Repeated learning updates clearly matching candidates; approved notes are preserved. Commits and pushes require separate authorization. A missing or inaccessible vault must be resolved before saving.

## Script examples

```bash
python .agents/skills/adaptive-engineering/scripts/inspect_project.py .
python .agents/skills/adaptive-engineering/scripts/find_patterns.py --repo . --scope app --query "store" --limit 5
python .agents/skills/adaptive-engineering/scripts/search_vault.py --query "validation" --limit 3
python .agents/skills/adaptive-engineering/scripts/search_catalog.py --query "laravel project structure" --limit 3
```

Search scripts return compact local JSON. `--scope app` assumes that directory exists; use an appropriate directory for your project. The vault is discovered from `ENGINEERING_VAULT_PATH` environment variable or from `~/.adaptive-engineering/config.json` (or explicitly via `--vault`). Without those configurations, lookup reports an error rather than guessing.

## Design constraints

- Web research is permitted on the fallback branch or an explicit learning request.
- No automatic vault writes during ordinary engineering. Explicit learning authorizes relevant notes and GitHub catalog updates, but not approval, Git commits/pushes, or repository cloning/fetching.
- The repository catalog includes *candidate* URLs only; commits and versions are not pre-verified.
- Python unit tests verify local tools/installer. Agent selection and true Codex allowance savings need live testing; see evals.

## Publishing a release

The [release workflow](.github/workflows/release.yml) runs when a version tag is pushed. It runs the unit suite, builds an installable ZIP, tests the extracted bundle and installers, then publishes a GitHub Release with generated notes, `adaptive-engineering-<tag>.zip`, and `SHA256SUMS`. The archive includes the hidden `.agents/` skill and marketplace directories, `.codex-plugin/` manifest, icon assets, and vault template; it excludes Git history, workflows, and untracked files.

After committing and pushing the intended changes, tag the release commit:

```bash
read -r -p "Release tag (vMAJOR.MINOR.PATCH): " release_tag
git tag -a "$release_tag" -m "Release $release_tag"
git push origin "$release_tag"
```

Use `vMAJOR.MINOR.PATCH` tags. Adding a prerelease suffix such as `-rc.N` publishes a prerelease. The workflow uses the repository's built-in `GITHUB_TOKEN` with `contents: write`; no personal token is needed. Existing releases are not overwritten. Workflow execution and publication must be verified in GitHub Actions after pushing a tag.

On Linux, download both assets into the same directory and verify with `sha256sum -c SHA256SUMS` before extracting. On Windows, replace `<tag>` with the downloaded release's tag in `Get-FileHash .\adaptive-engineering-<tag>.zip -Algorithm SHA256` and compare it with `SHA256SUMS`.

## Official documentation references

- Codex skills: https://learn.chatgpt.com/docs/build-skills
- Antigravity skills: https://antigravity.google/docs/skills
- Obsidian help: https://help.obsidian.md/
