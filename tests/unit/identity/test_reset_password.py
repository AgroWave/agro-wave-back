"""Unit tests for password reset use cases (AC-31, AC-01-06, RN-03, RN-04)."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from agrowave.modules.identity.application.use_cases.request_password_reset import (
    RequestPasswordReset,
    RequestPasswordResetCommand,
)
from agrowave.modules.identity.application.use_cases.reset_password import (
    ResetPassword,
    ResetPasswordCommand,
)
from agrowave.modules.identity.domain.errors import InvalidOrExpiredTokenError
from agrowave.modules.identity.domain.models import OneTimeToken, OneTimeTokenPurpose, User


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


class InMemoryOneTimeTokenRepository:
    """In-memory stub implementation of OneTimeTokenRepository."""

    def __init__(self) -> None:
        self.tokens: list[OneTimeToken] = []

    def find_by_hash_and_purpose(
        self, token_hash: str, purpose: OneTimeTokenPurpose
    ) -> OneTimeToken | None:
        for token in self.tokens:
            if token.token_hash == token_hash and token.purpose == purpose:
                return token
        return None

    def save(self, token: OneTimeToken) -> None:
        for i, existing in enumerate(self.tokens):
            if existing.id == token.id:
                self.tokens[i] = token
                return
        self.tokens.append(token)


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


def test_ac01_06_request_reset_always_succeeds_and_sends_email_if_user_exists() -> None:
    user_repo = InMemoryUserRepository()
    token_repo = InMemoryOneTimeTokenRepository()
    notifier = SpyNotifier()

    user = User(
        email="existing@example.com",
        name="Existing User",
        password_hash="old_hash",
        email_confirmed=True,
    )
    user_repo.save(user)

    use_case = RequestPasswordReset(user_repo=user_repo, token_repo=token_repo, notifier=notifier)

    # Calling with existing user creates token and sends email
    use_case.execute(RequestPasswordResetCommand(email="existing@example.com"))
    assert len(notifier.sent_messages) == 1
    assert notifier.sent_messages[0]["to"] == "existing@example.com"
    assert len(token_repo.tokens) == 1
    assert token_repo.tokens[0].purpose == OneTimeTokenPurpose.PASSWORD_RESET

    # Calling with non-existing user does not raise error and sends no email
    use_case.execute(RequestPasswordResetCommand(email="nonexistent@example.com"))
    assert len(notifier.sent_messages) == 1  # Unchanged


def test_ac31_expired_or_used_token_rejected() -> None:
    user_repo = InMemoryUserRepository()
    token_repo = InMemoryOneTimeTokenRepository()
    hasher = FakePasswordHasher()

    user = User(
        email="reset@example.com",
        name="Reset User",
        password_hash="initial_hash",
        email_confirmed=True,
    )
    user_repo.save(user)

    # 1. Expired token
    expired_raw_token = "expired_token_abc"
    expired_hash = hashlib.sha256(expired_raw_token.encode("utf-8")).hexdigest()
    expired_record = OneTimeToken(
        user_id=user.id,
        purpose=OneTimeTokenPurpose.PASSWORD_RESET,
        token_hash=expired_hash,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    token_repo.save(expired_record)

    reset_use_case = ResetPassword(user_repo=user_repo, token_repo=token_repo, hasher=hasher)

    with pytest.raises(InvalidOrExpiredTokenError):
        reset_use_case.execute(
            ResetPasswordCommand(token=expired_raw_token, new_password="NewPassword123!")
        )

    # 2. Valid token can be used once
    valid_raw_token = "valid_token_xyz"
    valid_hash = hashlib.sha256(valid_raw_token.encode("utf-8")).hexdigest()
    valid_record = OneTimeToken(
        user_id=user.id,
        purpose=OneTimeTokenPurpose.PASSWORD_RESET,
        token_hash=valid_hash,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    token_repo.save(valid_record)

    reset_use_case.execute(
        ResetPasswordCommand(token=valid_raw_token, new_password="NewPassword123!")
    )

    updated_user = user_repo.find_by_id(user.id)
    assert updated_user is not None
    assert updated_user.password_hash == "hashed_NewPassword123!"
    assert updated_user.password_changed_at is not None

    # Re-using the same token must now fail with InvalidOrExpiredTokenError (RN-03)
    with pytest.raises(InvalidOrExpiredTokenError):
        reset_use_case.execute(
            ResetPasswordCommand(token=valid_raw_token, new_password="AnotherPassword456!")
        )
