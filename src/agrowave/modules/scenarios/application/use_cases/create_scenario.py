"""Use case for creating a scenario (UC-SC-01)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from agrowave.modules.scenarios.domain.errors import (
    AreaOutsideColombiaError,
    DemDoesNotCoverAreaError,
    FrequencyOutOfProfileError,
    ProfileNotFoundError,
)
from agrowave.modules.scenarios.domain.models import (
    AccessNode,
    Antenna,
    Bounds,
    Deployment,
    EndNode,
    HeightAgl,
    LatLng,
    Link,
    Polarization,
    PropagationSetup,
    RadioConfig,
    Scenario,
    SensitivityOrigin,
    TxPower,
)
from agrowave.modules.scenarios.domain.ports import (
    DemLookup,
    ProfileLookup,
    ScenarioRepository,
    TerritoryBoundary,
)


@dataclass(frozen=True)
class CreateScenarioAccessNodeInput:
    """Input payload for an access node inside a scenario."""

    name: str
    lat: float
    lng: float
    height_agl_m: float
    antenna_ref: str | None
    antenna_gain_dbi: float
    polarization: Polarization
    sensitivity_dbm: float
    sensitivity_origin: SensitivityOrigin = SensitivityOrigin.REFERENCE_TO_VERIFY
    id: UUID | None = None


@dataclass(frozen=True)
class CreateScenarioEndNodeInput:
    """Input payload for an end node inside a scenario."""

    name: str
    lat: float
    lng: float
    height_agl_m: float
    antenna_ref: str | None
    antenna_gain_dbi: float
    polarization: Polarization
    tx_power_nominal_dbm: float
    tx_power_tolerance_db: float | None = None
    source_template_id: UUID | None = None
    id: UUID | None = None


@dataclass(frozen=True)
class CreateScenarioLinkInput:
    """Input payload for an uplink link between an end node and an access node."""

    end_node_id: UUID
    access_node_id: UUID
    id: UUID | None = None


@dataclass(frozen=True)
class CreateScenarioCommand:
    """Command to create a new scenario (draft or complete)."""

    owner_id: UUID
    name: str
    description: str | None
    bounds: Bounds
    dem_id: UUID | None = None
    profile_id: UUID | None = None
    band_code: str | None = None
    frequency_mhz: float | None = None
    access_nodes: list[CreateScenarioAccessNodeInput] = field(default_factory=list)
    end_nodes: list[CreateScenarioEndNodeInput] = field(default_factory=list)
    links: list[CreateScenarioLinkInput] = field(default_factory=list)
    propagation_setup: PropagationSetup | None = None


class CreateScenario:
    """Creates and persists a new Scenario aggregate (UC-SC-01)."""

    def __init__(
        self,
        scenario_repository: ScenarioRepository,
        territory_boundary: TerritoryBoundary,
        profile_lookup: ProfileLookup,
        dem_lookup: DemLookup,
    ) -> None:
        """Initializes the CreateScenario use case.

        Args:
            scenario_repository: Repository port for persisting scenarios.
            territory_boundary: Port for checking continental Colombia boundaries.
            profile_lookup: Port for looking up LPWAN profiles.
            dem_lookup: Port for looking up DEM bounds and status.
        """
        self._repo = scenario_repository
        self._territory = territory_boundary
        self._profiles = profile_lookup
        self._dems = dem_lookup

    def execute(self, command: CreateScenarioCommand) -> Scenario:
        """Validates invariants and persists a new Scenario.

        Args:
            command: Scenario creation payload.

        Returns:
            Persisted Scenario aggregate.

        Raises:
            AreaOutsideColombiaError: If the study area is outside continental Colombia (RN-12).
            DemDoesNotCoverAreaError: If the selected DEM does not cover the study area (RN-26).
            FrequencyOutOfProfileError: If band or frequency is invalid for the profile (RN-22).
        """
        if not self._territory.is_within_colombia_continental(command.bounds):
            raise AreaOutsideColombiaError()

        now = datetime.now(UTC)
        scenario = Scenario(
            id=uuid4(),
            owner_id=command.owner_id,
            name=command.name,
            description=command.description,
            comparison_group_id=uuid4(),
            propagation_setup=command.propagation_setup,
            created_at=now,
            updated_at=now,
        )
        scenario.define_area(command.bounds)

        if command.dem_id is not None:
            dem_info = self._dems.get_dem(command.dem_id, command.owner_id)
            if dem_info is None:
                raise DemDoesNotCoverAreaError("Selected DEM does not exist or is not accessible.")
            scenario.assign_terrain(dem_id=dem_info.id, dem_bounds=dem_info.bounds)

        if command.profile_id is not None:
            profile_info = self._profiles.get_profile(command.profile_id, command.owner_id)
            if profile_info is None:
                raise ProfileNotFoundError(
                    "Selected LPWAN profile was not found or is not accessible."
                )
            band_code = command.band_code or (
                profile_info.bands[0].code if profile_info.bands else ""
            )
            matched_band = next(
                (b for b in profile_info.bands if b.code == band_code),
                None,
            )
            if matched_band is None and profile_info.bands:
                raise FrequencyOutOfProfileError(
                    f"Band '{band_code}' does not belong to the selected LPWAN profile."
                )
            band_min = matched_band.min_mhz if matched_band else None
            band_max = matched_band.max_mhz if matched_band else None
            freq = command.frequency_mhz
            if freq is None:
                if band_min is not None and band_max is not None:
                    freq = round((band_min + band_max) / 2.0, 3)
                else:
                    raise FrequencyOutOfProfileError(
                        "Operating frequency in MHz is required for the selected band."
                    )
            scenario.radio_config = RadioConfig(
                profile_id=profile_info.id,
                technology=profile_info.technology,
                band_code=band_code,
                frequency_mhz=freq,
                band_min_mhz=band_min,
                band_max_mhz=band_max,
            )

        access_nodes = [
            AccessNode(
                id=an.id or uuid4(),
                name=an.name,
                position=LatLng(lat=an.lat, lng=an.lng),
                height_agl=HeightAgl(meters=an.height_agl_m),
                antenna=Antenna(
                    reference=an.antenna_ref,
                    gain_dbi=an.antenna_gain_dbi,
                    polarization=an.polarization,
                ),
                sensitivity_dbm=an.sensitivity_dbm,
                sensitivity_origin=an.sensitivity_origin,
            )
            for an in command.access_nodes
        ]

        end_nodes = [
            EndNode(
                id=en.id or uuid4(),
                name=en.name,
                position=LatLng(lat=en.lat, lng=en.lng),
                height_agl=HeightAgl(meters=en.height_agl_m),
                antenna=Antenna(
                    reference=en.antenna_ref,
                    gain_dbi=en.antenna_gain_dbi,
                    polarization=en.polarization,
                ),
                tx_power=TxPower(
                    nominal_dbm=en.tx_power_nominal_dbm,
                    tolerance_db=en.tx_power_tolerance_db
                    if en.tx_power_tolerance_db is not None
                    else 0.0,
                ),
                source_template_id=en.source_template_id,
            )
            for en in command.end_nodes
        ]

        links = [
            Link(
                id=lk.id or uuid4(),
                end_node_id=lk.end_node_id,
                access_node_id=lk.access_node_id,
            )
            for lk in command.links
        ]

        scenario.set_deployment(
            Deployment(
                access_nodes=access_nodes,
                end_nodes=end_nodes,
                links=links,
            )
        )
        return self._repo.save(scenario)
