"""Fixture-only integration coverage for the catalogue-import HTTP boundary."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.catalogue_import import (
    ATTRIBUTION,
    SOURCE_LICENSE,
    SOURCE_URL,
    CatalogueImporter,
    FetchedHtml,
)
from app.catalogue_repository import InMemoryAtomicCatalogueRepository
from app.main import app


RAW_HTML_SENTINEL = "RAW_HTML_MUST_NOT_BE_PERSISTED"
OPERATOR_TOKEN = "test-operator-token"


def _ranking_html(*, row_count: int = 500) -> str:
    """A deterministic in-memory stand-in for the approved REST response."""

    rows = "".join(
        "<tr>"
        f"<td>{rank}</td><td>Album {rank}</td><td>2000</td><td>Artist {rank}</td>"
        "</tr>"
        for rank in range(1, row_count + 1)
    )
    return (
        f"<aside>{RAW_HTML_SENTINEL}</aside>"
        '<table class="wikitable sortable">'
        "<tr><th>Posição</th><th>Título</th><th>Ano de lançamento</th>"
        "<th>Artista(s)</th></tr>"
        f"{rows}</table>"
    )


@pytest.fixture
def configured_client() -> tuple[TestClient, InMemoryAtomicCatalogueRepository]:
    """Wire the real importer to a local-only 500-row HTML response."""

    repository = InMemoryAtomicCatalogueRepository()
    fixture = FetchedHtml(
        html=_ranking_html(),
        retrieved_at=datetime(2026, 9, 19, tzinfo=UTC),
        source_revision='"fixture-revision"',
    )
    app.state.catalogue_repository = repository
    app.state.catalogue_importer = CatalogueImporter(repository, fetch_html=lambda: fixture)
    app.state.operator_token = OPERATOR_TOKEN
    with TestClient(app) as client:
        yield client, repository


def _post_import(client: TestClient, *, idempotency_key: str, dry_run: bool = False):
    return client.post(
        "/api/v1/catalog/imports",
        headers={
            "X-Operator-Token": OPERATOR_TOKEN,
            "Idempotency-Key": idempotency_key,
        },
        json={"dry_run": dry_run},
    )


def test_dry_run_reports_validated_provenance_without_writing_catalogue(
    configured_client: tuple[TestClient, InMemoryAtomicCatalogueRepository],
) -> None:
    client, repository = configured_client

    response = _post_import(client, idempotency_key="fixture-dry-run", dry_run=True)

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "dry_run"
    assert payload["parsed_row_count"] == 500
    assert len(payload["normalized_content_sha256"]) == 64
    assert payload["catalog_source_id"] is None
    assert payload["source"] == {
        "url": SOURCE_URL,
        "license": SOURCE_LICENSE,
        "attribution": ATTRIBUTION,
        "retrieved_at": "2026-09-19T00:00:00+00:00",
        "revision": '"fixture-revision"',
    }
    assert repository.snapshot_count == 0
    assert repository.album_count == 0


def test_import_upserts_atomically_idempotently_and_never_retains_raw_html(
    configured_client: tuple[TestClient, InMemoryAtomicCatalogueRepository],
) -> None:
    client, repository = configured_client

    first = _post_import(client, idempotency_key="fixture-commit")
    assert first.status_code == 201
    assert first.json()["status"] == "succeeded"
    assert repository.snapshot_count == 1
    assert repository.album_count == 500

    replay = _post_import(client, idempotency_key="fixture-commit")
    assert replay.status_code == 201
    assert replay.json()["status"] == "replayed"
    assert replay.json()["catalog_source_id"] == first.json()["catalog_source_id"]
    assert repository.snapshot_count == 1
    assert repository.album_count == 500

    # A different request key with identical normalized content reuses the
    # immutable content snapshot rather than creating duplicate album rows.
    same_content = _post_import(client, idempotency_key="fixture-same-content")
    assert same_content.status_code == 201
    assert same_content.json()["status"] == "succeeded"
    assert same_content.json()["catalog_source_id"] == first.json()["catalog_source_id"]
    assert repository.snapshot_count == 1
    assert repository.album_count == 500

    persisted = repr(repository.__dict__)
    assert RAW_HTML_SENTINEL not in persisted
    assert RAW_HTML_SENTINEL not in first.text


def test_invalid_fixture_leaves_no_partial_catalogue_write() -> None:
    repository = InMemoryAtomicCatalogueRepository()
    invalid_fixture = FetchedHtml(
        html=_ranking_html(row_count=499),
        retrieved_at=datetime(2026, 9, 19, tzinfo=UTC),
        source_revision=None,
    )
    app.state.catalogue_repository = repository
    app.state.catalogue_importer = CatalogueImporter(
        repository, fetch_html=lambda: invalid_fixture
    )
    app.state.operator_token = OPERATOR_TOKEN
    with TestClient(app) as client:
        response = _post_import(client, idempotency_key="invalid-fixture")

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_row_count"
    assert RAW_HTML_SENTINEL not in response.text
    assert repository.snapshot_count == 0
    assert repository.album_count == 0
