"""Application factory and main FastAPI configuration."""

from collections.abc import Callable

from fastapi import FastAPI

from agrowave.shared.presentation.health import create_health_router


def create_app(db_probe: Callable[[], bool] | None = None) -> FastAPI:
    """Creates and configures an AGROWAVE FastAPI application.

    Args:
        db_probe: Optional callable for verifying database health. If None,
            defaults to a probe returning True.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="AGROWAVE API",
        description="LPWAN uplink link simulator over FABDEM terrain in Colombia.",
        version="0.1.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )

    probe = db_probe or (lambda: True)
    health_router = create_health_router(probe)
    app.include_router(health_router, prefix="/api/v1")

    return app


# Default app placeholder; container.py provides the fully-wired application instance.
app = create_app()
