"""Unit tests for the scenarios domain model and rules (AC-01..AC-12)."""

from uuid import uuid4

import pytest

from agrowave.modules.scenarios.domain.errors import (
    AreaTooSmallError,
    AreaWouldExcludeNodesError,
    DemDoesNotCoverAreaError,
    EndNodeAlreadyLinkedError,
    FrequencyOutOfProfileError,
    HeightBelowMinimumError,
    LinkTooShortError,
    NodeOutsideAreaError,
)
from agrowave.modules.scenarios.domain.models import (
    AccessNode,
    Antenna,
    Bounds,
    EndNode,
    HeightAgl,
    LatLng,
    LongleyRiceParams,
    Polarization,
    PropagationSetup,
    RadioConfig,
    Scenario,
    SensitivityOrigin,
    StudyArea,
    Technology,
    TxPower,
)


def _valid_study_bounds() -> Bounds:
    """Returns a ~2.2 km x ~2.2 km bounding box in Boyaca."""
    return Bounds(south=5.50, west=-73.40, north=5.52, east=-73.38)


def _make_access_node(
    lat: float = 5.505, lng: float = -73.395, height_m: float = 10.0
) -> AccessNode:
    """Creates a sample valid AccessNode inside _valid_study_bounds."""
    return AccessNode(
        id=uuid4(),
        name="GW-1",
        position=LatLng(lat=lat, lng=lng),
        height_agl=HeightAgl(meters=height_m),
        antenna=Antenna(
            reference="Dragino DLOS8N", gain_dbi=3.0, polarization=Polarization.VERTICAL
        ),
        sensitivity_dbm=-137.0,
        sensitivity_origin=SensitivityOrigin.REFERENCE_TO_VERIFY,
    )


def _make_end_node(
    name: str = "EN-1",
    lat: float = 5.517,
    lng: float = -73.385,
    height_m: float = 1.5,
) -> EndNode:
    """Creates a sample valid EndNode > 1.2 km away from GW-1 inside _valid_study_bounds."""
    return EndNode(
        id=uuid4(),
        name=name,
        position=LatLng(lat=lat, lng=lng),
        height_agl=HeightAgl(meters=height_m),
        antenna=Antenna(
            reference="LoRa U.FL IP-EX", gain_dbi=2.0, polarization=Polarization.VERTICAL
        ),
        tx_power=TxPower(nominal_dbm=21.0, tolerance_db=1.0),
    )


def test_ac01_define_valid_study_area() -> None:
    """AC-01: Given a 2 x 2 km rectangle, defining study area stores the area on the scenario."""
    scenario = Scenario(owner_id=uuid4(), name="Finca El Rosal")
    bounds = _valid_study_bounds()

    scenario.define_area(bounds)

    assert scenario.study_area is not None
    assert scenario.study_area.bounds == bounds


def test_ac02_area_too_small_rejected() -> None:
    """AC-02: (RN-13) Given a 1.4 x 3 km rectangle, defining study area raises AreaTooSmallError."""
    scenario = Scenario(owner_id=uuid4(), name="Small Area Scenario")
    # 0.012 deg lat is ~1.33 km (< 1.5 km), 0.03 deg lng is ~3.3 km
    small_bounds = Bounds(south=5.500, west=-73.400, north=5.512, east=-73.370)

    with pytest.raises(AreaTooSmallError):
        StudyArea(bounds=small_bounds)

    with pytest.raises(AreaTooSmallError):
        scenario.define_area(small_bounds)


def test_ac04_shrinking_area_excluding_nodes_rejected() -> None:
    """AC-04 (RN-14): Shrinking area so existing nodes fall outside raises error."""
    scenario = Scenario(owner_id=uuid4(), name="Finca Con Nodos")
    large_bounds = Bounds(south=5.50, west=-73.45, north=5.55, east=-73.35)
    scenario.define_area(large_bounds)

    gw = _make_access_node(lat=5.505, lng=-73.440)
    en = _make_end_node(lat=5.545, lng=-73.360)
    scenario.add_link(end_node=en, access_node=gw)

    # New bounds exclude the end node at (5.545, -73.360)
    smaller_bounds = Bounds(south=5.50, west=-73.45, north=5.52, east=-73.40)

    with pytest.raises(AreaWouldExcludeNodesError) as exc_info:
        scenario.define_area(smaller_bounds)

    assert en.name in exc_info.value.excluded_node_names


def test_ac06_dem_not_covering_area_rejected() -> None:
    """AC-06 (RN-26): Assigning a DEM not covering the study area raises error."""
    scenario = Scenario(owner_id=uuid4(), name="Scenario Terreno")
    scenario.define_area(_valid_study_bounds())

    partial_dem_bounds = Bounds(south=5.505, west=-73.40, north=5.52, east=-73.38)
    with pytest.raises(DemDoesNotCoverAreaError):
        scenario.assign_terrain(dem_id=uuid4(), dem_bounds=partial_dem_bounds)

    covering_dem_bounds = Bounds(south=5.45, west=-73.45, north=5.55, east=-73.35)
    scenario.assign_terrain(dem_id=uuid4(), dem_bounds=covering_dem_bounds)
    assert scenario.terrain_ref is not None
    assert scenario.terrain_ref.window == _valid_study_bounds()


def test_ac08_add_valid_link_succeeds() -> None:
    """AC-08 (RN-19..21): Adding a valid link inside area succeeds."""
    scenario = Scenario(owner_id=uuid4(), name="Valid Link Scenario")
    scenario.define_area(_valid_study_bounds())

    gw = _make_access_node()
    en = _make_end_node()
    link = scenario.add_link(end_node=en, access_node=gw)

    assert len(scenario.deployment.links) == 1
    assert link.end_node_id == en.id
    assert link.access_node_id == gw.id


def test_ac09_link_shorter_than_1km_is_rejected() -> None:
    """AC-09 (RN-19): Adding or moving a link shorter than 1.0 km raises LinkTooShortError."""
    scenario = Scenario(owner_id=uuid4(), name="Short Link Scenario")
    scenario.define_area(_valid_study_bounds())

    gw = _make_access_node(lat=5.505, lng=-73.395)
    # 0.005 deg lat is ~0.55 km (< 1.0 km)
    close_en = _make_end_node(lat=5.510, lng=-73.395)

    with pytest.raises(LinkTooShortError):
        scenario.add_link(end_node=close_en, access_node=gw)

    # Now add a valid link and try to move node too close
    valid_en = _make_end_node(lat=5.517, lng=-73.385)
    scenario.add_link(end_node=valid_en, access_node=gw)

    with pytest.raises(LinkTooShortError):
        scenario.move_node(node_id=valid_en.id, position=LatLng(lat=5.508, lng=-73.395))


def test_ac10_height_below_05m_rejected() -> None:
    """AC-10: (RN-20) Creating a HeightAgl with meters < 0.5 raises HeightBelowMinimumError."""
    with pytest.raises(HeightBelowMinimumError):
        HeightAgl(meters=0.3)

    h = HeightAgl(meters=0.5)
    assert h.meters == 0.5


def test_ac11_end_node_already_linked_rejected() -> None:
    """AC-11 (RN-17): Linking an already linked end node raises EndNodeAlreadyLinkedError."""
    scenario = Scenario(owner_id=uuid4(), name="Duplicate EndNode Link")
    scenario.define_area(_valid_study_bounds())

    gw1 = _make_access_node(lat=5.502, lng=-73.398)
    gw2 = _make_access_node(lat=5.503, lng=-73.397)
    en = _make_end_node(lat=5.518, lng=-73.382)

    scenario.add_link(end_node=en, access_node=gw1)

    with pytest.raises(EndNodeAlreadyLinkedError):
        scenario.add_link(end_node=en, access_node=gw2)


def test_ac12_star_topology_one_gw_three_end_nodes() -> None:
    """AC-12: Linking 3 end nodes to 1 GW results in 1 access node, 3 end nodes, and 3 links."""
    scenario = Scenario(owner_id=uuid4(), name="Star Topology")
    scenario.define_area(_valid_study_bounds())

    gw = _make_access_node(lat=5.502, lng=-73.398)
    en1 = _make_end_node(name="EN-1", lat=5.515, lng=-73.385)
    en2 = _make_end_node(name="EN-2", lat=5.516, lng=-73.384)
    en3 = _make_end_node(name="EN-3", lat=5.518, lng=-73.382)

    scenario.add_link(end_node=en1, access_node=gw)
    scenario.add_link(end_node=en2, access_node=gw)
    scenario.add_link(end_node=en3, access_node=gw)

    assert len(scenario.deployment.access_nodes) == 1
    assert len(scenario.deployment.end_nodes) == 3
    assert len(scenario.deployment.links) == 3


def test_node_outside_area_rejected() -> None:
    """RN-21: Placing or moving a node outside the study area raises NodeOutsideAreaError."""
    scenario = Scenario(owner_id=uuid4(), name="Outside Node")
    scenario.define_area(_valid_study_bounds())

    gw = _make_access_node(lat=5.505, lng=-73.395)
    outside_en = _make_end_node(lat=5.60, lng=-73.30)

    with pytest.raises(NodeOutsideAreaError):
        scenario.add_link(end_node=outside_en, access_node=gw)


def test_frequency_out_of_profile_rejected() -> None:
    """RN-22: Frequency outside the band's [min_mhz, max_mhz] raises FrequencyOutOfProfileError."""
    with pytest.raises(FrequencyOutOfProfileError):
        RadioConfig(
            profile_id=uuid4(),
            technology=Technology.LORAWAN,
            band_code="902-928",
            frequency_mhz=868.0,
            band_min_mhz=902.0,
            band_max_mhz=928.0,
        )

    valid_rc = RadioConfig(
        profile_id=uuid4(),
        technology=Technology.LORAWAN,
        band_code="902-928",
        frequency_mhz=915.0,
        band_min_mhz=902.0,
        band_max_mhz=928.0,
    )
    assert valid_rc.frequency_mhz == 915.0


def test_validate_for_simulation_causes() -> None:
    """RN-31 / AC-16: validate_for_simulation returns causes when DEM or config is missing."""
    scenario = Scenario(owner_id=uuid4(), name="Incomplete Scenario")
    causes = scenario.validate_for_simulation(dem_available=False)
    codes = {c.code for c in causes}
    assert "MissingStudyArea" in codes
    assert "DemNotAvailable" in codes
    assert "MissingRadioConfig" in codes
    assert "NoLinksDefined" in codes
    assert "MissingPropagationSetup" in codes

    # Complete the scenario
    scenario.define_area(_valid_study_bounds())
    scenario.assign_terrain(dem_id=uuid4(), dem_bounds=_valid_study_bounds())
    scenario.radio_config = RadioConfig(
        profile_id=uuid4(),
        technology=Technology.LORAWAN,
        band_code="902-928",
        frequency_mhz=915.0,
        band_min_mhz=902.0,
        band_max_mhz=928.0,
    )
    gw = _make_access_node()
    en = _make_end_node()
    scenario.add_link(end_node=en, access_node=gw)
    scenario.propagation_setup = PropagationSetup(
        model_id="LONGLEY_RICE",
        parameters=LongleyRiceParams(ens0=314.0),
    )

    assert scenario.validate_for_simulation(dem_available=False)[0].code == "DemNotAvailable"
    assert scenario.validate_for_simulation(dem_available=True) == []
