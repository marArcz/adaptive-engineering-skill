"""Exact duplicate maintenance retains history, relationships and tentative basis."""
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
from memory_consolidation import consolidate, plan_consolidation
from memory_journal import _event, journal
from memory_operations import inspect_record, register_project
from memory_search import memory_snapshot, search_memory
from memory_setup import setup_memory, set_capture
from memory_store import write_record, read_record, _publish
from memory_summaries import build_summaries
from test_tools import ROOT, run


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault=Path(self.temp.name)
        setup_memory(self.vault)
        self.base=json.loads((ROOT/'tests/fixtures/memory-contract.json').read_text())['base']
        self.flags=dict.fromkeys(FLAGS,False)

    def add(self, body='A useful fact.\n', **fields):
        data=self.base|{'id':str(uuid.uuid4()),'title':'Fact: useful context'}|fields
        result=write_record(self.vault,data,body)
        self.assertEqual(result['status'],'created',result)
        return data

    def run_merge(self, **options):
        return consolidate(self.vault,flags=self.flags,skill_active=True,**options)

    def test_true_duplicates_preserve_sources_files_and_idempotence(self):
        one=self.add(id='00000000-0000-4000-8000-000000000001',sources=['Synthetic source one'])
        two=self.add(id='00000000-0000-4000-8000-000000000002',sources=['Synthetic source two'])
        before={p:p.read_bytes() for p in (self.vault/'memory/revisions').glob('*.md')}
        plan=plan_consolidation(self.vault)
        self.assertEqual(len(plan['groups']),1)
        result=self.run_merge()
        self.assertEqual(result['status'],'updated',result)
        self.assertEqual(result['groups_consolidated'],1)
        self.assertTrue(result['announcement'])
        current=inspect_record(self.vault,one['id'])
        self.assertEqual(current['metadata']['sources'],['Synthetic source one','Synthetic source two'])
        alias=inspect_record(self.vault,two['id'])
        self.assertEqual(alias['canonical_id'],one['id'])
        self.assertEqual(alias['requested_id'],two['id'])
        self.assertEqual(read_record(self.vault,two['id'])['metadata']['id'],one['id'])
        self.assertEqual(read_record(self.vault,two['id'],history=True)['metadata']['id'],two['id'])
        self.assertEqual(len(search_memory(self.vault,'useful')['matches']),1)
        self.assertEqual(search_memory(self.vault,record_id=two['id'])['matches'][0]['id'],one['id'])
        for path,raw in before.items():
            self.assertEqual(path.read_bytes(),raw)
        after={p:p.read_bytes() for p in (self.vault/'memory/revisions').glob('*.md')}
        repeat=self.run_merge()
        self.assertEqual(repeat['status'],'unchanged')
        self.assertEqual(repeat['announcement'],'')
        self.assertEqual(after,{p:p.read_bytes() for p in (self.vault/'memory/revisions').glob('*.md')})

    def test_keywords_different_outcomes_and_mixed_basis_not_merged(self):
        self.add(body='The release succeeded.',title='Experience: first release',kind='experience')
        self.add(body='The release was postponed.',title='Experience: second release',kind='experience')
        self.add(body='Tentative statement.',title='Fact: tentative statement',basis='inferred')
        self.add(body='Tentative statement.',title='Fact: tentative statement',basis='user-stated')
        self.add(body='Conflicting value one.',title='Fact: conflicting')
        self.add(body='Conflicting value two.',title='Fact: conflicting')
        plan=plan_consolidation(self.vault)
        self.assertEqual(plan['groups'],[])
        result=self.run_merge()
        self.assertEqual(result['status'],'unchanged')
        self.assertGreater(result['conflicted_records_skipped'],0)
        self.assertEqual(len(list((self.vault/'memory/revisions').glob('*.md'))),6)

    def test_later_merge_preserves_aliases_without_retargeting_changed_meaning(self):
        from memory_corrections import correct
        one=self.add(id='00000000-0000-4000-8000-000000000002',sources=['Source one'])
        two=self.add(id='00000000-0000-4000-8000-000000000003',sources=['Source two'])
        self.assertEqual(self.run_merge()['status'],'updated')
        newer=self.add(id='00000000-0000-4000-8000-000000000001',sources=['Source three'])
        self.assertEqual(self.run_merge()['status'],'updated')
        for key in (one['id'],two['id']):
            self.assertEqual(inspect_record(self.vault,key)['canonical_id'],newer['id'])
        self.assertEqual(set(inspect_record(self.vault,newer['id'])['metadata']['sources']),
                         {'Source one','Source two','Source three'})
        current=inspect_record(self.vault,newer['id'])
        changed=correct(self.vault,[newer['id']],'A different current value.',['Explicit correction'],
                        expected_tokens={newer['id']:current['token']},scope='general',origin='user',
                        flags=self.flags,clear=True,skill_active=True)
        self.assertEqual(changed['status'],'created',changed)
        self.assertEqual(memory_snapshot(self.vault)['aliases'],{})
        self.assertEqual(inspect_record(self.vault,two['id'])['status'],'not_current')
        self.assertEqual(read_record(self.vault,two['id'],history=True)['body'],'A useful fact.\n')
        self.assertEqual(len(search_memory(self.vault,'useful')['matches']),1)

    def test_project_isolation_and_bounded_groups(self):
        projects=[]
        for name in ('one','two'):
            project=register_project(self.vault,name,['Synthetic identity'],flags=self.flags,
                repository='https://example.org/team/'+name,skill_active=True)['record_id']
            projects.append(project)
            for _ in range(2):
                self.add(scope='project',project_id=project)
        result=self.run_merge(scope='project',project_id=projects[0])
        self.assertEqual(result['groups_consolidated'],1,result)
        self.assertEqual(len(search_memory(self.vault,'useful',scope='project',project_id=projects[1])['matches']),2)
        for title in ('Fact: general one','Fact: general two'):
            self.add(title=title)
            self.add(title=title)
        first=self.run_merge(max_groups=1)
        self.assertTrue(first['truncated'])
        self.assertEqual(first['groups_consolidated'],1)
        self.assertEqual(self.run_merge(max_groups=1)['groups_consolidated'],1)
        self.assertEqual(self.run_merge(max_groups=1)['status'],'unchanged')

    def test_old_experiences_and_inferred_relationships_survive(self):
        event=_event('collaboration_feedback','An old collaboration.','Questions clarified planning.',
                     'Useful collaboration feedback.','A plan was chosen.','Focused questions may help.')
        body=json.dumps(event,ensure_ascii=False,indent=2)+'\n'
        one=self.add(body,id='00000000-0000-4000-8000-000000000001',kind='experience',title='Experience: first feedback',
                     sources=['Old feedback source one'],created_at='1990-01-01T00:00:00Z',updated_at='1990-01-01T00:00:00Z')
        two=self.add(body,id='00000000-0000-4000-8000-000000000002',kind='experience',title=one['title'],sources=['Old feedback source two'])
        other=journal(self.vault,'Second feedback',significance='collaboration_feedback',context='A later collaboration.',
                      happened='Questions clarified deployment.',why='Helpful feedback.',outcome='A next step was agreed.',
                      lesson='Focused questions may help.',sources=['Distinct feedback source'],origin='user',flags=self.flags,skill_active=True)['record_id']
        inferred=self.add('Focused questions may help.',kind='assistant_identity',title='Working style',basis='inferred',related_ids=[two['id'],other])
        historical=self.add('A meaningful old outcome.',kind='experience',title='Experience: very old distinct event',
                            created_at='1980-01-01T00:00:00Z',updated_at='1980-01-01T00:00:00Z')
        self.assertIn(inferred['id'],build_summaries(self.vault)['source_ids'])
        result=self.run_merge()
        self.assertEqual(result['status'],'updated',result)
        self.assertIn(inferred['id'],build_summaries(self.vault)['source_ids'])
        self.assertEqual(inspect_record(self.vault,inferred['id'])['metadata']['basis'],'inferred')
        self.assertEqual(inspect_record(self.vault,historical['id'])['body'],'A meaningful old outcome.')
        linked=search_memory(self.vault,related_to=one['id'])['matches']
        self.assertIn(inferred['id'],{r['id'] for r in linked})
        self.assertIn(one['id'],next(r for r in linked if r['id']==inferred['id'])['resolved_related_ids'])
        summary=build_summaries(self.vault)
        self.assertTrue(all(r['tentative'] for r in summary['items'] if r['entry_type']=='inferred_trait'))

    def test_paused_inactive_failed_and_late_edit_outcomes(self):
        self.add()
        self.add()
        self.assertEqual(consolidate(self.vault,flags=self.flags)['status'],'excluded')
        set_capture(self.vault,'paused')
        self.assertEqual(self.run_merge()['status'],'paused')
        self.assertFalse((self.vault/'memory/.capture.lock').exists())
        set_capture(self.vault,'active')
        with patch('memory_store.os.link',side_effect=PermissionError):
            failed=self.run_merge()
        self.assertEqual(failed['status'],'failed',failed)
        self.assertEqual(failed['announcement'],'')
        self.assertEqual(len(search_memory(self.vault,'useful')['matches']),2)
        group=plan_consolidation(self.vault)['groups'][0]
        old=group['record_ids'][1]
        path=next((self.vault/'memory/revisions').glob(old+'.*.md'))
        original=_publish
        def edit_then_publish(*args):
            path.write_text(path.read_text().replace('A useful fact.','A manually changed fact.'))
            return original(*args)
        with patch('memory_store._publish',side_effect=edit_then_publish):
            result=self.run_merge()
        self.assertEqual(result['status'],'conflict',result)
        self.assertEqual(result['announcement'],'')
        self.assertIn('A manually changed fact.',path.read_text())
        self.assertEqual(search_memory(self.vault,'useful')['matches'],[])

    def test_late_canonical_edit_does_not_resurface_old_duplicate(self):
        canonical=self.add(id='00000000-0000-4000-8000-000000000001')
        self.add(id='00000000-0000-4000-8000-000000000002')
        path=next((self.vault/'memory/revisions').glob(canonical['id']+'.*.md'))
        original=_publish
        def edit_then_publish(*args):
            path.write_text(path.read_text().replace('A useful fact.','A changed canonical fact.'))
            return original(*args)
        with patch('memory_store._publish',side_effect=edit_then_publish):
            result=self.run_merge()
        self.assertEqual(result['status'],'conflict',result)
        self.assertEqual(search_memory(self.vault,'useful')['matches'],[])
        self.assertIn('A changed canonical fact.',path.read_text())

    def test_different_relationships_and_incomplete_scans_skip(self):
        target_one=self.add(title='Fact: target one')
        target_two=self.add(title='Fact: target two')
        self.add(related_ids=[target_one['id']])
        self.add(related_ids=[target_two['id']])
        self.assertEqual(plan_consolidation(self.vault)['groups'],[])
        self.assertEqual(plan_consolidation(self.vault,max_notes=1)['status'],'unavailable')

    def test_version_two_correction_guards_survive_consolidation(self):
        from memory_corrections import correct
        old=self.add('Original value.')
        original=inspect_record(self.vault,old['id'])
        fixed=correct(self.vault,[old['id']],'Corrected value.',['Synthetic correction'],
                       expected_tokens={old['id']:original['token']},scope='general',origin='user',flags=self.flags,
                       clear=True,skill_active=True)
        self.assertEqual(fixed['status'],'created',fixed)
        self.add('Corrected value.',sources=['Independent duplicate source'])
        merged=self.run_merge()
        self.assertEqual(merged['status'],'updated',merged)
        canonical=merged['changes'][0]['record_id']
        current=memory_snapshot(self.vault)
        node=current['groups'][canonical][current['resolved'][canonical]['tips'][0]]
        self.assertEqual(node['dependencies'][old['id']],original['token'])
        path=next((self.vault/'memory/revisions').glob(old['id']+'.*.md'))
        path.write_text(path.read_text().replace('Original value.','A late historical edit.'))
        self.assertEqual(search_memory(self.vault,'useful')['matches'],[])

    def test_post_publication_read_failure_preserves_pending_id(self):
        self.add()
        self.add()
        import memory_consolidation as maintenance
        original=maintenance.memory_snapshot
        calls=0
        def interrupted(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==3:
                raise PermissionError('synthetic after-publication failure')
            return original(*args,**kwargs)
        with patch('memory_consolidation.memory_snapshot',side_effect=interrupted):
            result=self.run_merge()
        self.assertEqual(result['status'],'unavailable',result)
        self.assertTrue(result['may_have_written'])
        self.assertIsNotNone(result['pending_record_id'])
        self.assertEqual(result['announcement'],'')
        self.assertEqual(inspect_record(self.vault,result['pending_record_id'])['status'],'current')

    def test_standalone_maintenance_and_opaque_metadata(self):
        one=self.add()
        two=self.add()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            run(ROOT/'install.py','--target','repo','--repo',root)
            scripts=root/'.agents/skills/adaptive-engineering/scripts'
            code='import json,sys;sys.path.insert(0,sys.argv[1]);from memory_consolidation import consolidate;print(consolidate(sys.argv[2],flags=json.loads(sys.argv[3]),skill_active=True)["status"])'
            env=dict(os.environ)
            env.pop('PYTHONPATH',None)
            result=subprocess.run([sys.executable,'-c',code,str(scripts),str(self.vault),json.dumps(self.flags)],
                                  cwd=root,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),'updated')
        for label in ('one','two'):
            record=self.add(title='Fact: opaque data')
            path=next((self.vault/'memory/revisions').glob(record['id']+'.*.md'))
            path.write_text(path.read_text().replace('kind:','custom: "'+label+'"\nkind:',1))
        self.assertEqual(plan_consolidation(self.vault)['groups'],[])


if __name__=='__main__':
    unittest.main()
