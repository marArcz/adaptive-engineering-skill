"""Read-only recall across revisions, scopes, lifecycle and legacy notes."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from memory_search import search_memory
from memory_setup import setup_memory
import memory_store as store
from test_tools import ROOT, SCRIPTS, run


def uid():
    return str(uuid.uuid4())


class MemorySearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name)
        setup_memory(self.vault)
        self.base = json.loads((ROOT / 'tests/fixtures/memory-contract.json').read_text())['base']

    def add(self, kind='user_fact', body='Queue memory.\n', **fields):
        data = self.base | {'id': uid(), 'title': 'Queue memory', 'kind': kind} | fields
        result = store.write_record(self.vault, data, body)
        self.assertEqual(result['status'], 'created', result)
        return data, result

    def find(self, **options):
        return search_memory(self.vault, 'queue', limit=30, **options)

    def test_all_kinds_project_context_and_tentative_provenance(self):
        general = []
        for kind in ('user_fact','preference','assistant_identity','experience','knowledge'):
            data, _ = self.add(kind, basis='inferred' if kind == 'preference' else 'user-stated')
            general.append(data['id'])
        first, second = uid(), uid()
        for project in (first, second):
            self.add('project', id=project, scope='project', project_id=project)
            self.add('knowledge', scope='project', project_id=project)
        self.assertEqual({r['id'] for r in self.find()['matches']}, set(general))
        context = self.find(project_id=first)
        self.assertEqual(len(context['matches']), 7)
        self.assertTrue(all(r.get('project_id', first) == first for r in context['matches']))
        self.assertEqual(len(self.find(scope='project', project_id=first)['matches']), 2)
        self.assertEqual({r['kind'] for r in self.find(scope='all')['matches']}, store.contract.KINDS)
        preference = self.find(kind='preference')['matches'][0]
        self.assertTrue(preference['tentative'])
        self.assertEqual(preference['basis'], 'inferred')
        self.assertNotIn('status', preference)
        self.assertEqual(preference['sources'], ['Synthetic conversation'])
        self.assertIn('memory/', preference['path'])
        with self.assertRaisesRegex(ValueError, 'project ID'):
            self.find(scope='project')

    def test_revision_history_supersession_and_relationship_lookup(self):
        old, initial = self.add(body='Queue old wording.\n')
        update = store.write_record(self.vault, old, 'Queue new wording.\n', expected_token=initial['record']['token'])
        self.assertEqual(update['status'], 'updated')
        current = self.find(record_id=old['id'])['matches']
        self.assertEqual(len(current), 1)
        self.assertFalse(current[0]['historical'])
        history = self.find(record_id=old['id'], history=True)['matches']
        self.assertEqual(len(history), 2)
        self.assertEqual(sum(r['historical'] for r in history), 1)
        correction, _ = self.add(supersedes=[old['id']], related_ids=[uid()])
        self.assertNotIn(old['id'], {r['id'] for r in self.find()['matches']})
        incoming = search_memory(self.vault, related_to=old['id'])['matches']
        self.assertEqual(incoming[0]['id'], correction['id'])
        self.assertEqual(len(incoming[0]['missing_reference_ids']), 1)
        unresolved, _ = self.add(state='unresolved')
        self.assertNotIn(unresolved['id'], {r['id'] for r in self.find()['matches']})
        self.assertIn(unresolved['id'], {r['id'] for r in self.find(history=True)['matches']})

    def test_deletions_invalid_records_and_conflicts_are_excluded(self):
        valid, _ = self.add(title='Independent queue fact')
        deleted, _ = self.add()
        bad, result = self.add()
        bad_path = self.vault / 'memory/revisions' / f"{bad['id']}.{result['revision_id']}.md"
        conflict, first = self.add()
        bad_path.write_text(bad_path.read_text() + '\n<<<<<<< HEAD\nconflict\n')
        path = self.vault / 'memory/revisions' / f"{conflict['id']}.{first['revision_id']}.md"
        revision = uid()
        envelope = {'version': 1, 'revision_id': revision, 'parents': {}}
        other = path.with_name(f"{conflict['id']}.{revision}.md")
        other.write_text(store.PREFIX + json.dumps(envelope) + ' -->\n' + store._serialize(conflict, 'Queue branch.\n'))
        markers = self.vault / 'memory/deletions'
        markers.mkdir()
        (markers / f"{deleted['id']}.json").write_text(json.dumps({'schema_version':1,'id':deleted['id'],'deleted_at':'2026-01-02T00:00:00Z'}))
        result = self.find(history=True)
        self.assertEqual({r['id'] for r in result['matches']}, {valid['id']})
        self.assertGreater(result['invalid_files'], 0)
        self.assertEqual(result['conflicted_records'], 1)
        self.assertEqual(search_memory(self.vault, record_id=deleted['id'], history=True)['matches'], [])
        self.assertNotIn('deleted_at', json.dumps(result))
        # Invalid deletion metadata cannot permit a potentially forgotten record.
        (markers / f"{deleted['id']}.json").write_text('{}')
        self.assertTrue(self.find()['memory_incomplete'])
        self.assertEqual(self.find()['matches'], [])

    def test_limits_determinism_and_incomplete_scan(self):
        for _ in range(4):
            self.add()
        before = {p: p.read_bytes() for p in self.vault.rglob('*') if p.is_file()}
        first = search_memory(self.vault, 'queue', limit=2)
        self.assertEqual(first, search_memory(self.vault, 'queue', limit=2))
        self.assertTrue(first['results_truncated'])
        self.assertEqual(first['result_count'], 4)
        short = search_memory(self.vault, 'queue', max_notes=1)
        self.assertTrue(short['scan_truncated'])
        self.assertTrue(short['memory_incomplete'])
        self.assertEqual(short['matches'], [])
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_cli_combined_search_and_standalone_install(self):
        self.add()
        note = self.vault / 'knowledge/queue.md'
        note.parent.mkdir()
        note.write_text('---\ntitle: Queue\nstatus: approved\n---\nQueue guidance.\n')
        before = note.read_bytes()
        result = json.loads(run(SCRIPTS/'search_vault.py','--vault',self.vault,'--query','queue','--mode','all','--limit',10).stdout)
        self.assertEqual({r['result_type'] for r in result['matches']}, {'legacy','memory'})
        self.assertEqual([r['status'] for r in result['matches'] if r['result_type']=='legacy'], ['approved'])
        self.assertEqual(note.read_bytes(), before)
        limited = json.loads(run(SCRIPTS/'search_vault.py','--vault',self.vault,'--query','queue','--mode','all','--limit',1).stdout)
        self.assertEqual(len(limited['matches']), 1)
        self.assertEqual(limited['result_count'], 2)
        self.assertTrue(limited['results_truncated'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(ROOT/'install.py','--target','repo','--repo',root)
            script = root / '.agents/skills/adaptive-engineering/scripts/search_vault.py'
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            command = subprocess.run([sys.executable,str(script),'--vault',str(self.vault),'--query','queue','--mode','memory'],
                                     cwd=root,env=env,text=True,capture_output=True)
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertEqual(len(json.loads(command.stdout)['matches']), 1)

    def test_unreadable_and_oversized_files_report_limits(self):
        data, result = self.add()
        path = self.vault / 'memory/revisions' / f"{data['id']}.{result['revision_id']}.md"
        with patch.object(Path, 'open', side_effect=PermissionError):
            result = self.find()
        self.assertGreater(result['unreadable_files'], 0)
        self.assertEqual(result['matches'], [])
        path.write_bytes(b'x' * (128*1024 + 1))
        result = self.find()
        self.assertEqual(result['oversized_files'], 1)
        self.assertEqual(result['matches'], [])


if __name__ == '__main__':
    unittest.main()
