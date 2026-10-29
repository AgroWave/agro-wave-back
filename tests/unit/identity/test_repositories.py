"""Unit tests for SQLModel repository implementations."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import SQLModel, create_engine

from agrowave.modules.identity.domain.models import (
    OneTimeToken,
    OneTimeTokenPurpose,
    RevokedToken,
    Role,
    User,
)
from agrowave.modules.identity.infrastructure.sqlmodel_token_repositories import (
    SqlModelOneTimeTokenRepository,
    SqlModelTokenRevocationRepository,
)
from agrowave.modules.identity.infrastructure.sqlmodel_user_repository import (
    SqlModelUserRepository,
)


@pytest.fixture
def in_memory_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def test_sqlmodel_user_repository_save_and_find(in_memory_engine) -> None:
    repo = SqlModelUserRepository(in_memory_engine)
    user = User(
        email="test@example.com",
        name="Test User",
        password_hash="argon2hash",
        role=Role.USER,
        email_confirmed=False,
    )

    repo.save(user)

    found_by_id = repo.find_by_id(user.id)
    assert found_by_id is not None
    assert found_by_id.email == "test@example.com"
    assert found_by_id.name == "Test User"
    assert found_by_id.email_confirmed is False

    found_by_email = repo.find_by_email("TEST@EXAMPLE.COM")
    assert found_by_email is not None
    assert found_by_email.id == user.id

    # Update
    found_by_id.confirm_email()
    repo.save(found_by_id)

    updated = repo.find_by_id(user.id)
    assert updated is not None
    assert updated.email_confirmed is True


def test_sqlmodel_token_repositories(in_memory_engine) -> None:
    token_repo = SqlModelOneTimeTokenRepository(in_memory_engine)
    revocation_repo = SqlModelTokenRevocationRepository(in_memory_engine)

    user_id = uuid4()
    now = datetime.now(UTC)
    token = OneTimeToken(
        user_id=user_id,
        purpose=OneTimeTokenPurpose.EMAIL_CONFIRMATION,
        token_hash="hash123",
        expires_at=now + timedelta(hours=24),
    )

    token_repo.save(token)

    found = token_repo.find_by_hash_and_purpose("hash123", OneTimeTokenPurpose.EMAIL_CONFIRMATION)
    assert found is not None
    assert found.user_id == user_id
    assert found.used_at is None

    found.mark_used(now)
    token_repo.save(found)

    updated = token_repo.find_by_hash_and_purpose("hash123", OneTimeTokenPurpose.EMAIL_CONFIRMATION)
    assert updated is not None
    assert updated.used_at is not None

    # Revocation
    assert revocation_repo.is_revoked("jti-123") is False
    revocation_repo.save(
        RevokedToken(jti="jti-123", user_id=user_id, expires_at=now + timedelta(minutes=15))
    )
    assert revocation_repo.is_revoked("jti-123") is True
