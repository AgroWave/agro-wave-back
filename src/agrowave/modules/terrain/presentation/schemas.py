"""Pydantic schemas for the terrain REST API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BoundsSchema(BaseModel):
    """Geographic bounding box in WGS84 decimal degrees."""

    south: float = Field(..., description="Southern latitude boundary.")
    west: float = Field(..., description="Western longitude boundary.")
    north: float = Field(..., description="Northern latitude boundary.")
    east: float = Field(..., description="Eastern longitude boundary.")


class CreateDemRequest(BaseModel):
    """Payload for requesting a new DEM download."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    bounds: BoundsSchema


class UpdateDemRequest(BaseModel):
    """Payload for updating DEM metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class DemResponse(BaseModel):
    """Response representation of a DEM entity."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    bounds: BoundsSchema
    status: str
    resolution_m: float
    object_key: str | None
    size_bytes: int | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime

