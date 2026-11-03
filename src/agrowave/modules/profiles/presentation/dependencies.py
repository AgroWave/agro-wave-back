"""FastAPI dependencies for the profiles module."""

from fastapi import Depends
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from agrowave.modules.profiles.domain.ports import (
    NodeTemplateRepository,
    ProfileRepository,
    ProfileUsageQuery,
)
from agrowave.modules.profiles.infrastructure.no_scenarios_profile_usage_query import (
    NoScenariosProfileUsageQuery,
)
from agrowave.modules.profiles.infrastructure.sqlmodel_node_template_repository import (
    SqlModelNodeTemplateRepository,
)
from agrowave.modules.profiles.infrastructure.sqlmodel_profile_repository import (
    SqlModelProfileRepository,
)
from agrowave.settings import get_settings

_engine: Engine | None = None
_usage_query_override: ProfileUsageQuery | None = None


def set_profiles_engine(engine: Engine) -> None:
    """Sets a custom database engine for profiles repositories."""
    global _engine
    _engine = engine


def set_profile_usage_query_override(query: ProfileUsageQuery | None) -> None:
    """Overrides the ProfileUsageQuery implementation (useful for tests)."""
    global _usage_query_override
    _usage_query_override = query


def get_profiles_engine() -> Engine:
    """Returns the database engine for profiles repositories."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(str(settings.database_url))
    return _engine


def get_profile_repository(
    engine: Engine = Depends(get_profiles_engine),
) -> ProfileRepository:
    """Provides ProfileRepository implementation."""
    return SqlModelProfileRepository(engine)


def get_node_template_repository(
    engine: Engine = Depends(get_profiles_engine),
) -> NodeTemplateRepository:
    """Provides NodeTemplateRepository implementation."""
    return SqlModelNodeTemplateRepository(engine)


def get_profile_usage_query() -> ProfileUsageQuery:
    """Provides ProfileUsageQuery implementation."""
    global _usage_query_override
    if _usage_query_override is not None:
        return _usage_query_override
    return NoScenariosProfileUsageQuery()
