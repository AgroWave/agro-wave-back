"""Unit tests for LogoutUser use case (AC-01-05, RN-05)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from agrowave.modules.identity.application.use_cases.logout import LogoutUser, LogoutUserCommand
from agrowave.modules.identity.domain.models import RevokedToken


class InMemoryTokenRevocationRepository:
    """In-memory stub implementation of TokenRevocationRepository."""

    def __init__(self) -> None:
        self.revoked: dict[str, RevokedToken] = {}

    def is_revoked(self, jti: str) -> bool:
        return jti in self.revoked

    def save(self, revoked_token: RevokedToken) -> None:
        self.revoked[revoked_token.jti] = revoked_token


def test_ac01_05_logout_revokes_token() -> None:
    repo = InMemoryTokenRevocationRepository()
    use_case = LogoutUser(revocation_repo=repo)

    user_id = uuid4()
    jti = "unique_jwt_token_id_123"
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    command = LogoutUserCommand(jti=jti, user_id=user_id, expires_at=expires_at)
    use_case.execute(command)

    assert repo.is_revoked(jti) is True
