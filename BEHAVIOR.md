# Local Album Journey MVP — Behavior Specification

## Transient operations

This experiment produces architecture, implementation planning, and later a
local-only MVP. It is not a production service and may be promoted only after
the side-project admission and repository requirements are met.

## Data and privacy boundary

- Import only an objective catalogue whose use is explicitly permitted and
  traceable. The selected MVP seed is the Portuguese Wikipedia REST HTML
  representation of *Lista dos 500 maiores discos da música brasileira pelo
  Discoteca Básica*; its derived data is CC BY-SA and must retain attribution.
- The importer may perform one explicit, operator-initiated, read-only fetch
  from `https://pt.wikipedia.org/api/rest_v1/page/html/Lista_dos_500_maiores_discos_da_m%C3%BAsica_brasileira_pelo_Discoteca_B%C3%A1sica`.
  It must not run in the browser, on application start, or as a background
  refresh job.
- Store only the normalized ranking fields (rank, title, release year, and
  credited artist text) plus source URL, retrieval timestamp, license,
  response revision identifier when supplied, and a hash of the normalized
  imported content. Do not retain the raw HTML payload in tracked contracts,
  database records, or application logs.
- Accept a source run only when it yields exactly 500 rows with unique ranks
  1 through 500. Invalid or incomplete source data must fail atomically.
- Display and return source attribution and the CC BY-SA notice wherever the
  imported catalogue is exposed or exported.
- Do not scrape 1001 Albums Generator or copy its catalogue, branding, user
  histories, reviews, or API responses into the local database.
- Keep locally recorded ratings and reviews private by default. Do not send
  them to external research, catalogue, analytics, or Knowledge systems.
- Do not store credentials, raw third-party payloads, containers, volumes,
  runtime logs, or database dumps in this experiment's tracked contracts.

## Runtime behavior under evaluation

The future MVP uses a browser-facing local website, an application-owned JSON
API, and a PostgreSQL database inside a private Compose network. Only the web
interface may bind to loopback after a port is reserved in `registry/PORTS.md`.
PostgreSQL must remain network-private.

## Invalidation flags

This experiment is automatically eligible for archival unless it receives a
dedicated repository, a verified local implementation, a provenance-backed
catalogue, and an explicit promotion decision.
