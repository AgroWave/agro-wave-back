"""Domain ports for the simulation bounded context."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from agrowave.modules.simulation.domain.coverage_models import CoverageResult
from agrowave.modules.simulation.domain.models import (
    PathLossQuantile,
    ScenarioSnapshot,
    Simulation,
    SimulationStatus,
    Technology,
)


@dataclass(frozen=True)
class SampledTerrainProfile:
    """Sampled terrain elevation profile between two geographic coordinates.

    Attributes:
        distances_m: Horizontal distances from the start point, in meters (m).
        elevations_m: Terrain elevations above sea level at each sample point, in meters (m).
        step_m: Horizontal sampling step between consecutive points, in meters (m).
    """

    distances_m: tuple[float, ...]
    elevations_m: tuple[float, ...]
    step_m: float


@dataclass(frozen=True)
class EngineEvaluationResult:
    """Output of a propagation model engine for a single link.

    Attributes:
        quantiles: Tuple of predicted path loss values by reliability quantile, in dB.
        warnings: Tuple of (code, message) warning pairs emitted by the engine (e.g. kwx != 0).
    """

    quantiles: tuple[PathLossQuantile, ...]
    warnings: tuple[tuple[str, str], ...] = ()


class SimulationRepository(Protocol):
    """Persistence port for the Simulation aggregate root."""

    def add(self, simulation: Simulation) -> None:
        """Persists a new simulation."""
        ...

    def save(self, simulation: Simulation) -> None:
        """Updates an existing simulation and its results/warnings if present."""
        ...

    def get_by_id(self, simulation_id: UUID, owner_id: UUID) -> Simulation | None:
        """Retrieves a simulation owned by the given user, including its results if completed."""
        ...

    def get_by_id_unscoped(self, simulation_id: UUID) -> Simulation | None:
        """Retrieves a simulation by ID for background worker execution."""
        ...

    def list_by_owner(
        self,
        owner_id: UUID,
        q: str | None = None,
        technology: Technology | None = None,
        status: SimulationStatus | None = None,
        comparison_group_id: UUID | None = None,
        sort: str = "newest",
    ) -> list[Simulation]:
        """Lists simulations belonging to the given owner with optional filters."""
        ...

    def delete(self, simulation_id: UUID, owner_id: UUID) -> None:
        """Deletes a simulation and its associated results."""
        ...

    def mark_running_as_failed_on_startup(self, reason: str) -> int:
        """Marks any simulations left in RUNNING state as FAILED on process startup."""
        ...


class ScenarioSnapshotSource(Protocol):
    """Port to validate a scenario and build its immutable ScenarioSnapshot (RN-31, RN-32)."""

    def capture_simulable_snapshot(
        self,
        scenario_id: UUID,
        owner_id: UUID,
    ) -> ScenarioSnapshot:
        """Validates the scenario and returns an immutable ScenarioSnapshot.

        Raises:
            ScenarioNotSimulableError: If the scenario has validation causes (RN-31).
        """
        ...


class TerrainProfileProvider(Protocol):
    """Port to extract a terrain elevation profile between two points from a DEM COG (ADR-07)."""

    def extract_profile(
        self,
        dem_id: UUID,
        dem_object_key: str | None,
        window_bounds: dict[str, float],
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        distance_m: float,
        resolution_m: float = 30.0,
    ) -> SampledTerrainProfile:
        """Extracts a sampled elevation profile from start (end node) to end (access node)."""
        ...


class PropagationEngine(Protocol):
    """Port for point-to-point radio propagation path loss prediction (RN-36, RN-43)."""

    def evaluate_link(
        self,
        profile: SampledTerrainProfile,
        frequency_mhz: float,
        tx_height_agl_m: float,
        rx_height_agl_m: float,
        polarization: str,
        propagation_params: dict[str, Any],
    ) -> EngineEvaluationResult:
        """Evaluates path loss by quantile and returns any engine warnings (e.g. kwx != 0)."""
        ...


class SimulationJobRunner(Protocol):
    """Port to schedule background simulation execution jobs (ADR-03)."""

    def enqueue(self, simulation_id: UUID) -> None:
        """Enqueues a simulation ID for asynchronous execution."""
        ...


class CoverageEnginePort(Protocol):
    """Port for computing area coverage simulation from an access node (RN-48)."""

    def compute_coverage(
        self,
        access_node: dict[str, Any],
        bounds: dict[str, float],
        radio_params: dict[str, Any],
        itm_params: dict[str, Any],
        azimuth_count: int = 360,
        radial_step_m: float = 100.0,
        max_radius_m: float = 5000.0,
    ) -> CoverageResult:
        """Computes polar coverage samples and consolidated DSR metrics.

        Args:
            access_node: Access node dictionary with position, height, gain, sensitivity.
            bounds: Geographical bounding box.
            radio_params: Radio configuration dictionary.
            itm_params: Longley-Rice environmental parameters.
            azimuth_count: Number of azimuthal angles.
            radial_step_m: Sampling step along each radial, in meters (m).
            max_radius_m: Maximum radial evaluation distance, in meters (m).

        Returns:
            CoverageResult containing evaluated samples and DSR metrics.
        """
        ...
