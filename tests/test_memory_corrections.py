"""Corrections preserve history and never choose conflicting imports by date."""
import json
import os
import sys
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from memory_capture import FLAGS
from memory_context import build_context
from memory_corrections import correct, record_contradiction, correction_candidates
from memory_operations import remember, inspect_record, register_project, associate_project
from memory_search import search_memory, memory_snapshot
from memory_store import write_record, read_record, _publish
from memory_summaries import build_summaries
from test_tools import ROOT, run


class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.vault=self.root/'vault'
        self.vault.mkdir()
        from memory_setup import setup_memory
        setup_memory(self.vault)
        self.flags=dict.fromkeys(FLAGS,False)
        self.first=remember(self.vault,'preference','Response detail','Use short explanations.',
                            ['Synthetic original preference'],origin='user',flags=self.flags,skill_active=True)
        self.key=self.first['record_id']
        self.token=inspect_record(self.vault,self.key)['token']

    def change(self, body='Use detailed explanations.', **options):
        args={'expected_tokens':{self.key:self.token},'scope':'general','origin':'user',
              'flags':self.flags,'clear':True,'skill_active':True}
        return correct(self.vault,[self.key],body,['Synthetic explicit correction'],**(args|options))

    def test_clear_correction_updates_all_current_views_and_history(self):
        before={p:p.read_bytes() for p in (self.vault/'memory/revisions').glob('*.md')}
        changed=self.change()
        self.assertEqual(changed['status'],'created',changed)
        self.assertNotEqual(changed['record_id'],self.key)
        self.assertEqual(changed['announcement'],'Memory corrected.')
        self.assertEqual(inspect_record(self.vault,self.key)['status'],'not_current')
        self.assertNotIn('body',read_record(self.vault,self.key))
        self.assertEqual(read_record(self.vault,self.key,history=True)['body'],'Use short explanations.')
        new=inspect_record(self.vault,changed['record_id'])
        self.assertEqual(new['metadata']['supersedes'],[self.key])
        self.assertEqual(new['metadata']['sources'],['Synthetic explicit correction'])
        self.assertEqual(new['metadata']['basis'],'user-stated')
        for text in (build_context(self.vault,'explanations')['context'],build_summaries(self.vault)['text']):
            self.assertIn('Use detailed explanations.',text)
            self.assertNotIn('Use short explanations.',text)
        matches=search_memory(self.vault,'explanations',limit=30)['matches']
        self.assertEqual({r['id'] for r in matches},{changed['record_id']})
        history=search_memory(self.vault,'explanations',limit=30,history=True)['matches']
        old=next(r for r in history if r['id']==self.key)
        self.assertTrue(old['historical'])
        self.assertEqual(old['state'],'superseded')
        for path,raw in before.items():
            self.assertEqual(path.read_bytes(),raw)
        self.assertEqual(self.change()['status'],'unchanged')

    def test_scope_ambiguous_source_and_stale_read_rejected(self):
        self.assertEqual(self.change(scope='project',project_id=str(uuid.uuid4()))['status'],'needs_review')
        self.assertEqual(self.change(clear=False)['status'],'needs_review')
        self.assertEqual(self.change(origin='source')['status'],'needs_review')
        update=write_record(self.vault,read_record(self.vault,self.key)['metadata'],'A manual edit.',expected_token=self.token)
        self.assertEqual(update['status'],'updated')
        self.assertEqual(self.change()['trace']['reason'],'stale_correction_snapshot')
        self.assertEqual(inspect_record(self.vault,self.key)['body'],'A manual edit.')

    def test_ambiguous_contradiction_stays_unresolved_until_explicit_choice(self):
        ambiguous=record_contradiction(self.vault,[self.key],'A different response preference.',
                     ['Synthetic uncertain statement'],expected_tokens={self.key:self.token},scope='general',
                     origin='inference',flags=self.flags,skill_active=True)
        self.assertEqual(ambiguous['status'],'unresolved',ambiguous)
        self.assertEqual(ambiguous['announcement'],'')
        self.assertEqual(search_memory(self.vault,'response')['matches'],[])
        candidates=correction_candidates(self.vault,self.key)['candidates']
        self.assertEqual(len(candidates),2)
        self.assertTrue(all(not r['is_current_advice'] for r in candidates))
        tokens={r['id']:r['token'] for r in candidates}
        resolved=correct(self.vault,list(tokens),'The user explicitly chose detailed responses.',
                         ['Synthetic clarification'],expected_tokens=tokens,scope='general',origin='user',
                         flags=self.flags,clear=True,skill_active=True)
        self.assertEqual(resolved['status'],'created',resolved)
        self.assertEqual(len(search_memory(self.vault,'responses')['matches']),1)
        self.assertNotIn('A different response preference.',build_context(self.vault)['context'])

    def test_manual_edit_during_publication_preserved_as_semantic_conflict(self):
        original=_publish
        path=next((self.vault/'memory/revisions').glob(self.key+'.*.md'))
        def edit_then_publish(*args):
            path.write_text(path.read_text().replace('Use short explanations.','Manually edited source value.'))
            return original(*args)
        with patch('memory_store._publish',side_effect=edit_then_publish):
            result=self.change()
        self.assertEqual(result['status'],'conflict',result)
        self.assertEqual(result['announcement'],'')
        self.assertIn('Manually edited source value.',path.read_text())
        self.assertEqual(search_memory(self.vault,'response')['matches'],[])
        candidates=correction_candidates(self.vault,result['record_id'])['candidates']
        tokens={r['id']:r['token'] for r in candidates}
        fixed=correct(self.vault,list(tokens),'The user clarified the final preference.',
                      ['Synthetic clarification after edit'],expected_tokens=tokens,scope='general',origin='user',
                      flags=self.flags,clear=True,skill_active=True)
        self.assertEqual(fixed['status'],'created',fixed)

    def test_clean_git_merge_does_not_resolve_semantic_conflicts_by_timestamp(self):
        def git(*args):
            return subprocess.run(['git','-C',str(self.vault),*args],capture_output=True,text=True,check=True)
        git('init','-q')
        git('config','user.email','synthetic@example.invalid')
        git('config','user.name','Synthetic test')
        git('add','.')
        git('commit','-qm','base')
        branch=git('branch','--show-current').stdout.strip()
        git('checkout','-qb','other')
        current=read_record(self.vault,self.key)
        other=current['metadata']|{'id':str(uuid.uuid4()),'updated_at':'2099-01-01T00:00:00Z'}
        self.assertEqual(write_record(self.vault,other,'Use another response style.')['status'],'created')
        git('add','.')
        git('commit','-qm','other claim')
        git('checkout','-q',branch)
        (self.vault/'unrelated.txt').write_text('Independent change')
        git('add','unrelated.txt')
        git('commit','-qm','independent change')
        git('merge','other','--no-edit')
        self.assertEqual(git('diff','--name-only','--diff-filter=U').stdout,'')
        self.assertEqual(search_memory(self.vault,'response')['matches'],[])
        self.assertEqual(len(correction_candidates(self.vault,self.key)['candidates']),2)
        history=search_memory(self.vault,'response',history=True)['matches']
        self.assertTrue(all(r['historical'] and r['state']=='unresolved' for r in history))

    def test_project_rename_stable_identity_and_compatible_fields(self):
        project=register_project(self.vault,'Original project',['Synthetic identity'],flags=self.flags,
                    repository='https://example.org/team/project',skill_active=True)['record_id']
        old=inspect_record(self.vault,project)
        data=json.loads(old['body'])|{'name':'Renamed project'}
        result=correct(self.vault,[project],json.dumps(data,indent=2)+'\n',['Synthetic rename'],
                       expected_tokens={project:old['token']},scope='project',project_id=project,title='Renamed project',
                       origin='user',flags=self.flags,skill_active=True,clear=True)
        self.assertEqual(result['status'],'updated',result)
        self.assertEqual(result['record_id'],project)
        self.assertEqual(associate_project(self.vault,repository='git@example.org:team/project.git')['project_id'],project)
        self.assertNotIn('Original project',inspect_record(self.vault,project)['body'])
        path=next((self.vault/'memory/revisions').glob(self.key+'.*.md'))
        path.write_text(path.read_text().replace('kind:','custom: "preserve"\nkind:',1))
        self.token=inspect_record(self.vault,self.key)['token']
        result=self.change()
        self.assertEqual(result['status'],'created',result)
        self.assertEqual(inspect_record(self.vault,result['record_id'])['metadata']['custom'],'preserve')

    def test_corrected_feedback_invalidates_related_inferred_identity(self):
        from memory_journal import journal
        feedback=[]
        for index in (1,2):
            result=journal(self.vault,'Feedback '+str(index),significance='collaboration_feedback',
                context='Synthetic shared work.',happened='Questions helped task '+str(index),why='Useful feedback.',
                outcome='A clear next step.',lesson='Focused questions may help.',sources=['Synthetic feedback '+str(index)],
                origin='user',flags=self.flags,skill_active=True)
            self.assertEqual(result['status'],'created',result)
            feedback.append(result['record_id'])
        old=read_record(self.vault,self.key)['metadata']
        identity=old|{'id':str(uuid.uuid4()),'kind':'assistant_identity','title':'Working style',
                      'basis':'inferred','related_ids':feedback}
        self.assertEqual(write_record(self.vault,identity,'Focused questions may help.')['status'],'created')
        self.assertIn(identity['id'],build_summaries(self.vault)['source_ids'])
        first=inspect_record(self.vault,feedback[0])
        body=json.loads(first['body'])
        body['inferred_lesson']['text']='Different collaboration guidance.'
        result=correct(self.vault,[feedback[0]],json.dumps(body,indent=2)+'\n',['Synthetic corrected feedback'],
                       expected_tokens={feedback[0]:first['token']},scope='general',origin='user',flags=self.flags,
                       clear=True,skill_active=True)
        self.assertEqual(result['status'],'created',result)
        self.assertNotIn(identity['id'],build_summaries(self.vault)['source_ids'])
        self.assertEqual(search_memory(self.vault,'working',kind='assistant_identity')['matches'],[])
        self.assertEqual(inspect_record(self.vault,identity['id'])['status'],'not_current')
        self.assertEqual(inspect_record(self.vault,result['record_id'])['status'],'current')

    def test_evidence_update_uses_new_head_and_keeps_dependency_guard(self):
        changed=self.change()
        new_id=changed['record_id']
        update=remember(self.vault,'preference','Response detail','Use detailed explanations.',
                        ['A later synthetic confirmation'],origin='user',flags=self.flags,skill_active=True)
        self.assertEqual(update['status'],'updated',update)
        self.assertEqual(update['record_id'],new_id)
        snapshot=memory_snapshot(self.vault)
        latest=snapshot['groups'][new_id][snapshot['resolved'][new_id]['tips'][0]]
        self.assertEqual(latest['dependencies'][self.key],self.token)
        path=next((self.vault/'memory/revisions').glob(self.key+'.*.md'))
        path.write_text(path.read_text().replace('Use short explanations.','Edited prior statement.'))
        self.assertEqual(search_memory(self.vault,'response')['matches'],[])
        self.assertNotIn('body',read_record(self.vault,new_id))

    def test_cross_scope_supersession_cannot_hide_general_record(self):
        project=register_project(self.vault,'Other scope',['Synthetic identity'],flags=self.flags,
                    repository='https://example.org/team/other-scope',skill_active=True)['record_id']
        old=read_record(self.vault,self.key)['metadata']
        bad=old|{'id':str(uuid.uuid4()),'scope':'project','project_id':project,'supersedes':[self.key]}
        self.assertEqual(write_record(self.vault,bad,'An unrelated project preference.')['status'],'created')
        snapshot=memory_snapshot(self.vault)
        self.assertIn(bad['id'],snapshot['semantic_conflicts'])
        self.assertNotIn(self.key,snapshot['superseded'])
        self.assertEqual(inspect_record(self.vault,self.key)['status'],'current')
        self.assertIn(self.key,{r['id'] for r in search_memory(self.vault,'response')['matches']})

    def test_standalone_correction_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            run(ROOT/'install.py','--target','repo','--repo',root)
            scripts=root/'.agents/skills/adaptive-engineering/scripts'
            options={'expected_tokens':{self.key:self.token},'scope':'general','origin':'user',
                     'flags':self.flags,'clear':True,'skill_active':True}
            code='import json,sys;sys.path.insert(0,sys.argv[1]);from memory_corrections import correct;print(correct(sys.argv[2],[sys.argv[3]],"A clarified response preference.",["Synthetic standalone correction"],**json.loads(sys.argv[4]))["status"])'
            env=dict(os.environ)
            env.pop('PYTHONPATH',None)
            result=subprocess.run([sys.executable,'-c',code,str(scripts),str(self.vault),self.key,json.dumps(options)],
                                  cwd=root,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),'created')
            self.assertEqual(inspect_record(self.vault,self.key)['status'],'not_current')

    def test_post_publication_read_failure_returns_inspectable_id(self):
        original=memory_snapshot
        calls=0
        def interrupted(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==3:
                raise PermissionError('synthetic final-read failure')
            return original(*args,**kwargs)
        with patch('memory_corrections.memory_snapshot',side_effect=interrupted):
            result=self.change()
        self.assertEqual(result['status'],'unavailable',result)
        self.assertTrue(result['may_have_written'])
        self.assertNotEqual(result['record_id'],self.key)
        self.assertEqual(result['announcement'],'')
        self.assertEqual(inspect_record(self.vault,result['record_id'])['status'],'current')

    def test_failed_and_unsafe_corrections_do_not_claim_success(self):
        with patch('memory_store.os.link',side_effect=PermissionError):
            failed=self.change()
        self.assertEqual(failed['status'],'failed')
        self.assertFalse(failed['may_have_written'])
        self.assertEqual(failed['announcement'],'')
        self.assertEqual(inspect_record(self.vault,self.key)['body'],'Use short explanations.')
        self.assertEqual(self.change(body='/home/private/project')['status'],'unavailable')
        self.assertEqual(self.change(flags=self.flags|{'do_not_remember':True})['status'],'excluded')
        self.assertEqual(self.change(skill_active=False)['status'],'excluded')


if __name__=='__main__':
    unittest.main()
