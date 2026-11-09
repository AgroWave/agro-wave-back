"""Use case for deleting a DEM."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.terrain.domain.errors import (
    DemNotFoundError,
    ResourceInUseError,
)
from agrowave.modules.terrain.domain.ports import (
    DemObjectStore,
    DemRepository,
    DemUsageQuery,
)


@dataclass(frozen=True)
class DeleteDemCommand:
    """Parameters for deleting a DEM.

    Attributes:
        dem_id: Unique identifier of the DEM to delete.
        user_id: Unique identifier of the requesting user.
    """

    dem_id: UUID
    user_id: UUID


class DeleteDem:
    """Deletes a DEM from database and object storage (AC-03-09, RN-28)."""

    def __init__(
        self,
        repo: DemRepository,
        object_store: DemObjectStore,
        usage_query: DemUsageQuery,
    ) -> None:
        """Initializes the delete use case with necessary ports."""
        self._repo = repo
        self._object_store = object_store
        self._usage_query = usage_query

    def execute(self, cmd: DeleteDemCommand) -> None:
        """Deletes a DEM if not in use.

        Args:
            cmd: Command specifying DEM and requesting user.

        Raises:
            DemNotFoundError: If DEM does not exist or belongs to another user.
            ResourceInUseError: If DEM is assigned to one or more scenarios (RN-28).
        """
        dem = self._repo.get_by_id(cmd.dem_id)
        if dem is None or dem.owner_id != cmd.user_id:
            raise DemNotFoundError(f"DEM '{cmd.dem_id}' not found.")

        if self._usage_query.is_dem_in_use(cmd.dem_id):
            raise ResourceInUseError(
                f"DEM '{cmd.dem_id}' cannot be deleted because it is in use by scenarios."
            )

        if dem.object_key:
            self._object_store.delete_file(dem.object_key)

        self._repo.delete(cmd.dem_id)
