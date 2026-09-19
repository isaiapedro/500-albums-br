# Architectural Decisions

## 2026-09-19 — Local-first, catalogue-import MVP

The first implementation is limited to a local website, application-owned
JSON API, local PostgreSQL, and container orchestration. It accepts only a
provenance-backed, rights-compatible catalogue import—either an approved JSON
or CSV file or the later-selected Wikipedia REST source—rather than scraping
or mirroring the 1001 Albums Generator service.

Reason

This preserves source rights, separates the experiment from third-party user
data, and makes the core selection/rating workflow reproducible offline after
import.

Alternatives

- Directly consume or scrape a third-party catalogue: rejected for the MVP
  because licence, rate-limit, availability, and user-data boundaries are not
  controlled by this experiment.
- Deploy a public service immediately: deferred until repository, security,
  identity, consent, backup, and catalogue-rights decisions are complete.

Consequences

The MVP needs an import workflow and provenance records. An optional external
source adapter can be evaluated only as a read-only, explicitly permitted
follow-up.

## 2026-09-19 — Wikipedia REST HTML is the MVP Discoteca Básica ranking source

The MVP catalogue import will use the Portuguese Wikipedia REST HTML endpoint
for *Lista dos 500 maiores discos da música brasileira pelo Discoteca Básica*.
It supplies the complete 500-row ranking in one documented public response,
with rank, title, release year, and credited artist fields. The import is a
manual, one-off API-side operation; the browser and runtime API never call the
source directly.

Reason

The official Discoteca Básica site documents and sells the book but does not
offer a complete machine-readable list. Album of the Year exposes the data as
ten paginated HTML pages, which would require scraping and conflicts with the
experiment's no-scraping boundary. Wikipedia's REST representation is the
least operationally complex source for the seed ranking, and its CC BY-SA
licence gives a clear attribution condition.

Alternatives

- Album of the Year paginated list: rejected for the MVP because it is a
  third-party HTML extraction route rather than a documented data API and
  requires ten page fetches.
- Official Discoteca Básica book/site: not selected as an ingestion endpoint;
  it remains the authority described by the provenance, but no complete public
  API was found.
- Hand-maintained CSV: deferred; it would create an avoidable transcription
  and maintenance responsibility.

Consequences

Each `catalog_sources` row must record the Wikipedia page URL, retrieval time,
CC BY-SA attribution/licence, response revision identifier when available, and
the hash of the normalized 500-row import. The importer must validate ranks
1–500 exactly and atomically reject any other result. Attribution must travel
with catalogue API responses and exports. A later source substitution requires
a new decision and licence/provenance review.

## 2026-09-19 — Immutable source snapshots and private journey separation

An accepted Wikipedia import is represented as an immutable, hash-identified
catalogue snapshot with exactly 500 album rows. Import attempts, client request
idempotency, and sanitized operational outcome are recorded separately. The
local journey—projects, assignments, ratings, and reviews—uses separate private
tables and opaque local owner identifiers.

Reason

This permits repeatable attribution and content-level deduplication without
making a repeated retrieval appear to be a new catalogue. It also ensures that
private review text cannot drift into catalogue provenance or audit records.

Alternatives

- Update a single mutable current catalogue in place: rejected because it
  destroys the source basis of past assignments and attribution.
- Store raw responses with each import attempt: rejected by the no-payload
  retention boundary and unnecessary for the normalized 500-row catalogue.

Consequences

Agent 2 must enforce source rank, hash, foreign-key, private-owner, assignment,
rating, and request-idempotency constraints in PostgreSQL. A separate
active-catalogue selection mechanism is required before a later source revision
can become the default. The initial project cycle cannot repeat an album;
multi-cycle behaviour needs a future decision.

## 2026-09-19 — Dedicated repository and loopback port for implementation

The experiment implementation is owned by the dedicated
`isaiapedro/500-albums-br` repository. The local browser entry point reserves
loopback port `5174`; PostgreSQL remains private to the Compose network.

Reason

The workspace root does not own application source. A nested repository keeps
the implementation independent, while a stable loopback port gives the local
website a predictable entry point without exposing the database.

Consequences

Agent 1 may create Compose and Docker artifacts in this repository. Public
deployment, a host-published database port, and new fixed listeners remain out
of scope without a later decision and Registry update.

## 2026-09-19 — Separate loopback edge and private service networks

The web container joins a normal Docker bridge network solely to publish its
loopback-bound port. It also joins the private internal network used by the API
and PostgreSQL; those services join only the private network.

Reason

An internal-only Docker network prevented the web port from being reachable
from the local host. The split preserves the browser entry point while keeping
the API and database unreachable from the host and edge network.
