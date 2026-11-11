"""Portable project identity. Workspace paths are used only while inspecting Git."""
from __future__ import annotations

import datetime
import json
import re
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from memory_boundary import validate_memory_content


def normalize_repository(remote: str) -> str:
    """Normalize supported network Git remotes, dropping user credentials."""
    if not isinstance(remote, str) or not remote or remote != remote.strip() or any(c.isspace() for c in remote):
        raise ValueError('repository: invalid remote')
    scp = re.fullmatch(r'(?:[^/@:]+@)?([^/:]+):(.+)', remote) if '://' not in remote else None
    if scp:
        host, path = scp.groups()
        port = None
    else:
        try:
            parsed = urlsplit(remote)
            if parsed.scheme.lower() not in ('https', 'ssh') or not parsed.hostname or parsed.query or parsed.fragment:
                raise ValueError
            host, path, port = parsed.hostname, parsed.path.lstrip('/'), parsed.port
            if port in (22 if parsed.scheme.lower() == 'ssh' else 443, None):
                port = None
        except ValueError:
            raise ValueError('repository: expected an HTTPS or SSH network remote') from None
    host = host.lower()
    if not re.fullmatch(r'[a-z0-9.-]+', host) or host.startswith('.') or host.endswith('.'):
        raise ValueError('repository: invalid host')
    if path.endswith('.git'):
        path = path[:-4]
    if not path or any(part in ('', '.', '..') for part in path.split('/')) or any(c in path for c in '?#\\'):
        raise ValueError('repository: invalid repository path')
    return f'https://{host}{":" + str(port) if port else ""}/{path}'


def repository_from_workspace(workspace: str | Path) -> str | None:
    """Read origin from Git; do not return or persist the workspace location."""
    path = Path(workspace)
    if not path.is_dir():
        raise ValueError('workspace: directory does not exist')
    try:
        check = subprocess.run(['git', '-C', str(path), 'rev-parse', '--git-dir'], capture_output=True, text=True, check=False)
        if check.returncode:
            raise ValueError('workspace: not an accessible Git repository')
        result = subprocess.run(['git', '-C', str(path), 'config', '--get', 'remote.origin.url'], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise ValueError(f'workspace: cannot run Git: {exc}') from exc
    if result.returncode == 1:
        return None
    if result.returncode:
        raise ValueError('workspace: unable to read Git origin')
    return normalize_repository(result.stdout.strip())


def _id(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError('project_id: expected lowercase UUID v4') from None
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError('project_id: expected lowercase UUID v4')
    return value


def new_project(name: str, repository: str | None = None) -> dict:
    _name(name)
    return {'id': str(uuid.uuid4()), 'name': name.strip(),
            'repository': normalize_repository(repository) if repository else None}


def _name(name: str) -> None:
    if not isinstance(name, str) or not name.strip() or any(c in name for c in '\n\r/\\'):
        raise ValueError('name: expected a nonempty single-line name without path separators')


def match_project(projects: list[dict], *, repository: str | None = None,
                  project_id: str | None = None, name: str | None = None) -> dict:
    """Return match, ambiguous, conflict, or unmatched; names never establish identity."""
    by_id = {}
    for project in projects:
        key = _id(project['id'])
        if key in by_id:
            raise ValueError('projects: duplicate project ID')
        by_id[key] = project
    remote = normalize_repository(repository) if repository else None
    remote_matches = [p for p in projects if remote and p.get('repository') and normalize_repository(p['repository']) == remote]
    if project_id:
        project_id = _id(project_id)
        if project_id not in by_id:
            return {'status': 'unmatched', 'candidate_ids': []}
        if remote_matches and any(p['id'] != project_id for p in remote_matches):
            return {'status': 'conflict', 'candidate_ids': sorted({project_id} | {p['id'] for p in remote_matches})}
        return {'status': 'matched', 'project_id': project_id}
    if len(remote_matches) == 1:
        return {'status': 'matched', 'project_id': remote_matches[0]['id']}
    if len(remote_matches) > 1:
        return {'status': 'ambiguous', 'candidate_ids': sorted(p['id'] for p in remote_matches)}
    names = [p['id'] for p in projects if name and p.get('name', '').casefold() == name.strip().casefold()]
    return {'status': 'ambiguous' if names else 'unmatched', 'candidate_ids': sorted(names)}


def serialize_project(project: dict, *, timestamp: str | None = None,
                      project_roots=(), device_identifiers=(), project_paths=()) -> str:
    """Create a v1 Markdown record; persist only through a validated writer."""
    project_id = _id(project['id'])
    name = project['name']
    _name(name)
    remote = normalize_repository(project['repository']) if project.get('repository') else None
    now = timestamp or datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        parsed = datetime.datetime.strptime(now, '%Y-%m-%dT%H:%M:%SZ')
        if parsed.strftime('%Y-%m-%dT%H:%M:%SZ') != now:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('timestamp: expected UTC YYYY-MM-DDTHH:MM:SSZ') from None
    metadata = {'schema_version': 1, 'id': project_id, 'kind': 'project', 'title': name,
                'scope': 'project', 'project_id': project_id, 'basis': 'user-stated',
                'state': 'current', 'created_at': now, 'updated_at': now,
                'sources': ['User-provided project identity'], 'related_ids': [], 'supersedes': []}
    body = {'name': name}
    if remote:
        body['repository'] = remote
    validate_memory_content({'metadata': metadata, 'body': body}, project_roots=project_roots,
                            device_identifiers=device_identifiers, project_paths=project_paths)
    return '---\n' + ''.join(f'{key}: {json.dumps(value, ensure_ascii=False)}\n' for key, value in metadata.items()) + '---\n' + json.dumps(body, ensure_ascii=False, indent=2) + '\n'


def parse_project(text: str) -> dict:
    """Read project identity records produced by serialize_project."""
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        raise ValueError('project record: invalid frontmatter')
    header, body = text[4:].split('\n---\n', 1)
    metadata = {}
    try:
        for line in header.splitlines():
            key, sep, value = line.partition(':')
            if not sep or key in metadata:
                raise ValueError('invalid or duplicate metadata')
            metadata[key] = json.loads(value)
        payload = json.loads(body)
        if type(metadata.get('schema_version')) is not int or metadata['schema_version'] != 1:
            raise ValueError('unsupported schema version')
        if metadata.get('kind') != 'project' or metadata.get('scope') != 'project':
            raise ValueError('not a project record')
        if metadata.get('state') != 'current':
            raise ValueError('project record is not current')
        project_id = _id(metadata.get('id'))
        if metadata.get('project_id') != project_id or not isinstance(payload, dict):
            raise ValueError('invalid project identity')
        if set(payload) - {'name', 'repository'} or 'name' not in payload:
            raise ValueError('invalid project body')
        _name(payload['name'])
        if payload['name'] != metadata.get('title'):
            raise ValueError('project name and title disagree')
        repo = normalize_repository(payload['repository']) if 'repository' in payload else None
        return {'id': project_id, 'name': payload['name'], 'repository': repo}
    except (ValueError, TypeError) as exc:
        raise ValueError(f'project record: {exc}') from exc
