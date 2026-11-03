"""SQLModel row models for identity database tables."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class IdentityUserRow(SQLModel, table=True):
    """Database row model for identity_user table."""

    __tablename__ = "identity_user"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    name: str = Field(nullable=False)
    password_hash: str = Field(nullable=False)
    role: str = Field(default="USER", nullable=False)
    email_confirmed: bool = Field(default=False, nullable=False)
    password_changed_at: datetime | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class IdentityOneTimeTokenRow(SQLModel, table=True):
    """Database row model for identity_one_time_token table."""

    __tablename__ = "identity_one_time_token"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="identity_user.id", index=True, nullable=False)
    purpose: str = Field(nullable=False)
    token_hash: str = Field(unique=True, index=True, nullable=False)
    expires_at: datetime = Field(nullable=False)
    used_at: datetime | None = Field(default=None, nullable=True)


class IdentityRevokedTokenRow(SQLModel, table=True):
    """Database row model for identity_revoked_token table."""

    __tablename__ = "identity_revoked_token"

    jti: str = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="identity_user.id", nullable=False)
    expires_at: datetime = Field(nullable=False)
