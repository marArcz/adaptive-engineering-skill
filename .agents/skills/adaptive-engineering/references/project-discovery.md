# Targeted project discovery

- Determine the smallest affected area and look for project-level AGENTS.md and closer nested rules.
- Inspect relevant manifests and lockfiles before claiming installed framework versions; manifest ranges alone are not exact installed versions.
- Search the most likely local feature, controller, service, view, component or test directories by filename first.
- Search analogous usage patterns and inspect matching small sections; one or two consistent examples usually suffice.
- Expand gradually if no matching pattern appears. Mark uncertain observations rather than inferring an architecture from folder names alone.
- In a monorepo, detect the affected package/subsystem independently of the top-level language.
- Avoid scanning .git, node_modules, vendor, build, .env, secrets, generated code and unrelated repositories.
- Never infer that OOP classes are always best: use the project's idiomatic patterns, including composition and pure functions where appropriate.
