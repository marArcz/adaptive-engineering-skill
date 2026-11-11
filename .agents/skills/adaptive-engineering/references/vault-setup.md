# Guided vault setup

Use this flow when the user runs plugin setup, asks to set up a vault, or accepts setup offered after a missing-vault error. It works from the installed plugin; a separate repository clone is unnecessary.

## Locate the bundled tools

- Anchor paths to the loaded skill location, not the current project or a guessed cache directory. The plugin root contains `.codex-plugin/plugin.json`, `init_vault.py`, `configure.py`, and `vault-template/`. From either bundled skill's directory (`.agents/skills/<name>/`), the root is three parent directories up.
- Verify these files exist. Use their absolute paths for commands, quoting paths through structured arguments where available. Do not scan the user's home directory or download and execute replacement scripts.
- Use an available Python 3.9+ interpreter (`python3`, `python`, or `py -3` as appropriate). If none is available, explain the requirement and resume after the user installs Python. Do not install it automatically.
- Standalone skill installations may omit the setup tools. In that case, request the extracted distribution path containing them; do not pretend the plugin bundle is present.

## Choose the vault

1. Check an explicitly supplied vault path first. Otherwise inspect `ENGINEERING_VAULT_PATH` and run the bundled `configure.py --show`. Environment configuration takes precedence over the saved per-user config.
2. If the effective vault exists and is readable, reuse it unless the user requested a change. Verify retrieval before reporting success. Do not rewrite configuration or seed existing folders on a repeated setup.
3. If no working destination is established, ask one concise question offering **Create a vault** (suggest `~/Dev/engineering-vault`, expanded using the user's actual home), **Use an existing folder** (request its path), or **Skip for now**. If the request already specifies create/reuse and a path, proceed without asking again. Choosing a destination authorizes its setup and the per-user configuration write.
4. For a stale/inaccessible path or invalid saved configuration, explain the specific problem and ask for the intended path or correction. Never silently replace an existing configuration. If an environment override points elsewhere, explain that it must be updated or unset in the running environment before the new saved path can take effect; do not edit shell profiles.

Keep the vault outside the plugin/cache and, by default, outside the current code repository so upgrades cannot remove learned knowledge. Do not create files merely because the plugin was installed. Skipping leaves coding available; learning and vault lookup need setup later.

## Create or connect

- **Create:** Check the chosen path. For a missing or empty directory, run `init_vault.py --path <absolute-path>` using the bundled script's absolute path. For a nonempty directory, do not seed or overwrite it; offer to connect it as an existing vault or choose a different location. Reject a path that is a file.
- **Connect:** Confirm the chosen directory is the intended vault and is readable. A general Obsidian vault need not contain `HOME.md`; preserve all existing files and explain that engineering folders will be created only when needed for learning. Missing engineering metadata alone does not require another confirmation.
- After successful creation or an explicit connection/reconfiguration choice, run `configure.py --vault <absolute-path>` using its absolute bundled path. It stores the path in `~/.adaptive-engineering/config.json` and preserves other config keys. If it rejects invalid existing JSON, stop and report it rather than overwrite that file.
- Do not pass `--git-init`, commit, push, or modify unrelated folders without a separate request. If filesystem permissions block setup, report the failed step and request only the needed access. Do not disable sandboxing or save to another location silently.

## Verify and finish

- Run `configure.py --show` after changing saved configuration. Run the installed `scripts/search_vault.py --query "engineering" --limit 1` with normal resolution to confirm the **effective** vault. Empty search results are valid; verify the reported vault path matches the selected destination, rather than assuming a successful config write defeats an environment override.
- Report the actual vault path and, if changed, configuration file path. State any unresolved access/override problems or partial success. Learning needs write access; do not claim a successful note save based on this read-only retrieval check.
- Tell users they can optionally open the folder in Obsidian, and can now request `learn <topic>` or `learn this`. Notes are saved under `research/candidates/`. If setup interrupted a learn request, resume that request once configuration works.
- This setup is per operating-system user and machine. It requires local filesystem tools; on a surface without those tools, explain that setup must run in a local Codex environment rather than inventing a vault path.
