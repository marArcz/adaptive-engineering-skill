# Scoped memory search

Use the bundled `scripts/search_vault.py`. Default mode searches legacy candidate/approved engineering notes. `--mode memory` searches managed portable memory; `--mode all` combines both under one result limit. Memory basis and lifecycle are independent of legacy approval status. Memory filters apply only to the memory portion of combined searches. Combined mode requires a text query; exact-ID and relationship-only lookup use memory mode.

```sh
python3 scripts/search_vault.py --query queue --mode memory --limit 5
python3 scripts/search_vault.py --query queue --mode all --limit 5
python3 scripts/search_vault.py --query queue --mode memory --project-id PROJECT_UUID
python3 scripts/search_vault.py --mode memory --record-id MEMORY_UUID
python3 scripts/search_vault.py --mode memory --related-to MEMORY_UUID
python3 scripts/search_vault.py --query queue --mode memory --history
```

Resolve the vault using `--vault`, the existing environment override or saved configuration. UUID placeholders above must be replaced with actual stable IDs. No workspace lookup, location registry, source repository scan, embeddings or network service is required. The root `memory_search.search_memory` API offers the same filters.

Default text recall includes general memories. A `--project-id` adds that project's memories to general recall; `--scope project` restricts to the specified project, `--scope general` restricts to general records, and `--scope all` intentionally permits cross-project recall. Exact record lookup without a project filter may retrieve that ID in any project. `--kind` accepts any v1 memory kind. `--related-to` finds incoming related_ids and supersedes references; it does not recursively expand the graph. Missing, invalid, conflicted or deleted reference targets appear only as missing IDs, never as source evidence.

Memory search uses T06's shared graph resolver and validates complete records before matching. Current recall excludes superseded lifecycle records, unresolved lifecycle records, targets of valid resolved supersession links, invalid records, conflict-marked files, graph conflicts and forgotten IDs. `--history` includes older revisions and superseded/unresolved lifecycle records as explicitly historical; it still excludes graph-conflicted records, invalid records and forgotten IDs. Inferred records are always marked tentative. Result pointers contain stable record/revision IDs, scope, basis, state, vault-relative source file, provenance and relationships. They contain no full body. Long pointer fields are clipped with pointer_truncated set.

The read-side deletion format is `memory/deletions/<memory UUID>.json`, containing only schema_version 1, id, and deleted_at in v1 UTC format. A marker suppresses the whole logical record, including history. Search never returns deletion payloads. T15 must implement deletion propagation and content cleanup, including derived summaries and references; this search does not claim those operations exist.

Search order is deterministic for an unchanged vault. Memory ranking scores title matches above body matches and breaks ties by historical flag, logical ID and revision ID. Legacy ranking retains its existing approved/candidate ordering. Combined results use each mode's ranking score and break ties by result type and source path. The limit is 1..30. Results report result_count, results_truncated and scan_truncated separately. Each mode examines at most --max-notes eligible files (default 1500). Memory reads at most 128 KiB plus one byte per file and excludes oversized records.

An incomplete memory scan suppresses memory results: a skipped file could contain a deletion, revision branch or supersession. Invalid files with recoverable IDs quarantine those records, allowing safe unrelated records to remain readable. Unidentifiable damaged records, invalid deletion metadata, inaccessible directories or unsafe directory links suppress all managed memory results and set memory_incomplete. Counts report invalid, unreadable, oversized and conflicted inputs. Legacy results can remain available independently. Readers observe filesystem snapshots rather than a lock against concurrent edits; re-open relevant sources before applying an update.

Standalone installation bundles the shared memory modules beside the search script. T18 still owns full plugin packaging and installation acceptance. No capture workflow is activated by search.

T13 also resolves effective lifecycle and competing claims sharing a kind,
normalized subject and scope. Semantic conflicts are excluded from current
recall; explicit history exposes them as unresolved historical candidates.
Revision-graph conflicts remain excluded even in history. Valid supersession
links cannot cross project/subject boundaries, and inferred records lose current
status when their linked supporting records become non-current.
