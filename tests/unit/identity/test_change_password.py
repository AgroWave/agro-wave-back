"""Unit tests for ChangePassword use case (AC-01-07, RN-04)."""

import pytest

from agrowave.modules.identity.application.use_cases.change_password import (
    ChangePassword,
    ChangePasswordCommand,
)
from agrowave.modules.identity.domain.errors import InvalidPasswordError
from agrowave.modules.identity.domain.models import User


class InMemoryUserRepository:
    """In-memory stub implementation of UserRepository."""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    def find_by_id(self, user_id):
        for user in self.users.values():
            if user.id == user_id:
                return user
        return None

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


def test_ac01_07_change_password_invalidates_previous_sessions() -> None:
    user_repo = InMemoryUserRepository()
    hasher = FakePasswordHasher()

    user = User(
        email="change@example.com",
        name="Change User",
        password_hash=hasher.hash("OldPassword123!"),
        email_confirmed=True,
    )
    user_repo.save(user)

    use_case = ChangePassword(user_repo=user_repo, hasher=hasher)

    command = ChangePasswordCommand(
        user_id=user.id,
        current_password="OldPassword123!",
        new_password="NewPassword456!",
    )
    use_case.execute(command)

    updated_user = user_repo.find_by_id(user.id)
    assert updated_user is not None
    assert updated_user.password_hash == "hashed_NewPassword456!"
    assert updated_user.password_changed_at is not None


def test_change_password_with_wrong_current_password_rejected() -> None:
    user_repo = InMemoryUserRepository()
    hasher = FakePasswordHasher()

    user = User(
        email="change@example.com",
        name="Change User",
        password_hash=hasher.hash("CorrectPassword123!"),
        email_confirmed=True,
    )
    user_repo.save(user)

    use_case = ChangePassword(user_repo=user_repo, hasher=hasher)

    command = ChangePasswordCommand(
        user_id=user.id,
        current_password="WrongPassword!",
        new_password="NewPassword456!",
    )

    with pytest.raises(InvalidPasswordError):
        use_case.execute(command)
