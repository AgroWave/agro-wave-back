"""Logout user use case implementation (UC-ID-07, RN-05)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from agrowave.modules.identity.domain.models import RevokedToken
from agrowave.modules.identity.domain.ports import TokenRevocationRepository


@dataclass(frozen=True)
class LogoutUserCommand:
    """Command payload for revoking an active access token."""

    jti: str
    user_id: UUID
    expires_at: datetime


class LogoutUser:
    """Revokes a JWT token JTI so it cannot be used again (RN-05)."""

    def __init__(self, revocation_repo: TokenRevocationRepository | Any) -> None:
        """Initializes the logout use case with revocation repository.

        Args:
            revocation_repo: Revoked token repository implementation.
        """
        self._revocation_repo = revocation_repo

    def execute(self, command: LogoutUserCommand) -> None:
        """Executes token revocation.

        Args:
            command: Command containing the JTI, user id, and expiration timestamp.
        """
        revoked_token = RevokedToken(
            jti=command.jti,
            user_id=command.user_id,
            expires_at=command.expires_at,
        )
        self._revocation_repo.save(revoked_token)
