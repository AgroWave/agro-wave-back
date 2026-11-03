"""Domain ports (interfaces) for the LPWAN profiles module."""

from abc import ABC, abstractmethod
from uuid import UUID

from agrowave.modules.profiles.domain.models import LpwanProfile, NodeTemplate, Technology


class ProfileRepository(ABC):
    """Abstract repository for persisting and querying LPWAN profiles."""

    @abstractmethod
    def get_by_id(self, profile_id: UUID) -> LpwanProfile | None:
        """Retrieves a profile by its unique identifier.

        Args:
            profile_id: Profile UUID.

        Returns:
            LpwanProfile instance if found, None otherwise.
        """

    @abstractmethod
    def list_accessible(
        self,
        user_id: UUID,
        technology: Technology | None = None,
        owner: str | None = None,
    ) -> list[LpwanProfile]:
        """Lists predefined profiles and profiles owned by the specified user.

        Args:
            user_id: Requesting user identifier.
            technology: Optional technology filter.
            owner: Optional filter ('mine' for owned only, 'predefined' for system only).

        Returns:
            List of accessible LpwanProfile instances.
        """

    @abstractmethod
    def save(self, profile: LpwanProfile) -> None:
        """Saves or updates an LPWAN profile.

        Args:
            profile: Profile entity to persist.
        """

    @abstractmethod
    def delete(self, profile_id: UUID) -> None:
        """Deletes a profile by its identifier.

        Args:
            profile_id: Profile UUID to remove.
        """


class NodeTemplateRepository(ABC):
    """Abstract repository for node templates."""

    @abstractmethod
    def list_by_technology(self, technology: Technology) -> list[NodeTemplate]:
        """Lists reference node templates for a given technology.

        Args:
            technology: Target LPWAN technology.

        Returns:
            List of matching NodeTemplate instances.
        """

    @abstractmethod
    def get_by_id(self, template_id: UUID) -> NodeTemplate | None:
        """Retrieves a template by identifier.

        Args:
            template_id: Template UUID.

        Returns:
            NodeTemplate if found, None otherwise.
        """


class ProfileUsageQuery(ABC):
    """Port to query whether a profile is in use by scenarios (RN-09)."""

    @abstractmethod
    def is_profile_in_use(self, profile_id: UUID) -> bool:
        """Checks if any scenario is currently referencing the profile.

        Args:
            profile_id: Profile UUID to check.

        Returns:
            True if at least one scenario references the profile, False otherwise.
        """
