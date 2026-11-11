"""Domain models for spatial coverage simulation and DSR evaluation metrics.

Defines spatial samples, aggregated DSR metrics (ACE, %COB, Rmax, IVC), and
the complete coverage result value objects.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class CoverageSample:
    """Single spatial evaluation point in a coverage simulation.

    Attributes:
        latitude: Geographic latitude in decimal degrees (WGS84).
        longitude: Geographic longitude in decimal degrees (WGS84).
        distance_m: Distance from the transmitter / gateway, in meters (m).
        azimuth_deg: Azimuth angle from the access node, in degrees [0, 360).
        received_power_dbm: Predicted received power at this sample, in dBm.
        viable: True if received_power_dbm >= sensitivity threshold.
        cell_area_km2: Elemental geographic surface area represented, in km².
    """

    latitude: float
    longitude: float
    distance_m: float
    azimuth_deg: float
    received_power_dbm: float
    viable: bool
    cell_area_km2: float


@dataclass(frozen=True)
class CoverageMetrics:
    """Quantitative DSR evaluation metrics calculated over a coverage simulation.

    Makes effective coverage area (RN-44), coverage percentage (RN-45),
    maximum coverage radius (RN-46), and linear variability index (RN-47) explicit.

    Attributes:
        effective_coverage_area_km2: Surface area with Prx >= S (RN-44), in km².
        coverage_percentage: Proportion ACE / Atotal * 100% (RN-45), in range [0, 100].
        max_coverage_radius_km: Distance to farthest viable point (RN-46), in km.
        variability_index: Coefficient of variation (sigma/mu) of linear power in mW (RN-47).
        total_area_km2: Total analyzed geographic surface area, in km².
        covered_samples_count: Count of samples where viable is True.
        total_samples_count: Total evaluated spatial samples count.
    """

    effective_coverage_area_km2: float
    coverage_percentage: float
    max_coverage_radius_km: float
    variability_index: float
    total_area_km2: float
    covered_samples_count: int
    total_samples_count: int


@dataclass(frozen=True)
class CoverageResult:
    """Immutable result of a spatial coverage simulation linked to a scenario run.

    Attributes:
        metrics: Consolidated DSR evaluation metrics (RN-44..47).
        samples: Evaluated spatial samples across all radial azimuths (RN-48).
        access_node_id: Identifier of the central access node / gateway.
        id: Unique identifier for this coverage result record.
    """

    metrics: CoverageMetrics
    samples: tuple[CoverageSample, ...]
    access_node_id: UUID
    id: UUID = field(default_factory=uuid4)
