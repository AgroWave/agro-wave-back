"""Public API for the profiles bounded context (P4: interfaces between modules)."""

from uuid import UUID

from agrowave.modules.profiles.domain.models import LpwanProfile, NodeTemplate, Technology
from agrowave.modules.profiles.domain.ports import NodeTemplateRepository, ProfileRepository


class ProfilesService:
    """Public facade exposing profile and template lookups to other contexts."""

    def __init__(
        self,
        profile_repository: ProfileRepository,
        node_template_repository: NodeTemplateRepository,
    ) -> None:
        """Initializes the public service facade.

        Args:
            profile_repository: Profile repository port.
            node_template_repository: Node template repository port.
        """
        self._profile_repo = profile_repository
        self._template_repo = node_template_repository

    def get_profile(self, profile_id: UUID) -> LpwanProfile | None:
        """Looks up a profile by its identifier.

        Args:
            profile_id: Profile UUID.

        Returns:
            LpwanProfile if found, None otherwise.
        """
        return self._profile_repo.get_by_id(profile_id)

    def get_templates_by_technology(self, technology: Technology) -> list[NodeTemplate]:
        """Looks up reference node templates for a given technology.

        Args:
            technology: Target LPWAN technology.

        Returns:
            List of matching NodeTemplate instances.
        """
        return self._template_repo.list_by_technology(technology)
