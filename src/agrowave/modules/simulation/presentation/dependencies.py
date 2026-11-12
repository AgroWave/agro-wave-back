"""FastAPI dependency providers for the simulation bounded context."""

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.engine import Engine

from agrowave.modules.scenarios.domain.ports import ScenarioRepository
from agrowave.modules.scenarios.presentation.dependencies import get_scenario_repository
from agrowave.modules.scenarios.public import ScenariosService
from agrowave.modules.simulation.domain.ports import (
    CoverageEnginePort,
    PropagationEngine,
    ScenarioSnapshotSource,
    SimulationJobRunner,
    SimulationRepository,
    TerrainProfileProvider,
)
from agrowave.modules.simulation.infrastructure.adapters import (
    ScenariosModuleSnapshotSource,
    ThreadPoolSimulationJobRunner,
)
from agrowave.modules.simulation.infrastructure.itm_propagation_engine import (
    ItmLongleyRiceEngine,
)
from agrowave.modules.simulation.infrastructure.polar_sweep_engine import (
    PolarSweepCoverageEngine,
)
from agrowave.modules.simulation.infrastructure.rasterio_profile_provider import (
    RasterioTerrainProfileProvider,
)
from agrowave.modules.simulation.infrastructure.sqlmodel_simulation_repository import (
    SqlModelSimulationRepository,
)
from agrowave.modules.terrain.domain.ports import DemRepository
from agrowave.modules.terrain.presentation.dependencies import get_dem_repository
from agrowave.modules.terrain.public import TerrainService
from agrowave.settings import Settings
from agrowave.shared.infrastructure.database import get_engine


@lru_cache(maxsize=1)
def get_simulation_engine() -> Engine:
    """Provides cached database engine for the simulation module."""
    return get_engine()


def get_simulation_repository(
    engine: Engine = Depends(get_simulation_engine),
) -> SimulationRepository:
    """Provides the SimulationRepository implementation."""
    return SqlModelSimulationRepository(engine)


def get_scenario_snapshot_source(
    scenario_repo: ScenarioRepository = Depends(get_scenario_repository),
    dem_repo: DemRepository = Depends(get_dem_repository),
) -> ScenarioSnapshotSource:
    """Provides the ScenarioSnapshotSource adapter backed by ScenariosService and TerrainService."""
    return ScenariosModuleSnapshotSource(
        scenarios_service=ScenariosService(scenario_repository=scenario_repo),
        terrain_service=TerrainService(dem_repository=dem_repo),
    )


def get_terrain_profile_provider() -> TerrainProfileProvider:
    """Provides the RasterioTerrainProfileProvider for reading COG elevation profiles."""
    return RasterioTerrainProfileProvider(Settings())


def get_propagation_engine() -> PropagationEngine:
    """Provides the Longley-Rice (ITM) point-to-point propagation engine adapter."""
    return ItmLongleyRiceEngine()


def get_coverage_engine() -> CoverageEnginePort:
    """Provides the polar sweep spatial coverage engine adapter (RN-48)."""
    return PolarSweepCoverageEngine()


def get_simulation_job_runner(
    engine: Engine = Depends(get_simulation_engine),
    profile_provider: TerrainProfileProvider = Depends(get_terrain_profile_provider),
    propagation_engine: PropagationEngine = Depends(get_propagation_engine),
    coverage_engine: CoverageEnginePort = Depends(get_coverage_engine),
) -> SimulationJobRunner:
    """Provides the background simulation job runner."""
    is_sqlite = str(engine.url).startswith("sqlite")
    return ThreadPoolSimulationJobRunner(
        engine=engine,
        profile_provider=profile_provider,
        propagation_engine=propagation_engine,
        coverage_engine=coverage_engine,
        run_synchronously=is_sqlite,
    )
