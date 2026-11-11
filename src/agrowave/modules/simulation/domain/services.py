"""Pure domain services for Fresnel analysis, link budget, FSPL, and simulation comparison."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.simulation.domain.errors import NotComparableError
from agrowave.modules.simulation.domain.models import (
    ElevationProfileSeries,
    FresnelAnalysis,
    FresnelVerdict,
    SensitivityOrigin,
    Simulation,
    SimulationStatus,
    SimulationSummary,
    Technology,
)

SPEED_OF_LIGHT_MPS = 299_792_458.0
EARTH_RADIUS_M = 6_371_000.0
EFFECTIVE_EARTH_FACTOR_K = 4.0 / 3.0


@dataclass(frozen=True)
class LinkBudgetOutcome:
    """Result of evaluating an uplink radio link budget (RN-34, RN-42).

    Attributes:
        received_power_dbm: Predicted received power at the access node, in dBm.
        margin_db: Link margin above receiver sensitivity, in dB.
        viable: True if margin_db >= 0.0 dB.
        sensitivity_used_dbm: Receiver sensitivity threshold used, in dBm.
        sensitivity_origin: Origin of the receiver sensitivity value (RN-42).
    """

    received_power_dbm: float
    margin_db: float
    viable: bool
    sensitivity_used_dbm: float
    sensitivity_origin: SensitivityOrigin


class LinkBudget:
    """Evaluates uplink LPWAN link budget and viability (RN-34, RN-42)."""

    @staticmethod
    def evaluate(
        tx_power_dbm: float,
        tx_gain_dbi: float,
        rx_gain_dbi: float,
        path_loss_db: float,
        sensitivity_dbm: float,
        sensitivity_origin: SensitivityOrigin,
    ) -> LinkBudgetOutcome:
        """Calculates uplink received power, link margin, and viability.

        Applies Prx = Ptx + Gtx + Grx - PL and compares against the access node
        sensitivity (RN-34). Preserves the sensitivity origin (RN-42).

        Args:
            tx_power_dbm: End node transmit power, in dBm.
            tx_gain_dbi: End node antenna gain, in dBi.
            rx_gain_dbi: Access node antenna gain, in dBi.
            path_loss_db: Predicted path loss (p50), in dB.
            sensitivity_dbm: Access node receiver sensitivity, in dBm.
            sensitivity_origin: Origin of the sensitivity value (RN-42).

        Returns:
            LinkBudgetOutcome with received power in dBm, margin in dB, viability, and sensitivity.
        """
        received_power_dbm = round(tx_power_dbm + tx_gain_dbi + rx_gain_dbi - path_loss_db, 4)
        margin_db = round(received_power_dbm - sensitivity_dbm, 4)
        viable = margin_db >= 0.0
        return LinkBudgetOutcome(
            received_power_dbm=received_power_dbm,
            margin_db=margin_db,
            viable=viable,
            sensitivity_used_dbm=sensitivity_dbm,
            sensitivity_origin=sensitivity_origin,
        )


class FreeSpacePathLoss:
    """Computes reference free-space path loss (FSPL)."""

    @staticmethod
    def calculate(distance_m: float, frequency_mhz: float) -> float:
        """Calculates free-space path loss in dB for a given distance and frequency.

        Args:
            distance_m: Path distance, in meters (m).
            frequency_mhz: Carrier frequency, in MHz.

        Returns:
            Free-space path loss, in dB.
        """
        dist_m = max(distance_m, 1e-3)
        wn = max(frequency_mhz, 1e-3) / 47.7
        fspl_db = 8.685890 * math.log(2.0 * wn * dist_m)
        return round(fspl_db, 2)


class FresnelAnalyzer:
    """Evaluates first Fresnel zone clearance over a sampled terrain profile (RN-35)."""

    @staticmethod
    def analyze(
        distances_m: Sequence[float],
        elevations_m: Sequence[float],
        tx_height_agl_m: float,
        rx_height_agl_m: float,
        frequency_mhz: float,
    ) -> tuple[FresnelAnalysis, ElevationProfileSeries]:
        """Calculates first Fresnel zone radii, Earth curvature bulge, and clearance verdict.

        Uses k = 4/3 and R = 6371 km for Earth curvature bulge, and r1 = sqrt(lambda * d1 * d2 / d)
        along the slant path (RN-35).

        Args:
            distances_m: Horizontal distances from the end node, in meters (m).
            elevations_m: Terrain elevations above sea level at each sample point, in meters (m).
            tx_height_agl_m: End node antenna height above ground level, in meters (m).
            rx_height_agl_m: Access node antenna height above ground level, in meters (m).
            frequency_mhz: Carrier frequency, in MHz.

        Returns:
            Tuple of (FresnelAnalysis summary, ElevationProfileSeries for visualization).
        """
        n = len(distances_m)
        if n < 2 or len(elevations_m) != n:
            raise ValueError("Profile must contain at least 2 matching distance/elevation points.")

        total_d_m = float(distances_m[-1] - distances_m[0])
        if total_d_m <= 0.0:
            raise ValueError("Total link distance must be positive.")

        wavelength_m = SPEED_OF_LIGHT_MPS / (frequency_mhz * 1_000_000.0)
        z_tx_m = float(elevations_m[0]) + tx_height_agl_m
        z_rx_m = float(elevations_m[-1]) + rx_height_agl_m
        delta_h_m = z_rx_m - z_tx_m
        slant_d_m = math.hypot(total_d_m, delta_h_m)

        two_k_r = 2.0 * EFFECTIVE_EARTH_FACTOR_K * EARTH_RADIUS_M

        dist_list: list[float] = []
        terrain_curv_list: list[float] = []
        los_list: list[float] = []
        f1_list: list[float] = []

        min_ratio = float("inf")
        min_ratio_at_m = 0.0
        max_f1_m = 0.0

        for idx in range(n):
            x_m = float(distances_m[idx] - distances_m[0])
            remain_m = max(total_d_m - x_m, 0.0)
            bulge_m = (x_m * remain_m) / two_k_r
            terrain_with_curv_m = float(elevations_m[idx]) + bulge_m
            los_h_m = z_tx_m + (x_m / total_d_m) * delta_h_m

            if 0 < idx < n - 1 and x_m > 0.0 and remain_m > 0.0:
                cos_t = total_d_m / slant_d_m
                r_perp_m = math.sqrt((wavelength_m * x_m * remain_m) / (total_d_m * cos_t))
                r_vert_m = r_perp_m / cos_t
                clearance_m = los_h_m - terrain_with_curv_m
                ratio = clearance_m / r_vert_m if r_vert_m > 0.0 else 0.0
                if ratio < min_ratio:
                    min_ratio = ratio
                    min_ratio_at_m = x_m
                if r_perp_m > max_f1_m:
                    max_f1_m = r_perp_m
            else:
                r_perp_m = 0.0
                r_vert_m = 0.0

            dist_list.append(round(x_m, 2))
            terrain_curv_list.append(round(terrain_with_curv_m, 3))
            los_list.append(round(los_h_m, 3))
            f1_list.append(round(r_perp_m, 3))

        if min_ratio == float("inf"):
            min_ratio = 1.0
            min_ratio_at_m = round(total_d_m / 2.0, 2)

        if min_ratio >= 0.6:
            verdict = FresnelVerdict.CLEAR
        elif min_ratio >= 0.0:
            verdict = FresnelVerdict.MARGINAL
        else:
            verdict = FresnelVerdict.OBSTRUCTED

        analysis = FresnelAnalysis(
            min_clearance_ratio=round(min_ratio, 2),
            min_clearance_at_m=round(min_ratio_at_m, 2),
            max_radius_m=round(max_f1_m, 2),
            verdict=verdict,
        )
        series = ElevationProfileSeries(
            distances_m=tuple(dist_list),
            terrain_with_curvature_m=tuple(terrain_curv_list),
            los_m=tuple(los_list),
            f1_radius_m=tuple(f1_list),
        )
        return analysis, series


@dataclass(frozen=True)
class ComparedSimulationSummary:
    """Summary entry for a single simulation in a multi-variant comparison report.

    Attributes:
        simulation_id: Identifier of the simulation.
        name: Simulation name.
        technology: LPWAN technology of the variant.
        frequency_mhz: Carrier frequency, in MHz.
        summary: Aggregated simulation summary metrics.
    """

    simulation_id: UUID
    name: str
    technology: Technology
    frequency_mhz: float
    summary: SimulationSummary


@dataclass(frozen=True)
class ComparedLinkMetric:
    """Link metrics for a specific simulation variant within a comparison row.

    Attributes:
        simulation_id: Identifier of the simulation.
        simulation_name: Name of the simulation variant.
        technology: LPWAN technology of the variant.
        path_loss_p50_db: Predicted p50 path loss, in dB.
        received_power_dbm: Predicted received power, in dBm.
        sensitivity_used_dbm: Receiver sensitivity threshold used, in dBm.
        margin_db: Link margin, in dB.
        viable: True if margin_db >= 0.0 dB.
        fresnel_verdict: Fresnel zone clearance verdict.
    """

    simulation_id: UUID
    simulation_name: str
    technology: Technology
    path_loss_p50_db: float
    received_power_dbm: float
    sensitivity_used_dbm: float
    margin_db: float
    viable: bool
    fresnel_verdict: FresnelVerdict


@dataclass(frozen=True)
class ComparedLinkRow:
    """Side-by-side comparison of the same physical link across simulation variants.

    Attributes:
        link_key: Grouping key (end_node_name -> access_node_name).
        end_node_name: Name of the transmitting end node.
        access_node_name: Name of the receiving access node.
        distance_m: Horizontal link distance, in meters (m).
        metrics_by_simulation: Tuple of link metrics for each compared simulation.
    """

    link_key: str
    end_node_name: str
    access_node_name: str
    distance_m: float
    metrics_by_simulation: tuple[ComparedLinkMetric, ...]


@dataclass(frozen=True)
class ComparisonReport:
    """Side-by-side comparison report for completed simulations of the same group (RN-37).

    Attributes:
        comparison_group_id: Shared comparison group identifier.
        propagation_model_id: Shared propagation model identifier.
        simulations: Tuple of per-simulation summary entries.
        links: Tuple of per-link comparison rows.
    """

    comparison_group_id: UUID
    propagation_model_id: str
    simulations: tuple[ComparedSimulationSummary, ...]
    links: tuple[ComparedLinkRow, ...]


class ComparisonService:
    """Compares COMPLETED simulations belonging to the same comparison group and model (RN-37)."""

    @staticmethod
    def compare(simulations: Sequence[Simulation]) -> ComparisonReport:
        """Builds a side-by-side comparison report across variant simulations (RN-37).

        Args:
            simulations: Sequence of at least 2 simulations to compare.

        Returns:
            ComparisonReport with summary and per-link metrics across variants.

        Raises:
            NotComparableError: If fewer than 2 simulations are provided, any simulation is not
                COMPLETED, or they do not share comparison_group_id and propagation_model_id.
        """
        if len(simulations) < 2:
            raise NotComparableError("At least two simulations are required for comparison")

        first = simulations[0]
        group_id = first.comparison_group_id
        model_id = first.propagation_model_id

        for sim in simulations:
            if (
                sim.status != SimulationStatus.COMPLETED
                or sim.summary is None
                or sim.result is None
            ):
                raise NotComparableError(
                    f"Simulation '{sim.name}' is in status '{sim.status.value}', not COMPLETED"
                )
            if sim.comparison_group_id != group_id:
                raise NotComparableError("Simulations belong to different comparison groups")
            if sim.propagation_model_id != model_id:
                raise NotComparableError("Simulations use different propagation models")

        sim_summaries = tuple(
            ComparedSimulationSummary(
                simulation_id=sim.id,
                name=sim.name,
                technology=sim.technology,
                frequency_mhz=sim.snapshot.frequency_mhz,
                summary=sim.summary,  # type: ignore[arg-type]
            )
            for sim in simulations
        )

        # Group links by (end_node_name, access_node_name) so variant scenarios match cleanly
        link_order: list[tuple[str, str, float]] = []
        seen_keys: set[tuple[str, str]] = set()
        metrics_map: dict[tuple[str, str], list[ComparedLinkMetric]] = {}

        for sim in simulations:
            assert sim.result is not None
            for lr in sim.result.link_results:
                key = (lr.end_node_name, lr.access_node_name)
                if key not in seen_keys:
                    seen_keys.add(key)
                    link_order.append((lr.end_node_name, lr.access_node_name, lr.distance_m))
                    metrics_map[key] = []
                metrics_map[key].append(
                    ComparedLinkMetric(
                        simulation_id=sim.id,
                        simulation_name=sim.name,
                        technology=sim.technology,
                        path_loss_p50_db=lr.path_loss.primary_loss_db(),
                        received_power_dbm=lr.received_power_dbm,
                        sensitivity_used_dbm=lr.sensitivity_used_dbm,
                        margin_db=lr.margin_db,
                        viable=lr.viable,
                        fresnel_verdict=lr.fresnel.verdict,
                    )
                )

        link_rows = tuple(
            ComparedLinkRow(
                link_key=f"{en_name} → {an_name}",
                end_node_name=en_name,
                access_node_name=an_name,
                distance_m=dist_m,
                metrics_by_simulation=tuple(metrics_map[(en_name, an_name)]),
            )
            for en_name, an_name, dist_m in link_order
        )

        return ComparisonReport(
            comparison_group_id=group_id,
            propagation_model_id=model_id,
            simulations=sim_summaries,
            links=link_rows,
        )
