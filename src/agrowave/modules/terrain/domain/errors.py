"""Domain exceptions for the terrain bounded context."""


class TerrainDomainError(Exception):
    """Base domain exception for the terrain module."""


class InvalidBoundsError(TerrainDomainError):
    """Raised when geographic bounds have south >= north or west >= east."""


class AreaOutsideColombiaError(TerrainDomainError):
    """Raised when a study area or DEM extends outside continental Colombia (RN-12)."""


class AreaTooSmallError(TerrainDomainError):
    """Raised when a study area side is smaller than 1.5 km (RN-13)."""


class DemNotFoundError(TerrainDomainError):
    """Raised when a requested DEM cannot be found."""


class ResourceInUseError(TerrainDomainError):
    """Raised when attempting to delete a DEM that is in use by scenarios (RN-28)."""

