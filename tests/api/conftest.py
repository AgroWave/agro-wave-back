"""Fixtures for API tests using SQLite in-memory database."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import agrowave.modules.simulation.infrastructure.row_models  # noqa: F401
from agrowave.main import create_app
from agrowave.modules.identity.presentation.dependencies import get_identity_engine
from agrowave.modules.profiles.presentation.dependencies import get_profiles_engine
from agrowave.modules.scenarios.presentation.dependencies import get_scenarios_engine
from agrowave.modules.simulation.presentation.dependencies import get_simulation_engine
from agrowave.modules.terrain.presentation.dependencies import get_terrain_engine


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
    app.dependency_overrides[get_profiles_engine] = lambda: api_engine
    app.dependency_overrides[get_terrain_engine] = lambda: api_engine
    app.dependency_overrides[get_scenarios_engine] = lambda: api_engine
    app.dependency_overrides[get_simulation_engine] = lambda: api_engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
