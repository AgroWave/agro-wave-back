"""Composition root wiring adapters and presentation."""

from fastapi import FastAPI

from agrowave.main import create_app
from agrowave.shared.infrastructure.database import ping_database


def create_container_app() -> FastAPI:
    """Builds the FastAPI application fully wired to infrastructure adapters.

    Returns:
        Configured FastAPI application instance.
    """
    return create_app(db_probe=ping_database)


app = create_container_app()
