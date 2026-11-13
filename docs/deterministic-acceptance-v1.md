# Deterministic acceptance v1

T19 verifies local script behavior using synthetic temporary vaults. The authoritative mapping is
[`tests/acceptance-matrix-v1.json`](../tests/acceptance-matrix-v1.json): each acceptance check lists
requirements, exact unittest IDs, the scope those tests establish and the remaining validation.
The source is the [MVP specification](https://www.notion.so/41558ec5244581fab0a0d560711a1f21).
The mapping covers R01–R10 and A01–A10/A12–A14. A11 is explicitly deferred.

## Reproduce the evidence

From a trusted source checkout or extracted distribution, with Python and Git installed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 run_acceptance.py \
  --output /tmp/acceptance-v1.json --markdown /tmp/acceptance-v1.md
```

Choose unused report paths; the runner refuses to overwrite existing reports. It discovers and runs
the complete suite once, rejects stale test references before execution, and records every test
outcome. A failed, skipped, expected-failure or unexecuted mapped test cannot count as passing
evidence; failed or skipped subtests also prevent a parent test from being reported as passed.
The report includes Python/platform details, fixture and matrix SHA-256 hashes, exact test IDs,
outcomes and the unittest log. It never claims full product acceptance.

Release CI runs this reporter and includes its JSON as a release asset. Extracted-bundle verification
runs the reporter again, then validates marketplace setup and all four standalone installation
layouts in temporary targets. This does not publish or install a live plugin when run locally:

```bash
python3 package_release.py build --tag v0.4.1-local-check --ref HEAD \
  --output /tmp/adaptive-engineering-local-check.zip
python3 package_release.py verify /tmp/adaptive-engineering-local-check.zip
```

The build uses tracked files from the selected Git tree. For changes awaiting commit, explicitly
stage only the intended files and supply the resulting `git write-tree` ID as `--ref`.

## Requirement traceability

| Requirement | Checks with local evidence | Main evidence |
| --- | --- | --- |
| R01: local persistence and continuity | A01, A14 | Isolated fresh Python process, empty/missing vaults, honest unavailable results |
| R02: bounded capture | A02, A03, A14 | Every policy row, excluded sources/material, sensitive request gates, tentative inference |
| R03: user, working style and experiences | A01, A03, A04 | Derived views, independent feedback, journal provenance and retry identity |
| R04: bounded retrieval | A01, A05 | Project scope, five excerpts, 12000-character boundaries, truncation |
| R05: portable project identity | A06, A07 | Two checkout paths, same-name and repository collisions, path rejection |
| R06: corrections and conflicts | A08, A12, A14 | Stale-token preservation, semantic conflict, real Git conflict, publication failures |
| R07: journal and consolidation | A04, A09 | Significant episodes, exact duplicates, distinct outcomes and old meaningful history |
| R08: explicit forgetting | A10 | Closure cleanup, derived-view removal, payload-free markers, interrupted deletion and resurrection prevention |
| R09: manual Git sync boundaries | A12 | Local conflicting branches and write gate; actual sync remains separate |
| R10: legacy compatibility | A13 | Before/after byte hashes, reviewed catalog fields, extracted installation checks |

The JSON matrix supplies executable test references for every row rather than treating this table
as independent proof.

## Versioned fixtures and cross-operation checks

[`tests/fixtures/acceptance-v1.json`](../tests/fixtures/acceptance-v1.json) defines synthetic preference
and correction text, two independent feedback episodes, two project decisions and an old experience.
It uses the existing `memory-contract.json`, `legacy-approved.md` and `legacy-candidate.md` fixtures.
`test_memory_acceptance.AcceptanceTests` exercises four combined workflows:

1. Persist a profile, derive a tentative working style and save scoped project decisions; start an
   isolated new Python process and reconstruct bounded activation and task context.
2. Consolidate duplicate preferences, correct the canonical fact, then forget its entire lineage and
   related feedback. Verify current/history search and derived views are clean, an unrelated old
   episode survives byte for byte, and legacy files remain unchanged.
3. Snapshot legacy approved/candidate notes, user-authored HOME/catalog overview and reviewed catalog
   JSON. Repeat setup, learn managed knowledge and a legacy candidate, forget the managed knowledge,
   then compare every snapshot hash and check approved/candidate retrieval and reviewed metadata.
4. Create an actual unresolved local Git merge. Verify capture stops without a save announcement,
   unrelated recall still works, conflicted text is excluded, and capture resumes after staging a
   resolution. No external remote is used.

Focused tests additionally exercise invalid metadata/graphs, unsafe paths/symlinks, duplicate retries,
stale external edits, failed publication/readback/fsync and partially completed deletion. Read-only
and permission failures use injected `PermissionError` at setup/publication boundaries so they are
reproducible under privileged test users; this is not a claim about a physically read-only device.
The evidence-report tests inject failures and skips into tiny independent suites to verify that
the report cannot turn those outcomes into passing acceptance evidence.

## Remaining acceptance

- **T20:** fresh-agent classification, hypothetical/inferred wording, source-as-data handling,
  relevance, selective journaling, semantic corrections and clarification, and legacy engineering
  behavior in an active host. A new Python process does not establish these behaviors.
- **T21:** independent local clones, sync/merge ordering and deletion propagation. Conflicting
  branches in one temporary repository do not establish all clone behavior.
- **T22/A11:** actual two-device manual sync, different device-local vault/workspace paths and a
  fresh active skill session. Neither local clones nor unit tests establish actual device acceptance.

Active managed deletion does not erase Git history, backups or other unsynced copies. Tests do not
use personal memory, user configuration or external remotes. Native Windows/macOS, live host discovery
and the GitHub Actions release job require their own evidence; the local suite exercises Linux
layouts and POSIX write behavior.
