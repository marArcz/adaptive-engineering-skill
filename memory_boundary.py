"""Reject location-bearing proposed memory; never log, rewrite, or save input."""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit


class MemoryBoundaryError(ValueError):
    """A proposal must be re-summarized before persistence."""


_FIELDS = re.compile(r'(?:^|_)(?:paths?|cwd|directories|directory|dirs?|roots?|hostname|host_name|host|device|machine|workspace|checkout|location)(?:_|$)', re.I)
_URL = re.compile(r'https?://[^\s<>"\x27`\]\)]+', re.I)
_WIKI = re.compile(r'\[\[([^\]\n]+)\]\]')
_MARKDOWN = re.compile(r'\[([^\]\n]*)\]\(([^)\n]+)\)')
_ABSOLUTE = re.compile(r'(?:file://|[A-Za-z]:[/\\]|\\\\|(?<![\w/])(?:/|~/|\./|\.\./)[\w.~%-])', re.I)
_RELATIVE = re.compile(r'(?<!\w)[\w.@~-]+[/\\][\w.@~-]+')
_FILE = re.compile(r'\b[\w.-]+\.(?:py|js|ts|tsx|jsx|php|rb|go|rs|java|swift|sh|ps1|md|json|ya?ml|toml|ini|env|txt|log)\b', re.I)


def _reject(reason):
    raise MemoryBoundaryError(f'Memory proposal rejected ({reason}); summarize without project locations or device details.')


def _vault_link(target):
    target = target.split('|', 1)[0].split('#', 1)[0]
    parts = target.split('/')
    return (len(parts) >= 3
            and ((parts[0] == 'memory' and parts[1] in {'profile', 'identity', 'experiences', 'projects', 'knowledge'})
                 or parts[:2] == ['research', 'candidates'])
            and all(p and p not in {'.', '..'} for p in parts)
            and '\\' not in target and '%' not in target and target.endswith('.md'))


def validate_memory_content(value, *, project_roots=(), device_identifiers=(), project_paths=()):
    """Check JSON-compatible proposals recursively, including keys and provenance.

    Runtime roots, identifiers and known relative paths are ephemeral inputs.
    Passing this check is necessary, not proof of semantic capture safety.
    """
    known = tuple(str(v).replace('\\', '/').casefold() for v in
                  (*project_roots, *device_identifiers, *project_paths) if str(v))

    def check_text(text):
        decoded = unquote(text)
        normalized = decoded.replace('\\', '/').casefold()
        if any(item in normalized for item in known):
            _reject('known runtime location or identifier')

        def safe_url(match):
            try:
                url = urlsplit(match.group())
                if not url.hostname or url.username is not None or url.password is not None:
                    _reject('unsafe source URL')
                # Query/fragment may contain local evidence or identifiers.
                if url.query:
                    check_text(url.query)
                if url.fragment:
                    check_text(url.fragment)
            except ValueError:
                _reject('unsafe source URL')
            return 'URL'

        text = _URL.sub(safe_url, decoded)
        text = _WIKI.sub(lambda m: m[1].split('|', 1)[1] if _vault_link(m[1]) and '|' in m[1]
                         else 'VAULT_LINK' if _vault_link(m[1]) else m[0], text)
        text = _MARKDOWN.sub(lambda m: m[1] if _vault_link(m[2]) else m[0], text)
        text = re.sub(r'(?<![\w/])\d+(?:/\d+)+(?![\w/])', 'NUMBER', text)
        if _ABSOLUTE.search(text) or _RELATIVE.search(text) or _FILE.search(text):
            _reject('filesystem path')

    def visit(item):
        if isinstance(item, str):
            check_text(item)
        elif isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    _reject('non-string metadata key')
                normalized_key = re.sub(r'([a-z])([A-Z])', r'\1_\2', key).replace('-', '_')
                if _FIELDS.search(normalized_key):
                    _reject('location-bearing metadata field')
                check_text(key)
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)
        elif item is not None and not isinstance(item, (bool, int, float)):
            _reject('unsupported content type')

    visit(value)
