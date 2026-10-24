#!/usr/bin/env python3
"""Explicitly configure local vault path for skill tools; stores no credentials."""
from __future__ import annotations
import argparse,json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--vault',help='Existing Obsidian vault folder')
    group.add_argument('--show',action='store_true')
    a=ap.parse_args()
    target=Path.home()/'.adaptive-engineering'/'config.json'
    if a.show:
        if target.exists():print(target.read_text(encoding='utf8'))
        else: print('No vault configured:',target)
        return
    v=Path(a.vault).expanduser().resolve()
    if not v.is_dir():ap.error(f'Vault folder does not exist: {v}')
    if not (v/'HOME.md').exists():print('Warning: HOME.md not found; ensure this is your intended Obsidian vault')
    obj={}
    if target.exists():
        try:
            obj=json.loads(target.read_text(encoding='utf8'))
            if not isinstance(obj,dict):obj={}
        except (OSError,ValueError):ap.error('Existing config is invalid; inspect it before retrying')
    obj['vault_path']=str(v)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf8')
    print('Configured local vault:',v,'\nConfig:',target)
if __name__=='__main__':main()
