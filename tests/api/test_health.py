"""Health endpoint tests using a mock database probe (AC-00-02, AC-00-03)."""

from fastapi.testclient import TestClient

from agrowave.main import create_app


def test_ac00_02_health_ok_when_database_reachable() -> None:
    app = create_app(db_probe=lambda: True)
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_ac00_03_health_degraded_when_database_unreachable() -> None:
    app = create_app(db_probe=lambda: False)
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
