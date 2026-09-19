# Album Journey MVP

Run the manual selector with Python 3:

```bash
python3 random_album.py
```

It makes one read-only request to the approved Portuguese Wikipedia REST HTML
source, validates the complete 500-rank table, prints a random album and its
required CC BY-SA attribution, and does not retain the response. Use
`--seed 42` for a repeatable selection.

## Catalogue import API

`POST /api/v1/catalog/imports` is the only catalogue-import entry point. It
accepts `{ "dry_run": true|false }`, requires `Idempotency-Key` and the local
operator's `X-Operator-Token`, and always fetches the single approved
Portuguese Wikipedia REST HTML URL; callers cannot supply a URL or payload.
Set `ALBUM_IMPORT_OPERATOR_TOKEN` for the API process before using it. A
dry-run validates and reports the normalized SHA-256 and CC BY-SA provenance
without persistence. A non-dry run validates all ranks 1–500 before one
atomic snapshot upsert. Raw source HTML is transient and is neither stored nor
logged.

The current import boundary uses an in-memory transactional reference adapter
until the PostgreSQL adapter from the database workstream is connected. Its
`CatalogueRepository` protocol records the required production transaction and
idempotency contract; it is not a substitute for persistent catalogue storage.
