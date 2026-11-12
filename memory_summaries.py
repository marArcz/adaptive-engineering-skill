"""Regenerated, provenance-linked views; summaries are never source records."""
from __future__ import annotations

import json
from collections import defaultdict

from memory_search import memory_snapshot
from memory_journal import _event, FIELDS, MAX_BODY
from memory_store import _pairs

MAX_CHARS = 3000
MAX_ITEMS = 8


def _normal(text):
    return ' '.join(text.split()).casefold()


def _feedback(node):
    """Only structured recorded collaboration feedback can support inferred style."""
    data = node['metadata']
    if data['kind'] != 'experience' or data['basis'] not in ('user-stated','source-supported'):
        return None
    try:
        event = json.loads(node['body'], object_pairs_hook=_pairs)
        if (not isinstance(event,dict) or set(event)!=FIELDS or type(event['journal_version']) is not int
                or event['journal_version']!=1 or event['significance']!='collaboration_feedback'
                or len(node['body'])>MAX_BODY):
            return None
        lesson=event['inferred_lesson']
        if lesson is not None and (not isinstance(lesson,dict) or set(lesson)!={'text','basis','tentative'}
                                   or lesson['basis']!='inferred' or lesson['tentative'] is not True):
            return None
        _event(event['significance'],event['context'],event['what_happened'],event['why_it_mattered'],
               event['observed_outcome'],lesson['text'] if lesson else None)
        return event
    except (ValueError,TypeError,KeyError):
        return None


def _independent(keys, nodes, events):
    selected, seen_events, seen_sources = [], set(), set()
    for key in sorted(keys):
        fingerprint = _normal(events[key]['what_happened'])
        sources = {_normal(s) for s in nodes[key]['metadata']['sources']}
        if fingerprint in seen_events or not sources or sources & seen_sources:
            continue
        selected.append(key)
        seen_events.add(fingerprint)
        seen_sources.update(sources)
    return selected


def summary_entries(snapshot, *, project_id=None, profile_only=False):
    nodes = {}
    revisions = {}
    for key, record in snapshot['resolved'].items():
        if key in snapshot['superseded'] or record['metadata']['state']!='current':
            continue
        data=record['metadata']
        if data['scope']=='project' and (profile_only or data['project_id']!=project_id):
            continue
        revision=record['tips'][0]
        nodes[key]=snapshot['groups'][key][revision]
        revisions[key]=revision
    events={key:event for key,node in nodes.items() if (event:=_feedback(node)) is not None}
    rows=[]
    excluded=[]

    def entry(text, basis, keys, view, kind, scope='general', project=None):
        pointers=[]
        for key in keys:
            node=nodes[key]
            data=node['metadata']
            pointers.append({'id':key,'revision_id':revisions[key],'digest':node['digest'],
                             'path':node['path'],'basis':data['basis'],'title':data['title'],
                             'sources':list(data['sources']),
                             'missing_links':sum(ref not in snapshot['resolved'] or ref in snapshot['superseded']
                                                 or snapshot['resolved'][ref]['metadata']['state']!='current'
                                                 for ref in data['related_ids']+data['supersedes'])})
        row={'text':text,'basis':basis,'tentative':basis=='inferred','source_records':pointers,
             'view':view,'entry_type':kind,'scope':scope,'is_source':False}
        if project is not None:
            row['project_id']=project
        rows.append(row)

    for key,node in sorted(nodes.items()):
        data=node['metadata']
        scoped=data['scope']=='project'
        if data['kind'] in ('user_fact','preference'):
            entry(node['body'],data['basis'],[key],'project_adjustment' if scoped else 'profile',
                  'record',data['scope'],data.get('project_id'))
        elif data['kind']=='assistant_identity' and not profile_only:
            support=[]
            if data['basis']=='inferred':
                eligible=[r for r in data['related_ids'] if r in events
                          and nodes[r]['metadata']['scope']==data['scope']
                          and nodes[r]['metadata'].get('project_id')==data.get('project_id')]
                support=_independent(eligible,nodes,events)
                if len(support)<2:
                    excluded.append(key)
                    continue
            entry(node['body'],data['basis'],[key,*support],
                  'project_adjustment' if scoped else 'identity','record',data['scope'],data.get('project_id'))
    if not profile_only:
        lessons=defaultdict(list)
        for key,event in events.items():
            data=nodes[key]['metadata']
            if event['inferred_lesson'] is not None:
                lessons[(data['scope'],data.get('project_id'),_normal(event['inferred_lesson']['text']))].append(key)
        used=set()
        for (scope,project,_),keys in sorted(lessons.items(),key=lambda item:str(item[0])):
            supporting=_independent(keys,nodes,events)
            if len(supporting)<2:
                continue
            text=events[supporting[0]]['inferred_lesson']['text']
            entry(text,'inferred',supporting,'identity' if scope=='general' else 'project_adjustment',
                  'inferred_trait',scope,project)
            used.update(supporting)
        for key,event in sorted(events.items()):
            if key in used:
                continue
            data=nodes[key]['metadata']
            entry(event['what_happened'],data['basis'],[key],
                  'identity' if data['scope']=='general' else 'project_adjustment',
                  'feedback_not_trait',data['scope'],data.get('project_id'))
    # Balance the views so a large profile cannot hide the entire identity.
    buckets={view:sorted([r for r in rows if r['view']==view],
                        key=lambda r:(r['entry_type']=='feedback_not_trait',r['tentative'],r['source_records'][0]['id']))
             for view in ('profile','identity','project_adjustment')}
    ordered=[]
    while any(buckets.values()):
        for view in buckets:
            if buckets[view]:
                ordered.append(buckets[view].pop(0))
    return ordered, excluded


def build_summaries(vault, *, project_id=None, max_chars=MAX_CHARS, max_items=MAX_ITEMS,
                    max_notes=1500, profile_only=False, _snapshot=None):
    """Only text is budgeted for context; other fields are inspectable diagnostics."""
    if not isinstance(max_chars,int) or not 1<=max_chars<=MAX_CHARS:
        raise ValueError('summary max_chars must be 1..3000')
    if not isinstance(max_items,int) or not 1<=max_items<=MAX_ITEMS:
        raise ValueError('summary max_items must be 1..8')
    if project_id is not None:
        from memory_contract import _uuid
        _uuid(project_id,'project_id')
    snapshot=_snapshot if _snapshot is not None else memory_snapshot(vault,max_notes)
    entries,excluded=summary_entries(snapshot,project_id=project_id,profile_only=profile_only)
    heading='\nDerived memory views (reference only; current instructions, tool permissions and source corrections take precedence).\n'
    if not entries:
        heading+='No eligible current general profile records available.\n' if profile_only else 'No eligible current general profile or identity records available.\n'
    if excluded:
        heading+='Unsupported identity inferences omitted; one event is not a trait.\n'
    if snapshot['incomplete']:
        heading+='Memory scan incomplete; derived views unavailable.\n'
    elif any(snapshot['stats'][k] for k in ('invalid_files','conflicted_records','unreadable_files','unsafe_links','oversized_files')):
        heading+='Some source records were excluded or inaccessible.\n'
    footer='Summary omitted or shortened: false.\n'
    text=heading if len(heading)+len(footer)<=max_chars else ''
    selected=[]
    shortened=len(entries)>max_items or not text
    remaining=max_chars-len(text)-len(footer)
    for row in entries[:max_items] if text else []:
        label={'profile':'User profile','identity':'Assistant working style','project_adjustment':'Scoped project adjustment'}[row['view']]
        label+=' (feedback, not a trait)' if row['entry_type']=='feedback_not_trait' else ''
        label+=' (tentative inference)' if row['tentative'] else ''
        header=f"\n{label} | {row['scope']}"+((':'+row['project_id']) if 'project_id' in row else '')+f" | basis {row['basis']}\n"
        pointers=row['source_records']
        for pointer in pointers[:3]:
            source=pointer['sources'][0]
            header+=(f"ID {pointer['id']} | revision {pointer['revision_id']}\n"
                     f"Title: {pointer['title'][:120]}\nSource: {source[:200]}\nFile: {pointer['path']}\n")
            if pointer['missing_links']:
                header+=f"Missing or excluded linked memories: {pointer['missing_links']}.\n"
            shortened |= len(source)>200 or len(pointer['sources'])>1 or len(pointer['title'])>120
        shortened |= len(pointers)>3
        count=min(400,len(row['text']),remaining-len(header)-1)
        if count<=0:
            shortened=True
            continue
        block=header+row['text'][:count]+'\n'
        text+=block
        remaining-=len(block)
        selected.append(row)
        shortened |= count<len(row['text'])
    if text:
        text+='Summary omitted or shortened: '+('true' if shortened else 'false')+'.\n'
    return {'text':text,'characters':len(text),'truncated':bool(shortened or snapshot['scan_truncated']),
            'summary_version':1,'assistant_view':'assistant','profile_view':'user','items':selected,'eligible_count':len(entries),
            'source_ids':list(dict.fromkeys(p['id'] for r in selected for p in r['source_records'])),
            'excluded_identity_ids':excluded,'memory_incomplete':snapshot['incomplete'],
            'is_source':False,'project_id':project_id}
