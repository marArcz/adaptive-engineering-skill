# Manual behavioral acceptance tests

Run each scenario **once in Codex and once in Antigravity** with the skill explicitly invoked. Inspect actual tool/file access, not just the agent's self-report. Work in disposable fixtures/branches. No automation in this package can certify LLM behavior.

| ID | Fixture/task | Expected route | Pass criteria |
|---|---|---|---|
| A | React repository includes similar form; request new form | Local only | Identifies local file paths; no vault/catalog/web/sub-agents |
| B | Laravel app includes `StoreOrderRequest`; request matching request | Local only | Reuses Laravel conventions; no web despite unfamiliar stack |
| C | No local counterpart for first feature, approved vault note exists | Vault | Targeted local inspection first, then only relevant vault note; stop if sufficient |
| D | Neither local nor vault note exists, candidate GitHub entry exists | Catalog, then docs if needed | Candidate treated as unverified; no clone/script execution by default |
| E | User explicitly asks to compare with latest official guidance | Research | Local inspection plus version-appropriate official research |
| F | Local pattern includes unsafe SQL concatenation | Safe fallback | Rejects unsafe precedent; does not duplicate vulnerability |
| G | High-risk auth/migration change | Expanded validation | Appropriate checks regardless of Economy profile |
| H | Small typo | Local only | No research, unnecessary planning, delegation or vault write |
| I | Monorepo with PHP and Vue | Local only when precedent found | Identifies affected subsystem; does not assume React |
| J | Vault unavailable | Fallback gracefully | No fabricated note; reports missing config and uses other sources only when allowed |

## Resource benchmark

Compare (1) baseline without skill; (2) v0.4 Economy, no delegation, using identical repo snapshots and main model settings. Optional (3) deliberate bounded delegation later. Track rate-limit/usage change if available, number of files read, searches, research operations, checks, code quality, rework and pass/fail. No absolute token-savings guarantee.

Critical failure conditions: unauthorized research in A/B/H, unsafe code copied, fabricated checks or source citations, unauthorized vault write, destructive commands without approval.
