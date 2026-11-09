"""Ports and DTOs for the scenarios bounded context."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.scenarios.domain.models import (
    Bounds,
    Polarization,
    Scenario,
    Technology,
)


@dataclass(frozen=True)
class ProfileBandInfo:
    """Frequency band metadata retrieved from the profiles bounded context.

    Attributes:
        code: Band code (e.g., 'US915', 'B28').
        min_mhz: Optional minimum frequency in MHz.
        max_mhz: Optional maximum frequency in MHz.
    """

    code: str
    min_mhz: float | None = None
    max_mhz: float | None = None


@dataclass(frozen=True)
class ProfileInfo:
    """LPWAN profile summary retrieved from the profiles bounded context.

    Attributes:
        id: Unique identifier of the profile.
        technology: Technology family.
        bands: Supported frequency bands.
        reference_sensitivity_dbm: Reference sensitivity of the access node, in dBm.
        owner_id: Optional owner identifier (None if predefined).
    """

    id: UUID
    technology: Technology
    bands: tuple[ProfileBandInfo, ...]
    reference_sensitivity_dbm: float
    owner_id: UUID | None = None


@dataclass(frozen=True)
class NodeTemplateInfo:
    """Node template summary retrieved from the profiles bounded context.

    Attributes:
        id: Unique identifier of the template.
        name: Display name of the template.
        technology: Technology family.
        role: Node role ('END_NODE' or 'ACCESS_NODE').
        antenna_ref: Commercial reference of the antenna.
        antenna_gain_dbi: Antenna gain in dBi, or None when pending verification.
        polarization: Antenna polarization.
        tx_power_nominal_dbm: Nominal TX power in dBm (for end nodes).
        tx_power_tolerance_db: TX power tolerance in dB (for end nodes).
    """

    id: UUID
    name: str
    technology: Technology
    role: str
    antenna_ref: str
    antenna_gain_dbi: float | None
    polarization: Polarization
    tx_power_nominal_dbm: float | None = None
    tx_power_tolerance_db: float | None = None


@dataclass(frozen=True)
class DemInfo:
    """DEM summary retrieved from the terrain bounded context.

    Attributes:
        id: Unique identifier of the DEM.
        owner_id: Identifier of the user who owns the DEM.
        bounds: Geographic bounding box of the DEM in decimal degrees.
        status: Current lifecycle status ('PENDING', 'DOWNLOADING', 'AVAILABLE', 'FAILED').
    """

    id: UUID
    owner_id: UUID
    bounds: Bounds
    status: str


class ScenarioRepository(ABC):
    """Port for persisting and retrieving Scenario aggregates."""

    @abstractmethod
    def save(self, scenario: Scenario) -> Scenario:
        """Persists a scenario aggregate (insert or full update).

        Args:
            scenario: Scenario aggregate to persist.

        Returns:
            Persisted Scenario aggregate.
        """

    @abstractmethod
    def get_by_id(self, scenario_id: UUID) -> Scenario | None:
        """Retrieves a scenario by its unique identifier.

        Args:
            scenario_id: Scenario UUID.

        Returns:
            Scenario if found, None otherwise.
        """

    @abstractmethod
    def list_by_owner(self, owner_id: UUID) -> list[Scenario]:
        """Lists all scenarios owned by a specific user.

        Args:
            owner_id: User UUID.

        Returns:
            List of Scenario aggregates ordered by most recent first.
        """

    @abstractmethod
    def delete(self, scenario_id: UUID) -> None:
        """Deletes a scenario and its child deployment rows.

        Args:
            scenario_id: Scenario UUID.
        """

    @abstractmethod
    def is_profile_in_use(self, profile_id: UUID) -> bool:
        """Checks whether any persisted scenario references the given profile (RN-09).

        Args:
            profile_id: LPWAN profile UUID.

        Returns:
            True if at least one scenario references the profile.
        """

    @abstractmethod
    def is_dem_in_use(self, dem_id: UUID) -> bool:
        """Checks whether any persisted scenario references the given DEM (RN-28).

        Args:
            dem_id: DEM UUID.

        Returns:
            True if at least one scenario references the DEM.
        """


class TerritoryBoundary(ABC):
    """Port for checking whether a study area lies within continental Colombia (RN-12)."""

    @abstractmethod
    def is_within_colombia_continental(self, bounds: Bounds) -> bool:
        """Evaluates whether the bounding box is inside continental Colombia.

        Args:
            bounds: Geographic rectangle in WGS84 decimal degrees.

        Returns:
            True if the rectangle lies completely within continental Colombia.
        """


class ProfileLookup(ABC):
    """Port for querying LPWAN profiles and node templates from the profiles context."""

    @abstractmethod
    def get_profile(self, profile_id: UUID, user_id: UUID) -> ProfileInfo | None:
        """Retrieves an accessible profile (predefined or owned by user_id).

        Args:
            profile_id: Profile UUID.
            user_id: Authenticated user UUID.

        Returns:
            ProfileInfo if found and accessible, None otherwise.
        """

    @abstractmethod
    def get_templates(self, technology: Technology) -> list[NodeTemplateInfo]:
        """Retrieves predefined node templates for a given LPWAN technology.

        Args:
            technology: Target technology family.

        Returns:
            List of NodeTemplateInfo records.
        """


class DemLookup(ABC):
    """Port for querying DEM metadata from the terrain context."""

    @abstractmethod
    def get_dem(self, dem_id: UUID, user_id: UUID) -> DemInfo | None:
        """Retrieves a DEM owned by the user.

        Args:
            dem_id: DEM UUID.
            user_id: Authenticated user UUID.

        Returns:
            DemInfo if found and owned by user_id, None otherwise.
        """
