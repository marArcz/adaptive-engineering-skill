"""Shared stdlib-only vault resolution for skill scripts."""
from __future__ import annotations
import json, os
from pathlib import Path

def config_path()->Path:
    return Path.home()/'.adaptive-engineering'/'config.json'

def resolve_vault(explicit:str|None)->Path|None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if os.environ.get('ENGINEERING_VAULT_PATH'):
        return Path(os.environ['ENGINEERING_VAULT_PATH']).expanduser().resolve()
    try:
        p=json.loads(config_path().read_text(encoding='utf-8')).get('vault_path')
        return Path(p).expanduser().resolve() if isinstance(p,str) and p else None
    except (OSError,ValueError):
        return None
