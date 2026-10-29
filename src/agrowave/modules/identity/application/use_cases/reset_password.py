"""Reset password use case implementation (UC-ID-05, RN-03, RN-04)."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from agrowave.modules.identity.domain.errors import InvalidOrExpiredTokenError
from agrowave.modules.identity.domain.models import OneTimeTokenPurpose
from agrowave.modules.identity.domain.ports import (
    OneTimeTokenRepository,
    PasswordHasher,
    UserRepository,
)


@dataclass(frozen=True)
class ResetPasswordCommand:
    """Command payload for completing a password reset."""

    token: str
    new_password: str


class ResetPassword:
    """Validates a password reset token and applies the new password."""

    def __init__(
        self,
        user_repo: UserRepository | Any,
        token_repo: OneTimeTokenRepository | Any,
        hasher: PasswordHasher | Any,
    ) -> None:
        """Initializes the reset password use case with dependencies.

        Args:
            user_repo: User repository implementation.
            token_repo: Single-use token repository implementation.
            hasher: Password hasher implementation.
        """
        self._user_repo = user_repo
        self._token_repo = token_repo
        self._hasher = hasher

    def execute(self, command: ResetPasswordCommand) -> None:
        """Executes the password reset.

        Args:
            command: Reset command containing the token and new password.

        Raises:
            InvalidOrExpiredTokenError: If the token is invalid, expired, or consumed (RN-03).
        """
        token_hash = hashlib.sha256(command.token.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)

        token_record = self._token_repo.find_by_hash_and_purpose(
            token_hash=token_hash,
            purpose=OneTimeTokenPurpose.PASSWORD_RESET,
        )
        if token_record is None or not token_record.is_valid(now):
            raise InvalidOrExpiredTokenError()

        user = self._user_repo.find_by_id(token_record.user_id)
        if user is None:
            raise InvalidOrExpiredTokenError()

        new_password_hash = self._hasher.hash(command.new_password)
        user.change_password(new_password_hash)
        self._user_repo.save(user)

        token_record.mark_used(now)
        self._token_repo.save(token_record)
