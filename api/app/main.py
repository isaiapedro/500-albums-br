"""Local API; catalogue imports are explicitly operator initiated only."""

from __future__ import annotations

import os
import secrets

from fastapi import FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from .catalogue_import import CatalogueImporter, ImportSourceError
from .catalogue_parser import CatalogueValidationError
from .catalogue_repository import IdempotencyConflict, ImportResult, InMemoryAtomicCatalogueRepository


class CatalogueImportRequest(BaseModel):
    dry_run: bool = Field(default=False, description="Validate only; do not write a catalogue snapshot.")


app = FastAPI(title="Local Album Journey API", version="0.1.0")
app.state.catalogue_repository = InMemoryAtomicCatalogueRepository()
app.state.catalogue_importer = CatalogueImporter(app.state.catalogue_repository)
# No fallback token: imports remain unavailable until the local operator sets it.
app.state.operator_token = os.environ.get("ALBUM_IMPORT_OPERATOR_TOKEN")


@app.get("/health", tags=["operations"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _result_payload(result: ImportResult) -> dict[str, object]:
    provenance = result.provenance
    return {
        "id": str(result.import_run_id),
        "status": result.status,
        "parsed_row_count": result.parsed_row_count,
        "normalized_content_sha256": result.normalized_content_sha256,
        "catalog_source_id": str(result.catalog_source_id) if result.catalog_source_id else None,
        "source": {
            "url": provenance.source_url,
            "license": provenance.source_license,
            "attribution": provenance.attribution_text,
            "retrieved_at": provenance.retrieved_at.isoformat(),
            "revision": provenance.source_revision,
        },
    }


@app.post("/api/v1/catalog/imports", status_code=status.HTTP_201_CREATED, tags=["catalogue"])
async def import_catalogue(
    payload: CatalogueImportRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    operator_token: str | None = Header(default=None, alias="X-Operator-Token"),
) -> dict[str, object]:
    """Fetch exactly the approved REST page, validate, then atomically upsert.

    The endpoint accepts no URL or source payload. This prevents callers and
    browsers from redirecting the importer to an unapproved source.
    """

    expected_token = request.app.state.operator_token
    if not expected_token or not operator_token or not secrets.compare_digest(operator_token, expected_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="operator_authorization_required")
    try:
        result = request.app.state.catalogue_importer.import_catalogue(
            idempotency_key=idempotency_key,
            dry_run=payload.dry_run,
        )
    except CatalogueValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except ImportSourceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    except IdempotencyConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _result_payload(result)
