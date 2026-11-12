#!/usr/bin/env python3
"""Install adaptive-engineering without overwriting a preexisting skill/AGENTS.md."""
from __future__ import annotations
import argparse,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
SKILL=HERE/'.agents'/'skills'/'adaptive-engineering'

def destination(target:str, repo:str|None)->Path:
    if target=='repo':
        if not repo:raise ValueError('--repo is required for target repo')
        root=Path(repo).expanduser().resolve()
        if not root.is_dir():raise ValueError(f'Repository does not exist: {root}')
        return root/'.agents'/'skills'/'adaptive-engineering'
    home=Path.home()
    roots={'codex-global':home/'.agents'/'skills','antigravity-global':home/'.gemini'/'config'/'skills','antigravity-cli-global':home/'.gemini'/'antigravity-cli'/'skills'}
    return roots[target]/'adaptive-engineering'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',required=True,choices=['repo','codex-global','antigravity-global','antigravity-cli-global'])
    p.add_argument('--repo')
    p.add_argument('--with-agents',action='store_true',help='On repo install, create AGENTS.md only if none exists')
    p.add_argument('--dry-run',action='store_true')
    a=p.parse_args()
    if a.with_agents and a.target!='repo':p.error('--with-agents only applies to repo installation')
    if not (SKILL/'SKILL.md').is_file():p.error(f'Skill source missing: {SKILL}')
    try:dest=destination(a.target,a.repo)
    except ValueError as exc:p.error(str(exc))
    if dest.exists():p.error(f'Existing installation will not be overwritten: {dest}')
    print(('Would install' if a.dry_run else 'Installing')+' skill:',dest)
    if not a.dry_run:
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(SKILL,dest)
        for module in ('memory_operations.py','project_identity.py','memory_capture.py','memory_setup.py','memory_context.py','memory_search.py','memory_store.py','memory_contract.py','memory_boundary.py'):
            shutil.copyfile(HERE/module,dest/'scripts'/module)
    if a.with_agents:
        root=Path(a.repo).expanduser().resolve(); agents=root/'AGENTS.md'
        if agents.exists():print('Existing AGENTS.md preserved:',agents)
        elif a.dry_run:print('Would create AGENTS.md:',agents)
        else:
            shutil.copyfile(HERE/'AGENTS.example.md',agents)
            print('Created AGENTS.md:',agents)
    if a.target=='repo':
        legacy=Path(a.repo).expanduser().resolve()/'.agents'/'skills'/'web-engineering'
        if legacy.exists():print('NOTE: v0.3 web-engineering remains installed separately; remove/disable manually after migration checks:',legacy)
if __name__=='__main__':main()
