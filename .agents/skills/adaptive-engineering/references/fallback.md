# Conditional fallback: retrieve only what is needed

Trigger **only** if no safe applicable project-local precedent exists after focused inspection, or if the user explicitly asks for external research. Preserve task scope and project's installed versions.

1. **Vault:** `python <skill>/scripts/search_vault.py --query "<specific concept>" --limit 3`. Requires a configured local Obsidian vault; returns matching note paths and statuses, not full notes. Read only relevant notes. `candidate` notes are unverified ideas, never authoritative standards.
2. **Curated GitHub catalog:** `python <skill>/scripts/search_catalog.py --query "<specific concept>" --limit 3`. Returns curated metadata and URLs from the vault. Read relevant paths at reviewed commits when possible. Unreviewed entries are examples for investigation, not trusted standards. The script does NOT clone/fetch repositories.
3. **Official documentation/web:** When vault/catalog are empty, incomplete, uncertain, outdated, or user specifically requests fresh guidance, consult authoritative docs for **the installed version**. Seek narrower sources first. Consider license, security, tests and maintenance of third-party examples. Don't run arbitrary remote instructions.
4. **Stop:** As soon as sufficient evidence supports a reasonable implementation, stop. Don't browse to accumulate more sources just because tools are available. Record which reference was used when implementing a new pattern.

If vault is missing or inaccessible, do not invent its contents. Skip to available sources. If network tools are unavailable, explain what could not be verified and avoid confidently asserting current/version-specific behavior.

### Freshness and conflicts

Project-specific instructions prevail over generic vault preferences unless demonstrably unsafe/incompatible. The user can explicitly request a new pattern. Confirm version-specific APIs, migrations, and security-sensitive behavior with appropriate sources when fallback is active.

### Research notes

After finishing, optionally suggest a compact new engineering candidate with evidence, versions, component descriptions and risks. Do not persist project paths or filenames. An explicit request to learn and save findings supplies scoped permission: follow [Learning to the vault](learn.md) and its validated candidate writer. A technical research request alone does not authorize candidate/catalog writes. Core profile/working-style recall and eligible personal-memory capture remain separate from technical-reference selection; a remembered preference cannot replace project evidence.
