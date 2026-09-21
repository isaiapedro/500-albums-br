from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.project_repository import InMemoryProjectRepository


def test_journey_uses_a_readable_collision_safe_url() -> None:
    app.state.project_repository = InMemoryProjectRepository()
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/journeys",
            json={"name": "Um Ano e Meio de Música", "timezone": "America/Sao_Paulo"},
        )
        second = client.post(
            "/api/v1/journeys",
            json={"name": "Um Ano e Meio de Música", "timezone": "America/Sao_Paulo"},
        )
        page = client.get("/journey/um-ano-e-meio-de-musica")

    assert first.status_code == 201
    assert first.json()["slug"] == "um-ano-e-meio-de-musica"
    assert second.json()["slug"] == "um-ano-e-meio-de-musica-2"
    assert page.status_code == 200
    assert "500 Discos Brasileiros" in page.text


def test_journey_requires_a_real_name_and_iana_timezone() -> None:
    app.state.project_repository = InMemoryProjectRepository()
    with TestClient(app) as client:
        blank_name = client.post("/api/v1/journeys", json={"name": "  ", "timezone": "America/Sao_Paulo"})
        invalid_timezone = client.post("/api/v1/journeys", json={"name": "Valid", "timezone": "Mars/Olympus"})

    assert blank_name.status_code == 422
    assert invalid_timezone.status_code == 422
