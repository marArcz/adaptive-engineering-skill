"""Bounded read-only search over resolved portable memory records."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import memory_contract as contract
from memory_store import AREAS, decode_record, resolve_nodes, _digest, _pairs

MAX_BYTES = 128 * 1024
SKIP = {'.git', '.obsidian', '.trash', 'templates', 'attachments', 'node_modules'}


def _identity(raw, path):
    """Recover identities only to quarantine damaged records, never to recall them."""
    ids = set()
    for value in [path.name.split('.')[0], *re.findall(rb'^id: ("[^"\n]+")\r?$', raw, re.M)]:
        try:
            if isinstance(value, bytes):
                value = json.loads(value)
            contract._uuid(value, 'id')
            ids.add(value)
        except (ValueError, TypeError):
            pass
    return ids


def _load(vault, max_notes):
    root = vault / 'memory'
    groups, blocked, deleted = {}, set(), set()
    stats = {k: 0 for k in ('files_examined', 'invalid_files', 'unreadable_files',
                            'oversized_files', 'unsafe_links', 'conflicted_records')}
    incomplete = False
    scan_truncated = False
    if not root.exists() and not root.is_symlink():
        return groups, deleted, stats, False, False
    if root.is_symlink() or not root.is_dir():
        stats['unsafe_links'] += 1
        return {}, deleted, stats, True, False

    def walk_error(error):
        nonlocal incomplete
        stats['unreadable_files'] += 1
        incomplete = True

    stop = False
    for directory, dirs, files in os.walk(root, onerror=walk_error, followlinks=False):
        folder = Path(directory)
        relative = folder.relative_to(root)
        allowed = set(AREAS) | {'revisions', 'deletions'} if folder == root else None
        kept = []
        for name in sorted(dirs):
            if name.startswith('.') or name in SKIP or (allowed is not None and name not in allowed):
                continue
            if (folder / name).is_symlink():
                stats['unsafe_links'] += 1
                incomplete = True
            else:
                kept.append(name)
        dirs[:] = kept
        if not relative.parts:
            continue
        area = relative.parts[0]
        for name in sorted(files):
            if name.startswith('.'):
                continue
            if area != 'deletions' and not name.endswith('.md'):
                continue
            if stats['files_examined'] >= max_notes:
                incomplete = scan_truncated = stop = True
                break
            stats['files_examined'] += 1
            path = folder / name
            raw = b''
            try:
                if path.is_symlink():
                    stats['unsafe_links'] += 1
                    raise ValueError('unsafe link')
                with path.open('rb') as source:
                    raw = source.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    stats['oversized_files'] += 1
                    raise ValueError('oversized file')
                if area == 'deletions':
                    marker = json.loads(raw, object_pairs_hook=_pairs)
                    contract.validate_collection([], [marker])
                    if path.name != marker['id'] + '.json' or marker['id'] in deleted:
                        raise ValueError('invalid deletion identity')
                    deleted.add(marker['id'])
                    continue
                data, body, envelope = decode_record(raw, revision=area == 'revisions')
                record_id = data['id']
                revision = envelope['revision_id'] if envelope else 'base'
                if envelope and name != f'{record_id}.{revision}.md':
                    raise ValueError('revision filename mismatch')
                nodes = groups.setdefault(record_id, {})
                if revision in nodes:
                    blocked.add(record_id)
                    raise ValueError('duplicate revision')
                nodes[revision] = {'metadata': data, 'body': body, 'digest': _digest(raw),
                                   'parents': envelope['parents'] if envelope else {},
                                   'path': path.relative_to(vault).as_posix()}
            except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError):
                stats['invalid_files'] += 1
                ids = _identity(raw, path)
                blocked.update(ids)
                # An unknown corrupt record could hide a branch or deletion marker.
                if not ids or area == 'deletions':
                    incomplete = True
                if not raw and not path.is_symlink():
                    stats['unreadable_files'] += 1
        if stop:
            break
    for record_id in blocked:
        groups.pop(record_id, None)
    if incomplete:
        groups = {}
    return groups, deleted, stats, incomplete, scan_truncated


def memory_snapshot(vault, max_notes=1500):
    """Load one bounded, validated snapshot for search and context assembly."""
    vault = Path(vault)
    if not vault.is_dir() or max_notes < 1:
        raise ValueError("Vault must exist and max_notes must be positive")
    groups, deleted, stats, incomplete, scan_truncated = _load(vault, max_notes)
    resolved = {}
    for key, nodes in groups.items():
        if key in deleted:
            continue
        try:
            current = resolve_nodes(nodes)
            if current['status'] == 'conflict':
                stats['conflicted_records'] += 1
                continue
            resolved[key] = current
        except ValueError:
            stats['conflicted_records'] += 1
    superseded = {ref for current in resolved.values()
                  for ref in current['metadata']['supersedes']}
    return {"groups": groups, "resolved": resolved, "superseded": superseded,
            "stats": stats, "incomplete": incomplete, "scan_truncated": scan_truncated}


def search_memory(vault, query='', limit=3, max_notes=1500, *, kind=None, scope=None,
                  project_id=None, record_id=None, related_to=None, history=False, _snapshot=None):
    """Return pointers and provenance, not full remembered content or deletion metadata."""
    vault = Path(vault)
    if not vault.is_dir():
        raise ValueError('Vault directory missing or inaccessible')
    if not 1 <= limit <= 30 or max_notes < 1:
        raise ValueError('limit must be 1..30 and max_notes must be positive')
    if kind is not None and kind not in contract.KINDS:
        raise ValueError('unknown memory kind')
    if scope not in (None, 'general', 'project', 'all'):
        raise ValueError('unknown memory scope')
    for value in (project_id, record_id, related_to):
        if value is not None:
            contract._uuid(value, 'lookup ID')
    if scope == 'project' and project_id is None:
        raise ValueError('project scope requires a project ID')
    terms = [s.casefold() for s in re.findall(r'[\w.+-]+', query) if len(s) > 1]
    if not terms and not (record_id or related_to):
        raise ValueError('provide searchable words, a record ID or a relationship ID')
    snapshot = _snapshot if _snapshot is not None else memory_snapshot(vault, max_notes)
    groups, resolved, superseded = (snapshot[k] for k in ('groups', 'resolved', 'superseded'))
    stats, incomplete, scan_truncated = (snapshot[k] for k in ('stats', 'incomplete', 'scan_truncated'))
    rows = []
    for key, current in resolved.items():
        if record_id and key != record_id:
            continue
        tip = current['tips'][0]
        candidates = groups[key].items() if history else [(tip, groups[key][tip])]
        for revision, node in candidates:
            data = node['metadata']
            historical = revision != tip or data['state'] != 'current' or key in superseded
            if historical and not history:
                continue
            if kind and data['kind'] != kind:
                continue
            if scope == 'general' and data['scope'] != 'general':
                continue
            if scope == 'project' and data['scope'] != 'project':
                continue
            if project_id:
                if data['scope'] == 'project' and data['project_id'] != project_id:
                    continue
            elif scope not in ('all', 'general') and not record_id and data['scope'] == 'project':
                continue
            references = data['related_ids'] + data['supersedes']
            if related_to and related_to not in references:
                continue
            score = sum(2 * (t in data['title'].casefold()) + (t in node['body'].casefold()) for t in terms)
            if terms and score == 0:
                continue
            row = {field: data[field] for field in ('id', 'kind', 'basis', 'state', 'scope')}
            if 'project_id' in data:
                row['project_id'] = data['project_id']
            row.update(title=data['title'][:240], revision_id=revision, path=node['path'], score=score,
                       historical=historical, tentative=data['basis'] == 'inferred',
                       sources=[s[:300] for s in data['sources'][:3]],
                       related_ids=data['related_ids'][:20], supersedes=data['supersedes'][:20],
                       missing_reference_ids=sorted({r for r in references if r not in resolved})[:20],
                       pointer_truncated=len(data['title']) > 240 or len(data['sources']) > 3
                       or any(len(s) > 300 for s in data['sources'][:3])
                       or len(data['related_ids']) > 20 or len(data['supersedes']) > 20
                       or len({r for r in references if r not in resolved}) > 20)
            rows.append(row)
    rows.sort(key=lambda r: (-r['score'], r['historical'], r['id'], r['revision_id']))
    return {'matches': rows[:limit], 'result_count': len(rows), 'truncated': scan_truncated or len(rows) > limit,
            'scan_truncated': scan_truncated, 'results_truncated': len(rows) > limit,
            'memory_incomplete': incomplete, **stats,
            'notice': 'Inferred memory is tentative. Historical results are not current advice. '
                      'Incomplete scans suppress memory results; deletion payloads are never returned.'}
