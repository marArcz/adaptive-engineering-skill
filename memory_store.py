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
        if not isinstance(envelope, dict) or type(envelope.get('version')) is not int:
            raise ValueError('unsupported revision envelope')
        fields = {'version', 'revision_id', 'parents'}
        if envelope['version'] in (2,3):
            fields |= {'dependencies', 'inherit_from'}
            if envelope['version']==3:
                fields.add('equivalent_ids')
                equivalents=envelope.get('equivalent_ids')
                if not isinstance(equivalents,list) or not equivalents:
                    raise ValueError('invalid equivalent identities')
                for key in equivalents:
                    contract._uuid(key,'equivalent_id')
                if len(set(equivalents))!=len(equivalents):
                    raise ValueError('duplicate equivalent identity')
            dependencies = envelope.get('dependencies')
            if not isinstance(dependencies, dict):
                raise ValueError('invalid dependencies')
            for key, token in dependencies.items():
                contract._uuid(key, 'dependency')
                if not isinstance(token, dict) or not token:
                    raise ValueError('invalid dependency snapshot')
                for revision, digest in token.items():
                    if revision != 'base':
                        contract._uuid(revision, 'dependency revision')
                    if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):
                        raise ValueError('invalid dependency digest')
            inherited = envelope.get('inherit_from')
            if inherited is not None and inherited not in dependencies:
                raise ValueError('invalid inherited metadata source')
        elif envelope['version'] != 1:
            raise ValueError('unsupported revision envelope')
        if set(envelope) != fields:
            raise ValueError('unsupported revision envelope')
        contract._uuid(envelope['revision_id'], 'revision_id')
        parents = envelope['parents']
        if not isinstance(parents, dict) or any(not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v) for v in parents.values()):
            raise ValueError('invalid revision parents')
        for parent in parents:
            if parent != 'base':
                contract._uuid(parent, 'parent')
    data, body = _record(text)
    if envelope and data['id'] in envelope.get('equivalent_ids',[]):
        raise ValueError('self alias is invalid')
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
                               'parents': envelope['parents'] if envelope else {},
                               'dependencies': envelope.get('dependencies', {}) if envelope else {},
                               'equivalent_ids': envelope.get('equivalent_ids',[]) if envelope else []}
    return nodes


def read_revision_record(vault, record_id):
    """Resolve a snapshot. Conflicts return no current metadata or body."""
    contract._uuid(record_id, 'id')
    if read_deletions(Path(vault)):
        from memory_search import memory_snapshot
        snapshot = memory_snapshot(vault)
        if snapshot['incomplete']:
            raise ValueError('deletion scan incomplete')
        if record_id in snapshot['deleted']:
            return None
    nodes = _nodes(Path(vault), record_id)
    return resolve_nodes(nodes)


def decode_deletions(raw, name):
    """Atomic batches contain only the original payload-free v1 markers."""
    value = json.loads(raw, object_pairs_hook=_pairs)
    if name.endswith('.batch.json'):
        contract._uuid(name[:-11], 'deletion batch')
        if not isinstance(value, list) or not 1 <= len(value) <= 500:
            raise ValueError('invalid deletion batch')
        markers = value
    else:
        markers = [value]
    contract.validate_collection([], markers)
    if not name.endswith('.batch.json') and name != markers[0]['id'] + '.json':
        raise ValueError('invalid deletion identity')
    return {marker['id'] for marker in markers}


def read_deletions(vault):
    """Fail closed on damaged, unsafe or unbounded deletion metadata."""
    directory = vault / 'memory/deletions'
    _safe(vault, directory)
    if not directory.exists():
        return set()
    if not directory.is_dir():
        raise ValueError('deletion area is not a directory')
    deleted = set()
    count = 0
    def failed(error):
        raise error
    for folder, dirs, files in os.walk(directory, onerror=failed, followlinks=False):
        for name in dirs:
            _safe(vault, Path(folder) / name)
        for name in files:
            if name.startswith('.'):
                continue
            count += 1
            if count > 1500:
                raise ValueError('deletion scan limit exceeded')
            path = Path(folder) / name
            _safe(vault, path)
            with path.open('rb') as source:
                raw = source.read(128 * 1024 + 1)
            if len(raw) > 128 * 1024:
                raise ValueError('oversized deletion metadata')
            deleted.update(decode_deletions(raw, name))
    return deleted


def read_record(vault, record_id, *, history=False):
    """Inspect semantic current state; explicit history can expose superseded payloads."""
    raw = read_revision_record(vault, record_id)
    if raw is None or raw['status'] == 'conflict':
        return raw
    from memory_search import memory_snapshot
    snapshot = memory_snapshot(vault)
    if snapshot['incomplete']:
        raise ValueError('semantic record scan incomplete')
    canonical=snapshot['aliases'].get(record_id,record_id) if not history else record_id
    current = snapshot['resolved'].get(canonical)
    if current is not None and canonical!=record_id:
        current=dict(current,requested_id=record_id,canonical_id=canonical)
    if current is None:
        return None
    if current['metadata']['state'] != 'current':
        return dict(current, status='historical') if history else {
            'status': 'not_current', 'token': current['token'], 'state': current['metadata']['state']}
    return current


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
        result.update(metadata=node['metadata'], body=node['body'], dependencies=node.get('dependencies',{}),equivalent_ids=node.get('equivalent_ids',[]))
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
        if directory.name not in ('revisions', 'deletions'):
            raise ValueError('unsupported managed publication area')
        directory_fd = os.open(directory.name, flags, dir_fd=memory_fd)
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
                 project_roots=(), project_paths=(), device_identifiers=(), dependencies=None, inherit_from=None, equivalent_ids=None):
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
        if data['id'] in read_deletions(vault):
            raise ValueError('deleted memory ID cannot be reintroduced')
        current = read_revision_record(vault, data['id'])
        if dependencies is None and current and current['status']=='current' and current.get('dependencies'):
            dependencies=current['dependencies']
        if equivalent_ids is None and current and current['status']=='current' and current.get('equivalent_ids'):
            equivalent_ids=current['equivalent_ids']
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
        if dependencies is not None:
            envelope.update(version=2, dependencies=dependencies, inherit_from=inherit_from)
        if equivalent_ids:
            envelope.update(version=3,dependencies=dependencies or {},inherit_from=inherit_from,equivalent_ids=sorted(equivalent_ids))
        raw = (PREFIX + json.dumps(envelope, sort_keys=True) + ' -->\n' + _serialize(data, body)).encode('utf-8')
        if len(raw)>128*1024:
            raise ValueError('record exceeds the supported bounded-reader size')
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
            if not dependencies or inherit_from not in dependencies:
                raise ValueError('unknown metadata on new record')
            inherited = read_revision_record(vault, inherit_from)
            if inherited is None or inherited['status'] != 'current' or {k:v for k,v in data.items() if k not in contract.FIELDS} != {k:v for k,v in inherited['metadata'].items() if k not in contract.FIELDS}:
                raise ValueError('compatible metadata must be inherited unchanged')
        gate = capture_gate(vault)
        if not gate.allowed:
            raise ValueError(gate.message)
        decode_record(raw, revision=True)
        deleted = read_deletions(vault)
        references = {data['id'], *data['related_ids'], *data['supersedes'],
                *(dependencies or {}), *(equivalent_ids or []),
                *([data['project_id']] if 'project_id' in data else [])}
        if references & deleted:
            raise ValueError('write references deleted memory')
        for key, expected in (dependencies or {}).items():
            dependent = read_revision_record(vault, key)
            if dependent is None or dependent['status'] != 'current' or dependent['token'] != expected:
                raise ValueError('dependency changed since it was read')
        published = _publish(directory, path.name, raw)
        if references & read_deletions(vault):
            raise ValueError('memory deleted during publication; cleanup required')
        saved = read_revision_record(vault, data['id'])
        if saved is None or saved['token'].get(revision_id) != _digest(raw):
            raise ValueError('published revision failed verification')
        if dependencies:
            from memory_search import memory_snapshot
            lifecycle = memory_snapshot(vault)
            if lifecycle['incomplete'] or data['id'] not in lifecycle['resolved'] or data['id'] in lifecycle['semantic_conflicts']:
                saved = dict(saved, status='conflict')
        return {'status': 'conflict' if saved['status'] == 'conflict' else 'updated' if current else 'created',
                'revision_id': revision_id, 'record': saved}
    except PublicationError as exc:
        return {'status': 'failed', 'message': 'revision publication or readback failed', 'may_have_written': exc.published}
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return {'status': 'failed', 'message': 'memory write rejected; inspect record state, token, schema and vault access',
                'may_have_written': published}
