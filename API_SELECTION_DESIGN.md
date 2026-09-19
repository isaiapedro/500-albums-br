# Local Album Journey MVP — API and Selection Design

## Status and authority

This is Agent 4's planning contract. It refines the API and selection work
against `DATABASE_DESIGN.md`; it creates neither an implementation nor a
runtime API. The browser reaches only the application-owned local API. It
never calls Wikipedia or another catalogue provider.

The contract is provisional where Agent 0 owns the architectural choice. In
particular, Agent 0 must approve the final OpenAPI error envelope, actor
mechanism, identifier representation, idempotency retention, active-catalogue
pointer, and timezone/date-override policy before application code or
migrations are authored.

## API conventions

- Version application routes under `/api/v1`; `/health` is an
  implementation-local liveness/readiness endpoint and exposes no catalogue or
  private data.
- JSON DTOs are explicit allow-lists, never direct ORM serialization. UUIDs
  are strings; timestamps serialize as UTC RFC 3339 instants; `local_date` is
  ISO `YYYY-MM-DD`.
- `Idempotency-Key` is required on import and assignment-generation POSTs. It
  is a bounded opaque client string and never copied to logs verbatim. Reuse
  with the same actor and request fingerprint replays the original result;
  reuse with a changed fingerprint returns `409 idempotency_key_reused`.
  Assignment generation needs a persisted request record in addition to Agent
  2's `import_runs`; its scope and retention remain Agent 0 decisions.
- Catalogue responses include `catalogue_attribution`: source URL, licence,
  attribution text, and normalized-content hash. No endpoint returns raw HTML.
- Cursors are opaque, URL-safe, versioned tokens bound to the active immutable
  source and query fingerprint. Invalid, expired, mismatched-filter, or
  snapshot-mismatched cursors return `400 invalid_cursor`. Album lists use
  `source_rank ASC, id ASC`, default `limit=50`, maximum `100`.

## Resource contract

| Route | Request / response intent | Privacy and outcome rules |
| --- | --- | --- |
| `GET /health` | Minimal status DTO. | No profile, source, database-error, or configuration detail. |
| `POST /catalog/imports` | Empty JSON body plus `Idempotency-Key`; sanitized import-run DTO. | Operator-only once Agent 0 selects the local actor mechanism. Performs only the explicit API-side source read in `BEHAVIOR.md`; accepts no browser payload. |
| `GET /catalog/imports/{id}` | Sanitized import-run DTO. | Operator-only; no raw response, headers, parser errors, or third-party body. |
| `GET /catalog/source` | Active source DTO and attribution. | `404 active_catalogue_not_found` until an approved active-source mechanism exists. |
| `GET /albums?q=&cursor=&limit=` | Items, next cursor, source identity, and attribution. An item has ID, rank, title, artist credit, and nullable year. | No project, assignment, rating, or review joins. |
| `GET /albums/{id}` | One album plus source identity and attribution. | `404 album_not_found` for unknown/non-active albums; no private joins. |
| `POST /projects` | `{name, timezone}` to owner-scoped project DTO. | Server derives owner from actor context; never accepts `owner_id`. IANA validation is required. |
| `GET /projects` | Bounded owner-scoped project list. | Stable creation-time/ID ordering and no other owner's records. |
| `POST /projects/{id}/assignments/generate` | Empty body plus `Idempotency-Key` to assignment DTO. | Owner only. Server derives date from UTC clock in stored project timezone; client dates remain non-authoritative pending Agent 0. |
| `GET /projects/{id}/assignments?from=&to=` | Owner-scoped history. | Bounded range; returns assigned album and attribution, never rating/review. |
| `PUT /assignments/{id}/rating` | `{score, review?}` to owner-scoped singleton rating DTO. | Create-or-replace semantics; assignment must belong to the actor's project. Score 1–5; Agent 0 sets review bound. |
| `GET /assignments/{id}/rating` | Owner-scoped rating DTO or `404 rating_not_found`. | Review text returns only to its owner. |
| `DELETE /assignments/{id}/rating` | `204 No Content`. | Owner only; cannot delete assignment/project/catalogue data. |

The import route is a command endpoint only. Catalogue reads never trigger an
import or external fetch. Future snapshots cannot become defaults until the
Agent 0 active-catalogue decision is implemented.

## DTO boundaries and errors

`Project`, `Assignment`, and `Rating` DTOs omit `owner_id`. Assignment includes
its ID, project ID, server-derived date, assigned time, album summary, source
identity, and attribution. A rating includes its ID, assignment ID, score,
optional review, and timestamps only in an owner-scoped response. Catalogue,
import, health, audit, and error DTOs never carry review text.

The proposed uniform error DTO is:

```json
{"error":{"code":"invalid_cursor","message":"The cursor is invalid."},"request_id":"uuid"}
```

Messages are fixed, client-safe explanations. `request_id` is opaque; SQL
errors, raw payloads, source responses, secrets, private names, and review text
are excluded. Agent 0 owns final approval. Planned codes: `invalid_request`
(400), `invalid_cursor` (400), `authentication_required` (401, if needed),
`forbidden` (403), resource-not-found codes (404),
`idempotency_key_reused`/`cycle_exhausted`/`assignment_conflict` (409),
`import_validation_failed` (422), and `import_unavailable` (503).

## Deterministic selection and concurrency

For an authorized generation request, the API uses one database transaction
against the project's current server-derived local date:

1. Lock/read the `(project_id, local_date)` assignment. If present, return it,
   including for a replayed idempotency request.
2. Resolve the approved active immutable source. If absent, return
   `404 active_catalogue_not_found`; candidates are only albums in that source.
3. Exclude every album already assigned to the project. If none remain, return
   `409 cycle_exhausted`; the MVP never repeats or starts a cycle implicitly.
4. Choose the smallest stable key: `SHA-256("album-journey-v1\\n" + project
   UUID + "\\n" + local date + "\\n" + active normalized-content SHA-256 +
   "\\n" + album UUID)`, with album UUID as final tie-breaker. Persist or make
   reconstructible the algorithm version and inputs. Database random ordering
   is prohibited.
5. Insert and return the assignment. Database unique project/date and
   project/album constraints remain authoritative. On a concurrent unique
   conflict, re-read the date assignment and return the winner.

This proposal is reproducible for the same project, date, source snapshot, and
history without retaining a Personal seed. Agent 0 must approve it or record a
replacement with migration/replay semantics.

## Ownership and prerequisites

Every private query resolves through `projects.owner_id = current_actor_id`;
an inaccessible resource is `404`, preventing cross-profile disclosure. The
MVP actor/profile bridge is not selected, so no route may accept an arbitrary
owner identifier or claim multi-user authentication. Private text cannot enter
audit metadata, catalogue provenance, errors, or external tools.

Agent 2 must add an assignment-generation idempotency record (or equivalent
transactional mechanism) and an active-source relation. It must also close the
ownership integrity gap: `ratings.owner_id` needs a database-enforced proof
that it owns the assignment's project, or ownership must be derived solely via
the assignment/project relation. Agent 3 must supply a sanitized
accepted-source handoff. No code, migrations, containers, or runtime records
may be created until the dedicated implementation repository and these
prerequisites are complete.

## Verification requirements

- Cursor traversal neither duplicates nor skips an active-snapshot album;
  malformed/mismatched cursors are safely rejected.
- Retries and concurrent same-date generation yield one assignment, respect
  the stable key, and exclude prior project albums.
- Absent active source and exhausted cycle return typed outcomes without writes
  or repeats.
- Cross-owner project/assignment/rating access reveals no resource; all
  catalogue/import/audit/error responses omit a review-text sentinel.
- Same idempotency key/fingerprint replays; a changed fingerprint conflicts;
  concurrent requests retain one assignment and request outcome.
