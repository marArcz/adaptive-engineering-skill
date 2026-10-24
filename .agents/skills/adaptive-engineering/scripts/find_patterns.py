#!/usr/bin/env python3
"""Bounded read-only filename/content search. Never expands hidden or dependency dirs."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path

EXCLUDE_DIRS={'.git','.obsidian','.env','node_modules','vendor','dist','build','target','coverage','.next','.nuxt','.venv','venv','__pycache__','.idea','.vscode','out','.turbo','.cache'}
EXCLUDE_EXT={'.png','.jpg','.jpeg','.gif','.webp','.pdf','.zip','.gz','.lock','.min.js','.map','.svg','.bin','.exe','.dll','.pem','.key','.p12','.db','.sqlite','.sqlite3'}

def find(repo:Path, scope:str, term:str, max_files:int=2500, limit:int=12) -> dict:
    if not term.strip() or not repo.is_dir(): raise ValueError('Require existing repository and nonempty query')
    base=(repo/scope).resolve()
    if not base.is_relative_to(repo.resolve()) or not base.is_dir(): raise ValueError('Scope must be an existing directory inside repository')
    files_scanned=0; matches=[]; truncated=False; needle=term.casefold()
    for path, dirs, files in os.walk(base):
        dirs[:]=sorted(d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.'))
        for name in sorted(files):
            if files_scanned>=max_files: truncated=True; break
            if name.startswith('.env') or name.startswith('.') or Path(name).suffix.lower() in EXCLUDE_EXT: continue
            f=Path(path)/name
            if not f.is_file() or f.is_symlink(): continue
            try:
                if f.stat().st_size>128*1024: continue
                files_scanned+=1
                file_match=needle in name.casefold()
                snippets=[]
                # Only inspect source-text-ish files; never parse binary
                if f.suffix.lower() in {'.py','.php','.ts','.tsx','.js','.jsx','.vue','.go','.rs','.cs','.java','.rb','.html','.css','.scss','.md','.json','.yml','.yaml','.toml','.sql','.blade.php'}:
                    for i,line in enumerate(f.read_text(encoding='utf-8').splitlines(),1):
                        if needle in line.casefold():
                            # Avoid returning very long code/config lines
                            snippets.append({'line':i,'excerpt':line.strip()[:160]})
                            if len(snippets)==2: break
                if file_match or snippets:
                    matches.append({'path':f.relative_to(repo).as_posix(),'filename_match':file_match,'snippets':snippets})
                    if len(matches)>=limit: truncated=True; break
            except (OSError,UnicodeError): continue
        if truncated: break
    return {'query':term,'scope':base.relative_to(repo).as_posix(),'files_scanned':files_scanned,'truncated':truncated,'matches':matches}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',default='.')
    p.add_argument('--scope',default='.')
    p.add_argument('--query',required=True)
    p.add_argument('--limit',type=int,default=12)
    p.add_argument('--max-files',type=int,default=2500)
    a=p.parse_args()
    if not 1<=a.limit<=100 or not 1<=a.max_files<=20000:p.error('invalid limit/max-files')
    try: print(json.dumps(find(Path(a.repo).expanduser().resolve(),a.scope,a.query,a.max_files,a.limit),indent=2))
    except ValueError as e:p.error(str(e))
if __name__=='__main__': main()
