"""Confirm email use case implementation (UC-ID-02, RN-02, RN-03)."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from agrowave.modules.identity.domain.errors import InvalidOrExpiredTokenError
from agrowave.modules.identity.domain.models import OneTimeTokenPurpose
from agrowave.modules.identity.domain.ports import OneTimeTokenRepository, UserRepository


@dataclass(frozen=True)
class ConfirmEmailCommand:
    """Command payload for confirming an email address."""

    token: str


class ConfirmEmail:
    """Validates a single-use confirmation token and activates the user account."""

    def __init__(
        self,
        user_repo: UserRepository | Any,
        token_repo: OneTimeTokenRepository | Any,
    ) -> None:
        """Initializes the confirm email use case with dependencies.

        Args:
            user_repo: User repository implementation.
            token_repo: Single-use token repository implementation.
        """
        self._user_repo = user_repo
        self._token_repo = token_repo

    def execute(self, command: ConfirmEmailCommand) -> None:
        """Executes email confirmation.

        Args:
            command: Confirmation command containing the plain verification token.

        Raises:
            InvalidOrExpiredTokenError: If the token is invalid, expired, or consumed (RN-03).
        """
        token_hash = hashlib.sha256(command.token.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)

        token_record = self._token_repo.find_by_hash_and_purpose(
            token_hash=token_hash,
            purpose=OneTimeTokenPurpose.EMAIL_CONFIRMATION,
        )
        if token_record is None or not token_record.is_valid(now):
            raise InvalidOrExpiredTokenError()

        user = self._user_repo.find_by_id(token_record.user_id)
        if user is None:
            raise InvalidOrExpiredTokenError()

        user.confirm_email()
        self._user_repo.save(user)

        token_record.mark_used(now)
        self._token_repo.save(token_record)
