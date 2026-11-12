"""Selective, concise accounts of sourced shared experiences."""
from __future__ import annotations

import json

from memory_capture import capture, _result
from memory_operations import _snapshot, inspect_record
from memory_search import search_memory
from memory_store import _pairs

SIGNIFICANCE = {'decision', 'outcome', 'lesson', 'collaboration_feedback'}
FIELDS = {'journal_version', 'significance', 'context', 'what_happened',
          'why_it_mattered', 'observed_outcome', 'inferred_lesson'}
MAX_BODY = 2400


def _event(significance, context, happened, why, outcome, lesson):
    if significance not in SIGNIFICANCE:
        raise ValueError('unsupported significance')
    for text, maximum in ((context,400), (happened,600), (why,400)):
        if not isinstance(text,str) or not text.strip() or len(text)>maximum:
            raise ValueError('experience requires a concise explicit account')
    for text, maximum in ((outcome,500), (lesson,400)):
        if text is not None and (not isinstance(text,str) or not text.strip() or len(text)>maximum):
            raise ValueError('optional evidence must be concise or absent')
    if significance == 'outcome' and outcome is None:
        raise ValueError('outcome significance needs an observed outcome')
    if significance == 'lesson' and lesson is None:
        raise ValueError('lesson significance needs an explicit tentative lesson')
    return {'journal_version':1, 'significance':significance, 'context':context.strip(),
            'what_happened':happened.strip(), 'why_it_mattered':why.strip(),
            'observed_outcome':outcome.strip() if outcome is not None else None,
            'inferred_lesson':{'text':lesson.strip(), 'basis':'inferred', 'tentative':True} if lesson is not None else None}


def journal(vault, subject, *, significance, context, happened, why, sources, origin, flags,
            outcome=None, lesson=None, scope='general', project_id=None, related_ids=(),
            record_id=None, skill_active=False, retain_sensitive=False, max_notes=1500, **runtime):
    """The trusted caller classifies actual available evidence, not source instructions."""
    if skill_active is not True:
        return _result('excluded','skill_inactive')
    if significance == 'routine':
        return _result('excluded','routine_exchange')
    if origin not in ('user','observation'):
        return _result('excluded','experience_requires_observed_or_reported_event')
    try:
        if not isinstance(subject,str) or not subject.strip() or len(subject)>160:
            raise ValueError('experience requires a concise stable subject')
        event = _event(significance, context, happened, why, outcome, lesson)
        body = json.dumps(event,ensure_ascii=False,indent=2) + '\n'
        if len(body)>MAX_BODY:
            return _result('needs_review','experience_summary_too_long')
        snapshot = _snapshot(vault,max_notes)
        links = list(dict.fromkeys(related_ids))
        if scope == 'project':
            project = snapshot['resolved'].get(project_id)
            if (project_id is None or project is None or project['metadata']['kind']!='project'
                    or project_id in snapshot['superseded'] or project['metadata']['state']!='current'):
                return _result('needs_review','project_association_required')
            links = list(dict.fromkeys([project_id,*links]))
        elif scope != 'general' or project_id is not None:
            return _result('unavailable','invalid_experience_scope')
        for key in links:
            linked = snapshot['resolved'].get(key)
            if linked is None or key in snapshot['superseded'] or linked['metadata']['state']!='current':
                return _result('needs_review','experience_reference_unavailable')
            data = linked['metadata']
            if data['scope']=='project' and (scope!='project' or data['project_id']!=project_id):
                return _result('needs_review','experience_reference_scope_mismatch')
        proposal = {'category':'significant_shared_experiences', 'origin':origin, 'kind':'experience',
                    'title':'Experience: '+subject.strip(), 'body':body, 'scope':scope,
                    'sources':sources, 'flags':flags, 'related_ids':links}
        if project_id is not None:
            proposal['project_id']=project_id
        return capture(vault,proposal,skill_active=True,retain_sensitive=retain_sensitive,
                       match_id=record_id,max_notes=max_notes,includes_inference=lesson is not None,**runtime)
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return _result('unavailable','invalid_or_inaccessible_experience')


def inspect_experience(vault, record_id, *, project_id=None, max_notes=1500):
    """Inspect a past account without promoting it to instructions or identity evidence."""
    record = inspect_record(vault,record_id,project_id=project_id,max_notes=max_notes)
    if record['status']!='current':
        return record
    if record['metadata']['kind']!='experience':
        return {'status':'not_found'}
    result = dict(record,account_type='past_experience',is_instruction=False)
    try:
        event = json.loads(record['body'],object_pairs_hook=_pairs)
    except ValueError:
        # Older v1 experience bodies remain readable as literal Markdown.
        return dict(result,format='markdown')
    if not isinstance(event,dict) or 'journal_version' not in event:
        return dict(result,format='markdown')
    try:
        if set(event)!=FIELDS or type(event['journal_version']) is not int or event['journal_version']!=1:
            raise ValueError('unsupported journal format')
        lesson=event['inferred_lesson']
        if lesson is not None and (not isinstance(lesson,dict) or set(lesson)!={'text','basis','tentative'}
                                   or lesson['basis']!='inferred' or lesson['tentative'] is not True):
            raise ValueError('invalid inferred lesson')
        _event(event['significance'],event['context'],event['what_happened'],event['why_it_mattered'],
               event['observed_outcome'],lesson['text'] if lesson else None)
        if len(record['body'])>MAX_BODY:
            raise ValueError('invalid experience account')
        return dict(result,format='journal_v1',event=event)
    except (ValueError,TypeError,KeyError):
        return {'status':'unavailable'}


def related_experiences(vault, query='', *, related_to=None, project_id=None, limit=5,
                        history=False, max_notes=1500):
    """Return provenance pointers; historical accounts are always reference data."""
    result=search_memory(vault,query,limit=limit,max_notes=max_notes,kind='experience',
                         related_to=related_to,project_id=project_id,history=history)
    for row in result['matches']:
        row.update(account_type='past_experience',is_instruction=False)
    return result
