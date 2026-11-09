"""Use case for listing user-owned DEMs."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.terrain.domain.models import Dem
from agrowave.modules.terrain.domain.ports import DemRepository


@dataclass(frozen=True)
class ListDemsQuery:
    """Parameters for listing DEMs.

    Attributes:
        owner_id: Unique identifier of the requesting user.
        search: Optional substring filter for name or description.
    """

    owner_id: UUID
    search: str | None = None


class ListDems:
    """Retrieves all DEMs belonging to an authenticated user."""

    def __init__(self, repo: DemRepository) -> None:
        """Initializes the use case with its repository dependency."""
        self._repo = repo

    def execute(self, query: ListDemsQuery) -> list[Dem]:
        """Lists user DEMs matching optional search term.

        Args:
            query: Query parameters including owner_id and optional search string.

        Returns:
            List of Dem entities owned by the user.
        """
        return self._repo.list_by_owner(owner_id=query.owner_id, search=query.search)

