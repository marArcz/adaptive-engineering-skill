"""Explicit corrections and unresolved claims with source-snapshot protection."""
from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path

import memory_contract as contract

from memory_capture import prepare_capture, _capture_lock, _policy, _result, ORIGINS
from memory_search import memory_snapshot, _subject_key
from memory_store import write_record, _serialize, _pairs


def _snapshot(vault, max_notes):
    snapshot=memory_snapshot(vault,max_notes)
    graph_conflicts=snapshot['stats']['conflicted_records']-len(snapshot['semantic_conflicts'])
    if snapshot['incomplete'] or graph_conflicts or any(snapshot['stats'][k] for k in
            ('invalid_files','unreadable_files','oversized_files','unsafe_links')):
        raise ValueError('unsafe correction evidence')
    return snapshot


def correction_candidates(vault, record_id, *, max_notes=1500):
    """Inspect same-subject claims explicitly; none is labelled current advice."""
    try:
        snapshot=_snapshot(vault,max_notes)
        selected=snapshot['resolved'].get(record_id)
        if selected is None:
            return {'status':'not_found','candidates':[]}
        key=_subject_key(selected['metadata'])
        candidates=[]
        for candidate,record in sorted(snapshot['resolved'].items()):
            if _subject_key(record['metadata'])!=key:
                continue
            if candidate in snapshot['superseded'] and candidate not in snapshot['semantic_conflicts']:
                continue
            if record['metadata']['state']=='superseded':
                continue
            candidates.append({'id':candidate,'metadata':record['metadata'],'body':record['body'],
                               'token':record['token'],'is_current_advice':False})
        return {'status':'needs_review','candidates':candidates,
                'question':'Which value should apply to this subject and scope?'}
    except (OSError,ValueError,TypeError,KeyError):
        return {'status':'unavailable','candidates':[]}


def _account(body, old_body):
    """Structured journal corrections cannot relabel a tentative lesson as observed."""
    try:
        original=json.loads(old_body)
    except ValueError:
        return False
    if not isinstance(original,dict) or 'journal_version' not in original:
        return False
    from memory_journal import _event, FIELDS, MAX_BODY
    account=json.loads(body,object_pairs_hook=_pairs)
    if (not isinstance(account,dict) or set(account)!=FIELDS or type(account['journal_version']) is not int
            or account['journal_version']!=1 or len(body)>MAX_BODY):
        raise ValueError('invalid journal correction')
    lesson=account['inferred_lesson']
    if lesson is not None and (not isinstance(lesson,dict) or set(lesson)!={'text','basis','tentative'}
                              or lesson['basis']!='inferred' or lesson['tentative'] is not True):
        raise ValueError('inferred lesson cannot become observed outcome')
    _event(account['significance'],account['context'],account['what_happened'],account['why_it_mattered'],
           account['observed_outcome'],lesson['text'] if lesson else None)
    return lesson is not None


def _change(vault, record_ids, body, sources, *, expected_tokens, scope, project_id=None,
            origin, flags, clear=False, title=None, skill_active=False, retain_sensitive=False,
            max_notes=1500, ambiguous=False, **runtime):
    if skill_active is not True:
        return _result('excluded','skill_inactive')
    written=None
    written_id=None
    try:
        if not isinstance(record_ids,(list,tuple)):
            raise ValueError('target IDs must be an explicit list')
        ids=sorted(set(record_ids))
        for key in ids:
            contract._uuid(key,'record_id')
        if not ambiguous and (clear is not True or origin!='user'):
            return _result('needs_review','explicit_correction_required',candidates=ids)
        if not ids or len(ids)!=len(record_ids) or not isinstance(expected_tokens,dict) or set(expected_tokens)!=set(ids):
            raise ValueError('correction requires exact target snapshots')
        vault=Path(vault)
        snapshot=_snapshot(vault,max_notes)
        records=[snapshot['resolved'][key] for key in ids]
        old=records[0]['metadata']
        subject=_subject_key(old)
        if old['scope']!=scope or old.get('project_id')!=project_id or any(_subject_key(r['metadata'])!=subject for r in records):
            return _result('needs_review','correction_scope_or_subject_mismatch',candidates=ids)
        if any(r['token']!=expected_tokens[key] for key,r in zip(ids,records)):
            return _result('needs_review','stale_correction_snapshot',candidates=ids)
        active={key for key,r in snapshot['resolved'].items() if _subject_key(r['metadata'])==subject
                and (key not in snapshot['superseded'] or key in snapshot['semantic_conflicts'])
                and r['metadata']['state']!='superseded'}
        if not ambiguous and len(active)==1 and not set(ids)<=active:
            winner=next(iter(active))
            current=snapshot['resolved'][winner]
            node=snapshot['groups'][winner][current['tips'][0]]
            if (current['metadata']['state']=='current' and set(current['metadata']['supersedes'])==set(ids)
                    and node.get('dependencies')==expected_tokens and current['body']==body
                    and all(source in current['metadata']['sources'] for source in sources)):
                return _result('unchanged','correction_already_recorded',record_id=winner)
        if not set(ids)<=active or (not ambiguous and set(ids)!=active):
            return _result('needs_review','resolve_all_subject_claims',candidates=active)
        if old['kind']=='project' and (ambiguous or len(ids)!=1):
            return _result('needs_review','project_identity_requires_explicit_single_target',candidates=ids)
        if title is not None and (old['kind']!='project' or not isinstance(title,str)):
            return _result('needs_review','subject_rename_not_a_correction',candidates=ids)
        extras={k:v for k,v in old.items() if k not in contract.FIELDS}
        if any({k:v for k,v in r['metadata'].items() if k not in contract.FIELDS}!=extras for r in records):
            return _result('needs_review','compatible_metadata_disagreement',candidates=ids)
        includes_inference=_account(body,records[0]['body']) if old['kind']=='experience' else False
        category='significant_shared_experiences' if old['kind']=='experience' else 'durable_preferences_goals_decisions'
        proposal={'category':category,'origin':origin,'kind':old['kind'],'title':title if title is not None else old['title'],
                  'body':body,'scope':scope,'sources':sources,'flags':flags,'related_ids':old['related_ids']}
        if project_id is not None:
            proposal['project_id']=project_id
        data,policy,blocked=prepare_capture(vault,proposal,skill_active=True,retain_sensitive=retain_sensitive,
                                           includes_inference=includes_inference,**runtime)
        if blocked is not None:
            return blocked
        with _capture_lock(vault):
            fresh=_snapshot(vault,max_notes)
            if _policy(vault)!=policy:
                return _result('unavailable','capture_settings_changed')
            if any(key not in fresh['resolved'] or fresh['resolved'][key]['token']!=expected_tokens[key] for key in ids):
                return _result('needs_review','stale_correction_snapshot',candidates=ids)
            fresh_active={key for key,r in fresh['resolved'].items() if _subject_key(r['metadata'])==subject
                          and (key not in fresh['superseded'] or key in fresh['semantic_conflicts'])
                          and r['metadata']['state']!='superseded'}
            if not ambiguous and fresh_active!=set(ids):
                return _result('needs_review','resolve_all_subject_claims',candidates=fresh_active)
            if not ambiguous and len(records)==1 and old['state']=='current' and old['basis']==ORIGINS.get(origin) and body==records[0]['body'] and proposal['title']==old['title'] and all(s in old['sources'] for s in sources):
                return _result('unchanged','correction_already_recorded',record_id=ids[0])
            data=dict(old, title=proposal['title'],basis=ORIGINS[origin],state='unresolved' if ambiguous else 'current',sources=list(sources))
            now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            same_identity=old['kind']=='project'
            if same_identity:
                from project_identity import parse_project, match_project
                proposed=parse_project(_serialize(data,body))
                projects=[parse_project(_serialize(r['metadata'],r['body'])) for r in fresh['resolved'].values()
                          if r['metadata']['kind']=='project' and r['metadata']['state']=='current']
                match=match_project(projects,project_id=ids[0],repository=proposed['repository'])
                if match['status']!='matched':
                    return _result('needs_review','project_repository_conflict',candidates=match.get('candidate_ids',[]))
            else:
                data.update(id=str(uuid.uuid4()),created_at=now,
                            supersedes=[] if ambiguous else ids)
            data['updated_at']=max(now,data['created_at'])
            result=write_record(vault,data,body,expected_token=expected_tokens[ids[0]] if same_identity else None,
                                dependencies=None if same_identity else expected_tokens,
                                inherit_from=None if same_identity else ids[0],**runtime)
            written=result
            written_id=data['id']
            status=result['status']
            if ambiguous and status=='conflict':
                status='unresolved'
            if status in ('created','updated','unchanged'):
                final=memory_snapshot(vault,max_notes)
                if ambiguous or data['id'] in final['semantic_conflicts'] or final['incomplete']:
                    status='unresolved'
            outcome=_result(status,'contradiction_recorded' if ambiguous else 'correction_'+status,
                            writer=result,record_id=data['id'])
            if status in ('created','updated'):
                outcome['announcement']='Memory corrected.'
            return outcome
    except BlockingIOError:
        return _result('busy','capture_in_progress_retry')
    except (OSError,ValueError,TypeError,KeyError,AttributeError,ImportError):
        return _result('unavailable','invalid_or_inaccessible_correction',writer=written,record_id=written_id)


def correct(vault, record_ids, body, sources, **options):
    """Apply an explicitly clear user correction to all active claims of a subject."""
    return _change(vault,record_ids,body,sources,**options)


def record_contradiction(vault, record_ids, body, sources, **options):
    """Retain an uncertain claim without choosing it as current truth."""
    return _change(vault,record_ids,body,sources,ambiguous=True,**options)
