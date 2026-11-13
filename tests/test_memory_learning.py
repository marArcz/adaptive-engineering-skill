"""General learning and legacy engineering compatibility use synthetic sources only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from memory_capture import FLAGS
from memory_context import build_context
from memory_learning import learn_knowledge, save_candidate
from memory_operations import inspect_record, register_project
from memory_search import search_memory
from memory_setup import setup_memory, set_capture
from memory_store import PublicationError, _publish
from test_tools import ROOT, SCRIPTS, run
from vault_guard import CaptureGate
from search_vault import search as legacy_search
from search_catalog import search as catalog_search


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name)
        setup_memory(self.vault)
        self.flags = dict.fromkeys(FLAGS, False)
        self.arguments = {'applicability': 'Planning short study sessions.',
                          'limitations': 'Supplied advice has not been independently tested.',
                          'sources': ['Synthetic supplied explanation about study habits'],
                          'evidence': 'user_claim', 'flags': self.flags,
                          'user_requested': True, 'skill_active': True}

    def learn(self, subject='Study sessions', findings='Use timeboxed study sessions.', **changes):
        return learn_knowledge(self.vault, subject, findings, **(self.arguments | changes))

    def candidate(self, subject='Bounded retries', findings='Stop retrying after a fixed attempt count.', **changes):
        return save_candidate(self.vault, subject, findings, technology='Python', **(self.arguments | changes))

    def files(self):
        return {p.relative_to(self.vault).as_posix(): p.read_bytes()
                for p in self.vault.rglob('*') if p.is_file()}

    def test_general_subject_has_honest_provenance_and_never_becomes_profile(self):
        saved = self.learn()
        self.assertEqual(saved['status'], 'created', saved)
        record = inspect_record(self.vault, saved['record_id'])
        self.assertEqual(record['metadata']['kind'], 'knowledge')
        self.assertEqual(record['metadata']['basis'], 'user-stated')
        self.assertIn('not independently verified', record['body'])
        self.assertIn('Planning short study sessions.', record['body'])
        self.assertIn('study', build_context(self.vault, 'study')['context'].lower())
        self.assertNotIn(saved['record_id'], build_context(self.vault, view='profile')['bootstrap_ids'])
        repeated = self.learn()
        self.assertEqual(repeated['status'], 'unchanged')
        self.assertEqual(repeated['record_id'], saved['record_id'])
        self.assertFalse(repeated['announcement'])
        enriched = self.learn(sources=['A later synthetic confirmation'])
        self.assertEqual(enriched['status'], 'updated', enriched)
        self.assertEqual(enriched['record_id'], saved['record_id'])
        changed = self.learn(findings='Use a different learning schedule.')
        self.assertEqual(changed['status'], 'needs_review')
        self.assertEqual(changed['trace']['reason'], 'knowledge_correction_required')

    def test_inspected_sources_inferences_and_domains_stay_distinct(self):
        source = self.learn(evidence='inspected_source', sources=['https://example.org/study'])
        record = inspect_record(self.vault, source['record_id'])
        self.assertEqual(record['metadata']['basis'], 'source-supported')
        self.assertIn('inspection alone does not establish', record['body'])
        inferred = self.learn(subject='Tentative study approach', evidence='inference')
        self.assertEqual(inspect_record(self.vault, inferred['record_id'])['metadata']['basis'], 'inferred')
        changed = self.learn(subject='Tentative study approach', evidence='inspected_source')
        self.assertEqual(changed['status'], 'needs_review')
        engineering = self.learn(domain='engineering')
        self.assertEqual(engineering['status'], 'created', engineering)
        self.assertNotEqual(engineering['record_id'], source['record_id'])
        self.assertIn('engineering', inspect_record(self.vault, engineering['record_id'])['metadata']['title'])

    def test_authority_and_privacy_boundaries_do_not_write_or_echo_payload(self):
        before = self.files()
        for changes in ({'user_requested': False}, {'skill_active': False},
                        *({'flags': self.flags | {key: True}} for key in
                          ('temporary', 'do_not_remember', 'secret', 'third_party_private', 'sensitive'))):
            with self.subTest(changes=changes):
                for function in (self.learn, self.candidate):
                    result = function(findings='Synthetic confidential payload.', **changes)
                    self.assertEqual(result['status'], 'excluded', result)
                    self.assertNotIn('confidential payload', json.dumps(result))
        self.assertEqual(self.files(), before)
        for evidence in ('source_instruction', 'hypothetical'):
            self.assertEqual(self.learn(evidence=evidence)['status'], 'unavailable')
            self.assertEqual(self.candidate(evidence=evidence)['status'], 'unavailable')
        self.assertEqual(self.files(), before)

    def test_paths_are_rejected_in_all_new_learning_content(self):
        before = self.files()
        cases = ({'subject': 'Study ../private'}, {'findings': 'Read src/private.py'},
                 {'applicability': '/home/synthetic/work'}, {'limitations': 'Inspect C:\\private\\note.txt'},
                 {'sources': ['The record came from ./project']},
                 {'findings': 'Mention synthetic-device', 'device_identifiers': ['synthetic-device']})
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.learn(**changes)['status'], 'unavailable')
                self.assertEqual(self.candidate(**changes)['status'], 'unavailable')
        rejected = self.candidate(tags=['src/private.py'])
        self.assertEqual(rejected['status'], 'unavailable')
        self.assertEqual(self.files(), before)

    def test_project_scoping_and_related_sources(self):
        project = register_project(self.vault, 'Study project', ['Synthetic project context'],
                                   flags=self.flags, skill_active=True,
                                   repository='https://example.org/team/study')['record_id']
        missing = self.learn(scope='project', project_id=str(uuid.uuid4()))
        self.assertEqual(missing['status'], 'needs_review')
        saved = self.learn(scope='project', project_id=project)
        self.assertEqual(saved['status'], 'created', saved)
        self.assertEqual(search_memory(self.vault, 'study', scope='general')['matches'], [])
        self.assertIn(saved['record_id'], {r['id'] for r in search_memory(self.vault, 'study', project_id=project)['matches']})
        cross_scope = self.learn(subject='Unscoped copy', related_ids=[saved['record_id']])
        self.assertEqual(cross_scope['status'], 'needs_review')
        self.assertEqual(cross_scope['trace']['reason'], 'learning_reference_scope_mismatch')

    def test_legacy_notes_and_reviewed_catalog_are_byte_preserved(self):
        existing = self.vault / 'knowledge'
        existing.mkdir()
        for fixture in ('legacy-approved.md', 'legacy-candidate.md'):
            (existing / fixture).write_bytes((ROOT / 'tests/fixtures' / fixture).read_bytes())
        catalog = self.vault / 'references/github/catalog.json'
        catalog.parent.mkdir(parents=True)
        catalog.write_text(json.dumps({'schema_version': 1, 'custom': 'keep', 'repositories': [
            {'id': 'reviewed', 'url': 'https://github.com/example/reviewed', 'status': 'approved',
             'description': 'Queue reference', 'tags': ['queue'], 'important_paths': ['old/source.py'],
             'reviewed_commit': 'abc123', 'verified_at': '2026-10-24', 'custom': 'preserve'}]}))
        before = self.files()
        saved = self.candidate(tags=['queue'], sources=['https://github.com/example/reviewed'])
        self.assertEqual(saved['status'], 'created', saved)
        self.assertFalse(saved['catalog_updated'])
        self.assertEqual(self.learn()['status'], 'created')
        for relative, raw in before.items():
            self.assertEqual((self.vault / relative).read_bytes(), raw)
        self.assertTrue(legacy_search(self.vault, 'queue')['matches'])
        reviewed = catalog_search(self.vault, 'queue')['matches'][0]
        self.assertEqual(reviewed['status'], 'approved')
        self.assertEqual(reviewed['important_paths'], ['old/source.py'])
        candidate = (self.vault / saved['path']).read_text()
        self.assertIn('status: "candidate"', candidate)
        self.assertIn('verified_at: ""', candidate)
        self.assertNotIn('old/source.py', candidate)

    def test_legacy_snapshots_are_idempotent_and_never_overwrite_a_manual_edit(self):
        first = self.candidate()
        self.assertEqual(first['status'], 'created', first)
        repeated = self.candidate()
        self.assertEqual(repeated['status'], 'unchanged')
        self.assertEqual(first['path'], repeated['path'])
        self.assertFalse(repeated['announcement'])
        refresh = self.candidate(findings='Use bounded retries with backoff.')
        self.assertEqual(refresh['status'], 'created')
        self.assertNotEqual(first['path'], refresh['path'])
        path = self.vault / first['path']
        path.write_text(path.read_text().replace('candidate', 'approved', 1))
        before = path.read_bytes()
        blocked = self.candidate()
        self.assertEqual(blocked['status'], 'unavailable')
        self.assertFalse(blocked['announcement'])
        self.assertEqual(path.read_bytes(), before)

    def test_legacy_learning_needs_no_managed_setup_and_is_separately_authorized(self):
        set_capture(self.vault, 'paused')
        self.assertEqual(self.learn()['status'], 'paused')
        saved = self.candidate()
        self.assertEqual(saved['status'], 'created', saved)
        with tempfile.TemporaryDirectory() as temporary:
            legacy = Path(temporary)
            result = save_candidate(legacy, 'Legacy learning', 'Use bounded retries.', technology='Python', **self.arguments)
            self.assertEqual(result['status'], 'created', result)
            self.assertFalse((legacy / 'memory').exists())

    def test_failed_or_uncertain_publication_has_no_success_and_keeps_pointer(self):
        with patch('memory_learning._publish', side_effect=PublicationError(False)):
            result = self.candidate()
        self.assertEqual(result['status'], 'unavailable')
        self.assertFalse(result['may_have_written'])
        def uncertain(*args):
            _publish(*args)
            raise PublicationError(True)
        with patch('memory_learning._publish', side_effect=uncertain):
            result = self.candidate()
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['may_have_written'])
        self.assertFalse(result['announcement'])
        self.assertTrue((self.vault / result['path']).is_file())
        self.assertEqual(self.candidate()['status'], 'unchanged')

    def test_merge_unsafe_storage_and_conflict_markers_block_candidates(self):
        with patch('memory_learning.capture_gate', return_value=CaptureGate(False, 'unresolved', 'blocked')):
            self.assertEqual(self.candidate()['reason'], 'merge_gate_blocked')
        self.assertFalse((self.vault / 'research').exists())
        self.assertEqual(self.candidate(findings='<<<<<<< HEAD\nprivate\n=======\nother\n>>>>>>> branch')['status'], 'unavailable')
        self.assertFalse((self.vault / 'research').exists())
        with tempfile.TemporaryDirectory() as temporary:
            (self.vault / 'research').symlink_to(temporary, target_is_directory=True)
            self.assertEqual(self.candidate()['status'], 'unavailable')
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_unverified_discovery_reports_partial_candidate_save(self):
        with patch('search_vault.search', side_effect=PermissionError):
            result = self.candidate()
        self.assertEqual(result['status'], 'partial')
        self.assertFalse(result['announcement'])
        self.assertTrue((self.vault / result['path']).is_file())
        self.assertEqual(self.candidate()['status'], 'unchanged')

    def test_explicit_candidate_links_are_portable_but_traversal_is_rejected(self):
        candidate = self.candidate()
        source = '[Saved engineering candidate](' + candidate['path'] + ')'
        learned = self.learn(sources=[source], evidence='inspected_source')
        self.assertEqual(learned['status'], 'created', learned)
        self.assertEqual(inspect_record(self.vault, learned['record_id'])['metadata']['sources'], [source])
        for link in ('[Bad](research/candidates/../../private.md)',
                     '[Bad](research/candidates/%2e%2e/private.md)',
                     '[src/private.py](research/candidates/safe.md)',
                     'research/candidates/unwrapped.md'):
            self.assertEqual(self.learn(sources=[link])['status'], 'unavailable')

    def test_intervening_edit_during_candidate_discovery_is_preserved_and_unverified(self):
        def changed(vault, subject, **options):
            found = legacy_search(vault, subject, **options)
            path = vault / found['matches'][0]['path']
            path.write_text(path.read_text().replace('Stop retrying after a fixed attempt count.',
                                                     'Manually changed guidance.'))
            return found
        with patch('search_vault.search', side_effect=changed):
            result = self.candidate()
        self.assertEqual(result['status'], 'partial', result)
        self.assertFalse(result['announcement'])
        self.assertIn('Manually changed guidance.', (self.vault / result['path']).read_text())

    def test_local_pattern_engineering_and_non_coding_learning_smoke(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / 'StudyPlan.py').write_text('def schedule_study():\n    return "timebox"\n')
            before = self.files()
            found = json.loads(run(SCRIPTS / 'find_patterns.py', '--repo', repo, '--query', 'schedule_study').stdout)
            self.assertEqual(found['matches'][0]['path'], 'StudyPlan.py')
            self.assertEqual(self.files(), before)
            saved = self.learn()
            self.assertEqual(saved['status'], 'created')
            recalled = search_memory(self.vault, 'study')['matches']
            self.assertEqual(recalled[0]['id'], saved['record_id'])
            self.assertNotIn(str(repo), (self.vault / recalled[0]['path']).read_text())

    def test_standalone_installed_general_and_legacy_learning(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            run(ROOT / 'install.py', '--target', 'repo', '--repo', repo)
            scripts = repo / '.agents/skills/adaptive-engineering/scripts'
            code = ('import json,sys;sys.path.insert(0,sys.argv[1]);'
                    'from memory_learning import learn_knowledge,save_candidate;'
                    'kw=json.loads(sys.argv[3]);'
                    'print(learn_knowledge(sys.argv[2],"Study planning","Use short sessions.",**kw)["status"]);'
                    'print(save_candidate(sys.argv[2],"Retry planning","Bound the attempts.",technology="Python",**kw)["status"])')
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            result = subprocess.run([sys.executable, '-c', code, str(scripts), str(self.vault), json.dumps(self.arguments)],
                                    cwd=repo, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ['created', 'created'])


if __name__ == '__main__':
    unittest.main()
