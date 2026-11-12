"""Synthetic revision tests, including controlled publication races."""
import concurrent.futures
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import memory_store as store
from memory_setup import setup_memory
from vault_guard import CaptureGate

BASE = json.loads((Path(__file__).parent / 'fixtures/memory-contract.json').read_text())['base']
BODY = 'The user likes pears.\n'


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name)
        setup_memory(self.vault)
        self.data = dict(BASE)
        self.revisions = self.vault / 'memory/revisions'

    def create(self):
        result = store.write_record(self.vault, self.data, BODY)
        self.assertEqual(result['status'], 'created', result)
        return result

    def test_create_update_retries_and_stale_tokens(self):
        revision = str(uuid.uuid4())
        first = store.write_record(self.vault, self.data, BODY, revision_id=revision)
        self.assertEqual(first['status'], 'created')
        self.assertEqual(store.write_record(self.vault, self.data, BODY, revision_id=revision)['status'], 'unchanged')
        token = first['record']['token']
        updated = store.write_record(self.vault, self.data, 'Apples.\n', expected_token=token)
        self.assertEqual(updated['status'], 'updated', updated)
        self.assertEqual(store.read_record(self.vault, self.data['id'])['body'], 'Apples.\n')
        self.assertEqual(store.write_record(self.vault, self.data, 'Other.\n', expected_token=token)['status'], 'failed')
        self.assertEqual(len(list(self.revisions.glob('*.md'))), 2)

    def test_concurrent_children_preserved_and_explicit_resolution(self):
        first = self.create()
        barrier = threading.Barrier(2)
        original = store._publish
        def publish(*args):
            barrier.wait(timeout=10)
            return original(*args)
        def write(body):
            return store.write_record(self.vault, self.data, body, expected_token=first['record']['token'])
        with patch('memory_store._publish', side_effect=publish), concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(write, ['Apples.\n', 'Bananas.\n']))
        self.assertTrue(all(r['status'] in ('updated', 'conflict') for r in results), results)
        conflict = store.read_record(self.vault, self.data['id'])
        self.assertEqual(conflict['status'], 'conflict')
        self.assertNotIn('body', conflict)
        self.assertEqual(len(conflict['tips']), 2)
        self.assertEqual(store.write_record(self.vault, self.data, 'Resolved.\n', expected_token=conflict['token'])['status'], 'failed')
        resolved = store.write_record(self.vault, self.data, 'Resolved.\n', expected_token=conflict['token'], resolve=True)
        self.assertEqual(resolved['status'], 'updated', resolved)
        self.assertEqual(resolved['record']['body'], 'Resolved.\n')
        self.assertEqual(len(list(self.revisions.glob('*.md'))), 4)

    def test_external_edit_during_publication_and_resolution(self):
        # A pre-existing v1 record is accepted without rewriting it.
        legacy = self.vault / 'memory/profile' / (self.data['id'] + '.md')
        legacy.write_text(store._serialize(self.data, BODY))
        token = store.read_record(self.vault, self.data['id'])['token']
        original = store._publish
        def edit_then_publish(*args):
            legacy.write_text(store._serialize(self.data, 'External edit.\n'))
            return original(*args)
        with patch('memory_store._publish', side_effect=edit_then_publish):
            result = store.write_record(self.vault, self.data, 'Assistant edit.\n', expected_token=token)
        self.assertEqual(result['status'], 'conflict', result)
        self.assertIn('External edit.', legacy.read_text())
        self.assertEqual(len(list(self.revisions.glob('*.md'))), 1)
        conflict = store.read_record(self.vault, self.data['id'])
        resolved = store.write_record(self.vault, self.data, 'Resolved.\n', expected_token=conflict['token'], resolve=True)
        self.assertEqual(resolved['status'], 'updated', resolved)
        self.assertIn('External edit.', legacy.read_text())

    def test_failed_publish_and_uncertain_readback(self):
        first = self.create()
        original = {p: p.read_bytes() for p in self.revisions.glob('*.md')}
        with patch('memory_store.os.link', side_effect=PermissionError):
            failed = store.write_record(self.vault, self.data, 'Changed.\n', expected_token=first['record']['token'])
        self.assertEqual(failed['status'], 'failed')
        self.assertFalse(failed['may_have_written'])
        self.assertEqual({p: p.read_bytes() for p in original}, original)
        self.assertFalse(list(self.revisions.glob('.memory-*')))
        real_publish = store._publish
        def publish_then_fail(*args):
            real_publish(*args)
            raise store.PublicationError(True)
        with patch('memory_store._publish', side_effect=publish_then_fail):
            failed = store.write_record(self.vault, self.data, 'Changed.\n', expected_token=first['record']['token'])
        self.assertTrue(failed['may_have_written'])
        self.assertEqual(store.read_record(self.vault, self.data['id'])['body'], 'Changed.\n')

    def test_boundary_merge_gate_and_symlinks(self):
        self.assertEqual(store.write_record(self.vault, self.data | {'id': '../escape'}, BODY)['status'], 'failed')
        self.assertEqual(store.write_record(self.vault, self.data | {'title': '/home/test/private'}, BODY)['status'], 'failed')
        with patch('memory_store.capture_gate', return_value=CaptureGate(False, 'unresolved', 'resolve conflicts')):
            self.assertEqual(store.write_record(self.vault, self.data, BODY)['status'], 'failed')
        self.revisions.rmdir()
        self.revisions.symlink_to(self.vault)
        self.assertEqual(store.write_record(self.vault, self.data, BODY)['status'], 'failed')

    def test_compatible_metadata_preserved_from_legacy(self):
        path = self.vault / 'memory/profile/old.md'
        path.write_text(store._serialize(self.data | {'custom': 'keep'}, BODY))
        read = store.read_record(self.vault, self.data['id'])
        self.assertEqual(store.write_record(self.vault, self.data, 'Changed.\n', expected_token=read['token'])['status'], 'failed')
        result = store.write_record(self.vault, read['metadata'], 'Changed.\n', expected_token=read['token'])
        self.assertEqual(result['status'], 'updated', result)
        self.assertEqual(result['record']['metadata']['custom'], 'keep')

    def test_missing_parent_duplicate_base_and_changed_ancestor(self):
        first = self.create()
        store.write_record(self.vault, self.data, 'Changed.\n', expected_token=first['record']['token'])
        path = self.revisions / f"{self.data['id']}.{first['revision_id']}.md"
        path.write_text(path.read_text().replace(BODY, 'Externally edited.\n'))
        self.assertEqual(store.read_record(self.vault, self.data['id'])['status'], 'conflict')
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing parent'):
            store.read_record(self.vault, self.data['id'])

    def test_invalid_graphs_versions_and_duplicate_base(self):
        one, two = str(uuid.uuid4()), str(uuid.uuid4())
        def revision(key, parents, version=1):
            header = {'version': version, 'revision_id': key, 'parents': parents}
            path = self.revisions / f"{self.data['id']}.{key}.md"
            path.write_text(store.PREFIX + json.dumps(header) + ' -->\n' + store._serialize(self.data, BODY))
            return path
        first = revision(one, {two: '0' * 64})
        second = revision(two, {one: '0' * 64})
        with self.assertRaisesRegex(ValueError, 'cycle'):
            store.read_record(self.vault, self.data['id'])
        second.unlink()
        revision(one, {}, version=2)
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            store.read_record(self.vault, self.data['id'])
        first.unlink()
        for area in ('profile', 'identity'):
            (self.vault / 'memory' / area / 'duplicate.md').write_text(store._serialize(self.data, BODY))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            store.read_record(self.vault, self.data['id'])

    def test_flush_failure_before_publication(self):
        first = self.create()
        originals = {p: p.read_bytes() for p in self.revisions.glob('*.md')}
        with patch('memory_store.os.fsync', side_effect=OSError('interrupted flush')):
            result = store.write_record(self.vault, self.data, 'Changed.\n', expected_token=first['record']['token'])
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['may_have_written'])
        self.assertEqual({p: p.read_bytes() for p in self.revisions.glob('*.md')}, originals)



if __name__ == '__main__':
    unittest.main()
