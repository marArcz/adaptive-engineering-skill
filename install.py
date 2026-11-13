#!/usr/bin/env python3
"""Install adaptive-engineering without overwriting a preexisting skill/AGENTS.md."""
from __future__ import annotations
import argparse,fnmatch,shutil
from pathlib import Path
from distribution import RUNTIME_MODULES, SETUP_SCRIPTS, SKILL_NAMES, IGNORE_PATTERNS
HERE=Path(__file__).resolve().parent

def safe_components(root, path):
    current=root
    for part in path.relative_to(root).parts:
        current=current/part
        if current.is_symlink():raise ValueError(f'Symlink in installation resources or target: {current}')

def check_sources():
    for name in (*RUNTIME_MODULES,*SETUP_SCRIPTS,'AGENTS.example.md','vault-template/memory-record.md'):
        path=HERE/name
        safe_components(HERE,path)
        if not path.is_file():raise ValueError(f'Required distribution file missing: {name}')
    for tree in (*(HERE/'.agents/skills'/name for name in SKILL_NAMES),HERE/'vault-template'):
        safe_components(HERE,tree)
        if not tree.is_dir():raise ValueError(f'Required distribution area missing: {tree}')
        for path in tree.rglob('*'):
            if any(fnmatch.fnmatch(part,pattern) for part in path.relative_to(tree).parts for pattern in IGNORE_PATTERNS):continue
            if path.is_symlink():raise ValueError(f'Symlink in distribution: {path}')
    for name in SKILL_NAMES:
        if not (HERE/'.agents/skills'/name/'SKILL.md').is_file():raise ValueError(f'Skill source missing: {name}')

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
    try:
        check_sources()
        dest=destination(a.target,a.repo)
        anchor=Path(a.repo).expanduser().resolve() if a.target=='repo' else Path.home()
        targets=[dest.parent/name for name in SKILL_NAMES]
        for target in targets:
            safe_components(anchor,target)
            if target.exists() or target.is_symlink():raise ValueError(f'Existing installation will not be overwritten: {target}')
    except (OSError,ValueError) as exc:p.error(str(exc))
    for target in targets:print(('Would install' if a.dry_run else 'Installing')+' skill:',target)
    if not a.dry_run:
        try:
            dest.parent.mkdir(parents=True,exist_ok=True)
            for name,target in zip(SKILL_NAMES,targets):
                shutil.copytree(HERE/'.agents/skills'/name,target,ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))
            for module in (*RUNTIME_MODULES,*SETUP_SCRIPTS):
                shutil.copyfile(HERE/module,dest/'scripts'/module)
            shutil.copytree(HERE/'vault-template',dest/'scripts/vault-template',ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))
        except OSError as exc:
            p.error(f'Installation incomplete; inspect new destinations before retrying: {exc}')
    if a.with_agents:
        root=Path(a.repo).expanduser().resolve(); agents=root/'AGENTS.md'
        if agents.exists() or agents.is_symlink():print('Existing AGENTS.md preserved:',agents)
        elif a.dry_run:print('Would create AGENTS.md:',agents)
        else:
            try:
                with (HERE/'AGENTS.example.md').open('rb') as source,agents.open('xb') as target:
                    shutil.copyfileobj(source,target)
                print('Created AGENTS.md:',agents)
            except FileExistsError:print('Existing AGENTS.md preserved:',agents)
            except OSError as exc:p.error(f'Skills installed, but AGENTS.md creation failed: {exc}')
    if a.target=='repo':
        legacy=Path(a.repo).expanduser().resolve()/'.agents'/'skills'/'web-engineering'
        if legacy.exists():print('NOTE: v0.3 web-engineering remains installed separately; remove/disable manually after migration checks:',legacy)
if __name__=='__main__':main()
