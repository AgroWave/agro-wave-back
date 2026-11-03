"""Use case for updating an existing LPWAN profile."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.profiles.domain.errors import (
    PredefinedProfileReadOnlyError,
    ProfileNotFoundError,
    ResourceInUseError,
)
from agrowave.modules.profiles.domain.models import Band, LpwanProfile
from agrowave.modules.profiles.domain.ports import ProfileRepository, ProfileUsageQuery


@dataclass(frozen=True)
class UpdateProfileCommand:
    """Command payload for updating an LPWAN profile."""

    profile_id: UUID
    user_id: UUID
    name: str | None = None
    reference_sensitivity_dbm: float | None = None
    bands: list[Band] | None = None
    spreading_factor: int | None = None


class UpdateProfile:
    """Updates an owned LPWAN profile.

    Enforces that predefined profiles cannot be edited (RN-10),
    profiles currently in use by scenarios cannot be modified (RN-09),
    and profiles owned by other users are inaccessible.
    """

    def __init__(
        self,
        profile_repository: ProfileRepository,
        profile_usage_query: ProfileUsageQuery,
    ) -> None:
        """Initializes the update use case.

        Args:
            profile_repository: Profile persistence port.
            profile_usage_query: Query port checking if profile is in use.
        """
        self._repo = profile_repository
        self._usage_query = profile_usage_query

    def execute(self, command: UpdateProfileCommand) -> LpwanProfile:
        """Executes profile update.

        Args:
            command: Update parameters.

        Returns:
            Updated LpwanProfile instance.

        Raises:
            ProfileNotFoundError: If profile does not exist or belongs to another user.
            PredefinedProfileReadOnlyError: If target profile is predefined (RN-10).
            ResourceInUseError: If profile is in use by scenarios (RN-09).
            SpreadingFactorNotAllowedError: If SF violates technology rules (RN-07).
            InvalidBandRangeError: If band min_mhz >= max_mhz.
        """
        profile = self._repo.get_by_id(command.profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"Profile {command.profile_id} not found")

        if profile.is_predefined or profile.owner_id is None:
            raise PredefinedProfileReadOnlyError(
                f"Predefined profile {command.profile_id} is read-only "
                "and cannot be modified (RN-10)"
            )

        if profile.owner_id != command.user_id:
            raise ProfileNotFoundError(f"Profile {command.profile_id} not found")

        if self._usage_query.is_profile_in_use(profile.id):
            raise ResourceInUseError(
                f"Profile {command.profile_id} cannot be edited "
                "because it is in use by scenarios (RN-09)"
            )

        updated_name = command.name if command.name is not None else profile.name
        updated_sensitivity = (
            command.reference_sensitivity_dbm
            if command.reference_sensitivity_dbm is not None
            else profile.reference_sensitivity_dbm
        )
        updated_bands = command.bands if command.bands is not None else profile.bands
        updated_sf = (
            command.spreading_factor
            if command.spreading_factor is not None
            else profile.spreading_factor
        )

        updated_profile = LpwanProfile(
            id=profile.id,
            name=updated_name,
            technology=profile.technology,
            reference_sensitivity_dbm=updated_sensitivity,
            bands=updated_bands,
            spreading_factor=updated_sf,
            owner_id=profile.owner_id,
            is_predefined=False,
            created_at=profile.created_at,
        )

        self._repo.save(updated_profile)
        return updated_profile
