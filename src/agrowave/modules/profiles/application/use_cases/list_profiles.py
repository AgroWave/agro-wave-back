"""Use case for listing accessible LPWAN profiles (AC-02-03)."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.profiles.domain.models import LpwanProfile, Technology
from agrowave.modules.profiles.domain.ports import ProfileRepository


@dataclass(frozen=True)
class ListProfilesQuery:
    """Query parameters for listing profiles."""

    user_id: UUID
    technology: Technology | None = None
    owner: str | None = None  # 'mine' or 'predefined'


class ListProfiles:
    """Lists predefined profiles and profiles owned by the requesting user (AC-02-03)."""

    def __init__(self, profile_repository: ProfileRepository) -> None:
        """Initializes the query use case.

        Args:
            profile_repository: Profile persistence port.
        """
        self._repo = profile_repository

    def execute(self, query: ListProfilesQuery) -> list[LpwanProfile]:
        """Executes profile listing.

        Args:
            query: Listing query filters.

        Returns:
            List of accessible LpwanProfile instances.
        """
        return self._repo.list_accessible(
            user_id=query.user_id,
            technology=query.technology,
            owner=query.owner,
        )
