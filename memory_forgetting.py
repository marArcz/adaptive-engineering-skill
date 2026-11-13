"""Explicit whole-record forgetting with atomic payload-free deletion batches."""
from __future__ import annotations

import datetime
import json
import os
import uuid
from pathlib import Path

import memory_contract as contract
from memory_capture import _capture_lock
from memory_search import memory_snapshot, deletion_closure
from memory_store import _digest, _publish, PublicationError
from vault_guard import capture_gate

LIMITS = ('Git history, backups, unsynchronized devices and unrelated user-authored '
          'files are outside this active-memory deletion.')


def _snapshot(vault, max_notes):
    snapshot = memory_snapshot(vault, max_notes)
    if snapshot['incomplete'] or any(snapshot['stats'][key] for key in
            ('invalid_files', 'unreadable_files', 'unsafe_links', 'oversized_files')):
        raise ValueError('incomplete forgetting evidence')
    return snapshot


def _token(snapshot, affected):
    files = {node['path']: node['digest'] for nodes in snapshot['groups'].values()
             for node in nodes.values()}
    return _digest(json.dumps([sorted(affected), files, sorted(snapshot['marked_deleted']),
        sorted(sorted(batch) for batch in snapshot['deletion_batches'])], sort_keys=True).encode())


def _plan(snapshot, *, record_id=None, subject=None, kind=None, scope=None, project_id=None):
    if scope not in (None, 'general', 'project') or kind not in (None, *contract.KINDS):
        raise ValueError('invalid forget scope or kind')
    if project_id is not None:
        contract._uuid(project_id, 'project_id')
    if (scope == 'general' and project_id is not None) or (scope == 'project' and project_id is None):
        raise ValueError('explicit project scope required')
    if (record_id is None) == (subject is None):
        raise ValueError('provide one exact target')
    def matches(data):
        return ((scope is None or data['scope'] == scope)
                and (project_id is None or data.get('project_id') == project_id)
                and (kind is None or data['kind'] == kind))
    if record_id is not None:
        contract._uuid(record_id, 'record_id')
        nodes = snapshot['groups'].get(record_id, {})
        if nodes and not all(matches(n['metadata']) for n in nodes.values()):
            return {'status': 'needs_review', 'reason': 'target_scope_mismatch', 'candidate_ids': []}
        if not nodes and record_id not in snapshot['marked_deleted']:
            return {'status': 'not_found', 'candidate_ids': []}
        seeds = {record_id}
    else:
        if not isinstance(subject, str) or not subject.strip() or kind is None or scope is None:
            raise ValueError('subject needs explicit kind and scope')
        title = ' '.join(subject.split()).casefold()
        seeds = {key for key, nodes in snapshot['groups'].items()
                 if key not in snapshot['deleted'] and any(matches(node['metadata'])
                    and ' '.join(node['metadata']['title'].split()).casefold() == title for node in nodes.values())}
        if len(seeds) != 1:
            return {'status': 'needs_review' if seeds else 'not_found',
                    'reason': 'ambiguous_subject' if seeds else 'subject_not_found',
                    'candidate_ids': sorted(seeds)}
    affected = deletion_closure(snapshot['groups'], seeds, snapshot['deletion_batches'])
    if len(affected) > 500:
        raise ValueError('forget scope exceeds atomic batch limit')
    count = sum(len(nodes) for key, nodes in snapshot['groups'].items() if key in affected)
    return {'status': 'ready' if count or affected - snapshot['marked_deleted'] else 'unchanged',
            'record_ids': sorted(affected), 'files_to_remove': count, 'token': _token(snapshot, affected)}


def plan_forgetting(vault, *, max_notes=1500, **target):
    """Read-only ID/subject resolution and dependency closure; no payload in result."""
    try:
        return dict(_plan(_snapshot(vault, max_notes), **target), limits=LIMITS)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {'status': 'unavailable', 'reason': 'invalid_or_inaccessible_target', 'limits': LIMITS}


def _deletion_directory(vault):
    handles = []
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        handles.append(os.open(vault, flags))
        handles.append(os.open('memory', flags, dir_fd=handles[-1]))
        try:
            os.mkdir('deletions', mode=0o700, dir_fd=handles[-1])
        except FileExistsError:
            pass
        os.fsync(handles[-1])
    finally:
        for handle in reversed(handles):
            os.close(handle)


def _remove(vault, relative, expected):
    """Unlink only the inspected file through no-follow directory handles."""
    handles = []
    try:
        parts = Path(relative).parts
        if not parts or parts[0] != 'memory' or any(p in ('.', '..') for p in parts):
            raise ValueError('invalid managed removal')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        handles.append(os.open(vault, flags))
        for part in parts[:-1]:
            handles.append(os.open(part, flags, dir_fd=handles[-1]))
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=handles[-1])
        with os.fdopen(fd, 'rb') as source:
            before = os.fstat(source.fileno())
            raw = source.read(128 * 1024 + 1)
            after = os.fstat(source.fileno())
        current = os.stat(parts[-1], dir_fd=handles[-1], follow_symlinks=False)
        signature = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if _digest(raw) != expected or signature(before) != signature(after) or signature(after) != signature(current):
            raise ValueError('managed file changed during forgetting')
        os.unlink(parts[-1], dir_fd=handles[-1])
        os.fsync(handles[-1])
    finally:
        for handle in reversed(handles):
            os.close(handle)


def forget(vault, *, expected_token, user_requested=False, skill_active=False, max_notes=1500, **target):
    """Execute a reviewed plan. A failed cleanup keeps markers and is retryable."""
    result = {'status': 'unavailable', 'announcement': '', 'limits': LIMITS,
              'may_have_written': False, 'files_removed': 0}
    if user_requested is not True or skill_active is not True:
        return dict(result, status='excluded', reason='explicit_user_request_and_active_skill_required')
    try:
        vault = Path(vault)
        if not capture_gate(vault).allowed:
            return dict(result, reason='merge_gate_blocked')
        with _capture_lock(vault):
            snapshot = _snapshot(vault, max_notes)
            plan = _plan(snapshot, **target)
            if plan['status'] not in ('ready', 'unchanged'):
                return dict(result, **plan)
            if expected_token != plan['token']:
                return dict(result, status='needs_review', reason='forgetting_snapshot_changed')
            if plan['status'] == 'unchanged':
                return dict(result, status='unchanged')
            affected = set(plan['record_ids'])
            files = {node['path']: node['digest'] for key, nodes in snapshot['groups'].items()
                     if key in affected for node in nodes.values()}
            if not capture_gate(vault).allowed:
                return dict(result, reason='merge_gate_blocked')
            if affected - snapshot['marked_deleted']:
                _deletion_directory(vault)
                now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                markers = [{'schema_version': 1, 'id': key, 'deleted_at': now} for key in sorted(affected)]
                raw = (json.dumps(markers, sort_keys=True) + '\n').encode()
                _publish(vault / 'memory/deletions', str(uuid.uuid4()) + '.batch.json', raw)
                result['may_have_written'] = True
            # The deletion batch suppresses every affected ID atomically, including
            # after an interruption. It carries enough IDs to resume cleanup.
            fresh = _snapshot(vault, max_notes)
            remaining = {node['path']: node['digest'] for key, nodes in fresh['groups'].items()
                         if key in affected for node in nodes.values()}
            if not affected <= fresh['marked_deleted'] or files != remaining:
                raise ValueError('forgetting snapshot changed after publication')
            for relative, digest in sorted(files.items()):
                if not capture_gate(vault).allowed:
                    raise ValueError('merge gate changed during cleanup')
                result['may_have_written'] = True
                _remove(vault, relative, digest)
                result['files_removed'] += 1
            final = _snapshot(vault, max_notes)
            if (any(key in final['groups'] for key in affected)
                    or not affected <= final['marked_deleted']
                    or deletion_closure(final['groups'], affected, final['deletion_batches']) != affected):
                raise ValueError('forgetting verification incomplete')
            # Context/profile/journal views and search indexes are computed from
            # this snapshot; no independent persisted summaries are maintained.
            return dict(result, status='forgotten', announcement='Requested managed memory was forgotten.',
                        records_forgotten=len(affected))
    except BlockingIOError:
        return dict(result, status='busy', reason='memory_operation_in_progress')
    except PublicationError as exc:
        result['may_have_written'] |= exc.published
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError):
        pass
    return dict(result, status='partial' if result['may_have_written'] else 'unavailable',
                reason='cleanup_incomplete_replan_and_retry')
