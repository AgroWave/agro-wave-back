"""FastAPI dependency providers for the scenarios bounded context."""

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.engine import Engine

from agrowave.modules.profiles.domain.ports import (
    NodeTemplateRepository,
    ProfileRepository,
)
from agrowave.modules.profiles.presentation.dependencies import (
    get_node_template_repository,
    get_profile_repository,
)
from agrowave.modules.profiles.public import ProfilesService
from agrowave.modules.scenarios.domain.ports import (
    DemLookup,
    ProfileLookup,
    ScenarioRepository,
    TerritoryBoundary,
)
from agrowave.modules.scenarios.infrastructure.adapters import (
    ColombiaScenarioTerritoryBoundary,
    ProfilesModuleLookup,
    TerrainModuleLookup,
)
from agrowave.modules.scenarios.infrastructure.sqlmodel_scenario_repository import (
    SqlModelScenarioRepository,
)
from agrowave.modules.terrain.domain.ports import DemRepository
from agrowave.modules.terrain.presentation.dependencies import get_dem_repository
from agrowave.modules.terrain.public import TerrainService
from agrowave.shared.infrastructure.database import get_engine


@lru_cache(maxsize=1)
def get_scenarios_engine() -> Engine:
    """Provides cached database engine for the scenarios module."""
    return get_engine()


def get_scenario_repository(
    engine: Engine = Depends(get_scenarios_engine),
) -> ScenarioRepository:
    """Provides the ScenarioRepository implementation."""
    return SqlModelScenarioRepository(engine)


def get_scenario_territory_boundary() -> TerritoryBoundary:
    """Provides the continental Colombia boundary checker for scenarios (RN-12)."""
    return ColombiaScenarioTerritoryBoundary()


def get_profile_lookup(
    profile_repo: ProfileRepository = Depends(get_profile_repository),
    template_repo: NodeTemplateRepository = Depends(get_node_template_repository),
) -> ProfileLookup:
    """Provides the ProfileLookup adapter backed by ProfilesService."""
    service = ProfilesService(
        profile_repository=profile_repo,
        node_template_repository=template_repo,
    )
    return ProfilesModuleLookup(service)


def get_dem_lookup(
    dem_repo: DemRepository = Depends(get_dem_repository),
) -> DemLookup:
    """Provides the DemLookup adapter backed by TerrainService."""
    service = TerrainService(dem_repository=dem_repo)
    return TerrainModuleLookup(service)
