"""Unit tests for DSR coverage metrics calculation in the domain layer (AC-26)."""

import math

import pytest

from agrowave.modules.simulation.domain.coverage_calculator import (
    compute_coverage_metrics,
)
from agrowave.modules.simulation.domain.coverage_models import (
    CoverageMetrics,
    CoverageSample,
)


def test_ac26_coverage_metrics_calculation_and_linear_ivc() -> None:
    """Verifies AC-26: calculation of ACE, %COB, Rmax, and linear mW IVC (RN-44..47).

    Given 4 spatial samples covering a 4 km² scenario:
        - Sample 1: viable (-90 dBm = 1e-9 mW), distance = 1000 m (1.0 km), cell = 1.0 km²
        - Sample 2: viable (-100 dBm = 1e-10 mW), distance = 2500 m (2.5 km), cell = 1.0 km²
        - Sample 3: non-viable (-140 dBm, below sensitivity), distance = 3000 m, cell = 1.0 km²
        - Sample 4: non-viable (-145 dBm), distance = 3500 m, cell = 1.0 km²
    Total area = 4.0 km².
    Sensitivity threshold = -137.0 dBm.

    When compute_coverage_metrics is executed:
    Then:
        - ACE = 2.0 km² (RN-44)
        - %COB = 50.0 % (RN-45)
        - Rmax = 2.5 km (RN-46)
        - IVC is calculated strictly on linear mW (RN-47):
            p1 = 10^(-90/10) = 1e-9 mW
            p2 = 10^(-100/10) = 1e-10 mW
            mean = (1e-9 + 1e-10) / 2 = 5.5e-10 mW
            std = sqrt(((1e-9 - 5.5e-10)^2 + (1e-10 - 5.5e-10)^2) / 1) = 4.5e-10 * sqrt(2)
            cv = std / mean = (4.5e-10 * 1.41421356) / 5.5e-10 ≈ 1.157157
    """
    samples = (
        CoverageSample(
            latitude=4.65,
            longitude=-74.05,
            distance_m=1000.0,
            azimuth_deg=45.0,
            received_power_dbm=-90.0,
            viable=True,
            cell_area_km2=1.0,
        ),
        CoverageSample(
            latitude=4.66,
            longitude=-74.04,
            distance_m=2500.0,
            azimuth_deg=90.0,
            received_power_dbm=-100.0,
            viable=True,
            cell_area_km2=1.0,
        ),
        CoverageSample(
            latitude=4.67,
            longitude=-74.03,
            distance_m=3000.0,
            azimuth_deg=135.0,
            received_power_dbm=-140.0,
            viable=False,
            cell_area_km2=1.0,
        ),
        CoverageSample(
            latitude=4.68,
            longitude=-74.02,
            distance_m=3500.0,
            azimuth_deg=180.0,
            received_power_dbm=-145.0,
            viable=False,
            cell_area_km2=1.0,
        ),
    )

    metrics = compute_coverage_metrics(
        samples=samples,
        total_area_km2=4.0,
    )

    assert isinstance(metrics, CoverageMetrics)
    assert metrics.effective_coverage_area_km2 == pytest.approx(2.0, rel=1e-3)
    assert metrics.coverage_percentage == pytest.approx(50.0, rel=1e-3)
    assert metrics.max_coverage_radius_km == pytest.approx(2.5, rel=1e-3)
    assert metrics.total_area_km2 == pytest.approx(4.0, rel=1e-3)
    assert metrics.covered_samples_count == 2
    assert metrics.total_samples_count == 4

    # Theoretical linear IVC
    p1 = 10.0 ** (-90.0 / 10.0)
    p2 = 10.0 ** (-100.0 / 10.0)
    mean_p = (p1 + p2) / 2.0
    var_p = ((p1 - mean_p) ** 2 + (p2 - mean_p) ** 2) / 1.0
    expected_ivc = math.sqrt(var_p) / mean_p

    assert metrics.variability_index == pytest.approx(expected_ivc, rel=1e-4)


def test_ac26_coverage_metrics_no_viable_samples() -> None:
    """Verifies that with zero viable samples, metrics return 0.0 without division by zero."""
    samples = (
        CoverageSample(
            latitude=4.65,
            longitude=-74.05,
            distance_m=1000.0,
            azimuth_deg=45.0,
            received_power_dbm=-150.0,
            viable=False,
            cell_area_km2=1.0,
        ),
    )
    metrics = compute_coverage_metrics(samples=samples, total_area_km2=5.0)

    assert metrics.effective_coverage_area_km2 == 0.0
    assert metrics.coverage_percentage == 0.0
    assert metrics.max_coverage_radius_km == 0.0
    assert metrics.variability_index == 0.0
    assert metrics.covered_samples_count == 0
    assert metrics.total_samples_count == 1
