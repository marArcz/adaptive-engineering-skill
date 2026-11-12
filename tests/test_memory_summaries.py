"""Derived profile/identity views retain live source identity, not cached beliefs."""
import json
import tempfile
import unittest
import uuid
from pathlib import Path

from memory_capture import FLAGS
from memory_context import build_context
from memory_journal import journal
from memory_operations import register_project, remember
from memory_setup import setup_memory
from memory_store import write_record, read_record
from memory_summaries import build_summaries
from test_tools import ROOT


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault=Path(self.temp.name)
        setup_memory(self.vault)
        self.flags=dict.fromkeys(FLAGS,False)
        self.base=json.loads((ROOT/'tests/fixtures/memory-contract.json').read_text())['base']

    def add(self, kind='assistant_identity', body='Ask focused questions.\n', **fields):
        data=self.base|{'id':str(uuid.uuid4()),'kind':kind}|fields
        result=write_record(self.vault,data,body)
        self.assertEqual(result['status'],'created',result)
        return data,result

    def feedback(self, title, happened, source, lesson='Focused questions may help collaboration.', **scope):
        result=journal(self.vault,title,significance='collaboration_feedback',context='Synthetic collaboration.',
                       happened=happened,why='The feedback identified a useful working style.',
                       outcome='Feedback was recorded.',lesson=lesson,sources=[source],origin='user',
                       flags=self.flags,skill_active=True,**scope)
        self.assertEqual(result['status'],'created',result)
        return result['record_id']

    def test_empty_separate_views_and_no_persisted_summary(self):
        before={p:p.read_bytes() for p in self.vault.rglob('*') if p.is_file()}
        empty=build_summaries(self.vault)
        self.assertEqual(empty['items'],[])
        self.assertFalse(empty['is_source'])
        self.assertIn('No eligible current',empty['text'])
        self.assertEqual(before,{p:p.read_bytes() for p in self.vault.rglob('*') if p.is_file()})
        user,_=self.add('user_fact','The user likes pears.\n')
        style,_=self.add()
        summary=build_summaries(self.vault)
        self.assertEqual({r['view'] for r in summary['items']},{'profile','identity'})
        self.assertEqual(summary,build_summaries(self.vault))
        self.assertEqual(summary['assistant_view'],'assistant')
        self.assertEqual(set(summary['source_ids']),{user['id'],style['id']})

    def test_direct_feedback_change_regenerates_from_current_revision(self):
        data,first=self.add()
        before=build_summaries(self.vault)
        update=write_record(self.vault,data,'Explain decisions in detail.\n',expected_token=first['record']['token'])
        self.assertEqual(update['status'],'updated')
        after=build_summaries(self.vault)
        self.assertIn('Explain decisions in detail.',after['text'])
        self.assertNotIn('Ask focused questions.',after['text'])
        self.assertEqual(before['source_ids'],after['source_ids'])
        self.assertNotEqual(before['items'][0]['source_records'][0]['digest'],after['items'][0]['source_records'][0]['digest'])

    def test_single_mistake_and_retold_feedback_are_not_traits(self):
        first=self.feedback('First incident','The assistant missed one detail.','Synthetic feedback one')
        summary=build_summaries(self.vault)
        self.assertEqual(summary['items'][0]['entry_type'],'feedback_not_trait')
        self.assertNotIn('Focused questions may help',summary['text'])
        second=self.feedback('Retold incident','The assistant missed one detail.','Synthetic retelling')
        inferred,_=self.add(basis='inferred',related_ids=[first,second])
        summary=build_summaries(self.vault)
        self.assertIn(inferred['id'],summary['excluded_identity_ids'])
        self.assertFalse(any(r['entry_type']=='inferred_trait' for r in summary['items']))
        context=build_context(self.vault,'focused')
        self.assertNotIn(inferred['id'],context['bootstrap_ids']+context['excerpt_ids'])

    def test_independent_feedback_infers_tentatively_without_promotion(self):
        first=self.feedback('First feedback','Focused questions clarified the release.','Synthetic conversation one')
        second=self.feedback('Second feedback','Focused questions clarified deployment.','Synthetic conversation two')
        summary=build_summaries(self.vault)
        traits=[r for r in summary['items'] if r['entry_type']=='inferred_trait']
        self.assertEqual(len(traits),1)
        self.assertEqual(traits[0]['basis'],'inferred')
        self.assertTrue(traits[0]['tentative'])
        self.assertEqual({p['id'] for p in traits[0]['source_records']},{first,second})
        explicit,_=self.add(basis='inferred',related_ids=[first,second])
        linked=build_summaries(self.vault)
        self.assertIn(explicit['id'],linked['source_ids'])
        self.assertNotIn(explicit['id'],linked['excluded_identity_ids'])
        self.assertTrue(next(r for r in linked['items'] if r['source_records'][0]['id']==explicit['id'])['tentative'])
        # A third source adds support; it cannot turn inference into confirmation.
        self.feedback('Third feedback','Focused questions clarified the queue.','Synthetic conversation three')
        again=build_summaries(self.vault)
        self.assertTrue(all(r['basis']=='inferred' for r in again['items'] if r['entry_type']=='inferred_trait'))

    def test_scoped_preferences_and_feedback_never_become_global(self):
        project=register_project(self.vault,'Synthetic project',['Synthetic identity'],flags=self.flags,
                                 repository='https://example.org/team/project',skill_active=True)['record_id']
        pref=remember(self.vault,'preference','Project response style','Use short explanations here.',
                       ['Synthetic project request'],origin='user',flags=self.flags,skill_active=True,
                       scope='project',project_id=project)['record_id']
        self.feedback('Project feedback one','The project explanation helped.','Project source one',scope='project',project_id=project)
        self.feedback('Project feedback two','The project review helped.','Project source two',scope='project',project_id=project)
        self.assertNotIn(pref,build_summaries(self.vault)['source_ids'])
        scoped=build_summaries(self.vault,project_id=project)
        self.assertIn(pref,scoped['source_ids'])
        self.assertTrue(all(r['view']=='project_adjustment' for r in scoped['items']))
        self.assertEqual(scoped['assistant_view'],'assistant')
        self.assertNotIn(pref,build_context(self.vault,project_id=project)['bootstrap_ids'])

    def test_deletion_and_supersession_invalidate_derived_support(self):
        first=self.feedback('Feedback one','Questions helped planning.','Synthetic feedback one')
        second=self.feedback('Feedback two','Questions helped review.','Synthetic feedback two')
        self.assertTrue(any(r['entry_type']=='inferred_trait' for r in build_summaries(self.vault)['items']))
        markers=self.vault/'memory/deletions'
        markers.mkdir()
        (markers/(first+'.json')).write_text(json.dumps({'schema_version':1,'id':first,'deleted_at':'2026-01-02T00:00:00Z'}))
        after=build_summaries(self.vault)
        self.assertNotIn(first,after['source_ids'])
        self.assertFalse(any(r['entry_type']=='inferred_trait' for r in after['items']))
        old,_=self.add('preference','Old response preference.\n')
        self.add('preference','New response preference.\n',supersedes=[old['id']])
        self.assertNotIn('Old response preference.',build_summaries(self.vault)['text'])

    def test_summary_and_context_budgets_with_current_instructions(self):
        for _ in range(10):
            self.add('user_fact','Synthetic user fact. '*100)
        self.add(body='Recorded working style. '*100)
        summary=build_summaries(self.vault)
        self.assertLessEqual(len(summary['text']),3000)
        self.assertEqual(summary['characters'],len(summary['text']))
        self.assertTrue(summary['truncated'])
        self.assertTrue(any(r['view']=='identity' for r in summary['items']))
        tiny=build_summaries(self.vault,max_chars=1)
        self.assertEqual(tiny['text'],'')
        self.assertTrue(tiny['truncated'])
        with self.assertRaises(ValueError):
            build_summaries(self.vault,max_chars=3001)
        instruction='Use current instructions over stored style.'
        context=build_context(self.vault,current_instructions=instruction)
        self.assertLessEqual(context['characters'],12000)
        self.assertLess(context['context'].index(instruction),context['context'].index('Recorded working style.'))


if __name__=='__main__':
    unittest.main()
