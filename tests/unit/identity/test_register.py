"""Unit tests for the RegisterUser use case (AC-29, AC-01-01)."""

import pytest

from agrowave.modules.identity.application.use_cases.register import (
    RegisterUser,
    RegisterUserCommand,
)
from agrowave.modules.identity.domain.errors import DuplicateEmailError
from agrowave.modules.identity.domain.models import Role, User


class InMemoryUserRepository:
    """In-memory stub implementation of UserRepository."""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    def find_by_email(self, email: str) -> User | None:
        return self.users.get(email.lower())

    def save(self, user: User) -> None:
        self.users[user.email.lower()] = user


class InMemoryOneTimeTokenRepository:
    """In-memory stub implementation of OneTimeTokenRepository."""

    def __init__(self) -> None:
        self.tokens: list[dict] = []

    def save(self, token_record: dict) -> None:
        self.tokens.append(token_record)


class FakePasswordHasher:
    """Stub password hasher for fast unit tests."""

    def hash(self, password: str) -> str:
        return f"hashed_{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed_{password}"


class SpyNotifier:
    """Spy notifier capturing sent email dispatches."""

    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    def send_confirmation_email(self, to_email: str, token: str) -> None:
        self.sent_messages.append({"to": to_email, "token": token, "type": "confirmation"})

    def send_password_reset_email(self, to_email: str, token: str) -> None:
        self.sent_messages.append({"to": to_email, "token": token, "type": "reset"})


def test_ac29_duplicate_email_rejected() -> None:
    user_repo = InMemoryUserRepository()
    token_repo = InMemoryOneTimeTokenRepository()
    hasher = FakePasswordHasher()
    notifier = SpyNotifier()

    use_case = RegisterUser(
        user_repo=user_repo,
        token_repo=token_repo,
        hasher=hasher,
        notifier=notifier,
    )

    command = RegisterUserCommand(
        email="juan@example.com",
        name="Juan Perez",
        password="ValidPassword123!",
    )
    use_case.execute(command)

    # Attempting to register again with the same email must raise DuplicateEmailError (RN-01)
    with pytest.raises(DuplicateEmailError):
        use_case.execute(command)


def test_ac01_01_register_creates_inactive_user_with_token() -> None:
    user_repo = InMemoryUserRepository()
    token_repo = InMemoryOneTimeTokenRepository()
    hasher = FakePasswordHasher()
    notifier = SpyNotifier()

    use_case = RegisterUser(
        user_repo=user_repo,
        token_repo=token_repo,
        hasher=hasher,
        notifier=notifier,
    )

    command = RegisterUserCommand(
        email="maria@example.com",
        name="Maria Gomez",
        password="SecurePassword456!",
    )
    user = use_case.execute(command)

    assert user.email == "maria@example.com"
    assert user.name == "Maria Gomez"
    assert user.email_confirmed is False
    assert user.role == Role.USER
    assert user.password_hash == "hashed_SecurePassword456!"
    assert len(notifier.sent_messages) == 1
    assert notifier.sent_messages[0]["to"] == "maria@example.com"
    assert len(token_repo.tokens) == 1
