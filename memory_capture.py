"""Selective capture of trusted, structured proposals while the skill is active."""
from __future__ import annotations

import datetime
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import memory_contract as contract
from memory_boundary import validate_memory_content
from memory_search import memory_snapshot, search_memory
from memory_setup import DEFAULT_POLICY, read_policy
from memory_store import write_record
from vault_guard import capture_gate

CATEGORIES = set(DEFAULT_POLICY['boundaries'])
FLAGS = {'temporary', 'do_not_remember', 'sensitive', 'secret', 'third_party_private'}
ORIGINS = {'user': 'user-stated', 'observation': 'source-supported',
           'source': 'source-supported', 'inference': 'inferred'}


def _result(status, reason, *, candidates=(), writer=None, record_id=None):
    result = {'status': status, 'trace': {'reason': reason, 'candidate_ids': sorted(candidates)},
              'announcement': ''}
    if record_id:
        result['record_id'] = record_id
    if writer is not None:
        result['may_have_written'] = writer.get('may_have_written', status in ('created', 'updated', 'conflict'))
    if status in ('created', 'updated'):
        result['announcement'] = 'Memory saved.' if status == 'created' else 'Memory evidence updated.'
    return result


def _policy(vault):
    data = read_policy(vault)
    boundaries = data['boundaries']
    if set(boundaries) != CATEGORIES:
        raise ValueError('unsupported capture boundaries')
    for key, default in DEFAULT_POLICY['boundaries'].items():
        allowed = {'capture', 'exclude'} if default == 'capture' else {default, 'exclude'}
        if boundaries[key] not in allowed:
            raise ValueError('capture boundary cannot relax required exclusions')
    return data


def _validate(proposal):
    required = {'category', 'origin', 'kind', 'title', 'body', 'scope', 'sources', 'flags'}
    if not isinstance(proposal, dict) or set(proposal) - required - {'project_id', 'related_ids'} or required - set(proposal):
        raise ValueError('invalid capture proposal fields')
    if proposal['category'] not in CATEGORIES or proposal['origin'] not in {*ORIGINS, 'hypothetical', 'source_instruction'}:
        raise ValueError('unsupported capture classification')
    flags = proposal['flags']
    if not isinstance(flags, dict) or set(flags) != FLAGS or any(type(v) is not bool for v in flags.values()):
        raise ValueError('all capture flags must be explicit booleans')
    data = {'schema_version': 1, 'id': str(uuid.uuid4()), 'kind': proposal['kind'],
            'title': proposal['title'], 'scope': proposal['scope'],
            'basis': ORIGINS.get(proposal['origin'], 'inferred'), 'state': 'current',
            'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z',
            'sources': proposal['sources'], 'related_ids': proposal.get('related_ids', []), 'supersedes': []}
    if 'project_id' in proposal:
        data['project_id'] = proposal['project_id']
    if data['kind'] == 'project' and 'project_id' in data:
        data['id'] = data['project_id']
    contract.validate(data, proposal['body'])
    return data


@contextmanager
def _capture_lock(vault):
    # Cooperative capture callers serialize matching plus publication. The lock has
    # no personal content and cannot be interpreted as a memory record.
    import fcntl
    handles = []
    locked = False
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        root = os.open(vault, flags)
        handles.append(root)
        directory = os.open('memory', flags, dir_fd=root)
        handles.append(directory)
        lock = os.open('.capture.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        handles.append(lock)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield
    finally:
        if locked:
            fcntl.flock(handles[-1], fcntl.LOCK_UN)
        for handle in reversed(handles):
            os.close(handle)


def _subject(value):
    return ' '.join(value.split()).casefold()


def _statement(value):
    return ' '.join(value.split())


def capture(vault, proposal, *, skill_active=False, retain_sensitive=False, match_id=None,
            project_roots=(), project_paths=(), device_identifiers=(), max_notes=1500):
    """Classifications and authorization are trusted caller context, never source text."""
    if skill_active is not True:
        return _result('excluded', 'skill_inactive')
    try:
        data = _validate(proposal)
        flags, category, origin = proposal['flags'], proposal['category'], proposal['origin']
        if origin in ('hypothetical', 'source_instruction'):
            return _result('excluded', 'non_memory_source')
        if any(flags[key] for key in ('temporary', 'do_not_remember', 'secret', 'third_party_private')):
            return _result('excluded', 'required_exclusion')
        if category in ('temporary_or_do_not_remember', 'credentials_and_third_party_private_data', 'project_filesystem_paths'):
            return _result('excluded', 'required_exclusion')
        if origin == 'source' and data['kind'] != 'knowledge':
            return _result('excluded', 'source_cannot_assert_personal_fact')
        sensitive = flags['sensitive'] or category == 'sensitive_personal_details'
        if sensitive and (retain_sensitive is not True or origin != 'user'):
            return _result('excluded', 'sensitive_requires_direct_retain_request')
        # Inference classification cannot be promoted by a nominal user origin.
        if category == 'inferences' and origin != 'inference':
            return _result('excluded', 'inconsistent_inference_classification')
        validate_memory_content({'metadata': data, 'body': proposal['body']}, project_roots=project_roots,
                                project_paths=project_paths, device_identifiers=device_identifiers)
        vault = Path(vault)
        policy = _policy(vault)
        if policy['capture'] == 'paused':
            return _result('paused', 'capture_paused')
        boundaries = policy['boundaries']
        if boundaries[category] == 'exclude' or (sensitive and boundaries['sensitive_personal_details'] == 'exclude'):
            return _result('excluded', 'configured_exclusion')
        if origin == 'inference' and boundaries['inferences'] == 'exclude':
            return _result('excluded', 'inferences_excluded')
        gate = capture_gate(vault)
        if not gate.allowed:
            return _result('unavailable', 'merge_gate_blocked')
        with _capture_lock(vault):
            # Recheck policy after acquiring the lock rather than acting on old settings.
            if _policy(vault) != policy:
                return _result('unavailable', 'capture_settings_changed')
            snapshot = memory_snapshot(vault, max_notes)
            stats = snapshot['stats']
            if snapshot['incomplete'] or any(stats[k] for k in ('invalid_files', 'conflicted_records', 'unreadable_files', 'unsafe_links', 'oversized_files')):
                return _result('unavailable', 'capture_evidence_incomplete')
            found = search_memory(vault, data['title'], limit=30, max_notes=max_notes,
                                  kind=data['kind'], scope=data['scope'], project_id=data.get('project_id'),
                                  history=True, _snapshot=snapshot)
            if found['truncated']:
                return _result('unavailable', 'subject_search_truncated')
            candidates = set()
            for row in found['matches']:
                node = snapshot['groups'][row['id']][row['revision_id']]
                if _subject(node['metadata']['title']) == _subject(data['title']):
                    candidates.add(row['id'])
            if match_id is not None:
                contract._uuid(match_id, 'match_id')
                if match_id not in candidates:
                    return _result('needs_review', 'explicit_match_disagrees', candidates=candidates)
                candidates = {match_id}
            if len(candidates) > 1:
                return _result('needs_review', 'ambiguous_subject', candidates=candidates)
            previous = None
            if candidates:
                key = next(iter(candidates))
                previous = snapshot['resolved'][key]
                old = previous['metadata']
                if (key in snapshot['superseded'] or old['state'] != 'current'
                        or _subject(old['title']) != _subject(data['title'])
                        or _statement(previous['body']) != _statement(proposal['body'])):
                    return _result('needs_review', 'changed_or_historical_statement', candidates=candidates)
                data = dict(old)  # Preserve basis, identity, compatible fields and original statement.
                sources = list(dict.fromkeys(old['sources'] + proposal['sources']))
                related = list(dict.fromkeys(old['related_ids'] + proposal.get('related_ids', [])))
                if sources == old['sources'] and related == old['related_ids']:
                    return _result('unchanged', 'already_recorded', record_id=key)
                data.update(sources=sources, related_ids=related)
            elif data['kind'] == 'project' and data['id'] in snapshot['resolved']:
                return _result('needs_review', 'project_identity_subject_changed', candidates=[data['id']])
            now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            data['updated_at'] = max(now, data['updated_at'])
            if previous is None:
                data['created_at'] = now
            if _policy(vault) != policy:
                return _result('unavailable', 'capture_settings_changed')
            result = write_record(vault, data, previous['body'] if previous else proposal['body'],
                                  expected_token=previous['token'] if previous else None,
                                  project_roots=project_roots, project_paths=project_paths,
                                  device_identifiers=device_identifiers)
            status = result['status']
            return _result(status, 'verified_change' if status in ('created','updated') else 'writer_' + status,
                           writer=result, record_id=data['id'])
    except BlockingIOError:
        return _result('busy', 'capture_in_progress_retry')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError):
        return _result('unavailable', 'invalid_proposal_policy_or_storage')
