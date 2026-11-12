#!/usr/bin/env python3
"""Search Obsidian Markdown note metadata/text locally; return short file-path results."""
from __future__ import annotations
import argparse,json,re,sys,os
from pathlib import Path
from _vault_common import resolve_vault
from vault_guard import has_conflict_markers

SKIP={'.obsidian','.git','.trash','node_modules','attachments','templates'}

def parse_frontmatter(text:str)->dict:
    if not text.startswith('---\n'): return {}
    end=text.find('\n---',4)
    if end<0:return {}
    out={}
    for line in text[4:end].splitlines():
        if ':' in line and not line.startswith(' '):
            key,value=line.split(':',1)
            if key.strip() in {'title','status','tags','technology','applies_to','verified_at'}:out[key.strip()]=value.strip().strip('"\'')
    return out

def _walk_notes(vault, onerror):
    for directory, dirs, files in os.walk(vault,onerror=onerror,followlinks=False):
        folder=Path(directory)
        kept=[]
        for name in sorted(dirs):
            rel=(folder/name).relative_to(vault)
            if name in SKIP or name.startswith('.') or (folder/name).is_symlink():continue
            if rel.parts[0]=='memory':continue
            if 'research' in rel.parts and rel.parts[0]!='research':continue
            if rel.parts[0]=='research' and len(rel.parts)>1 and rel.parts[1]!='candidates':continue
            kept.append(name)
        dirs[:]=kept
        for name in sorted(files):
            if name.endswith('.md') and not name.startswith('.'):
                yield folder/name

def search(vault:Path,query:str,limit:int=3,max_notes:int=1500)->dict:
    if not vault.is_dir(): raise ValueError(f'Vault directory is missing or inaccessible: {vault}')
    if not 1<=limit<=30 or max_notes<1: raise ValueError('limit must be 1..30 and max_notes must be positive')
    terms=[t.casefold() for t in re.findall(r'[\w.+-]+',query) if len(t)>1]
    if not terms: raise ValueError('Query must contain searchable words')
    results=[]; seen=0; truncated=False; conflicts=0; unreadable=0; oversized=0
    def walk_error(error):
        nonlocal unreadable
        unreadable+=1
    for p in _walk_notes(vault,walk_error):
        rel=p.relative_to(vault)
        if rel.parts[0]=='memory' or p.is_symlink() or any(parent.is_symlink() for parent in p.parents if parent!=vault):continue
        if any(part in SKIP or part.startswith('.') for part in rel.parts):continue
        if 'research' in rel.parts and rel.parts[:2] != ('research','candidates'):continue
        if seen>=max_notes:truncated=True;break
        seen+=1
        try:
            with p.open('rb') as source:
                raw=source.read(128*1024+1)
            if len(raw)>128*1024:
                oversized+=1; continue
            content=raw.decode('utf8')
            if has_conflict_markers(content):
                conflicts+=1; continue
            content=content[:16000]
        except (OSError,UnicodeError):
            unreadable+=1; continue
        meta=parse_frontmatter(content)
        status=meta.get('status','unreviewed')
        if status not in ('approved','candidate'):continue
        name=rel.stem.casefold(); pathstr=rel.as_posix().casefold()
        meta_str=' '.join(str(meta.get(x,'')) for x in ('title','tags','technology')).casefold()
        body=content.casefold()
        score=sum(5*(t in name)+3*(t in pathstr)+2*(t in meta_str)+(t in body) for t in terms)
        if score>0:
            results.append({'path':rel.as_posix(),'status':status,'score':int(score),'title':meta.get('title') or rel.stem})
    results.sort(key=lambda x:(-x['score'],x['status']!='approved',x['path']))
    return {'vault':str(vault),'query':query,'notes_examined':seen,'truncated':truncated or len(results)>limit,'scan_truncated':truncated,'results_truncated':len(results)>limit,'result_count':len(results),'unreadable_files':unreadable,'oversized_files':oversized,'conflict_files_excluded':conflicts,'matches':results[:limit], 'notice':'Candidate notes are unverified; inspect before adopting. Paths, not full note content, are returned.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vault');p.add_argument('--query',default='');p.add_argument('--limit',type=int,default=3)
    p.add_argument('--max-notes',type=int,default=1500)
    p.add_argument('--mode',choices=['legacy','memory','all'],default='legacy')
    p.add_argument('--kind');p.add_argument('--scope',choices=['general','project','all'])
    p.add_argument('--project-id');p.add_argument('--record-id');p.add_argument('--related-to')
    p.add_argument('--history',action='store_true')
    a=p.parse_args()
    if not 1<=a.limit<=30 or a.max_notes<1:p.error('limit must be 1..30 and max-notes must be positive')
    if a.mode=='legacy' and any((a.kind,a.scope,a.project_id,a.record_id,a.related_to,a.history)):
        p.error('memory filters require --mode memory or --mode all')
    vault=resolve_vault(a.vault)
    if vault is None:p.error('No vault configured. Run configure.py --vault PATH, set ENGINEERING_VAULT_PATH, or pass --vault.')
    try:
        if a.mode=='legacy':
            output=search(vault,a.query,a.limit,a.max_notes)
        else:
            # Source checkouts keep the shared API at distribution root; the installer
            # bundles the same modules beside this script for standalone operation.
            distribution=Path(__file__).resolve().parents[4]
            if (distribution/'memory_search.py').is_file():sys.path.insert(0,str(distribution))
            from memory_search import search_memory
            memory=search_memory(vault,a.query,a.limit,a.max_notes,kind=a.kind,scope=a.scope,
                                 project_id=a.project_id,record_id=a.record_id,related_to=a.related_to,history=a.history)
            output={'vault':str(vault),'query':a.query,**memory}
            if a.mode=='all':
                legacy=search(vault,a.query,a.limit,a.max_notes)
                combined=[dict(row,result_type='memory') for row in memory['matches']]
                combined.extend(dict(row,result_type='legacy') for row in legacy['matches'])
                combined.sort(key=lambda row:(-row['score'],row['result_type'],row['path']))
                output['matches']=combined[:a.limit]
                output['result_count']=memory['result_count']+legacy['result_count']
                output['scan_truncated']=memory['scan_truncated'] or legacy['scan_truncated']
                output['results_truncated']=output['result_count']>a.limit
                output['truncated']=output['scan_truncated'] or output['results_truncated']
                output['legacy_limits']={k:legacy[k] for k in ('notes_examined','unreadable_files','oversized_files','conflict_files_excluded')}
                output['notice']+=' Legacy candidate notes are unverified; approved status remains a separate technical review label.'
        print(json.dumps(output,indent=2))
    except ValueError as e:p.error(str(e))
if __name__=='__main__':main()
