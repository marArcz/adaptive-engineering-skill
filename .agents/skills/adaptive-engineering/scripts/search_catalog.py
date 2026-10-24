#!/usr/bin/env python3
"""Query the local curated GitHub catalog, without network operations."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from _vault_common import resolve_vault

def search(vault:Path,query:str,limit:int=3)->dict:
    cat=vault/'references'/'github'/'catalog.json'
    if not cat.is_file():raise ValueError(f'Catalog not found: {cat}')
    try: obj=json.loads(cat.read_text(encoding='utf8'))
    except (OSError,ValueError) as e:raise ValueError(f'Invalid catalog: {e}') from e
    items=obj.get('repositories',[])
    if not isinstance(items,list):raise ValueError('Catalog.repositories must be a list')
    terms=[t.casefold() for t in re.findall(r'[\w.+-]+',query) if len(t)>1]
    if not terms:raise ValueError('Query must contain searchable words')
    hits=[]
    for item in items:
        if not isinstance(item,dict): continue
        corpus=' '.join(str(item.get(k,'')) for k in ('id','description','tags','use_for','limitations')).casefold()
        score=sum(2*(t in str(item.get('tags','')).casefold())+(t in corpus) for t in terms)
        if score:
            hits.append({'id':item.get('id'),'url':item.get('url'),'status':item.get('status','candidate'), 'reviewed_commit':item.get('reviewed_commit'),'verified_at':item.get('verified_at'),'score':int(score),'use_for':item.get('use_for',[]),'important_paths':item.get('important_paths',[]),'limitations':item.get('limitations',[])})
    hits.sort(key=lambda r:(-r['score'],r['status']!='approved',str(r['id'])))
    return {'query':query,'catalog':str(cat),'matches':hits[:limit],'notice':'No cloning/fetching occurred; candidate entries require independent verification.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vault');p.add_argument('--query',required=True);p.add_argument('--limit',type=int,default=3)
    a=p.parse_args()
    if not 1<=a.limit<=30:p.error('limit must be 1..30')
    vault=resolve_vault(a.vault)
    if vault is None:p.error('No vault configured. Run configure.py --vault PATH or set ENGINEERING_VAULT_PATH.')
    try:print(json.dumps(search(vault,a.query,a.limit),indent=2))
    except ValueError as e:p.error(str(e))
if __name__=='__main__':main()
