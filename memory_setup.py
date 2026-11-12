"""Add portable memory scaffolding to a vault without replacing user files."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

AREAS = ('profile', 'identity', 'experiences', 'projects', 'knowledge/general', 'revisions')
POLICY = Path('memory') / 'capture-settings.json'
DEFAULT_POLICY = {
    'schema_version': 1,
    'capture': 'active',
    'boundaries': {
        'durable_preferences_goals_decisions': 'capture',
        'useful_progress_commitments_questions': 'capture',
        'significant_shared_experiences': 'capture',
        'inferences': 'tentative',
        'temporary_or_do_not_remember': 'exclude',
        'sensitive_personal_details': 'explicit_request',
        'credentials_and_third_party_private_data': 'exclude',
        'project_filesystem_paths': 'exclude',
    },
}


def check_writable(vault: Path) -> None:
    if not vault.is_dir():
        raise ValueError(f'Vault folder does not exist or is not a directory: {vault}')
    try:
        with tempfile.TemporaryFile(dir=vault):
            pass
    except OSError as exc:
        raise ValueError(f'Vault is not writable: {vault}: {exc}') from exc


def setup_memory(vault: Path) -> None:
    check_writable(vault)
    for area in AREAS:
        (vault / 'memory' / area).mkdir(parents=True, exist_ok=True)
    template = vault / 'memory' / 'templates' / 'record.md'
    template.parent.mkdir(parents=True, exist_ok=True)
    try:
        with (Path(__file__).resolve().parent / 'vault-template' / 'memory-record.md').open('rb') as src, template.open('xb') as dest:
            shutil.copyfileobj(src, dest)
    except FileExistsError:
        pass
    policy = vault / POLICY
    try:
        with policy.open('x', encoding='utf-8') as output:
            json.dump(DEFAULT_POLICY, output, indent=2)
            output.write('\n')
    except FileExistsError:
        read_policy(vault)


def read_policy(vault: Path) -> dict:
    try:
        data = json.loads((vault / POLICY).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Cannot read capture settings: {exc}') from exc
    if (not isinstance(data, dict) or type(data.get('schema_version')) is not int
            or data['schema_version'] != 1 or data.get('capture') not in ('active', 'paused')
            or not isinstance(data.get('boundaries'), dict)):
        raise ValueError('Invalid or unsupported capture settings; inspect them before retrying')
    return data


def set_capture(vault: Path, mode: str) -> None:
    check_writable(vault)
    data = read_policy(vault)
    data['capture'] = mode
    path = vault / POLICY
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
            json.dump(data, out, indent=2)
            out.write('\n')
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
