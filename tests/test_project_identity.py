"""Portable project recognition with synthetic local Git repositories."""
import subprocess
import tempfile
import unittest
from pathlib import Path

import memory_contract
import project_identity as identity


class ProjectIdentityTests(unittest.TestCase):
    def test_remote_normalization_and_credentials(self):
        remotes = ('git@EXAMPLE.org:team/Repo.git', 'ssh://git@example.org/team/Repo.git',
                   'https://user:secret@example.org/team/Repo.git')
        self.assertEqual({identity.normalize_repository(r) for r in remotes}, {'https://example.org/team/Repo'})
        self.assertNotEqual(identity.normalize_repository('https://example.org/team/repo'), identity.normalize_repository(remotes[0]))
        for remote in ('/tmp/project', 'file:///tmp/project', 'https://example.org/a/../b',
                       'https://example.org/a?token=secret', 'https://example.org/a#token', 'C:\\project'):
            with self.subTest(remote=remote), self.assertRaises(ValueError):
                identity.normalize_repository(remote)

    def test_two_checkouts_match_without_persisting_locations(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-device-') as temporary:
            root = Path(temporary)
            first, second = root / 'one' / 'checkout', root / 'two' / 'renamed'
            for path, remote in ((first, 'git@example.org:team/demo.git'), (second, 'https://user:secret@example.org/team/demo.git')):
                path.mkdir(parents=True)
                subprocess.run(['git', 'init', '-q', str(path)], check=True)
                subprocess.run(['git', '-C', str(path), 'remote', 'add', 'origin', remote], check=True)
            project = identity.new_project('Demo', identity.repository_from_workspace(first))
            encoded = identity.serialize_project(project, timestamp='2026-01-01T00:00:00Z')
            metadata, _ = memory_contract.parse(encoded)
            self.assertEqual(metadata['project_id'], project['id'])
            restored = identity.parse_project(encoded)
            self.assertEqual(identity.match_project([restored], repository=identity.repository_from_workspace(second)),
                             {'status': 'matched', 'project_id': project['id']})
            for forbidden in (str(root), str(first), str(second), 'synthetic-device-', 'secret', 'user:'):
                self.assertNotIn(forbidden, encoded)

    def test_remoteless_rename_and_collisions(self):
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run(['git', 'init', '-q', temporary], check=True)
            self.assertIsNone(identity.repository_from_workspace(temporary))
        first = identity.new_project('Shared')
        second = identity.new_project('Shared')
        projects = [first, second]
        self.assertEqual(identity.match_project(projects, name='Shared')['status'], 'ambiguous')
        self.assertEqual(identity.match_project([first], name='Shared')['status'], 'ambiguous')
        self.assertEqual(identity.match_project(projects, project_id=first['id'])['project_id'], first['id'])
        renamed = dict(first, name='Renamed')
        self.assertEqual(identity.parse_project(identity.serialize_project(renamed))['id'], first['id'])

    def test_remote_collision_and_explicit_conflict(self):
        first = identity.new_project('First', 'git@example.org:org/a.git')
        second = identity.new_project('Second', 'https://example.org/org/a')
        self.assertEqual(identity.match_project([first, second], repository=first['repository'])['status'], 'ambiguous')
        self.assertEqual(identity.match_project([first, second], repository=first['repository'], project_id=first['id'])['status'], 'conflict')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            identity.match_project([first, first])
        with self.assertRaisesRegex(ValueError, 'path separators'):
            identity.new_project('/tmp/checkout')
        with self.assertRaisesRegex(ValueError, 'project record'):
            identity.parse_project('---\nschema_version: 2\n---\n{}')


if __name__ == '__main__':
    unittest.main()
