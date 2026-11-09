"""SQLModel row models for the scenarios bounded context."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class ScenariosScenarioRow(SQLModel, table=True):
    """Database row model for an LPWAN simulation scenario."""

    __tablename__ = "scenarios_scenario"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(
        foreign_key="identity_user.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    name: str = Field(nullable=False)
    description: str | None = Field(default=None, nullable=True)
    comparison_group_id: UUID = Field(
        default_factory=uuid4,
        nullable=False,
        index=True,
    )
    south: float = Field(nullable=False)
    west: float = Field(nullable=False)
    north: float = Field(nullable=False)
    east: float = Field(nullable=False)
    dem_id: UUID | None = Field(
        default=None,
        foreign_key="terrain_dem.id",
        ondelete="RESTRICT",
        nullable=True,
        index=True,
    )
    profile_id: UUID | None = Field(
        default=None,
        foreign_key="profiles_lpwan_profile.id",
        ondelete="RESTRICT",
        nullable=True,
        index=True,
    )
    technology: str | None = Field(default=None, nullable=True)
    band_code: str | None = Field(default=None, nullable=True)
    frequency_mhz: float | None = Field(default=None, nullable=True)
    propagation_model_id: str | None = Field(default=None, nullable=True)
    propagation_params: dict[str, Any] | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON(), nullable=True),
    )
    propagation_params_version: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class ScenariosAccessNodeRow(SQLModel, table=True):
    """Database row model for an access node (gateway or base station) in a scenario."""

    __tablename__ = "scenarios_access_node"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    scenario_id: UUID = Field(
        foreign_key="scenarios_scenario.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    name: str = Field(nullable=False)
    lat: float = Field(nullable=False)
    lng: float = Field(nullable=False)
    height_agl_m: float = Field(nullable=False)
    antenna_ref: str | None = Field(default=None, nullable=True)
    antenna_gain_dbi: float = Field(nullable=False)
    polarization: str | None = Field(default=None, nullable=True)
    sensitivity_dbm: float = Field(nullable=False)
    sensitivity_origin: str = Field(nullable=False)


class ScenariosEndNodeRow(SQLModel, table=True):
    """Database row model for an end node (field device) in a scenario."""

    __tablename__ = "scenarios_end_node"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    scenario_id: UUID = Field(
        foreign_key="scenarios_scenario.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    name: str = Field(nullable=False)
    lat: float = Field(nullable=False)
    lng: float = Field(nullable=False)
    height_agl_m: float = Field(nullable=False)
    antenna_ref: str | None = Field(default=None, nullable=True)
    antenna_gain_dbi: float = Field(nullable=False)
    polarization: str | None = Field(default=None, nullable=True)
    tx_power_nominal_dbm: float = Field(nullable=False)
    tx_power_tolerance_db: float = Field(default=0.0, nullable=False)
    source_template_id: UUID | None = Field(default=None, nullable=True)


class ScenariosLinkRow(SQLModel, table=True):
    """Database row model for an uplink radio link in a scenario."""

    __tablename__ = "scenarios_link"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    scenario_id: UUID = Field(
        foreign_key="scenarios_scenario.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    end_node_id: UUID = Field(
        foreign_key="scenarios_end_node.id",
        ondelete="CASCADE",
        nullable=False,
        unique=True,
    )
    access_node_id: UUID = Field(
        foreign_key="scenarios_access_node.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
