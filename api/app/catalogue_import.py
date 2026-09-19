"""Operator-only import orchestration for the one approved catalogue source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from typing import Callable
from urllib.request import Request, urlopen
from uuid import uuid4

from .catalogue_parser import CatalogueValidationError, normalized_sha256, parse_and_validate_html
from .catalogue_repository import CatalogueRepository, ImportResult, SourceProvenance


SOURCE_URL = (
    "https://pt.wikipedia.org/api/rest_v1/page/html/"
    "Lista_dos_500_maiores_discos_da_m%C3%BAsica_brasileira_pelo_Discoteca_B%C3%A1sica"
)
SOURCE_LICENSE = "CC BY-SA 4.0"
ATTRIBUTION = (
    "Source: Portuguese Wikipedia, Lista dos 500 maiores discos da música "
    "brasileira pelo Discoteca Básica (CC BY-SA)."
)


class ImportSourceError(RuntimeError):
    """Safe source failure code; it intentionally contains no server response."""


@dataclass(frozen=True)
class FetchedHtml:
    html: str
    retrieved_at: datetime
    source_revision: str | None


def fetch_approved_source(timeout: float = 20.0) -> FetchedHtml:
    """Fetch the fixed REST endpoint only when an operator starts an import."""

    request = Request(
        SOURCE_URL,
        headers={"Accept": "text/html", "User-Agent": "album-journey-mvp/0.1"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed approved URL
            body = response.read()
            revision = response.headers.get("ETag") or response.headers.get("Content-Revision-Id")
    except Exception as error:
        # Do not expose the remote URL/body/header/error details to audit/API logs.
        raise ImportSourceError("approved_source_unavailable") from error
    try:
        html = body.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ImportSourceError("approved_source_invalid_encoding") from error
    finally:
        del body
    return FetchedHtml(html=html, retrieved_at=datetime.now(UTC), source_revision=revision)


class CatalogueImporter:
    """Coordinates parse-before-write import and a non-persisting dry run."""

    def __init__(
        self,
        repository: CatalogueRepository,
        fetch_html: Callable[[], FetchedHtml] = fetch_approved_source,
    ) -> None:
        self.repository = repository
        self.fetch_html = fetch_html

    def import_catalogue(self, *, idempotency_key: str, dry_run: bool) -> ImportResult:
        fetched = self.fetch_html()
        retrieved_at = fetched.retrieved_at
        source_revision = fetched.source_revision
        try:
            rows = parse_and_validate_html(fetched.html)
        finally:
            # The source representation is transient.  Neither repository nor
            # result has a raw-payload field, and parser errors are sanitized.
            del fetched

        provenance = SourceProvenance(
            source_url=SOURCE_URL,
            source_license=SOURCE_LICENSE,
            attribution_text=ATTRIBUTION,
            retrieved_at=retrieved_at,
            source_revision=source_revision,
            normalized_content_sha256=normalized_sha256(rows),
        )
        # Use a deterministic request fingerprint distinct from source content.
        # The key's purpose is a request replay, so dry-run is part of it.
        request_fingerprint = hashlib.sha256(
            f"catalogue-import:v1:dry_run={str(dry_run).lower()}".encode("ascii")
        ).hexdigest()
        if dry_run:
            return ImportResult(
                import_run_id=uuid4(),
                status="dry_run",
                parsed_row_count=len(rows),
                normalized_content_sha256=provenance.normalized_content_sha256,
                catalog_source_id=None,
                provenance=provenance,
            )
        return self.repository.upsert_snapshot(
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            rows=rows,
            provenance=provenance,
        )
