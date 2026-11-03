"""Domain models and value objects for the LPWAN profiles module."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from agrowave.modules.profiles.domain.errors import (
    InvalidBandRangeError,
    SpreadingFactorNotAllowedError,
)


class Technology(StrEnum):
    """Supported LPWAN technologies."""

    LORAWAN = "LORAWAN"
    NB_IOT = "NB_IOT"
    LTE_M = "LTE_M"


class NodeRole(StrEnum):
    """Role of a network node."""

    END_NODE = "END_NODE"
    ACCESS_NODE = "ACCESS_NODE"


class Polarization(StrEnum):
    """Antenna polarization."""

    VERTICAL = "VERTICAL"
    HORIZONTAL = "HORIZONTAL"


@dataclass(frozen=True)
class Band:
    """Frequency band for LPWAN communication.

    Attributes:
        code: Identifier or 3GPP band code (e.g. '902-928', 'B1', 'B28').
        min_mhz: Lower frequency limit in MHz.
        max_mhz: Upper frequency limit in MHz.

    Raises:
        InvalidBandRangeError: If min_mhz >= max_mhz when both are specified.
    """

    code: str
    min_mhz: float | None = None
    max_mhz: float | None = None

    def __post_init__(self) -> None:
        """Validate that the band range is strictly increasing when both limits exist."""
        if self.min_mhz is not None and self.max_mhz is not None and self.min_mhz >= self.max_mhz:
            raise InvalidBandRangeError(
                f"min_mhz ({self.min_mhz}) must be strictly less than max_mhz ({self.max_mhz})"
            )


@dataclass(frozen=True)
class Antenna:
    """Antenna specification.

    Attributes:
        reference: Commercial reference or model name.
        gain_dbi: Antenna gain in dBi, or None while the value has no source ("pending").
        polarization: Optional polarization type.
    """

    reference: str | None = None
    gain_dbi: float | None = None
    polarization: Polarization | None = None


@dataclass(frozen=True)
class TxPower:
    """Transmitter power specification.

    Attributes:
        nominal_dbm: Nominal transmit power in dBm.
        tolerance_db: Manufacturer tolerance in dB.
    """

    nominal_dbm: float
    tolerance_db: float = 0.0


@dataclass
class NodeTemplate:
    """Reference node template defined by technology.

    Attributes:
        id: Unique identifier.
        technology: LPWAN technology this template applies to.
        role: End node or access node.
        name: Display name.
        module_ref: Hardware or radio module reference.
        antenna: Antenna configuration.
        tx_power: Nominal transmit power (end nodes only).
    """

    id: UUID
    technology: Technology
    role: NodeRole
    name: str
    antenna: Antenna
    module_ref: str | None = None
    tx_power: TxPower | None = None


@dataclass
class LpwanProfile:
    """LPWAN radio profile aggregate root.

    Attributes:
        id: Unique identifier.
        name: Profile display name.
        technology: LPWAN technology (LoRaWAN, NB-IoT, LTE-M).
        reference_sensitivity_dbm: Reference receiver sensitivity in dBm.
        bands: List of operating frequency bands.
        spreading_factor: LoRaWAN spreading factor (7..12).
        owner_id: Identifier of the owner user, or None if predefined.
        is_predefined: True if profile is system predefined (read-only for users).
        created_at: Creation timestamp in UTC.

    Raises:
        SpreadingFactorNotAllowedError: If spreading factor is missing or outside 7..12
            for LoRaWAN, or if spreading factor is provided for NB-IoT/LTE-M (RN-07).
    """

    id: UUID
    name: str
    technology: Technology
    reference_sensitivity_dbm: float
    bands: list[Band] = field(default_factory=list)
    spreading_factor: int | None = None
    owner_id: UUID | None = None
    is_predefined: bool = False
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        """Enforce RN-07, derive the predefined flag and default the creation timestamp."""
        if self.technology == Technology.LORAWAN:
            if self.spreading_factor is None or not (7 <= self.spreading_factor <= 12):
                raise SpreadingFactorNotAllowedError(
                    "LoRaWAN requires a spreading factor between 7 and 12, "
                    f"got: {self.spreading_factor} (RN-07)"
                )
        else:
            if self.spreading_factor is not None:
                raise SpreadingFactorNotAllowedError(
                    "Spreading factor is only allowed for LoRaWAN; "
                    f"got {self.spreading_factor} for {self.technology} (RN-07)"
                )

        if self.owner_id is None:
            self.is_predefined = True
        else:
            self.is_predefined = False

        if self.created_at is None:
            self.created_at = datetime.now(UTC)
