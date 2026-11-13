"""Session controls and synthetic operation routes; no fresh-agent claims."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory_capture import FLAGS, _capture_lock, capture
from memory_consolidation import consolidate, plan_consolidation
from memory_context import build_context
from memory_corrections import correct, record_contradiction, correction_candidates
from memory_forgetting import forget, plan_forgetting
from memory_journal import journal, inspect_experience
from memory_operations import remember, inspect_record, register_project, continue_project
from memory_search import memory_snapshot, search_memory
from memory_session import activate, change_capture
from memory_setup import POLICY, read_policy, set_capture, setup_memory
from test_tools import ROOT, run
from vault_guard import CaptureGate


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name)
        setup_memory(self.vault)
        self.flags = dict.fromkeys(FLAGS, False)
        self.sources = ['Synthetic session fixture: direct statement']

    def remember(self, topic='preference', title='Reply length', body='Use short replies.', **options):
        return remember(self.vault, topic, title, body, self.sources,
                        origin='user', flags=self.flags, skill_active=True, **options)

    def files(self):
        return {p.relative_to(self.vault).as_posix(): p.read_bytes()
                for p in self.vault.rglob('*') if p.is_file()}

    def test_activation_is_read_only_general_bounded_and_not_a_save_claim(self):
        saved = self.remember()
        project = register_project(self.vault, 'Synthetic project', self.sources, flags=self.flags,
                                   repository='https://example.org/team/session', skill_active=True)['record_id']
        self.remember(title='Project reply style', body='Only this project uses dense tables.',
                      scope='project', project_id=project)
        before = self.files()
        active = activate(self.vault, current_instructions='Explain this request in detail.')
        self.assertEqual(active['status'], 'ready', active)
        self.assertTrue(active['capture_eligible'])
        self.assertFalse(active['persistence_verified'])
        self.assertIn(saved['record_id'], active['bootstrap_ids'])
        self.assertIn('Explain this request in detail.', active['context'])
        self.assertNotIn('dense tables', active['context'])
        self.assertEqual(active['excerpt_count'], 0)
        self.assertLessEqual(len(active['context']), 12000)
        self.assertEqual(self.files(), before)
        small = activate(self.vault, max_chars=600)
        self.assertLessEqual(len(small['context']), 600)
        self.assertEqual(self.files(), before)

    def test_empty_missing_and_unconfigured_vaults_do_not_invent_or_initialize(self):
        empty = activate(self.vault)
        self.assertEqual(empty['bootstrap_ids'], [])
        self.assertEqual(empty['excerpt_ids'], [])
        before = self.files()
        missing = self.vault / 'missing'
        self.assertEqual(activate(missing)['reason'], 'vault_missing_or_inaccessible')
        self.assertFalse(missing.exists())
        with patch('memory_session.resolve_vault', return_value=None):
            self.assertEqual(activate()['reason'], 'vault_not_configured')
            self.assertEqual(change_capture('paused', user_requested=True, skill_active=True)['status'], 'unavailable')
        self.assertEqual(self.files(), before)

    def test_configuration_precedence_is_reused_by_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            other = Path(temporary)
            setup_memory(other)
            self.remember()
            with patch.dict(os.environ, {'ENGINEERING_VAULT_PATH': str(other)}):
                implicit = json.loads(run(ROOT / 'memory_session.py').stdout)
                explicit = json.loads(run(ROOT / 'memory_session.py', '--vault', self.vault).stdout)
            self.assertEqual(implicit['bootstrap_ids'], [])
            self.assertEqual(len(explicit['bootstrap_ids']), 1)

    def test_invalid_settings_and_merge_gates_preserve_read_only_context(self):
        self.remember()
        with patch('memory_session.capture_gate', return_value=CaptureGate(False, 'unresolved', 'blocked')):
            blocked = activate(self.vault)
        self.assertFalse(blocked['capture_eligible'])
        self.assertEqual(blocked['reason'], 'merge_gate_blocked')
        self.assertIn('Use short replies.', blocked['context'])
        (self.vault / POLICY).write_text('{}')
        invalid = activate(self.vault)
        self.assertEqual(invalid['status'], 'recall_only')
        self.assertFalse(invalid['capture_eligible'])
        self.assertIn('Use short replies.', invalid['context'])

    def test_incomplete_recall_never_enables_capture(self):
        self.remember()
        (self.vault / 'memory/profile' / 'unidentifiable.md').write_text('invalid input')
        result = activate(self.vault)
        self.assertTrue(result['memory_incomplete'])
        self.assertFalse(result['capture_eligible'])
        self.assertEqual(result['bootstrap_ids'], [])

    def test_tightened_boundaries_are_visible_and_not_relaxed_by_activation(self):
        data = read_policy(self.vault)
        data['boundaries'] = dict.fromkeys(data['boundaries'], 'exclude')
        (self.vault / POLICY).write_text(json.dumps(data))
        before = self.files()
        result = activate(self.vault)
        self.assertEqual(result['boundaries'], data['boundaries'])
        self.assertFalse(result['capture_eligible'])
        self.assertEqual(result['reason'], 'all_capture_categories_excluded')
        self.assertEqual(self.files(), before)

    def test_pause_resume_preserve_policy_and_no_change_is_quiet(self):
        self.remember()
        data = read_policy(self.vault)
        data['custom_setting'] = 'preserve this setting'
        (self.vault / POLICY).write_text(json.dumps(data))
        before = self.files()
        for options in ({}, {'user_requested': True}, {'skill_active': True}):
            result = change_capture('paused', self.vault, **options)
            self.assertEqual(result['status'], 'excluded')
        self.assertEqual(self.files(), before)
        paused = change_capture('paused', self.vault, user_requested=True, skill_active=True)
        self.assertEqual(paused['status'], 'updated', paused)
        self.assertTrue(paused['announcement'])
        active = activate(self.vault)
        self.assertEqual(active['reason'], 'capture_paused')
        self.assertIn('Use short replies.', active['context'])
        rejected = self.remember(title='A new subject')
        self.assertEqual(rejected['status'], 'paused')
        settings = (self.vault / POLICY).read_bytes()
        unchanged = change_capture('paused', self.vault, user_requested=True, skill_active=True)
        self.assertEqual(unchanged['status'], 'unchanged')
        self.assertFalse(unchanged['announcement'])
        self.assertEqual((self.vault / POLICY).read_bytes(), settings)
        resumed = change_capture('active', self.vault, user_requested=True, skill_active=True)
        self.assertEqual(resumed['status'], 'updated')
        self.assertEqual(read_policy(self.vault), data)

    def test_mode_failures_busy_and_unsafe_settings_have_no_success_claim(self):
        with patch('memory_session.set_capture', side_effect=PermissionError):
            failed = change_capture('paused', self.vault, user_requested=True, skill_active=True)
        self.assertEqual(failed['status'], 'unavailable')
        self.assertFalse(failed['announcement'])
        self.assertTrue(failed['may_have_written'])
        self.assertEqual(read_policy(self.vault)['capture'], 'active')
        def uncertain(vault, mode):
            set_capture(vault, mode)
            raise OSError('synthetic failed readback')
        with patch('memory_session.set_capture', side_effect=uncertain):
            failed = change_capture('paused', self.vault, user_requested=True, skill_active=True)
        self.assertEqual(failed['status'], 'unavailable')
        self.assertTrue(failed['may_have_written'])
        self.assertFalse(failed['announcement'])
        with _capture_lock(self.vault):
            self.assertEqual(change_capture('active', self.vault, user_requested=True, skill_active=True)['status'], 'busy')
        with patch('memory_session.capture_gate', return_value=CaptureGate(False, 'unresolved', 'blocked')):
            self.assertEqual(change_capture('active', self.vault, user_requested=True, skill_active=True)['reason'], 'merge_gate_blocked')
        policy = self.vault / POLICY
        outside = self.vault / 'external-settings.json'
        policy.rename(outside)
        policy.symlink_to(outside)
        raw = outside.read_bytes()
        self.assertEqual(change_capture('active', self.vault, user_requested=True, skill_active=True)['status'], 'unavailable')
        self.assertEqual(outside.read_bytes(), raw)

    def test_intervening_policy_edit_is_reported_unverified(self):
        def concurrent(vault, mode):
            set_capture(vault, mode)
            data = read_policy(vault)
            data['other_edit'] = 'preserve and report'
            (vault / POLICY).write_text(json.dumps(data))
        with patch('memory_session.set_capture', side_effect=concurrent):
            result = change_capture('paused', self.vault, user_requested=True, skill_active=True)
        self.assertEqual(result['status'], 'unavailable')
        self.assertTrue(result['may_have_written'])
        self.assertFalse(result['announcement'])
        self.assertEqual(read_policy(self.vault)['other_edit'], 'preserve and report')

    def test_synthetic_conversation_operation_routes(self):
        # Routes are deliberately selected by the caller, not an NLP classifier.
        self.assertEqual(activate(self.vault)['bootstrap_ids'], [])
        # “Remember that I prefer short replies”; repeat without new evidence.
        saved = self.remember()
        self.assertEqual(saved['status'], 'created')
        repeat = self.remember()
        self.assertEqual(repeat['status'], 'unchanged')
        self.assertFalse(repeat['announcement'])
        # “What do you know about me?” / inspect the provenance.
        profile = build_context(self.vault, view='profile')
        self.assertIn('Use short replies.', profile['context'])
        inspected = inspect_record(self.vault, saved['record_id'])
        self.assertEqual(inspected['metadata']['basis'], 'user-stated')
        # “For this request only use detailed replies”; do not retain this as a preference.
        proposal = {'category': 'durable_preferences_goals_decisions', 'origin': 'user',
                    'kind': 'preference', 'title': 'Temporary reply instruction', 'body': 'Use detailed replies.',
                    'scope': 'general', 'sources': self.sources, 'flags': self.flags | {'temporary': True}}
        before = len(memory_snapshot(self.vault)['groups'])
        for flags, origin in (({'temporary': True}, 'user'), ({'sensitive': True}, 'user'),
                              ({'secret': True}, 'user'), ({'third_party_private': True}, 'user'),
                              ({}, 'source_instruction'), ({}, 'hypothetical')):
            rejected = capture(self.vault, proposal | {'flags': self.flags | flags, 'origin': origin}, skill_active=True)
            self.assertEqual(rejected['status'], 'excluded', rejected)
            self.assertFalse(rejected['announcement'])
        self.assertEqual(len(memory_snapshot(self.vault)['groups']), before)
        # A general life decision needs no fictitious project; an inferred preference stays inferred.
        general = capture(self.vault, proposal | {'kind': 'knowledge', 'title': 'Decision: learning routine',
                          'body': 'Reserve time for learning.', 'flags': self.flags}, skill_active=True)
        self.assertEqual(general['status'], 'created', general)
        inferred = capture(self.vault, proposal | {'category': 'inferences', 'origin': 'inference',
                           'title': 'Tentative planning preference', 'body': 'Small plans may be useful.',
                           'flags': self.flags}, skill_active=True)
        self.assertEqual(inferred['status'], 'created', inferred)
        self.assertEqual(inspect_record(self.vault, inferred['record_id'])['metadata']['basis'], 'inferred')
        # “That preference changed: I now prefer detailed replies.”
        fixed = correct(self.vault, [saved['record_id']], 'Use detailed replies.', self.sources,
                        expected_tokens={saved['record_id']: inspected['token']}, scope='general',
                        origin='user', flags=self.flags, clear=True, skill_active=True)
        self.assertEqual(fixed['status'], 'created', fixed)
        self.assertNotIn('Use short replies.', build_context(self.vault, view='profile')['context'])
        # An uncertain contradiction is historical/unresolved, not current advice.
        current = inspect_record(self.vault, fixed['record_id'])
        uncertain = record_contradiction(self.vault, [fixed['record_id']], 'Reply style is uncertain.',
                        self.sources, expected_tokens={fixed['record_id']: current['token']}, scope='general',
                        origin='user', flags=self.flags, skill_active=True)
        self.assertEqual(uncertain['status'], 'unresolved', uncertain)
        self.assertEqual(len(correction_candidates(self.vault, fixed['record_id'])['candidates']), 2)
        # Resolve all claims before subsequent captures (the writer fails closed on conflicts).
        candidates = correction_candidates(self.vault, fixed['record_id'])['candidates']
        corrected = correct(self.vault, [r['id'] for r in candidates], 'Use detailed replies.', self.sources,
                            expected_tokens={r['id']: r['token'] for r in candidates}, scope='general',
                            origin='user', flags=self.flags, clear=True, skill_active=True)
        self.assertEqual(corrected['status'], 'created', corrected)
        # “Continue this project”: establish portable identity then use scoped context.
        project = register_project(self.vault, 'Session project', self.sources, flags=self.flags,
                                   repository='https://example.org/team/session', skill_active=True)['record_id']
        decision = self.remember('decision', 'Release scope', 'Ship the smaller release.',
                                 scope='project', project_id=project)
        self.assertEqual(decision['status'], 'created', decision)
        continuation = continue_project(self.vault, project_id=project)
        self.assertEqual(continuation['status'], 'ready', continuation)
        self.assertIn('Ship the smaller release.', continuation['context'])
        event = journal(self.vault, 'Release scope agreement', significance='decision',
                        context='Synthetic user and assistant planned a release.', happened='They chose smaller scope.',
                        why='Time was limited.', outcome='A smaller plan was chosen.', lesson=None,
                        sources=self.sources, origin='user', flags=self.flags, skill_active=True,
                        scope='project', project_id=project, related_ids=[decision['record_id']])
        self.assertEqual(event['status'], 'created', event)
        self.assertIsNone(inspect_experience(self.vault, event['record_id'])['event']['inferred_lesson'])
        # Maintenance uses the actual plan and keeps unchanged runs quiet.
        self.assertEqual(plan_consolidation(self.vault)['status'], 'unchanged')
        maintenance = consolidate(self.vault, flags=self.flags, skill_active=True)
        self.assertEqual(maintenance['status'], 'unchanged')
        self.assertFalse(maintenance['announcement'])
        # Paused capture allows explicit forgetting and removes linked experience content.
        self.assertEqual(change_capture('paused', self.vault, user_requested=True, skill_active=True)['status'], 'updated')
        plan = plan_forgetting(self.vault, record_id=decision['record_id'])
        forgotten = forget(self.vault, record_id=decision['record_id'], expected_token=plan['token'],
                           user_requested=True, skill_active=True)
        self.assertEqual(forgotten['status'], 'forgotten', forgotten)
        self.assertEqual(inspect_record(self.vault, event['record_id'])['status'], 'not_found')
        self.assertEqual(search_memory(self.vault, record_id=decision['record_id'], history=True)['matches'], [])

    def test_explicit_learning_keeps_legacy_candidate_route_separate(self):
        # Supplied-material fixture for “learn this”; T17 owns managed learning integration.
        set_capture(self.vault, 'paused')
        before = memory_snapshot(self.vault)['groups']
        note = self.vault / 'research/candidates' / 'bounded-learning.md'
        note.parent.mkdir(parents=True)
        note.write_text('---\ntitle: Bounded learning\nstatus: candidate\n'
                        'tags: [learning]\ntechnology: general\napplies_to: study planning\n'
                        'verified_at: ""\nsources: [Synthetic supplied material]\n---\n'
                        'Short learning sessions can be scheduled. Unverified supplied advice.\n')
        scripts = ROOT / '.agents/skills/adaptive-engineering/scripts'
        found = json.loads(run(scripts / 'search_vault.py', '--vault', self.vault, '--query', 'learning').stdout)
        self.assertEqual(found['matches'][0]['status'], 'candidate')
        self.assertEqual(memory_snapshot(self.vault)['groups'], before)
        self.assertEqual(read_policy(self.vault)['capture'], 'paused')

    def test_standalone_session_cli_and_explicit_mode_authorization(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            run(ROOT / 'install.py', '--target', 'repo', '--repo', repo)
            script = repo / '.agents/skills/adaptive-engineering/scripts/memory_session.py'
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            def installed(*args):
                return subprocess.run([sys.executable, str(script), '--vault', str(self.vault), *args],
                                      cwd=repo, env=env, text=True, capture_output=True)
            result = installed()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'ready')
            denied = installed('--action', 'pause')
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual(json.loads(denied.stdout)['status'], 'excluded')
            result = installed('--action', 'pause', '--user-requested')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'updated')
            self.assertEqual(read_policy(self.vault)['capture'], 'paused')


if __name__ == '__main__':
    unittest.main()
