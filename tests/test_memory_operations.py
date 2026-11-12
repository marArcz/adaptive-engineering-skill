"""Synthetic remember/inspect/continue operations using portable projects."""
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
from memory_operations import remember, inspect_record, register_project, associate_project, continue_project
from memory_setup import setup_memory
from test_tools import ROOT, run


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        setup_memory(self.vault)
        self.flags = dict.fromkeys(FLAGS, False)

    def project(self, name='Synthetic project', repository='https://example.org/team/project', **kwargs):
        result = register_project(self.vault, name, ['Synthetic project identity'], flags=self.flags,
                                  repository=repository, skill_active=True, **kwargs)
        self.assertEqual(result['status'], 'created', result)
        return result['record_id']

    def remember(self, topic='fact', title='Release context', body='Release happens in June.\n', **kwargs):
        return remember(self.vault, topic, title, body, kwargs.pop('sources', ['Synthetic user statement']),
                        origin=kwargs.pop('origin','user'), flags=self.flags, skill_active=True, **kwargs)

    def test_all_topics_creation_and_inspection(self):
        project = self.project()
        for topic in ('fact','preference','goal','decision','progress','commitment','question'):
            with self.subTest(topic=topic):
                args = {'scope':'project','project_id':project} if topic == 'decision' else {}
                result = self.remember(topic, **args)
                self.assertEqual(result['status'], 'created', result)
                record = inspect_record(self.vault, result['record_id'])
                self.assertEqual(record['status'], 'current')
                self.assertEqual(record['metadata']['basis'], 'user-stated')
                self.assertEqual(record['metadata']['sources'], ['Synthetic user statement'])
                self.assertIn('token', record)
        self.assertEqual(self.remember('preference', origin='observation')['status'], 'needs_review')
        self.assertEqual(self.remember('decision')['status'], 'needs_review')

    def test_evidence_updates_stable_id_and_compatible_metadata(self):
        first = self.remember()
        old = inspect_record(self.vault, first['record_id'])
        # User-added compatible metadata on an existing revision is preserved.
        path = next((self.vault/'memory/revisions').glob(first['record_id'] + '.*.md'))
        path.write_text(path.read_text().replace('kind:', 'custom: "keep"\nkind:', 1))
        repeat = self.remember()
        self.assertEqual(repeat['status'], 'unchanged')
        result = self.remember(sources=['Later synthetic confirmation'])
        self.assertEqual(result['status'], 'updated', result)
        self.assertEqual(result['record_id'], first['record_id'])
        current = inspect_record(self.vault, first['record_id'])
        self.assertEqual(current['metadata']['custom'], 'keep')
        self.assertEqual(len(current['metadata']['sources']), 2)
        changed = self.remember(body='Release happens in July.\n', record_id=first['record_id'])
        self.assertEqual(changed['trace']['reason'], 'correction_required')
        self.assertEqual(inspect_record(self.vault, first['record_id'])['body'], old['body'])

    def test_append_progress_stale_checks_and_no_change_retry(self):
        first = self.remember('progress', body='Planning finished.\n')
        original = inspect_record(self.vault, first['record_id'])
        kwargs = {'record_id':first['record_id'], 'append':True, 'expected_token':original['token']}
        update = self.remember('progress', body='Implementation started.\n', **kwargs)
        self.assertEqual(update['status'], 'updated', update)
        repeated = self.remember('progress', body='Implementation started.\n', **kwargs)
        self.assertEqual(repeated['status'], 'unchanged')
        stale = self.remember('progress', body='Testing finished.\n', **kwargs)
        self.assertEqual(stale['status'], 'needs_review')
        current = inspect_record(self.vault, first['record_id'])
        self.assertIn('Planning finished.', current['body'])
        self.assertIn('Implementation started.', current['body'])
        self.assertNotIn('Testing finished.', current['body'])
        preference = self.remember('preference')
        self.assertEqual(self.remember('preference', body='New preference.', record_id=preference['record_id'], append=True)['trace']['reason'], 'correction_required')

    def test_project_identity_retry_and_ambiguous_names(self):
        first = self.project()
        retry = register_project(self.vault, 'Synthetic project', ['Synthetic project identity'],
                                 flags=self.flags, repository='git@example.org:team/project.git', skill_active=True)
        self.assertEqual(retry['status'], 'unchanged', retry)
        self.assertEqual(retry['record_id'], first)
        collision = register_project(self.vault, 'Synthetic project', ['Synthetic identity'], flags=self.flags,
                                     repository='https://example.org/other/project', skill_active=True)
        self.assertEqual(collision['status'], 'needs_review')
        second = self.project(repository='https://example.org/other/project', create_new=True)
        ambiguous = associate_project(self.vault, name='Synthetic project')
        self.assertEqual(ambiguous['status'], 'ambiguous')
        self.assertEqual(set(ambiguous['candidate_ids']), {first,second})
        self.assertEqual(associate_project(self.vault, project_id=first)['project_id'], first)
        self.assertEqual(associate_project(self.vault, project_id=first, repository='https://example.org/other/project')['status'], 'conflict')
        renamed = register_project(self.vault, 'Renamed project', ['Synthetic rename request'], flags=self.flags,
                                   repository='https://example.org/team/project', skill_active=True)
        self.assertEqual(renamed['status'], 'needs_review')
        no_remote = self.project(name='Offline project', repository=None)
        repeated = register_project(self.vault, 'Offline project', ['Synthetic project identity'], flags=self.flags,
                                    project_id=no_remote, skill_active=True)
        self.assertEqual(repeated['status'], 'unchanged', repeated)
        self.project(name='Q', repository='https://example.org/team/short')

    def test_project_isolation_and_runtime_checkouts(self):
        project = self.project()
        other = self.project(name='Other project', repository='https://example.org/team/other')
        decision = self.remember('decision', title='Queue design', body='Use bounded queue retries.\n',
                                 scope='project', project_id=project, reasoning='Retries should stop after a fixed number of attempts.')
        self.assertEqual(decision['status'], 'created', decision)
        second = self.remember('decision', title='Queue design', body='Use a different queue.\n', scope='project', project_id=other)
        self.assertEqual(second['status'], 'created')
        self.assertNotEqual(decision['record_id'], second['record_id'])
        self.assertEqual(inspect_record(self.vault, decision['record_id'], project_id=other)['status'], 'not_found')
        for name in ('checkout-one','differently-located-checkout'):
            checkout = self.root/name
            checkout.mkdir()
            subprocess.run(['git','-C',str(checkout),'init','-q'],check=True)
            subprocess.run(['git','-C',str(checkout),'remote','add','origin','git@example.org:team/project.git'],check=True)
            context = continue_project(self.vault, 'queue', workspace=checkout)
            self.assertEqual(context['status'], 'ready', context)
            self.assertEqual(context['project_id'], project)
            self.assertIn('Use bounded queue retries.', context['context'])
            self.assertIn('Retries should stop', context['context'])
            self.assertNotIn('Use a different queue.', context['context'])
        for path in (self.vault/'memory/revisions').glob('*.md'):
            self.assertNotIn(str(self.root), path.read_text())
        foreign = self.root/'foreign-workspace'
        foreign.mkdir()
        subprocess.run(['git','-C',str(foreign),'init','-q'],check=True)
        subprocess.run(['git','-C',str(foreign),'remote','add','origin','https://example.org/team/other'],check=True)
        with patch.dict(os.environ, {'GIT_DIR':str(foreign/'.git')}):
            context = continue_project(self.vault, 'queue', workspace=checkout)
        self.assertEqual(context['project_id'], project)
        self.assertEqual(self.remember(scope='project', project_id=str(uuid.uuid4()))['status'], 'needs_review')

    def test_boundary_activation_and_standalone_api(self):
        inactive = remember(self.vault,'fact','A fact','Some fact.',['Synthetic conversation'],origin='user',flags=self.flags)
        self.assertEqual(inactive['status'], 'excluded')
        self.assertEqual(self.remember(reasoning='/home/test/project')['status'], 'unavailable')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(ROOT/'install.py','--target','repo','--repo',root)
            scripts = root/'.agents/skills/adaptive-engineering/scripts'
            code = 'import sys; sys.path.insert(0,sys.argv[1]); from memory_operations import inspect_record; print(inspect_record(sys.argv[2],sys.argv[3])["status"])'
            env = dict(os.environ)
            env.pop('PYTHONPATH',None)
            result = subprocess.run([sys.executable,'-c',code,str(scripts),str(self.vault),str(uuid.uuid4())],
                                    cwd=root,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),'not_found')


if __name__ == '__main__':
    unittest.main()
