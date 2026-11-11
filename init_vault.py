#!/usr/bin/env python3
"""Create an Obsidian vault from the included template; never replace existing files."""
from __future__ import annotations
import argparse,shutil,subprocess
from pathlib import Path
from memory_setup import setup_memory
HERE=Path(__file__).resolve().parent
SOURCE=HERE/'vault-template'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--path',required=True)
    p.add_argument('--git-init',action='store_true',help='Explicitly run git init after creation; no commit/push')
    p.add_argument('--dry-run',action='store_true')
    a=p.parse_args();dest=Path(a.path).expanduser().resolve()
    if dest.exists() and not dest.is_dir():p.error(f'Target is not a directory: {dest}')
    fresh=not dest.exists() or not any(dest.iterdir())
    print(('Would initialize' if a.dry_run else 'Initializing')+' vault:',dest)
    if a.dry_run:return
    try:
        dest.mkdir(parents=True,exist_ok=True)
        setup_memory(dest)
        for src in sorted(SOURCE.rglob('*')) if fresh else ():
            rel=src.relative_to(SOURCE);d=dest/rel
            if rel == Path('memory-record.md'):continue
            if src.is_dir():d.mkdir(parents=True,exist_ok=True)
            elif src.is_file():
                d.parent.mkdir(parents=True,exist_ok=True)
                try:
                    with src.open('rb') as source, d.open('xb') as target:
                        shutil.copyfileobj(source,target)
                except FileExistsError:pass
    except (OSError, ValueError) as ex:
        p.error(f'Vault setup incomplete: {ex}')
    if a.git_init:
        try: subprocess.run(['git','init',str(dest)],check=True)
        except (OSError,subprocess.CalledProcessError) as ex:
            p.error(f'Vault created, but git init failed: {ex}')
    print('Open this folder in Obsidian. Git remote and push remain manual.')
if __name__=='__main__':main()
