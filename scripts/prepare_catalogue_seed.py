#!/usr/bin/env python3
"""Build a reviewed, static catalogue seed from the declared source once.

This is a release-preparation utility, not part of the running application.
It fetches the approved MediaWiki REST HTML into memory, validates it with the
same strict parser used by the application, writes normalized JSON plus its
provenance, and discards the HTML.  Do not run it from a container or browser.
Review the generated file and its CC BY-SA obligations before adding it to a
release.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "api"))

from app.catalogue_parser import (  # noqa: E402 - project-local import path
    CatalogueValidationError,
    NormalizedAlbum,
    normalized_sha256,
    parse_and_validate_html,
)


SOURCE_URL = (
    "https://pt.wikipedia.org/api/rest_v1/page/html/"
    "Lista_dos_500_maiores_discos_da_m%C3%BAsica_brasileira_pelo_Discoteca_B%C3%A1sica"
)
SOURCE_TITLE = "Lista dos 500 maiores discos da música brasileira pelo Discoteca Básica"
SOURCE_LICENSE = "CC BY-SA"
MAX_SOURCE_BYTES = 5 * 1024 * 1024


def fetch_source_html(*, timeout: float) -> str:
    """Read the fixed source into memory with a bounded response size."""

    request = Request(SOURCE_URL, headers={"User-Agent": "album-journey-release-prep/1"})
    with urlopen(request, timeout=timeout) as response:
        content_length = response.headers.get("Content-Length")
        if content_length is not None and int(content_length) > MAX_SOURCE_BYTES:
            raise ValueError("source_response_too_large")

        chunks: list[bytes] = []
        received = 0
        while chunk := response.read(64 * 1024):
            received += len(chunk)
            if received > MAX_SOURCE_BYTES:
                raise ValueError("source_response_too_large")
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8")


def album_payload(album: NormalizedAlbum) -> dict[str, object]:
    """Give each immutable source row a stable UUID derived from its rank."""

    return {
        "id": str(uuid5(NAMESPACE_URL, f"{SOURCE_URL}#rank={album.rank}")),
        "rank": album.rank,
        "title": album.title,
        "release_year": album.release_year,
        "artist_credit": album.artist_credit,
    }


def seed_payload(*, rows: tuple[NormalizedAlbum, ...], retrieved_at: datetime) -> dict[str, object]:
    """Return the complete portable seed without retaining source HTML."""

    content_sha256 = normalized_sha256(rows)
    return {
        "schema_version": 1,
        "catalogue_version": f"discoteca-basica-500-{content_sha256[:12]}",
        "provenance": {
            "source_url": SOURCE_URL,
            "source_title": SOURCE_TITLE,
            "license": SOURCE_LICENSE,
            "retrieved_at": retrieved_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "normalized_content_sha256": content_sha256,
        },
        "albums": [album_payload(album) for album in rows],
    }


def write_seed(*, output: Path, payload: dict[str, object]) -> None:
    """Atomically write only the normalized release asset."""

    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(output)
    output.chmod(0o644)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "api" / "app" / "catalogue_seed.json",
        help="normalized release asset path (default: api/app/catalogue_seed.json)",
    )
    parser.add_argument("--timeout", type=float, default=20, help="HTTP timeout in seconds (default: 20)")
    args = parser.parse_args()

    try:
        rows = parse_and_validate_html(fetch_source_html(timeout=args.timeout))
        write_seed(output=args.output, payload=seed_payload(rows=rows, retrieved_at=datetime.now(UTC)))
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, ValueError, CatalogueValidationError) as error:
        # Validation categories are intentionally safe; never print source HTML.
        print(f"Catalogue seed preparation failed: {error}", file=sys.stderr)
        return 1

    print(f"Wrote reviewed-candidate static seed: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
