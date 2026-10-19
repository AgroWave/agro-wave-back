"""Integration test verifying health endpoint against a real PostgreSQL database (AC-00-02)."""

import pytest
from fastapi.testclient import TestClient

from agrowave.container import create_container_app

pytestmark = pytest.mark.integration


def test_ac00_02_health_ok_against_real_database() -> None:
    app = create_container_app()
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
