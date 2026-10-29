"""Unit tests for identity CLI commands."""

import pytest
from sqlmodel import SQLModel, create_engine

from agrowave.modules.identity.cli import run_cli
from agrowave.modules.identity.domain.models import Role
from agrowave.modules.identity.infrastructure.sqlmodel_user_repository import (
    SqlModelUserRepository,
)


@pytest.fixture
def in_memory_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def test_ac01_08_create_admin_cli(in_memory_engine) -> None:
    repo = SqlModelUserRepository(in_memory_engine)

    exit_code = run_cli(
        [
            "create-admin",
            "--email",
            "admin@agrowave.com",
            "--name",
            "System Admin",
            "--password",
            "SuperAdminPass123!",
        ],
        engine=in_memory_engine,
    )

    assert exit_code == 0
    admin = repo.find_by_email("admin@agrowave.com")
    assert admin is not None
    assert admin.name == "System Admin"
    assert admin.role == Role.ADMIN
    assert admin.email_confirmed is True
