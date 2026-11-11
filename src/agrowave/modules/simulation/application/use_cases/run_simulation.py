"""Use cases for starting and executing a simulation in the background (UC-SI-02)."""

import math
from uuid import UUID

from agrowave.modules.simulation.domain.coverage_models import CoverageResult
from agrowave.modules.simulation.domain.errors import SimulationNotFoundError
from agrowave.modules.simulation.domain.models import (
    LinkResult,
    PathLossPrediction,
    SensitivityOrigin,
    Simulation,
    SimulationResult,
    SimulationStatus,
    SimulationWarning,
)
from agrowave.modules.simulation.domain.ports import (
    CoverageEnginePort,
    PropagationEngine,
    SimulationJobRunner,
    SimulationRepository,
    TerrainProfileProvider,
)
from agrowave.modules.simulation.domain.services import (
    FreeSpacePathLoss,
    FresnelAnalyzer,
    LinkBudget,
)

EARTH_RADIUS_M = 6_371_000.0


def _haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculates horizontal great-circle distance in meters between two WGS84 coordinates."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat_r = math.radians(lat2 - lat1)
    dlng_r = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat_r / 2.0) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng_r / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return EARTH_RADIUS_M * c


class RunSimulation:
    """Transitions simulation from CREATED to RUNNING and enqueues execution (UC-SI-02)."""

    def __init__(
        self,
        repository: SimulationRepository,
        job_runner: SimulationJobRunner,
    ) -> None:
        """Initializes the use case with repository and job runner ports."""
        self._repository = repository
        self._job_runner = job_runner

    def execute(self, simulation_id: UUID, owner_id: UUID) -> Simulation:
        """Starts the simulation and schedules its asynchronous evaluation.

        Args:
            simulation_id: Identifier of the simulation to run.
            owner_id: Identifier of the requesting user.

        Returns:
            Updated Simulation aggregate in RUNNING status.

        Raises:
            SimulationNotFoundError: If the simulation does not exist or belongs to another user.
            InvalidStatusTransitionError: If the simulation is not in CREATED status (RN-30).
        """
        simulation = self._repository.get_by_id(simulation_id=simulation_id, owner_id=owner_id)
        if simulation is None:
            raise SimulationNotFoundError(str(simulation_id))

        simulation.start()
        self._repository.save(simulation)
        self._job_runner.enqueue(simulation.id)
        return simulation


class ExecuteSimulationJob:
    """Background worker use case that evaluates all links in a RUNNING simulation (UC-SI-02)."""

    def __init__(
        self,
        repository: SimulationRepository,
        profile_provider: TerrainProfileProvider,
        propagation_engine: PropagationEngine,
        coverage_engine: CoverageEnginePort | None = None,
    ) -> None:
        """Initializes executor with repository, terrain, propagation, and coverage ports."""
        self._repository = repository
        self._profile_provider = profile_provider
        self._propagation_engine = propagation_engine
        self._coverage_engine = coverage_engine

    def execute(self, simulation_id: UUID) -> None:
        """Evaluates Fresnel, path loss, and link budget for every link in the snapshot.

        Saves COMPLETED with link results and warnings on success, or FAILED with
        failure_reason if an exception occurs (RN-30, RN-34, RN-35, RN-36, RN-42, RN-43).

        Args:
            simulation_id: Identifier of the RUNNING simulation to process.
        """
        simulation = self._repository.get_by_id_unscoped(simulation_id)
        if simulation is None or simulation.status != SimulationStatus.RUNNING:
            return

        try:
            snapshot = simulation.snapshot
            an_by_id = {str(an["id"]): an for an in snapshot.access_nodes}
            en_by_id = {str(en["id"]): en for en in snapshot.end_nodes}

            link_results: list[LinkResult] = []
            warnings: list[SimulationWarning] = []

            for link_data in snapshot.links:
                link_id = UUID(str(link_data["id"]))
                en = en_by_id[str(link_data["end_node_id"])]
                an = an_by_id[str(link_data["access_node_id"])]

                start_lat = float(en["lat"])
                start_lng = float(en["lng"])
                end_lat = float(an["lat"])
                end_lng = float(an["lng"])

                exact_distance_m = _haversine_distance_m(start_lat, start_lng, end_lat, end_lng)
                if exact_distance_m <= 0.0 and link_data.get("distance_km") is not None:
                    exact_distance_m = float(link_data["distance_km"]) * 1000.0
                distance_m = round(exact_distance_m, 2)

                tx_height_m = float(en["height_agl_m"])
                rx_height_m = float(an["height_agl_m"])
                tx_power_dbm = float(en["tx_power_nominal_dbm"])
                tx_gain_dbi = float(en["antenna_gain_dbi"])
                rx_gain_dbi = float(an["antenna_gain_dbi"])
                sensitivity_dbm = float(an["sensitivity_dbm"])
                sensitivity_origin = SensitivityOrigin(
                    str(an.get("sensitivity_origin", "REFERENCE_TO_VERIFY"))
                )
                polarization = str(en.get("polarization", "VERTICAL"))

                sampled_profile = self._profile_provider.extract_profile(
                    dem_id=snapshot.dem_id,
                    dem_object_key=snapshot.dem_object_key,
                    window_bounds=snapshot.bounds,
                    start_lat=start_lat,
                    start_lng=start_lng,
                    end_lat=end_lat,
                    end_lng=end_lng,
                    distance_m=exact_distance_m,
                    resolution_m=snapshot.dem_resolution_m,
                )

                fresnel_analysis, profile_series = FresnelAnalyzer.analyze(
                    distances_m=sampled_profile.distances_m,
                    elevations_m=sampled_profile.elevations_m,
                    tx_height_agl_m=tx_height_m,
                    rx_height_agl_m=rx_height_m,
                    frequency_mhz=snapshot.frequency_mhz,
                )

                engine_out = self._propagation_engine.evaluate_link(
                    profile=sampled_profile,
                    frequency_mhz=snapshot.frequency_mhz,
                    tx_height_agl_m=tx_height_m,
                    rx_height_agl_m=rx_height_m,
                    polarization=polarization,
                    propagation_params=snapshot.propagation_params,
                )

                for warn_code, warn_msg in engine_out.warnings:
                    warnings.append(
                        SimulationWarning(
                            link_id=link_id,
                            source=snapshot.propagation_model_id,
                            code=warn_code,
                            message=warn_msg,
                        )
                    )

                fspl_db = FreeSpacePathLoss.calculate(
                    distance_m=exact_distance_m,
                    frequency_mhz=snapshot.frequency_mhz,
                )
                path_loss_pred = PathLossPrediction(
                    free_space_loss_db=fspl_db,
                    loss_by_quantile=engine_out.quantiles,
                )

                budget = LinkBudget.evaluate(
                    tx_power_dbm=tx_power_dbm,
                    tx_gain_dbi=tx_gain_dbi,
                    rx_gain_dbi=rx_gain_dbi,
                    path_loss_db=path_loss_pred.primary_loss_db(),
                    sensitivity_dbm=sensitivity_dbm,
                    sensitivity_origin=sensitivity_origin,
                )

                link_results.append(
                    LinkResult(
                        link_id=link_id,
                        end_node_name=str(en["name"]),
                        access_node_name=str(an["name"]),
                        distance_m=distance_m,
                        fresnel=fresnel_analysis,
                        path_loss=path_loss_pred,
                        received_power_dbm=budget.received_power_dbm,
                        sensitivity_used_dbm=budget.sensitivity_used_dbm,
                        sensitivity_origin=budget.sensitivity_origin,
                        margin_db=budget.margin_db,
                        viable=budget.viable,
                        profile_series=profile_series,
                    )
                )

            coverage_res: CoverageResult | None = None
            if self._coverage_engine is not None and snapshot.access_nodes:
                try:
                    primary_an = snapshot.access_nodes[0]
                    first_en = snapshot.end_nodes[0] if snapshot.end_nodes else {}
                    radio_params = {
                        "frequency_mhz": snapshot.frequency_mhz,
                        "tx_power_dbm": float(first_en.get("tx_power_nominal_dbm", 20.0)),
                        "tx_gain_dbi": float(first_en.get("antenna_gain_dbi", 2.0)),
                        "tx_height_agl_m": float(first_en.get("height_agl_m", 2.0)),
                    }
                    coverage_res = self._coverage_engine.compute_coverage(
                        access_node=primary_an,
                        bounds=snapshot.bounds,
                        radio_params=radio_params,
                        itm_params=snapshot.propagation_params,
                    )
                except Exception as cov_err:
                    warnings.append(
                        SimulationWarning(
                            link_id=None,
                            source="COVERAGE_ENGINE",
                            code="COVERAGE_CALC_FAILED",
                            message=str(cov_err),
                        )
                    )

            simulation.complete(
                SimulationResult(
                    link_results=tuple(link_results),
                    warnings=tuple(warnings),
                    coverage_result=coverage_res,
                )
            )
            self._repository.save(simulation)
        except Exception as exc:
            target = (
                simulation
                if simulation.status == SimulationStatus.RUNNING
                else self._repository.get_by_id_unscoped(simulation_id)
            )
            if target is not None and target.status == SimulationStatus.RUNNING:
                target.fail(str(exc))
                self._repository.save(target)
