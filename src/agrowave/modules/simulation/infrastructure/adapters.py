"""Infrastructure adapters for ScenarioSnapshotSource and SimulationJobRunner."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from sqlalchemy.engine import Engine

from agrowave.modules.scenarios.domain.models import geodesic_distance_km
from agrowave.modules.scenarios.public import ScenariosService
from agrowave.modules.simulation.application.use_cases.run_simulation import (
    ExecuteSimulationJob,
)
from agrowave.modules.simulation.domain.errors import (
    ScenarioNotSimulableError,
    SimulationNotFoundError,
)
from agrowave.modules.simulation.domain.models import ScenarioSnapshot, Technology
from agrowave.modules.simulation.domain.ports import (
    PropagationEngine,
    TerrainProfileProvider,
)
from agrowave.modules.simulation.infrastructure.sqlmodel_simulation_repository import (
    SqlModelSimulationRepository,
)
from agrowave.modules.terrain.public import TerrainService


class ScenariosModuleSnapshotSource:
    """Adapter building a validated ScenarioSnapshot via ScenariosService and TerrainService."""

    def __init__(
        self,
        scenarios_service: ScenariosService,
        terrain_service: TerrainService,
    ) -> None:
        """Initializes the adapter with public facades of scenarios and terrain."""
        self._scenarios_service = scenarios_service
        self._terrain_service = terrain_service

    def capture_simulable_snapshot(
        self,
        scenario_id: UUID,
        owner_id: UUID,
    ) -> ScenarioSnapshot:
        """Validates the scenario and returns an immutable ScenarioSnapshot (RN-31, RN-32).

        Raises:
            SimulationNotFoundError: If the scenario does not exist or belongs to another owner.
            ScenarioNotSimulableError: If the scenario is not simulable (RN-31).
        """
        scenario = self._scenarios_service.get_scenario(scenario_id)
        if scenario is None or scenario.owner_id != owner_id:
            raise SimulationNotFoundError(str(scenario_id))

        dem = (
            self._terrain_service.get_dem(scenario.terrain_ref.dem_id)
            if scenario.terrain_ref is not None
            else None
        )
        dem_available = (
            dem is not None and dem.owner_id == owner_id and dem.status.value == "AVAILABLE"
        )

        causes = scenario.validate_for_simulation(dem_available=dem_available)
        if causes:
            raise ScenarioNotSimulableError(
                [{"code": c.code, "message": c.message} for c in causes]
            )

        assert scenario.study_area is not None
        assert scenario.terrain_ref is not None
        assert scenario.radio_config is not None
        assert scenario.propagation_setup is not None
        assert dem is not None

        b = scenario.study_area.bounds
        an_map = {an.id: an for an in scenario.deployment.access_nodes}
        en_map = {en.id: en for en in scenario.deployment.end_nodes}
        access_nodes = [
            {
                "id": str(an.id),
                "name": an.name,
                "lat": an.position.lat,
                "lng": an.position.lng,
                "height_agl_m": an.height_agl.meters,
                "antenna_ref": an.antenna.reference,
                "antenna_gain_dbi": an.antenna.gain_dbi,
                "polarization": (
                    an.antenna.polarization.value if an.antenna.polarization else "VERTICAL"
                ),
                "sensitivity_dbm": an.sensitivity_dbm,
                "sensitivity_origin": an.sensitivity_origin.value,
            }
            for an in scenario.deployment.access_nodes
        ]
        end_nodes = [
            {
                "id": str(en.id),
                "name": en.name,
                "lat": en.position.lat,
                "lng": en.position.lng,
                "height_agl_m": en.height_agl.meters,
                "antenna_ref": en.antenna.reference,
                "antenna_gain_dbi": en.antenna.gain_dbi,
                "polarization": (
                    en.antenna.polarization.value if en.antenna.polarization else "VERTICAL"
                ),
                "tx_power_nominal_dbm": en.tx_power.nominal_dbm,
                "tx_power_tolerance_db": en.tx_power.tolerance_db,
            }
            for en in scenario.deployment.end_nodes
        ]
        links = [
            {
                "id": str(lnk.id),
                "end_node_id": str(lnk.end_node_id),
                "access_node_id": str(lnk.access_node_id),
                "distance_km": round(
                    geodesic_distance_km(
                        en_map[lnk.end_node_id].position,
                        an_map[lnk.access_node_id].position,
                    ),
                    4,
                ),
            }
            for lnk in scenario.deployment.links
        ]
        p = scenario.propagation_setup.parameters
        prop_params = {
            "ens0": p.ens0,
            "ipol": p.ipol,
            "eps": p.eps,
            "sgm": p.sgm,
            "klim": p.klim,
            "mdvar": p.mdvar,
            "qc": p.qc,
            "qr": list(p.qr),
        }

        return ScenarioSnapshot(
            scenario_id=scenario.id,
            comparison_group_id=scenario.comparison_group_id,
            name=scenario.name,
            technology=Technology(scenario.radio_config.technology.value),
            frequency_mhz=scenario.radio_config.frequency_mhz,
            propagation_model_id=scenario.propagation_setup.model_id,
            propagation_params=prop_params,
            dem_id=dem.id,
            bounds={
                "south": b.south,
                "west": b.west,
                "north": b.north,
                "east": b.east,
            },
            access_nodes=access_nodes,
            end_nodes=end_nodes,
            links=links,
            dem_object_key=dem.object_key,
            dem_resolution_m=dem.resolution_m or 30.0,
        )


_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sim-worker")


class ThreadPoolSimulationJobRunner:
    """In-process background job runner for simulations using its own DB session (ADR-03)."""

    def __init__(
        self,
        engine: Engine,
        profile_provider: TerrainProfileProvider,
        propagation_engine: PropagationEngine,
        run_synchronously: bool = False,
    ) -> None:
        """Initializes the job runner with a database engine and external ports."""
        self._engine = engine
        self._profile_provider = profile_provider
        self._propagation_engine = propagation_engine
        self._run_synchronously = run_synchronously

    def enqueue(self, simulation_id: UUID) -> None:
        """Schedules or runs the simulation evaluation job."""
        if self._run_synchronously:
            self._run_job(simulation_id)
        else:
            _EXECUTOR.submit(self._run_job, simulation_id)

    def _run_job(self, simulation_id: UUID) -> None:
        """Executes the simulation job using an isolated repository instance."""
        repo = SqlModelSimulationRepository(self._engine)
        executor = ExecuteSimulationJob(
            repository=repo,
            profile_provider=self._profile_provider,
            propagation_engine=self._propagation_engine,
        )
        executor.execute(simulation_id)
