"""Read-only vault merge inspection and textual conflict detection."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaptureGate:
    allowed: bool
    state: str
    message: str


def capture_gate(vault: Path) -> CaptureGate:
    """Check Git state immediately before capture; failures block writes."""
    if not vault.is_dir():
        return CaptureGate(False, 'unavailable', 'Vault is unavailable; restore access and retry.')
    # Clear Git's repository overrides so the inspected directory determines scope.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env['GIT_OPTIONAL_LOCKS'] = '0'
    try:
        probe = subprocess.run(['git', '-C', str(vault), 'rev-parse', '--show-toplevel'],
                               capture_output=True, text=True, env=env)
        if probe.returncode:
            if 'not a git repository' in probe.stderr.lower():
                return CaptureGate(True, 'non-git', 'Non-Git vault; capture may proceed.')
            return CaptureGate(False, 'unknown', 'Cannot inspect vault Git state; restore Git access and retry.')
        result = subprocess.run(['git', '-C', str(vault), 'diff', '--name-only', '--diff-filter=U', '-z'],
                                capture_output=True, env=env)
        if result.returncode:
            return CaptureGate(False, 'unknown', 'Cannot inspect vault Git state; restore Git access and retry.')
        if result.stdout:
            return CaptureGate(False, 'unresolved', 'Capture paused: resolve the vault Git conflicts, then retry.')
        return CaptureGate(True, 'clean', 'No unresolved Git conflicts detected.')
    except OSError:
        return CaptureGate(False, 'unknown', 'Cannot inspect vault Git state; install or restore Git and retry.')


_CONFLICT = re.compile(r'^(?:<{7}(?:\s|$)|\|{7}(?:\s|$)|={7}\s*$|>{7}(?:\s|$))', re.MULTILINE)


def has_conflict_markers(text: str) -> bool:
    """Identify Git-style markers; semantic contradictions require separate handling."""
    return bool(_CONFLICT.search(text))
