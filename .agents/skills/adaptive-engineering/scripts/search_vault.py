#!/usr/bin/env python3
"""Search Obsidian Markdown note metadata/text locally; return short file-path results."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from _vault_common import resolve_vault

SKIP={'.obsidian','.git','.trash','node_modules','attachments','templates','research'}

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

def search(vault:Path,query:str,limit:int=3,max_notes:int=1500)->dict:
    if not vault.is_dir(): raise ValueError(f'Vault directory is missing or inaccessible: {vault}')
    terms=[t.casefold() for t in re.findall(r'[\w.+-]+',query) if len(t)>1]
    if not terms: raise ValueError('Query must contain searchable words')
    results=[]; seen=0; truncated=False
    for p in sorted(vault.rglob('*.md')):
        rel=p.relative_to(vault)
        if any(part in SKIP or part.startswith('.') for part in rel.parts):continue
        if seen>=max_notes:truncated=True;break
        seen+=1
        try:
            if p.stat().st_size>128*1024:continue
            content=p.read_text(encoding='utf8')[:16000]
        except (OSError,UnicodeError):continue
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
    return {'vault':str(vault),'query':query,'notes_examined':seen,'truncated':truncated,'matches':results[:limit], 'notice':'Candidate notes are unverified; inspect before adopting. Paths, not full note content, are returned.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vault');p.add_argument('--query',required=True);p.add_argument('--limit',type=int,default=3)
    a=p.parse_args()
    if not 1<=a.limit<=30:p.error('limit must be 1..30')
    vault=resolve_vault(a.vault)
    if vault is None:p.error('No vault configured. Run configure.py --vault PATH, set ENGINEERING_VAULT_PATH, or pass --vault.')
    try:print(json.dumps(search(vault,a.query,a.limit),indent=2))
    except ValueError as e:p.error(str(e))
if __name__=='__main__':main()
