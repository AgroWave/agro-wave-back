"""Unit tests for ConfirmEmail use case (AC-01-02, RN-02, RN-03)."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from agrowave.modules.identity.application.use_cases.confirm_email import (
    ConfirmEmail,
    ConfirmEmailCommand,
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


def test_ac01_02_confirm_email_activates_account() -> None:
    user_repo = InMemoryUserRepository()
    token_repo = InMemoryOneTimeTokenRepository()

    user = User(
        email="unconfirmed@example.com",
        name="Test User",
        password_hash="any_hash",
        email_confirmed=False,
    )
    user_repo.save(user)

    raw_token = "valid_sample_token_123"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token_record = OneTimeToken(
        user_id=user.id,
        purpose=OneTimeTokenPurpose.EMAIL_CONFIRMATION,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    token_repo.save(token_record)

    use_case = ConfirmEmail(user_repo=user_repo, token_repo=token_repo)
    use_case.execute(ConfirmEmailCommand(token=raw_token))

    updated_user = user_repo.find_by_id(user.id)
    assert updated_user is not None
    assert updated_user.email_confirmed is True

    # Token must now be marked as used
    consumed_token = token_repo.find_by_hash_and_purpose(
        token_hash, OneTimeTokenPurpose.EMAIL_CONFIRMATION
    )
    assert consumed_token is not None
    assert consumed_token.used_at is not None


def test_confirm_email_with_expired_or_invalid_token_rejected() -> None:
    user_repo = InMemoryUserRepository()
    token_repo = InMemoryOneTimeTokenRepository()

    use_case = ConfirmEmail(user_repo=user_repo, token_repo=token_repo)

    with pytest.raises(InvalidOrExpiredTokenError):
        use_case.execute(ConfirmEmailCommand(token="non_existent_token"))
