"""Shared runtime and release inventory; no user configuration or vault content."""

SKILL_NAMES = ('adaptive-engineering', 'setup-vault')
RUNTIME_MODULES = (
    'memory_learning.py', 'memory_session.py', 'memory_forgetting.py', 'memory_consolidation.py',
    'memory_corrections.py', 'memory_summaries.py', 'memory_journal.py', 'memory_operations.py',
    'project_identity.py', 'memory_capture.py', 'memory_setup.py', 'memory_context.py',
    'memory_search.py', 'memory_store.py', 'memory_contract.py', 'memory_boundary.py',
)
SETUP_SCRIPTS = ('init_vault.py', 'configure.py')
IGNORE_PATTERNS = ('__pycache__', '*.pyc', '*.pyo', '.DS_Store', '.env', '.env.*', '.envrc', '.git')
BUNDLE_FILES = (*RUNTIME_MODULES, *SETUP_SCRIPTS, 'install.py', 'distribution.py',
                'package_release.py', 'run_acceptance.py', 'AGENTS.example.md', 'README.md',
                'SETUP-AND-ACCEPTANCE.md')
BUNDLE_TREES = ('.agents/skills', '.agents/plugins', '.codex-plugin', 'assets',
                'vault-template', 'docs', 'tests')
