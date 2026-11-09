"""Use case for requesting a DEM download for a study area."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from agrowave.modules.terrain.domain.errors import AreaOutsideColombiaError
from agrowave.modules.terrain.domain.models import Bounds, Dem, DemStatus, StudyArea
from agrowave.modules.terrain.domain.ports import DemRepository, TerritoryBoundary


@dataclass(frozen=True)
class RequestDemDownloadCommand:
    """Command attributes for requesting a DEM download.

    Attributes:
        owner_id: Identifier of the owner user.
        name: Name for the DEM.
        bounds: Geographic boundary rectangle.
        description: Optional user description.
    """

    owner_id: UUID
    name: str
    bounds: Bounds
    description: str | None = None


class RequestDemDownload:
    """Use case that validates study area bounds and initiates a DEM download."""

    def __init__(
        self,
        repo: DemRepository,
        territory_boundary: TerritoryBoundary,
    ) -> None:
        """Initializes the use case with required dependencies.

        Args:
            repo: Port for persisting DEM records.
            territory_boundary: Port for validating national boundary inclusion.
        """
        self._repo = repo
        self._territory_boundary = territory_boundary

    def execute(self, command: RequestDemDownloadCommand) -> Dem:
        """Validates geographic rules and registers a new DEM in DOWNLOADING state.

        Args:
            command: Request parameters.

        Returns:
            Created Dem entity in DOWNLOADING status.

        Raises:
            AreaOutsideColombiaError: If bounds extend outside continental Colombia (RN-12).
            AreaTooSmallError: If either side of the bounds is smaller than 1.5 km (RN-13).
            InvalidBoundsError: If bounds coordinates are geometrically invalid.
        """
        # Validate inclusion in continental Colombia (RN-12)
        if not self._territory_boundary.is_within_colombia_continental(command.bounds):
            raise AreaOutsideColombiaError(
                f"Study area bounds {command.bounds} extend outside continental Colombia (RN-12)"
            )

        # Validate minimum area of 1.5 km x 1.5 km (RN-13)
        StudyArea(bounds=command.bounds)

        dem = Dem(
            id=uuid4(),
            owner_id=command.owner_id,
            name=command.name,
            bounds=command.bounds,
            status=DemStatus.DOWNLOADING,
            description=command.description,
            resolution_m=30.0,
        )
        self._repo.save(dem)
        return dem

