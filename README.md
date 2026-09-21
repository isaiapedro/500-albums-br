# 500 Discos Brasileiros

A deliberately small, local-first album journey. Each journey gets a stable,
human-readable URL such as `/journey/um-ano-e-meio-de-musica`; no login or
application token is needed on the loopback-only MVP.

## Run

```bash
cp .env.example .env
docker compose up --build -d --wait
```

Open `http://127.0.0.1:5174`. One FastAPI container serves the HTML/CSS/JS,
JSON API, reviewed 500-album catalogue, and a persistent SQLite database. It
uses Docker host networking only to bind Uvicorn directly to that loopback
address; no service is exposed on a non-loopback interface.

For local development:

```bash
cd api
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
ALBUM_JOURNEY_DB=/tmp/album-journey.db .venv/bin/uvicorn app.main:app --reload --port 5174
```

## Data and privacy

The runtime never contacts Wikipedia, MusicBrainz, Cover Art Archive, or another catalogue provider. The
release includes one normalized, attributed CC BY-SA seed; the browser displays
its attribution. Journey names, daily assignments, ratings, and reviews remain
in the local SQLite volume and are never sent to external services.

Optional cover thumbnails are imported only during release preparation and then
served from `/static/covers/` alongside the app. Run `python3 scripts/import_cover_art.py`
from the project root to perform that explicit, rate-limited operation; it
keeps unmatched albums on the built-in cover fallback.

The URL selects a local journey, not an authenticated public account. Before
any public deployment, add an explicit identity/privacy design, TLS, encrypted
backup storage, retention policy, abuse controls, and an incident owner.

`BACKUP_DIR=/secure/path make backup` creates a private SQL snapshot. Restore
is intentionally destructive and requires `BACKUP_FILE=/path/file.sql.gz make
restore`.

## Why this shape

The MVP has one process, one image, one volume, no Node production build, no
reverse proxy, no database server, and no credentials. SQLite is appropriate
for this single-process, low-write workload; move to a client/server database
only if measured concurrency or multi-instance deployment requires it.
