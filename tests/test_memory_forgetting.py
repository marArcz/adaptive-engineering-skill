"""Deletion safety: archives, derived records, interrupted cleanup and later imports."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import memory_forgetting as forgetting
from memory_capture import FLAGS, _capture_lock
from memory_consolidation import consolidate
from memory_context import build_context
from memory_corrections import correct
from memory_operations import inspect_record, register_project
from memory_search import memory_snapshot, search_memory
from memory_setup import setup_memory, set_capture
from memory_store import (PREFIX, PublicationError, _publish, _serialize,
                          read_record, read_revision_record, write_record)
from memory_summaries import build_summaries
from test_tools import ROOT, run
from vault_guard import CaptureGate


class ForgettingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name)
        setup_memory(self.vault)
        self.base = json.loads((ROOT / 'tests/fixtures/memory-contract.json').read_text())['base']
        self.flags = dict.fromkeys(FLAGS, False)

    def add(self, body='Private synthetic apples.\n', **fields):
        data = self.base | {'id': str(uuid.uuid4()), 'title': 'Fact: synthetic apples'} | fields
        result = write_record(self.vault, data, body)
        self.assertEqual(result['status'], 'created', result)
        return data

    def paths(self, key):
        return sorted((self.vault / 'memory/revisions').glob(key + '.*.md'))

    def execute(self, **target):
        plan = forgetting.plan_forgetting(self.vault, **target)
        self.assertIn(plan['status'], ('ready', 'unchanged'), plan)
        return forgetting.forget(self.vault, expected_token=plan['token'],
                                 user_requested=True, skill_active=True, **target)

    def test_remove_all_revisions_base_and_conflict_branches(self):
        target = self.add()
        first = read_record(self.vault, target['id'])
        changed = write_record(self.vault, target, 'Changed private apples.', expected_token=first['token'])
        self.assertEqual(changed['status'], 'updated')
        # A divergent immutable branch must also be physically removed.
        revision = str(uuid.uuid4())
        path = self.vault / 'memory/revisions' / f"{target['id']}.{revision}.md"
        path.write_text(PREFIX + json.dumps({'version': 1, 'revision_id': revision, 'parents': first['token']})
                        + ' -->\n' + _serialize(target, 'Competing private apples.'))
        unrelated = self.add('Independent oranges.', title='Fact: oranges')
        stable = {p: p.read_bytes() for p in self.paths(unrelated['id'])}
        legacy = self.vault / 'knowledge' / 'personal-note.md'
        legacy.parent.mkdir()
        legacy.write_text('User-authored apples remain outside managed deletion.')
        result = self.execute(record_id=target['id'])
        self.assertEqual(result['status'], 'forgotten', result)
        self.assertEqual(result['files_removed'], 3)
        self.assertFalse(self.paths(target['id']))
        self.assertIsNone(read_record(self.vault, target['id'], history=True))
        self.assertIsNone(read_revision_record(self.vault, target['id']))
        self.assertEqual(inspect_record(self.vault, target['id'])['status'], 'not_found')
        self.assertEqual(search_memory(self.vault, 'apples', history=True)['matches'], [])
        for p, raw in stable.items():
            self.assertEqual(p.read_bytes(), raw)
        self.assertIn('User-authored', legacy.read_text())
        markers = list((self.vault / 'memory/deletions').glob('*.json'))
        self.assertEqual(len(markers), 1)
        for marker in json.loads(markers[0].read_text()):
            self.assertEqual(set(marker), {'schema_version', 'id', 'deleted_at'})
        self.assertNotIn('apples', json.dumps(result) + markers[0].read_text())
        self.assertIn('Git history', result['limits'])
        repeat = self.execute(record_id=target['id'])
        self.assertEqual(repeat['status'], 'unchanged')
        self.assertEqual(len(list((self.vault / 'memory/deletions').glob('*.json'))), 1)

        base = dict(self.base, id=str(uuid.uuid4()), title='Fact: base record')
        base_path = self.vault / 'memory/profile' / 'existing.md'
        base_path.write_text(_serialize(base, 'Legacy managed payload.'))
        self.assertEqual(self.execute(record_id=base['id'])['status'], 'forgotten')
        self.assertFalse(base_path.exists())

    def test_derived_records_and_views_are_cleaned_transitively(self):
        source = self.add()
        inferred = self.add('Apples may improve collaboration.', kind='assistant_identity',
                            title='Working style', basis='inferred', related_ids=[source['id']])
        derivative = self.add('A summary of apples.', title='Fact: copied summary', related_ids=[inferred['id']])
        plan = forgetting.plan_forgetting(self.vault, record_id=source['id'])
        self.assertEqual(set(plan['record_ids']), {source['id'], inferred['id'], derivative['id']})
        self.assertEqual(self.execute(record_id=source['id'])['records_forgotten'], 3)
        self.assertEqual(build_summaries(self.vault)['source_ids'], [])
        self.assertNotIn('apples', json.dumps(build_context(self.vault, 'apples')).lower())
        for key in plan['record_ids']:
            self.assertFalse(self.paths(key))

    def test_aliases_and_correction_history_are_removed_together(self):
        first = self.add(id='00000000-0000-4000-8000-000000000001')
        alias = self.add(id='00000000-0000-4000-8000-000000000002')
        self.assertEqual(consolidate(self.vault, flags=self.flags, skill_active=True)['status'], 'updated')
        current = inspect_record(self.vault, first['id'])
        fixed = correct(self.vault, [first['id']], 'Corrected private pears.', ['Explicit synthetic correction'],
                        expected_tokens={first['id']: current['token']}, scope='general', origin='user',
                        flags=self.flags, clear=True, skill_active=True)
        self.assertEqual(fixed['status'], 'created', fixed)
        plan = forgetting.plan_forgetting(self.vault, record_id=alias['id'])
        self.assertEqual(set(plan['record_ids']), {first['id'], alias['id'], fixed['record_id']})
        self.assertEqual(self.execute(record_id=alias['id'])['status'], 'forgotten')
        self.assertEqual(list((self.vault / 'memory/revisions').glob('*.md')), [])
        self.assertEqual(search_memory(self.vault, 'private', history=True)['matches'], [])

    def test_subject_resolution_ambiguity_scope_and_stale_plan(self):
        one = self.add()
        self.add('Another value for apples.')
        before = set((self.vault / 'memory/revisions').iterdir())
        plan = forgetting.plan_forgetting(self.vault, subject=one['title'], kind='user_fact', scope='general')
        self.assertEqual(plan['status'], 'needs_review')
        self.assertEqual(len(plan['candidate_ids']), 2)
        self.assertEqual(forgetting.plan_forgetting(self.vault, subject=one['title'])['status'], 'unavailable')
        self.assertEqual(forgetting.plan_forgetting(self.vault, record_id=one['id'], kind='preference')['status'], 'needs_review')
        exact = forgetting.plan_forgetting(self.vault, record_id=one['id'])
        path = self.paths(one['id'])[0]
        path.write_text(path.read_text().replace('Private synthetic', 'Changed synthetic'))
        result = forgetting.forget(self.vault, record_id=one['id'], expected_token=exact['token'],
                                   user_requested=True, skill_active=True)
        self.assertEqual(result['status'], 'needs_review')
        self.assertFalse((self.vault / 'memory/deletions').exists())
        self.assertEqual(set((self.vault / 'memory/revisions').iterdir()), before)
        unique = self.add(title='Fact: distinct target')
        # A token for one target must not authorize a different target in the same vault.
        exact = forgetting.plan_forgetting(self.vault, record_id=one['id'])
        wrong = forgetting.forget(self.vault, record_id=unique['id'], expected_token=exact['token'],
                                  user_requested=True, skill_active=True)
        self.assertEqual(wrong['status'], 'needs_review')
        self.assertEqual(self.execute(subject=unique['title'], kind='user_fact', scope='general')['status'], 'forgotten')

    def test_interrupted_cleanup_suppresses_whole_batch_and_resumes(self):
        target = self.add()
        derived = self.add(title='Fact: derived', related_ids=[target['id']])
        original = forgetting._remove
        calls = 0
        def interrupted(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PermissionError('synthetic interruption')
            return original(*args)
        with patch('memory_forgetting._remove', side_effect=interrupted):
            result = self.execute(record_id=target['id'])
        self.assertEqual(result['status'], 'partial', result)
        self.assertEqual(result['files_removed'], 1)
        self.assertEqual(result['announcement'], '')
        self.assertEqual(search_memory(self.vault, 'apples', history=True)['matches'], [])
        self.assertIsNone(read_revision_record(self.vault, derived['id']))
        resumed = self.execute(record_id=target['id'])
        self.assertEqual(resumed['status'], 'forgotten', resumed)
        self.assertEqual(resumed['files_removed'], 1)
        self.assertFalse(self.paths(derived['id']))
        self.assertEqual(len(list((self.vault / 'memory/deletions').glob('*.json'))), 1)

    def test_intervening_edit_is_preserved_and_requires_replanning(self):
        target = self.add()
        path = self.paths(target['id'])[0]
        original = forgetting._remove
        def edited(*args):
            path.write_text(path.read_text().replace('Private synthetic', 'An intervening edit to'))
            return original(*args)
        with patch('memory_forgetting._remove', side_effect=edited):
            result = self.execute(record_id=target['id'])
        self.assertEqual(result['status'], 'partial', result)
        self.assertTrue(path.exists())
        self.assertIn('An intervening edit', path.read_text())
        self.assertEqual(result['files_removed'], 0)
        self.assertEqual(self.execute(record_id=target['id'])['status'], 'forgotten')

    def test_failed_marker_publication_and_uncertain_readback(self):
        target = self.add()
        with patch('memory_forgetting._publish', side_effect=PublicationError(False)):
            result = self.execute(record_id=target['id'])
        self.assertEqual(result['status'], 'unavailable')
        self.assertTrue(self.paths(target['id']))
        self.assertEqual(inspect_record(self.vault, target['id'])['status'], 'current')
        def uncertain(*args):
            _publish(*args)
            raise PublicationError(True)
        with patch('memory_forgetting._publish', side_effect=uncertain):
            result = self.execute(record_id=target['id'])
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['may_have_written'])
        self.assertTrue(self.paths(target['id']))
        self.assertEqual(inspect_record(self.vault, target['id'])['status'], 'not_found')
        self.assertEqual(self.execute(record_id=target['id'])['status'], 'forgotten')

    def test_unlink_flush_failure_on_retry_still_reports_possible_changes(self):
        target = self.add()
        with patch('memory_forgetting._remove', side_effect=PermissionError):
            self.assertEqual(self.execute(record_id=target['id'])['status'], 'partial')
        original = forgetting._remove
        def removed_then_failed(*args):
            original(*args)
            raise OSError('synthetic directory flush failure')
        with patch('memory_forgetting._remove', side_effect=removed_then_failed):
            result = self.execute(record_id=target['id'])
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['may_have_written'])
        self.assertFalse(self.paths(target['id']))

    def test_late_write_is_reported_failed_and_hidden_after_marker_publication(self):
        target = self.add()
        saved = read_record(self.vault, target['id'])
        def write_then_delete(directory, name, raw):
            published = _publish(directory, name, raw)
            deleting = self.vault / 'memory/deletions'
            deleting.mkdir()
            (deleting / (target['id'] + '.json')).write_text(json.dumps(
                {'schema_version': 1, 'id': target['id'], 'deleted_at': '2026-11-13T00:00:00Z'}))
            return published
        with patch('memory_store._publish', side_effect=write_then_delete):
            result = write_record(self.vault, target, 'A racing private update.', expected_token=saved['token'])
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['may_have_written'])
        self.assertIsNone(read_revision_record(self.vault, target['id']))
        self.assertEqual(self.execute(record_id=target['id'])['status'], 'forgotten')

    def test_authorization_merge_gates_and_paused_capture(self):
        target = self.add()
        plan = forgetting.plan_forgetting(self.vault, record_id=target['id'])
        for options in ({}, {'user_requested': True}, {'skill_active': True}):
            result = forgetting.forget(self.vault, record_id=target['id'], expected_token=plan['token'], **options)
            self.assertEqual(result['status'], 'excluded')
        with patch('memory_forgetting.capture_gate', return_value=CaptureGate(False, 'unresolved', 'blocked')):
            self.assertEqual(self.execute(record_id=target['id'])['reason'], 'merge_gate_blocked')
        self.assertFalse((self.vault / 'memory/deletions').exists())
        set_capture(self.vault, 'paused')
        self.assertEqual(self.execute(record_id=target['id'])['status'], 'forgotten')

    def test_known_ids_and_imported_dependencies_cannot_resurface(self):
        target = self.add()
        saved = {p: p.read_bytes() for p in self.paths(target['id'])}
        self.assertEqual(self.execute(record_id=target['id'])['status'], 'forgotten')
        self.assertEqual(write_record(self.vault, target, 'Private synthetic apples.')['status'], 'failed')
        dependent = self.base | {'id': str(uuid.uuid4()), 'title': 'Fact: offline copy', 'related_ids': [target['id']]}
        self.assertEqual(write_record(self.vault, dependent, 'Copied apples.')['status'], 'failed')
        # Model a later import by an older/offline client, bypassing the writer.
        for path, raw in saved.items():
            path.write_bytes(raw)
        offline_path = self.vault / 'memory/profile' / 'offline.md'
        offline_path.write_text(_serialize(dependent, 'Copied apples.'))
        for key in (target['id'], dependent['id']):
            self.assertEqual(search_memory(self.vault, record_id=key, history=True)['matches'], [])
            self.assertIsNone(read_record(self.vault, key, history=True))
            self.assertIsNone(read_revision_record(self.vault, key))
        result = self.execute(record_id=target['id'])
        self.assertEqual(result['status'], 'forgotten', result)
        self.assertFalse(offline_path.exists())
        self.assertEqual(result['records_forgotten'], 2)

    def test_busy_lock_and_merge_conflict_after_marking(self):
        target = self.add()
        with _capture_lock(self.vault):
            self.assertEqual(self.execute(record_id=target['id'])['status'], 'busy')
        self.assertFalse((self.vault / 'memory/deletions').exists())
        allowed = CaptureGate(True, 'clean', 'allowed')
        blocked = CaptureGate(False, 'unresolved', 'blocked')
        with patch('memory_forgetting.capture_gate', side_effect=[allowed, allowed, blocked]):
            result = self.execute(record_id=target['id'])
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['files_removed'], 0)
        self.assertTrue(self.paths(target['id']))
        self.assertEqual(search_memory(self.vault, 'apples', history=True)['matches'], [])
        self.assertEqual(self.execute(record_id=target['id'])['status'], 'forgotten')

    def test_project_scope_and_project_forgetting(self):
        projects = []
        records = []
        for name in ('one', 'two'):
            key = register_project(self.vault, name, ['Synthetic project'], flags=self.flags,
                    repository='https://example.org/team/' + name, skill_active=True)['record_id']
            projects.append(key)
            records.append(self.add(scope='project', project_id=key))
        result = self.execute(subject=records[0]['title'], kind='user_fact', scope='project', project_id=projects[0])
        self.assertEqual(result['status'], 'forgotten')
        self.assertEqual(inspect_record(self.vault, records[1]['id'])['status'], 'current')
        self.add(title='Fact: other project detail', scope='project', project_id=projects[0])
        self.assertEqual(self.execute(record_id=projects[0])['records_forgotten'], 2)
        self.assertEqual(inspect_record(self.vault, projects[1])['status'], 'current')

    def test_invalid_cross_subject_lineage_does_not_delete_unrelated_memory(self):
        unrelated = self.add('Independent oranges.', title='Fact: unrelated oranges')
        target = self.add(supersedes=[unrelated['id']])
        self.assertEqual(inspect_record(self.vault, target['id'])['status'], 'not_current')
        plan = forgetting.plan_forgetting(self.vault, record_id=target['id'])
        self.assertEqual(plan['record_ids'], [target['id']])
        self.assertEqual(self.execute(record_id=target['id'])['status'], 'forgotten')
        self.assertEqual(inspect_record(self.vault, unrelated['id'])['status'], 'current')

    def test_incomplete_corrupt_and_symlinked_storage_fails_closed(self):
        target = self.add()
        self.add(title='Fact: independent')
        self.assertEqual(forgetting.plan_forgetting(self.vault, record_id=target['id'], max_notes=1)['status'], 'unavailable')
        directory = self.vault / 'memory/deletions'
        directory.mkdir()
        marker = directory / (str(uuid.uuid4()) + '.batch.json')
        marker.write_text('[{}]')
        self.assertTrue(memory_snapshot(self.vault)['incomplete'])
        self.assertEqual(forgetting.plan_forgetting(self.vault, record_id=target['id'])['status'], 'unavailable')
        self.assertEqual(write_record(self.vault, self.base, 'Independent payload.')['status'], 'failed')
        marker.unlink()
        directory.rmdir()
        directory.write_text('invalid deletion area')
        self.assertTrue(memory_snapshot(self.vault)['incomplete'])
        self.assertEqual(write_record(self.vault, self.base, 'Independent payload.')['status'], 'failed')
        directory.unlink()
        with tempfile.TemporaryDirectory() as external:
            directory.symlink_to(external, target_is_directory=True)
            self.assertEqual(forgetting.plan_forgetting(self.vault, record_id=target['id'])['status'], 'unavailable')
            self.assertEqual(list(Path(external).iterdir()), [])

    def test_symlink_swap_during_cleanup_preserves_external_file(self):
        target = self.add()
        path = self.paths(target['id'])[0]
        original = forgetting._remove
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external) / 'outside.md'
            outside.write_text(path.read_text())
            def swapped(*args):
                path.unlink()
                path.symlink_to(outside)
                return original(*args)
            with patch('memory_forgetting._remove', side_effect=swapped):
                result = self.execute(record_id=target['id'])
            self.assertEqual(result['status'], 'partial')
            self.assertTrue(outside.exists())
            self.assertTrue(path.is_symlink())

    def test_post_cleanup_verification_failure_is_partial(self):
        target = self.add()
        original = forgetting._snapshot
        def inaccessible(*args):
            if not self.paths(target['id']):
                raise PermissionError('synthetic failed readback')
            return original(*args)
        with patch('memory_forgetting._snapshot', side_effect=inaccessible):
            result = self.execute(record_id=target['id'])
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['files_removed'], 1)
        self.assertEqual(result['announcement'], '')
        self.assertEqual(self.execute(record_id=target['id'])['status'], 'unchanged')

    def test_standalone_installed_forgetting(self):
        target = self.add()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run(ROOT / 'install.py', '--target', 'repo', '--repo', root)
            scripts = root / '.agents/skills/adaptive-engineering/scripts'
            code = ('import sys;sys.path.insert(0,sys.argv[1]);'
                    'from memory_forgetting import plan_forgetting,forget;'
                    'p=plan_forgetting(sys.argv[2],record_id=sys.argv[3]);'
                    'print(forget(sys.argv[2],record_id=sys.argv[3],expected_token=p["token"],'
                    'user_requested=True,skill_active=True)["status"])')
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            result = subprocess.run([sys.executable, '-c', code, str(scripts), str(self.vault), target['id']],
                                    cwd=root, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'forgotten')


if __name__ == '__main__':
    unittest.main()
