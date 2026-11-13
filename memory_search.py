"""Bounded read-only search over resolved portable memory records."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import memory_contract as contract
from memory_store import AREAS, decode_record, decode_deletions, resolve_nodes, _digest

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
    deletion_batches = []
    stats = {k: 0 for k in ('files_examined', 'invalid_files', 'unreadable_files',
                            'oversized_files', 'unsafe_links', 'conflicted_records')}
    incomplete = False
    scan_truncated = False
    if not root.exists() and not root.is_symlink():
        return groups, deleted, stats, False, False, deletion_batches
    if root.is_symlink() or not root.is_dir():
        stats['unsafe_links'] += 1
        return {}, deleted, stats, True, False, deletion_batches
    deletion_area = root / 'deletions'
    if deletion_area.exists() and not deletion_area.is_dir():
        stats['invalid_files'] += 1
        return {}, deleted, stats, True, False, deletion_batches

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
                    ids = decode_deletions(raw, path.name)
                    deleted.update(ids)
                    deletion_batches.append(ids)
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
                                   'path': path.relative_to(vault).as_posix(),
                                   'dependencies': envelope.get('dependencies', {}) if envelope else {},
                                   'equivalent_ids': envelope.get('equivalent_ids',[]) if envelope else []}
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
    return groups, deleted, stats, incomplete, scan_truncated, deletion_batches


def _subject_key(data):
    return (data['kind'], data['scope'], data.get('project_id'), ' '.join(data['title'].split()).casefold())


def deletion_closure(groups, seeds, batches=()):
    """Whole-record cleanup follows lineage, provenance links and project scope."""
    affected = set(seeds)
    changed = True
    while changed:
        before = set(affected)
        for batch in batches:
            if affected & batch:
                affected.update(batch)
        for key, nodes in groups.items():
            for node in nodes.values():
                data = node['metadata']
                lineage = set(data['supersedes']) | set(node.get('equivalent_ids', []))
                references = lineage | set(data['related_ids']) | set(node.get('dependencies', {}))
                if 'project_id' in data:
                    references.add(data['project_id'])
                if references & affected:
                    affected.add(key)
                if key in affected:
                    # Invalid cross-subject supersedes/alias claims must not
                    # turn a forget request into deletion of unrelated memory.
                    affected.update(ref for ref in lineage if ref not in groups or any(
                        _subject_key(other['metadata']) == _subject_key(data)
                        for other in groups[ref].values()))
        changed = affected != before
    return affected


def _lifecycle(groups, resolved, blocked_subjects=()):
    """Resolve subject claims without treating import order or timestamps as truth."""
    conflicts={key for key,record in resolved.items() if _subject_key(record['metadata']) in blocked_subjects}
    edges={key:set() for key in resolved}
    for key,record in resolved.items():
        data=record['metadata']
        for ref in data['supersedes']:
            if (ref not in resolved or _subject_key(resolved[ref]['metadata'])!=_subject_key(data)
                    or data['state']=='unresolved'):
                conflicts.add(key)
            else:
                edges[key].add(ref)
    superseded=set().union(*edges.values()) if edges else set()
    pending=set(edges)
    done=set()
    while pending:
        ready={key for key in pending if edges[key] <= done}
        if not ready:
            conflicts.update(pending)
            break
        pending-=ready
        done|=ready
    for key,record in resolved.items():
        data=record['metadata']
        if key in superseded or data['state']=='superseded':
            continue
        tip=groups[key][record['tips'][0]]
        for ref,expected in tip.get('dependencies',{}).items():
            actual=resolved.get(ref)
            if actual is None or actual['token']!=expected:
                conflicts.add(key)
                if ref in resolved:
                    conflicts.add(ref)
    subjects={}
    for key,record in resolved.items():
        if key not in superseded and record['metadata']['state']!='superseded':
            subjects.setdefault(_subject_key(record['metadata']),[]).append(key)
    for keys in subjects.values():
        values={' '.join(resolved[key]['body'].split()) for key in keys}
        if len(values)>1:
            conflicts.update(keys)
    aliases={}
    for key,record in resolved.items():
        if key in superseded or key in conflicts or record['metadata']['state']!='current':
            continue
        node=groups[key][record['tips'][0]]
        for ref in node.get('equivalent_ids',[]):
            target=resolved.get(ref)
            ignored=set(node.get('equivalent_ids',[]))|{key}
            if (target is None or ref not in edges[key] or _subject_key(target['metadata'])!=_subject_key(record['metadata'])
                    or target['metadata']['basis']!=record['metadata']['basis'] or target['body']!=record['body']
                    or {k:v for k,v in target['metadata'].items() if k not in contract.FIELDS}!={k:v for k,v in record['metadata'].items() if k not in contract.FIELDS}
                    or not set(target['metadata']['sources'])<=set(record['metadata']['sources'])
                    or not (set(target['metadata']['related_ids'])-ignored)<=set(record['metadata']['related_ids'])
                    or node.get('dependencies',{}).get(ref)!=target['token']):
                conflicts.add(key)
                continue
            if ref in aliases and aliases[ref]!=key:
                conflicts.update((key,aliases[ref]))
            aliases[ref]=key
    changed=True
    while changed:
        changed=False
        for key,record in resolved.items():
            data=record['metadata']
            if data['basis']!='inferred' or key in conflicts or key in superseded:
                continue
            if any(ref not in resolved or ref in superseded or ref in conflicts
                   or resolved[ref]['metadata']['state']!='current' for raw_ref in data['related_ids'] for ref in [aliases.get(raw_ref,raw_ref)]):
                conflicts.add(key)
                changed=True
    for key,record in list(resolved.items()):
        state='unresolved' if key in conflicts else 'superseded' if key in superseded else record['metadata']['state']
        resolved[key]=dict(record,metadata=dict(record['metadata'],state=state))
    aliases={ref:key for ref,key in aliases.items() if ref not in conflicts and key not in conflicts}
    return superseded,conflicts,aliases


def memory_snapshot(vault, max_notes=1500):
    """Load one bounded, validated snapshot for search and context assembly."""
    vault = Path(vault)
    if not vault.is_dir() or max_notes < 1:
        raise ValueError("Vault must exist and max_notes must be positive")
    groups, deleted, stats, incomplete, scan_truncated, deletion_batches = _load(vault, max_notes)
    marked_deleted = set(deleted)
    deleted = deletion_closure(groups, deleted, deletion_batches)
    resolved = {}
    blocked_subjects=set()
    for key, nodes in groups.items():
        if key in deleted:
            continue
        try:
            current = resolve_nodes(nodes)
            if current['status'] == 'conflict':
                stats['conflicted_records'] += 1
                blocked_subjects.update(_subject_key(node['metadata']) for node in nodes.values())
                continue
            resolved[key] = current
        except ValueError:
            stats['conflicted_records'] += 1
            blocked_subjects.update(_subject_key(node['metadata']) for node in nodes.values())
    superseded,semantic_conflicts,aliases=_lifecycle(groups,resolved,blocked_subjects)
    stats['conflicted_records']+=len(semantic_conflicts)
    return {"groups": groups, "resolved": resolved, "superseded": superseded,
            "deleted": deleted, "marked_deleted": marked_deleted, "deletion_batches": deletion_batches,
            "semantic_conflicts":semantic_conflicts,"aliases":aliases,
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
    if record_id and not history:
        record_id=snapshot['aliases'].get(record_id,record_id)
    rows = []
    for key, current in resolved.items():
        if record_id and key != record_id:
            continue
        tip = current['tips'][0]
        candidates = groups[key].items() if history else [(tip, groups[key][tip])]
        for revision, node in candidates:
            data = node['metadata']
            semantic=key in snapshot['semantic_conflicts']
            historical = revision != tip or data['state'] != 'current' or key in superseded or semantic
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
            if related_to and snapshot['aliases'].get(related_to,related_to) not in {snapshot['aliases'].get(r,r) for r in references}:
                continue
            score = sum(2 * (t in data['title'].casefold()) + (t in node['body'].casefold()) for t in terms)
            if terms and score == 0:
                continue
            row = {field: data[field] for field in ('id', 'kind', 'basis', 'state', 'scope')}
            row['state']='unresolved' if semantic else 'superseded' if key in superseded else data['state']
            if 'project_id' in data:
                row['project_id'] = data['project_id']
            row.update(title=data['title'][:240], revision_id=revision, path=node['path'], score=score,
                       historical=historical, tentative=data['basis'] == 'inferred',
                       sources=[s[:300] for s in data['sources'][:3]],
                       related_ids=data['related_ids'][:20],
                       resolved_related_ids=[snapshot['aliases'].get(r,r) for r in data['related_ids'][:20]], supersedes=data['supersedes'][:20],
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
