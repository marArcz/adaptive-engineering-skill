#!/usr/bin/env python3
"""Build a tracked-source ZIP or verify it using disposable installations."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, BadZipFile

from distribution import BUNDLE_FILES, BUNDLE_TREES, IGNORE_PATTERNS, RUNTIME_MODULES, SETUP_SCRIPTS, SKILL_NAMES

TAG = re.compile(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?')
REQUIRED = (*BUNDLE_FILES, 'vault-template/memory-record.md', '.codex-plugin/plugin.json',
            '.agents/plugins/marketplace.json', *(f'.agents/skills/{name}/SKILL.md' for name in SKILL_NAMES))


def build_release(source, output, *, tag, ref='HEAD'):
    """Archive only selected tracked blobs; a Git tree ID supports precommit checks."""
    if not TAG.fullmatch(tag):
        raise ValueError('expected version tag such as v0.4.1 or v0.4.1-rc.1')
    if ref.startswith('-'):
        raise ValueError('expected a Git revision or tree ID')
    source, output = Path(source), Path(output)
    git_env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    git_env['GIT_OPTIONAL_LOCKS'] = '0'
    listed = subprocess.run(['git', '--literal-pathspecs', '-C', str(source), 'ls-tree', '-r', '-z', ref, '--',
                             *BUNDLE_FILES, *BUNDLE_TREES], check=True, capture_output=True, env=git_env).stdout
    paths = []
    for entry in listed.split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.decode().split('\t', 1)
        if any(fnmatch.fnmatch(part, pattern) for part in PurePosixPath(name).parts for pattern in IGNORE_PATTERNS):
            continue
        if metadata.split()[0] not in ('100644', '100755'):
            raise ValueError('distribution must contain ordinary tracked files, not links/submodules')
        paths.append(name)
    missing = set(REQUIRED) - set(paths)
    if missing:
        raise ValueError('required tracked distribution files missing: ' + ', '.join(sorted(missing)))
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with output.open('xb') as destination:
            created = True
            subprocess.run(['git', '--literal-pathspecs', '-C', str(source), 'archive', '--format=zip',
                            '--prefix=adaptive-engineering-' + tag + '/', ref, '--', *paths],
                           stdout=destination, stderr=subprocess.PIPE, check=True, env=git_env)
        with ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise ValueError('archive checksum failed')
    except (OSError, ValueError, BadZipFile, subprocess.CalledProcessError):
        if created:
            output.unlink(missing_ok=True)
        raise
    return output


def _extract(archive_path, destination):
    with ZipFile(archive_path) as archive:
        names = set()
        roots = set()
        for item in archive.infolist():
            path = PurePosixPath(item.filename)
            parts = path.parts
            canonical = path.as_posix()
            if (not parts or parts[0] == '/' or '..' in parts or '\\' in item.filename
                    or canonical != item.filename.rstrip('/') or canonical in names
                    or stat.S_ISLNK(item.external_attr >> 16)
                    or any(fnmatch.fnmatch(part, pattern) for part in parts for pattern in IGNORE_PATTERNS)):
                raise ValueError('unsafe or duplicate archive member')
            names.add(canonical)
            roots.add(parts[0])
        if len(roots) != 1:
            raise ValueError('archive must contain one distribution root')
        root = roots.pop()
        if not root.startswith('adaptive-engineering-') or not TAG.fullmatch(root[len('adaptive-engineering-'):]):
            raise ValueError('unexpected distribution root')
        if any(root + '/' + path not in names for path in REQUIRED):
            raise ValueError('archive is missing runtime or setup files')
        archive.extractall(destination)
    return destination / root


def _run(script, *arguments, home, cwd, env):
    # Patch only the child Python's Path.home; never touch the real user's config.
    wrapper = ('import pathlib,runpy,sys; fixture_home=pathlib.Path(sys.argv[1]);'
               'pathlib.Path.home=classmethod(lambda cls: fixture_home);'
               'entry=sys.argv[2];sys.path.insert(0,str(pathlib.Path(entry).parent));'
               'sys.argv=[entry,*sys.argv[3:]];runpy.run_path(entry,run_name="__main__")')
    return subprocess.run([sys.executable, '-I', '-B', '-c', wrapper, str(home), str(script), *map(str, arguments)],
                          cwd=cwd, env=env, check=True, text=True, capture_output=True)


def verify_bundle(archive_path, *, run_tests=True):
    """Verify the marketplace tree and all standalone target layouts in isolation."""
    with tempfile.TemporaryDirectory(prefix='adaptive-bundle-') as temporary:
        root = Path(temporary)
        bundle = _extract(archive_path, root)
        home = root / 'fixture-home'
        home.mkdir()
        project = root / 'fixture-project'
        project.mkdir()
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env.pop('PYTHONPATH', None)
        env.pop('ENGINEERING_VAULT_PATH', None)
        if run_tests:
            subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'],
                           cwd=bundle, env=env, check=True)
        manifest = json.loads((bundle / '.codex-plugin/plugin.json').read_text())
        marketplace = json.loads((bundle / '.agents/plugins/marketplace.json').read_text())
        if manifest['name'] != marketplace['plugins'][0]['name']:
            raise ValueError('plugin identity mismatch')
        if not (bundle / manifest['extensions']['com.openai']['onboardingSkill']).is_file():
            raise ValueError('packaged onboarding skill missing')
        targets = {
            'repo': project / '.agents/skills',
            'codex-global': home / '.agents/skills',
            'antigravity-global': home / '.gemini/config/skills',
            'antigravity-cli-global': home / '.gemini/antigravity-cli/skills',
        }
        for target, skills in targets.items():
            args = ['--target', target] + (['--repo', str(project), '--with-agents'] if target == 'repo' else [])
            _run(bundle / 'install.py', *args, '--dry-run', home=home, cwd=root, env=env)
            if skills.exists():
                raise ValueError('dry run created installation files')
            _run(bundle / 'install.py', *args, home=home, cwd=root, env=env)
            for name in SKILL_NAMES:
                if not (skills / name / 'SKILL.md').is_file():
                    raise ValueError('installed skill missing')
            scripts = skills / 'adaptive-engineering/scripts'
            for name in (*RUNTIME_MODULES, *SETUP_SCRIPTS):
                if not (scripts / name).is_file():
                    raise ValueError('installed runtime file missing')
            vault = root / ('vault-' + target)
            _run(scripts / 'init_vault.py', '--path', vault, home=home, cwd=root, env=env)
            _run(scripts / 'configure.py', '--vault', vault, home=home, cwd=root, env=env)
            active = json.loads(_run(scripts / 'memory_session.py', home=home, cwd=root, env=env).stdout)
            if active['status'] != 'ready' or active['bootstrap_ids']:
                raise ValueError('isolated activation failed or invented profile history')
            _run(scripts / 'search_vault.py', '--query', 'engineering', home=home, cwd=root, env=env)
            try:
                _run(bundle / 'install.py', *args, home=home, cwd=root, env=env)
            except subprocess.CalledProcessError:
                pass
            else:
                raise ValueError('installer replaced an existing target')
        # Marketplace setup must also work with only the extracted source tree.
        _run(bundle / 'init_vault.py', '--path', root / 'marketplace-vault', home=home, cwd=root, env=env)
        return {'standalone_targets': len(targets), 'marketplace_setup': True,
                'extracted_tests_run': run_tests}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build')
    build.add_argument('--source', default=str(Path(__file__).resolve().parent))
    build.add_argument('--ref', default='HEAD')
    build.add_argument('--tag', required=True)
    build.add_argument('--output', required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('archive')
    args = parser.parse_args()
    try:
        if args.command == 'build':
            print(build_release(args.source, args.output, tag=args.tag, ref=args.ref))
        else:
            print(json.dumps(verify_bundle(args.archive), indent=2))
    except (OSError, ValueError, BadZipFile, subprocess.CalledProcessError) as exc:
        parser.error('distribution build/verification failed: ' + str(exc))


if __name__ == '__main__':
    main()
