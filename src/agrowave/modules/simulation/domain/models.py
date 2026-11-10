"""Domain entities and value objects for the simulation bounded context."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from agrowave.modules.simulation.domain.errors import InvalidStatusTransitionError


class Technology(StrEnum):
    """Supported LPWAN radio technologies."""

    LORAWAN = "LORAWAN"
    NB_IOT = "NB_IOT"
    LTE_M = "LTE_M"


class SensitivityOrigin(StrEnum):
    """Origin of the access node receiver sensitivity value (RN-42)."""

    REFERENCE_TO_VERIFY = "REFERENCE_TO_VERIFY"
    USER_DEFINED = "USER_DEFINED"


class SimulationStatus(StrEnum):
    """Lifecycle states of a simulation (RN-30)."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FresnelVerdict(StrEnum):
    """First Fresnel zone clearance verdict (RN-35)."""

    CLEAR = "CLEAR"
    MARGINAL = "MARGINAL"
    OBSTRUCTED = "OBSTRUCTED"


@dataclass(frozen=True)
class ScenarioSnapshot:
    """Immutable versioned snapshot of a Scenario at simulation creation time (RN-32).

    Attributes:
        scenario_id: Identifier of the source scenario.
        comparison_group_id: Identifier grouping variant scenarios (RN-29, RN-37).
        name: Scenario name at capture time.
        technology: LPWAN technology of the scenario profile.
        frequency_mhz: Carrier frequency in MHz.
        propagation_model_id: Identifier of the propagation model (e.g. LONGLEY_RICE).
        propagation_params: Dictionary of propagation parameters (ens0, klim, eps, sgm, etc.).
        dem_id: Identifier of the assigned DEM.
        bounds: Study area bounding box dictionary (south, west, north, east in degrees).
        access_nodes: List of serialized access node dictionaries.
        end_nodes: List of serialized end node dictionaries.
        links: List of serialized link dictionaries.
        snapshot_version: Schema version of the serialized snapshot.
        dem_object_key: Optional S3 object key of the DEM COG at capture time.
        dem_resolution_m: Nominal resolution of the DEM in meters (default 30.0 m).
    """

    scenario_id: UUID
    comparison_group_id: UUID
    name: str
    technology: Technology
    frequency_mhz: float
    propagation_model_id: str
    propagation_params: dict[str, Any]
    dem_id: UUID
    bounds: dict[str, float]
    access_nodes: list[dict[str, Any]]
    end_nodes: list[dict[str, Any]]
    links: list[dict[str, Any]]
    snapshot_version: int = 1
    dem_object_key: str | None = None
    dem_resolution_m: float = 30.0

    def to_dict(self) -> dict[str, Any]:
        """Serializes the snapshot to a JSON-compatible dictionary.

        Returns:
            Dictionary representation of the scenario snapshot.
        """
        return {
            "scenario_id": str(self.scenario_id),
            "comparison_group_id": str(self.comparison_group_id),
            "name": self.name,
            "technology": self.technology.value,
            "frequency_mhz": self.frequency_mhz,
            "propagation_model_id": self.propagation_model_id,
            "propagation_params": self.propagation_params,
            "dem_id": str(self.dem_id),
            "bounds": self.bounds,
            "access_nodes": self.access_nodes,
            "end_nodes": self.end_nodes,
            "links": self.links,
            "snapshot_version": self.snapshot_version,
            "dem_object_key": self.dem_object_key,
            "dem_resolution_m": self.dem_resolution_m,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], snapshot_version: int = 1) -> "ScenarioSnapshot":
        """Reconstructs a ScenarioSnapshot from its persisted dictionary.

        Args:
            data: Persisted JSON dictionary.
            snapshot_version: Schema version integer.

        Returns:
            Reconstructed ScenarioSnapshot value object.
        """
        return cls(
            scenario_id=UUID(str(data["scenario_id"])),
            comparison_group_id=UUID(str(data["comparison_group_id"])),
            name=str(data["name"]),
            technology=Technology(str(data["technology"])),
            frequency_mhz=float(data["frequency_mhz"]),
            propagation_model_id=str(data["propagation_model_id"]),
            propagation_params=dict(data.get("propagation_params", {})),
            dem_id=UUID(str(data["dem_id"])),
            bounds={k: float(v) for k, v in data.get("bounds", {}).items()},
            access_nodes=list(data.get("access_nodes", [])),
            end_nodes=list(data.get("end_nodes", [])),
            links=list(data.get("links", [])),
            snapshot_version=snapshot_version,
            dem_object_key=data.get("dem_object_key"),
            dem_resolution_m=float(data.get("dem_resolution_m", 30.0)),
        )


@dataclass(frozen=True)
class FresnelAnalysis:
    """First Fresnel zone evaluation summary for a single link (RN-35).

    Attributes:
        min_clearance_ratio: Minimum ratio of vertical clearance to F1 radius (dimensionless).
        min_clearance_at_m: Distance from the end node where minimum clearance occurs, in m.
        max_radius_m: Maximum first Fresnel zone radius along the path, in meters (m).
        verdict: Clearance classification (CLEAR >= 0.6, MARGINAL in [0, 0.6), OBSTRUCTED < 0).
    """

    min_clearance_ratio: float
    min_clearance_at_m: float
    max_radius_m: float
    verdict: FresnelVerdict


@dataclass(frozen=True)
class PathLossQuantile:
    """Predicted path loss for a specific reliability and confidence quantile (RN-36).

    Attributes:
        reliability_pct: Reliability percentage qr (e.g. 10, 50, 90).
        confidence_pct: Confidence percentage qc (e.g. 50).
        loss_db: Predicted propagation path loss, in dB.
    """

    reliability_pct: float
    confidence_pct: float
    loss_db: float


@dataclass(frozen=True)
class PathLossPrediction:
    """Propagation model path loss prediction for a link (RN-36).

    Attributes:
        free_space_loss_db: Reference free-space path loss, in dB.
        loss_by_quantile: Tuple of predicted path loss values by reliability quantile.
    """

    free_space_loss_db: float
    loss_by_quantile: tuple[PathLossQuantile, ...]

    def primary_loss_db(self) -> float:
        """Returns the primary path loss (p50 or median quantile) in dB for link budget (RN-34).

        Returns:
            Path loss in dB for the 50% reliability quantile (or closest available quantile).
        """
        if not self.loss_by_quantile:
            return self.free_space_loss_db
        for q in self.loss_by_quantile:
            if abs(q.reliability_pct - 50.0) < 1e-6:
                return q.loss_db
        sorted_q = sorted(self.loss_by_quantile, key=lambda item: item.reliability_pct)
        return sorted_q[len(sorted_q) // 2].loss_db


@dataclass(frozen=True)
class ElevationProfileSeries:
    """Sampled geometric series for rendering the terrain and Fresnel chart of a link.

    Attributes:
        distances_m: Horizontal distance samples from the end node, in meters (m).
        terrain_with_curvature_m: Terrain elevation plus Earth curvature bulge, in meters (m).
        los_m: Direct line-of-sight height between antennas, in meters (m).
        f1_radius_m: First Fresnel zone radius at each sample point, in meters (m).
        series_version: Schema version of the profile series.
    """

    distances_m: tuple[float, ...]
    terrain_with_curvature_m: tuple[float, ...]
    los_m: tuple[float, ...]
    f1_radius_m: tuple[float, ...]
    series_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serializes the profile series into a JSON-compatible dictionary.

        Returns:
            Dictionary with distance, terrain, LoS, and F1 radius arrays in meters (m).
        """
        return {
            "distances_m": list(self.distances_m),
            "terrain_with_curvature_m": list(self.terrain_with_curvature_m),
            "los_m": list(self.los_m),
            "f1_radius_m": list(self.f1_radius_m),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], series_version: int = 1) -> "ElevationProfileSeries":
        """Reconstructs an ElevationProfileSeries from a JSON dictionary.

        Args:
            data: Persisted dictionary containing profile arrays.
            series_version: Schema version integer.

        Returns:
            Reconstructed ElevationProfileSeries value object.
        """
        return cls(
            distances_m=tuple(float(x) for x in data.get("distances_m", [])),
            terrain_with_curvature_m=tuple(
                float(x) for x in data.get("terrain_with_curvature_m", [])
            ),
            los_m=tuple(float(x) for x in data.get("los_m", [])),
            f1_radius_m=tuple(float(x) for x in data.get("f1_radius_m", [])),
            series_version=series_version,
        )


@dataclass(frozen=True)
class LinkResult:
    """Evaluation result of a single uplink LPWAN link (RN-34, RN-35, RN-36, RN-42).

    Attributes:
        link_id: Identifier of the link in the scenario snapshot.
        end_node_name: Name of the transmitting end node.
        access_node_name: Name of the receiving access node.
        distance_m: Horizontal link distance, in meters (m).
        fresnel: First Fresnel zone clearance analysis.
        path_loss: Path loss prediction including FSPL and reliability quantiles, in dB.
        received_power_dbm: Predicted received power at the access node, in dBm.
        sensitivity_used_dbm: Receiver sensitivity threshold used, in dBm.
        sensitivity_origin: Origin of the receiver sensitivity (RN-42).
        margin_db: Link margin (received_power_dbm - sensitivity_used_dbm), in dB.
        viable: True if margin_db >= 0.0 dB (RN-34).
        profile_series: Sampled profile series for the elevation and Fresnel chart.
        id: Unique identifier of this link result record.
    """

    link_id: UUID
    end_node_name: str
    access_node_name: str
    distance_m: float
    fresnel: FresnelAnalysis
    path_loss: PathLossPrediction
    received_power_dbm: float
    sensitivity_used_dbm: float
    sensitivity_origin: SensitivityOrigin
    margin_db: float
    viable: bool
    profile_series: ElevationProfileSeries
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class SimulationWarning:
    """Warning emitted by the propagation engine or terrain profile sampler (RN-43).

    Attributes:
        link_id: Optional link identifier if the warning applies to a specific link.
        source: Component that generated the warning (e.g. 'ITM').
        code: Machine-readable warning code (e.g. 'KWX_4').
        message: Descriptive warning message.
        id: Unique warning identifier.
    """

    link_id: UUID | None
    source: str
    code: str
    message: str
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class SimulationSummary:
    """Aggregated summary metrics for a completed simulation.

    Attributes:
        viable_links_pct: Percentage of links with margin_db >= 0 (0 to 100).
        min_margin_db: Minimum link margin across all evaluated links, in dB.
        mean_margin_db: Arithmetic mean of link margins across all links, in dB.
        fresnel_clear_count: Number of links with CLEAR Fresnel verdict.
        fresnel_marginal_count: Number of links with MARGINAL Fresnel verdict.
        fresnel_obstructed_count: Number of links with OBSTRUCTED Fresnel verdict.
    """

    viable_links_pct: float
    min_margin_db: float
    mean_margin_db: float
    fresnel_clear_count: int
    fresnel_marginal_count: int
    fresnel_obstructed_count: int


@dataclass(frozen=True)
class SimulationResult:
    """Complete result set produced when a simulation finishes execution.

    Attributes:
        link_results: Tuple of per-link evaluation results.
        warnings: Tuple of engine or terrain warnings (RN-43).
    """

    link_results: tuple[LinkResult, ...]
    warnings: tuple[SimulationWarning, ...] = ()

    def compute_summary(self) -> SimulationSummary:
        """Computes aggregated summary metrics across all link results.

        Returns:
            SimulationSummary with viability percentage, margin stats in dB, and Fresnel counts.
        """
        total = len(self.link_results)
        if total == 0:
            return SimulationSummary(
                viable_links_pct=0.0,
                min_margin_db=0.0,
                mean_margin_db=0.0,
                fresnel_clear_count=0,
                fresnel_marginal_count=0,
                fresnel_obstructed_count=0,
            )
        viable_count = sum(1 for lr in self.link_results if lr.viable)
        margins = [lr.margin_db for lr in self.link_results]
        clear_count = sum(
            1 for lr in self.link_results if lr.fresnel.verdict == FresnelVerdict.CLEAR
        )
        marginal_count = sum(
            1 for lr in self.link_results if lr.fresnel.verdict == FresnelVerdict.MARGINAL
        )
        obstructed_count = sum(
            1 for lr in self.link_results if lr.fresnel.verdict == FresnelVerdict.OBSTRUCTED
        )
        return SimulationSummary(
            viable_links_pct=round((viable_count / total) * 100.0, 2),
            min_margin_db=round(min(margins), 2),
            mean_margin_db=round(sum(margins) / total, 2),
            fresnel_clear_count=clear_count,
            fresnel_marginal_count=marginal_count,
            fresnel_obstructed_count=obstructed_count,
        )


@dataclass
class Simulation:
    """Simulation aggregate root representing a propagation run on a ScenarioSnapshot.

    Enforces lifecycle transitions (RN-30) and deletion restrictions while running (RN-33).

    Attributes:
        id: Unique simulation identifier.
        owner_id: Identifier of the user who owns the simulation.
        scenario_id: Identifier of the source scenario (informational, no FK cascade per RF-026).
        comparison_group_id: Identifier of the scenario variant comparison group (RN-37).
        name: User-visible name of the simulation.
        description: Optional description of the simulation.
        status: Current lifecycle state (CREATED, RUNNING, COMPLETED, FAILED).
        technology: LPWAN technology copied from the snapshot for filtering.
        propagation_model_id: Propagation model identifier copied from the snapshot.
        snapshot: Immutable scenario snapshot captured at creation (RN-32).
        summary: Aggregated metrics populated when status is COMPLETED.
        result: Detailed per-link results and warnings when status is COMPLETED.
        failure_reason: Error description populated when status is FAILED.
        created_at: UTC creation timestamp.
        started_at: UTC execution start timestamp.
        finished_at: UTC execution completion or failure timestamp.
    """

    id: UUID
    owner_id: UUID
    scenario_id: UUID
    comparison_group_id: UUID
    name: str
    description: str | None
    status: SimulationStatus
    technology: Technology
    propagation_model_id: str
    snapshot: ScenarioSnapshot
    summary: SimulationSummary | None = None
    result: SimulationResult | None = None
    failure_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def create(
        cls,
        owner_id: UUID,
        name: str,
        description: str | None,
        snapshot: ScenarioSnapshot,
    ) -> "Simulation":
        """Creates a new simulation in CREATED state with an immutable scenario snapshot (RN-32).

        Args:
            owner_id: User identifier of the simulation owner.
            name: Simulation name.
            description: Optional simulation description.
            snapshot: Validated immutable snapshot of the scenario.

        Returns:
            Newly created Simulation aggregate in CREATED status.
        """
        clean_name = name.strip() or f"Simulación - {snapshot.name}"
        return cls(
            id=uuid4(),
            owner_id=owner_id,
            scenario_id=snapshot.scenario_id,
            comparison_group_id=snapshot.comparison_group_id,
            name=clean_name,
            description=description.strip() if description else None,
            status=SimulationStatus.CREATED,
            technology=snapshot.technology,
            propagation_model_id=snapshot.propagation_model_id,
            snapshot=snapshot,
        )

    def start(self) -> None:
        """Transitions the simulation from CREATED to RUNNING (RN-30).

        Raises:
            InvalidStatusTransitionError: If current status is not CREATED.
        """
        if self.status != SimulationStatus.CREATED:
            raise InvalidStatusTransitionError(
                current_status=self.status.value,
                attempted_action="start",
            )
        self.status = SimulationStatus.RUNNING
        self.started_at = datetime.now(UTC)
        self.finished_at = None
        self.failure_reason = None

    def retry(self) -> None:
        """Transitions a FAILED simulation back to RUNNING for re-execution (RN-30).

        Raises:
            InvalidStatusTransitionError: If current status is not FAILED.
        """
        if self.status != SimulationStatus.FAILED:
            raise InvalidStatusTransitionError(
                current_status=self.status.value,
                attempted_action="retry",
            )
        self.status = SimulationStatus.RUNNING
        self.started_at = datetime.now(UTC)
        self.finished_at = None
        self.failure_reason = None
        self.summary = None
        self.result = None

    def complete(self, result: SimulationResult) -> None:
        """Transitions simulation from RUNNING to COMPLETED and computes summary metrics (RN-30).

        Args:
            result: Per-link results and engine warnings.

        Raises:
            InvalidStatusTransitionError: If current status is not RUNNING.
        """
        if self.status != SimulationStatus.RUNNING:
            raise InvalidStatusTransitionError(
                current_status=self.status.value,
                attempted_action="complete",
            )
        self.status = SimulationStatus.COMPLETED
        self.result = result
        self.summary = result.compute_summary()
        self.failure_reason = None
        self.finished_at = datetime.now(UTC)

    def fail(self, reason: str) -> None:
        """Transitions the simulation from RUNNING to FAILED with an explanation (RN-30).

        Args:
            reason: Description of the failure cause.

        Raises:
            InvalidStatusTransitionError: If current status is not RUNNING.
        """
        if self.status != SimulationStatus.RUNNING:
            raise InvalidStatusTransitionError(
                current_status=self.status.value,
                attempted_action="fail",
            )
        self.status = SimulationStatus.FAILED
        self.failure_reason = reason
        self.finished_at = datetime.now(UTC)

    def update_info(self, name: str | None, description: str | None) -> None:
        """Updates the simulation name and description metadata.

        Args:
            name: Optional new name.
            description: Optional new description.
        """
        if name is not None and name.strip():
            self.name = name.strip()
        if description is not None:
            self.description = description.strip() or None

    def ensure_deletable(self) -> None:
        """Verifies that the simulation is not currently RUNNING before deletion (RN-33).

        Raises:
            InvalidStatusTransitionError: If the simulation is in RUNNING status.
        """
        if self.status == SimulationStatus.RUNNING:
            raise InvalidStatusTransitionError(
                current_status=self.status.value,
                attempted_action="delete",
            )
