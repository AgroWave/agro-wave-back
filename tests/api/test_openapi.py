"""OpenAPI contract verification (AC-00-04, ADR-09)."""

from fastapi.testclient import TestClient

from agrowave.main import create_app


def test_ac00_04_openapi_exposes_health_path() -> None:
    app = create_app(db_probe=lambda: True)
    client = TestClient(app)

    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/health" in schema["paths"]
    assert "get" in schema["paths"]["/api/v1/health"]
