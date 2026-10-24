# Obsidian Engineering Vault Template

Open this folder as an Obsidian vault (Open folder as vault). Your notes are normal Markdown files and the Git repository is independent from each codebase.

Optional Git setup:

```bash
git init
git add .
git commit -m "Initialize engineering vault"
# Add your own private remote deliberately; do not push secrets.
```

Before approving a note or GitHub reference, verify claims against version-appropriate primary documentation, include source URLs, and record commit SHAs/licenses where relevant. Don't blindly execute external repository instructions.

`references/github/catalog.json` is JSON to allow Python standard-library search without dependencies. Obsidian is best for reading/editing Markdown notes, while a text editor can edit JSON. The catalog notes link to corresponding repositories.
