"""Domain models and value objects for terrain and elevation models."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from agrowave.modules.terrain.domain.errors import (
    AreaTooSmallError,
    InvalidBoundsError,
)
from agrowave.modules.terrain.domain.services import bounds_dimensions_km


class DemStatus(StrEnum):
    """Execution status of a digital elevation model lifecycle."""

    DOWNLOADING = "DOWNLOADING"
    AVAILABLE = "AVAILABLE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class LatLng:
    """Geographic point coordinate on WGS84 ellipsoid.

    Attributes:
        lat: Latitude in decimal degrees [-90.0, 90.0].
        lng: Longitude in decimal degrees [-180.0, 180.0].
    """

    lat: float
    lng: float


@dataclass(frozen=True)
class Bounds:
    """Axis-aligned geographic bounding box on WGS84 ellipsoid.

    Attributes:
        south: Lower latitude in decimal degrees.
        west: Lower longitude in decimal degrees.
        north: Upper latitude in decimal degrees.
        east: Upper longitude in decimal degrees.

    Raises:
        InvalidBoundsError: If south >= north or west >= east.
    """

    south: float
    west: float
    north: float
    east: float

    def __post_init__(self) -> None:
        """Validates that bounding box bounds are strictly positive."""
        if self.south >= self.north or self.west >= self.east:
            raise InvalidBoundsError(
                f"Invalid bounds: south ({self.south}) must be < north ({self.north}) "
                f"and west ({self.west}) must be < east ({self.east})"
            )

    def contains(self, point: LatLng) -> bool:
        """Checks if a point is contained within the bounding box."""
        return self.south <= point.lat <= self.north and self.west <= point.lng <= self.east

    def contains_bounds(self, other: "Bounds") -> bool:
        """Checks if another bounding box is fully contained within this bounding box."""
        return (
            self.south <= other.south
            and other.north <= self.north
            and self.west <= other.west
            and other.east <= self.east
        )


@dataclass(frozen=True)
class StudyArea:
    """Study area value object enforcing minimum size (RN-13).

    Attributes:
        bounds: Geographic boundary rectangle.

    Raises:
        AreaTooSmallError: If either width or height is less than 1.5 km (RN-13).
    """

    bounds: Bounds

    def __post_init__(self) -> None:
        """Enforces that study area has a minimum side of 1.5 km (RN-13)."""
        width_km, height_km = bounds_dimensions_km(self.bounds)
        if width_km < 1.5 or height_km < 1.5:
            raise AreaTooSmallError(
                f"Study area must measure at least 1.5 km per side (RN-13). "
                f"Got width={width_km:.2f} km, height={height_km:.2f} km"
            )


@dataclass
class Dem:
    """Digital elevation model aggregate root representing terrain raster data.

    Attributes:
        id: Unique identifier.
        owner_id: Identifier of the owner user.
        name: User-defined display name.
        bounds: Geographic bounding box of the DEM.
        status: Lifecycle processing status (DOWNLOADING, AVAILABLE, FAILED).
        description: Optional user-defined description.
        resolution_m: Spatial resolution in meters (30.0 for FABDEM, RN-25).
        object_key: Object storage key when available.
        size_bytes: Size of the raster file in bytes.
        failure_reason: Error message if download failed.
        created_at: Creation timestamp in UTC.
        updated_at: Last update timestamp in UTC.
    """

    id: UUID
    owner_id: UUID
    name: str
    bounds: Bounds
    status: DemStatus = DemStatus.DOWNLOADING
    description: str | None = None
    resolution_m: float = 30.0
    object_key: str | None = None
    size_bytes: int | None = None
    failure_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        """Initializes default timestamps in UTC."""
        now = datetime.now(UTC)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
