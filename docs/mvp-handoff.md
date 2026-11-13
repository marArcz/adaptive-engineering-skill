# Personal-memory MVP technical handoff

The implementation and local documentation are available for review. **Full MVP acceptance and T23 remain Blocked**: T22 actual second-device execution was deferred by the user, and Antigravity live behavior remains untested. Preparing a runbook, passing fixtures or producing an archive cannot close those gates. The [Notion project](https://www.notion.so/41558ec5244581ac8165d11fe45bbcbb) owns the [user guide](https://www.notion.so/41758ec524458120875bf66547af99b2), task progress and [acceptance and SDD handoff](https://www.notion.so/41758ec5244581858a80e317ce9d0d6f); this document is the repository technical handoff.

## Architecture and operating boundary

The loaded skill selects intent, scope, provenance and privacy flags from accessible conversation. Standard-library Python helpers validate structured operations; they are not an NLP classifier or a background transcript collector. Source records, immutable revisions and deletion markers live in a configured local Markdown vault. Derived user/assistant views and search context rebuild from surviving valid sources rather than persisting a second summary store.

| Area | Owning source |
| --- | --- |
| Record/persistence contract and privacy boundary | [Contract](personal-memory-contract-v1.md), [boundary](memory-boundary.md), `memory_contract.py`, `memory_boundary.py` |
| Active-only capture and portable settings | [Session route](../.agents/skills/adaptive-engineering/references/memory-session.md), `memory_session.py`, `memory_capture.py`, `memory_setup.py` |
| Revisions and current/history resolution | [Revision design](memory-revisions-design.md), `memory_store.py` |
| Bounded search/context and derived views | `memory_search.py`, `memory_context.py`, `memory_summaries.py` |
| Remember/project continuation/journals | `memory_operations.py`, `project_identity.py`, `memory_journal.py` |
| Correction/consolidation/forgetting | `memory_corrections.py`, `memory_consolidation.py`, `memory_forgetting.py` |
| General knowledge and legacy candidates | [Learning route](../.agents/skills/adaptive-engineering/references/learn.md), `memory_learning.py` (`learn_knowledge` and `save_candidate`) |
| Installation and reproducible distribution | [Setup](../SETUP-AND-ACCEPTANCE.md), `distribution.py`, `install.py`, `package_release.py` |

Vault resolution is explicit `--vault` where supported, then `ENGINEERING_VAULT_PATH`, then device-local `~/.adaptive-engineering/config.json`. `memory/capture-settings.json` is portable; local paths/configuration are not. Projects use portable UUIDs and optional credential-free repository identities. Names alone require clarification; workspace paths are runtime inputs only. Manual Git sync requires separate authorization and review. Runtime Git use is read-only merge inspection.

Capture defaults to `active` only while the skill is invoked. Pause allows recall and direct explicit forgetting; new remember/correction/journal/consolidation/managed-learning writes stay paused. Stop ends this session's memory loop. Missing/invalid settings, unavailable helpers, merge conflicts, unsafe input and uncertain publication must not produce a save claim or raw-file fallback. Verified capture is distinct from successful installation or read-only activation.

## Acceptance coverage and evidence limits

The [executable matrix](../tests/acceptance-matrix-v1.json) maps exact tests to R01–R10 and A01–A14. The table below separates evidence types; no row is a blanket product signoff. T20 uses synthetic direct user turns in an actual Codex CLI, T21 uses installed helpers in local clones, and T22 requires actual machines.

| Check | Deterministic/helper evidence | T20 live Codex observation | T21 one-host simulation | Actual device / remaining gate |
| --- | --- | --- | --- | --- |
| A01 continuity | Fresh Python process, profile/identity/project isolation | Fresh sessions reconstruct stored context | Installed beta recalls alpha data | T22 fresh session on another machine not run |
| A02 capture boundaries | Policy rows, exclusions, direct sensitive-retain gate | Privacy/source classification and eligible capture | Synthetic explicit captures only | Other host/general conversation quality unverified |
| A03 emerging identity | Empty views, independent support, tentative inference | Hypothetical claims excluded; working-style evidence inspected | Tentative derived trait survives sync then disappears with deleted support | Antigravity untested; no claim of human personality |
| A04 selective journal | Significance, provenance and retry identity | Significant event captured, routine chatter skipped | Experience and feedback records transferred | Broader semantic selection remains bounded to tested cases |
| A05 bounded recall | Five excerpts, 12,000-character total, truncation and scopes | Five excerpts within budget, omission disclosed | Scoped project/current-history recall | Device/host invocation not run |
| A06 portable identity | Two runtime checkout paths, no stored mapping | Project routing observed within fixture | Same UUID at different checkouts; shared content scanned | Actual differing machines not run |
| A07 ambiguity | Same-name/repository collisions | Clarification rather than silent project choice | Not an added semantic claim | Actual hosts unverified |
| A08 correction | Immutable history, stale tokens, unresolved claims | Clear correction and uncertain-claim handling observed | Correction propagates both ways | Actual-device propagation not run |
| A09 consolidation | Exact duplicates only; distinct/old experiences retained | Duplicate request and distinct-event handling observed | Not semantic paraphrase deduplication | No archive deletion or date-based expiry claim |
| A10 forgetting | Lineage/dependency closure, markers, partial cleanup retry | Paused explicit forgetting observed | Deletion closure and derived cleanup propagate | Unsynced copies/Git history/backups not erased; T22 not run |
| A11 two-device acceptance | Explicitly deferred in matrix | Local fresh sessions do not cover it | Two clones do not cover it | **Not run / Blocked** |
| A12 divergence and sync | Real textual conflict, semantic ambiguity | Conflict blocks saves; unrelated recall retained | Both semantic merge orders, explicit text resolution, no automatic sync | External network/auth failures and actual devices not run |
| A13 legacy compatibility | Byte snapshots, reviewed metadata, install checks | General/engineering learning routes preserve legacy files | Runtime shared data/config separation | Antigravity workflow untested |
| A14 honest failure | Missing/read-only injection, unsafe paths, partial publication | Actual denied save, missing vault, stop with zero tools | Runtime subprocess guard rejects unexpected commands | Native unsupported filesystems/hosts unverified |

Evidence milestones:

- **T19 / `6b66811`:** 161 passing offline tests; [deterministic evidence guide](deterministic-acceptance-v1.md). Fault injection is reproducible helper evidence, not proof of a physically read-only device.
- **T20 / `f5bb4c6`:** 25 fresh Codex CLI 0.168.0 turns in `t20/live-v2`; main review recorded 24 passed and case 13 partial because its preceding correction left no settled preference for positive paused recall. Preserve that partial observation. A separate focused `t20/paused-positive` run of cases 01, 12 and 13 passed main review and demonstrated settled preference recall while paused with no case-13 writes. This resolves that specific criterion without rewriting the original run. Antigravity was unavailable. Native default model/effort were requested; actual server model identity is unverified.
- **T21 / `3a9d679`:** Three focused tests and the full 169-test suite passed. Two installed runtimes, independent configs/clones and one local bare remote exercised corrections, deletion closure, both clean semantic merge orders and a real textual conflict. The trace distinguishes 120 actual read-only runtime Git inspections from 108 explicit harness Git commands. No automatic sync was added; no product helper defect was found.
- **T22 / `8735b0c`:** [Runbook](two-device-acceptance.md) and [blank JSON template](../tests/fixtures/two-device-evidence-v1.json) only. All 11 checks start `not_run`; no device observation exists. Actual execution remains user-deferred and Blocked.
- **T23:** User guide and acceptance/SDD record belong in Notion; local README/setup navigation and this handoff can be review-ready while overall dependency gates remain Blocked. No deployment, tag, published release or personal-vault migration is implied.

Raw synthetic run artifacts are under `/tmp/codex-sdd/adaptive-engineering/remaining-mvp/` in the current development environment. These temporary paths are developer evidence, not portable memory or durable release assets. Retain or export sanitized evidence before deleting that directory. The final Notion record should identify the final reviewed commit/tree, test reports and local archive hash rather than treating these temporary paths as permanent publication.

## Reproduce local checks and prepare a distribution

From a trusted checkout, choose unused output paths. Bytecode suppression preserves unrelated cache state:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 run_acceptance.py \
  --output /tmp/ae-handoff-acceptance.json --markdown /tmp/ae-handoff-acceptance.md
```

The acceptance report records exact tests, hashes and environment; it explicitly excludes full product signoff. The final reviewer should build from the intended committed tree or an explicitly staged tree containing only reviewed files. An uncommitted working tree is not the build input. Preserve unrelated changes when staging. For a committed tree:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 package_release.py build \
  --tag v0.4.1-local-handoff --ref HEAD --output /tmp/ae-local-handoff.zip
PYTHONDONTWRITEBYTECODE=1 python3 package_release.py verify /tmp/ae-local-handoff.zip
```

For precommit verification, the reviewer may stage the intended paths, run `git write-tree`, and pass that exact tree ID as `--ref`. Record the tree ID, archive SHA-256 and verifier output. Building does not tag, install into a live host, push or publish. Verify only trusted archives: verification executes packaged code. Extracted verification runs the complete suite/acceptance mapping and disposable setup across all four standalone target layouts plus marketplace resources; it does not certify live host activation or actual devices. The `v0.4.1-local-handoff` label does not change the manifest version.

## Recovery and unfinished acceptance

Safe managed/candidate publication currently requires Git, POSIX directory/no-follow handles, hard links, directory flushing and locking. Linux layout/synthetic runtime checks do not establish native Windows/macOS behavior. Setup/read-only tools can run separately; unsupported writes report unavailable. A `partial`, `may_have_written` or failed readback needs reinspection before retry or a completion claim.

Forgetting deletes complete managed records and linked lineage/dependencies, suppresses affected IDs with payload-free markers and rebuilds derived views. It does not remove Git history, backups, legacy notes, unlinked copies or an unsynchronized machine's unknown edits. Keep deletion markers and upgrade clients together; older clients cannot interpret batch deletion files. Consolidation reduces active duplication through aliases/revisions and preserves historical files.

When separately authorized, the next acceptance work is the deferred T22 procedure with two actual machines and the same reviewed artifact, plus unavailable host checks. Record failures and stopped runs; do not substitute clone fixtures for the missing evidence. Only reviewed actual observations can advance dependent T23/full MVP status.
