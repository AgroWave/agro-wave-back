"""Use case for retrieving a single DEM by identifier."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.terrain.domain.errors import DemNotFoundError
from agrowave.modules.terrain.domain.models import Dem
from agrowave.modules.terrain.domain.ports import DemRepository


@dataclass(frozen=True)
class GetDemQuery:
    """Parameters for retrieving a single DEM.

    Attributes:
        dem_id: Unique identifier of the requested DEM.
        user_id: Unique identifier of the requesting user.
    """

    dem_id: UUID
    user_id: UUID


class GetDem:
    """Retrieves a DEM ensuring ownership isolation (AC-03-11)."""

    def __init__(self, repo: DemRepository) -> None:
        """Initializes the use case with its repository dependency."""
        self._repo = repo

    def execute(self, query: GetDemQuery) -> Dem:
        """Retrieves a DEM by id if owned by the user.

        Args:
            query: Query parameters with dem_id and user_id.

        Returns:
            The Dem entity.

        Raises:
            DemNotFoundError: If the DEM does not exist or belongs to another user.
        """
        dem = self._repo.get_by_id(query.dem_id)
        if dem is None or dem.owner_id != query.user_id:
            raise DemNotFoundError(f"DEM '{query.dem_id}' not found.")
        return dem

