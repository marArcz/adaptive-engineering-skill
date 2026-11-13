"""Evidence must fail closed for stale mappings and unsuccessful tests."""
import copy
import json
import unittest

from run_acceptance import MATRIX, check_evidence, run_suite, test_ids, validate_matrix


class ReportTests(unittest.TestCase):
    def test_bad_reference_or_missing_check_cannot_produce_evidence(self):
        matrix = json.loads(MATRIX.read_text())
        names = {name for check in matrix['checks'] for name in check['tests']}
        validate_matrix(matrix, names)
        broken = copy.deepcopy(matrix)
        broken['checks'][0]['tests'].append('missing.Test.test_missing')
        with self.assertRaisesRegex(ValueError, 'unknown tests'):
            validate_matrix(broken, names)
        broken = copy.deepcopy(matrix)
        broken['checks'].pop()
        with self.assertRaisesRegex(ValueError, 'A01 through A14'):
            validate_matrix(broken, names)

    def test_subtest_failure_skip_and_unexecuted_test_never_count_as_passed(self):
        class Synthetic(unittest.TestCase):
            def test_pass(self):
                self.assertTrue(True)

            def test_subtest_failure(self):
                with self.subTest(value='synthetic'):
                    self.fail('synthetic failure')

            @unittest.skip('synthetic unavailable capability')
            def test_skip(self):
                pass

            @unittest.expectedFailure
            def test_expected_failure(self):
                self.fail('synthetic expected failure')

            def test_skipped_subtest(self):
                with self.subTest(value='synthetic'):
                    self.skipTest('synthetic missing capability')

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Synthetic)
        ids = list(test_ids(suite))
        result, _ = run_suite(suite)
        self.assertFalse(result.wasSuccessful())
        matrix = {'checks': [{'id': name, 'tests': [name]} for name in ids] +
                  [{'id': 'unexecuted', 'tests': ['not.run']}, {'id': 'device', 'tests': []}]}
        evidence = {check['id']: check['deterministic_status']
                    for check in check_evidence(matrix, result.outcomes)}
        for name in ids:
            self.assertEqual(evidence[name], 'passed' if name.endswith('.test_pass') else 'incomplete')
        self.assertEqual(evidence['unexecuted'], 'incomplete')
        self.assertEqual(evidence['device'], 'deferred')


if __name__ == '__main__':
    unittest.main()
