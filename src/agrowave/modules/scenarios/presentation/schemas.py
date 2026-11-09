"""Pydantic request and response schemas for the scenarios API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from agrowave.modules.scenarios.domain.models import (
    Polarization,
    SensitivityOrigin,
    Technology,
)


class BoundsSchema(BaseModel):
    """Geographic bounding box in WGS84 decimal degrees."""

    south: float
    west: float
    north: float
    east: float


class AccessNodeInputSchema(BaseModel):
    """Input schema for an access node inside a scenario."""

    id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=120)
    lat: float
    lng: float
    height_agl_m: float
    antenna_ref: str | None = None
    antenna_gain_dbi: float
    polarization: Polarization = Polarization.VERTICAL
    sensitivity_dbm: float
    sensitivity_origin: SensitivityOrigin = SensitivityOrigin.REFERENCE_TO_VERIFY


class EndNodeInputSchema(BaseModel):
    """Input schema for an end node inside a scenario."""

    id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=120)
    lat: float
    lng: float
    height_agl_m: float
    antenna_ref: str | None = None
    antenna_gain_dbi: float
    polarization: Polarization = Polarization.VERTICAL
    tx_power_nominal_dbm: float
    tx_power_tolerance_db: float = 0.0
    source_template_id: UUID | None = None


class LinkInputSchema(BaseModel):
    """Input schema for an uplink link between an end node and an access node."""

    id: UUID | None = None
    end_node_id: UUID
    access_node_id: UUID


class LongleyRiceParamsSchema(BaseModel):
    """Parameters for the Longley-Rice (ITM) propagation model."""

    ens0: float
    ipol: int = 1
    eps: float = 15.0
    sgm: float = 0.005
    klim: int = 5
    mdvar: int = 11
    qc: float = 50.0
    qr: list[float] = Field(default_factory=lambda: [10.0, 50.0, 90.0])


class PropagationSetupSchema(BaseModel):
    """Propagation model configuration."""

    model_id: str = "LONGLEY_RICE"
    schema_version: int = 1
    parameters: LongleyRiceParamsSchema


class CreateScenarioRequest(BaseModel):
    """Request payload for creating or updating a scenario."""

    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    bounds: BoundsSchema
    dem_id: UUID | None = None
    profile_id: UUID | None = None
    band_code: str | None = None
    frequency_mhz: float | None = None
    access_nodes: list[AccessNodeInputSchema] = Field(default_factory=list)
    end_nodes: list[EndNodeInputSchema] = Field(default_factory=list)
    links: list[LinkInputSchema] = Field(default_factory=list)
    propagation_setup: PropagationSetupSchema | None = None


class UpdateScenarioRequest(CreateScenarioRequest):
    """Request payload for updating an existing scenario."""


class DuplicateScenarioRequest(BaseModel):
    """Optional request payload when duplicating a scenario."""

    name: str | None = None


class CreateScenarioVariantRequest(BaseModel):
    """Request payload when creating a scenario variant with another LPWAN profile."""

    target_profile_id: UUID
    band_code: str | None = None
    frequency_mhz: float | None = None
    name: str | None = None


class AccessNodeResponseSchema(BaseModel):
    """Response schema for an access node."""

    id: UUID
    name: str
    lat: float
    lng: float
    height_agl_m: float
    antenna_ref: str | None
    antenna_gain_dbi: float
    polarization: Polarization | None
    sensitivity_dbm: float
    sensitivity_origin: SensitivityOrigin


class EndNodeResponseSchema(BaseModel):
    """Response schema for an end node."""

    id: UUID
    name: str
    lat: float
    lng: float
    height_agl_m: float
    antenna_ref: str | None
    antenna_gain_dbi: float
    polarization: Polarization | None
    tx_power_nominal_dbm: float
    tx_power_tolerance_db: float
    source_template_id: UUID | None


class LinkResponseSchema(BaseModel):
    """Response schema for an uplink link."""

    id: UUID
    end_node_id: UUID
    access_node_id: UUID


class RadioConfigResponseSchema(BaseModel):
    """Response schema for the scenario's radio configuration."""

    profile_id: UUID
    technology: Technology
    band_code: str
    frequency_mhz: float


class TerrainRefResponseSchema(BaseModel):
    """Response schema for the scenario's terrain reference."""

    dem_id: UUID
    window: BoundsSchema


class ScenarioResponse(BaseModel):
    """Full response schema for a Scenario aggregate."""

    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    comparison_group_id: UUID
    bounds: BoundsSchema
    terrain_ref: TerrainRefResponseSchema | None
    radio_config: RadioConfigResponseSchema | None
    access_nodes: list[AccessNodeResponseSchema]
    end_nodes: list[EndNodeResponseSchema]
    links: list[LinkResponseSchema]
    propagation_setup: PropagationSetupSchema | None
    created_at: datetime
    updated_at: datetime


class ValidationCauseResponse(BaseModel):
    """Response schema for a single simulation blocking cause."""

    code: str
    message: str


class ScenarioValidationResponse(BaseModel):
    """Response schema for POST /scenarios/{id}/validate (RN-31, AC-16)."""

    simulable: bool
    causes: list[ValidationCauseResponse]
