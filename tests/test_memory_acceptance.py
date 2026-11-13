"""Cross-operation acceptance using fixture v1; no live agent or remote devices."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from memory_capture import FLAGS
from memory_consolidation import consolidate
from memory_context import build_context
from memory_corrections import correct
from memory_forgetting import forget, plan_forgetting
from memory_journal import journal
from memory_learning import learn_knowledge, save_candidate
from memory_operations import remember, inspect_record, register_project
from memory_search import search_memory
from memory_store import write_record
from memory_summaries import build_summaries
from test_tools import ROOT, SCRIPTS, run
from search_vault import search as legacy_search
from search_catalog import search as catalog_search


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.flags = dict.fromkeys(FLAGS, False)
        self.fixture = json.loads((ROOT / 'tests/fixtures/acceptance-v1.json').read_text())
        self.assertEqual(self.fixture['fixture_version'], 1)
        self.base = json.loads((ROOT / 'tests/fixtures/memory-contract.json').read_text())['base']
        self.legacy = self.seed_legacy()
        self.legacy_hashes = self.hashes(self.legacy)
        run(ROOT / 'init_vault.py', '--path', self.vault)

    def seed_legacy(self):
        files = []
        for fixture in ('legacy-approved.md', 'legacy-candidate.md'):
            path = self.vault / 'knowledge' / fixture
            path.parent.mkdir(exist_ok=True)
            path.write_bytes((ROOT / 'tests/fixtures' / fixture).read_bytes())
            files.append(path)
        home = self.vault / 'HOME.md'
        home.write_text('User-authored synthetic vault home.\n')
        files.append(home)
        catalog = self.vault / 'references/github/catalog.json'
        catalog.parent.mkdir(parents=True)
        catalog.write_text(json.dumps({'schema_version': 1, 'custom': 'keep', 'repositories': [
            {'id': 'reviewed', 'url': 'https://github.com/example/reviewed', 'status': 'approved',
             'tags': ['queue'], 'reviewed_commit': 'synthetic-reviewed-revision',
             'verified_at': '2026-10-24', 'important_paths': ['legacy/component.py'], 'custom': 'keep'}]}))
        files.append(catalog)
        overview = catalog.with_name('GitHub Catalog.md')
        overview.write_text('User-authored reviewed catalog overview.\n')
        files.append(overview)
        return files

    def hashes(self, files):
        return {p.relative_to(self.vault).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}

    def preference(self):
        data = self.fixture['preference']
        result = remember(self.vault, 'preference', data['subject'], data['original'], [data['source']],
                          origin='user', flags=self.flags, skill_active=True)
        self.assertEqual(result['status'], 'created', result)
        return result['record_id']

    def feedback(self, related_id):
        ids = []
        for data in self.fixture['feedback']:
            result = journal(self.vault, data['subject'], significance='collaboration_feedback',
                             context='Synthetic collaboration during acceptance testing.', happened=data['happened'],
                             why='The feedback identified a useful collaboration pattern.', outcome='Feedback was recorded.',
                             lesson=self.fixture['lesson'], sources=[data['source']], origin='user', flags=self.flags,
                             related_ids=[related_id], skill_active=True)
            self.assertEqual(result['status'], 'created', result)
            ids.append(result['record_id'])
        return ids

    def test_fresh_process_recall_keeps_identity_profile_and_project_scopes(self):
        pref = self.preference()
        feedback = self.feedback(pref)
        decisions = []
        projects = []
        for data in self.fixture['projects']:
            result = register_project(self.vault, data['name'], ['Synthetic acceptance project identity'],
                                      repository=data['repository'], flags=self.flags, skill_active=True)
            self.assertEqual(result['status'], 'created', result)
            project = result['record_id']
            projects.append(project)
            decision = remember(self.vault, 'decision', 'Release scope', data['decision'],
                                ['Synthetic acceptance project decision'], origin='user', flags=self.flags,
                                scope='project', project_id=project, skill_active=True)
            self.assertEqual(decision['status'], 'created', decision)
            decisions.append(decision['record_id'])
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        # A new interpreter can reconstruct data; it is not a fresh LLM session.
        code = ('import sys,json;sys.path.insert(0,sys.argv[1]);'
                'from memory_session import activate;from memory_context import build_context;'
                'print(json.dumps({"activation":activate(sys.argv[2]),'
                '"task":build_context(sys.argv[2],"release",project_id=sys.argv[3],'
                'current_instructions="Use detail for this request.")}))')
        process = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(ROOT), str(self.vault), projects[0]],
                                 cwd=self.root, env=env, capture_output=True, text=True, check=True)
        result = json.loads(process.stdout)
        active, task = result['activation'], result['task']
        self.assertIn(pref, active['bootstrap_ids'])
        self.assertTrue(set(feedback) <= set(active['bootstrap_ids']))
        self.assertIn('tentative', active['context'].lower())
        self.assertEqual(active['excerpt_count'], 0)
        self.assertIn(decisions[0], task['excerpt_ids'])
        self.assertNotIn(decisions[1], task['excerpt_ids'])
        self.assertIn(self.fixture['projects'][0]['decision'], task['context'])
        self.assertNotIn(self.fixture['projects'][1]['decision'], task['context'])
        self.assertLessEqual(task['characters'], 12000)
        self.assertLessEqual(task['excerpt_count'], 5)
        for path in (self.vault / 'memory/revisions').glob('*.md'):
            self.assertNotIn(str(self.root), path.read_text())
        self.assertEqual(self.hashes(self.legacy), self.legacy_hashes)

    def test_consolidate_correct_and_forget_refresh_every_view_and_keep_legacy(self):
        pref = self.preference()
        feedback = self.feedback(pref)
        old = inspect_record(self.vault, pref)
        duplicate_id = '00000000-0000-4000-8000-000000000010'
        self.assertEqual(write_record(self.vault, old['metadata'] | {'id': duplicate_id,
                         'sources': ['Independent synthetic duplicate']}, old['body'])['status'], 'created')
        experience = self.fixture['old_experience']
        data = self.base | {'id': experience['id'], 'kind': 'experience', 'title': experience['title'],
                            'created_at': experience['timestamp'], 'updated_at': experience['timestamp']}
        self.assertEqual(write_record(self.vault, data, experience['body'])['status'], 'created')
        untouched = {p: p.read_bytes() for p in (self.vault / 'memory/revisions').glob(experience['id'] + '.*.md')}
        self.assertTrue(untouched)
        self.assertTrue(any(item['entry_type'] == 'inferred_trait' for item in build_summaries(self.vault)['items']))
        merged = consolidate(self.vault, flags=self.flags, skill_active=True)
        self.assertEqual(merged['status'], 'updated', merged)
        self.assertEqual(merged['groups_consolidated'], 1)
        self.assertEqual(consolidate(self.vault, flags=self.flags, skill_active=True)['status'], 'unchanged')
        canonical = inspect_record(self.vault, pref)
        canonical_id = min(pref, duplicate_id)
        self.assertEqual(canonical['canonical_id'], canonical_id)
        corrected = correct(self.vault, [canonical_id], self.fixture['preference']['corrected'],
                            ['Synthetic acceptance explicit correction'], expected_tokens={canonical_id: canonical['token']},
                            scope='general', origin='user', flags=self.flags, clear=True, skill_active=True)
        self.assertEqual(corrected['status'], 'created', corrected)
        context = build_context(self.vault, 'reply')['context']
        self.assertIn(self.fixture['preference']['corrected'], context)
        self.assertNotIn(self.fixture['preference']['original'], context)
        self.assertTrue(search_memory(self.vault, record_id=pref, history=True)['matches'])
        target = corrected['record_id']
        plan = plan_forgetting(self.vault, record_id=target)
        self.assertTrue({pref, duplicate_id, target, *feedback} <= set(plan['record_ids']))
        forgotten = forget(self.vault, record_id=target, expected_token=plan['token'],
                           user_requested=True, skill_active=True)
        self.assertEqual(forgotten['status'], 'forgotten', forgotten)
        self.assertEqual(build_summaries(self.vault)['source_ids'], [])
        self.assertEqual(build_context(self.vault)['bootstrap_ids'], [])
        for key in plan['record_ids']:
            self.assertEqual(search_memory(self.vault, record_id=key, history=True)['matches'], [])
        for path in (self.vault / 'memory').rglob('*.md'):
            self.assertNotIn(self.fixture['preference']['original'], path.read_text())
            self.assertNotIn(self.fixture['preference']['corrected'], path.read_text())
        for path, raw in untouched.items():
            self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(self.hashes(self.legacy), self.legacy_hashes)

    def test_legacy_snapshot_survives_setup_learning_and_managed_forgetting(self):
        run(ROOT / 'init_vault.py', '--path', self.vault)
        self.assertEqual(self.hashes(self.legacy), self.legacy_hashes)
        args = {'applicability': 'Synthetic acceptance planning.', 'limitations': 'Synthetic supplied advice only.',
                'sources': ['Synthetic acceptance learning explanation'], 'evidence': 'user_claim',
                'flags': self.flags, 'user_requested': True, 'skill_active': True}
        learned = learn_knowledge(self.vault, 'Study planning', 'Use short study sessions.', **args)
        self.assertEqual(learned['status'], 'created', learned)
        candidate = save_candidate(self.vault, 'Queue retries', 'Bound retry attempts.', technology='Python', **args)
        self.assertEqual(candidate['status'], 'created', candidate)
        plan = plan_forgetting(self.vault, record_id=learned['record_id'])
        self.assertEqual(forget(self.vault, record_id=learned['record_id'], expected_token=plan['token'],
                               user_requested=True, skill_active=True)['status'], 'forgotten')
        self.assertEqual(self.hashes(self.legacy), self.legacy_hashes)
        legacy = legacy_search(self.vault, 'queue', limit=30)
        self.assertEqual({row['status'] for row in legacy['matches']}, {'approved', 'candidate'})
        catalog = catalog_search(self.vault, 'queue')['matches'][0]
        self.assertEqual(catalog['reviewed_commit'], 'synthetic-reviewed-revision')
        self.assertEqual(catalog['important_paths'], ['legacy/component.py'])
        self.assertTrue((self.vault / candidate['path']).is_file())

    def test_real_merge_gate_blocks_capture_and_keeps_unrelated_recall(self):
        pref = self.preference()
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        def git(*args, check=True):
            return subprocess.run(['git', '-C', str(self.vault), *args], env=env, check=check,
                                  capture_output=True, text=True)
        git('init', '-q')
        git('config', 'user.email', 'acceptance@example.invalid')
        git('config', 'user.name', 'Synthetic acceptance fixture')
        conflict = self.vault / 'knowledge/conflict.md'
        conflict.write_text('---\ntitle: Queue conflict\nstatus: approved\n---\nbase queue\n')
        git('add', '.')
        git('commit', '-qm', 'synthetic base')
        branch = git('branch', '--show-current').stdout.strip()
        git('checkout', '-qb', 'other')
        conflict.write_text(conflict.read_text().replace('base queue', 'other queue'))
        git('commit', '-qam', 'synthetic other')
        git('checkout', '-q', branch)
        conflict.write_text(conflict.read_text().replace('base queue', 'current queue'))
        git('commit', '-qam', 'synthetic current')
        self.assertNotEqual(git('merge', 'other', check=False).returncode, 0)
        before = conflict.read_bytes()
        blocked = remember(self.vault, 'goal', 'Blocked goal', 'Finish the acceptance review.',
                           ['Synthetic acceptance goal'], origin='user', flags=self.flags, skill_active=True)
        self.assertEqual(blocked['status'], 'unavailable')
        self.assertEqual(blocked['trace']['reason'], 'merge_gate_blocked')
        self.assertFalse(blocked['announcement'])
        self.assertEqual(conflict.read_bytes(), before)
        self.assertIn(pref, build_context(self.vault)['bootstrap_ids'])
        self.assertNotIn('knowledge/conflict.md', {r['path'] for r in legacy_search(self.vault, 'queue', limit=30)['matches']})
        conflict.write_text('---\ntitle: Queue resolved\nstatus: approved\n---\nresolved queue\n')
        git('add', 'knowledge/conflict.md')
        saved = remember(self.vault, 'goal', 'Blocked goal', 'Finish the acceptance review.',
                         ['Synthetic acceptance goal'], origin='user', flags=self.flags, skill_active=True)
        self.assertEqual(saved['status'], 'created', saved)


if __name__ == '__main__':
    unittest.main()
