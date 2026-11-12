"""Merge-gate integration tests using only temporary local repositories."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '.agents/skills/adaptive-engineering/scripts'
sys.path.insert(0, str(SCRIPTS))
from vault_guard import capture_gate, has_conflict_markers


def git(vault, *args, check=True):
    return subprocess.run(['git', '-C', str(vault), *args], check=check,
                          capture_output=True, text=True)


class VaultGuardTests(unittest.TestCase):
    def test_real_conflict_and_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            git(vault, 'init', '-q')
            git(vault, 'config', 'user.email', 'test@example.invalid')
            git(vault, 'config', 'user.name', 'Test')
            note = vault / 'note.md'
            note.write_text('base\n')
            git(vault, 'add', 'note.md')
            git(vault, 'commit', '-qm', 'base')
            branch = git(vault, 'branch', '--show-current').stdout.strip()
            git(vault, 'checkout', '-qb', 'other')
            note.write_text('other\n')
            git(vault, 'commit', '-qam', 'other')
            git(vault, 'checkout', '-q', branch)
            note.write_text('current\n')
            git(vault, 'commit', '-qam', 'current')
            self.assertNotEqual(git(vault, 'merge', 'other', check=False).returncode, 0)
            before = note.read_bytes()
            self.assertEqual(capture_gate(vault).state, 'unresolved')
            self.assertFalse(capture_gate(vault).allowed)
            self.assertEqual(note.read_bytes(), before)
            self.assertTrue(has_conflict_markers(before.decode()))
            note.write_text('resolved\n')
            git(vault, 'add', 'note.md')
            self.assertTrue(capture_gate(vault).allowed)

    def test_non_git_and_inspection_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            self.assertEqual(capture_gate(vault).state, 'non-git')
            with patch('vault_guard.subprocess.run', side_effect=FileNotFoundError):
                self.assertFalse(capture_gate(vault).allowed)
            with patch('vault_guard.subprocess.run', return_value=subprocess.CompletedProcess([], 128, '', 'permission denied')):
                self.assertEqual(capture_gate(vault).state, 'unknown')
            self.assertFalse(capture_gate(vault / 'missing').allowed)

    def test_search_excludes_markers_beyond_excerpt(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            (vault / 'valid.md').write_text('---\ntitle: Queue\nstatus: approved\n---\nqueue\n')
            (vault / 'conflict.md').write_text('---\ntitle: Queue\nstatus: approved\n---\nqueue\n' + 'x' * 17000 + '\n<<<<<<< HEAD\nsecret queue\n=======\nother\n>>>>>>> branch\n')
            result = subprocess.run([sys.executable, str(SCRIPTS / 'search_vault.py'), '--vault', str(vault), '--query', 'queue'], capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            self.assertEqual([m['path'] for m in data['matches']], ['valid.md'])
            self.assertEqual(data['conflict_files_excluded'], 1)


if __name__ == '__main__':
    unittest.main()
