"""Unit tests for scenarios application use cases (UC-SC-01 to UC-SC-06)."""

from uuid import UUID, uuid4

import pytest

from agrowave.modules.scenarios.application.use_cases.create_scenario import (
    CreateScenario,
    CreateScenarioAccessNodeInput,
    CreateScenarioCommand,
    CreateScenarioEndNodeInput,
    CreateScenarioLinkInput,
)
from agrowave.modules.scenarios.application.use_cases.create_scenario_variant import (
    CreateScenarioVariant,
    CreateScenarioVariantCommand,
)
from agrowave.modules.scenarios.application.use_cases.duplicate_scenario import (
    DuplicateScenario,
    DuplicateScenarioCommand,
)
from agrowave.modules.scenarios.application.use_cases.validate_scenario import (
    ValidateScenario,
    ValidateScenarioQuery,
)
from agrowave.modules.scenarios.domain.errors import (
    AreaOutsideColombiaError,
    DemDoesNotCoverAreaError,
)
from agrowave.modules.scenarios.domain.models import (
    Bounds,
    LongleyRiceParams,
    Polarization,
    PropagationSetup,
    Scenario,
    SensitivityOrigin,
    Technology,
)
from agrowave.modules.scenarios.domain.ports import (
    DemInfo,
    DemLookup,
    NodeTemplateInfo,
    ProfileBandInfo,
    ProfileInfo,
    ProfileLookup,
    ScenarioRepository,
    TerritoryBoundary,
)


class FakeTerritoryBoundary(TerritoryBoundary):
    """Fake territory boundary for unit tests."""

    def __init__(self, inside: bool = True) -> None:
        """Initializes fake boundary check."""
        self._inside = inside

    def is_within_colombia_continental(self, bounds: Bounds) -> bool:
        """Returns preconfigured boundary check result."""
        return self._inside


class FakeScenarioRepository(ScenarioRepository):
    """In-memory scenario repository for unit testing."""

    def __init__(self) -> None:
        """Initializes in-memory scenario store."""
        self.scenarios: dict[UUID, Scenario] = {}

    def save(self, scenario: Scenario) -> Scenario:
        """Saves a scenario in memory."""
        self.scenarios[scenario.id] = scenario
        return scenario

    def get_by_id(self, scenario_id: UUID) -> Scenario | None:
        """Looks up a scenario by ID."""
        return self.scenarios.get(scenario_id)

    def list_by_owner(self, owner_id: UUID) -> list[Scenario]:
        """Lists scenarios owned by the given user."""
        return [s for s in self.scenarios.values() if s.owner_id == owner_id]

    def delete(self, scenario_id: UUID) -> None:
        """Removes a scenario by ID."""
        self.scenarios.pop(scenario_id, None)

    def is_profile_in_use(self, profile_id: UUID) -> bool:
        """Checks whether any stored scenario uses the profile."""
        return any(
            s.radio_config is not None and s.radio_config.profile_id == profile_id
            for s in self.scenarios.values()
        )

    def is_dem_in_use(self, dem_id: UUID) -> bool:
        """Checks whether any stored scenario uses the DEM."""
        return any(
            s.terrain_ref is not None and s.terrain_ref.dem_id == dem_id
            for s in self.scenarios.values()
        )


class FakeProfileLookup(ProfileLookup):
    """Fake profile lookup for unit tests."""

    def __init__(
        self,
        profiles: dict[UUID, ProfileInfo] | None = None,
        templates: dict[Technology, list[NodeTemplateInfo]] | None = None,
    ) -> None:
        """Initializes fake profiles and templates."""
        self.profiles = profiles or {}
        self.templates = templates or {}

    def get_profile(self, profile_id: UUID, user_id: UUID) -> ProfileInfo | None:
        """Returns matching profile if accessible."""
        return self.profiles.get(profile_id)

    def get_templates(self, technology: Technology) -> list[NodeTemplateInfo]:
        """Returns templates for a technology."""
        return self.templates.get(technology, [])


class FakeDemLookup(DemLookup):
    """Fake DEM lookup for unit tests."""

    def __init__(self, dems: dict[UUID, DemInfo] | None = None) -> None:
        """Initializes fake DEM store."""
        self.dems = dems or {}

    def get_dem(self, dem_id: UUID, user_id: UUID) -> DemInfo | None:
        """Returns matching DEM if owned by user."""
        return self.dems.get(dem_id)


def _sample_propagation() -> PropagationSetup:
    return PropagationSetup(
        parameters=LongleyRiceParams(
            ens0=314.0,
            ipol=1,
            eps=15.0,
            sgm=0.005,
            klim=5,
            mdvar=11,
            qc=50.0,
            qr=(10.0, 50.0, 90.0),
        )
    )


def test_ac03_area_outside_colombia_rejected() -> None:
    """AC-03 (RN-12): Creating a scenario with bounds outside Colombia raises error."""
    repo = FakeScenarioRepository()
    use_case = CreateScenario(
        scenario_repository=repo,
        territory_boundary=FakeTerritoryBoundary(inside=False),
        profile_lookup=FakeProfileLookup(),
        dem_lookup=FakeDemLookup(),
    )
    cmd = CreateScenarioCommand(
        owner_id=uuid4(),
        name="Scenario Outside Colombia",
        description=None,
        bounds=Bounds(south=-34.62, west=-58.42, north=-34.58, east=-58.38),
    )
    with pytest.raises(AreaOutsideColombiaError):
        use_case.execute(cmd)


def test_ac05_assign_covering_dem_succeeds_and_non_covering_rejected() -> None:
    """AC-05 (RN-26, RN-27): Covering DEM succeeds; non-covering DEM raises error."""
    owner_id = uuid4()
    covering_dem_id = uuid4()
    small_dem_id = uuid4()
    dems = {
        covering_dem_id: DemInfo(
            id=covering_dem_id,
            owner_id=owner_id,
            bounds=Bounds(south=4.55, west=-74.15, north=4.70, east=-74.00),
            status="AVAILABLE",
        ),
        small_dem_id: DemInfo(
            id=small_dem_id,
            owner_id=owner_id,
            bounds=Bounds(south=4.60, west=-74.10, north=4.62, east=-74.08),
            status="AVAILABLE",
        ),
    }
    repo = FakeScenarioRepository()
    use_case = CreateScenario(
        scenario_repository=repo,
        territory_boundary=FakeTerritoryBoundary(inside=True),
        profile_lookup=FakeProfileLookup(),
        dem_lookup=FakeDemLookup(dems=dems),
    )

    study_bounds = Bounds(south=4.59, west=-74.11, north=4.63, east=-74.07)

    scenario = use_case.execute(
        CreateScenarioCommand(
            owner_id=owner_id,
            name="Covered Scenario",
            description="Uses existing DEM",
            bounds=study_bounds,
            dem_id=covering_dem_id,
        )
    )
    assert scenario.terrain_ref is not None
    assert scenario.terrain_ref.dem_id == covering_dem_id
    assert scenario.terrain_ref.window == study_bounds

    with pytest.raises(DemDoesNotCoverAreaError):
        use_case.execute(
            CreateScenarioCommand(
                owner_id=owner_id,
                name="Uncovered Scenario",
                description=None,
                bounds=study_bounds,
                dem_id=small_dem_id,
            )
        )


def test_ac13_template_values_copied_independently() -> None:
    """AC-13 (RN-23): End node created from template stores its own independent values."""
    owner_id = uuid4()
    profile_id = uuid4()
    template_id = uuid4()
    profiles = {
        profile_id: ProfileInfo(
            id=profile_id,
            technology=Technology.LORAWAN,
            bands=(ProfileBandInfo(code="US915", min_mhz=902.0, max_mhz=928.0),),
            reference_sensitivity_dbm=-137.0,
        )
    }
    repo = FakeScenarioRepository()
    use_case = CreateScenario(
        scenario_repository=repo,
        territory_boundary=FakeTerritoryBoundary(inside=True),
        profile_lookup=FakeProfileLookup(profiles=profiles),
        dem_lookup=FakeDemLookup(),
    )

    access_id = uuid4()
    end_id = uuid4()
    scenario = use_case.execute(
        CreateScenarioCommand(
            owner_id=owner_id,
            name="Template Copy Test",
            description=None,
            bounds=Bounds(south=4.58, west=-74.12, north=4.66, east=-74.04),
            profile_id=profile_id,
            band_code="US915",
            frequency_mhz=915.0,
            access_nodes=[
                CreateScenarioAccessNodeInput(
                    id=access_id,
                    name="GW-1",
                    lat=4.60,
                    lng=-74.10,
                    height_agl_m=15.0,
                    antenna_ref="Dragino Outdoor",
                    antenna_gain_dbi=5.5,
                    polarization=Polarization.VERTICAL,
                    sensitivity_dbm=-137.0,
                    sensitivity_origin=SensitivityOrigin.REFERENCE_TO_VERIFY,
                )
            ],
            end_nodes=[
                CreateScenarioEndNodeInput(
                    id=end_id,
                    name="Sensor-1",
                    lat=4.62,
                    lng=-74.08,
                    height_agl_m=2.0,
                    antenna_ref="Custom Antenna",
                    antenna_gain_dbi=3.5,
                    polarization=Polarization.VERTICAL,
                    tx_power_nominal_dbm=18.0,
                    tx_power_tolerance_db=1.0,
                    source_template_id=template_id,
                )
            ],
            links=[
                CreateScenarioLinkInput(
                    end_node_id=end_id,
                    access_node_id=access_id,
                )
            ],
        )
    )
    end_node = scenario.deployment.end_nodes[0]
    assert end_node.source_template_id == template_id
    assert end_node.antenna.gain_dbi == 3.5
    assert end_node.tx_power.nominal_dbm == 18.0


def test_ac14_create_variant_shares_comparison_group_and_preserves_geometry() -> None:
    """AC-14 (RN-29): Creating a variant preserves geometry and shares comparison_group_id."""
    owner_id = uuid4()
    lora_profile_id = uuid4()
    nbiot_profile_id = uuid4()
    dem_id = uuid4()
    nbiot_end_tpl_id = uuid4()
    nbiot_access_tpl_id = uuid4()

    profiles = {
        lora_profile_id: ProfileInfo(
            id=lora_profile_id,
            technology=Technology.LORAWAN,
            bands=(ProfileBandInfo(code="US915", min_mhz=902.0, max_mhz=928.0),),
            reference_sensitivity_dbm=-137.0,
        ),
        nbiot_profile_id: ProfileInfo(
            id=nbiot_profile_id,
            technology=Technology.NB_IOT,
            bands=(ProfileBandInfo(code="B28", min_mhz=703.0, max_mhz=748.0),),
            reference_sensitivity_dbm=-141.0,
        ),
    }
    templates = {
        Technology.NB_IOT: [
            NodeTemplateInfo(
                id=nbiot_end_tpl_id,
                name="NB-IoT Sensor",
                technology=Technology.NB_IOT,
                role="END_NODE",
                antenna_ref="Taoglas FXP611",
                antenna_gain_dbi=2.1,
                polarization=Polarization.VERTICAL,
                tx_power_nominal_dbm=23.0,
                tx_power_tolerance_db=2.0,
            ),
            NodeTemplateInfo(
                id=nbiot_access_tpl_id,
                name="eNodeB NB-IoT",
                technology=Technology.NB_IOT,
                role="ACCESS_NODE",
                antenna_ref="3GPP Sector",
                antenna_gain_dbi=None,
                polarization=Polarization.VERTICAL,
                tx_power_nominal_dbm=None,
                tx_power_tolerance_db=None,
            ),
        ]
    }
    dems = {
        dem_id: DemInfo(
            id=dem_id,
            owner_id=owner_id,
            bounds=Bounds(south=4.55, west=-74.15, north=4.70, east=-74.00),
            status="AVAILABLE",
        )
    }

    repo = FakeScenarioRepository()
    profile_lookup = FakeProfileLookup(profiles=profiles, templates=templates)
    dem_lookup = FakeDemLookup(dems=dems)

    create_uc = CreateScenario(
        scenario_repository=repo,
        territory_boundary=FakeTerritoryBoundary(inside=True),
        profile_lookup=profile_lookup,
        dem_lookup=dem_lookup,
    )

    access_id = uuid4()
    end_id = uuid4()
    source = create_uc.execute(
        CreateScenarioCommand(
            owner_id=owner_id,
            name="Finca LoRaWAN",
            description="Base scenario",
            bounds=Bounds(south=4.58, west=-74.12, north=4.66, east=-74.04),
            dem_id=dem_id,
            profile_id=lora_profile_id,
            band_code="US915",
            frequency_mhz=915.0,
            access_nodes=[
                CreateScenarioAccessNodeInput(
                    id=access_id,
                    name="GW-1",
                    lat=4.60,
                    lng=-74.10,
                    height_agl_m=15.0,
                    antenna_ref="Dragino Outdoor",
                    antenna_gain_dbi=5.5,
                    polarization=Polarization.VERTICAL,
                    sensitivity_dbm=-137.0,
                    sensitivity_origin=SensitivityOrigin.REFERENCE_TO_VERIFY,
                )
            ],
            end_nodes=[
                CreateScenarioEndNodeInput(
                    id=end_id,
                    name="Sensor-1",
                    lat=4.62,
                    lng=-74.08,
                    height_agl_m=2.0,
                    antenna_ref="Taoglas",
                    antenna_gain_dbi=1.1,
                    polarization=Polarization.VERTICAL,
                    tx_power_nominal_dbm=20.0,
                    tx_power_tolerance_db=1.5,
                )
            ],
            links=[CreateScenarioLinkInput(end_node_id=end_id, access_node_id=access_id)],
            propagation_setup=_sample_propagation(),
        )
    )

    variant_uc = CreateScenarioVariant(
        scenario_repository=repo,
        profile_lookup=profile_lookup,
    )
    variant = variant_uc.execute(
        CreateScenarioVariantCommand(
            scenario_id=source.id,
            owner_id=owner_id,
            target_profile_id=nbiot_profile_id,
            band_code="B28",
            frequency_mhz=725.0,
            name="Finca NB-IoT",
        )
    )

    assert variant.id != source.id
    assert variant.comparison_group_id == source.comparison_group_id
    assert variant.study_area == source.study_area
    assert variant.terrain_ref == source.terrain_ref
    assert variant.propagation_setup == source.propagation_setup
    assert variant.radio_config is not None
    assert variant.radio_config.profile_id == nbiot_profile_id
    assert variant.radio_config.technology == Technology.NB_IOT
    assert variant.radio_config.frequency_mhz == 725.0
    assert len(variant.deployment.access_nodes) == 1
    assert len(variant.deployment.end_nodes) == 1
    assert len(variant.deployment.links) == 1
    assert variant.deployment.access_nodes[0].position == source.deployment.access_nodes[0].position
    assert (
        variant.deployment.access_nodes[0].height_agl
        == source.deployment.access_nodes[0].height_agl
    )
    assert variant.deployment.access_nodes[0].sensitivity_dbm == -141.0
    assert (
        variant.deployment.access_nodes[0].sensitivity_origin
        == SensitivityOrigin.REFERENCE_TO_VERIFY
    )
    # Q3b: Preserve source access node gain when template gain is None
    assert variant.deployment.access_nodes[0].antenna.gain_dbi == 5.5
    assert variant.deployment.end_nodes[0].position == source.deployment.end_nodes[0].position
    assert variant.deployment.end_nodes[0].tx_power.nominal_dbm == 23.0
    assert variant.deployment.end_nodes[0].antenna.gain_dbi == 2.1


def test_ac16_validate_scenario_reports_dem_not_available() -> None:
    """AC-16 (RN-31): Validating a scenario with non-available DEM reports DemNotAvailable."""
    owner_id = uuid4()
    dem_id = uuid4()
    profile_id = uuid4()

    dems = {
        dem_id: DemInfo(
            id=dem_id,
            owner_id=owner_id,
            bounds=Bounds(south=4.55, west=-74.15, north=4.70, east=-74.00),
            status="PENDING",
        )
    }
    profiles = {
        profile_id: ProfileInfo(
            id=profile_id,
            technology=Technology.LORAWAN,
            bands=(ProfileBandInfo(code="US915", min_mhz=902.0, max_mhz=928.0),),
            reference_sensitivity_dbm=-137.0,
        )
    }
    repo = FakeScenarioRepository()
    profile_lookup = FakeProfileLookup(profiles=profiles)
    dem_lookup = FakeDemLookup(dems=dems)

    create_uc = CreateScenario(
        scenario_repository=repo,
        territory_boundary=FakeTerritoryBoundary(inside=True),
        profile_lookup=profile_lookup,
        dem_lookup=dem_lookup,
    )
    access_id = uuid4()
    end_id = uuid4()
    scenario = create_uc.execute(
        CreateScenarioCommand(
            owner_id=owner_id,
            name="Pending DEM Scenario",
            description=None,
            bounds=Bounds(south=4.58, west=-74.12, north=4.66, east=-74.04),
            dem_id=dem_id,
            profile_id=profile_id,
            band_code="US915",
            frequency_mhz=915.0,
            access_nodes=[
                CreateScenarioAccessNodeInput(
                    id=access_id,
                    name="GW-1",
                    lat=4.60,
                    lng=-74.10,
                    height_agl_m=15.0,
                    antenna_ref="Dragino Outdoor",
                    antenna_gain_dbi=5.5,
                    polarization=Polarization.VERTICAL,
                    sensitivity_dbm=-137.0,
                    sensitivity_origin=SensitivityOrigin.REFERENCE_TO_VERIFY,
                )
            ],
            end_nodes=[
                CreateScenarioEndNodeInput(
                    id=end_id,
                    name="Sensor-1",
                    lat=4.62,
                    lng=-74.08,
                    height_agl_m=2.0,
                    antenna_ref="Taoglas",
                    antenna_gain_dbi=1.1,
                    polarization=Polarization.VERTICAL,
                    tx_power_nominal_dbm=20.0,
                    tx_power_tolerance_db=1.5,
                )
            ],
            links=[CreateScenarioLinkInput(end_node_id=end_id, access_node_id=access_id)],
            propagation_setup=_sample_propagation(),
        )
    )

    validate_uc = ValidateScenario(
        scenario_repository=repo,
        dem_lookup=dem_lookup,
    )
    result = validate_uc.execute(ValidateScenarioQuery(scenario_id=scenario.id, owner_id=owner_id))
    assert result.simulable is False
    assert any(c.code == "DemNotAvailable" for c in result.causes)


def test_duplicate_scenario_creates_new_comparison_group() -> None:
    """UC-SC-03: Duplicating a scenario assigns a new comparison_group_id and fresh IDs."""
    owner_id = uuid4()
    repo = FakeScenarioRepository()
    create_uc = CreateScenario(
        scenario_repository=repo,
        territory_boundary=FakeTerritoryBoundary(inside=True),
        profile_lookup=FakeProfileLookup(),
        dem_lookup=FakeDemLookup(),
    )
    source = create_uc.execute(
        CreateScenarioCommand(
            owner_id=owner_id,
            name="Original Scenario",
            description="Desc",
            bounds=Bounds(south=4.58, west=-74.12, north=4.66, east=-74.04),
        )
    )
    dup_uc = DuplicateScenario(scenario_repository=repo)
    duplicated = dup_uc.execute(
        DuplicateScenarioCommand(
            scenario_id=source.id,
            owner_id=owner_id,
            name="Original Scenario (Copia)",
        )
    )
    assert duplicated.id != source.id
    assert duplicated.comparison_group_id != source.comparison_group_id
    assert duplicated.name == "Original Scenario (Copia)"
