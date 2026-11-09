"""Infrastructure adapters for the scenarios bounded context."""

from uuid import UUID

from shapely.geometry import Polygon, box

from agrowave.modules.profiles.domain.models import Technology as ProfileTechnology
from agrowave.modules.profiles.domain.ports import ProfileUsageQuery
from agrowave.modules.profiles.public import ProfilesService
from agrowave.modules.scenarios.domain.models import Bounds, Polarization, Technology
from agrowave.modules.scenarios.domain.ports import (
    DemInfo,
    DemLookup,
    NodeTemplateInfo,
    ProfileBandInfo,
    ProfileInfo,
    ProfileLookup,
    TerritoryBoundary,
)
from agrowave.modules.scenarios.public import ScenariosService
from agrowave.modules.terrain.domain.ports import DemUsageQuery
from agrowave.modules.terrain.public import TerrainService

_COLOMBIA_CONTINENTAL_COORDS = [
    (-71.66, 12.46),
    (-71.10, 11.85),
    (-71.75, 10.90),
    (-72.35, 9.40),
    (-72.45, 8.00),
    (-70.40, 7.05),
    (-67.40, 6.20),
    (-67.80, 3.85),
    (-66.85, 1.23),
    (-69.45, 0.05),
    (-69.80, -1.20),
    (-69.95, -4.23),
    (-70.50, -4.25),
    (-74.00, -2.00),
    (-75.20, -0.50),
    (-77.50, 0.80),
    (-78.80, 1.50),
    (-79.03, 1.65),
    (-77.50, 4.00),
    (-77.60, 7.00),
    (-77.90, 7.20),
    (-77.30, 8.60),
    (-75.80, 9.50),
    (-75.50, 10.50),
    (-74.80, 11.00),
    (-74.20, 11.25),
    (-72.50, 11.75),
    (-71.66, 12.46),
]


class ColombiaScenarioTerritoryBoundary(TerritoryBoundary):
    """Adapter checking whether a scenario study area is inside continental Colombia (RN-12)."""

    def __init__(self, buffer_degrees: float = 0.05) -> None:
        """Initializes continental Colombia polygon with boundary buffer."""
        raw_poly = Polygon(_COLOMBIA_CONTINENTAL_COORDS)
        self._poly = raw_poly.buffer(buffer_degrees)
        self._min_lon = -79.15
        self._max_lon = -66.80
        self._min_lat = -4.30
        self._max_lat = 12.55

    def is_within_colombia_continental(self, bounds: Bounds) -> bool:
        """Returns True if bounds lie within continental Colombia."""
        if (
            bounds.west < self._min_lon
            or bounds.east > self._max_lon
            or bounds.south < self._min_lat
            or bounds.north > self._max_lat
        ):
            return False

        b_box = box(bounds.west, bounds.south, bounds.east, bounds.north)
        return bool(self._poly.intersects(b_box) and self._poly.contains(b_box.centroid))


class ProfilesModuleLookup(ProfileLookup):
    """Adapter querying the profiles bounded context via its public facade."""

    def __init__(self, profiles_service: ProfilesService) -> None:
        """Initializes lookup with ProfilesService."""
        self._service = profiles_service

    def get_profile(self, profile_id: UUID, user_id: UUID) -> ProfileInfo | None:
        """Retrieves an accessible LPWAN profile."""
        p = self._service.get_profile(profile_id)
        if p is None:
            return None
        if not p.is_predefined and p.owner_id != user_id:
            return None
        return ProfileInfo(
            id=p.id,
            technology=Technology(p.technology.value),
            bands=tuple(
                ProfileBandInfo(code=b.code, min_mhz=b.min_mhz, max_mhz=b.max_mhz) for b in p.bands
            ),
            reference_sensitivity_dbm=p.reference_sensitivity_dbm,
            owner_id=p.owner_id,
        )

    def get_templates(self, technology: Technology) -> list[NodeTemplateInfo]:
        """Retrieves predefined node templates for a technology."""
        templates = self._service.get_templates_by_technology(ProfileTechnology(technology.value))
        return [
            NodeTemplateInfo(
                id=t.id,
                name=t.name,
                technology=Technology(t.technology.value),
                role=t.role.value,
                antenna_ref=t.antenna.reference or "Reference Antenna",
                antenna_gain_dbi=t.antenna.gain_dbi,
                polarization=(
                    Polarization(t.antenna.polarization.value)
                    if t.antenna.polarization
                    else Polarization.VERTICAL
                ),
                tx_power_nominal_dbm=t.tx_power.nominal_dbm if t.tx_power else None,
                tx_power_tolerance_db=t.tx_power.tolerance_db if t.tx_power else None,
            )
            for t in templates
        ]


class TerrainModuleLookup(DemLookup):
    """Adapter querying the terrain bounded context via its public facade."""

    def __init__(self, terrain_service: TerrainService) -> None:
        """Initializes lookup with TerrainService."""
        self._service = terrain_service

    def get_dem(self, dem_id: UUID, user_id: UUID) -> DemInfo | None:
        """Retrieves a DEM owned by the user."""
        dem = self._service.get_dem(dem_id)
        if dem is None or dem.owner_id != user_id:
            return None
        return DemInfo(
            id=dem.id,
            owner_id=dem.owner_id,
            bounds=Bounds(
                south=dem.bounds.south,
                west=dem.bounds.west,
                north=dem.bounds.north,
                east=dem.bounds.east,
            ),
            status=dem.status.value,
        )


class ScenariosProfileUsageQuery(ProfileUsageQuery):
    """Adapter implementing ProfileUsageQuery via ScenariosService (RN-09)."""

    def __init__(self, scenarios_service: ScenariosService) -> None:
        """Initializes adapter with ScenariosService."""
        self._service = scenarios_service

    def is_profile_in_use(self, profile_id: UUID) -> bool:
        """Returns True if any persisted scenario uses profile_id."""
        return self._service.is_profile_in_use(profile_id)


class ScenariosDemUsageQuery(DemUsageQuery):
    """Adapter implementing DemUsageQuery via ScenariosService (RN-28)."""

    def __init__(self, scenarios_service: ScenariosService) -> None:
        """Initializes adapter with ScenariosService."""
        self._service = scenarios_service

    def is_dem_in_use(self, dem_id: UUID) -> bool:
        """Returns True if any persisted scenario uses dem_id."""
        return self._service.is_dem_in_use(dem_id)
