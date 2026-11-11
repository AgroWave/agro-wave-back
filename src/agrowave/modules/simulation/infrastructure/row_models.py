"""SQLModel row models for the simulation bounded context."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class SimulationSimulationRow(SQLModel, table=True):
    """Database row model for a simulation execution and its scenario snapshot."""

    __tablename__ = "simulation_simulation"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(
        foreign_key="identity_user.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    scenario_id: UUID = Field(nullable=False, index=True)
    comparison_group_id: UUID = Field(nullable=False, index=True)
    name: str = Field(nullable=False)
    description: str | None = Field(default=None, nullable=True)
    status: str = Field(nullable=False, index=True)
    technology: str = Field(nullable=False)
    propagation_model_id: str = Field(nullable=False)
    snapshot: dict[str, Any] = Field(
        sa_column=sa.Column(sa.JSON(), nullable=False),
    )
    snapshot_version: int = Field(default=1, nullable=False)
    viable_links_pct: float | None = Field(default=None, nullable=True)
    min_margin_db: float | None = Field(default=None, nullable=True)
    mean_margin_db: float | None = Field(default=None, nullable=True)
    fresnel_clear_count: int | None = Field(default=None, nullable=True)
    fresnel_marginal_count: int | None = Field(default=None, nullable=True)
    fresnel_obstructed_count: int | None = Field(default=None, nullable=True)
    effective_coverage_area_km2: float | None = Field(default=None, nullable=True)
    coverage_percentage: float | None = Field(default=None, nullable=True)
    max_coverage_radius_km: float | None = Field(default=None, nullable=True)
    variability_index: float | None = Field(default=None, nullable=True)
    failure_reason: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )


class SimulationLinkResultRow(SQLModel, table=True):
    """Database row model for the evaluated radio and Fresnel metrics of a single link."""

    __tablename__ = "simulation_link_result"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    simulation_id: UUID = Field(
        foreign_key="simulation_simulation.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    link_id: UUID = Field(nullable=False)
    end_node_name: str = Field(nullable=False)
    access_node_name: str = Field(nullable=False)
    distance_m: float = Field(nullable=False)
    fresnel_min_ratio: float = Field(nullable=False)
    fresnel_min_at_m: float = Field(nullable=False)
    fresnel_max_radius_m: float = Field(nullable=False)
    fresnel_verdict: str = Field(nullable=False)
    free_space_loss_db: float = Field(nullable=False)
    received_power_dbm: float = Field(nullable=False)
    sensitivity_used_dbm: float = Field(nullable=False)
    sensitivity_origin: str = Field(nullable=False)
    margin_db: float = Field(nullable=False)
    viable: bool = Field(nullable=False)


class SimulationPathLossQuantileRow(SQLModel, table=True):
    """Database row model for a reliability quantile path loss prediction on a link."""

    __tablename__ = "simulation_path_loss_quantile"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    link_result_id: UUID = Field(
        foreign_key="simulation_link_result.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    reliability_pct: float = Field(nullable=False)
    confidence_pct: float = Field(nullable=False)
    loss_db: float = Field(nullable=False)


class SimulationLinkProfileRow(SQLModel, table=True):
    """Database row model for the sampled elevation and Fresnel series of a link."""

    __tablename__ = "simulation_link_profile"

    link_result_id: UUID = Field(
        foreign_key="simulation_link_result.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    series: dict[str, Any] = Field(
        sa_column=sa.Column(sa.JSON(), nullable=False),
    )
    series_version: int = Field(default=1, nullable=False)


class SimulationWarningRow(SQLModel, table=True):
    """Database row model for engine or terrain warnings emitted during simulation."""

    __tablename__ = "simulation_warning"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    simulation_id: UUID = Field(
        foreign_key="simulation_simulation.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    link_result_id: UUID | None = Field(default=None, nullable=True)
    source: str = Field(nullable=False)
    code: str = Field(nullable=False)
    message: str = Field(nullable=False)


class SimulationCoverageResultRow(SQLModel, table=True):
    """Database row model for spatial coverage simulation and DSR metrics (RN-44..49)."""

    __tablename__ = "simulation_coverage_result"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    simulation_id: UUID = Field(
        foreign_key="simulation_simulation.id",
        ondelete="CASCADE",
        nullable=False,
        index=True,
    )
    access_node_id: UUID = Field(nullable=False)
    effective_coverage_area_km2: float = Field(nullable=False)
    coverage_percentage: float = Field(nullable=False)
    max_coverage_radius_km: float = Field(nullable=False)
    variability_index: float = Field(nullable=False)
    total_area_km2: float = Field(nullable=False)
    covered_samples_count: int = Field(nullable=False)
    total_samples_count: int = Field(nullable=False)
    samples: list[dict[str, Any]] = Field(
        sa_column=sa.Column(sa.JSON(), nullable=False),
    )
