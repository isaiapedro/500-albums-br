# Traceability

## Scope

This experiment translates the local album-journey MVP concept into a
containerized implementation plan. It is a planning artifact, not evidence of
rights to any third-party catalogue or readiness for public deployment.

## Artifact map

| Need | Contract artifact |
| --- | --- |
| Local web/API/database MVP | `IMPLEMENTATION_PLAN.md` |
| Discoteca Básica ranking source and ingestion constraints | `BEHAVIOR.md`, `DECISIONS.md`, and `IMPLEMENTATION_PLAN.md` |
| CC BY-SA attribution and normalized-source provenance | `BEHAVIOR.md` and `IMPLEMENTATION_PLAN.md` |
| Database entities, private/objective separation, and import invariants | `DATABASE_DESIGN.md` |
| API routes/DTOs, safe errors, attribution, cursors, and deterministic private selection | `API_SELECTION_DESIGN.md` |
| Hermetic contract, migration, import, privacy, browser, and Compose quality gate | `QUALITY_STRATEGY.md` |
| Bounded implementation ownership | `AGENT_SPECIFICATIONS.md` |
| Privacy and lifecycle boundary | `BEHAVIOR.md` and `manifest.yaml` |
| Architectural rationale | `DECISIONS.md` |
| Verification status | `AUDIT.md` |

## Follow-up conditions

Before application source is initialized, resolve Agent 0's active catalogue,
actor, API envelope, timezone, review-bound, canonicalization/year, importer
authorization, and idempotency decisions; extend Agent 2's schema for
assignment idempotency, active-source selection, and rating ownership integrity;
and complete Agent 3's sanitized accepted-source handoff. Agents 1, 4, and 5
must then supply the platform, final API/selection semantics, and browser
hooks required by `QUALITY_STRATEGY.md`. The selected Wikipedia source's
attribution, exact 500-row validation, and atomic-import requirements remain
mandatory. Before public deployment, add authentication, consent,
backup/restore, observability, rate limiting, and legal/privacy review.

## Agent 1 implementation evidence

The dedicated `isaiapedro/500-albums-br` repository is registered and the
loopback web port `5174` is reserved. `compose.yaml` creates a loopback edge
network for the web container and an internal-only network for API/PostgreSQL.
The database is never host-published.
