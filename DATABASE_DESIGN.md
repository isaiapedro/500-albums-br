# Local Album Journey MVP — Database Design

## Status and boundary

This is Agent 2's implementation-ready database plan, not a migration or a database artifact. PostgreSQL will be private to the Compose network; it has no published host port. All timestamps are `timestamptz` in UTC. UUID primary keys are server-generated, and all runtime values, volumes, credentials, raw source payloads, and database dumps remain untracked.

The database has two data classes. Objective catalogue/provenance tables contain only the attributed Discoteca Básica ranking. Private journey tables contain projects, assignments, ratings, and reviews. APIs and audit records must not copy private review text into objective or operational data.

## Tables and relationships

```text
catalog_sources 1 ── * albums 1 ── * album_links (only if later approved)
       │
       └────────── * import_runs

local_profiles 1 ── * projects 1 ── * assignments * ── 1 albums
local_profiles 1 ── * ratings * ── 1 assignments
```

`local_profiles` represents a local opaque owner identifier only: no name, email, credential, or external account is stored for the MVP. It enforces the single-user boundary without hard-coding Personal information.

### Objective catalogue and provenance

| Table | Required fields and constraints | Purpose |
| --- | --- | --- |
| `catalog_sources` | `id`; immutable `source_kind = wikipedia_rest_html`; non-null `source_url`, `source_license`, `attribution_text`, `retrieved_at`, and `normalized_content_sha256`; optional `source_revision`; `imported_row_count = 500`; unique SHA-256 | One accepted, immutable normalized catalogue snapshot. No raw HTTP body, headers, or parser output. |
| `albums` | `id`; `catalog_source_id` FK `RESTRICT`; `source_rank` 1–500; nonblank `title` and `artist_credit`; `release_year` 1880–2100 when present; unique (`catalog_source_id`, `source_rank`) | Exact normalized source rows. Do not globally deduplicate albums by text. |
| `album_links` | Deferred unless a specific link target is approved; `album_id` FK `RESTRICT`; constrained relation/target kind; HTTPS URL; unique (`album_id`, `relation`, `target_url`) | Optional application-owned outbound references, never source scraping or asset caching. |
| `import_runs` | `id`; `idempotency_key`; request fingerprint; lifecycle status; timestamps; parsed-row count; normalized SHA-256 when available; optional accepted `catalog_source_id` FK; sanitized error code only; unique request idempotency scope | Fetch/import attempt and request replay record, separate from accepted source truth. No raw HTML or error excerpts. |

The SHA-256 comes from a deterministic canonical serialization of validated rows, ordered by rank, after documented Unicode and whitespace normalization. It is content idempotency, distinct from a client request's idempotency key. A changed later source creates a new immutable snapshot; an explicit active-catalogue pointer is required before an API may switch its default source.

### Private journey tables

| Table | Required fields and constraints | Purpose |
| --- | --- | --- |
| `local_profiles` | opaque `id`, creation timestamp | Local ownership boundary. |
| `projects` | `id`; `owner_id` FK; nonblank name; IANA timezone; lifecycle timestamps/status | A private album journey. Validate the timezone against an IANA database in the application. |
| `assignments` | `id`; `project_id` FK `RESTRICT`; `album_id` FK `RESTRICT`; `local_date`; assignment timestamp; unique (`project_id`, `local_date`) and (`project_id`, `album_id`) | Stable daily selection and no album repeat within the MVP's single cycle. |
| `ratings` | `id`; `assignment_id` FK; `owner_id` FK; score 1–5; optional bounded review; timestamps; unique (`assignment_id`, `owner_id`) | Private rating/review only. No catalogue or export endpoint returns it. |
| `audit_events` | typed event, UTC timestamp, optional opaque actor/correlation FK, allow-listed non-sensitive metadata | Minimal operational trace. It never contains review bodies, private names, credentials, raw payloads, or full errors. |

Ratings may cascade only when a deliberately supported assignment deletion is introduced; the MVP otherwise uses `RESTRICT` to preserve history. The rating scale is provisionally 1–5 and must be reflected in Agent 0's API contract before implementation. A project is complete after 500 distinct assignments; multi-cycle behaviour needs a future decision.

## Import transaction and idempotency

1. The operator invokes the API-side importer with an idempotency key. The importer fetches and parses outside the database transaction and discards the raw response immediately after parsing.
2. Before any write, validate exactly 500 normalized rows, ranks equal to 1–500, required nonblank text, valid optional years, and canonical SHA-256. A bad payload produces a sanitized failed run with no catalogue writes.
3. A serialized transaction or advisory lock reuses an existing accepted snapshot for an existing SHA-256. Otherwise it inserts one source and exactly 500 albums, verifies count/rank span, marks the run successful, and commits.
4. Any failure rolls back source and album writes. A failure audit/run record, if required, is written separately with a bounded code. Concurrent identical imports resolve through the unique hash and return the existing result.
5. Reusing an idempotency key with a different request fingerprint is a conflict; replaying the same request returns its original result. This request-level rule is separate from content-level deduplication.

## Migration, access, and verification plan

Migrations are additive and forward-only; they create schema, constraints, indexes, and least-privilege roles but never fetch or seed catalogue data. The migrator owns DDL, the runtime API receives application DML only, and the importer is restricted to catalogue/import writes. A read-only diagnostic role has no private-review access. Exact grants and downgrade policy are implementation-repository work.

Required verification before Agent 2 is accepted:

- Blank-database migration, re-run no-op, and forward upgrade test pass.
- Direct SQL rejects orphan FKs, duplicate source ranks, ranks outside 1–500, duplicate project dates, repeated project albums, invalid scores, and duplicate per-owner ratings.
- A valid 500-row fixture creates one source and 500 albums; replay does not add rows. Same request key replays; a changed request under that key conflicts.
- 499/501 rows, missing/duplicate/out-of-range ranks, malformed required data, and injected mid-transaction failure leave zero partial catalogue writes. Concurrent identical imports leave one snapshot.
- Persistence/log inspection proves a raw-HTML sentinel and review-text sentinel are absent from provenance/audit records; catalogue responses include attribution and never private ratings/reviews.

## Open implementation contracts

Before migrations are authored, Agent 0 must confirm canonicalization details, whether a missing/non-numeric release year is rejected or null, idempotency-key scope and retention, importer operator authorization, maximum review length, and active-catalogue selection. These are deliberately not settled by this planning record.
