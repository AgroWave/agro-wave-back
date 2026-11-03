"""SQLModel row models for the profiles bounded context."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel


class ProfilesProfileBandRow(SQLModel, table=True):
    """Database row model for frequency bands associated with an LPWAN profile."""

    __tablename__ = "profiles_profile_band"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    profile_id: UUID = Field(
        foreign_key="profiles_lpwan_profile.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    code: str = Field(nullable=False)
    min_mhz: float | None = Field(default=None, nullable=True)
    max_mhz: float | None = Field(default=None, nullable=True)

    profile: "ProfilesLpwanProfileRow" = Relationship(back_populates="bands")


class ProfilesLpwanProfileRow(SQLModel, table=True):
    """Database row model for an LPWAN radio profile."""

    __tablename__ = "profiles_lpwan_profile"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID | None = Field(default=None, nullable=True, index=True)
    is_predefined: bool = Field(default=False, nullable=False)
    name: str = Field(nullable=False)
    technology: str = Field(nullable=False, index=True)
    spreading_factor: int | None = Field(default=None, nullable=True)
    reference_sensitivity_dbm: float = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )

    bands: list[ProfilesProfileBandRow] = Relationship(
        back_populates="profile",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ProfilesNodeTemplateRow(SQLModel, table=True):
    """Database row model for reference node templates."""

    __tablename__ = "profiles_node_template"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    technology: str = Field(nullable=False, index=True)
    role: str = Field(nullable=False)
    name: str = Field(nullable=False)
    module_ref: str | None = Field(default=None, nullable=True)
    antenna_ref: str | None = Field(default=None, nullable=True)
    antenna_gain_dbi: float | None = Field(default=None, nullable=True)
    polarization: str | None = Field(default=None, nullable=True)
    tx_power_nominal_dbm: float | None = Field(default=None, nullable=True)
    tx_power_tolerance_db: float | None = Field(default=None, nullable=True)
