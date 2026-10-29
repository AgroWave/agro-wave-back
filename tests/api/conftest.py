"""Fixtures for API tests using SQLite in-memory database."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from agrowave.main import create_app
from agrowave.modules.identity.presentation.dependencies import get_identity_engine


@pytest.fixture
def api_engine():
    """Provides an in-memory SQLite engine with all SQLModel tables created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(api_engine) -> Iterator[TestClient]:
    """Provides a TestClient wired to the in-memory engine."""
    app = create_app()
    app.dependency_overrides[get_identity_engine] = lambda: api_engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
