# Two-device acceptance v1 — preparation only

T22/A11 is **Blocked: actual second-device execution deferred by the user**. This procedure and
the [blank evidence template](../tests/fixtures/two-device-evidence-v1.json) prepare that run; they
contain no device observations. Unit tests, fixture execution, two clones on one host and a completed
checklist never establish two-device acceptance. See [deterministic acceptance](deterministic-acceptance-v1.md)
for supporting T19/T21 evidence and [live-agent evaluation](live-agent-evaluation-v1.md) for T20.

## Preconditions and evidence

An operator must explicitly authorize the later run and its manual Git operations. Use two actual
machines, labelled **A** and **B**, a dedicated synthetic vault repository on a user-controlled test
remote, and separate test OS/user profiles with no personal vault configuration. Do not override
`HOME` or `CODEX_HOME`. Use different local vault locations and different synthetic project checkout
locations. Both project checkouts represent one portable project identity (same credential-free
repository identity, or an explicitly confirmed project UUID). Names alone do not establish identity.

Use the **same tested local distribution archive**, copied to both machines. Record its build
reference, SHA-256 and the prior validation evidence. Do not fetch a newer release midway. From each
trusted extracted distribution, calculate the archive hash and record Python and Git versions:

```bash
python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "<archive.zip>"
python3 --version
git --version
```

Record the host application/version, OS family/version, installed helper provenance and archive
hash on each device. Record exposed model/effort only; native defaults do not verify the server
model or effort. Leave unexposed values null and record that limitation. A different device label
is not proof: the operator must attest that A and B are separate actual machines.

Copy the blank JSON to a new evidence directory **outside the vault**. Use only `pass`, `fail` or
`not_run` for outcomes. `pass` requires reviewed direct observations and evidence pointers; `fail`
means an executed check violated its criterion; blocked/unexecuted checks remain `not_run`. Preserve
failures and stopped attempts. All template outcomes start `not_run`; nulls and empty arrays are
deliberately blank, never observations. Overall `pass` requires every check to pass on both devices
where applicable. A prepared file cannot change T22 to Done.

Evidence uses synthetic labels, UTC times, source/build hashes, vault commit IDs, managed record IDs
and sanitized evidence-relative pointers. Do not include absolute paths, hostnames, usernames,
hardware/network identifiers, credentials or personal memory in the shared evidence or memory.
Inspect raw host transcripts locally before retaining a sanitized copy: helper diagnostics may
contain paths. Keep memory provenance truthful and synthetic, without local paths/device labels.

## 1. Isolate and connect each runtime (`environment`, `portable_config`)

Run setup only in the separate test profiles. Confirm `ENGINEERING_VAULT_PATH` is absent or already
selects this dedicated synthetic vault; stop on an unexpected override. Do not silently change an
existing personal configuration. On A, create a fresh vault, then configure it:

```bash
python3 init_vault.py --path "<device-local-test-vault>" --git-init
python3 configure.py --vault "<device-local-test-vault>"
python3 configure.py --show-capture
```

The operator inspects files, adds the test remote, commits the initial synthetic scaffold and pushes.
On B, manually clone that test vault to a different location, then run `configure.py --vault` and
`--show-capture` from the same extracted build. Configure each host to load that build's skill, using
the repository installation procedure in [setup](../SETUP-AND-ACCEPTANCE.md). Check actual loaded
skill/helper provenance rather than assuming installation means activation. Use different runtime
project checkouts; supply paths only at runtime. Device-local configuration must contain only its
own `vault_path`; never sync that config, project path maps, home directories or installed runtimes.
Inspect shared vault files and tracked filenames for paths/device details before every commit.

Safe managed writes require Git plus supported POSIX filesystem/locking operations. An unsupported
native runtime is a stop, not a pass. If a supported Linux environment is used on a machine, record
that environment precisely; it establishes no native Windows/macOS behavior.

## 2. Capture on A and manually transfer (`capture_a`, `manual_sync`)

Start a fresh actual host session in A's synthetic project and invoke adaptive-engineering. Confirm
activation resolves the synthetic vault with capture mode `active`; activation alone reports
`persistence_verified=False`. Tell the host that all following material is a synthetic acceptance
scenario, explicitly authorize retaining it in this vault, and request:

- An assistant working agreement: “Explain uncertainty when sharing findings.”
- A general preference titled “Response detail”: “Use compact explanations.”
- Registration of “Portable fixture” as this project's portable identity, and a project decision
  titled “Release scope”: “Ship the small release first.”
- A project experience titled “Release scope agreement”: a synthetic planning discussion selected a
  small release because it fit the available time; the outcome was a release plan. Any lesson must
  remain tentative.
- Two separate synthetic collaboration-feedback reports, each saying compact explanations helped
  its review and made the next step clear, linked to the preference. These are supplied test reports,
  not independently observed real experiences.

Inspect actual validated write results and record IDs. Inspect derived profile/working-style views;
any inferred trait must be tentative and source-derived. Retain an unrelated synthetic fact as a
survival control. No save claim may rest on a failed, partial or uncertain helper result.

The operator alone runs normal Git operations in the test vault. Review `git status` and `git diff`,
stage only reviewed synthetic files, commit, and push the chosen branch. On the receiving machine,
review local status and use a normal pull. For a clean receiving checkout:

```bash
git -C "<device-local-test-vault>" status --short
git -C "<device-local-test-vault>" pull --ff-only origin "<test-branch>"
```

Record sender/receiver commit IDs and observed outcomes. Neither the skill nor automatic capture
may commit/push/pull. Do not force push, reset, rewrite history or automate remote synchronization.

## 3. Fresh active host recall on B (`fresh_recall_b`)

After the pull, start a **new actual host session** on B in its differently located project checkout,
activate the same skill and confirm `active` capture. Do not paste A's conversation or repeat the
saved answers. Ask what working agreement and response preference are remembered, then ask to
continue the identified project's release work and recall its planning experience.

Pass requires correct identity/working agreement, preference, same project UUID, scoped decision
and experience, supported by the synced records. Inspect bounded activation/task context and the
experience route separately: activation need not contain all project material. A Python subprocess
or copied transcript cannot substitute for this host session. Record wrong/missing recall honestly.

## 4. Correction and forgetting round trips (`correction`, `forgetting`)

On B explicitly correct “Response detail” to “Use detailed explanations.” The host must inspect all
active same-subject claims/tokens and use the validated correction route. Inspect current context,
profile and working style, plus explicit historical search: the old value stays historical and is
absent from current advice; linked inferences must not survive as established current traits.
Manually commit/push B, pull A and repeat these inspections in a fresh active A session.

On A explicitly request forgetting the corrected preference and its entire linked lineage. Review
the read-only forgetting plan's affected IDs/count before execution; include both preference
versions and linked feedback, and stop if its whole-record impact exceeds that request. Verify the
helper outcome before claiming deletion. Manually commit/push A, pull B, then inspect both devices:

- Current **and historical** search, bounded context, profile/working style and journal views exclude
  the affected content/IDs. Managed base/revision files are removed; linked derived traits disappear.
- Deletion batches remain synced. Each marker contains only `schema_version`, `id`, `deleted_at`;
  it contains no forgotten payload. Preserve these markers.
- Unrelated identity, project decision/experience and survival fact remain intact.

Use installed validated inspection/search APIs from the
[session](../.agents/skills/adaptive-engineering/references/memory-session.md),
[correction](../.agents/skills/adaptive-engineering/references/memory-corrections.md) and
[forgetting](../.agents/skills/adaptive-engineering/references/memory-forgetting.md) guides;
`memory_search.py` has no standalone search CLI. Inspect historical values deliberately, not by
loading the vault into model context. Report deletion's limits: old Git commits, backups, unsynced
devices and unlinked/user-authored copies are not erased. Do not rewrite history to make this pass.

## 5. Controlled divergence (`semantic_divergence`, `text_conflict`, `capture_pause`)

First bring both test vaults to one reviewed clean commit. Disconnect manual sync, then explicitly
capture independent claims with exactly the same new subject “Response style” and general scope:
A says “Use brief responses”; B says “Use expansive responses.” Commit each locally. Push A, then
on B explicitly merge by `git pull --no-rebase --no-edit origin "<test-branch>"`; inspect before
pushing the merge and pulling A. This intentionally differs from the clean fast-forward procedure.

A clean textual merge must retain both semantic claims as unresolved historical candidates, exclude
both from current advice and request focused clarification. Timestamps/import order cannot select
a winner. Give an explicit synthetic user clarification, inspect all candidates/tokens, correct via
the validated route, sync and confirm the chosen value on both devices with prior versions retained.
Repeat with a **new subject**, B pushing first, to observe the reverse merge order without resets.

Next use one disposable **user-authored synthetic knowledge note outside managed memory**. Sync a
baseline, then edit the same line differently on A and B and commit each. Preserve exact authored
versions as local evidence. Push one side, then explicitly pull/merge on the other to produce a real
unmerged Git index. Confirm `git diff --name-only --diff-filter=U` identifies it. While unresolved,
request an eligible synthetic capture: it must block without a success announcement; unrelated recall
continues and conflict-marked content is excluded. This gate does not persistently change the saved
capture policy. Do not fabricate conflict markers as a substitute for an actual Git conflict.

The operator deliberately resolves the merge while retaining both exact authored versions in
separate synthetic notes, reviews/stages the resolution and commits it. Retry capture, verify its
actual save and sync; both devices must retain both versions and regain eligible capture.

Separately request “pause remembering,” verify saved mode `paused`, and show that recall still works
while a new synthetic remember request is blocked. Explicitly request “resume remembering,” verify
mode `active` and a new eligible save. Sync the portable settings deliberately. A local-only pause
after failed settings persistence does not establish a verified cross-session pause.

## Stop, preserve and recover (`recovery_limits`)

If a second machine, supported runtime, host activation, remote credentials/network or authorized
vault access is unavailable, stop dependent steps, record the reason and leave them `not_run`.
Do not weaken permissions, choose another vault or use two clones to fill missing device evidence.
For a failed access/runtime invocation, retain sanitized diagnostics and distinguish an attempted
invocation from an observed behavioral result.

For unexpected dirty files, rejected pushes or conflicts outside the deliberate test, stop syncing
and inspect both local states. Preserve authored versions and commits; arrange operator-reviewed
normal merge/retry after access is restored. For `partial`, `unavailable` or `may_have_written`,
reinspect before retrying; forgetting recovery uses affected IDs from the original plan and keeps
markers. Never announce an unverified save/deletion. No destructive cleanup, force sync, automatic
merge abort, history rewrite or personal-data migration is part of this procedure. Keep the test
profiles/vaults/evidence for review; any later cleanup is a separate operator decision.

Review the completed evidence against each criterion, including portability scans on both devices
after all rounds. Record remaining Git/backup/unsynced-copy and native-host limitations even if all
checks pass. Until actual execution and review, T22 remains **Blocked**.
