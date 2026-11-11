"""Reference reader for the T01 Markdown contract; no vault writes."""
import datetime
import json
import uuid
from memory_boundary import validate_memory_content

FIELDS = {'schema_version', 'id', 'kind', 'title', 'scope', 'project_id',
          'basis', 'state', 'created_at', 'updated_at', 'sources',
          'related_ids', 'supersedes'}
REQUIRED = FIELDS - {'project_id'}
KINDS = {'user_fact', 'preference', 'assistant_identity', 'experience', 'project', 'knowledge'}


def _uuid(value, field):
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f'{field}: expected lowercase UUID v4') from None
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError(f'{field}: expected lowercase UUID v4')


def _timestamp(value, field):
    try:
        parsed = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
        if parsed.strftime('%Y-%m-%dT%H:%M:%SZ') != value:
            raise ValueError
        return parsed
    except (ValueError, TypeError):
        raise ValueError(f'{field}: expected UTC YYYY-MM-DDTHH:MM:SSZ') from None


def parse(text):
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        raise ValueError('frontmatter: missing delimiters')
    header, body = text[4:].split('\n---\n', 1)
    data = {}
    for line in header.splitlines():
        key, sep, value = line.partition(':')
        if not sep or not key or key.strip() != key:
            raise ValueError('frontmatter: invalid field')
        if key in data:
            raise ValueError(f'{key}: duplicate field')
        try:
            data[key] = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f'{key}: invalid JSON') from exc
    validate(data, body)
    return data, body


def validate(data, body):
    missing, extra = REQUIRED - data.keys(), data.keys() - FIELDS
    if missing or extra:
        raise ValueError(f'fields: missing {sorted(missing)}, unknown {sorted(extra)}')
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('schema_version: unsupported version')
    _uuid(data['id'], 'id')
    for field, allowed in [('kind', KINDS), ('scope', {'general', 'project'}),
                           ('basis', {'user-stated', 'inferred', 'source-supported'}),
                           ('state', {'current', 'superseded', 'unresolved'})]:
        if not isinstance(data[field], str) or data[field] not in allowed:
            raise ValueError(f'{field}: unsupported value')
    if not isinstance(data['title'], str) or not data['title'].strip():
        raise ValueError('title: expected nonempty string')
    if not isinstance(body, str) or not body.strip():
        raise ValueError('body: expected nonempty Markdown')
    if data['scope'] == 'project':
        _uuid(data.get('project_id'), 'project_id')
    elif 'project_id' in data:
        raise ValueError('project_id: not allowed in general scope')
    if data['kind'] == 'project' and (data['scope'] != 'project' or data['project_id'] != data['id']):
        raise ValueError('project_id: project record must identify itself')
    if _timestamp(data['updated_at'], 'updated_at') < _timestamp(data['created_at'], 'created_at'):
        raise ValueError('updated_at: precedes created_at')
    sources = data['sources']
    if not isinstance(sources, list) or not sources or any(not isinstance(s, str) or not s.strip() for s in sources):
        raise ValueError('sources: expected nonempty array of nonempty strings')
    for field in ('related_ids', 'supersedes'):
        values = data[field]
        if not isinstance(values, list):
            raise ValueError(f'{field}: expected array')
        for value in values:
            _uuid(value, field)
        if len(values) != len(set(values)) or data['id'] in values:
            raise ValueError(f'{field}: duplicate or self reference')
    validate_memory_content({'metadata': data, 'body': body})


def serialize(data, body):
    validate(data, body)
    return '---\n' + '\n'.join(f'{key}: {json.dumps(value, ensure_ascii=False)}' for key, value in data.items()) + '\n---\n' + body


def validate_collection(records, deleted):
    ids = set()
    for data, body in records:
        validate(data, body)
        if data['id'] in ids:
            raise ValueError(f"id: duplicate {data['id']}")
        ids.add(data['id'])
    deleted_ids = set()
    for marker in deleted:
        if set(marker) != {'schema_version', 'id', 'deleted_at'}:
            raise ValueError('deletion marker: expected only schema_version, id, deleted_at')
        if type(marker['schema_version']) is not int or marker['schema_version'] != 1:
            raise ValueError('deletion marker: unsupported schema_version')
        _uuid(marker['id'], 'id')
        _timestamp(marker['deleted_at'], 'deleted_at')
        if marker['id'] in deleted_ids or marker['id'] in ids:
            raise ValueError('deletion marker: duplicate or active id')
        deleted_ids.add(marker['id'])
    for data, _ in records:
        for ref in data['related_ids'] + data['supersedes']:
            if ref not in ids:
                raise ValueError(f'reference: missing or deleted id {ref}')
