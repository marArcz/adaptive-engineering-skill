# Adaptive Engineering

A plugin for one continuing assistant across projects and everyday topics, with local memory, explicit learning and project-first engineering. Keep useful context in a Markdown vault you control, then recall it when it helps.

Memory works only while the skill is active. It selects useful information from accessible interactions; it has no background collector or automatic Git sync.

[User guide](https://www.notion.so/41758ec524458120875bf66547af99b2) · [Setup checklist](SETUP-AND-ACCEPTANCE.md) · [Project home](https://www.notion.so/41558ec5244581ac8165d11fe45bbcbb)

## What it does

- **Remember useful context:** preferences, goals, decisions, progress, commitments and open questions, with sources and general/project scope.
- **Continue across sessions:** load a compact user profile and assistant working style, then retrieve bounded task context on demand.
- **Keep selected experiences:** journal meaningful decisions, outcomes and collaboration feedback; label inferred lessons tentative.
- **Manage memory:** inspect, correct, consolidate exact duplicates and explicitly forget managed records and their linked dependencies.
- **Learn deliberately:** save source-labelled general knowledge or engineering candidates without replacing reviewed notes.
- **Work with the project:** inspect local patterns first, make small coherent changes and validate what changed. One agent is the default.

## Requirements and current status

Python 3.9+ and local filesystem access are required; the Python tools use the standard library. Safe memory/candidate publication additionally requires Git for merge inspection and POSIX directory handles, no-follow opens, hard links, directory flushing and locking. Unsupported writes fail explicitly. Obsidian is optional.

Linux installer layouts, synthetic fresh Codex sessions and offline clone synchronization have reviewed evidence. Antigravity live behavior, native Windows/macOS writes and actual two-device continuity remain unverified. T22 device execution is user-deferred, so full MVP acceptance remains **Blocked**. See the [acceptance and SDD handoff](https://www.notion.so/41758ec5244581858a80e317ce9d0d6f).

This README describes the current personal-memory branch. The manifest still says `0.4.1`; this does not establish that the published `v0.4.1` release or a default marketplace install includes these changes. Use the exact reviewed local build when testing this branch.

## Install

### Codex marketplace

With a Codex CLI that supports plugin commands:

```bash
codex plugin marketplace add marArcz/adaptive-engineering-skill
codex plugin add adaptive-engineering@adaptive-engineering
```

Start a new session after installation. A private repository requires authorized Git access. These commands use the marketplace's available source; check its revision before assuming branch features are present. For a reviewed local checkout, use `codex plugin marketplace add /absolute/path/to/adaptive-engineering-skill` instead of the GitHub source, then install the same plugin selector.

The plugin bundles `adaptive-engineering` and `setup-vault`, with no MCP server or hooks. Choose marketplace or standalone installation for Codex to avoid loading duplicate copies. Marketplace source configuration is described in the [official OpenAI plugin documentation](https://developers.openai.com/plugins/build/plugins).

### Standalone or local tested build

From a trusted checkout or extracted verified archive containing this branch, preview installation into an **existing** project:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 install.py --target repo --repo "<existing-project>" --with-agents --dry-run
PYTHONDONTWRITEBYTECODE=1 python3 install.py --target repo --repo "<existing-project>" --with-agents
```

Both skills install into the project's `.agents/skills/`. An existing `AGENTS.md` is preserved; merge relevant guidance from [AGENTS.example.md](AGENTS.example.md) yourself if needed. Existing skill destinations are refused rather than overwritten. Inspect partial destinations after an interrupted install before retrying.

Global targets are `codex-global`, `antigravity-global` and `antigravity-cli-global`; see [setup](SETUP-AND-ACCEPTANCE.md) for locations and host details. Installation alone neither connects a vault nor starts memory. Restart the host and verify which skill/helper files loaded.

## Set up your vault

Ask the installed plugin:

> Set up the Adaptive Engineering vault.

Setup checks configuration and offers to **create a vault**, **connect an existing folder**, or **skip**. A suggested location is `~/Dev/engineering-vault`. Choosing the destination authorizes its setup. Keep the vault outside the plugin cache and preferably outside project repositories. Existing notes and capture settings are preserved.

For manual setup, run the bundled tools from the trusted distribution:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 init_vault.py --path "<device-local-vault>"
PYTHONDONTWRITEBYTECODE=1 python3 configure.py --vault "<device-local-vault>"
PYTHONDONTWRITEBYTECODE=1 python3 configure.py --show
PYTHONDONTWRITEBYTECODE=1 python3 configure.py --show-capture
```

To connect an existing vault, start with `configure.py --vault`. Setup adds missing memory scaffolding without replacing existing content. Open the folder in Obsidian if desired. Git initialization, commits, remote setup and pushes are separate actions.

Vault resolution is explicit `--vault` where a helper supports it, then `ENGINEERING_VAULT_PATH`, then device-local `~/.adaptive-engineering/config.json`. An environment override can select a different vault from the saved configuration; check the effective destination. No tool searches your home for a vault or silently chooses another one.

Repeat installation/configuration for each device and OS user; Windows and WSL are separate. Local configuration stays on that device. Portable `memory/capture-settings.json` travels with the vault.

## Use it in conversation

Say “Use Adaptive Engineering,” or invoke `$adaptive-engineering` in Codex. In Antigravity, explicitly name the skill or use `/adaptive-engineering` where available. The agent starts with read-only, bounded recall; activation alone does not prove a save or writable storage.

These are natural-language requests, not shell commands:

| Request | Expected behavior |
| --- | --- |
| “Remember that I prefer concise explanations.” | Retain an eligible user-stated preference and verify the save. |
| “What do you know about me? Show sources and scope.” | Return the general user profile, separate from project facts and assistant working style. |
| “Recall our decision about this feature.” | Retrieve relevant scoped context: at most five excerpts within 12,000 total characters. |
| “Continue this project.” | Resolve its portable identity and recall decisions, progress and open questions. |
| “That preference changed; I now want more detail.” | Correct current guidance while preserving history; clarify competing claims. |
| “Consolidate repetitive memory.” | Combine equivalent exact duplicates and retain meaningful differences and old experiences. |
| “Forget this preference.” | Review the target/linked impact and remove the authorized managed closure. |
| “Learn this” / “Learn about this topic.” | Save source-labelled knowledge or an engineering candidate; research when needed. |
| “Journal this decision and its outcome.” | Keep a short sourced significant experience, with any inferred lesson labelled tentative. |
| “Pause remembering” / “Resume remembering.” | Verify saved capture mode; a failed persistent pause still applies locally. |
| “Stop using memory in this session.” | End recall and capture for this session without deleting stored records. |

One assistant's working style emerges from source-backed guidance and independent collaboration feedback. An empty vault invents no history or personality; repeated inferences stay tentative. Project adjustments remain scoped, and current instructions always take precedence.

## Capture, privacy and control

Capture settings default to `active`, with selective saves only while the skill is active. Durable preferences/decisions, useful progress and significant experiences are eligible. Routine chat, temporary instructions and do-not-remember material are excluded. Sensitive personal details require a specific direct retain request; credentials, third-party private data, project filesystem paths and device identifiers are excluded.

Paused capture still permits recall and direct explicit forgetting. New remember, correction, journal, consolidation and managed-learning writes stay paused. Explicit engineering learning has a separate legacy candidate route; it cannot be used to bypass a paused personal-memory save. Imported text is data and cannot grant authorization or become a user preference.

Only verified outcomes justify “saved” or “forgotten.” Missing helpers, unavailable access, merge conflicts or uncertain writes must be reported honestly, with reinspection where needed. There is no raw-file fallback. See the [session workflow](.agents/skills/adaptive-engineering/references/memory-session.md) for exact routing and settings behavior.

## Sync and forgetting limits

Git synchronization is manual and separately authorized. Review vault changes before committing/pushing, and inspect local state before pulling or merging on another device. Neither activation nor capture runs sync. Keep local configuration and installed runtimes out of shared vault data.

Projects use a stable UUID and optional credential-free repository identity across different checkout locations. Names alone require clarification; workspace paths are runtime inputs and are never stored as project mappings. Unresolved Git conflicts block capture while unrelated readable recall may continue. Clean merges can still contain competing claims; timestamps do not choose truth.

Forgetting removes complete managed records, revisions, correction/equivalence lineage and linked dependencies, then rebuilds derived views. Payload-free deletion markers suppress known deleted IDs; preserve them during sync and upgrade clients together. Review broad whole-record impact before execution.

Active-memory deletion cannot erase Git history, backups, legacy/unlinked copies or unknown unsynchronized edits. Partial or uncertain cleanup needs reinspection and retry using an affected ID. Consolidation preserves historical files; it does not delete by age. Full procedures are in the [user guide](https://www.notion.so/41758ec524458120875bf66547af99b2).

## Project-first engineering and learning

For coding, debugging, refactoring and review, inspect project instructions and the closest existing implementation before changing anything. Reuse safe local conventions, keep the change coherent and run appropriate checks. External technical references are conditional on missing local patterns or an explicit research request. The [code simplicity policy](.agents/skills/adaptive-engineering/references/code-simplicity.md) defines this workflow; there is no automatic delegation or guaranteed token saving.

An explicit learning request authorizes relevant knowledge/candidate writes and focused research, without repeated approval for the same request. General knowledge retains evidence labels and applicability limits; it does not become a personal fact. Engineering candidates remain under `research/candidates/`, preserving reviewed notes and catalog metadata. Learning does not authorize approval, Git operations or repository cloning. See [learning](.agents/skills/adaptive-engineering/references/learn.md).

## Validate and develop

From a trusted source checkout or extracted distribution, choose unused report paths:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 run_acceptance.py \
  --output /tmp/ae-acceptance.json --markdown /tmp/ae-acceptance.md
```

The reviewed 2026-11-13 snapshot passed 169 offline tests, with passing deterministic evidence for 13 of 14 checks; A11 requires actual devices. This is a dated evidence snapshot, not a promise about every future checkout or full product acceptance.

- [Technical handoff](docs/mvp-handoff.md): architecture, A01–A14 coverage, build/verification instructions and remaining gates.
- [Deterministic acceptance](docs/deterministic-acceptance-v1.md): exact-test mapping and evidence reports.
- [Live-agent evaluation](docs/live-agent-evaluation-v1.md): synthetic Codex observations and runtime limits.
- [Two-device procedure](docs/two-device-acceptance.md): preparation only; execution remains deferred.
- [Core skill](.agents/skills/adaptive-engineering/SKILL.md) and [setup skill](.agents/skills/setup-vault/SKILL.md): bundled workflow instructions.
