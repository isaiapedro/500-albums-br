"""Load optional, release-bundled cover-art metadata without network access."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CoverAsset:
    path: str
    source_url: str
    musicbrainz_release_group_id: str


def load_cover_manifest(path: Path) -> dict[UUID, CoverAsset]:
    """Return reviewed local assets; a missing manifest means covers are optional."""

    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", {}) if isinstance(payload, dict) else {}
    if not isinstance(items, dict):
        return {}

    assets: dict[UUID, CoverAsset] = {}
    for raw_id, raw_asset in items.items():
        if not isinstance(raw_asset, dict):
            continue
        relative_path = raw_asset.get("path")
        if not isinstance(relative_path, str) or not relative_path.startswith("covers/"):
            continue
        try:
            album_id = UUID(raw_id)
        except (TypeError, ValueError):
            continue
        assets[album_id] = CoverAsset(
            path=relative_path,
            source_url=str(raw_asset.get("source_url", "")),
            musicbrainz_release_group_id=str(raw_asset.get("musicbrainz_release_group_id", "")),
        )
    return assets
