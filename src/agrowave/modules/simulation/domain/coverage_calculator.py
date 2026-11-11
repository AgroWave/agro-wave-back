"""Pure domain calculator for spatial coverage metrics (RN-44, RN-45, RN-46, RN-47)."""

import math
from typing import Sequence

from agrowave.modules.simulation.domain.coverage_models import (
    CoverageMetrics,
    CoverageSample,
)


def compute_coverage_metrics(
    samples: Sequence[CoverageSample],
    total_area_km2: float,
) -> CoverageMetrics:
    """Computes DSR quantitative evaluation metrics from evaluated spatial samples.

    Implements Effective Coverage Area ACE (RN-44), Coverage Percentage %COB (RN-45),
    Maximum Coverage Radius Rmax (RN-46), and Coverage Variability Index IVC (RN-47).
    Crucially, IVC is computed strictly on linear milliwatt powers (mW) rather than
    logarithmic dBm to prevent physical and mathematical inconsistencies.

    Args:
        samples: Sequence of spatial evaluation samples with distance and received power.
        total_area_km2: Total geographical area analyzed in the scenario, in km².

    Returns:
        CoverageMetrics value object with ACE (km²), %COB (%), Rmax (km), and IVC.
    """
    total_count = len(samples)
    viable_samples = [s for s in samples if s.viable]
    covered_count = len(viable_samples)

    if covered_count == 0:
        return CoverageMetrics(
            effective_coverage_area_km2=0.0,
            coverage_percentage=0.0,
            max_coverage_radius_km=0.0,
            variability_index=0.0,
            total_area_km2=max(0.0, float(total_area_km2)),
            covered_samples_count=0,
            total_samples_count=total_count,
        )

    # RN-44: Effective Coverage Area (ACE) in km²
    ace_km2 = sum(s.cell_area_km2 for s in viable_samples)

    # RN-45: Coverage Percentage (%COB)
    safe_total_area = max(ace_km2, float(total_area_km2))
    cob_pct = min(100.0, max(0.0, (ace_km2 / safe_total_area) * 100.0))

    # RN-46: Maximum Coverage Radius (Rmax) in km
    max_radius_km = max(s.distance_m / 1000.0 for s in viable_samples)

    # RN-47: Coverage Variability Index (IVC = sigma / mu) on linear mW
    # P_mW = 10^(P_rx_dbm / 10)
    powers_mw = [10.0 ** (s.received_power_dbm / 10.0) for s in viable_samples]

    if covered_count < 2:
        ivc = 0.0
    else:
        mean_mw = sum(powers_mw) / float(covered_count)
        if mean_mw <= 0.0:
            ivc = 0.0
        else:
            variance_mw = sum((p - mean_mw) ** 2 for p in powers_mw) / float(
                covered_count - 1
            )
            std_mw = math.sqrt(variance_mw)
            ivc = std_mw / mean_mw

    return CoverageMetrics(
        effective_coverage_area_km2=round(ace_km2, 4),
        coverage_percentage=round(cob_pct, 2),
        max_coverage_radius_km=round(max_radius_km, 3),
        variability_index=round(ivc, 4),
        total_area_km2=round(safe_total_area, 4),
        covered_samples_count=covered_count,
        total_samples_count=total_count,
    )
