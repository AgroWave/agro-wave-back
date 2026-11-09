"""Domain entities and value objects for the scenarios bounded context."""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from agrowave.modules.scenarios.domain.errors import (
    AreaTooSmallError,
    AreaWouldExcludeNodesError,
    DemDoesNotCoverAreaError,
    EndNodeAlreadyLinkedError,
    FrequencyOutOfProfileError,
    HeightBelowMinimumError,
    InvalidBoundsError,
    LinkTooShortError,
    NodeOutsideAreaError,
    OrphanNodeError,
)

EARTH_RADIUS_KM = 6371.0
MIN_AREA_SIDE_KM = 1.5
MIN_LINK_DISTANCE_KM = 1.0
MIN_HEIGHT_AGL_M = 0.5


class Technology(StrEnum):
    """Supported LPWAN radio technologies."""

    LORAWAN = "LORAWAN"
    NB_IOT = "NB_IOT"
    LTE_M = "LTE_M"


class Polarization(StrEnum):
    """Antenna polarization orientation."""

    VERTICAL = "VERTICAL"
    HORIZONTAL = "HORIZONTAL"


class SensitivityOrigin(StrEnum):
    """Origin of the access node receiver sensitivity value (RN-42)."""

    REFERENCE_TO_VERIFY = "REFERENCE_TO_VERIFY"
    USER_DEFINED = "USER_DEFINED"


@dataclass(frozen=True)
class LatLng:
    """Geographic coordinate in decimal degrees WGS84.

    Attributes:
        lat: Latitude in decimal degrees (-90 to 90).
        lng: Longitude in decimal degrees (-180 to 180).
    """

    lat: float
    lng: float


def geodesic_distance_km(p1: LatLng, p2: LatLng) -> float:
    """Calculates great-circle horizontal distance between two WGS84 points using Haversine.

    Args:
        p1: First geographic coordinate in degrees.
        p2: Second geographic coordinate in degrees.

    Returns:
        Horizontal distance in kilometers (km).
    """
    lat1_rad = math.radians(p1.lat)
    lat2_rad = math.radians(p2.lat)
    dlat_rad = math.radians(p2.lat - p1.lat)
    dlng_rad = math.radians(p2.lng - p1.lng)

    a = (
        math.sin(dlat_rad / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng_rad / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


@dataclass(frozen=True)
class Bounds:
    """Geographic bounding box aligned with coordinate axes in WGS84.

    Attributes:
        south: Southern latitude boundary in decimal degrees.
        west: Western longitude boundary in decimal degrees.
        north: Northern latitude boundary in decimal degrees.
        east: Eastern longitude boundary in decimal degrees.

    Raises:
        InvalidBoundsError: If south >= north or west >= east.
    """

    south: float
    west: float
    north: float
    east: float

    def __post_init__(self) -> None:
        """Validates coordinate ordering."""
        if self.south >= self.north:
            raise InvalidBoundsError(
                f"South latitude ({self.south}) must be strictly less than north ({self.north})."
            )
        if self.west >= self.east:
            raise InvalidBoundsError(
                f"West longitude ({self.west}) must be strictly less than east ({self.east})."
            )

    def contains(self, point: LatLng) -> bool:
        """Checks whether a point lies inside or on the boundary of this box."""
        return self.south <= point.lat <= self.north and self.west <= point.lng <= self.east

    def contains_bounds(self, other: "Bounds") -> bool:
        """Checks whether another bounding box is completely covered by this box."""
        return (
            self.south <= other.south
            and self.north >= other.north
            and self.west <= other.west
            and self.east >= other.east
        )


def bounds_dimensions_km(bounds: Bounds) -> tuple[float, float]:
    """Calculates horizontal width and vertical height of a bounding box in kilometers.

    Args:
        bounds: Bounding box in decimal degrees.

    Returns:
        Tuple (width_km, height_km) in kilometers.
    """
    mid_lat = (bounds.south + bounds.north) / 2.0
    mid_lng = (bounds.west + bounds.east) / 2.0
    width_km = geodesic_distance_km(
        LatLng(lat=mid_lat, lng=bounds.west),
        LatLng(lat=mid_lat, lng=bounds.east),
    )
    height_km = geodesic_distance_km(
        LatLng(lat=bounds.south, lng=mid_lng),
        LatLng(lat=bounds.north, lng=mid_lng),
    )
    return width_km, height_km


@dataclass(frozen=True)
class StudyArea:
    """Study area of a scenario enforcing minimum dimensions (RN-13).

    Attributes:
        bounds: Geographic bounding box in decimal degrees.

    Raises:
        AreaTooSmallError: If width or height is less than 1.5 km (RN-13).
    """

    bounds: Bounds

    def __post_init__(self) -> None:
        """Validates that both sides measure at least 1.5 km (RN-13)."""
        width_km, height_km = bounds_dimensions_km(self.bounds)
        if width_km < MIN_AREA_SIDE_KM or height_km < MIN_AREA_SIDE_KM:
            raise AreaTooSmallError(
                f"Study area dimensions ({width_km:.2f} km x {height_km:.2f} km) "
                f"must be at least {MIN_AREA_SIDE_KM} km per side (RN-13)."
            )


@dataclass(frozen=True)
class TerrainRef:
    """Reference to the DEM assigned to a scenario and its clipping window (RN-27).

    Attributes:
        dem_id: Unique identifier of the assigned DEM.
        window: Clipping window equal to the scenario study area bounds.
    """

    dem_id: UUID
    window: Bounds


@dataclass(frozen=True)
class HeightAgl:
    """Antenna height above ground level of the DEM (RN-20).

    Attributes:
        meters: Height above ground level, in meters (m).

    Raises:
        HeightBelowMinimumError: If height is less than 0.5 m (RN-20).
    """

    meters: float

    def __post_init__(self) -> None:
        """Validates minimum antenna height >= 0.5 m (RN-20)."""
        if self.meters < MIN_HEIGHT_AGL_M:
            raise HeightBelowMinimumError(
                f"Antenna height ({self.meters} m) must be at least {MIN_HEIGHT_AGL_M} m (RN-20)."
            )


@dataclass(frozen=True)
class Antenna:
    """Antenna specification for a deployed node.

    Attributes:
        reference: Optional model or datasheet reference name.
        gain_dbi: Antenna gain, in dBi.
        polarization: Antenna polarization (VERTICAL or HORIZONTAL).
    """

    reference: str | None
    gain_dbi: float
    polarization: Polarization | None = Polarization.VERTICAL


@dataclass(frozen=True)
class TxPower:
    """Transmitter power specification of an end node.

    Attributes:
        nominal_dbm: Nominal transmission power, in dBm.
        tolerance_db: Power tolerance, in dB.
    """

    nominal_dbm: float
    tolerance_db: float = 0.0


@dataclass(frozen=True)
class RadioConfig:
    """Radio configuration of a scenario tied to a single LPWAN profile (RN-15, RN-22).

    Attributes:
        profile_id: Unique identifier of the LPWAN profile.
        technology: LPWAN technology of the profile.
        band_code: Selected band code from the profile.
        frequency_mhz: Operating carrier frequency, in MHz.
        band_min_mhz: Optional lower bound of the band, in MHz.
        band_max_mhz: Optional upper bound of the band, in MHz.

    Raises:
        FrequencyOutOfProfileError: If frequency_mhz <= 0 or outside [band_min_mhz, band_max_mhz].
    """

    profile_id: UUID
    technology: Technology
    band_code: str
    frequency_mhz: float
    band_min_mhz: float | None = None
    band_max_mhz: float | None = None

    def __post_init__(self) -> None:
        """Validates operating frequency against band limits (RN-22)."""
        if self.frequency_mhz <= 0:
            raise FrequencyOutOfProfileError(
                f"Frequency ({self.frequency_mhz} MHz) must be positive (RN-22)."
            )
        if (
            self.band_min_mhz is not None
            and self.band_max_mhz is not None
            and not (self.band_min_mhz <= self.frequency_mhz <= self.band_max_mhz)
        ):
            raise FrequencyOutOfProfileError(
                f"Frequency {self.frequency_mhz} MHz is outside band {self.band_code} "
                f"[{self.band_min_mhz}, {self.band_max_mhz}] MHz (RN-22)."
            )


@dataclass
class AccessNode:
    """Receiver node (gateway in LoRaWAN or base station in NB-IoT/LTE-M).

    Attributes:
        id: Unique identifier of the access node.
        name: Display name of the access node.
        position: Geographic position in WGS84 degrees.
        height_agl: Antenna height above ground level, in meters.
        antenna: Antenna parameters (gain in dBi, polarization).
        sensitivity_dbm: Receiver sensitivity threshold, in dBm.
        sensitivity_origin: Whether sensitivity comes from reference table or user edit.
    """

    name: str
    position: LatLng
    height_agl: HeightAgl
    antenna: Antenna
    sensitivity_dbm: float
    sensitivity_origin: SensitivityOrigin = SensitivityOrigin.REFERENCE_TO_VERIFY
    id: UUID = field(default_factory=uuid4)


@dataclass
class EndNode:
    """Transmitter field device node in an uplink LPWAN link.

    Attributes:
        id: Unique identifier of the end node.
        name: Display name of the end node.
        position: Geographic position in WGS84 degrees.
        height_agl: Antenna height above ground level, in meters.
        antenna: Antenna parameters (gain in dBi, polarization).
        tx_power: Transmitter power in dBm and tolerance in dB.
        source_template_id: Informative reference to the template copied from (RN-23).
    """

    name: str
    position: LatLng
    height_agl: HeightAgl
    antenna: Antenna
    tx_power: TxPower
    source_template_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class Link:
    """Uplink radio connection from an EndNode to an AccessNode.

    Attributes:
        id: Unique identifier of the link.
        end_node_id: Identifier of the transmitting end node.
        access_node_id: Identifier of the receiving access node.
    """

    end_node_id: UUID
    access_node_id: UUID
    id: UUID = field(default_factory=uuid4)


@dataclass
class Deployment:
    """Collection of access nodes, end nodes, and uplink links in a scenario.

    Attributes:
        access_nodes: Deployed receiving gateways/base stations.
        end_nodes: Deployed transmitting field nodes.
        links: Uplink links connecting each end node to an access node.
    """

    access_nodes: list[AccessNode] = field(default_factory=list)
    end_nodes: list[EndNode] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)


@dataclass(frozen=True)
class LongleyRiceParams:
    """User-configurable parameters for the Longley-Rice (ITM) point-to-point model.

    Attributes:
        ens0: Surface refractivity in N-units (mandatory per Q4).
        ipol: Polarization code (0 = horizontal, 1 = vertical).
        eps: Relative permittivity of ground.
        sgm: Ground conductivity, in S/m.
        klim: Radio climate code (5 = continental temperate).
        mdvar: Mode of variability (11 = accidental + point-to-point).
        qc: Confidence percentage (0 to 100).
        qr: Reliability quantile percentages.
    """

    ens0: float
    ipol: int = 1
    eps: float = 15.0
    sgm: float = 0.005
    klim: int = 5
    mdvar: int = 11
    qc: float = 50.0
    qr: tuple[float, ...] = (10.0, 50.0, 90.0)


@dataclass(frozen=True)
class PropagationSetup:
    """Propagation model selection and versioned parameters.

    Attributes:
        model_id: Identifier of the propagation model (default LONGLEY_RICE).
        parameters: Longley-Rice propagation parameters.
        schema_version: Schema version of the serialized parameters.
    """

    parameters: LongleyRiceParams
    model_id: str = "LONGLEY_RICE"
    schema_version: int = 1


@dataclass(frozen=True)
class ValidationCause:
    """Reason why a scenario cannot yet be simulated (RN-31).

    Attributes:
        code: Machine-readable error/cause code.
        message: Human-readable explanation.
    """

    code: str
    message: str


@dataclass
class Scenario:
    """Aggregate root representing an LPWAN simulation scenario.

    Enforces invariants across study area, terrain reference, radio configuration,
    nodes, and links (RN-11 to RN-31).

    Attributes:
        id: Unique identifier of the scenario.
        owner_id: Unique identifier of the owning user.
        name: Scenario name.
        description: Optional scenario description.
        comparison_group_id: Group identifier shared by scenario variants (RN-29).
        study_area: Geographic study area (RN-13).
        terrain_ref: Assigned DEM and clipping window (RN-26, RN-27).
        radio_config: LPWAN profile, band, and frequency configuration (RN-15, RN-22).
        deployment: Access nodes, end nodes, and links.
        propagation_setup: Propagation model and parameters.
        created_at: Creation UTC timestamp.
        updated_at: Last modification UTC timestamp.
    """

    owner_id: UUID
    name: str
    description: str | None = None
    id: UUID = field(default_factory=uuid4)
    comparison_group_id: UUID = field(default_factory=uuid4)
    study_area: StudyArea | None = None
    terrain_ref: TerrainRef | None = None
    radio_config: RadioConfig | None = None
    deployment: Deployment = field(default_factory=Deployment)
    propagation_setup: PropagationSetup | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def define_area(self, bounds: Bounds) -> None:
        """Defines or updates the study area of the scenario (UC-SC-01, RN-13, RN-14).

        Args:
            bounds: Target bounding box in decimal degrees.

        Raises:
            AreaTooSmallError: If any side of the area is smaller than 1.5 km (RN-13).
            AreaWouldExcludeNodesError: If existing deployed nodes fall outside bounds (RN-14).
        """
        new_area = StudyArea(bounds=bounds)

        excluded_names: list[str] = []
        for an in self.deployment.access_nodes:
            if not bounds.contains(an.position):
                excluded_names.append(an.name)
        for en in self.deployment.end_nodes:
            if not bounds.contains(en.position):
                excluded_names.append(en.name)

        if excluded_names:
            raise AreaWouldExcludeNodesError(excluded_node_names=excluded_names)

        self.study_area = new_area
        if self.terrain_ref is not None:
            self.terrain_ref = TerrainRef(
                dem_id=self.terrain_ref.dem_id,
                window=new_area.bounds,
            )
        self.updated_at = datetime.now(UTC)

    def assign_terrain(self, dem_id: UUID, dem_bounds: Bounds) -> None:
        """Assigns a DEM to the scenario and sets clipping window equal to study area (UC-SC-02).

        Args:
            dem_id: Unique identifier of the DEM.
            dem_bounds: Geographic bounds of the DEM.

        Raises:
            DemDoesNotCoverAreaError: If study area is missing or not covered by dem_bounds (RN-26).
        """
        if self.study_area is None:
            raise DemDoesNotCoverAreaError(
                "Cannot assign terrain before defining the scenario study area."
            )
        if not dem_bounds.contains_bounds(self.study_area.bounds):
            raise DemDoesNotCoverAreaError(
                "Assigned DEM bounds do not completely cover the scenario study area (RN-26)."
            )
        self.terrain_ref = TerrainRef(
            dem_id=dem_id,
            window=self.study_area.bounds,
        )
        self.updated_at = datetime.now(UTC)

    def add_link(
        self,
        end_node: EndNode,
        access_node: AccessNode,
        link_id: UUID | None = None,
    ) -> Link:
        """Adds an uplink link and registers its nodes in the deployment (UC-SC-03).

        Args:
            end_node: Transmitting end node.
            access_node: Receiving access node.
            link_id: Optional explicit UUID for the link.

        Returns:
            The created Link entity.

        Raises:
            NodeOutsideAreaError: If either node is outside the study area (RN-21).
            EndNodeAlreadyLinkedError: If the end node already belongs to a link (RN-17).
            LinkTooShortError: If horizontal distance between nodes is < 1.0 km (RN-19).
        """
        if self.study_area is None:
            raise NodeOutsideAreaError("Study area must be defined before placing nodes (RN-21).")

        if not self.study_area.bounds.contains(access_node.position):
            raise NodeOutsideAreaError(
                f"Access node '{access_node.name}' is outside the study area (RN-21)."
            )
        if not self.study_area.bounds.contains(end_node.position):
            raise NodeOutsideAreaError(
                f"End node '{end_node.name}' is outside the study area (RN-21)."
            )

        for existing_link in self.deployment.links:
            if existing_link.end_node_id == end_node.id:
                raise EndNodeAlreadyLinkedError(
                    f"End node '{end_node.name}' is already connected to a link (RN-17)."
                )

        dist_km = geodesic_distance_km(end_node.position, access_node.position)
        if dist_km < MIN_LINK_DISTANCE_KM:
            raise LinkTooShortError(
                f"Link distance ({dist_km:.2f} km) must be >= {MIN_LINK_DISTANCE_KM} km (RN-19)."
            )

        if not any(an.id == access_node.id for an in self.deployment.access_nodes):
            self.deployment.access_nodes.append(access_node)
        if not any(en.id == end_node.id for en in self.deployment.end_nodes):
            self.deployment.end_nodes.append(end_node)

        link = Link(
            id=link_id or uuid4(),
            end_node_id=end_node.id,
            access_node_id=access_node.id,
        )
        self.deployment.links.append(link)
        self.updated_at = datetime.now(UTC)
        return link

    def move_node(self, node_id: UUID, position: LatLng) -> None:
        """Moves an existing access node or end node while preserving area and link invariants.

        Args:
            node_id: Identifier of the node to move.
            position: New geographic coordinates in WGS84 degrees.

        Raises:
            NodeOutsideAreaError: If the new position is outside the study area (RN-21).
            LinkTooShortError: If moving the node makes any connected link < 1.0 km (RN-19).
        """
        if self.study_area is None or not self.study_area.bounds.contains(position):
            raise NodeOutsideAreaError(
                "New node position lies outside the scenario study area (RN-21)."
            )

        an_map = {an.id: an for an in self.deployment.access_nodes}
        en_map = {en.id: en for en in self.deployment.end_nodes}

        if node_id in an_map:
            for link in self.deployment.links:
                if link.access_node_id == node_id:
                    other_en = en_map[link.end_node_id]
                    if geodesic_distance_km(other_en.position, position) < MIN_LINK_DISTANCE_KM:
                        raise LinkTooShortError(
                            "Moving access node makes connected link shorter than 1.0 km (RN-19)."
                        )
            an_map[node_id].position = position
        elif node_id in en_map:
            for link in self.deployment.links:
                if link.end_node_id == node_id:
                    other_an = an_map[link.access_node_id]
                    if geodesic_distance_km(position, other_an.position) < MIN_LINK_DISTANCE_KM:
                        raise LinkTooShortError(
                            "Moving end node makes connected link shorter than 1.0 km (RN-19)."
                        )
            en_map[node_id].position = position

        self.updated_at = datetime.now(UTC)

    def set_deployment(self, deployment: Deployment) -> None:
        """Replaces the full deployment validating all node and link invariants (RN-17..21).

        Args:
            deployment: New deployment of access nodes, end nodes, and links.

        Raises:
            NodeOutsideAreaError: If any node lies outside the study area (RN-21).
            EndNodeAlreadyLinkedError: If an end node appears in more than one link (RN-17).
            LinkTooShortError: If any link is shorter than 1.0 km (RN-19).
            OrphanNodeError: If any deployed node is not connected to at least one link (RN-18).
        """
        if (
            deployment.access_nodes or deployment.end_nodes or deployment.links
        ) and self.study_area is None:
            raise NodeOutsideAreaError("Cannot deploy nodes without a defined study area (RN-21).")

        if self.study_area is not None:
            for an in deployment.access_nodes:
                if not self.study_area.bounds.contains(an.position):
                    raise NodeOutsideAreaError(
                        f"Access node '{an.name}' is outside the study area (RN-21)."
                    )
            for en in deployment.end_nodes:
                if not self.study_area.bounds.contains(en.position):
                    raise NodeOutsideAreaError(
                        f"End node '{en.name}' is outside the study area (RN-21)."
                    )

        an_map = {an.id: an for an in deployment.access_nodes}
        en_map = {en.id: en for en in deployment.end_nodes}
        linked_en_ids: set[UUID] = set()
        linked_an_ids: set[UUID] = set()

        for link in deployment.links:
            if link.end_node_id not in en_map or link.access_node_id not in an_map:
                raise OrphanNodeError("Link references a node not present in deployment.")
            if link.end_node_id in linked_en_ids:
                raise EndNodeAlreadyLinkedError(
                    f"End node '{en_map[link.end_node_id].name}' is linked more than once (RN-17)."
                )
            linked_en_ids.add(link.end_node_id)
            linked_an_ids.add(link.access_node_id)

            dist_km = geodesic_distance_km(
                en_map[link.end_node_id].position,
                an_map[link.access_node_id].position,
            )
            if dist_km < MIN_LINK_DISTANCE_KM:
                raise LinkTooShortError(
                    f"Link distance ({dist_km:.2f} km) is below 1.0 km minimum (RN-19)."
                )

        orphan_names = [an.name for an in deployment.access_nodes if an.id not in linked_an_ids] + [
            en.name for en in deployment.end_nodes if en.id not in linked_en_ids
        ]
        if orphan_names:
            joined_names = ", ".join(orphan_names)
            raise OrphanNodeError(
                f"Deployment contains orphan nodes without links: {joined_names} (RN-18)."
            )

        self.deployment = deployment
        self.updated_at = datetime.now(UTC)

    def validate_for_simulation(self, dem_available: bool) -> list[ValidationCause]:
        """Checks whether the scenario satisfies all preconditions to run a simulation (RN-31).

        Args:
            dem_available: True if the assigned DEM exists and is in AVAILABLE status.

        Returns:
            List of ValidationCause objects; empty if the scenario is ready to simulate.
        """
        causes: list[ValidationCause] = []

        if self.study_area is None:
            causes.append(
                ValidationCause(
                    code="MissingStudyArea",
                    message="Study area is not defined.",
                )
            )

        if self.terrain_ref is None or not dem_available:
            causes.append(
                ValidationCause(
                    code="DemNotAvailable",
                    message="Assigned DEM is missing or not in AVAILABLE status (RN-26, RN-31).",
                )
            )

        if self.radio_config is None:
            causes.append(
                ValidationCause(
                    code="MissingRadioConfig",
                    message="LPWAN radio profile and frequency are not configured.",
                )
            )

        if not self.deployment.links:
            causes.append(
                ValidationCause(
                    code="NoLinksDefined",
                    message="At least one uplink link must be defined.",
                )
            )
        else:
            linked_an = {lnk.access_node_id for lnk in self.deployment.links}
            linked_en = {lnk.end_node_id for lnk in self.deployment.links}
            if len(linked_an) < len(self.deployment.access_nodes) or len(linked_en) < len(
                self.deployment.end_nodes
            ):
                causes.append(
                    ValidationCause(
                        code="OrphanNode",
                        message="All deployed nodes must belong to at least one link (RN-18).",
                    )
                )

        if self.propagation_setup is None:
            causes.append(
                ValidationCause(
                    code="MissingPropagationSetup",
                    message="Propagation model and parameters are not configured.",
                )
            )

        return causes
