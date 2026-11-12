"""Pydantic request and response schemas for the simulation endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSimulationRequest(BaseModel):
    """Request payload for creating a simulation from a scenario (UC-SI-01)."""

    scenario_id: UUID
    name: str = Field(default="", max_length=150)
    description: str | None = Field(default=None, max_length=500)


class UpdateSimulationRequest(BaseModel):
    """Request payload for updating simulation metadata (UC-SI-04)."""

    name: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=500)


class CoverageMetricsResponse(BaseModel):
    """Consolidated DSR quantitative evaluation metrics (RN-44..47)."""

    effective_coverage_area_km2: float
    coverage_percentage: float
    max_coverage_radius_km: float
    variability_index: float
    total_area_km2: float
    covered_samples_count: int
    total_samples_count: int


class SimulationSummaryResponse(BaseModel):
    """Aggregated summary metrics for a completed simulation."""

    viable_links_pct: float
    min_margin_db: float
    mean_margin_db: float
    fresnel_clear_count: int
    fresnel_marginal_count: int
    fresnel_obstructed_count: int
    coverage_metrics: CoverageMetricsResponse | None = None


class FresnelAnalysisResponse(BaseModel):
    """First Fresnel zone clearance evaluation for a link (RN-35)."""

    min_clearance_ratio: float
    min_clearance_at_m: float
    max_radius_m: float
    verdict: str


class PathLossQuantileResponse(BaseModel):
    """Path loss prediction for a reliability and confidence quantile (RN-36)."""

    reliability_pct: float
    confidence_pct: float
    loss_db: float


class PathLossPredictionResponse(BaseModel):
    """Path loss prediction including free-space loss and quantiles (RN-36)."""

    free_space_loss_db: float
    loss_by_quantile: list[PathLossQuantileResponse]


class ElevationProfileSeriesResponse(BaseModel):
    """Sampled geometric series for the terrain and Fresnel chart of a link."""

    distances_m: list[float]
    terrain_with_curvature_m: list[float]
    los_m: list[float]
    f1_radius_m: list[float]
    series_version: int = 1


class LinkResultResponse(BaseModel):
    """Per-link evaluation result (RN-34, RN-35, RN-36, RN-42)."""

    id: UUID
    link_id: UUID
    end_node_name: str
    access_node_name: str
    distance_m: float
    fresnel: FresnelAnalysisResponse
    path_loss: PathLossPredictionResponse
    received_power_dbm: float
    sensitivity_used_dbm: float
    sensitivity_origin: str
    margin_db: float
    viable: bool
    profile_series: ElevationProfileSeriesResponse


class SimulationWarningResponse(BaseModel):
    """Warning emitted by the propagation engine or terrain sampler (RN-43)."""

    id: UUID
    link_id: UUID | None
    source: str
    code: str
    message: str


class SimulationResponse(BaseModel):
    """Summary representation of a simulation for list and status endpoints."""

    id: UUID
    owner_id: UUID
    scenario_id: UUID
    comparison_group_id: UUID
    name: str
    description: str | None
    status: str
    technology: str
    propagation_model_id: str
    snapshot: dict[str, Any]
    summary: SimulationSummaryResponse | None
    failure_reason: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CoverageSampleResponse(BaseModel):
    """Spatial coverage sample point."""

    latitude: float
    longitude: float
    distance_m: float
    azimuth_deg: float
    received_power_dbm: float
    viable: bool
    cell_area_km2: float


class CoverageResultResponse(BaseModel):
    """Coverage simulation result with samples and consolidated DSR metrics."""

    id: UUID
    access_node_id: UUID
    metrics: CoverageMetricsResponse
    samples: list[CoverageSampleResponse]


class SimulationResultsResponse(SimulationResponse):
    """Full simulation detail including per-link results, profiles, warnings, and coverage."""

    link_results: list[LinkResultResponse]
    warnings: list[SimulationWarningResponse]
    coverage_result: CoverageResultResponse | None = None


class CoverageExportRow(BaseModel):
    """Format matching Radio Mobile Cartesian/Polar export structure."""

    latitude: float
    longitude: float
    received_power_dbm: float
    viable: bool
    distance_km: float
    azimuth_deg: float


class CoverageExportResponse(BaseModel):
    """Export package containing metadata, DSR metrics, and grid/radial samples."""

    simulation_id: UUID
    simulation_name: str
    technology: str
    frequency_mhz: float
    access_node_name: str
    access_node_lat: float
    access_node_lon: float
    sensitivity_dbm: float
    metrics: CoverageMetricsResponse
    samples: list[CoverageExportRow]


class ComparedSimulationSummaryResponse(BaseModel):
    """Summary entry for a simulation variant in a comparison report."""

    simulation_id: UUID
    name: str
    technology: str
    frequency_mhz: float
    summary: SimulationSummaryResponse


class ComparedLinkMetricResponse(BaseModel):
    """Link metrics for a specific variant within a comparison row."""

    simulation_id: UUID
    simulation_name: str
    technology: str
    path_loss_p50_db: float
    received_power_dbm: float
    sensitivity_used_dbm: float
    margin_db: float
    viable: bool
    fresnel_verdict: str


class ComparedLinkRowResponse(BaseModel):
    """Side-by-side comparison row for a single physical link across variants."""

    link_key: str
    end_node_name: str
    access_node_name: str
    distance_m: float
    metrics_by_simulation: list[ComparedLinkMetricResponse]


class ComparisonReportResponse(BaseModel):
    """Side-by-side comparison report for simulations of the same group (RN-37)."""

    comparison_group_id: UUID
    propagation_model_id: str
    simulations: list[ComparedSimulationSummaryResponse]
    links: list[ComparedLinkRowResponse]
