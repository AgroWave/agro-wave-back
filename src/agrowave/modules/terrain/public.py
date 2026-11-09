"""Public API for the terrain bounded context (interfaces between modules)."""

from uuid import UUID

from agrowave.modules.terrain.domain.models import Dem
from agrowave.modules.terrain.domain.ports import DemRepository


class TerrainService:
    """Public facade exposing terrain data lookups to other bounded contexts."""

    def __init__(self, dem_repository: DemRepository) -> None:
        """Initializes the terrain public service facade.

        Args:
            dem_repository: DEM repository port.
        """
        self._dem_repo = dem_repository

    def get_dem(self, dem_id: UUID) -> Dem | None:
        """Looks up a DEM by identifier.

        Args:
            dem_id: Unique identifier of the DEM.

        Returns:
            Dem if found, None otherwise.
        """
        return self._dem_repo.get_by_id(dem_id)
