"""Exercise additive setup and capture configuration in synthetic vaults."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_tools import ROOT, run

sys.path.insert(0, str(ROOT))
import memory_setup


class MemorySetupTests(unittest.TestCase):
    def test_existing_vault_is_additive_and_repeatable(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            note = vault / 'personal.md'
            note.write_bytes(b'---\nstatus: approved\n---\nKeep this.\n')
            run(ROOT / 'init_vault.py', '--path', vault)
            policy = vault / memory_setup.POLICY
            before = policy.read_bytes()
            template = vault / 'memory/templates/record.md'
            template.write_text('User edited template', encoding='utf8')
            run(ROOT / 'init_vault.py', '--path', vault)
            self.assertEqual(note.read_bytes(), b'---\nstatus: approved\n---\nKeep this.\n')
            self.assertEqual(policy.read_bytes(), before)
            self.assertEqual(template.read_text(), 'User edited template')
            self.assertFalse((vault / 'HOME.md').exists())
            self.assertFalse((vault / '.git').exists())
            for area in memory_setup.AREAS:
                self.assertTrue((vault / 'memory' / area).is_dir())

    def test_capture_override_and_existing_config_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = root / 'profile'; profile.mkdir()
            saved = root / 'saved'; saved.mkdir()
            override = root / 'override'; override.mkdir()
            memory_setup.setup_memory(override)
            config = profile / '.adaptive-engineering/config.json'
            config.parent.mkdir()
            config.write_text(json.dumps({'custom': 'keep'}))
            with patch.object(Path, 'home', return_value=profile), patch.dict(os.environ, {'ENGINEERING_VAULT_PATH': str(override)}):
                with patch.object(sys, 'argv', ['configure.py', '--vault', str(saved)]), contextlib.redirect_stdout(io.StringIO()) as output:
                    runpy.run_path(str(ROOT / 'configure.py'), run_name='__main__')
                self.assertIn('overrides', output.getvalue())
                with patch.object(sys, 'argv', ['configure.py', '--capture', 'paused']), contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(ROOT / 'configure.py'), run_name='__main__')
            self.assertEqual(json.loads(config.read_text())['custom'], 'keep')
            self.assertEqual(memory_setup.read_policy(saved)['capture'], 'active')
            self.assertEqual(memory_setup.read_policy(override)['capture'], 'paused')
            self.assertNotIn(str(saved), (saved / memory_setup.POLICY).read_text())

    def test_invalid_config_file_target_and_failed_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); profile = root / 'profile'; profile.mkdir()
            vault = root / 'vault'; vault.mkdir()
            config = profile / '.adaptive-engineering/config.json'; config.parent.mkdir()
            config.write_text('[]')
            with patch.object(Path, 'home', return_value=profile), patch.object(sys, 'argv', ['configure.py', '--vault', str(vault)]), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runpy.run_path(str(ROOT / 'configure.py'), run_name='__main__')
            self.assertEqual(config.read_text(), '[]')
            target = root / 'file'; target.write_text('unchanged')
            result = run(ROOT / 'init_vault.py', '--path', target, ok=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('not a directory', result.stderr)
            with patch('memory_setup.tempfile.TemporaryFile', side_effect=PermissionError('read-only')):
                with self.assertRaisesRegex(ValueError, 'not writable'):
                    memory_setup.setup_memory(vault)
            self.assertFalse((vault / 'memory').exists())

    def test_bad_existing_policy_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            policy = vault / memory_setup.POLICY; policy.parent.mkdir()
            policy.write_text('{bad')
            with self.assertRaisesRegex(ValueError, 'capture settings'):
                memory_setup.setup_memory(vault)
            self.assertEqual(policy.read_text(), '{bad')


if __name__ == '__main__':
    unittest.main()
