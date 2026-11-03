"""Use case for listing reference node templates for a profile (AC-02-07)."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.profiles.domain.errors import ProfileNotFoundError
from agrowave.modules.profiles.domain.models import NodeTemplate
from agrowave.modules.profiles.domain.ports import NodeTemplateRepository, ProfileRepository


@dataclass(frozen=True)
class ListNodeTemplatesQuery:
    """Query payload for fetching node templates."""

    profile_id: UUID
    user_id: UUID


class ListNodeTemplates:
    """Fetches reference node templates associated with a profile's technology (AC-02-07)."""

    def __init__(
        self,
        profile_repository: ProfileRepository,
        node_template_repository: NodeTemplateRepository,
    ) -> None:
        """Initializes the node templates query use case.

        Args:
            profile_repository: Profile persistence port.
            node_template_repository: Node template persistence port.
        """
        self._profile_repo = profile_repository
        self._template_repo = node_template_repository

    def execute(self, query: ListNodeTemplatesQuery) -> list[NodeTemplate]:
        """Executes node templates lookup.

        Args:
            query: Query parameters with profile_id and user_id.

        Returns:
            List of NodeTemplate instances matching the profile's technology.

        Raises:
            ProfileNotFoundError: If profile does not exist or belongs to another user.
        """
        profile = self._profile_repo.get_by_id(query.profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"Profile {query.profile_id} not found")

        if not profile.is_predefined and profile.owner_id != query.user_id:
            raise ProfileNotFoundError(f"Profile {query.profile_id} not found")

        return self._template_repo.list_by_technology(profile.technology)
