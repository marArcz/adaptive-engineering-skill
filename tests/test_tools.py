"""Deterministic stdlib smoke and regression tests; no API calls."""
from __future__ import annotations
import json,subprocess,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'.agents'/'skills'/'adaptive-engineering'/'scripts'

def run(script:Path,*args:str,ok=True)->subprocess.CompletedProcess:
    result=subprocess.run([sys.executable,str(script),*map(str,args)],text=True,capture_output=True)
    if ok and result.returncode!=0:
        raise AssertionError(result.stderr)
    return result

class ToolsTests(unittest.TestCase):
    def test_inspector_detects_laravel_php_and_no_installed_version_claim(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t)
            (repo/'composer.json').write_text('{"require":{"laravel/framework":"^12.0"}}')
            (repo/'artisan').write_text('php')
            data=json.loads(run(SCRIPTS/'inspect_project.py',repo).stdout)
            self.assertEqual(data['languages'],['PHP'])
            self.assertTrue(any(x['name']=='Laravel' and x['declared_requirement']=='^12.0' for x in data['framework_hints']))
            self.assertIn('not confirmed installed versions',data['notice'])
    def test_inspector_detects_react(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t)
            (repo/'package.json').write_text('{"dependencies":{"react":"^19.0.0"}}')
            (repo/'pnpm-lock.yaml').write_text('')
            data=json.loads(run(SCRIPTS/'inspect_project.py',repo).stdout)
            self.assertIn('pnpm',data['lockfile_hints'])
            self.assertEqual(data['framework_hints'][0]['name'],'React')
    def test_finder_ignores_node_modules_and_respects_scope(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)
            (r/'src').mkdir();(r/'node_modules').mkdir()
            (r/'src'/'UserForm.tsx').write_text('export function UserForm() {}\n')
            (r/'node_modules'/'EvilForm.tsx').write_text('UserForm')
            data=json.loads(run(SCRIPTS/'find_patterns.py','--repo',r,'--scope','src','--query','UserForm').stdout)
            self.assertEqual(len(data['matches']),1)
            self.assertEqual(data['matches'][0]['path'],'src/UserForm.tsx')
            bad=run(SCRIPTS/'find_patterns.py','--repo',r,'--scope','../','--query','form',ok=False)
            self.assertNotEqual(bad.returncode,0)
    def test_vault_search_and_catalog_candidate_flag(self):
        with tempfile.TemporaryDirectory() as t:
            v=Path(t); note=v/'knowledge'/'technologies'/'laravel'/'validation.md'
            note.parent.mkdir(parents=True)
            note.write_text('---\ntitle: Laravel validation\nstatus: candidate\ntags: [laravel, validation]\n---\n# Laravel validation\n')
            (v/'references'/'github').mkdir(parents=True)
            (v/'references'/'github'/'catalog.json').write_text(json.dumps({'repositories':[{'id':'laravel-example','tags':['laravel'],'status':'candidate','url':'https://github.com/laravel/laravel'}]}))
            md=json.loads(run(SCRIPTS/'search_vault.py','--vault',v,'--query','laravel validation').stdout)
            self.assertEqual(md['matches'][0]['status'],'candidate')
            self.assertTrue(md['matches'][0]['path'].endswith('validation.md'))
            catalog=json.loads(run(SCRIPTS/'search_catalog.py','--vault',v,'--query','laravel').stdout)
            self.assertEqual(catalog['matches'][0]['status'],'candidate')
    def test_learned_candidates_searchable_but_other_research_excluded(self):
        with tempfile.TemporaryDirectory() as t:
            vault=Path(t)
            included=['research/candidates/queue-retries.md',
                      'research/candidates/python/queue-backoff.md']
            excluded=['research/drafts/queue.md', 'research/queue.md',
                      'research/candidates-old/queue.md', 'templates/queue.md',
                      '.obsidian/queue.md', 'research/candidates/.hidden/queue.md',
                      'research/candidates/node_modules/queue.md',
                      'knowledge/research/candidates/queue.md']
            for relative in included+excluded:
                note=vault/relative
                note.parent.mkdir(parents=True,exist_ok=True)
                note.write_text('---\ntitle: Queue retries\nstatus: candidate\ntags: [queue]\n---\nBounded retries.\n',encoding='utf8')
            result=json.loads(run(SCRIPTS/'search_vault.py','--vault',vault,'--query','queue','--limit',30).stdout)
            self.assertEqual({m['path'] for m in result['matches']},set(included))
            self.assertTrue(all(m['status']=='candidate' for m in result['matches']))
            self.assertEqual(result['notes_examined'],len(included))

    def test_catalog_supports_learned_entry_without_mutating_reviewed_metadata(self):
        with tempfile.TemporaryDirectory() as t:
            vault=Path(t); catalog=vault/'references'/'github'/'catalog.json'
            catalog.parent.mkdir(parents=True)
            existing={'id':'reviewed','url':'https://github.com/example/reviewed',
                      'tags':['queue'],'status':'approved','reviewed_commit':'abc123',
                      'verified_at':'2026-10-24','custom_field':'keep'}
            learned={'id':'learned','url':'https://github.com/example/learned',
                     'description':'Queue retry reference','tags':['queue'],
                     'use_for':['bounded retries'],'status':'candidate',
                     'reviewed_commit':None,'verified_at':None,
                     'important_paths':['src/retry.py'],'limitations':['Unreviewed']}
            original=json.dumps({'schema_version':1,'repositories':[existing,learned]})
            catalog.write_text(original,encoding='utf8')
            result=json.loads(run(SCRIPTS/'search_catalog.py','--vault',vault,'--query','queue').stdout)
            by_id={m['id']:m for m in result['matches']}
            self.assertEqual(by_id['learned']['status'],'candidate')
            self.assertIsNone(by_id['learned']['reviewed_commit'])
            self.assertEqual(by_id['learned']['important_paths'],['src/retry.py'])
            self.assertEqual(by_id['reviewed']['status'],'approved')
            self.assertEqual(by_id['reviewed']['reviewed_commit'],'abc123')
            self.assertEqual(catalog.read_text(encoding='utf8'),original)

    def test_vault_missing_fails_without_fabrication(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'missing'
            r=run(SCRIPTS/'search_vault.py','--vault',p,'--query','react',ok=False)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('missing',r.stderr.lower())
    def test_install_dry_run_non_destructive_and_preserve_agents(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t); (repo/'AGENTS.md').write_text('existing policy')
            run(ROOT/'install.py','--target','repo','--repo',repo,'--with-agents','--dry-run')
            self.assertFalse((repo/'.agents').exists())
            run(ROOT/'install.py','--target','repo','--repo',repo,'--with-agents')
            self.assertTrue((repo/'.agents'/'skills'/'adaptive-engineering'/'SKILL.md').is_file())
            self.assertTrue((repo/'.agents'/'skills'/'adaptive-engineering'/'references'/'learn.md').is_file())
            self.assertEqual((repo/'AGENTS.md').read_text(),'existing policy')
            repeated=run(ROOT/'install.py','--target','repo','--repo',repo,ok=False)
            self.assertNotEqual(repeated.returncode,0)
    def test_vault_initializer_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            v=Path(t)/'vault'
            run(ROOT/'init_vault.py','--path',v)
            self.assertTrue((v/'HOME.md').is_file())
            self.assertTrue((v/'references'/'github'/'catalog.json').is_file())
            out=run(ROOT/'init_vault.py','--path',v,ok=False)
            self.assertNotEqual(out.returncode,0)

if __name__=='__main__':unittest.main()
