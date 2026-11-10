"""Use case for listing simulations owned by a user (RF-004)."""

from uuid import UUID

from agrowave.modules.simulation.domain.models import (
    Simulation,
    SimulationStatus,
    Technology,
)
from agrowave.modules.simulation.domain.ports import SimulationRepository


class ListSimulations:
    """Lists simulations owned by the requesting user with optional filtering and sorting."""

    def __init__(self, repository: SimulationRepository) -> None:
        """Initializes the use case with the simulation repository port."""
        self._repository = repository

    def execute(
        self,
        owner_id: UUID,
        q: str | None = None,
        technology: Technology | None = None,
        status: SimulationStatus | None = None,
        comparison_group_id: UUID | None = None,
        sort: str = "newest",
    ) -> list[Simulation]:
        """Retrieves matching simulations for the user.

        Args:
            owner_id: User identifier.
            q: Optional substring search on simulation name.
            technology: Optional LPWAN technology filter.
            status: Optional simulation lifecycle status filter.
            comparison_group_id: Optional comparison group filter.
            sort: Sort order ('newest', 'oldest', 'name').

        Returns:
            List of matching Simulation aggregates.
        """
        return self._repository.list_by_owner(
            owner_id=owner_id,
            q=q,
            technology=technology,
            status=status,
            comparison_group_id=comparison_group_id,
            sort=sort,
        )
