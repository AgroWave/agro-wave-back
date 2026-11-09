"""Domain ports (interfaces) for the terrain bounded context."""

from abc import ABC, abstractmethod
from pathlib import Path
from uuid import UUID

from agrowave.modules.terrain.domain.models import Bounds, Dem


class DemRepository(ABC):
    """Port for persisting and retrieving Dem entities."""

    @abstractmethod
    def save(self, dem: Dem) -> None:
        """Persists or updates a DEM entity."""

    @abstractmethod
    def get_by_id(self, dem_id: UUID) -> Dem | None:
        """Retrieves a DEM by unique identifier."""

    @abstractmethod
    def list_by_owner(self, owner_id: UUID, search: str | None = None) -> list[Dem]:
        """Lists DEMs owned by a user, optionally filtered by search query."""

    @abstractmethod
    def delete(self, dem_id: UUID) -> None:
        """Deletes a DEM record by identifier."""


class TerritoryBoundary(ABC):
    """Port for verifying geographical inclusion in national territory (RN-12)."""

    @abstractmethod
    def is_within_colombia_continental(self, bounds: Bounds) -> bool:
        """Verifies if the bounding box is entirely within continental Colombia.

        Args:
            bounds: Target bounding box.

        Returns:
            True if bounds are entirely contained within continental Colombia.
        """


class ElevationSource(ABC):
    """Port for acquiring digital elevation data from external sources."""

    @abstractmethod
    def download_and_mosaic(self, bounds: Bounds, output_cog_path: Path) -> tuple[int, float]:
        """Downloads, mosaics, and formats terrain tiles into a Cloud Optimized GeoTIFF.

        Args:
            bounds: Bounding box to extract.
            output_cog_path: Local filesystem destination path for generated COG.

        Returns:
            Tuple (size_bytes, resolution_m) of the produced raster file.
        """


class DemObjectStore(ABC):
    """Port for storing and retrieving DEM raster files in object storage."""

    @abstractmethod
    def upload_file(self, key: str, file_path: Path) -> None:
        """Uploads a local raster file to object storage."""

    @abstractmethod
    def delete_file(self, key: str) -> None:
        """Removes a raster file from object storage."""


class DemUsageQuery(ABC):
    """Port for checking if a DEM is in use by scenarios (RN-28)."""

    @abstractmethod
    def is_dem_in_use(self, dem_id: UUID) -> bool:
        """Returns True if any scenario is currently assigned to this DEM."""

