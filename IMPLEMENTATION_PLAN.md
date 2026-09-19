# Local Album Journey MVP — Implementation Plan

## Objective

Build a local-only website that imports an attributed CC BY-SA album ranking,
stores it in PostgreSQL, assigns an album per project/day, and persists private
ratings and reviews through an application-owned JSON API.

## MVP boundary

Included:

- Local browser UI.
- FastAPI JSON REST API.
- PostgreSQL persistence and schema migrations.
- Manual Wikipedia REST HTML ranking import with provenance and idempotency.
- Daily album assignment, history, and private rating/review flows.
- Docker Compose orchestration for web, API, and database containers.

Excluded:

- Scraping, copying, or mirroring third-party catalogues or user histories.
- Public sharing, groups, email, OAuth, analytics, and production deployment.
- Audio hosting, cover-art downloading, or caching third-party assets.
- Scheduled source refreshes, runtime source reads, or raw third-party payload
  retention.

## Selected catalogue source

The initial catalogue is the 500-row Portuguese Wikipedia article table served
by MediaWiki REST HTML:

`https://pt.wikipedia.org/api/rest_v1/page/html/Lista_dos_500_maiores_discos_da_m%C3%BAsica_brasileira_pelo_Discoteca_B%C3%A1sica`

The importer is an API-side, operator-invoked job. It extracts `rank`,
`title`, `release_year`, and `artist_credit`, validates one row for every rank
from 1 to 500, and atomically upserts the normalized data. It records source
URL, retrieval time, CC BY-SA attribution/licence, HTTP revision metadata when
available, and a SHA-256 hash of the normalized input; it discards the raw
response after parsing. Catalogue reads and exports include the source
attribution. This is a derivative, convenience ingestion source—not a claim
that Wikipedia is the ranking's original publisher.

## Target topology

```text
Browser
  -> web container (same-origin UI and /api proxy)
  -> api container (FastAPI)
  -> db container (PostgreSQL named volume)

One-off import command -> API service -> PostgreSQL
```

The Compose network is private. PostgreSQL has no host-published port. The web
container is the only loopback-published interface, and its fixed port must be
allocated in `registry/PORTS.md` before implementation begins.

## Data and API contract

The database design is specified in `DATABASE_DESIGN.md`. It separates
immutable objective `catalog_sources`/`albums` provenance from private
`local_profiles`/`projects`/`assignments`/`ratings` journey data. `import_runs`
records request attempts and idempotency independently of a source snapshot;
it does not retain raw source content. `album_links` is deferred until a
specific link target has been approved.

Database invariants:

```text
UNIQUE (assignments.project_id, assignments.local_date)
UNIQUE (assignments.project_id, assignments.album_id)
UNIQUE (ratings.assignment_id, ratings.owner_id)
UNIQUE (catalog_sources.normalized_content_sha256)
UNIQUE (albums.catalog_source_id, albums.source_rank)
UNIQUE (import_runs.idempotency_key)
```

The route, DTO, cursor, attribution, privacy, error, idempotency, and
deterministic-selection contract is `API_SELECTION_DESIGN.md`. Its minimum
REST surface is:

```text
GET  /health
POST /api/v1/catalog/imports
GET  /api/v1/catalog/imports/{id}
GET  /api/v1/catalog/source
GET  /api/v1/albums?q=&cursor=&limit=
GET  /api/v1/albums/{id}
POST /api/v1/projects
GET  /api/v1/projects
POST /api/v1/projects/{id}/assignments/generate
GET  /api/v1/projects/{id}/assignments?from=&to=
PUT  /api/v1/assignments/{id}/rating
GET  /api/v1/assignments/{id}/rating
DELETE /api/v1/assignments/{id}/rating
```

All payloads are JSON. Import and assignment-generation requests require an
idempotency key. The initial single-user local profile does not expose an
external listener; multi-user authentication is a prerequisite for promotion.
Generation uses only the approved active immutable snapshot, derives its date
server-side from the project's IANA timezone, uses no database-random ordering,
and returns no repeat before typed cycle exhaustion.

`QUALITY_STRATEGY.md` defines the hermetic implementation acceptance gate.
It requires inline synthetic 500-row fixtures and fake HTTP only; no test may
fetch, retain, or commit a real Wikipedia response. It also specifies migration,
atomicity/idempotency, privacy/attribution, browser, and Compose-topology
evidence.

## Delivery sequence

```text
Architecture contract
        ↓
Container platform + database migrations
        ↓
 Wikipedia REST import with 500-row validation and source snapshot provenance
        ↓
API and idempotent selection engine
        ↓
Web client
        ↓
End-to-end test and local handoff
```

## Completion gate

From a clean dedicated implementation repository, the following must succeed:

```bash
docker compose up --build
make migrate
make import-sample  # provisional name: synthetic local fixture only
make test
```

The browser must demonstrate: fixture import, project creation, stable daily
assignment, private rating persistence, and assignment history display.
