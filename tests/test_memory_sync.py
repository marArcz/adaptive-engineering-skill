"""Offline manual-sync simulation: two installed runtimes, local clones, no devices."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from distribution import RUNTIME_MODULES
from package_release import _run
from test_tools import ROOT


# Executed only by package_release._run's child Path.home wrapper. Every actual
# runtime subprocess call is spied; Git mutations belong solely to this harness.
DRIVER = '''import importlib,json,pathlib,subprocess,sys
from unittest.mock import patch
from _vault_common import resolve_vault
request=json.loads(sys.argv[1])
calls=[]
real_run=subprocess.run
def observed(command,*args,**kwargs):
    command=list(map(str,command))
    calls.append(command)
    allowed=(command[0]=='git' and command[1]=='-C' and
        (command[3:] in [['rev-parse','--show-toplevel'],['rev-parse','--git-dir'],
                         ['diff','--name-only','--diff-filter=U','-z'],
                         ['config','--get','remote.origin.url']]))
    if not allowed: raise AssertionError('Unexpected runtime subprocess: '+repr(command))
    return real_run(command,*args,**kwargs)
with patch('subprocess.run',side_effect=observed):
    module=importlib.import_module(request['module'])
    options=request.get('options',{})
    result=getattr(module,request['function'])(resolve_vault(None),*request.get('args',[]),**options)
print(json.dumps({'result':result,'calls':calls,'module_file':module.__file__}))
'''


class MemorySyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='adaptive-offline-sync-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith('GIT_') and k not in ('PYTHONPATH', 'ENGINEERING_VAULT_PATH')}
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'
        # Do not override HOME or CODEX_HOME. All Python config access is confined
        # to child-only Path.home fixtures, as in distribution verification.
        self.remote = self.root / 'offline-remote.git'
        self.git(self.root, 'init', '--bare', '--initial-branch=main', str(self.remote))
        self.devices = []
        self.calls = []
        self.harness_commands = []
        for name, vault_name, workspace_name in (
                ('fixture-alpha', 'notes-on-alpha', 'checkout-orchid'),
                ('fixture-beta', 'renamed-notes-beta', 'different-checkout-fern')):
            device = self.root / name
            device.mkdir()
            home, install = device / 'home', device / 'installed-build'
            home.mkdir()
            install.mkdir()
            vault, workspace = device / vault_name, device / workspace_name
            self.git(device, 'clone', str(self.remote), str(vault))
            self.git(vault, 'config', 'user.name', 'Synthetic offline sync')
            self.git(vault, 'config', 'user.email', 'offline@example.invalid')
            self.git(workspace.parent, 'init', '--initial-branch=main', str(workspace))
            self.git(workspace, 'remote', 'add', 'origin', 'https://example.invalid/team/portable-project.git')
            _run(ROOT / 'install.py', '--target', 'repo', '--repo', install,
                 home=home, cwd=device, env=self.env)
            scripts = install / '.agents/skills/adaptive-engineering/scripts'
            config = home / '.adaptive-engineering/config.json'
            _run(scripts / 'configure.py', '--vault', vault, home=home, cwd=device, env=self.env)
            driver = scripts / 'offline_fixture_driver.py'
            driver.write_text(DRIVER)
            self.devices.append(dict(home=home, scripts=scripts, vault=vault,
                                     workspace=workspace, config=config, driver=driver, cwd=device))
            if len(self.devices) == 1:
                self.commit(self.devices[0], 'HARNESS initial scaffolding')
                self.push(self.devices[0])
        self.a, self.b = self.devices
        self.flags = dict.fromkeys(('temporary', 'do_not_remember', 'sensitive', 'secret', 'third_party_private'), False)
        self.pull(self.b)
        for name in RUNTIME_MODULES:
            self.assertEqual((self.a['scripts'] / name).read_bytes(), (self.b['scripts'] / name).read_bytes())

    def git(self, directory, *args, ok=True):
        command = ['git', '-C', str(directory), *map(str, args)]
        if hasattr(self, 'harness_commands'):
            self.harness_commands.append(command)
        result = subprocess.run(command, env=self.env, capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def commit(self, device, message):
        self.git(device['vault'], 'add', '--all')
        self.git(device['vault'], 'commit', '-qm', message)

    def push(self, device):
        self.git(device['vault'], 'push', 'origin', 'main')

    def pull(self, device, *, ok=True):
        return self.git(device['vault'], 'pull', '--no-rebase', '--no-edit', 'origin', 'main', ok=ok)

    def runtime(self, device, module, function, *args, workspace=False, **options):
        if workspace:
            options['workspace'] = str(device['workspace'])
        request = dict(module=module, function=function, args=args, options=options)
        response = json.loads(_run(device['driver'], json.dumps(request), home=device['home'],
                                   cwd=device['cwd'], env=self.env).stdout)
        self.assertEqual(Path(response['module_file']).parent, device['scripts'])
        self.calls.extend(response['calls'])
        return response['result']

    def remember(self, device, title, body, *, topic='preference', **options):
        return self.runtime(device, 'memory_operations', 'remember', topic, title, body,
                            ['Synthetic offline sync statement'], flags=self.flags, origin='user',
                            skill_active=True, **options)

    def search(self, device, **options):
        return self.runtime(device, 'memory_search', 'search_memory', **options)['matches']

    def inspect(self, device, key):
        return self.runtime(device, 'memory_operations', 'inspect_record', key)

    def assert_portable(self):
        forbidden = [str(self.root), *(str(d[k]) for d in self.devices
                     for k in ('home', 'workspace', 'vault', 'config')), 'workspace_mapping', 'vault_path']
        for device in self.devices:
            for path in device['vault'].rglob('*'):
                if path.is_file() and '.git' not in path.relative_to(device['vault']).parts:
                    text = path.read_text()
                    for token in forbidden:
                        self.assertNotIn(token, text, str(path))
            tracked = self.git(device['vault'], 'ls-files').stdout
            self.assertNotIn('config.json', tracked)
            config = json.loads(device['config'].read_text())
            self.assertEqual(config['vault_path'], str(device['vault']))
            self.assertEqual(set(config), {'vault_path'})
        self.assertTrue(self.calls, 'The runtime spy must observe real Git inspection calls.')
        # The child spy permits only exact read-only commands and fails before any
        # unexpected subprocess could run. Sync operations are explicit harness calls.
        self.assertTrue(any('push' in c for c in self.harness_commands))
        self.assertTrue(any('pull' in c for c in self.harness_commands))

    def test_bidirectional_recall_correction_and_forgetting_closure(self):
        identity = self.runtime(self.a, 'memory_capture', 'capture', {
            'kind': 'assistant_identity', 'category': 'durable_preferences_goals_decisions',
            'title': 'Working agreement', 'body': 'Explain uncertainty when sharing findings.',
            'scope': 'general', 'origin': 'user', 'flags': self.flags,
            'sources': ['Synthetic explicit working agreement']}, skill_active=True)
        self.assertEqual(identity['status'], 'created', identity)
        pref = self.remember(self.a, 'Response detail', 'Use compact explanations.')
        fact = self.remember(self.a, 'Study interest', 'The user studies astronomy.', topic='fact')
        self.assertEqual(pref['status'], 'created', pref)
        self.assertEqual(fact['status'], 'created', fact)
        project = self.runtime(self.a, 'memory_operations', 'register_project', 'Portable fixture',
                               ['Synthetic project identity'], flags=self.flags, skill_active=True, workspace=True)
        self.assertEqual(project['status'], 'created', project)
        project_id = project['record_id']
        decision = self.remember(self.a, 'Release scope', 'Ship the small release first.', topic='decision',
                                 scope='project', project_id=project_id)
        self.assertEqual(decision['status'], 'created', decision)
        episode = self.runtime(self.a, 'memory_journal', 'journal', 'Release scope agreement',
            significance='decision', context='Synthetic planning discussion.', happened='A small release was chosen.',
            why='The scope fit the available time.', outcome='A release plan was selected.',
            lesson='Smaller releases may be easier to verify.', sources=['Synthetic release discussion'],
            origin='user', flags=self.flags, skill_active=True, scope='project', project_id=project_id,
            related_ids=[decision['record_id']])
        self.assertEqual(episode['status'], 'created', episode)
        feedback = []
        for number in (1, 2):
            row = self.runtime(self.a, 'memory_journal', 'journal', f'Feedback {number}',
                significance='collaboration_feedback', context='Synthetic collaboration.',
                happened=f'Compact explanations helped review number {number}.', why='Useful feedback.',
                outcome='The next step was clear.', lesson='Compact explanations may help review.',
                sources=[f'Synthetic independent feedback {number}'], origin='user', flags=self.flags,
                skill_active=True, related_ids=[pref['record_id']])
            self.assertEqual(row['status'], 'created', row)
            feedback.append(row['record_id'])
        initial = self.runtime(self.a, 'memory_summaries', 'build_summaries')
        self.assertTrue(any(r['entry_type'] == 'inferred_trait' for r in initial['items']))
        self.commit(self.a, 'HARNESS capture portable records')
        self.push(self.a)
        self.pull(self.b)
        active = self.runtime(self.b, 'memory_session', 'activate')
        self.assertTrue({identity['record_id'], pref['record_id'], fact['record_id']} <= set(active['bootstrap_ids']))
        continuation = self.runtime(self.b, 'memory_operations', 'continue_project', 'release', workspace=True)
        self.assertEqual(continuation['project_id'], project_id)
        self.assertIn(decision['record_id'], continuation['excerpt_ids'])
        self.assertEqual(self.runtime(self.b, 'memory_journal', 'inspect_experience', episode['record_id'])['status'], 'current')
        original = self.inspect(self.b, pref['record_id'])
        corrected = self.runtime(self.b, 'memory_corrections', 'correct', [pref['record_id']],
            'Use detailed explanations.', ['Synthetic explicit correction'],
            expected_tokens={pref['record_id']: original['token']}, scope='general', origin='user',
            flags=self.flags, skill_active=True, clear=True)
        self.assertEqual(corrected['status'], 'created', corrected)
        self.commit(self.b, 'HARNESS correction on beta')
        self.push(self.b)
        self.pull(self.a)
        current = self.runtime(self.a, 'memory_context', 'build_context', 'explanations')
        self.assertIn('Use detailed explanations.', current['context'])
        self.assertNotIn('Use compact explanations.', current['context'])
        old = self.search(self.a, record_id=pref['record_id'], history=True)
        self.assertTrue(old and all(r['historical'] for r in old))
        self.assertEqual(self.inspect(self.a, corrected['record_id'])['status'], 'current')
        plan = self.runtime(self.a, 'memory_forgetting', 'plan_forgetting', record_id=corrected['record_id'])
        closure = {pref['record_id'], corrected['record_id'], *feedback}
        self.assertEqual(set(plan['record_ids']), closure)
        forgotten = self.runtime(self.a, 'memory_forgetting', 'forget', record_id=corrected['record_id'],
                                 expected_token=plan['token'], user_requested=True, skill_active=True)
        self.assertEqual(forgotten['status'], 'forgotten', forgotten)
        self.commit(self.a, 'HARNESS requested forgetting closure')
        self.push(self.a)
        self.pull(self.b)
        for device in self.devices:
            for key in closure:
                self.assertEqual(self.search(device, record_id=key, history=True), [])
                self.assertEqual(list((device['vault'] / 'memory/revisions').glob(key + '.*.md')), [])
            summaries = self.runtime(device, 'memory_summaries', 'build_summaries')
            self.assertFalse(closure & set(summaries['source_ids']))
            self.assertFalse(any(r['entry_type'] == 'inferred_trait' for r in summaries['items']))
            context = self.runtime(device, 'memory_context', 'build_context')['context']
            for payload in ('Use compact explanations.', 'Use detailed explanations.', 'Compact explanations may help review.'):
                self.assertNotIn(payload, context)
                for path in (device['vault'] / 'memory').rglob('*'):
                    if path.is_file():
                        self.assertNotIn(payload, path.read_text())
            markers = []
            for path in (device['vault'] / 'memory/deletions').glob('*.batch.json'):
                for marker in json.loads(path.read_text()):
                    self.assertEqual(set(marker), {'schema_version', 'id', 'deleted_at'})
                    markers.append(marker['id'])
            self.assertEqual(set(markers), closure)
            self.assertEqual(self.inspect(device, fact['record_id'])['body'], 'The user studies astronomy.')
            self.assertEqual(self.inspect(device, identity['record_id'])['status'], 'current')
            self.assertEqual(self.inspect(device, decision['record_id'])['status'], 'current')
        self.assert_portable()

    def test_textual_conflict_blocks_capture_but_keeps_unrelated_recall(self):
        pref = self.remember(self.a, 'Review habit', 'Explain the evidence.')
        self.assertEqual(pref['status'], 'created', pref)
        relative = 'knowledge/queue-conflict.md'
        path = self.a['vault'] / relative
        path.parent.mkdir(exist_ok=True)
        path.write_text('---\ntitle: Queue proposal\nstatus: approved\n---\nBase queue proposal.\n')
        self.commit(self.a, 'HARNESS conflict base')
        self.push(self.a)
        self.pull(self.b)
        versions = []
        for device, proposal in ((self.a, 'Alpha queue proposal.'), (self.b, 'Beta queue proposal.')):
            text = (device['vault'] / relative).read_text().replace('Base queue proposal.', proposal)
            (device['vault'] / relative).write_text(text)
            versions.append(text)
            self.commit(device, 'HARNESS divergent queue proposal')
        self.push(self.a)
        self.assertNotEqual(self.pull(self.b, ok=False).returncode, 0)
        self.assertIn(relative, self.git(self.b['vault'], 'diff', '--name-only', '--diff-filter=U').stdout)
        conflict_bytes = (self.b['vault'] / relative).read_bytes()
        self.assertIn(b'<<<<<<<', conflict_bytes)
        blocked = self.remember(self.b, 'Blocked capture', 'Save only after deliberate resolution.', topic='goal')
        self.assertEqual(blocked['trace']['reason'], 'merge_gate_blocked', blocked)
        self.assertEqual(blocked['announcement'], '')
        self.assertEqual((self.b['vault'] / relative).read_bytes(), conflict_bytes)
        active = self.runtime(self.b, 'memory_session', 'activate')
        self.assertIn(pref['record_id'], active['bootstrap_ids'])
        self.assertFalse(active['capture_eligible'])
        self.assertNotIn('queue proposal.', active['context'].lower())
        recalled = self.runtime(self.b, 'search_vault', 'search', 'queue', limit=30)
        self.assertNotIn(relative, {r['path'] for r in recalled['matches']})
        # Explicit HARNESS resolution retains both exact authored versions in
        # separate notes rather than choosing a timestamp or discarding a side.
        for label, text in zip(('alpha', 'beta'), versions):
            (self.b['vault'] / f'knowledge/queue-{label}.md').write_text(text)
        (self.b['vault'] / relative).write_text(
            '---\ntitle: Queue proposals retained\nstatus: approved\n---\nBoth authored queue proposals are retained for review.\n')
        self.commit(self.b, 'HARNESS deliberate resolution retains both versions')
        resumed = self.remember(self.b, 'Resumed capture', 'Resolution was reviewed.', topic='goal')
        self.assertEqual(resumed['status'], 'created', resumed)
        self.commit(self.b, 'HARNESS capture after resolution')
        self.push(self.b)
        self.pull(self.a)
        for device in self.devices:
            self.assertEqual(self.git(device['vault'], 'diff', '--name-only', '--diff-filter=U').stdout, '')
            for label, text in zip(('alpha', 'beta'), versions):
                self.assertEqual((device['vault'] / f'knowledge/queue-{label}.md').read_text(), text)
            self.assertEqual(self.inspect(device, resumed['record_id'])['status'], 'current')
        self.assert_portable()

    def test_clean_semantic_contradiction_stays_unresolved_in_both_merge_orders(self):
        # Rewind only disposable clones between subtests. Never touch source Git.
        base = self.git(self.a['vault'], 'rev-parse', 'HEAD').stdout.strip()
        for first_index in (0, 1):
            with self.subTest(first_pusher=first_index):
                for device in self.devices:
                    self.git(device['vault'], 'reset', '--hard', base)
                    # Git does not track empty managed directories; restore the
                    # fixture scaffolding after rewinding this disposable clone.
                    self.runtime(device, 'memory_setup', 'setup_memory')
                self.git(self.remote, 'update-ref', 'refs/heads/main', base)
                claims = []
                for index, device in enumerate(self.devices):
                    claim = self.remember(device, 'Response style',
                                          ('Use brief responses.', 'Use expansive responses.')[index])
                    self.assertEqual(claim['status'], 'created', claim)
                    if index == 1:
                        # A valid imported later timestamp must confer no authority.
                        record = self.inspect(device, claim['record_id'])
                        metadata = record['metadata'] | {'updated_at': '2099-01-01T00:00:00Z'}
                        update = self.runtime(device, 'memory_store', 'write_record', metadata, record['body'],
                                              expected_token=record['token'])
                        self.assertEqual(update['status'], 'updated', update)
                    claims.append(claim['record_id'])
                    self.commit(device, 'HARNESS independent semantic claim')
                first, second = self.devices[first_index], self.devices[1 - first_index]
                self.push(first)
                self.pull(second)
                self.push(second)
                self.pull(first)
                for device in self.devices:
                    self.assertEqual(self.git(device['vault'], 'diff', '--name-only', '--diff-filter=U').stdout, '')
                    self.assertEqual(self.search(device, query='response'), [])
                    candidates = self.runtime(device, 'memory_corrections', 'correction_candidates', claims[0])['candidates']
                    self.assertEqual({r['id'] for r in candidates}, set(claims))
                    self.assertTrue(all(not r['is_current_advice'] for r in candidates))
                    history = self.search(device, query='response', history=True)
                    self.assertEqual({r['id'] for r in history}, set(claims))
                    self.assertTrue(all(r['historical'] and r['state'] == 'unresolved' for r in history))
                    context = self.runtime(device, 'memory_context', 'build_context', 'response')['context']
                    self.assertNotIn('Use brief responses.', context)
                    self.assertNotIn('Use expansive responses.', context)
                self.assert_portable()


if __name__ == '__main__':
    unittest.main()
