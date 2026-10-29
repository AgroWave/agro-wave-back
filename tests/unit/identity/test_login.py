"""Unit tests for the LoginUser use case (AC-30, AC-01-03)."""

import pytest

from agrowave.modules.identity.application.use_cases.login import (
    LoginResult,
    LoginUser,
    LoginUserCommand,
)
from agrowave.modules.identity.domain.errors import InvalidCredentialsError, UnconfirmedAccountError
from agrowave.modules.identity.domain.models import Role, User


class InMemoryUserRepository:
    """In-memory stub implementation of UserRepository."""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    def find_by_email(self, email: str) -> User | None:
        return self.users.get(email.lower())

    def save(self, user: User) -> None:
        self.users[user.email.lower()] = user


class FakePasswordHasher:
    """Stub password hasher for fast unit tests."""

    def hash(self, password: str) -> str:
        return f"hashed_{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed_{password}"


class FakeTokenService:
    """Stub token service issuing predictable access tokens."""

    def create_access_token(self, user_id, email, role, expires_in_seconds=900) -> str:
        return f"jwt_token_for_{email}_{role}"

    def decode_access_token(self, token: str) -> dict:
        return {}


def test_ac30_unconfirmed_account_rejected() -> None:
    user_repo = InMemoryUserRepository()
    hasher = FakePasswordHasher()
    token_service = FakeTokenService()

    # Create unconfirmed user
    unconfirmed_user = User(
        email="unconfirmed@example.com",
        name="Test User",
        password_hash=hasher.hash("Secret123!"),
        email_confirmed=False,
    )
    user_repo.save(unconfirmed_user)

    use_case = LoginUser(user_repo=user_repo, hasher=hasher, token_service=token_service)

    command = LoginUserCommand(
        email="unconfirmed@example.com",
        password="Secret123!",
    )

    with pytest.raises(UnconfirmedAccountError):
        use_case.execute(command)


def test_ac01_03_login_returns_valid_jwt() -> None:
    user_repo = InMemoryUserRepository()
    hasher = FakePasswordHasher()
    token_service = FakeTokenService()

    confirmed_user = User(
        email="active@example.com",
        name="Active User",
        password_hash=hasher.hash("Secret123!"),
        role=Role.USER,
        email_confirmed=True,
    )
    user_repo.save(confirmed_user)

    use_case = LoginUser(user_repo=user_repo, hasher=hasher, token_service=token_service)

    command = LoginUserCommand(
        email="active@example.com",
        password="Secret123!",
    )
    result = use_case.execute(command)

    assert isinstance(result, LoginResult)
    assert result.access_token == "jwt_token_for_active@example.com_USER"
    assert result.token_type == "bearer"
    assert result.user.email == "active@example.com"
    assert result.user.email_confirmed is True


def test_login_with_invalid_credentials_rejected() -> None:
    user_repo = InMemoryUserRepository()
    hasher = FakePasswordHasher()
    token_service = FakeTokenService()

    use_case = LoginUser(user_repo=user_repo, hasher=hasher, token_service=token_service)

    command = LoginUserCommand(
        email="nonexistent@example.com",
        password="AnyPassword",
    )

    with pytest.raises(InvalidCredentialsError):
        use_case.execute(command)
