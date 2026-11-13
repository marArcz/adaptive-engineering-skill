#!/usr/bin/env python3
"""Run synthetic deterministic checks and report their acceptance evidence."""
import argparse
import hashlib
import io
import json
import platform
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MATRIX = ROOT / 'tests/acceptance-matrix-v1.json'


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


def validate_matrix(matrix, available):
    """Reject stale references before executing the suite."""
    if matrix.get('schema_version') != 1 or matrix.get('fixture_version') != 1:
        raise ValueError('unsupported acceptance matrix or fixture version')
    checks = matrix['checks']
    if [check['id'] for check in checks] != [f'A{i:02}' for i in range(1, 15)]:
        raise ValueError('matrix must list A01 through A14 once, in order')
    for check in checks:
        if not check['scope'] or not check['follow_up'] or not check['requirements']:
            raise ValueError(f"incomplete scope or limitations for {check['id']}")
        if not set(check['requirements']) <= {f'R{i:02}' for i in range(1, 11)}:
            raise ValueError(f"unknown requirement for {check['id']}")
        if check['id'] != 'A11' and not check['tests']:
            raise ValueError(f"missing deterministic evidence for {check['id']}")
        if check['id'] == 'A11' and check['tests']:
            raise ValueError('A11 actual-device acceptance cannot be established by this suite')
        missing = set(check['tests']) - set(available)
        if missing:
            raise ValueError(f"unknown tests for {check['id']}: {sorted(missing)}")


class EvidenceResult(unittest.TextTestResult):
    """Record parent outcomes too: a failing subtest must never count as a pass."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes.setdefault(test.id(), 'passed')

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = 'failed'

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = 'error'

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        parent = getattr(test, 'test_case', test)
        if self.outcomes.get(parent.id()) not in ('failed', 'error'):
            self.outcomes[parent.id()] = 'skipped'

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.outcomes[test.id()] = 'expected_failure'

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.outcomes[test.id()] = 'unexpected_success'

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.outcomes[test.id()] = 'failed'


def run_suite(suite):
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=EvidenceResult).run(suite)
    return result, stream.getvalue()


def check_evidence(matrix, outcomes):
    checks = []
    for check in matrix['checks']:
        evidence = {name: outcomes.get(name, 'not_run') for name in check['tests']}
        status = ('deferred' if not evidence else
                  'passed' if all(value == 'passed' for value in evidence.values()) else 'incomplete')
        checks.append({**check, 'deterministic_status': status, 'test_outcomes': evidence,
                       'full_acceptance': 'not_claimed'})
    return checks


def build_report(matrix, result, log):
    checks = check_evidence(matrix, result.outcomes)
    fingerprints = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted((ROOT / 'tests/fixtures').rglob('*')) if path.is_file()}
    fingerprints[str(MATRIX.relative_to(ROOT))] = hashlib.sha256(MATRIX.read_bytes()).hexdigest()
    return {'schema_version': 1, 'source_spec': matrix['source_spec'],
            'matrix_version': matrix['schema_version'],
            'fixture_version': matrix['fixture_version'], 'python': platform.python_version(),
            'platform': platform.system(), 'fixture_sha256': fingerprints,
            'tests_run': result.testsRun, 'suite_successful': result.wasSuccessful(),
            'test_outcomes': result.outcomes, 'checks': checks, 'test_log': log,
            'full_acceptance': 'not_claimed',
            'successful': result.wasSuccessful() and all(
                check['deterministic_status'] != 'incomplete' for check in checks)}


def markdown_report(report):
    lines = ['# Deterministic acceptance evidence v1', '',
             f"Python {report['python']} on {report['platform']}; fixture v{report['fixture_version']}.",
             f"Ran {report['tests_run']} tests; suite successful: {report['suite_successful']}.", '',
             'This reports local deterministic evidence only. Full product acceptance is not claimed.', '',
             '| Check | Requirements | Deterministic evidence | Remaining validation |',
             '| --- | --- | --- | --- |']
    for check in report['checks']:
        lines.append(f"| {check['id']} | {', '.join(check['requirements'])} | "
                     f"{check['deterministic_status']} ({len(check['tests'])} tests) | {check['follow_up']} |")
    lines.extend(['', 'See the JSON report for exact test IDs, outcomes, fixture hashes and the test log.', ''])
    return '\n'.join(lines)


def write_new(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as output:
        output.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new JSON report path; never overwrites a report')
    parser.add_argument('--markdown', type=Path, help='optional new Markdown report path')
    args = parser.parse_args()
    try:
        matrix = json.loads(MATRIX.read_text())
        suite = unittest.TestLoader().discover(str(ROOT / 'tests'))
        validate_matrix(matrix, set(test_ids(suite)))
        result, log = run_suite(suite)
        report = build_report(matrix, result, log)
        if args.output:
            write_new(args.output, json.dumps(report, indent=2) + '\n')
        if args.markdown:
            write_new(args.markdown, markdown_report(report))
        print(log, file=sys.stderr, end='')
        passed = sum(check['deterministic_status'] == 'passed' for check in report['checks'])
        print(f"{report['tests_run']} tests; {passed}/14 checks have passing deterministic evidence. "
              'A11 requires real devices. Full acceptance is not claimed.')
        return 0 if report['successful'] else 1
    except (OSError, ValueError, KeyError) as error:
        print(f'Acceptance report failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
