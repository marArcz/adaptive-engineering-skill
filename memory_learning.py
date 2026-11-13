"""Evidence-labelled knowledge and non-overwriting legacy learning candidates."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from memory_boundary import validate_memory_content
from memory_capture import capture, _result, _validate
from memory_operations import _snapshot
from memory_store import _digest, _publish, PublicationError, _safe
from vault_guard import capture_gate, has_conflict_markers

EVIDENCE = {
    'user_claim': ('user', 'User-supplied claims; not independently verified.'),
    'inspected_source': ('source', 'Source inspected; inspection alone does not establish applicability or correctness.'),
    'inference': ('inference', 'Tentative inference; not independently verified.'),
}


def _proposal(subject, findings, applicability, limitations, sources, evidence, flags, domain):
    if domain not in ('general', 'engineering') or evidence not in EVIDENCE:
        raise ValueError('unsupported learning domain or evidence')
    for text, maximum in ((subject, 160), (findings, 4000), (applicability, 800), (limitations, 1000)):
        if not isinstance(text, str) or not text.strip() or len(text) > maximum:
            raise ValueError('learning needs concise explicit findings, applicability and limits')
    origin, label = EVIDENCE[evidence]
    body = (f'Learning domain: {domain}\n\nEvidence: {label}\n\n'
            f'## Findings\n\n{findings.strip()}\n\n'
            f'## Applicability\n\n{applicability.strip()}\n\n'
            f'## Limitations\n\n{limitations.strip()}\n')
    return {'category': 'inferences' if evidence == 'inference' else 'durable_preferences_goals_decisions',
            'origin': origin, 'kind': 'knowledge', 'title': f'Knowledge: {domain}: {subject.strip()}',
            'body': body, 'scope': 'general', 'sources': sources, 'flags': flags}


def learn_knowledge(vault, subject, findings, *, applicability, limitations, sources, evidence,
                    flags, domain='general', scope='general', project_id=None, related_ids=(),
                    record_id=None, user_requested=False, skill_active=False, retain_sensitive=False,
                    max_notes=1500, **runtime):
    """A direct learn request retains knowledge, never a personal-profile assertion."""
    if user_requested is not True or skill_active is not True:
        return _result('excluded', 'direct_learning_request_and_active_skill_required')
    try:
        proposal = _proposal(subject, findings, applicability, limitations, sources, evidence, flags, domain)
        if scope not in ('general', 'project') or (scope == 'general' and project_id is not None):
            raise ValueError('invalid learning scope')
        links = list(dict.fromkeys(related_ids))
        if scope == 'project' or links:
            snapshot = _snapshot(vault, max_notes)
            if scope == 'project':
                project = snapshot['resolved'].get(project_id)
                if (project is None or project_id in snapshot['superseded']
                        or project['metadata']['kind'] != 'project' or project['metadata']['state'] != 'current'):
                    return _result('needs_review', 'project_association_required')
                links = list(dict.fromkeys([project_id, *links]))
            for key in links:
                canonical = snapshot['aliases'].get(key, key)
                linked = snapshot['resolved'].get(canonical)
                if linked is None or canonical in snapshot['superseded'] or linked['metadata']['state'] != 'current':
                    return _result('needs_review', 'learning_reference_unavailable')
                data = linked['metadata']
                if data['scope'] == 'project' and (scope != 'project' or data['project_id'] != project_id):
                    return _result('needs_review', 'learning_reference_scope_mismatch')
        proposal.update(scope=scope, related_ids=links)
        if project_id is not None:
            proposal['project_id'] = project_id
        result = capture(vault, proposal, skill_active=True, retain_sensitive=retain_sensitive,
                         match_id=record_id, max_notes=max_notes, **runtime)
        if result['status'] == 'needs_review' and result['trace']['reason'] == 'changed_or_historical_statement':
            result['trace']['reason'] = 'knowledge_correction_required'
        if result['status'] in ('created', 'updated'):
            result['announcement'] = 'Knowledge saved.'
        return result
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return _result('unavailable', 'invalid_or_inaccessible_learning')


def _candidate_directory(vault):
    handles = []
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        handles.append(os.open(vault, flags))
        for name in ('research', 'candidates'):
            try:
                os.mkdir(name, mode=0o700, dir_fd=handles[-1])
            except FileExistsError:
                pass
            os.fsync(handles[-1])
            handles.append(os.open(name, flags, dir_fd=handles[-1]))
    finally:
        for handle in reversed(handles):
            os.close(handle)


def save_candidate(vault, subject, findings, *, applicability, limitations, sources, evidence,
                   flags, technology, tags=(), user_requested=False, skill_active=False,
                   retain_sensitive=False, project_roots=(), project_paths=(), device_identifiers=()):
    """Explicit legacy-engineering save; no migration, approval or catalog mutation.

    Identical content reuses a deterministic file; refreshed material gets a new
    snapshot instead of replacing an existing candidate or reviewed note.
    """
    result = {'status': 'unavailable', 'announcement': '', 'may_have_written': False,
              'catalog_updated': False}
    if user_requested is not True or skill_active is not True:
        return dict(result, status='excluded', reason='direct_learning_request_and_active_skill_required')
    try:
        proposal = _proposal(subject, findings, applicability, limitations, sources, evidence, flags, 'engineering')
        _validate(proposal)
        if any(flags[key] for key in ('temporary', 'do_not_remember', 'secret', 'third_party_private')):
            return dict(result, status='excluded', reason='required_exclusion')
        if flags['sensitive'] and (retain_sensitive is not True or evidence != 'user_claim'):
            return dict(result, status='excluded', reason='sensitive_requires_direct_retain_request')
        if (not isinstance(technology, str) or not technology.strip() or len(technology) > 160
                or not isinstance(tags, (list, tuple)) or len(tags) > 20
                or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 80 for tag in tags)):
            raise ValueError('invalid legacy learning metadata')
        metadata = {'title': subject.strip(), 'status': 'candidate', 'tags': list(tags),
                    'technology': technology.strip(), 'applies_to': applicability.strip(),
                    'verified_at': '', 'sources': sources}
        validate_memory_content({'metadata': metadata, 'body': proposal['body']},
                                project_roots=project_roots, project_paths=project_paths,
                                device_identifiers=device_identifiers)
        raw = ('---\n' + ''.join(f'{key}: {json.dumps(value, ensure_ascii=False)}\n'
                                 for key, value in metadata.items()) + '---\n' + proposal['body']).encode()
        if (len(raw) > 128 * 1024 or has_conflict_markers(raw.decode())
                or not any(len(term) > 1 for term in re.findall(r'[\w.+-]+', subject))):
            raise ValueError('candidate cannot be safely searched')
        vault = Path(vault)
        if not capture_gate(vault).allowed:
            return dict(result, reason='merge_gate_blocked')
        directory = vault / 'research/candidates'
        _safe(vault, directory)
        _candidate_directory(vault)
        filename = 'learning-' + _digest(raw) + '.md'
        relative = 'research/candidates/' + filename
        result['path'] = relative
        if not capture_gate(vault).allowed:
            return dict(result, reason='merge_gate_blocked')
        published = _publish(directory, filename, raw)
        result['may_have_written'] = published
        # Publication verifies bytes; legacy search must also discover this exact candidate.
        from search_vault import search
        found = search(vault, subject, limit=30)
        if (found['scan_truncated'] or found['unreadable_files'] or found['oversized_files']
                or not any(row['path'] == relative and row['status'] == 'candidate' for row in found['matches'])):
            return dict(result, status='partial' if published else 'unavailable',
                        reason='candidate_discovery_unverified', path=relative)
        _safe(vault, directory / filename)
        fd = os.open(directory / filename, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as saved:
            if saved.read(128 * 1024 + 1) != raw:
                raise ValueError('candidate changed during discovery')
        return dict(result, status='created' if published else 'unchanged', path=relative,
                    announcement='Engineering candidate saved.' if published else '')
    except PublicationError as exc:
        result['may_have_written'] |= exc.published
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError):
        pass
    return dict(result, status='partial' if result['may_have_written'] else 'unavailable',
                reason='candidate_write_or_verification_failed')
