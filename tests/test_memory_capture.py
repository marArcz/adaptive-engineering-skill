"""Synthetic policy decisions and persistence integration; no live-agent claims."""
import json
import concurrent.futures
import os
import subprocess
import sys
import threading
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import memory_capture as capture
from memory_setup import POLICY, set_capture, setup_memory
from memory_store import read_record, write_record
from vault_guard import CaptureGate


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name)
        setup_memory(self.vault)

    def proposal(self, **changes):
        return {'category':'durable_preferences_goals_decisions', 'origin':'user',
                'kind':'preference', 'title':'Answer length', 'body':'Prefers concise explanations.\n',
                'scope':'general', 'sources':['Synthetic direct conversation'],
                'flags':dict.fromkeys(capture.FLAGS, False)} | changes

    def save(self, proposal=None, **kwargs):
        return capture.capture(self.vault, proposal or self.proposal(), skill_active=True, **kwargs)

    def test_every_policy_row(self):
        cases = [
            ('durable_preferences_goals_decisions', {}, 'created'),
            ('useful_progress_commitments_questions', {'kind':'user_fact'}, 'created'),
            ('significant_shared_experiences', {'kind':'experience'}, 'created'),
            ('inferences', {'origin':'inference'}, 'created'),
            ('temporary_or_do_not_remember', {}, 'excluded'),
            ('sensitive_personal_details', {}, 'excluded'),
            ('credentials_and_third_party_private_data', {}, 'excluded'),
            ('project_filesystem_paths', {}, 'excluded')]
        for category, changes, expected in cases:
            with self.subTest(category=category):
                result = self.save(self.proposal(category=category, title=category.replace('_',' '), **changes))
                self.assertEqual(result['status'], expected, result)

    def test_required_exclusions_and_untrusted_origins(self):
        for flag in ('temporary','do_not_remember','secret','third_party_private'):
            flags = self.proposal()['flags'] | {flag:True}
            self.assertEqual(self.save(self.proposal(flags=flags))['status'], 'excluded')
        for origin in ('hypothetical','source_instruction'):
            self.assertEqual(self.save(self.proposal(origin=origin))['status'], 'excluded')
        self.assertEqual(self.save(self.proposal(origin='source',body='This source says the user likes apples.'))['status'], 'excluded')
        self.assertEqual(capture.capture(self.vault,self.proposal())['trace']['reason'], 'skill_inactive')
        # A source cannot supply authorization through proposal fields.
        proposal = self.proposal(origin='source_instruction') | {'retain_sensitive':True}
        self.assertEqual(self.save(proposal)['status'], 'unavailable')
        self.assertEqual(list((self.vault/'memory/revisions').glob('*.md')), [])

    def test_sensitive_requires_trusted_direct_request(self):
        proposal = self.proposal(flags=self.proposal()['flags'] | {'sensitive':True})
        self.assertEqual(self.save(proposal)['status'], 'excluded')
        self.assertEqual(self.save(proposal,retain_sensitive=True)['status'], 'created')
        self.assertEqual(self.save(proposal | {'origin':'inference'}, retain_sensitive=True)['status'], 'excluded')
        source = self.save(self.proposal(origin='source',kind='knowledge',title='Useful source'))
        self.assertEqual(source['status'], 'created')
        self.assertEqual(read_record(self.vault, source['record_id'])['metadata']['basis'], 'source-supported')

    def test_repeat_updates_evidence_without_promoting_inference(self):
        proposal = self.proposal(origin='inference')
        first = self.save(proposal)
        self.assertEqual(first['status'], 'created')
        self.assertTrue(first['announcement'])
        same = self.save(proposal)
        self.assertEqual(same['status'], 'unchanged')
        self.assertEqual(same['announcement'], '')
        updated = self.save(self.proposal(sources=['A later synthetic direct statement']))
        self.assertEqual(updated['status'], 'updated', updated)
        self.assertEqual(updated['record_id'], first['record_id'])
        stored = read_record(self.vault, first['record_id'])
        self.assertEqual(stored['metadata']['basis'], 'inferred')
        self.assertEqual(len(stored['metadata']['sources']), 2)
        self.assertEqual(len(list((self.vault/'memory/revisions').glob('*.md'))), 2)
        self.assertEqual(self.save(self.proposal(body='Now prefers lengthy explanations.'))['status'], 'needs_review')

    def test_scope_versions_and_ambiguous_matches(self):
        first = self.save()
        project = str(uuid.uuid4())
        scoped = self.save(self.proposal(scope='project',project_id=project))
        self.assertEqual(scoped['status'], 'created')
        self.assertNotEqual(first['record_id'], scoped['record_id'])
        self.assertEqual(self.save(self.proposal(title='Answer length for version two'))['status'], 'created')
        existing = read_record(self.vault, first['record_id'])
        duplicate = existing['metadata'] | {'id':str(uuid.uuid4())}
        self.assertEqual(write_record(self.vault,duplicate,existing['body'])['status'], 'created')
        ambiguous = self.save()
        self.assertEqual(ambiguous['status'], 'needs_review')
        self.assertEqual(len(ambiguous['trace']['candidate_ids']), 2)
        self.assertEqual(self.save(match_id=first['record_id'])['status'], 'unchanged')
        self.assertEqual(self.save(match_id=str(uuid.uuid4()))['status'], 'needs_review')

    def test_paused_missing_and_stricter_policy(self):
        set_capture(self.vault, 'paused')
        self.assertEqual(self.save()['status'], 'paused')
        self.assertFalse((self.vault/'memory/.capture.lock').exists())
        set_capture(self.vault, 'active')
        settings = json.loads((self.vault/POLICY).read_text())
        settings['boundaries']['inferences'] = 'exclude'
        (self.vault/POLICY).write_text(json.dumps(settings))
        self.assertEqual(self.save(self.proposal(origin='inference'))['status'], 'excluded')
        settings['boundaries']['credentials_and_third_party_private_data'] = 'capture'
        (self.vault/POLICY).write_text(json.dumps(settings))
        self.assertEqual(self.save()['status'], 'unavailable')
        self.assertEqual(capture.capture(self.vault/'missing',self.proposal(),skill_active=True)['status'], 'unavailable')

    def test_path_gate_failures_and_uncertain_results(self):
        result = self.save(self.proposal(body='The prompt contained /home/example/project.'))
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('/home/example', json.dumps(result))
        with patch('memory_capture.capture_gate',return_value=CaptureGate(False,'unresolved','resolve merge')):
            self.assertEqual(self.save()['status'], 'unavailable')
        for writer in ({'status':'failed','may_have_written':False},
                       {'status':'failed','may_have_written':True}, {'status':'conflict'}):
            with patch('memory_capture.write_record',return_value=writer):
                result = self.save()
                self.assertEqual(result['status'], writer['status'])
                self.assertEqual(result['announcement'], '')
        self.assertEqual(list((self.vault/'memory/revisions').glob('*.md')), [])
        with patch('memory_store.os.link', side_effect=PermissionError):
            failed = self.save()
        self.assertEqual(failed['status'], 'failed')
        self.assertFalse(failed['may_have_written'])
        self.assertEqual(failed['announcement'], '')

    def test_busy_capture_and_incomplete_matching_do_not_create(self):
        with capture._capture_lock(self.vault):
            self.assertEqual(self.save()['status'], 'busy')
        first = self.save()
        self.assertEqual(first['status'], 'created')
        self.assertEqual(self.save()['status'], 'unchanged')
        with patch('memory_capture.search_memory',return_value={'truncated':True}):
            self.assertEqual(self.save()['status'], 'unavailable')
        with patch('memory_capture.write_record',return_value={'status':'failed','may_have_written':False}):
            self.assertEqual(self.save(self.proposal(title='Another subject'))['status'], 'failed')

    def test_concurrent_capture_retries_without_duplicate_creation(self):
        entered, release = threading.Event(), threading.Event()
        original = write_record
        def delayed(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError('test writer was not released')
            return original(*args, **kwargs)
        with patch('memory_capture.write_record', side_effect=delayed), concurrent.futures.ThreadPoolExecutor(1) as pool:
            future = pool.submit(self.save)
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.save()['status'], 'busy')
            finally:
                release.set()
            self.assertEqual(future.result(timeout=5)['status'], 'created')
        self.assertEqual(self.save()['status'], 'unchanged')
        self.assertEqual(len(list((self.vault/'memory/revisions').glob('*.md'))), 1)

    def test_standalone_capture_module(self):
        from test_tools import ROOT, run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(ROOT/'install.py', '--target', 'repo', '--repo', root)
            scripts = root / '.agents/skills/adaptive-engineering/scripts'
            code = 'import json,sys; sys.path.insert(0,sys.argv[1]); from memory_capture import capture; print(json.dumps(capture(sys.argv[2],json.loads(sys.argv[3]),skill_active=True)))'
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            result = subprocess.run([sys.executable, '-c', code, str(scripts), str(self.vault), json.dumps(self.proposal())],
                                    cwd=root, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'created')


if __name__ == '__main__':
    unittest.main()
