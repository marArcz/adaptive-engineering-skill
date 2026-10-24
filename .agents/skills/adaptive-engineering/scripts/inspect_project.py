#!/usr/bin/env python3
"""Read-only root-manifest inspection. Python 3.9+, no dependencies."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

MANIFESTS = ('package.json','composer.json','pyproject.toml','go.mod','Cargo.toml','Gemfile','.csproj','pom.xml','build.gradle','artisan','vite.config.ts','next.config.js','nuxt.config.ts')

def safe_json(path: Path) -> dict:
    try:
        if path.stat().st_size > 512000:
            return {}
        obj = json.loads(path.read_text(encoding='utf-8'))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}

def detect(root: Path) -> dict:
    if not root.is_dir():
        raise ValueError(f'Not a directory: {root}')
    names = {p.name for p in root.iterdir() if p.is_file() and not p.name.startswith('.env')}
    manifests = sorted(n for n in names if n in MANIFESTS or n.endswith('.csproj'))
    langs, frameworks = set(), []
    package = safe_json(root / 'package.json') if 'package.json' in names else {}
    composer = safe_json(root / 'composer.json') if 'composer.json' in names else {}
    dependencies = {**package.get('dependencies', {}), **package.get('devDependencies', {})} if isinstance(package.get('dependencies', {}),dict) and isinstance(package.get('devDependencies',{}),dict) else {}
    phpdeps = {**composer.get('require', {}), **composer.get('require-dev', {})} if isinstance(composer.get('require', {}),dict) and isinstance(composer.get('require-dev', {}),dict) else {}
    def add(name, evidence, declaration=None):
        frameworks.append({'name':name, 'evidence':evidence, 'declared_requirement':declaration})
    if 'package.json' in names:
        langs.add('JavaScript/TypeScript')
        for key,name in [('react','React'),('vue','Vue'),('next','Next.js'),('nuxt','Nuxt'),('@angular/core','Angular'),('svelte','Svelte'),('vite','Vite')]:
            if key in dependencies: add(name, 'package.json', dependencies[key])
    if 'composer.json' in names:
        langs.add('PHP')
        if 'laravel/framework' in phpdeps: add('Laravel','composer.json', phpdeps['laravel/framework'])
        if 'symfony/framework-bundle' in phpdeps: add('Symfony','composer.json',phpdeps['symfony/framework-bundle'])
    if 'artisan' in names and not any(f['name']=='Laravel' for f in frameworks): add('Laravel (possible)','artisan',None)
    if 'pyproject.toml' in names: langs.add('Python')
    if 'go.mod' in names: langs.add('Go')
    if 'Cargo.toml' in names: langs.add('Rust')
    if 'Gemfile' in names: langs.add('Ruby')
    if 'pom.xml' in names or 'build.gradle' in names: langs.add('Java/JVM')
    if any(n.endswith('.csproj') for n in names): langs.add('.NET')
    if 'pyproject.toml' in names:
        try:
            text=(root/'pyproject.toml').read_text(encoding='utf8')[:32768].lower()
            for token,name in [('django','Django'),('fastapi','FastAPI'),('flask','Flask')]:
                if re.search(r'\b'+token+r'\b',text): add(name,'pyproject.toml',None)
        except (OSError,UnicodeError): pass
    locks = [('pnpm-lock.yaml','pnpm'),('yarn.lock','yarn'),('package-lock.json','npm'),('bun.lockb','bun'),('bun.lock','bun'),('composer.lock','composer'),('uv.lock','uv'),('poetry.lock','poetry'),('Cargo.lock','cargo')]
    return {'project':root.name,'manifests':manifests,'languages':sorted(langs),'framework_hints':frameworks,'lockfile_hints':[tool for file,tool in locks if file in names], 'top_level_dirs':sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith('.') and p.name not in ('node_modules','vendor','dist','build'))[:30], 'notice':'Manifest requirements are not confirmed installed versions; inspect lockfiles/commands when needed.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('repo',nargs='?',default='.')
    args=ap.parse_args()
    try:
        print(json.dumps(detect(Path(args.repo).expanduser().resolve()), indent=2))
    except ValueError as e: ap.error(str(e))

if __name__=='__main__':main()
