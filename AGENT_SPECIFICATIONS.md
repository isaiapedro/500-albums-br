# Local Album Journey MVP — Agent Specifications

Each agent owns a bounded specification. Application source remains out of
this workspace root until a dedicated repository is created and registered.

| Agent | Scope and deliverables | Dependencies | Acceptance criteria |
| --- | --- | --- | --- |
| 0 — Architecture | ADRs, OpenAPI contract, local port/config decision, Wikipedia CC BY-SA provenance policy, repository layout | None | Contract defines IDs, error shape, timezone behavior, data boundary, source attribution, and no-scraping rule. |
| 1 — Container platform | Dockerfiles, Compose stack, health checks, non-root images, `.env.example`, task commands | Agent 0 | `docker compose up --build` starts web, API, and healthy database; DB is private. |
| 2 — Database | `DATABASE_DESIGN.md`, then PostgreSQL schema, Alembic migrations, fixtures, indexes, least-privilege roles, and import/assignment transaction boundaries | Agents 0–1 | Blank and forward migrations pass; constraints enforce immutable source provenance, ranks 1–500, private ownership, no repeated project album, and unique assignment/rating/idempotency keys. |
| 3 — Catalogue import | Operator-invoked Wikipedia REST HTML fetch/parser, 500-rank validation, provenance fields, canonical hashing, dry-run report, atomic upserts | Agents 0 and 2 | A complete 500-row import re-imports idempotently; malformed, incomplete, or duplicate-ranked input leaves no partial writes and raw HTML is not retained. |
| 4 — API and selection | `API_SELECTION_DESIGN.md`, then FastAPI routes, explicit DTOs, deterministic assignment selection, owner-scoped ratings/reviews, cursor pagination, and error mapping | Agents 0, 2, and 3 | Same project/date/replay returns one assignment; prior albums are excluded until typed cycle exhaustion; catalogue attribution travels with every catalogue DTO; private review text never crosses owner scope. |
| 5 — Web client | React/Vite UI, generated typed API client, Today, catalogue, history, rating/review states | Agents 0 and 4 | The whole local happy path works from the browser without direct database access. |
| 6 — Quality | `QUALITY_STRATEGY.md`, then hermetic unit, migration, API, browser-smoke, Compose, formatting, and type gates | Agents 1–5 | Synthetic inline fixture import → assignment → rating → history passes as one automated end-to-end check; live source access, raw-payload retention, private-data leakage, and private API/DB exposure are rejected. |
| 7 — Local handoff | Setup, backup/restore, reset, troubleshooting, source-rights guidance, MVP limitations | Agents 1–6 | A new developer can reproduce and test the local stack without undocumented steps. |

## Coordination order

1. Agent 0 establishes contracts before implementation.
2. Agents 1 and 2 establish the runnable platform and persistence layer.
3. Agent 3 builds the import boundary while Agent 4 scaffolds API routes.
4. Agent 5 connects the browser to the contract-defined API.
5. Agent 6 owns the final integrated gate; Agent 7 documents the verified result.

## Cross-agent rules

- The browser never fetches third-party catalogue APIs directly.
- Only the API may process imports; import records retain source metadata but
  do not persist raw credentials or private third-party user data.
- The Wikipedia source is a manual read-only import dependency; no browser,
  background worker, or runtime catalogue endpoint may fetch it.
- Catalogue responses and exports include the stored CC BY-SA attribution.
- Store timestamps in UTC and derive assignment dates using the project IANA
  timezone.
- PostgreSQL constraints and transaction/re-read handling are the final
  authority for idempotency and duplicate prevention; assignment generation
  additionally needs its own persisted idempotency record.
- Agent 2 keeps immutable accepted catalogue snapshots separate from import
  attempts and private journey data; neither raw source responses nor private
  review text may enter operational provenance/audit fields.
- Agent 6 tests use only in-process fake HTTP and inline synthetic data. They
  exercise the real parser/transaction boundary but never call Wikipedia or
  retain a real source response.
- A production deployment, public sharing, or external source adapter requires
  a new decision, privacy review, and promotion plan.
