"""Append-only Markdown revisions; existing memory files are never replaced."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

import memory_contract as contract
from memory_boundary import validate_memory_content

SCRIPTS = Path(__file__).resolve().parent / '.agents/skills/adaptive-engineering/scripts'
sys.path.insert(0, str(SCRIPTS))
from vault_guard import capture_gate, has_conflict_markers

PREFIX = '<!-- memory-revision '
AREAS = ('profile', 'identity', 'experiences', 'projects', 'knowledge')


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def _record(text):
    if has_conflict_markers(text):
        raise ValueError('textual merge conflict')
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        raise ValueError('invalid record delimiters')
    header, body = text[4:].split('\n---\n', 1)
    data = {}
    for line in header.splitlines():
        key, sep, value = line.partition(':')
        if not sep or not key or key.strip() != key or key in data:
            raise ValueError('invalid or duplicate metadata')
        data[key] = json.loads(value, object_pairs_hook=_pairs)
    contract.validate({k: v for k, v in data.items() if k in contract.FIELDS}, body)
    validate_memory_content({'metadata': data, 'body': body})
    return data, body


def _serialize(data, body):
    return '---\n' + ''.join(f'{k}: {json.dumps(v, ensure_ascii=False)}\n' for k, v in data.items()) + '---\n' + body


def _safe(root, path):
    """Reject static symlink escapes, including dangling links."""
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('symlink in managed memory')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('unsafe managed destination')


def decode_record(raw, *, revision=False):
    """Decode a complete v1 record or revision envelope without vault access."""
    text = raw.decode('utf-8')
    envelope = None
    if revision:
        first, sep, text = text.partition('\n')
        if not sep or not first.startswith(PREFIX) or not first.endswith(' -->'):
            raise ValueError('invalid revision envelope')
        envelope = json.loads(first[len(PREFIX):-4], object_pairs_hook=_pairs)
        if set(envelope) != {'version', 'revision_id', 'parents'} or type(envelope['version']) is not int or envelope['version'] != 1:
            raise ValueError('unsupported revision envelope')
        contract._uuid(envelope['revision_id'], 'revision_id')
        parents = envelope['parents']
        if not isinstance(parents, dict) or any(not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v) for v in parents.values()):
            raise ValueError('invalid revision parents')
        for parent in parents:
            if parent != 'base':
                contract._uuid(parent, 'parent')
    data, body = _record(text)
    return data, body, envelope


def _nodes(vault, record_id):
    root = vault / 'memory'
    if not vault.is_dir() or not root.is_dir():
        raise ValueError('managed memory directory unavailable')
    _safe(vault, root)
    nodes = {}
    for area in (*AREAS, 'revisions'):
        folder = root / area
        _safe(vault, folder)
        if not folder.exists():
            continue
        for path in sorted(folder.rglob('*.md')):
            _safe(vault, path)
            raw = path.read_bytes()
            data, body, envelope = decode_record(raw, revision=area == 'revisions')
            if data['id'] != record_id:
                continue
            revision = envelope['revision_id'] if envelope else 'base'
            if envelope and path.name != f'{record_id}.{revision}.md':
                raise ValueError('revision filename disagrees with identity')
            if revision in nodes:
                raise ValueError('duplicate memory or revision ID')
            nodes[revision] = {'metadata': data, 'body': body, 'digest': _digest(raw),
                               'parents': envelope['parents'] if envelope else {}}
    return nodes


def read_record(vault, record_id):
    """Resolve a snapshot. Conflicts return no current metadata or body."""
    contract._uuid(record_id, 'id')
    nodes = _nodes(Path(vault), record_id)
    return resolve_nodes(nodes)


def resolve_nodes(nodes):
    """Resolve already validated nodes from one logical record."""
    if not nodes:
        return None
    ancestors = {}
    pending = set(nodes)
    while pending:
        ready = [key for key in sorted(pending) if all(p in ancestors for p in nodes[key]['parents'])]
        if not ready:
            raise ValueError('missing parent or cycle in memory revisions')
        for key in ready:
            parents = nodes[key]['parents']
            ancestors[key] = set(parents).union(*(ancestors[p] for p in parents))
            pending.remove(key)
    referenced = {p for n in nodes.values() for p in n['parents']}
    tips = sorted(set(nodes) - referenced)
    mismatches = []
    for child, node in nodes.items():
        for parent, digest in node['parents'].items():
            if digest == nodes[parent]['digest']:
                continue
            # A resolution may explicitly acknowledge the edited ancestor and child.
            acknowledged = any(child in ancestors[k] and n['parents'].get(parent) == nodes[parent]['digest']
                               for k, n in nodes.items())
            if not acknowledged:
                mismatches.append((child, parent))
    token = {k: nodes[k]['digest'] for k in sorted(nodes)}
    result = {'status': 'conflict' if len(tips) != 1 or mismatches else 'current',
              'token': token, 'tips': tips, 'changed_parents': mismatches}
    if result['status'] == 'current':
        node = nodes[tips[0]]
        result.update(metadata=node['metadata'], body=node['body'])
    return result


def _publish(directory, filename, raw):
    """Publish through anchored directory handles; never replace a destination."""
    handles = []
    temporary = None
    published = False
    try:
        # Refuse unsupported platforms rather than falling back to unsafe path writes.
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        root_fd = os.open(directory.parents[1], flags)
        handles.append(root_fd)
        memory_fd = os.open('memory', flags, dir_fd=root_fd)
        handles.append(memory_fd)
        directory_fd = os.open('revisions', flags, dir_fd=memory_fd)
        handles.append(directory_fd)
        temporary = '.memory-' + str(uuid.uuid4())
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory_fd)
        with os.fdopen(fd, 'wb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temporary, filename, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                    follow_symlinks=False)
            published = True
        except FileExistsError:
            pass
        os.fsync(directory_fd)
        saved_fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        with os.fdopen(saved_fd, 'rb') as saved:
            if saved.read() != raw:
                raise ValueError('revision ID collision or readback failure')
        return published
    except (OSError, ValueError, AttributeError, NotImplementedError) as exc:
        raise PublicationError(published) from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=handles[-1])
            except OSError:
                pass  # Ignored temporary files are never recalled as memory.
        for handle in reversed(handles):
            os.close(handle)


class PublicationError(Exception):
    def __init__(self, published):
        self.published = published


def write_record(vault, data, body, *, expected_token=None, revision_id=None, resolve=False,
                 project_roots=(), project_paths=(), device_identifiers=()):
    """Append a revision. Supply the returned snapshot token on updates/resolutions."""
    published = False
    try:
        vault = Path(vault)
        if not isinstance(data, dict):
            raise ValueError('metadata must be an object')
        contract.validate({k: v for k, v in data.items() if k in contract.FIELDS}, body)
        validate_memory_content({'metadata': data, 'body': body}, project_roots=project_roots,
                                project_paths=project_paths, device_identifiers=device_identifiers)
        if has_conflict_markers(body):
            raise ValueError('textual conflict in proposal')
        revision_id = revision_id or str(uuid.uuid4())
        contract._uuid(revision_id, 'revision_id')
        gate = capture_gate(vault)
        if not gate.allowed:
            raise ValueError(gate.message)
        current = read_record(vault, data['id'])
        token = current['token'] if current else {}
        # Explicit revision IDs make retries deterministic, even after a lost response.
        directory = vault / 'memory/revisions'
        _safe(vault, directory)
        if not directory.is_dir():
            raise ValueError('revision area missing; run additive vault setup')
        path = directory / f"{data['id']}.{revision_id}.md"
        _safe(vault, path)
        parents = expected_token or {}
        if not isinstance(parents, dict):
            raise ValueError('invalid snapshot token')
        envelope = {'version': 1, 'revision_id': revision_id, 'parents': parents}
        raw = (PREFIX + json.dumps(envelope, sort_keys=True) + ' -->\n' + _serialize(data, body)).encode('utf-8')
        if revision_id in token:
            if path.read_bytes() == raw:
                return {'status': 'unchanged', 'revision_id': revision_id, 'record': current}
            raise ValueError('revision ID already contains different content')
        if parents != token:
            raise ValueError('record changed since it was read')
        if current and current['status'] == 'conflict' and not resolve:
            raise ValueError('explicit conflict resolution required')
        if current and current['status'] == 'current':
            previous = current['metadata']
            if {k: v for k, v in previous.items() if k not in contract.FIELDS} != {k: v for k, v in data.items() if k not in contract.FIELDS}:
                raise ValueError('compatible metadata must be preserved')
            if previous == data and current['body'] == body:
                return {'status': 'unchanged', 'record': current}
        elif not current and set(data) - contract.FIELDS:
            raise ValueError('unknown metadata on new record')
        gate = capture_gate(vault)
        if not gate.allowed:
            raise ValueError(gate.message)
        published = _publish(directory, path.name, raw)
        saved = read_record(vault, data['id'])
        if saved is None or saved['token'].get(revision_id) != _digest(raw):
            raise ValueError('published revision failed verification')
        return {'status': 'conflict' if saved['status'] == 'conflict' else 'updated' if current else 'created',
                'revision_id': revision_id, 'record': saved}
    except PublicationError as exc:
        return {'status': 'failed', 'message': 'revision publication or readback failed', 'may_have_written': exc.published}
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return {'status': 'failed', 'message': 'memory write rejected; inspect record state, token, schema and vault access',
                'may_have_written': published}
