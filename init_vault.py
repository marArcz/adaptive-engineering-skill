#!/usr/bin/env python3
"""Create an Obsidian vault from the included template; never replace existing files."""
from __future__ import annotations
import argparse,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
SOURCE=HERE/'vault-template'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--path',required=True)
    p.add_argument('--git-init',action='store_true',help='Explicitly run git init after creation; no commit/push')
    p.add_argument('--dry-run',action='store_true')
    a=p.parse_args();dest=Path(a.path).expanduser().resolve()
    if dest.exists() and any(dest.iterdir()):p.error(f'Target is not empty; nothing overwritten: {dest}')
    print(('Would initialize' if a.dry_run else 'Initializing')+' vault:',dest)
    if a.dry_run:return
    dest.mkdir(parents=True,exist_ok=True)
    for src in sorted(SOURCE.rglob('*')):
        rel=src.relative_to(SOURCE);d=dest/rel
        if src.is_dir():d.mkdir(parents=True,exist_ok=True)
        elif src.is_file():
            d.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src,d)
    if a.git_init:
        try: subprocess.run(['git','init',str(dest)],check=True)
        except (OSError,subprocess.CalledProcessError) as ex:
            p.error(f'Vault created, but git init failed: {ex}')
    print('Open this folder in Obsidian. Git remote and push remain manual.')
if __name__=='__main__':main()
