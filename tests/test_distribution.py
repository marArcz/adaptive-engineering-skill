"""Distribution completeness and standalone setup, with no live installations."""
import fnmatch
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZipInfo

from distribution import BUNDLE_FILES, BUNDLE_TREES, IGNORE_PATTERNS, RUNTIME_MODULES
from package_release import build_release, verify_bundle, _extract
from test_tools import ROOT, run


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self):
        source = self.root / 'distribution'
        source.mkdir()
        for name in BUNDLE_FILES:
            shutil.copyfile(ROOT / name, source / name)
        for name in BUNDLE_TREES:
            shutil.copytree(ROOT / name, source / name, ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))
        return source

    def tree(self, source):
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        for args in (['init', '-q'], ['add', '--all']):
            subprocess.run(['git', '-C', str(source), *args], env=env, check=True, capture_output=True)
        return subprocess.run(['git', '-C', str(source), 'write-tree'], env=env,
                              check=True, capture_output=True, text=True).stdout.strip()

    def test_extracted_marketplace_and_all_standalone_setups_are_self_contained(self):
        source = self.source()
        tree = self.tree(source)
        archive = self.root / 'bundle.zip'
        build_release(source, archive, tag='v0.4.1-t18', ref=tree)
        # Hide the fixture checkout before executing anything from the bundle.
        source.rename(self.root / 'unavailable-source')
        result = verify_bundle(archive, run_tests=False)
        self.assertEqual(result['standalone_targets'], 4)
        self.assertTrue(result['marketplace_setup'])
        self.assertFalse(result['extracted_tests_run'])

    def test_archive_uses_tracked_runtime_and_omits_local_state_and_bytecode(self):
        source = self.source()
        cache = source / '.agents/skills/adaptive-engineering/scripts/__pycache__'
        cache.mkdir()
        (cache / 'sample.pyc').write_bytes(b'synthetic compiled cache')
        nested_env = source / '.agents/skills/adaptive-engineering/scripts/.env'
        nested_env.write_text('SYNTHETIC_CONFIG=not-for-distribution')
        (source / '.envrc').write_text('synthetic environment')
        private = source / 'memory/profile/private.md'
        private.parent.mkdir(parents=True)
        private.write_text('Synthetic personal memory excluded from distribution.')
        tree = self.tree(source)
        (source / 'docs/untracked-private.md').write_text('Synthetic untracked note.')
        archive = self.root / 'bundle.zip'
        build_release(source, archive, tag='v0.4.1-t18', ref=tree)
        with ZipFile(archive) as bundle:
            names = bundle.namelist()
            prefix = 'adaptive-engineering-v0.4.1-t18/'
            for name in RUNTIME_MODULES:
                self.assertIn(prefix + name, names)
            self.assertIn(prefix + 'vault-template/.gitignore', names)
            self.assertIn(prefix + '.agents/skills/setup-vault/SKILL.md', names)
            self.assertFalse(any('private' in name for name in names))
            for name in names:
                self.assertFalse(any(fnmatch.fnmatch(part, pattern)
                                     for part in Path(name).parts for pattern in IGNORE_PATTERNS), name)

    def test_existing_archive_and_missing_source_resources_are_preserved(self):
        source = self.source()
        tree = self.tree(source)
        archive = self.root / 'existing.zip'
        archive.write_bytes(b'preserve existing artifact')
        with self.assertRaises(FileExistsError):
            build_release(source, archive, tag='v0.4.1-t18', ref=tree)
        self.assertEqual(archive.read_bytes(), b'preserve existing artifact')
        (source / 'memory_session.py').unlink()
        tree = self.tree(source)
        missing_archive = self.root / 'missing.zip'
        with self.assertRaises(ValueError):
            build_release(source, missing_archive, tag='v0.4.1-t18', ref=tree)
        self.assertFalse(missing_archive.exists())
        project = self.root / 'project'
        project.mkdir()
        result = run(source / 'install.py', '--target', 'repo', '--repo', project, ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((project / '.agents').exists())

    def test_existing_setup_skill_blocks_entire_install_and_preserves_agents(self):
        project = self.root / 'project'
        existing = project / '.agents/skills/setup-vault'
        existing.mkdir(parents=True)
        note = existing / 'SKILL.md'
        note.write_text('Existing setup instructions.')
        agents = project / 'AGENTS.md'
        agents.write_text('Existing project rules.')
        result = run(ROOT / 'install.py', '--target', 'repo', '--repo', project, '--with-agents', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((existing.parent / 'adaptive-engineering').exists())
        self.assertEqual(note.read_text(), 'Existing setup instructions.')
        self.assertEqual(agents.read_text(), 'Existing project rules.')

    def test_symlinks_are_rejected_and_dangling_agents_is_preserved(self):
        source = self.source()
        link = source / 'assets/linked.svg'
        link.symlink_to('icon.svg')
        tree = self.tree(source)
        with self.assertRaises(ValueError):
            build_release(source, self.root / 'linked.zip', tag='v0.4.1-t18', ref=tree)
        project = self.root / 'project'
        project.mkdir()
        outside = self.root / 'outside'
        outside.mkdir()
        (project / '.agents').symlink_to(outside, target_is_directory=True)
        result = run(ROOT / 'install.py', '--target', 'repo', '--repo', project, ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        (project / '.agents').unlink()
        missing = self.root / 'missing-agents.md'
        (project / 'AGENTS.md').symlink_to(missing)
        run(ROOT / 'install.py', '--target', 'repo', '--repo', project, '--with-agents')
        self.assertTrue((project / 'AGENTS.md').is_symlink())
        self.assertFalse(missing.exists())
        self.assertEqual(list((project / '.agents/skills').rglob('__pycache__')), [])

    def test_archive_extraction_refuses_unsafe_members(self):
        output = self.root / 'extracted'
        output.mkdir()
        for index, name in enumerate(('../outside.md', '/absolute.md',
                                      'adaptive-engineering-v0.4.1/a/../outside.md',
                                      'adaptive-engineering-v0.4.1/.env')):
            archive = self.root / f'unsafe-{index}.zip'
            with ZipFile(archive, 'w') as bundle:
                bundle.writestr(name, 'Synthetic unsafe archive member.')
            with self.assertRaises(ValueError):
                _extract(archive, output)
        link = ZipInfo('adaptive-engineering-v0.4.1/link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive = self.root / 'symlink.zip'
        with ZipFile(archive, 'w') as bundle:
            bundle.writestr(link, '../outside')
        with self.assertRaises(ValueError):
            _extract(archive, output)
        self.assertEqual(list(output.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
