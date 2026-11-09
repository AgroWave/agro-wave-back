"""SQLModel row models for the terrain bounded context."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class TerrainDemRow(SQLModel, table=True):
    """Database row model for terrain digital elevation models (DEM)."""

    __tablename__ = "terrain_dem"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(
        foreign_key="identity_user.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    name: str = Field(nullable=False)
    description: str | None = Field(default=None, nullable=True)
    south: float = Field(nullable=False)
    west: float = Field(nullable=False)
    north: float = Field(nullable=False)
    east: float = Field(nullable=False)
    status: str = Field(nullable=False, index=True)
    resolution_m: float = Field(default=30.0, nullable=False)
    object_key: str | None = Field(default=None, nullable=True)
    size_bytes: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.BigInteger(), nullable=True),
    )
    failure_reason: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
