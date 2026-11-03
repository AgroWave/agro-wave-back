"""Pydantic schemas for the profiles presentation layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agrowave.modules.profiles.domain.models import NodeRole, Polarization, Technology


class BandPayload(BaseModel):
    """Schema for a frequency band in requests."""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(min_length=1, max_length=50)
    min_mhz: float | None = None
    max_mhz: float | None = None


class BandResponse(BaseModel):
    """Schema for a frequency band in responses."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    min_mhz: float | None
    max_mhz: float | None


class AntennaResponse(BaseModel):
    """Schema for antenna configuration in node templates."""

    model_config = ConfigDict(from_attributes=True)

    reference: str | None = None
    gain_dbi: float | None
    polarization: Polarization | None = None


class TxPowerResponse(BaseModel):
    """Schema for transmitter power in node templates."""

    model_config = ConfigDict(from_attributes=True)

    nominal_dbm: float
    tolerance_db: float


class NodeTemplateResponse(BaseModel):
    """Schema for reference node template responses (AC-02-07)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    technology: Technology
    role: NodeRole
    name: str
    module_ref: str | None
    antenna: AntennaResponse
    tx_power: TxPowerResponse | None = None


class CreateProfileRequest(BaseModel):
    """Request payload for creating a custom LPWAN profile (AC-02-04)."""

    name: str = Field(min_length=1, max_length=100)
    technology: Technology
    reference_sensitivity_dbm: float
    bands: list[BandPayload] = Field(default_factory=list)
    spreading_factor: int | None = None


class UpdateProfileRequest(BaseModel):
    """Request payload for updating an owned profile."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    reference_sensitivity_dbm: float | None = None
    bands: list[BandPayload] | None = None
    spreading_factor: int | None = None


class DuplicateProfileRequest(BaseModel):
    """Request payload for duplicating a profile (AC-27)."""

    name: str | None = Field(default=None, max_length=100)


class ProfileResponse(BaseModel):
    """Response payload representing an LPWAN profile."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    technology: Technology
    reference_sensitivity_dbm: float
    bands: list[BandResponse]
    spreading_factor: int | None
    owner_id: UUID | None
    is_predefined: bool
    created_at: datetime
