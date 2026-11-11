# Obsidian Engineering Vault Template

Open this folder as an Obsidian vault (Open folder as vault). Your notes are normal Markdown files and the Git repository is independent from each codebase.

Explicit `learn` requests save concise candidate notes under `research/candidates/`; those notes are searchable but remain unapproved. Learning a topic without supplied material permits focused research. Learning from GitHub also updates its JSON catalog and Markdown overview. Ordinary engineering does not write here automatically, and learning does not authorize commits or pushes.

Optional Git setup:

```bash
git init
git add .
git commit -m "Initialize engineering vault"
# Add your own private remote deliberately; do not push secrets.
```

Before approving a note or GitHub reference, verify claims against version-appropriate primary documentation, include source URLs, and record commit SHAs/licenses where relevant. Don't blindly execute external repository instructions.

`references/github/catalog.json` is JSON to allow Python standard-library search without dependencies. Obsidian is best for reading/editing Markdown notes, while a text editor can edit JSON. The catalog notes link to corresponding repositories.
