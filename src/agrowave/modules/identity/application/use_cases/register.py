"""Register user use case implementation (UC-ID-01, RN-01, RN-03)."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from agrowave.modules.identity.domain.errors import DuplicateEmailError
from agrowave.modules.identity.domain.models import OneTimeToken, OneTimeTokenPurpose, User
from agrowave.modules.identity.domain.ports import (
    Notifier,
    OneTimeTokenRepository,
    PasswordHasher,
    UserRepository,
)


@dataclass(frozen=True)
class RegisterUserCommand:
    """Command payload for registering a new user."""

    email: str
    name: str
    password: str


class RegisterUser:
    """Registers a new user, hashes credentials, and dispatches a confirmation token."""

    def __init__(
        self,
        user_repo: UserRepository | Any,
        token_repo: OneTimeTokenRepository | Any,
        hasher: PasswordHasher | Any,
        notifier: Notifier | Any,
    ) -> None:
        """Initializes the register use case with dependencies.

        Args:
            user_repo: User repository implementation.
            token_repo: Single-use token repository implementation.
            hasher: Password hasher implementation.
            notifier: Notification dispatcher implementation.
        """
        self._user_repo = user_repo
        self._token_repo = token_repo
        self._hasher = hasher
        self._notifier = notifier

    def execute(self, command: RegisterUserCommand) -> User:
        """Executes user registration.

        Args:
            command: Registration command with email, name, and plain password.

        Returns:
            The created User aggregate in unconfirmed state.

        Raises:
            DuplicateEmailError: If the email is already in use (RN-01).
        """
        existing = self._user_repo.find_by_email(command.email)
        if existing is not None:
            raise DuplicateEmailError(command.email)

        password_hash = self._hasher.hash(command.password)
        user = User(
            email=command.email,
            name=command.name,
            password_hash=password_hash,
            email_confirmed=False,
        )
        self._user_repo.save(user)

        # Generate single-use confirmation token (24 hours validity, RN-03)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(hours=24)

        token_record = OneTimeToken(
            user_id=user.id,
            purpose=OneTimeTokenPurpose.EMAIL_CONFIRMATION,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._token_repo.save(token_record)

        self._notifier.send_confirmation_email(user.email, raw_token)
        return user
