"""FastAPI dependency providers for the terrain bounded context."""

import os
from functools import lru_cache

import boto3
from fastapi import Depends
from sqlalchemy.engine import Engine

from agrowave.modules.scenarios.infrastructure.adapters import ScenariosDemUsageQuery
from agrowave.modules.scenarios.infrastructure.sqlmodel_scenario_repository import (
    SqlModelScenarioRepository,
)
from agrowave.modules.scenarios.public import ScenariosService
from agrowave.modules.terrain.domain.ports import (
    DemObjectStore,
    DemRepository,
    DemUsageQuery,
    ElevationSource,
    TerritoryBoundary,
)
from agrowave.modules.terrain.infrastructure.colombia_territory_boundary import (
    ColombiaTerritoryBoundary,
)
from agrowave.modules.terrain.infrastructure.fabdem_elevation_source import (
    FabdemElevationSource,
)
from agrowave.modules.terrain.infrastructure.s3_dem_object_store import S3DemObjectStore
from agrowave.modules.terrain.infrastructure.sqlmodel_dem_repository import (
    SqlModelDemRepository,
)
from agrowave.settings import Settings, get_settings
from agrowave.shared.infrastructure.database import get_engine


@lru_cache(maxsize=1)
def get_terrain_engine() -> Engine:
    """Provides cached database engine for terrain module."""
    return get_engine()


def get_dem_repository(
    engine: Engine = Depends(get_terrain_engine),
) -> DemRepository:
    """Provides the DemRepository implementation."""
    return SqlModelDemRepository(engine)


def get_territory_boundary() -> TerritoryBoundary:
    """Provides the continental Colombia boundary checker (RN-12)."""
    return ColombiaTerritoryBoundary()


def get_elevation_source() -> ElevationSource:
    """Provides the FABDEM elevation tile downloader (RN-25)."""
    cache_dir = os.environ.get("FABDEM_CACHE_DIR", "/var/cache/fabdem")
    return FabdemElevationSource(cache_dir=cache_dir)


def get_dem_object_store(
    settings: Settings = Depends(get_settings),
) -> DemObjectStore:
    """Provides the S3/MinIO raster object store."""
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        region_name=settings.s3_region,
    )
    return S3DemObjectStore(s3_client=s3_client, bucket_name=settings.s3_bucket_dems)


def get_dem_usage_query(
    engine: Engine = Depends(get_terrain_engine),
) -> DemUsageQuery:
    """Provides the DEM usage checker backed by ScenariosService (RN-28)."""
    scenario_repo = SqlModelScenarioRepository(engine)
    return ScenariosDemUsageQuery(ScenariosService(scenario_repo))
