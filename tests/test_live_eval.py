"""Offline evidence integrity checks; never start a model session."""
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from run_live_eval import changed_files, events_summary, report, run, snapshot


class LiveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_snapshots_do_not_follow_external_file_directory_or_root_links(self):
        vault = self.root / 'vault'
        vault.mkdir()
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'private.txt').write_text('Not evaluation data.')
        (vault / 'safe.txt').write_text('Synthetic evaluation data.')
        (vault / 'file-link').symlink_to(outside / 'private.txt')
        (vault / 'directory-link').symlink_to(outside, target_is_directory=True)
        self.assertEqual(set(snapshot(vault)), {'safe.txt'})
        root_link = self.root / 'root-link'
        root_link.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            snapshot(root_link)
        before = snapshot(vault)
        (vault / 'safe.txt').unlink()
        (vault / 'new.txt').write_text('A new synthetic fact.')
        self.assertEqual(changed_files(before, snapshot(vault)),
                         {'new.txt': 'created', 'safe.txt': 'deleted'})

    def manifest(self):
        (self.root / 'manifest.json').write_text(json.dumps({'fixture': {
            'cases': [{'id': '01-example', 'criteria': ['Observed behavior required.']}],
            'host_gaps': ['Antigravity not evaluated.']}}))
        folder = self.root / 'cases/01-example'
        folder.mkdir(parents=True)
        return folder

    def test_successful_process_remains_unreviewed_and_missing_session_not_run(self):
        folder = self.manifest()
        self.assertEqual(report(self.root)['cases'][0]['verdict'], 'not_run')
        raw = '\n'.join(json.dumps(event) for event in [
            {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'synthetic',
                                               'aggregated_output': 'created', 'exit_code': 0}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 2}}])
        observed = events_summary(raw)
        self.assertTrue(observed['turn_completed'])
        self.assertEqual(len(observed['tools']), 1)
        (folder / 'result.json').write_text(json.dumps(dict(observed, execution='observed')))
        data = report(self.root)
        self.assertEqual(data['cases'][0]['verdict'], 'unreviewed')
        self.assertEqual(data['full_acceptance'], 'not_claimed')
        self.assertEqual(events_summary('{invalid\n')['invalid_lines'], 1)
        self.assertFalse(events_summary('{invalid\n')['turn_completed'])

    def test_runtime_failure_cannot_be_promoted_to_behavioral_pass(self):
        folder = self.manifest()
        (folder / 'result.json').write_text(json.dumps({'execution': 'runtime_failed'}))
        (self.root / 'reviews.json').write_text(json.dumps({'01-example': {
            'verdict': 'passed', 'evidence': ['cases/01-example/events.jsonl'],
            'notes': 'Cannot count this as observed behavior.'}}))
        with self.assertRaisesRegex(ValueError, 'cannot establish'):
            report(self.root)
        (self.root / 'reviews.json').write_text(json.dumps({'unknown': {'verdict': 'passed'}}))
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            report(self.root)

    def test_missing_runtime_blocks_remaining_cases_without_retries(self):
        workspace = self.root / 'workspace'
        workspace.mkdir()
        (workspace / 'AGENTS.md').write_text('Synthetic isolation instructions.')
        (self.root / 'vaults/example').mkdir(parents=True)
        cases = [{'id': name, 'group': 'example', 'prompt': 'Synthetic direct turn.'}
                 for name in ('01-first', '02-dependent')]
        manifest = {'fixture': {'cases': cases, 'host_gaps': ['No device acceptance.']}}
        (self.root / 'manifest.json').write_text(json.dumps(manifest))
        with patch('run_live_eval.subprocess.Popen', side_effect=FileNotFoundError) as process:
            data = run(self.root, [], 1)
            self.assertEqual(process.call_count, 1)
            self.assertEqual([case['execution'] for case in data['cases']],
                             ['runtime_failed', 'not_run'])
            self.assertEqual([case['verdict'] for case in data['cases']], ['not_run', 'not_run'])
            self.assertEqual(data['cases'][0]['reason'], 'FileNotFoundError')
            cases.append({'id': '03-later', 'group': 'example', 'prompt': 'Another direct turn.'})
            (self.root / 'manifest.json').write_text(json.dumps(manifest))
            data = run(self.root, [], 1)
            self.assertEqual(process.call_count, 1)
            self.assertEqual(data['cases'][-1]['execution'], 'not_run')

    def test_review_requires_real_contained_evidence(self):
        folder = self.manifest()
        (folder / 'result.json').write_text(json.dumps({'execution': 'observed'}))
        (self.root / 'reviews.json').write_text(json.dumps({'01-example': {
            'verdict': 'passed', 'evidence': ['../outside.txt'], 'notes': 'Missing evidence.'}}))
        with self.assertRaisesRegex(ValueError, 'evidence'):
            report(self.root)


if __name__ == '__main__':
    unittest.main()
