# Local Album Journey MVP — Quality Strategy

## Status and boundary

This is Agent 6's planning contract. It defines the implementation-repository
quality gate; it creates no application code, migrations, Compose artifacts,
containers, databases, fixtures, source payloads, or runtime records. All
tests must be hermetic: they must never call Wikipedia or another external
service, and they must not commit real source HTML, database dumps, secrets,
or Personal data.

Agent 6 owns the eventual test harness, synthetic fixture adapter, assertions,
and integrated local/CI gate. Agent 6 does not replace the implementation work
owned by Agents 1–5.

## Test data and source isolation

Every parser, API, database, browser, and integration test uses an in-process
fake HTTP client and deterministic inline synthetic data. The accepted fixture
has 500 synthetic rows with ranks 1–500, fixed URL/licence/attribution/revision
metadata, predictable normalized fields, and a known canonical hash. It must
exercise the real parser and transaction boundary, but it is not a retained
MediaWiki response or a file fixture.

Inline variants cover 499 and 501 rows, duplicate, missing, and out-of-range
ranks, blank title/artist, malformed year, parser failure, and injected
failures after source insertion and during the album batch. Unique raw-body,
header, and private-review sentinels prove transience: they must be absent from
database provenance/import/audit records, API DTOs, captured logs, and browser
network payloads. Canonical Unicode/whitespace/hash vectors wait for Agent 0's
canonicalization decision.

## Contract matrix

| Level | Required evidence |
| --- | --- |
| Unit/parser | Exact rank set, required normalized fields, year policy, canonical hash, dry run, and sanitized parser failures using only inline fakes. |
| Database/migration | Empty-database migrate; repeat migration no-op; supported forward upgrade; schema/introspection and direct SQL prove FKs, `RESTRICT`, source hash/rank, project date/album, rating score, and idempotency constraints. Migrations neither seed nor fetch. Verify migrator/runtime/importer/diagnostic grants once Agent 2 specifies them. |
| Import integration | Valid 500-row import yields one immutable source and 500 albums. Same content deduplicates; same key/fingerprint replays; changed fingerprint under that key is `409`; a changed hash makes a separate immutable snapshot. Invalid input and injected failure leave no partial source/album writes; concurrent identical imports leave one snapshot. |
| API/selection | Allow-listed DTOs and final fixed error envelope; import accepts neither URL nor payload and requires operator authorization plus key. Cursor traversal yields each active-snapshot album once in stable order; tampered, expired, query-, or snapshot-mismatched cursor is `400`. Attribution accompanies every catalogue/assignment-history result. Frozen clock, UUIDs, timezone, snapshot, and history prove SHA-256-minimum selection. Retry/concurrency produces one daily assignment; no active source and exhausted cycle produce typed outcomes without writes. |
| Privacy/security | Two opaque actors prove cross-owner project, assignment, and rating operations return `404` without disclosure. Requests never accept `owner_id`. Snapshots and log assertions reject owner IDs, review sentinels, raw HTML/headers/parser details, credentials, and SQL errors outside the owner-scoped rating response. Browser traffic is same-origin application API only—never Wikipedia. |
| Browser smoke | Synthetic fixture import, project creation, deterministic today assignment, private rating/review, and history complete through the web UI with no direct database access. Agent 5 supplies stable selectors and flow hooks. |
| Compose integration | In an isolated, clean test project: build, readiness, migrate, hermetic fixture import, API suite, browser smoke, and teardown pass. Assert only web binds `127.0.0.1:5174`; API/PostgreSQL publish no host port; web bridges edge/private networks; API/database are private-only; containers are non-root; isolated test volumes are cleaned. |

## Reproducible acceptance gate

In the registered implementation repository, with only a documented
non-secret `.env.example`, the eventual gate is:

```text
docker compose up --build → readiness → migrate → hermetic fixture import
→ unit/migration/API tests → browser smoke → topology/log/sentinel checks
→ teardown
```

The existing `make import-sample` name is provisional: it must mean a
synthetic local fixture command, never a live source import. The production
operator import remains explicit and API-side under the behavior contract.

## Blocking decisions and handoffs

No runnable quality gate may be accepted until the following are resolved or
delivered:

| Owner | Required resolution or handoff |
| --- | --- |
| Agent 0 | Actor mechanism; final error envelope; canonical serialization/Unicode and year policy; active-catalogue pointer; idempotency scope/retention; operator authorization; review bound; timezone/date override. |
| Agent 1 | Registered implementation repository; non-root split-network Compose topology; health/readiness; environment contract; reproducible task commands. |
| Agent 2 | Forward migrations, roles/grants, active-source and assignment-request persistence, transaction hooks, and database-enforced rating ownership or derived ownership design. |
| Agent 3 | Fakeable parser/import boundary, dry-run behavior, and sanitized accepted-source handoff. |
| Agent 4 | Final routes/DTOs/cursors/error/idempotency and selection-concurrency semantics. |
| Agent 5 | Browser API boundary, stable test selectors, and private-flow states. |

Until those handoffs exist, this strategy is a test plan only. It does not
authorize a live import, a fixture payload, or any implementation artifact in
this unmanaged planning scope.
