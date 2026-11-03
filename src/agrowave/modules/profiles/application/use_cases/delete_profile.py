"""Use case for deleting an owned LPWAN profile."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.profiles.domain.errors import (
    PredefinedProfileReadOnlyError,
    ProfileNotFoundError,
    ResourceInUseError,
)
from agrowave.modules.profiles.domain.ports import ProfileRepository, ProfileUsageQuery


@dataclass(frozen=True)
class DeleteProfileCommand:
    """Command payload for deleting an LPWAN profile."""

    profile_id: UUID
    user_id: UUID


class DeleteProfile:
    """Deletes an owned LPWAN profile.

    Enforces that predefined profiles cannot be deleted (RN-10),
    profiles currently referenced by scenarios cannot be removed (RN-09),
    and foreign profiles are rejected as not found.
    """

    def __init__(
        self,
        profile_repository: ProfileRepository,
        profile_usage_query: ProfileUsageQuery,
    ) -> None:
        """Initializes the delete use case.

        Args:
            profile_repository: Profile persistence port.
            profile_usage_query: Query port checking if profile is in use.
        """
        self._repo = profile_repository
        self._usage_query = profile_usage_query

    def execute(self, command: DeleteProfileCommand) -> None:
        """Executes profile deletion.

        Args:
            command: Deletion parameters.

        Raises:
            ProfileNotFoundError: If profile does not exist or belongs to another user.
            PredefinedProfileReadOnlyError: If target profile is predefined (RN-10).
            ResourceInUseError: If profile is referenced by scenarios (RN-09).
        """
        profile = self._repo.get_by_id(command.profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"Profile {command.profile_id} not found")

        if profile.is_predefined or profile.owner_id is None:
            raise PredefinedProfileReadOnlyError(
                f"Predefined profile {command.profile_id} is read-only "
                "and cannot be deleted (RN-10)"
            )

        if profile.owner_id != command.user_id:
            raise ProfileNotFoundError(f"Profile {command.profile_id} not found")

        if self._usage_query.is_profile_in_use(profile.id):
            raise ResourceInUseError(
                f"Profile {command.profile_id} cannot be deleted "
                "because it is in use by scenarios (RN-09)"
            )

        self._repo.delete(profile.id)
