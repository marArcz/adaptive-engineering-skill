"""Synthetic contract checks; these do not exercise production memory writes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import memory_contract as contract
from test_tools import ROOT, SCRIPTS, run

FIXTURES = Path(__file__).parent / 'fixtures'


class ContractTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((FIXTURES / 'memory-contract.json').read_text())
        self.records = []
        for item in fixture['records']:
            data = fixture['base'] | item
            body = data.pop('body')
            self.records.append((data, body))
        self.deleted = fixture['deleted']

    def test_roundtrip_and_collection(self):
        for data, body in self.records:
            with self.subTest(kind=data['kind'], id=data['id']):
                self.assertEqual(contract.parse(contract.serialize(data, body)), (data, body))
        contract.validate_collection(self.records, self.deleted)
        self.assertEqual({r[0]['kind'] for r in self.records}, contract.KINDS)

    def test_invalid_records(self):
        data, body = self.records[0]
        cases = [({'schema_version': 2}, 'schema_version'), ({'sources': []}, 'sources'),
                 ({'basis': 'approved'}, 'basis'), ({'scope': 'project'}, 'project_id'),
                 ({'updated_at': '2025-01-01T00:00:00Z'}, 'updated_at'),
                 ({'related_ids': [data['id']]}, 'related_ids'), ({'extra': 1}, 'unknown')]
        for change, error in cases:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, error):
                contract.validate(data | change, body)
        with self.assertRaisesRegex(ValueError, 'missing'):
            contract.validate({k: v for k, v in data.items() if k != 'sources'}, body)
        with self.assertRaisesRegex(ValueError, 'duplicate field'):
            contract.parse(contract.serialize(data, body).replace('kind:', 'id: "x"\nkind:', 1))
        for data, body in self.records:
            with self.subTest(kind=data['kind']), self.assertRaisesRegex(ValueError, 'sources'):
                contract.validate(data | {'sources': []}, body)
        with self.assertRaisesRegex(ValueError, 'schema_version'):
            contract.parse(contract.serialize(self.records[0][0], body).replace('schema_version: 1', 'schema_version: 2', 1))

    def test_invalid_collection_and_markers(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            contract.validate_collection(self.records + [self.records[0]], self.deleted)
        marker = self.deleted[0] | {'body': 'forgotten payload'}
        with self.assertRaisesRegex(ValueError, 'deletion marker'):
            contract.validate_collection(self.records, [marker])
        records = copy.deepcopy(self.records)
        records[0][0]['related_ids'] = [self.deleted[0]['id']]
        with self.assertRaisesRegex(ValueError, 'missing or deleted'):
            contract.validate_collection(records, self.deleted)

    def test_legacy_search_preserves_bytes_and_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            originals = {}
            for name in ('legacy-candidate.md', 'legacy-approved.md'):
                original = (FIXTURES / name).read_bytes()
                (vault / name).write_bytes(original)
                originals[name] = original
            result = json.loads(run(SCRIPTS / 'search_vault.py', '--vault', vault, '--query', 'queue', '--limit', '10').stdout)
            self.assertEqual({m['status'] for m in result['matches']}, {'candidate', 'approved'})
            self.assertEqual({name: (vault / name).read_bytes() for name in originals}, originals)


if __name__ == '__main__':
    unittest.main()
