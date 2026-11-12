"""Remember, inspect and continue operations using portable memory foundations."""
from __future__ import annotations


from memory_capture import capture, _result
from memory_context import build_context
from memory_search import memory_snapshot
from memory_store import _record, _serialize
from project_identity import (new_project, normalize_repository, repository_from_workspace,
                              match_project, parse_project, serialize_project)

TOPICS = {
    'fact': ('user_fact', 'durable_preferences_goals_decisions', 'Fact'),
    'preference': ('preference', 'durable_preferences_goals_decisions', 'Preference'),
    'goal': ('user_fact', 'durable_preferences_goals_decisions', 'Goal'),
    'decision': ('knowledge', 'durable_preferences_goals_decisions', 'Decision'),
    'progress': ('user_fact', 'useful_progress_commitments_questions', 'Progress'),
    'commitment': ('user_fact', 'useful_progress_commitments_questions', 'Commitment'),
    'question': ('user_fact', 'useful_progress_commitments_questions', 'Question'),
}


def _snapshot(vault, max_notes):
    snapshot = memory_snapshot(vault, max_notes)
    if snapshot['incomplete'] or any(snapshot['stats'][k] for k in
            ('invalid_files','conflicted_records','unreadable_files','unsafe_links','oversized_files')):
        raise ValueError('incomplete operation evidence')
    return snapshot


def _repository(workspace, repository):
    explicit = normalize_repository(repository) if repository else None
    runtime = repository_from_workspace(workspace) if workspace is not None else None
    if explicit and runtime and explicit != runtime:
        raise ValueError('conflicting runtime repository identity')
    return explicit or runtime


def associate_project(vault, *, workspace=None, repository=None, project_id=None, name=None, max_notes=1500):
    """Read-only association. Names alone always require clarification."""
    try:
        snapshot = _snapshot(vault, max_notes)
        projects = [parse_project(_serialize(r['metadata'], r['body']))
                    for key, r in snapshot['resolved'].items()
                    if key not in snapshot['superseded'] and r['metadata']['kind'] == 'project'
                    and r['metadata']['state'] == 'current']
        result = match_project(projects, repository=_repository(workspace, repository),
                               project_id=project_id, name=name)
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return {'status':'unavailable', 'candidate_ids':[]}


def register_project(vault, name, sources, *, flags, repository=None, workspace=None,
                     project_id=None, create_new=False, skill_active=False, max_notes=1500, **runtime):
    """Create or reuse a canonical T03 project through the shared capture gate."""
    if skill_active is not True:
        return _result('excluded', 'skill_inactive')
    try:
        remote = _repository(workspace, repository)
        project = new_project(name, remote)
        if project_id is not None:
            associated = associate_project(vault, repository=remote, project_id=project_id, max_notes=max_notes)
            if associated['status'] != 'matched':
                return _result('needs_review', 'project_association_required', candidates=associated.get('candidate_ids', []))
            project['id'] = associated['project_id']
        roots = tuple(runtime.pop('project_roots', ())) + ((str(workspace),) if workspace is not None else ())
        data, body = _record(serialize_project(project, project_roots=roots,
                                               project_paths=runtime.get('project_paths', ()),
                                               device_identifiers=runtime.get('device_identifiers', ())))
        proposal = {'kind':'project', 'category':'durable_preferences_goals_decisions', 'origin':'user',
                    'title':data['title'], 'body':body, 'scope':'project', 'project_id':data['id'],
                    'sources':sources, 'flags':flags}
        return capture(vault, proposal, skill_active=True, project_identity=True, create_new_project=create_new,
                       project_roots=roots, max_notes=max_notes, **runtime)
    except (OSError, ValueError, TypeError, KeyError):
        return _result('unavailable', 'invalid_project_operation')


def remember(vault, topic, title, body, sources, *, origin, flags, scope='general', project_id=None,
             reasoning=None, related_ids=(), record_id=None, append=False, expected_token=None,
             skill_active=False, retain_sensitive=False, max_notes=1500, **runtime):
    """Create/evidence-update a subject or explicitly append ongoing progress."""
    if skill_active is not True:
        return _result('excluded', 'skill_inactive')
    try:
        if topic not in TOPICS or not isinstance(title, str) or not title.strip() or not isinstance(body, str) or not body.strip():
            return _result('unavailable', 'invalid_memory_operation')
        if topic == 'preference' and origin != 'user':
            return _result('needs_review', 'direct_preference_statement_required')
        if topic == 'decision' and (scope != 'project' or project_id is None):
            return _result('needs_review', 'project_decision_requires_project')
        if append and topic not in ('progress', 'commitment', 'question'):
            return _result('needs_review', 'correction_required', candidates=[record_id] if record_id else [])
        links = list(related_ids)
        if scope == 'project':
            association = associate_project(vault, project_id=project_id, max_notes=max_notes)
            if project_id is None or association['status'] != 'matched':
                return _result('needs_review', 'project_association_required', candidates=association.get('candidate_ids', []))
            links = list(dict.fromkeys([project_id, *links]))
        if reasoning is not None:
            if not isinstance(reasoning, str) or not reasoning.strip():
                return _result('unavailable', 'reasoning_must_be_explicit_text')
            body = body.rstrip() + '\n\nReasoning:\n' + reasoning.strip() + '\n'
        kind, category, label = TOPICS[topic]
        proposal = {'kind':kind, 'category':category, 'origin':origin, 'title':label + ': ' + title.strip(),
                    'body':body, 'scope':scope, 'sources':sources, 'flags':flags, 'related_ids':links}
        if project_id is not None:
            proposal['project_id'] = project_id
        result = capture(vault, proposal, skill_active=True, retain_sensitive=retain_sensitive,
                         match_id=record_id, append=append, expected_token=expected_token,
                         max_notes=max_notes, **runtime)
        if result['status'] == 'needs_review' and result['trace']['reason'] == 'changed_or_historical_statement':
            result['trace']['reason'] = 'correction_required'
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return _result('unavailable', 'invalid_memory_operation')


def inspect_record(vault, record_id, *, project_id=None, max_notes=1500):
    """Return an explicit current record and update token, with no fabricated fallback."""
    try:
        from memory_contract import _uuid
        _uuid(record_id, 'record_id')
        snapshot = _snapshot(vault, max_notes)
        current = snapshot['resolved'].get(record_id)
        if current is None:
            return {'status':'not_found'}
        data = current['metadata']
        if project_id is not None and (data['scope'] != 'project' or data['project_id'] != project_id):
            return {'status':'not_found'}
        if record_id in snapshot['superseded'] or data['state'] != 'current':
            return {'status':'not_current'}
        return {'status':'current', 'metadata':dict(data), 'body':current['body'], 'token':dict(current['token'])}
    except (OSError, ValueError, TypeError, KeyError):
        return {'status':'unavailable'}


def continue_project(vault, query='progress commitment question decision', *, workspace=None,
                     repository=None, project_id=None, name=None, max_notes=1500, **context_options):
    """Reconstruct bounded continuation context using current portable association."""
    association = associate_project(vault, workspace=workspace, repository=repository,
                                    project_id=project_id, name=name, max_notes=max_notes)
    if association['status'] != 'matched':
        return association
    try:
        context = build_context(vault, query, project_id=association['project_id'],
                                max_notes=max_notes, **context_options)
        return {'status':'ready', 'project_id':association['project_id'], **context}
    except (OSError, ValueError, TypeError, KeyError):
        return {'status':'unavailable'}
