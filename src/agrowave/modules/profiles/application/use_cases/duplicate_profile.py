"""Use case for duplicating an LPWAN profile (AC-27)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from agrowave.modules.profiles.domain.errors import ProfileNotFoundError
from agrowave.modules.profiles.domain.models import LpwanProfile
from agrowave.modules.profiles.domain.ports import ProfileRepository


@dataclass(frozen=True)
class DuplicateProfileCommand:
    """Command payload for duplicating a profile."""

    profile_id: UUID
    user_id: UUID
    name: str | None = None


class DuplicateProfile:
    """Clones a predefined or owned profile into a new custom profile for the user (AC-27)."""

    def __init__(self, profile_repository: ProfileRepository) -> None:
        """Initializes the duplication use case.

        Args:
            profile_repository: Profile persistence port.
        """
        self._repo = profile_repository

    def execute(self, command: DuplicateProfileCommand) -> LpwanProfile:
        """Executes profile duplication.

        Args:
            command: Duplication command parameters.

        Returns:
            Newly created, owned LpwanProfile clone.

        Raises:
            ProfileNotFoundError: If profile does not exist or is owned by another user.
        """
        source = self._repo.get_by_id(command.profile_id)
        if source is None:
            raise ProfileNotFoundError(f"Profile {command.profile_id} not found")

        # Must be either predefined or owned by the requesting user
        if not source.is_predefined and source.owner_id != command.user_id:
            raise ProfileNotFoundError(f"Profile {command.profile_id} not found")

        target_name = command.name if command.name is not None else source.name

        clone = LpwanProfile(
            id=uuid4(),
            name=target_name,
            technology=source.technology,
            reference_sensitivity_dbm=source.reference_sensitivity_dbm,
            bands=list(source.bands),
            spreading_factor=source.spreading_factor,
            owner_id=command.user_id,
            is_predefined=False,
            created_at=datetime.now(UTC),
        )

        self._repo.save(clone)
        return clone
