"""Integration test for admin CLI against real database."""

import pytest
from sqlmodel import SQLModel, create_engine

from agrowave.modules.identity.cli import run_cli
from agrowave.modules.identity.domain.models import Role
from agrowave.modules.identity.infrastructure.sqlmodel_user_repository import (
    SqlModelUserRepository,
)


@pytest.mark.integration
def test_ac01_08_create_admin_cli(test_database_url: str) -> None:
    engine = create_engine(test_database_url)
    SQLModel.metadata.create_all(engine)
    repo = SqlModelUserRepository(engine)

    exit_code = run_cli(
        [
            "create-admin",
            "--email",
            "integration_admin@agrowave.com",
            "--name",
            "Integration Admin",
            "--password",
            "AdminPass1234!",
        ],
        engine=engine,
    )

    assert exit_code == 0
    admin = repo.find_by_email("integration_admin@agrowave.com")
    assert admin is not None
    assert admin.role == Role.ADMIN
    assert admin.email_confirmed is True
