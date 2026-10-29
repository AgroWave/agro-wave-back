"""SQLModel implementations of token-related repositories."""

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from agrowave.modules.identity.domain.models import (
    OneTimeToken,
    OneTimeTokenPurpose,
    RevokedToken,
)
from agrowave.modules.identity.domain.ports import (
    OneTimeTokenRepository,
    TokenRevocationRepository,
)
from agrowave.modules.identity.infrastructure.row_models import (
    IdentityOneTimeTokenRow,
    IdentityRevokedTokenRow,
)


class SqlModelOneTimeTokenRepository(OneTimeTokenRepository):
    """Adapter implementing OneTimeTokenRepository port backed by PostgreSQL / SQLModel."""

    def __init__(self, engine: Engine) -> None:
        """Initializes the repository with a database engine.

        Args:
            engine: SQLAlchemy/SQLModel database engine.
        """
        self._engine = engine

    def _to_entity(self, row: IdentityOneTimeTokenRow) -> OneTimeToken:
        return OneTimeToken(
            id=row.id,
            user_id=row.user_id,
            purpose=OneTimeTokenPurpose(row.purpose),
            token_hash=row.token_hash,
            expires_at=row.expires_at,
            used_at=row.used_at,
        )

    def find_by_hash_and_purpose(
        self, token_hash: str, purpose: OneTimeTokenPurpose
    ) -> OneTimeToken | None:
        """Finds a single-use token by its hash and purpose.

        Args:
            token_hash: SHA-256 hash string of the token.
            purpose: Expected purpose of the token.

        Returns:
            OneTimeToken entity if found, None otherwise.
        """
        with Session(self._engine) as session:
            statement = select(IdentityOneTimeTokenRow).where(
                IdentityOneTimeTokenRow.token_hash == token_hash,
                IdentityOneTimeTokenRow.purpose == purpose.value,
            )
            row = session.exec(statement).first()
            return self._to_entity(row) if row else None

    def save(self, token: OneTimeToken) -> None:
        """Saves or updates a single-use token entity.

        Args:
            token: The token domain entity to persist.
        """
        with Session(self._engine) as session:
            row = session.get(IdentityOneTimeTokenRow, token.id)
            if row is None:
                row = IdentityOneTimeTokenRow(
                    id=token.id,
                    user_id=token.user_id,
                    purpose=token.purpose.value,
                    token_hash=token.token_hash,
                    expires_at=token.expires_at,
                    used_at=token.used_at,
                )
                session.add(row)
            else:
                row.used_at = token.used_at
            session.commit()


class SqlModelTokenRevocationRepository(TokenRevocationRepository):
    """Adapter implementing TokenRevocationRepository backed by SQLModel."""

    def __init__(self, engine: Engine) -> None:
        """Initializes the repository with a database engine.

        Args:
            engine: SQLAlchemy/SQLModel database engine.
        """
        self._engine = engine

    def is_revoked(self, jti: str) -> bool:
        """Checks if a given token JTI is recorded as revoked.

        Args:
            jti: Unique JWT ID claim.

        Returns:
            True if revoked, False otherwise.
        """
        with Session(self._engine) as session:
            row = session.get(IdentityRevokedTokenRow, jti)
            return row is not None

    def save(self, revoked_token: RevokedToken) -> None:
        """Registers a token JTI as revoked.

        Args:
            revoked_token: RevokedToken entity.
        """
        with Session(self._engine) as session:
            row = IdentityRevokedTokenRow(
                jti=revoked_token.jti,
                user_id=revoked_token.user_id,
                expires_at=revoked_token.expires_at,
            )
            session.add(row)
            session.commit()
