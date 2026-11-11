# Portable project identity

`project_identity.py` supplies a local, standard-library API for generating,
serializing, reading, and matching project identities. It does not write to a
vault. T06 owns validated, recoverable writes, and T07/T10 will integrate
identity with retrieval and project memory. T04 owns comprehensive path
exclusion for all memory content.

Generate a random UUID v4 once per project using `new_project`. The v1 project
record stores that ID as both `id` and `project_id`, with a readable name and
optional repository identity in its JSON Markdown body. Preserve the ID when the
name changes. `serialize_project` creates a new record; it is not an update API
and must not be used to overwrite an existing record or reset its timestamps.

`repository_from_workspace` reads the Git origin from a workspace for the
current operation. Its returned value contains no workspace location. The
normalizer accepts HTTPS, SSH and SCP-style network Git remotes, strips user
credentials, normalizes the host and the `.git` suffix, and preserves repository
path case. It rejects local paths, URL query strings and fragments. It does not
contact a server, resolve redirects, or infer that different hosts, ports, or
case-sensitive paths are the same project.

`match_project` matches an unambiguous repository or an explicitly supplied
stable ID. Without a remote, supply the saved ID. Name matches are only
candidates, even when there is one; the calling skill must ask which identity
the user intends. Multiple records sharing a repository or a conflict between
an explicit ID and a matching remote are reported for clarification. No machine
or checkout directory mapping is stored. Project-scoped records use the resolved
ID; general records omit it. The API returns context to its caller but is not
yet wired into search or capture.

Real two-device continuity remains an acceptance task. Local tests use separate
temporary repositories and do not demonstrate Git synchronization.
