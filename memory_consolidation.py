"""Bounded consolidation of exact, current duplicates without removing history."""
from __future__ import annotations

import datetime
import json
from collections import defaultdict
from pathlib import Path

import memory_contract as contract
from memory_capture import prepare_capture, _capture_lock, _policy, _result
from memory_corrections import _account
from memory_search import memory_snapshot, _subject_key
from memory_store import write_record
from vault_guard import capture_gate


def _plan(snapshot, scope, project_id, max_groups):
    if scope not in (None,'general','project','all') or (scope=='project' and project_id is None):
        raise ValueError('invalid maintenance scope')
    if project_id is not None:
        contract._uuid(project_id,'project_id')
    if not isinstance(max_groups,int) or not 1<=max_groups<=10:
        raise ValueError('max_groups must be 1..10')
    if snapshot['incomplete'] or any(snapshot['stats'][k] for k in
            ('invalid_files','unreadable_files','oversized_files','unsafe_links')):
        return {'status':'unavailable','groups':[],'truncated':snapshot['scan_truncated']}
    buckets=defaultdict(list)
    for key,record in snapshot['resolved'].items():
        data=record['metadata']
        if key in snapshot['superseded'] or data['state']!='current' or data['kind']=='project':
            continue
        if scope=='general' and data['scope']!='general':
            continue
        if scope=='project' and data['scope']!='project':
            continue
        if data['scope']=='project':
            if project_id is None and scope!='all':
                continue
            if project_id is not None and data['project_id']!=project_id:
                continue
        extras={k:v for k,v in data.items() if k not in contract.FIELDS}
        refs=tuple(sorted({snapshot['aliases'].get(ref,ref) for ref in data['related_ids']}))
        signature=(_subject_key(data),data['title'],data['basis'],record['body'],refs,
                   json.dumps(extras,sort_keys=True,ensure_ascii=False,allow_nan=False))
        buckets[signature].append(key)
    groups=[]
    oversized=0
    for keys in sorted((sorted(keys) for keys in buckets.values() if len(keys)>1)):
        if len(keys)>30:
            oversized+=1
            continue
        canonical=keys[0]
        groups.append({'canonical_id':canonical,'record_ids':keys,
                       'expected_tokens':{key:snapshot['resolved'][key]['token'] for key in keys}})
    return {'status':'ready' if groups else 'unchanged','groups':groups[:max_groups],
            'eligible_groups':len(groups),'truncated':len(groups)>max_groups,
            'oversized_groups_skipped':oversized,'conflicted_records_skipped':snapshot['stats']['conflicted_records']}


def plan_consolidation(vault, *, scope=None, project_id=None, max_groups=3, max_notes=1500):
    """Read-only duplicate plan; it does not authorize a merge or classify private data."""
    try:
        return _plan(memory_snapshot(vault,max_notes),scope,project_id,max_groups)
    except (OSError,ValueError,TypeError,KeyError):
        return {'status':'unavailable','groups':[],'truncated':False}


def _merge(vault, snapshot, group, flags, retain_sensitive, policy, runtime):
    keys=group['record_ids']
    canonical=group['canonical_id']
    records=[snapshot['resolved'][key] for key in keys]
    old=records[0]['metadata']
    sources=list(dict.fromkeys(source for record in records for source in record['metadata']['sources']))
    links=list(dict.fromkeys(ref for record in records for ref in record['metadata']['related_ids']))
    equivalents=set(keys)-{canonical}
    supersedes={ref for record in records for ref in record['metadata']['supersedes']}
    dependencies={}
    for key,record in zip(keys,records):
        node=snapshot['groups'][key][record['tips'][0]]
        equivalents.update(node.get('equivalent_ids',[]))
        for ref,token in node.get('dependencies',{}).items():
            if ref in dependencies and dependencies[ref]!=token:
                return _result('needs_review','incompatible_source_guards')
            dependencies[ref]=token
        if key!=canonical:
            dependencies[key]=record['token']
    # The canonical record's prior revisions are guarded by its parent snapshot.
    if canonical in dependencies:
        if dependencies[canonical]!=records[0]['token']:
            return _result('needs_review','incompatible_self_guard')
        dependencies.pop(canonical)
    supersedes.update(equivalents)
    supersedes.discard(canonical)
    links=[ref for ref in links if ref not in {*keys,*equivalents}]
    includes_inference=old['basis']=='inferred'
    if old['kind']=='experience':
        includes_inference |= _account(records[0]['body'],records[0]['body'])
        # Legacy Markdown does not provide a trustworthy mixed-basis field schema.
        try:
            structured=json.loads(records[0]['body'])
        except ValueError:
            structured=None
        includes_inference |= not isinstance(structured,dict) or 'journal_version' not in structured
    category=('significant_shared_experiences' if old['kind']=='experience' else
              'useful_progress_commitments_questions' if old['title'].startswith(('Progress:','Commitment:','Question:')) else
              'durable_preferences_goals_decisions')
    origin={'user-stated':'user','source-supported':'observation','inferred':'inference'}[old['basis']]
    proposal={'category':category,'origin':origin,'kind':old['kind'],'title':old['title'],
              'body':records[0]['body'],'scope':old['scope'],'sources':sources,'flags':flags,'related_ids':links}
    if 'project_id' in old:
        proposal['project_id']=old['project_id']
    _,checked,blocked=prepare_capture(vault,proposal,skill_active=True,retain_sensitive=retain_sensitive,
                                     includes_inference=includes_inference,**runtime)
    if blocked is not None:
        return blocked
    if checked!=policy:
        return _result('unavailable','capture_settings_changed')
    data=dict(old,sources=sources,related_ids=links,supersedes=sorted(supersedes))
    now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    data['updated_at']=max(now,data['updated_at'])
    result=write_record(vault,data,records[0]['body'],expected_token=records[0]['token'],
                        dependencies=dependencies,equivalent_ids=sorted(equivalents),**runtime)
    return _result(result['status'],'consolidation_'+result['status'],writer=result,record_id=canonical)


def consolidate(vault, *, flags, skill_active=False, retain_sensitive=False, scope=None,
                project_id=None, max_groups=3, max_notes=1500, **runtime):
    """Run bounded active-skill maintenance; no scheduler, deletion or age policy."""
    if skill_active is not True:
        return {'status':'excluded','announcement':'','changes':[],'reason':'skill_inactive'}
    changes=[]
    pending_result=None
    try:
        vault=Path(vault)
        policy=_policy(vault)
        if policy['capture']=='paused':
            return {'status':'paused','announcement':'','changes':[]}
        if not capture_gate(vault).allowed:
            return {'status':'unavailable','announcement':'','changes':[],'reason':'merge_gate_blocked'}
        with _capture_lock(vault):
            snapshot=memory_snapshot(vault,max_notes)
            plan=_plan(snapshot,scope,project_id,max_groups)
            if plan['status']=='unavailable':
                return dict(plan,announcement='',changes=[])
            for group in plan['groups']:
                # Re-plan each group against current state to avoid acting on a prior merge.
                fresh=memory_snapshot(vault,max_notes)
                candidates=_plan(fresh,scope,project_id,10)
                exact=next((g for g in candidates['groups'] if g['record_ids']==group['record_ids']),None)
                if exact is None or exact['expected_tokens']!=group['expected_tokens']:
                    changes.append({'status':'needs_review','reason':'maintenance_snapshot_changed'})
                    break
                result=_merge(vault,fresh,exact,flags,retain_sensitive,policy,runtime)
                pending_result=result
                if result['status'] in ('updated','unchanged'):
                    after=memory_snapshot(vault,max_notes)
                    if after['incomplete'] or any(after['aliases'].get(key)!=group['canonical_id']
                                                for key in group['record_ids'] if key!=group['canonical_id']):
                        result=dict(result,status='conflict',announcement='',may_have_written=True)
                changes.append(result)
                pending_result=None
                if result['status'] not in ('updated','unchanged','excluded'):
                    break
            count=sum(r['status']=='updated' for r in changes)
            pending=any(r['status'] not in ('updated','unchanged','excluded') for r in changes)
            return {'status':'partial' if pending and count else 'updated' if count else changes[-1]['status'] if changes else 'unchanged',
                    'changes':changes,'groups_consolidated':count,'truncated':plan['truncated'],
                    'oversized_groups_skipped':plan.get('oversized_groups_skipped',0),
                    'conflicted_records_skipped':plan.get('conflicted_records_skipped',0),
                    'announcement':(f'Consolidated {count} duplicate memory group(s).'+(' Some work needs review.' if pending else '')) if count else ''}
    except BlockingIOError:
        return {'status':'busy','changes':changes,'announcement':''}
    except (OSError,ValueError,TypeError,KeyError,AttributeError,ImportError):
        return {'status':'unavailable','changes':changes,'announcement':'',
                'may_have_written':any(r.get('may_have_written',False) for r in changes)
                    or bool(pending_result and pending_result.get('may_have_written')),
                'pending_record_id':pending_result.get('record_id') if pending_result else None}
