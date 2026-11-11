"""Adversarial proposals only; no real vault reads or writes."""
import unittest

from memory_boundary import MemoryBoundaryError, validate_memory_content
import project_identity


class MemoryBoundaryTests(unittest.TestCase):
    def test_paths_in_every_position(self):
        paths = ['/home/synthetic/work/app', '/Users/synthetic/Code/app',
                 'C:\\Users\\Synthetic\\app', '\\\\server\\share\\app',
                 './src/service', '../project/main.py', 'src/service.py', 'main.py',
                 '~/projects/app', 'file:///tmp/app']
        for value in paths:
            for proposal in ({'title': value}, {'body': 'Log:\n> ' + value},
                             {'sources': ['Quoted conversation: ' + value]},
                             {'summary': {'evidence': [value]}}, {value: 'hidden in key'}):
                with self.subTest(proposal=proposal), self.assertRaises(MemoryBoundaryError) as caught:
                    validate_memory_content(proposal)
                self.assertNotIn(value, str(caught.exception))

    def test_context_and_fields(self):
        for field in ('cwd', 'project_path', 'workspaceRoot', 'device_id', 'hostname', 'location_mapping'):
            with self.subTest(field=field), self.assertRaises(MemoryBoundaryError):
                validate_memory_content({field: 'apparently harmless'})
        for value, context in [('Evidence from synthetic-host', {'device_identifiers': ['synthetic-host']}),
                               ('See Dockerfile', {'project_paths': ['Dockerfile']}),
                               ('https://example.org/%2Fhome%2Fsynthetic%2Fapp', {'project_roots': ['/home/synthetic/app']})]:
            with self.subTest(value=value), self.assertRaises(MemoryBoundaryError):
                validate_memory_content(value, **context)

    def test_safe_links_and_plain_evidence(self):
        validate_memory_content({'body': 'Improved the queue component. Evidence: user discussion. 1/2 completed.',
                                 'sources': ['https://example.org/team/repo',
                                             '[Decision](memory/projects/decision.md)',
                                             '[[memory/experiences/session.md|Session]]']})
        for value in ('[unsafe](memory/projects/../../src/main.py)',
                      '[[memory/projects/session.md|/tmp/app]]',
                      'https://user:secret@example.org/repo',
                      'https://example.org/?source=%2Ftmp%2Fapp'):
            with self.subTest(value=value), self.assertRaises(MemoryBoundaryError):
                validate_memory_content(value)

    def test_project_serializer_uses_boundary(self):
        project = project_identity.new_project('synthetic-host')
        with self.assertRaises(MemoryBoundaryError):
            project_identity.serialize_project(project, device_identifiers=['synthetic-host'])
        project = project_identity.new_project('Queue')
        self.assertIn('Queue', project_identity.serialize_project(project))


if __name__ == '__main__':
    unittest.main()
