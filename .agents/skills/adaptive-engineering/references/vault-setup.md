# Guided vault setup

Use this flow when the user runs plugin setup, asks to set up a vault, or accepts setup offered after a missing-vault error. It works from the installed plugin; a separate repository clone is unnecessary.

## Locate the bundled tools

- Anchor paths to the loaded skill location, not the current project or a guessed cache directory. Both distribution modes provide the existing adaptive-engineering and setup-vault skills as siblings. In a standalone installation, the main skill's `scripts/` contains `init_vault.py`, `configure.py`, `memory_setup.py` and `vault-template/`. Prefer that complete directory. In a source/marketplace bundle these resources are at the distribution root, three parent directories above either `.agents/skills/<name>/` folder.
- Verify these files exist. Use their absolute paths for commands, quoting paths through structured arguments where available. Do not scan the user's home directory or download and execute replacement scripts.
- Use an available Python 3.9+ interpreter (`python3`, `python`, or `py -3` as appropriate). If none is available, explain the requirement and resume after the user installs Python. Do not install it automatically.
- Older standalone installations may omit setup resources. If neither location contains the required tools/template, report the missing resources and request the extracted distribution path or a separately authorized reinstall. Never substitute files from the active project.

## Choose the vault

1. Check an explicitly supplied vault path first. Otherwise inspect `ENGINEERING_VAULT_PATH` and run the bundled `configure.py --show`. Environment configuration takes precedence over the saved per-user config.
2. If the effective vault exists and is readable, reuse it unless the user requested a change. Run the bundled `init_vault.py --path <vault>` to add missing memory scaffolding without replacing existing files, then verify retrieval and the write check before reporting success. Preserve existing configuration and capture settings.
3. If no working destination is established, ask one concise question offering **Create a vault** (suggest `~/Dev/engineering-vault`, expanded using the user's actual home), **Use an existing folder** (request its path), or **Skip for now**. If the request already specifies create/reuse and a path, proceed without asking again. Choosing a destination authorizes its setup and the per-user configuration write.
4. For a stale/inaccessible path or invalid saved configuration, explain the specific problem and ask for the intended path or correction. Never silently replace an existing configuration. If an environment override points elsewhere, explain that it must be updated or unset in the running environment before the new saved path can take effect; do not edit shell profiles.

Keep the vault outside the plugin/cache and, by default, outside the current code repository so upgrades cannot remove learned knowledge. Do not create files merely because the plugin was installed. Skipping leaves coding available; learning and vault lookup need setup later.

## Create or connect

- **Create:** Check the chosen path. For a missing or empty directory, run `init_vault.py --path <absolute-path>` using the bundled script's absolute path. For a nonempty directory, connect it only when it is the intended vault; setup adds missing memory scaffolding and preserves existing files. Reject a path that is a file.
- **Connect:** Confirm the chosen directory is the intended vault and is readable. A general Obsidian vault need not contain `HOME.md`; preserve existing files. The configuration command adds missing memory folders, template, and capture settings without replacing existing content. Missing engineering metadata alone does not require another confirmation.
- After successful creation or an explicit connection/reconfiguration choice, run `configure.py --vault <absolute-path>` using its absolute bundled path. It stores the path in `~/.adaptive-engineering/config.json` and preserves other config keys. If it rejects invalid existing JSON, stop and report it rather than overwrite that file.
- Do not pass `--git-init`, commit, push, or modify unrelated folders without a separate request. If filesystem permissions block setup, report the failed step and request only the needed access. Do not disable sandboxing or save to another location silently.

## Verify and finish

- Run `configure.py --show` after changing saved configuration and `--show-capture` to inspect portable settings. The core skill invokes selective capture only during active sessions; setup installs no background hook and is not proof that a memory save occurred. For conversational pause/resume, use the verified memory_session controls. Run the main skill's `scripts/search_vault.py --query "engineering" --limit 1` with normal resolution to confirm the **effective** vault. Empty search results are valid; verify the reported vault path matches the selected destination, rather than assuming a successful config write defeats an environment override.
- Report the actual vault path and, if changed, configuration file path. State any unresolved access/override problems or partial success. Learning needs write access; do not claim a successful note save based on this read-only retrieval check.
- Tell users they can optionally open the folder in Obsidian, activate memory or request `learn <topic>`/`learn this`. General knowledge uses managed memory; engineering candidates remain under `research/candidates/`. Capture and candidate publication require Git for merge inspection and POSIX directory/no-follow/hard-link/locking operations; unsupported writes fail explicitly. Setup/read-only tooling can be used separately. If setup interrupted a learn request, resume it once configuration and required write capabilities work.
- This setup is per operating-system user and machine. It requires local filesystem tools; on a surface without those tools, explain that setup must run in a local Codex environment rather than inventing a vault path.
