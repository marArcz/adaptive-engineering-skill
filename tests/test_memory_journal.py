"""Selective experience fixtures; no live semantic-selection claims."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory_capture import FLAGS
from memory_journal import journal, inspect_experience, related_experiences
from memory_operations import remember, register_project
from memory_setup import POLICY, set_capture, setup_memory
from memory_store import write_record
from test_tools import ROOT, run


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault=Path(self.temp.name)
        setup_memory(self.vault)
        self.flags=dict.fromkeys(FLAGS,False)

    def add(self, subject='Release scope agreement', **changes):
        args={'significance':'decision','context':'The user and assistant planned a release.',
              'happened':'They chose a smaller release scope.','why':'A smaller scope fit the available time.',
              'outcome':'A release plan was selected.','lesson':'Smaller releases may be easier to verify.',
              'sources':['Synthetic planning conversation'],'origin':'user','flags':self.flags,
              'skill_active':True}
        return journal(self.vault,subject,**(args|changes))

    def test_event_fields_provenance_and_related_decision(self):
        project=register_project(self.vault,'Release project',['Synthetic identity'],flags=self.flags,
                                 repository='https://example.org/team/release',skill_active=True)['record_id']
        decision=remember(self.vault,'decision','Release scope','Use a smaller release.',
                          ['Synthetic decision'],origin='user',flags=self.flags,scope='project',
                          project_id=project,skill_active=True)['record_id']
        result=self.add(scope='project',project_id=project,related_ids=[decision])
        self.assertEqual(result['status'],'created',result)
        read=inspect_experience(self.vault,result['record_id'])
        self.assertEqual(read['format'],'journal_v1')
        self.assertEqual(read['metadata']['basis'],'user-stated')
        self.assertEqual(read['event']['inferred_lesson']['basis'],'inferred')
        self.assertTrue(read['event']['inferred_lesson']['tentative'])
        self.assertIn('release plan',read['event']['observed_outcome'])
        self.assertEqual(set(read['metadata']['related_ids']),{project,decision})
        self.assertEqual(read['metadata']['sources'],['Synthetic planning conversation'])
        rows=related_experiences(self.vault,related_to=decision,project_id=project)['matches']
        self.assertEqual(rows[0]['id'],result['record_id'])
        self.assertFalse(rows[0]['is_instruction'])
        self.assertEqual(rows[0]['account_type'],'past_experience')

    def test_significance_routine_and_invented_event_exclusion(self):
        for criterion in ('decision','outcome','lesson','collaboration_feedback'):
            result=self.add(subject='Synthetic '+criterion,significance=criterion)
            self.assertEqual(result['status'],'created',result)
        before=list((self.vault/'memory/revisions').glob('*.md'))
        self.assertEqual(self.add(significance='routine')['status'],'excluded')
        for origin in ('hypothetical','source_instruction','source','inference'):
            self.assertEqual(self.add(origin=origin)['status'],'excluded')
        self.assertEqual(len(list((self.vault/'memory/revisions').glob('*.md'))),len(before))
        unknown=self.add(subject='Outcome not yet observed',outcome=None,lesson=None)
        self.assertEqual(unknown['status'],'created')
        self.assertIsNone(inspect_experience(self.vault,unknown['record_id'])['event']['observed_outcome'])
        self.assertEqual(self.add(significance='outcome',outcome=None)['status'],'unavailable')

    def test_repetition_evidence_and_changed_account_keep_identity(self):
        first=self.add()
        same=self.add()
        self.assertEqual(same['status'],'unchanged')
        self.assertEqual(same['announcement'],'')
        updated=self.add(sources=['Later synthetic confirmation'])
        self.assertEqual(updated['status'],'updated')
        self.assertEqual(updated['record_id'],first['record_id'])
        self.assertEqual(len(inspect_experience(self.vault,first['record_id'])['metadata']['sources']),2)
        changed=self.add(outcome='A different result was reported.')
        self.assertEqual(changed['status'],'needs_review')
        self.assertEqual(len(list((self.vault/'memory/revisions').glob('*.md'))),2)

    def test_scope_links_and_path_exclusions(self):
        one=register_project(self.vault,'One project',['Synthetic identity'],flags=self.flags,
                             repository='https://example.org/team/one',skill_active=True)['record_id']
        two=register_project(self.vault,'Two project',['Synthetic identity'],flags=self.flags,
                             repository='https://example.org/team/two',skill_active=True)['record_id']
        decision=remember(self.vault,'decision','Queue choice','Use bounded retries.',['Synthetic choice'],
                          flags=self.flags,origin='user',scope='project',project_id=two,skill_active=True)['record_id']
        self.assertEqual(self.add(scope='project',project_id=one,related_ids=[decision])['status'],'needs_review')
        self.assertEqual(self.add(related_ids=[decision])['status'],'needs_review')
        self.assertEqual(self.add(related_ids=['00000000-0000-4000-8000-000000000001'])['status'],'needs_review')
        for key in ('context','happened','why','outcome','lesson'):
            result=self.add(**{key:'/home/test/private-project'})
            self.assertEqual(result['status'],'unavailable',result)
            self.assertNotIn('/home/test',json.dumps(result))
        self.assertEqual(self.add(context='x'*401)['status'],'unavailable')

    def test_policy_sensitive_lessons_and_failed_write_announcements(self):
        self.assertEqual(self.add(skill_active=False)['status'],'excluded')
        set_capture(self.vault,'paused')
        self.assertEqual(self.add()['status'],'paused')
        set_capture(self.vault,'active')
        policy=json.loads((self.vault/POLICY).read_text())
        policy['boundaries']['inferences']='exclude'
        (self.vault/POLICY).write_text(json.dumps(policy))
        self.assertEqual(self.add()['status'],'excluded')
        with patch('memory_capture.write_record',return_value={'status':'failed','may_have_written':True}):
            result=self.add(lesson=None)
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['may_have_written'])
        self.assertEqual(result['announcement'],'')
        sensitive=self.flags|{'sensitive':True}
        self.assertEqual(self.add(lesson=None,flags=sensitive)['status'],'excluded')
        self.assertEqual(self.add(lesson=None,flags=sensitive,retain_sensitive=True)['status'],'created')

    def test_legacy_inspection_and_standalone_module(self):
        fixture=json.loads((ROOT/'tests/fixtures/memory-contract.json').read_text())['base']
        legacy=write_record(self.vault,fixture|{'kind':'experience'},'Context: a synthetic shared event.\n')
        read=inspect_experience(self.vault,fixture['id'])
        self.assertEqual(read['format'],'markdown')
        self.assertFalse(read['is_instruction'])
        self.assertEqual(inspect_experience(self.vault,'00000000-0000-4000-8000-000000000002')['status'],'not_found')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            run(ROOT/'install.py','--target','repo','--repo',root)
            scripts=root/'.agents/skills/adaptive-engineering/scripts'
            code='import sys;sys.path.insert(0,sys.argv[1]);from memory_journal import inspect_experience;print(inspect_experience(sys.argv[2],sys.argv[3])["format"])'
            env=dict(os.environ)
            env.pop('PYTHONPATH',None)
            result=subprocess.run([sys.executable,'-c',code,str(scripts),str(self.vault),fixture['id']],
                                  cwd=root,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),'markdown')


if __name__=='__main__':
    unittest.main()
