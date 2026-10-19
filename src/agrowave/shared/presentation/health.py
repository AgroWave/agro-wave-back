"""Health check presentation endpoints."""

from collections.abc import Callable

from fastapi import APIRouter, Response, status
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Schema representing the health status of the application and its dependencies.

    Attributes:
        status: High-level status ('ok' or 'degraded').
        database: Status of the primary relational database ('ok' or 'unavailable').
    """

    status: str
    database: str


def create_health_router(db_probe: Callable[[], bool]) -> APIRouter:
    """Creates a health check APIRouter with an injected database probe.

    Args:
        db_probe: Callable returning True if the database is reachable, False otherwise.

    Returns:
        Configured APIRouter handling GET /health.
    """
    router = APIRouter(tags=["health"])

    @router.get(
        "/health",
        response_model=HealthResponse,
        responses={
            200: {"description": "System is fully operational"},
            503: {"description": "One or more core components are unavailable"},
        },
    )
    def check_health(response: Response) -> HealthResponse:
        """Returns the health status of the API and its backing services."""
        is_db_healthy = db_probe()

        if is_db_healthy:
            return HealthResponse(status="ok", database="ok")

        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", database="unavailable")

    return router
