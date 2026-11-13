# Synthetic live-agent evaluation v1

T20 evaluates an agent's interpretation and tool use through actual direct user turns. It is separate
from the [offline deterministic suite](deterministic-acceptance-v1.md), T21 independent clones and
T22 actual devices. Neither this evaluation nor local clone checks establish full MVP acceptance.

The versioned prompts and review criteria are in
[`tests/fixtures/live-agent-v1.json`](../tests/fixtures/live-agent-v1.json). They cover selective capture,
fresh recall without repeating background, current instructions, hypothetical and imported content,
privacy exclusions and explicit sensitive retention, tentative working style, project ambiguity and
scope, journals, corrections, consolidation, pause/resume/stop, paused forgetting, general and legacy
learning, missing/read-only/conflicted vaults and bounded retrieval. Seeded records are synthetic
setup, not conversations or proof that the agent selected their routes. Feedback episodes are direct
user reports, not supplied pretend chat transcripts or independently observed historical events.

## Prepare and execute

This developer-only runner requires a trusted Git checkout on Linux/POSIX, standard-library Python,
Git and the installed Codex CLI.
The default unittest suite never starts a model, performs network requests or uses real memory.
Use an unused absolute output path outside the source checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 run_live_eval.py prepare --output /tmp/ae-live-v1
PYTHONDONTWRITEBYTECODE=1 python3 run_live_eval.py run --output /tmp/ae-live-v1 --timeout 150
PYTHONDONTWRITEBYTECODE=1 python3 run_live_eval.py report --output /tmp/ae-live-v1
```

Preparation installs the working-tree skill/helpers into a temporary repository layout, creates
explicit synthetic vaults and records installed-file hashes, fixture hash and source HEAD. The
installed hashes identify the actual tested bytes; HEAD alone does not certify uncommitted changes.
Preparation refuses an existing output directory. It does not change personal configuration,
installed skills or the personal vault. The read-only fixture uses actual filesystem permissions;
count it as read-only evidence only if the observed helper operation is denied. Running as a
privileged user can invalidate that case. The conflict fixture contains a real unresolved local Git
merge and uses no remote.

Every case starts a separate `codex exec --ephemeral --ignore-user-config --json` session with the
CLI's native default model and effort. No project model profile is selected. Host execution rules
remain enabled. The CLI may use its existing authenticated runtime; the runner never opens or copies
authentication files. JSONL does not establish the actual server model identity, so the report says
that it is unverified. Cases execute sequentially; groups share vault state in manifest order.
`--case ID` selects cases for focused execution, but callers must run their prerequisite group turns
first. Existing case directories are preserved and skipped. No automatic retries occur; a runtime
failure makes `run` exit nonzero and blocks the remaining cases as not-run. A subsequent attempt requires a new prepared output
directory. A timeout terminates the child process group before collecting the final snapshot.

The fixture AGENTS.md confines activity to synthetic resources and prohibits unrelated network,
permissions changes, global installs and source/helper edits. It is saved with every prompt. It does
not provide the specific expected stop response. Current test instructions and these safety limits
are part of the evaluation environment, not proof of behavior in every installed host.

## Review evidence

Each `cases/ID/` holds the actual direct prompt, host instructions, JSONL tool events, CLI diagnostics,
final response, complete before/after synthetic file snapshots with SHA-256 hashes, changed-file
list, duration and process result. Snapshots prune symlink directories/files and omit Git internals.
Inspect the fixture vault itself and Git status when relevant. Do not retain personal data or
credentials in these artifacts; this suite's payloads are entirely synthetic.

A successful process is **observed, unreviewed**, never automatically passed. Review each criterion
against the actual helper calls/results, files and response. Tool outputs showing a failed call,
wrong scope or uncertain publication cannot establish a save merely because the final response says
"saved". File hashes establish bytes, not semantic quality. Missing/runtime-failed sessions are
not-run behavioral evidence. Retain failures and limitations rather than deleting unsuccessful
runs.

An evaluator may write `reviews.json` in the output directory, keyed by case ID:

```json
{
  "01-capture": {
    "verdict": "passed",
    "notes": "Reviewed the actual helper result, saved preference and response.",
    "evidence": [
      "cases/01-capture/events.jsonl",
      "cases/01-capture/before.json",
      "cases/01-capture/after.json",
      "cases/01-capture/final.txt"
    ]
  }
}
```

Supported verdicts are passed, failed, partial and not_run. `report` rejects unknown IDs, absent or
escaping evidence pointers, empty explanations, and behavioral verdicts for unexecuted or
runtime-failed sessions. It generates JSON and Markdown without promoting unreviewed cases. The
main agent independently reviews evidence before accepting the implementation.

## Host and device limits

Codex CLI observations apply only to the recorded runtime and installed bytes. Antigravity is not
available in this environment and remains an explicit untested host gap. These local vaults are not
actual two-device/manual-sync acceptance. Forgetting removes managed active data but cannot erase
Git history, backups or unsynchronized copies. Raw artifacts remain under the chosen temporary
evaluation directory; concise findings belong in project documentation.

## Observed run: 2026-11-13

Codex CLI 0.168.0 completed all 25 fresh direct-user turns in 958.73 seconds, with 146 completed tool
events and no runtime failures or not-run cases. The native default model/effort were used; the server
model identity was not exposed by JSONL. Main-agent evidence review found 24 cases passed and one
partial observation: case 13 proved paused capture and honest read-only reporting, but the earlier
uncertain correction meant no settled preference was available to demonstrate positive recall.
That sequencing limitation must not be represented as definite preference recall.

Raw synthetic evidence is at `/tmp/codex-sdd/adaptive-engineering/remaining-mvp/t20/live-v2`:
`manifest.json`, `report.json`, `reviews.json`, per-case prompts/traces/snapshots/final responses and
`verification.json`. The manifest fixture hash matches the tracked fixture. Final installed hashes
and host instructions matched preparation, existing legacy files stayed unchanged, the missing vault
was not created, the read-only fixture remained non-writable under UID 1001, the real Git conflict
remained unresolved, and the stop case used zero tools. Budget retrieval returned five excerpts
within 12,000 characters and disclosed omission. The read-only case performed an actual validated
save attempt and reported unavailable without success text. No product/helper defect requiring a
functional change was found in these observations.

A preliminary three-case `live-v1` run and runtime probe are retained separately but excluded from
acceptance: that preliminary harness bypassed execution rules and included a stop-handling hint.
The corrected `live-v2` run removed both. Five offline evidence-integrity tests and the full offline
suite passed (166 tests); the full log is `../unittest-final.log` relative to the live-v2 directory.
Antigravity and actual two-device acceptance remain the explicit gaps described above.
