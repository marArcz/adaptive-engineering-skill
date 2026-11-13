#!/usr/bin/env python3
"""Developer-only fresh-agent evaluation. Never invoked by unittest discovery."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / 'tests/fixtures/live-agent-v1.json'


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def snapshot(vault):
    """Only the explicitly synthetic vault; omit Git internals, never follow links."""
    files = {}
    if vault.is_symlink():
        raise ValueError('Synthetic vault root cannot be a symlink')
    if not vault.exists():
        return files
    for current, directories, names in os.walk(vault, followlinks=False):
        directories[:] = sorted(name for name in directories
                                 if name != '.git' and not (Path(current) / name).is_symlink())
        for name in sorted(names):
            path = Path(current) / name
            if path.is_symlink() or not path.is_file():
                continue
            raw = path.read_bytes()
            files[path.relative_to(vault).as_posix()] = {'sha256': digest(raw), 'text': raw.decode('utf-8')}
    return files


def changed_files(before, after):
    return {name: ('created' if name not in before else 'deleted' if name not in after else 'changed')
            for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)}


def git(vault, *args, ok=True):
    process = subprocess.run(['git', '-C', str(vault), *args], text=True, capture_output=True)
    if ok and process.returncode:
        raise RuntimeError(process.stderr)
    return process


def seed(vault, recipe):
    """Structured setup is not live evidence. IDs/contents are synthetic only."""
    from memory_capture import FLAGS
    from memory_operations import remember, register_project
    from memory_setup import setup_memory
    from memory_store import write_record
    if recipe == 'missing':
        return
    vault.mkdir()
    setup_memory(vault)
    flags = dict.fromkeys(FLAGS, False)
    sources = ['Synthetic live-evaluation fixture, not a conversation']
    if recipe == 'projects':
        for suffix in ('one', 'two'):
            result = register_project(vault, 'Cedar', sources, flags=flags,
                                      repository='https://example.org/eval/cedar-' + suffix,
                                      create_new=True, skill_active=True)
            if result['status'] != 'created':
                raise RuntimeError(result)
            saved = remember(vault, 'preference', 'Planning format',
                             'Use a checklist for Cedar ' + suffix + '.', sources,
                             origin='user', flags=flags, scope='project',
                             project_id=result['record_id'], skill_active=True)
            if saved['status'] != 'created':
                raise RuntimeError(saved)
    if recipe in ('duplicates', 'budget'):
        base = json.loads((ROOT / 'tests/fixtures/memory-contract.json').read_text())['base']
        count = 4 if recipe == 'duplicates' else 12
        for index in range(count):
            data = dict(base, id=f'00000000-0000-4000-8000-{index + 101:012}',
                        title='Fact: duplicated study plan' if index < 2 and recipe == 'duplicates'
                        else f'Fact: synthetic study topic {index}', sources=[f'Synthetic fixture source {index}'])
            body = ('Reserve a weekly study block.\n' if index < 2 else
                    ('The release succeeded.\n' if index == 2 else 'The release was postponed.\n'))
            if recipe == 'duplicates' and index >= 2:
                data.update(kind='experience', title=f'Experience: distinct outcome {index}',
                            created_at='1990-01-01T00:00:00Z', updated_at='1990-01-01T00:00:00Z')
            if recipe == 'budget':
                data.update(kind='knowledge')
                body = (f'Synthetic study topic {index}: ' + 'A bounded study observation. ' * 150 + '\n')
            result = write_record(vault, data, body)
            if result['status'] != 'created':
                raise RuntimeError(result)
    if recipe == 'legacy':
        for name in ('legacy-approved.md', 'legacy-candidate.md'):
            target = vault / 'knowledge' / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes((ROOT / 'tests/fixtures' / name).read_bytes())
        catalog = vault / 'references/github/catalog.json'
        catalog.parent.mkdir(parents=True)
        write_json(catalog, {'schema_version': 1, 'repositories': [{
            'id': 'reviewed', 'url': 'https://github.com/example/reviewed', 'status': 'approved',
            'reviewed_commit': 'synthetic-reviewed', 'verified_at': '2026-01-01',
            'important_paths': ['legacy/component.py'], 'custom': 'preserve'}]})
        catalog.with_name('GitHub Catalog.md').write_text('Synthetic reviewed overview; preserve.\n')
    if recipe in ('readonly', 'conflict'):
        result = remember(vault, 'preference', 'Existing planning style', 'Use short planning lists.',
                          sources, origin='user', flags=flags, skill_active=True)
        if result['status'] != 'created':
            raise RuntimeError(result)
    if recipe == 'readonly':
        for path in vault.rglob('*'):
            path.chmod(0o555 if path.is_dir() else 0o444)
        vault.chmod(0o555)
    if recipe == 'conflict':
        git(vault, 'init', '-b', 'main')
        git(vault, 'config', 'user.name', 'Synthetic Evaluator')
        git(vault, 'config', 'user.email', 'eval@example.invalid')
        note = vault / 'conflict.txt'
        note.write_text('base\n')
        git(vault, 'add', '.')
        git(vault, 'commit', '-m', 'synthetic base')
        git(vault, 'checkout', '-b', 'other')
        note.write_text('other\n')
        git(vault, 'commit', '-am', 'synthetic other')
        git(vault, 'checkout', 'main')
        note.write_text('main\n')
        git(vault, 'commit', '-am', 'synthetic main')
        if git(vault, 'merge', 'other', ok=False).returncode != 1:
            raise RuntimeError('expected real unresolved merge')


def prepare(destination):
    if destination.exists():
        raise ValueError('Choose an unused output directory; existing artifacts are preserved')
    fixture = json.loads(FIXTURE.read_text())
    destination.mkdir(parents=True)
    workspace = destination / 'workspace'
    workspace.mkdir()
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    process = subprocess.run([sys.executable, str(ROOT / 'install.py'), '--target', 'repo',
                              '--repo', str(workspace)], env=environment, capture_output=True, text=True)
    if process.returncode:
        raise RuntimeError(process.stderr)
    (destination / 'install.txt').write_text(process.stdout)
    (workspace / 'AGENTS.md').write_text(
        '# Synthetic live evaluation\n\n'
        'Use only the installed Adaptive Engineering skill in .agents/skills/adaptive-engineering/SKILL.md '
        'and its bundled helpers. ENGINEERING_VAULT_PATH is an explicit disposable synthetic vault. '
        'Never read personal memory, configuration, authentication files, other projects or home directories. '
        'Do not use network, delegate, commit, sync, approve notes, change permissions, install globally, '
        'or write outside this evaluation directory. Do not edit skill/helpers or use raw files as a '
        'persistence fallback.\n')
    vaults = destination / 'vaults'
    vaults.mkdir()
    for group, recipe in fixture['groups'].items():
        seed(vaults / group, recipe)
    installed = {p.relative_to(workspace).as_posix(): digest(p.read_bytes())
                 for p in sorted((workspace / '.agents').rglob('*')) if p.is_file()}
    try:
        version = subprocess.run(['codex', '--version'], text=True, capture_output=True).stdout.strip()
    except FileNotFoundError:
        version = 'unavailable'
    write_json(destination / 'manifest.json', {
        'schema_version': 1, 'fixture': fixture, 'fixture_sha256': digest(FIXTURE.read_bytes()),
        'installed_sha256': installed, 'source_head': git(ROOT, 'rev-parse', 'HEAD').stdout.strip(),
        'codex_version': version, 'model': 'CLI native default; no override',
        'effort': 'CLI native default; no override', 'actual_model': 'not established by JSONL',
        'note': 'Installed hashes establish tested working-tree bytes; source HEAD alone does not.',
    })
    write_json(destination / 'initial-vaults.json',
               {group: snapshot(vaults / group) for group in fixture['groups']})


def events_summary(raw):
    events = []
    invalid_lines = 0
    for line in raw.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            invalid_lines += 1
    tools = [event['item'] for event in events
             if event.get('type') == 'item.completed'
             and event.get('item', {}).get('type') in ('command_execution', 'mcp_tool_call', 'file_change')]
    completed = any(event.get('type') == 'turn.completed' for event in events)
    return {'turn_completed': completed, 'invalid_lines': invalid_lines, 'tools': tools,
            'errors': [event for event in events if event.get('type') in ('error', 'turn.failed')],
            'usage': [event['usage'] for event in events if event.get('type') == 'turn.completed']}


def run(destination, selected, timeout):
    manifest = json.loads((destination / 'manifest.json').read_text())
    cases = manifest['fixture']['cases']
    known = {case['id'] for case in cases}
    if set(selected) - known:
        raise ValueError('Unknown case IDs')
    evidence = destination / 'cases'
    evidence.mkdir(exist_ok=True)
    failed = [folder.name for folder in evidence.iterdir()
              if (folder / 'result.json').is_file()
              and json.loads((folder / 'result.json').read_text()).get('execution') == 'runtime_failed']
    blocked = f'Prior runtime failure in {failed[0]}; no retries in this run.' if failed else None
    for case in cases:
        if selected and case['id'] not in selected:
            continue
        folder = evidence / case['id']
        if folder.exists():
            continue  # Never silently rerun/overwrite evidence.
        folder.mkdir()
        if blocked:
            write_json(folder / 'result.json', {'execution': 'not_run', 'reason': blocked})
            continue
        vault = destination / 'vaults' / case['group']
        before = snapshot(vault)
        write_json(folder / 'before.json', before)
        prompt = (('Use the installed Adaptive Engineering skill with the explicit synthetic vault '
                   'configured for this turn.\n\n') if case['id'] != '16-stop' else '') + case['prompt']
        (folder / 'prompt.txt').write_text(prompt + '\n')
        (folder / 'host-instructions.md').write_bytes((destination / 'workspace/AGENTS.md').read_bytes())
        command = ['codex', 'exec', '--ephemeral', '--ignore-user-config',
                   '--skip-git-repo-check', '--json', '--sandbox', 'workspace-write',
                   '-C', str(destination / 'workspace'), '--add-dir', str(destination / 'vaults'),
                   '-o', str(folder / 'final.txt'), '-']
        env = dict(os.environ, ENGINEERING_VAULT_PATH=str(vault), PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        started = time.monotonic()
        try:
            with (folder / 'events.jsonl').open('w') as output, (folder / 'stderr.txt').open('w') as error:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, text=True, stdout=output,
                                           stderr=error, env=env, start_new_session=True)
                try:
                    process.communicate(prompt, timeout=timeout)
                    reason = ''
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.communicate()
                    reason = 'TimeoutExpired; terminated the process group before snapshotting'
            returncode = process.returncode
        except FileNotFoundError:
            returncode = None
            reason = 'FileNotFoundError'
        summary = events_summary((folder / 'events.jsonl').read_text())
        after = snapshot(vault)
        write_json(folder / 'after.json', after)
        result = dict(summary, command=command, seconds=round(time.monotonic() - started, 2),
                      returncode=returncode, files=changed_files(before, after),
                      execution='observed' if not reason and returncode == 0 and summary['turn_completed'] else 'runtime_failed',
                      reason=reason, verdict='unreviewed')
        write_json(folder / 'result.json', result)
        print(case['id'], result['execution'], len(result['tools']), 'tool events', flush=True)
        if result['execution'] == 'runtime_failed':
            blocked = f"Runtime failed in {case['id']}; inspect its exact events/stderr. No retries."
    return report(destination)


def report(destination):
    manifest = json.loads((destination / 'manifest.json').read_text())
    reviews_path = destination / 'reviews.json'
    reviews = json.loads(reviews_path.read_text()) if reviews_path.exists() else {}
    known = {case['id'] for case in manifest['fixture']['cases']}
    if set(reviews) - known:
        raise ValueError('Unknown reviewed case IDs')
    rows = []
    for case in manifest['fixture']['cases']:
        folder = destination / 'cases' / case['id']
        result = json.loads((folder / 'result.json').read_text()) if (folder / 'result.json').exists() else {
            'execution': 'not_run', 'reason': 'No live session executed'}
        review = reviews.get(case['id'], {})
        if review and (review.get('verdict') not in ('passed', 'failed', 'partial', 'not_run')
                       or not review.get('evidence') or not review.get('notes')):
            raise ValueError('Review needs verdict, evidence pointers and explanatory notes')
        if review.get('verdict') in ('passed', 'partial', 'failed') and result['execution'] != 'observed':
            raise ValueError('Unexecuted/runtime-failed session cannot establish a behavioral verdict')
        if review:
            pointers = review['evidence']
            if not isinstance(pointers, list) or any(
                    not isinstance(pointer, str) or Path(pointer).is_absolute()
                    or not (destination / pointer).resolve().is_relative_to(destination.resolve())
                    or not (destination / pointer).is_file() for pointer in pointers):
                raise ValueError('Review evidence must point to existing files inside this run')
        rows.append(dict(case, execution=result['execution'], reason=result.get('reason', ''),
                         changed_files=result.get('files', {}),
                         verdict=review.get('verdict', 'unreviewed' if result['execution'] == 'observed' else 'not_run'),
                         review=review, evidence=f"cases/{case['id']}/"))
    data = {'schema_version': 1, 'host': 'Codex CLI', 'manifest': manifest, 'cases': rows,
            'full_acceptance': 'not_claimed', 'gaps': manifest['fixture']['host_gaps'],
            'review_rule': 'Process success is not a semantic pass. Inspect prompts, tool traces, before/after files and final responses.'}
    write_json(destination / 'report.json', data)
    lines = ['# Synthetic live-agent evaluation v1', '',
             'Full product acceptance is not claimed. Each observed turn uses a fresh ephemeral session.', '',
             '| Case | Execution | Reviewed verdict |', '| --- | --- | --- |']
    lines += [f"| {row['id']} | {row['execution']} | {row['verdict']} |" for row in rows]
    lines += ['', *data['gaps'], '', data['review_rule']]
    (destination / 'report.md').write_text('\n'.join(lines) + '\n')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'report'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', default=[])
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    destination = args.output.expanduser().resolve()
    try:
        if args.action == 'prepare':
            prepare(destination)
        elif args.action == 'run':
            data = run(destination, args.case, args.timeout)
            return 1 if any(case['execution'] == 'runtime_failed' for case in data['cases']) else 0
        else:
            report(destination)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    sys.exit(main())
