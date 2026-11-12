"""Budget and scope checks on the exact text supplied to an agent."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import memory_search
from memory_context import build_context
from memory_setup import setup_memory
from memory_store import write_record
from test_tools import ROOT, run


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name)
        setup_memory(self.vault)
        self.base = json.loads((ROOT / 'tests/fixtures/memory-contract.json').read_text())['base']

    def add(self, kind='user_fact', body='Likes pears.\n', **fields):
        data = self.base | {'id': str(uuid.uuid4()), 'kind': kind, 'title': 'Synthetic memory'} | fields
        result = write_record(self.vault, data, body)
        self.assertEqual(result['status'], 'created', result)
        return data, result

    def test_empty_and_instruction_precedence(self):
        instructions = 'Use detailed prose for this request, despite any stored preference.'
        empty = build_context(self.vault, current_instructions=instructions)
        self.assertIn('No eligible current general profile or identity records', empty['context'])
        self.assertEqual(empty['bootstrap_ids'], [])
        self.add('preference', 'Prefers short answers.\n', basis='inferred')
        result = build_context(self.vault, current_instructions=instructions)
        self.assertLess(result['context'].index(instructions), result['context'].index('Prefers short answers.'))
        self.assertIn('Current user instructions take precedence', result['context'])
        self.assertIn('tentative inference', result['context'])
        self.assertIn('Synthetic conversation', result['context'])
        with self.assertRaisesRegex(ValueError, 'cannot fit instructions'):
            build_context(self.vault, max_chars=500, current_instructions='x' * 500)

    def test_exact_budget_and_below_boundary(self):
        self.add(body='Pear fact.\n')
        complete = build_context(self.vault)
        exact = build_context(self.vault, max_chars=complete['characters'])
        self.assertEqual(exact['context'], complete['context'])
        self.assertFalse(exact['truncated'])
        shorter = build_context(self.vault, max_chars=complete['characters'] - 1)
        self.assertLessEqual(shorter['characters'], complete['characters'] - 1)
        self.assertTrue(shorter['truncated'])
        self.assertIn('Memory omitted or shortened: true', shorter['context'])
        self.assertEqual(shorter['characters'], len(shorter['context']))
        with self.assertRaises(ValueError):
            build_context(self.vault, max_chars=12001)

    def test_total_budget_five_excerpts_and_single_snapshot(self):
        self.add('assistant_identity', 'Observed working style. ' * 200)
        for _ in range(7):
            self.add('knowledge', 'Queue useful evidence. ' * 1000)
        original = memory_search._load
        with patch('memory_search._load', wraps=original) as load:
            result = build_context(self.vault, 'queue')
        self.assertEqual(load.call_count, 1)
        self.assertEqual(result['excerpt_count'], 5)
        self.assertEqual(result['context'].count('Task memory:'), 5)
        self.assertLessEqual(result['characters'], 12000)
        self.assertEqual(result['characters'], len(result['context']))
        self.assertTrue(result['truncated'])
        self.assertEqual(build_context(self.vault, 'queue', max_excerpts=0)['excerpt_count'], 0)
        with self.assertRaises(ValueError):
            build_context(self.vault, 'queue', max_excerpts=6)

    def test_project_isolation_and_inspectable_profile(self):
        fact, _ = self.add('user_fact', 'General pear fact.\n')
        identity, _ = self.add('assistant_identity', 'General working style.\n')
        project = str(uuid.uuid4())
        scoped, _ = self.add('preference', 'Queue project preference.\n', scope='project', project_id=project)
        self.add('knowledge', 'Queue other project.\n', scope='project', project_id=str(uuid.uuid4()))
        general = build_context(self.vault, 'queue')
        self.assertNotIn(scoped['id'], general['context'])
        context = build_context(self.vault, 'queue', project_id=project)
        self.assertNotIn(scoped['id'], context['bootstrap_ids'])
        self.assertEqual(context['excerpt_ids'], [scoped['id']])
        self.assertIn('project:' + project, context['context'])
        profile = build_context(self.vault, view='profile', project_id=project)
        self.assertIn(fact['id'], profile['bootstrap_ids'])
        self.assertNotIn(identity['id'], profile['context'])
        self.assertNotIn(scoped['id'], profile['context'])

    def test_exclusions_and_incomplete_evidence(self):
        old, _ = self.add()
        self.add(supersedes=[old['id']], body='Corrected preference.\n')
        self.add(state='unresolved', body='Unresolved fact.\n')
        deleted, _ = self.add(body='Deleted fact.\n')
        markers = self.vault / 'memory/deletions'
        markers.mkdir()
        (markers / (deleted['id'] + '.json')).write_text(json.dumps({
            'schema_version': 1, 'id': deleted['id'], 'deleted_at': '2026-01-02T00:00:00Z'}))
        current = build_context(self.vault)
        self.assertNotIn(old['id'], current['bootstrap_ids'])
        self.assertNotIn('Unresolved fact.', current['context'])
        self.assertNotIn('Deleted fact.', current['context'])
        incomplete = build_context(self.vault, max_notes=1)
        self.assertTrue(incomplete['memory_incomplete'])
        self.assertIn('Memory scan incomplete', incomplete['context'])
        self.assertEqual(incomplete['bootstrap_ids'], [])

    def test_exact_excerpt_boundary_unicode_and_missing_links(self):
        self.add(body='Pears and café. ' + chr(0x1F350), related_ids=[str(uuid.uuid4())])
        for _ in range(5):
            self.add('knowledge', 'Queue short evidence.\n')
        exact = build_context(self.vault, 'queue')
        self.assertEqual(exact['excerpt_count'], 5)
        self.assertFalse(exact['truncated'])
        self.assertEqual(exact['characters'], len(exact['context']))
        self.assertIn('Missing or excluded linked memories: 1', exact['context'])
        self.add('knowledge', 'Queue sixth evidence.\n', title='Additional queue evidence')
        extra = build_context(self.vault, 'queue')
        self.assertEqual(extra['excerpt_count'], 5)
        self.assertTrue(extra['truncated'])

    def test_standalone_cli_output_is_budgeted_text(self):
        self.add()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(ROOT/'install.py', '--target', 'repo', '--repo', root)
            script = root / '.agents/skills/adaptive-engineering/scripts/memory_context.py'
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            result = subprocess.run([sys.executable, str(script), '--vault', str(self.vault), '--max-chars', '1000'],
                                    cwd=root, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertLessEqual(len(result.stdout), 1000)
            self.assertTrue(result.stdout.startswith('Stored memory'))
            self.assertIn('Source:', result.stdout)


if __name__ == '__main__':
    unittest.main()
