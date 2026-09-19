"""Transactional catalogue persistence boundary.

The production adapter must implement the same atomic semantics with the
database constraints described in ``DATABASE_DESIGN.md``.  The small in-memory
adapter keeps the HTTP boundary executable before the PostgreSQL adapter from
the database workstream is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Protocol, Sequence
from uuid import UUID, uuid4

from .catalogue_parser import NormalizedAlbum


class IdempotencyConflict(ValueError):
    """An idempotency key was replayed with a different request fingerprint."""


@dataclass(frozen=True)
class SourceProvenance:
    source_url: str
    source_license: str
    attribution_text: str
    retrieved_at: datetime
    source_revision: str | None
    normalized_content_sha256: str


@dataclass(frozen=True)
class ImportResult:
    import_run_id: UUID
    status: str
    parsed_row_count: int
    normalized_content_sha256: str
    catalog_source_id: UUID | None
    provenance: SourceProvenance


class CatalogueRepository(Protocol):
    """Stores a fully validated snapshot as one all-or-nothing operation."""

    def upsert_snapshot(
        self,
        *,
        idempotency_key: str,
        request_fingerprint: str,
        rows: Sequence[NormalizedAlbum],
        provenance: SourceProvenance,
    ) -> ImportResult: ...


@dataclass(frozen=True)
class _StoredSnapshot:
    id: UUID
    rows: tuple[NormalizedAlbum, ...]
    provenance: SourceProvenance


class InMemoryAtomicCatalogueRepository:
    """Thread-safe reference adapter used only until the DB adapter is wired.

    It deliberately has no field for raw response bytes/HTML or arbitrary
    response headers.  The lock models the one transaction boundary required
    for the source-hash and idempotency uniqueness checks.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_hash: dict[str, _StoredSnapshot] = {}
        self._runs: dict[str, tuple[str, ImportResult]] = {}

    @property
    def snapshot_count(self) -> int:
        return len(self._by_hash)

    @property
    def album_count(self) -> int:
        return sum(len(snapshot.rows) for snapshot in self._by_hash.values())

    def upsert_snapshot(
        self,
        *,
        idempotency_key: str,
        request_fingerprint: str,
        rows: Sequence[NormalizedAlbum],
        provenance: SourceProvenance,
    ) -> ImportResult:
        # Parser validation happens before this method.  This guard prevents a
        # future caller from turning a persistence mistake into partial data.
        expected_ranks = tuple(range(1, 501))
        if len(rows) != 500 or tuple(row.rank for row in rows) != expected_ranks:
            raise ValueError("validated source rows must contain ranks 1 through 500")

        with self._lock:
            previous = self._runs.get(idempotency_key)
            if previous:
                fingerprint, result = previous
                if fingerprint != request_fingerprint:
                    raise IdempotencyConflict("idempotency key request mismatch")
                return ImportResult(
                    import_run_id=result.import_run_id,
                    status="replayed",
                    parsed_row_count=result.parsed_row_count,
                    normalized_content_sha256=result.normalized_content_sha256,
                    catalog_source_id=result.catalog_source_id,
                    provenance=result.provenance,
                )

            snapshot = self._by_hash.get(provenance.normalized_content_sha256)
            if snapshot is None:
                snapshot = _StoredSnapshot(uuid4(), tuple(rows), provenance)
                self._by_hash[provenance.normalized_content_sha256] = snapshot

            result = ImportResult(
                import_run_id=uuid4(),
                status="succeeded",
                parsed_row_count=len(rows),
                normalized_content_sha256=provenance.normalized_content_sha256,
                catalog_source_id=snapshot.id,
                provenance=snapshot.provenance,
            )
            self._runs[idempotency_key] = (request_fingerprint, result)
            return result
