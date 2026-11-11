#!/usr/bin/env python3
"""Explicitly configure local vault path for skill tools; stores no credentials."""
from __future__ import annotations
import argparse,json,os
from pathlib import Path
from memory_setup import read_policy,set_capture,setup_memory

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--vault',help='Existing Obsidian vault folder')
    group.add_argument('--show',action='store_true')
    group.add_argument('--show-capture',action='store_true',help='Show portable capture settings for the effective vault')
    group.add_argument('--capture',choices=['active','paused'],help='Change capture for the effective vault')
    a=ap.parse_args()
    target=Path.home()/'.adaptive-engineering'/'config.json'
    if a.show:
        if target.exists():print(target.read_text(encoding='utf8'))
        else: print('No vault configured:',target)
        return
    if a.show_capture or a.capture:
        try:
            override=os.environ.get('ENGINEERING_VAULT_PATH')
            if override: location=override
            else:
                obj=json.loads(target.read_text(encoding='utf8'))
                if not isinstance(obj,dict) or not isinstance(obj.get('vault_path'),str) or not obj['vault_path']:
                    raise ValueError('No valid vault_path in local configuration')
                location=obj['vault_path']
            v=Path(location).expanduser().resolve()
            if a.capture:set_capture(v,a.capture)
            print(json.dumps(read_policy(v),indent=2))
            if override:print('Effective vault selected by ENGINEERING_VAULT_PATH:',v)
        except (OSError,ValueError) as exc:ap.error(str(exc))
        return
    v=Path(a.vault).expanduser().resolve()
    if not v.is_dir():ap.error(f'Vault folder does not exist: {v}')
    if not (v/'HOME.md').exists():print('Warning: HOME.md not found; ensure this is your intended Obsidian vault')
    obj={}
    if target.exists():
        try:
            obj=json.loads(target.read_text(encoding='utf8'))
            if not isinstance(obj,dict):ap.error('Existing config is invalid; inspect it before retrying')
        except (OSError,ValueError):ap.error('Existing config is invalid; inspect it before retrying')
    try:setup_memory(v)
    except (OSError,ValueError) as exc:ap.error(f'Vault setup incomplete; configuration not changed: {exc}')
    obj['vault_path']=str(v)
    try:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf8')
    except OSError as exc:ap.error(f'Vault scaffolding may have been created, but local configuration was not saved: {exc}')
    print('Configured local vault:',v,'\nConfig:',target)
    override=os.environ.get('ENGINEERING_VAULT_PATH')
    if override and Path(override).expanduser().resolve()!=v:
        print('Note: ENGINEERING_VAULT_PATH overrides this saved location:',Path(override).expanduser().resolve())
if __name__=='__main__':main()
