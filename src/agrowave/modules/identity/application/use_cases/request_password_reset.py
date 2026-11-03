"""Request password reset use case implementation (UC-ID-04, RN-03)."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from agrowave.modules.identity.domain.models import OneTimeToken, OneTimeTokenPurpose
from agrowave.modules.identity.domain.ports import Notifier, OneTimeTokenRepository, UserRepository


@dataclass(frozen=True)
class RequestPasswordResetCommand:
    """Command payload for initiating a password reset."""

    email: str


class RequestPasswordReset:
    """Initiates a password reset flow without revealing user existence."""

    def __init__(
        self,
        user_repo: UserRepository | Any,
        token_repo: OneTimeTokenRepository | Any,
        notifier: Notifier | Any,
    ) -> None:
        """Initializes the request password reset use case with dependencies.

        Args:
            user_repo: User repository implementation.
            token_repo: Single-use token repository implementation.
            notifier: Notification dispatcher implementation.
        """
        self._user_repo = user_repo
        self._token_repo = token_repo
        self._notifier = notifier

    def execute(self, command: RequestPasswordResetCommand) -> None:
        """Executes the request. If the user exists, sends a reset email.

        Args:
            command: Command containing the target email address.
        """
        user = self._user_repo.find_by_email(command.email)
        if user is None:
            return

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        token_record = OneTimeToken(
            user_id=user.id,
            purpose=OneTimeTokenPurpose.PASSWORD_RESET,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._token_repo.save(token_record)

        self._notifier.send_password_reset_email(user.email, raw_token)
