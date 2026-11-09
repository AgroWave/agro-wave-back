"""Use case for updating DEM metadata."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.terrain.domain.errors import DemNotFoundError
from agrowave.modules.terrain.domain.models import Dem
from agrowave.modules.terrain.domain.ports import DemRepository


@dataclass(frozen=True)
class UpdateDemCommand:
    """Parameters for updating DEM metadata.

    Attributes:
        dem_id: Unique identifier of the DEM to update.
        user_id: Unique identifier of the requesting user.
        name: Optional updated name.
        description: Optional updated description.
    """

    dem_id: UUID
    user_id: UUID
    name: str | None = None
    description: str | None = None


class UpdateDem:
    """Updates metadata (name, description) of an existing DEM (AC-03-08)."""

    def __init__(self, repo: DemRepository) -> None:
        """Initializes the use case with its repository dependency."""
        self._repo = repo

    def execute(self, cmd: UpdateDemCommand) -> Dem:
        """Updates DEM metadata.

        Args:
            cmd: Command containing updated fields and user credentials.

        Returns:
            The updated Dem entity.

        Raises:
            DemNotFoundError: If the DEM does not exist or belongs to another user.
        """
        dem = self._repo.get_by_id(cmd.dem_id)
        if dem is None or dem.owner_id != cmd.user_id:
            raise DemNotFoundError(f"DEM '{cmd.dem_id}' not found.")

        updated_name = cmd.name if cmd.name is not None else dem.name
        updated_description = cmd.description if cmd.description is not None else dem.description

        updated_dem = Dem(
            id=dem.id,
            owner_id=dem.owner_id,
            name=updated_name,
            description=updated_description,
            bounds=dem.bounds,
            status=dem.status,
            resolution_m=dem.resolution_m,
            object_key=dem.object_key,
            size_bytes=dem.size_bytes,
            failure_reason=dem.failure_reason,
            created_at=dem.created_at,
        )
        self._repo.save(updated_dem)
        return updated_dem
