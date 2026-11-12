"""Unit and integration tests for polar sweep coverage engine (AC-27)."""

from uuid import uuid4

import pytest

from agrowave.modules.simulation.domain.coverage_models import (
    CoverageMetrics,
    CoverageResult,
)
from agrowave.modules.simulation.infrastructure.polar_sweep_engine import (
    PolarSweepCoverageEngine,
)


def test_ac27_polar_sweep_trajectories_and_itm_loss() -> None:
    """Verifies AC-27: generation of radial sweep trajectories and ITM evaluation.

    Given:
        - Access Node at (4.65, -74.05) with 15 m AGL, 3 dBi gain, -137 dBm sensitivity.
        - Radio config: 915 MHz, End node TX power = 20 dBm, End node gain = 2 dBi, height = 2 m.
        - Longley-Rice params (klim=5, eps=15, sgm=0.005, ens0=301).
        - Angular resolution: 8 azimuths (every 45°), radial step: 500 m, max distance: 2000 m.
        - Synthetic elevation provider returning flat 2600 m terrain.

    When PolarSweepCoverageEngine.compute_coverage is executed:
    Then:
        - Evaluates 8 * 4 = 32 spatial samples.
        - Computes received power for each sample via ITM path loss.
        - Returns a CoverageResult containing samples and CoverageMetrics (ACE, %COB, Rmax, IVC).
        - Samples nearer to GW have higher received power than samples further away.
    """
    engine = PolarSweepCoverageEngine()

    access_node_dict = {
        "id": str(uuid4()),
        "name": "Gateway-DLOS8N",
        "latitude": 4.65,
        "longitude": -74.05,
        "height_agl_m": 15.0,
        "antenna_gain_dbi": 3.0,
        "sensitivity_dbm": -137.0,
    }

    bounds = {
        "south": 4.60,
        "west": -74.10,
        "north": 4.70,
        "east": -74.00,
    }

    radio_params = {
        "frequency_mhz": 915.0,
        "tx_power_dbm": 20.0,
        "tx_gain_dbi": 2.0,
        "tx_height_agl_m": 2.0,
    }

    itm_params = {
        "ens0": 301.0,
        "klim": 5,
        "eps": 15.0,
        "sgm": 0.005,
    }

    result = engine.compute_synthetic_coverage(
        access_node=access_node_dict,
        bounds=bounds,
        radio_params=radio_params,
        itm_params=itm_params,
        azimuth_count=8,
        radial_step_m=500.0,
        max_radius_m=2000.0,
    )

    assert isinstance(result, CoverageResult)
    assert len(result.samples) == 32
    assert isinstance(result.metrics, CoverageMetrics)
    assert result.metrics.total_samples_count == 32
    assert result.metrics.effective_coverage_area_km2 > 0.0
    assert result.metrics.coverage_percentage > 0.0
    assert result.metrics.max_coverage_radius_km == pytest.approx(2.0, rel=1e-2)
    assert result.metrics.variability_index >= 0.0

    # Near sample (500m) vs far sample (2000m) on same azimuth (e.g. 0 deg)
    sample_500m = next(s for s in result.samples if s.azimuth_deg == 0.0 and s.distance_m == 500.0)
    sample_2000m = next(
        s for s in result.samples if s.azimuth_deg == 0.0 and s.distance_m == 2000.0
    )

    # Free space + ground loss increases with distance, so Prx at 500m must be greater than at 2000m
    assert sample_500m.received_power_dbm > sample_2000m.received_power_dbm
