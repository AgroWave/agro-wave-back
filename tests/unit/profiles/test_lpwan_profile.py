"""Unit tests for LpwanProfile domain entity and business rules (RN-07, AC-02-02, AC-02-08)."""

from uuid import uuid4

import pytest

from agrowave.modules.profiles.domain.errors import (
    InvalidBandRangeError,
    SpreadingFactorNotAllowedError,
)
from agrowave.modules.profiles.domain.models import Band, LpwanProfile, Technology


def test_ac02_02_spreading_factor_rules() -> None:
    """Verifies RN-07: SF must be between 7 and 12 for LoRaWAN, and None for NB-IoT/LTE-M."""
    # 1. Valid LoRaWAN profile with SF in 7..12
    profile = LpwanProfile(
        id=uuid4(),
        name="LoRaWAN SF7 Test",
        technology=Technology.LORAWAN,
        spreading_factor=7,
        reference_sensitivity_dbm=-124.0,
        bands=[Band(code="902-928", min_mhz=902.0, max_mhz=928.0)],
    )
    assert profile.spreading_factor == 7

    # 2. Invalid LoRaWAN without SF
    with pytest.raises(SpreadingFactorNotAllowedError):
        LpwanProfile(
            id=uuid4(),
            name="LoRaWAN No SF",
            technology=Technology.LORAWAN,
            spreading_factor=None,
            reference_sensitivity_dbm=-124.0,
            bands=[],
        )

    # 3. Invalid LoRaWAN with SF outside 7..12 (e.g. 6 or 13)
    with pytest.raises(SpreadingFactorNotAllowedError):
        LpwanProfile(
            id=uuid4(),
            name="LoRaWAN SF6",
            technology=Technology.LORAWAN,
            spreading_factor=6,
            reference_sensitivity_dbm=-124.0,
            bands=[],
        )

    with pytest.raises(SpreadingFactorNotAllowedError):
        LpwanProfile(
            id=uuid4(),
            name="LoRaWAN SF13",
            technology=Technology.LORAWAN,
            spreading_factor=13,
            reference_sensitivity_dbm=-124.0,
            bands=[],
        )

    # 4. Valid NB-IoT without SF
    nbiot = LpwanProfile(
        id=uuid4(),
        name="NB-IoT Test",
        technology=Technology.NB_IOT,
        spreading_factor=None,
        reference_sensitivity_dbm=-130.0,
        bands=[Band(code="B1")],
    )
    assert nbiot.spreading_factor is None

    # 5. Invalid NB-IoT with SF
    with pytest.raises(SpreadingFactorNotAllowedError):
        LpwanProfile(
            id=uuid4(),
            name="NB-IoT with SF",
            technology=Technology.NB_IOT,
            spreading_factor=7,
            reference_sensitivity_dbm=-130.0,
            bands=[Band(code="B1")],
        )

    # 6. Invalid LTE-M with SF
    with pytest.raises(SpreadingFactorNotAllowedError):
        LpwanProfile(
            id=uuid4(),
            name="LTE-M with SF",
            technology=Technology.LTE_M,
            spreading_factor=10,
            reference_sensitivity_dbm=-130.0,
            bands=[Band(code="B1")],
        )


def test_ac02_08_band_range_must_be_increasing() -> None:
    """Verifies that min_mhz must be strictly less than max_mhz when both are provided."""
    # Valid band
    band = Band(code="902-928", min_mhz=902.0, max_mhz=928.0)
    assert band.min_mhz == 902.0
    assert band.max_mhz == 928.0

    # Valid band with None ranges (e.g., pending 3GPP frequencies)
    pending_band = Band(code="B28", min_mhz=None, max_mhz=None)
    assert pending_band.min_mhz is None

    # Invalid band: min_mhz >= max_mhz
    with pytest.raises(InvalidBandRangeError):
        Band(code="InvalidEqual", min_mhz=900.0, max_mhz=900.0)

    with pytest.raises(InvalidBandRangeError):
        Band(code="InvalidInverted", min_mhz=928.0, max_mhz=902.0)
