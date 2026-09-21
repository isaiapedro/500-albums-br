"""Immutable shared catalogue and private per-user ordered journeys.

The production database adapter persists the same records. This module keeps
the rules deterministic and makes no network request: a catalogue is supplied
as an already-approved static 500-row seed at build/release time.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Sequence
from uuid import UUID, uuid5


class StaticCatalogueError(ValueError):
    """A static catalogue does not meet the immutable 500-item contract."""


@dataclass(frozen=True, slots=True)
class StaticAlbum:
    id: UUID
    rank: int
    title: str
    artist_credit: str
    release_year: int | None


@dataclass(frozen=True, slots=True)
class JourneyItem:
    user_id: UUID
    album_id: UUID
    position: int
    status: str = "pending"


@dataclass(frozen=True, slots=True)
class StaticCatalogueSeed:
    version: str
    albums: tuple[StaticAlbum, ...]
    source_url: str
    source_license: str
    attribution_text: str
    normalized_content_sha256: str


def load_static_catalogue_seed(path: Path) -> StaticCatalogueSeed | None:
    """Read a release artifact only; this function never contacts a source."""

    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["albums"] if isinstance(payload, dict) else payload
    version = payload.get("catalogue_version", payload.get("version", "static-v1")) if isinstance(payload, dict) else "static-v1"
    provenance = payload.get("provenance", {}) if isinstance(payload, dict) else {}
    namespace = UUID("e0ba1899-cab3-44a0-9e2a-914c01937d34")
    albums = tuple(
        StaticAlbum(
            id=UUID(str(row["id"])) if row.get("id") else uuid5(namespace, f"{version}:{row['rank']}"),
            rank=int(row["rank"]), title=str(row["title"]).strip(),
            artist_credit=str(row["artist_credit"]).strip(),
            release_year=int(row["release_year"]) if row.get("release_year") else None,
        )
        for row in rows
    )
    if not version or any(not album.title or not album.artist_credit for album in albums):
        raise StaticCatalogueError("catalogue_seed_fields_required")
    return StaticCatalogueSeed(
        version=version,
        albums=validate_static_catalogue(albums),
        source_url=str(provenance.get("source_url", "")),
        source_license=str(provenance.get("license", "CC BY-SA")),
        attribution_text=str(provenance.get("source_title", "Discoteca Básica via Wikipédia")),
        normalized_content_sha256=str(provenance.get("normalized_content_sha256", "")),
    )


def validate_static_catalogue(albums: Sequence[StaticAlbum]) -> tuple[StaticAlbum, ...]:
    """Accept one and only one complete immutable ranking."""

    if len(albums) != 500:
        raise StaticCatalogueError("catalogue_must_have_500_albums")
    ranks = [album.rank for album in albums]
    if len(set(ranks)) != 500 or set(ranks) != set(range(1, 501)):
        raise StaticCatalogueError("catalogue_ranks_must_be_1_through_500")
    if len({album.id for album in albums}) != 500:
        raise StaticCatalogueError("catalogue_album_ids_must_be_unique")
    return tuple(sorted(albums, key=lambda album: album.rank))


def create_user_journey(*, user_id: UUID, catalogue: Sequence[StaticAlbum], catalogue_version: str) -> tuple[JourneyItem, ...]:
    """Create a stable private permutation without a stored personal seed.

    Persist the returned 500 rows once. The sorting key is derived from the
    opaque user ID, immutable catalogue version, and shared album ID; no
    personal profile field or third-party data participates.
    """

    approved = validate_static_catalogue(catalogue)
    if not catalogue_version:
        raise StaticCatalogueError("catalogue_version_required")
    ordered = sorted(
        approved,
        key=lambda album: sha256(
            f"album-journey-v2\\n{user_id}\\n{catalogue_version}\\n{album.id}".encode("utf-8")
        ).digest(),
    )
    return tuple(
        JourneyItem(user_id=user_id, album_id=album.id, position=index)
        for index, album in enumerate(ordered, start=1)
    )


def next_pending(items: Sequence[JourneyItem]) -> JourneyItem | None:
    """Return the next position; ratings/reviews never affect ordering."""

    pending = [item for item in items if item.status == "pending"]
    return min(pending, key=lambda item: item.position, default=None)
