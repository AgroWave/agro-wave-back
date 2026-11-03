"""Use case for creating a custom LPWAN profile."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from agrowave.modules.profiles.domain.models import Band, LpwanProfile, Technology
from agrowave.modules.profiles.domain.ports import ProfileRepository


@dataclass(frozen=True)
class CreateProfileCommand:
    """Command payload for creating an LPWAN profile."""

    user_id: UUID
    name: str
    technology: Technology
    reference_sensitivity_dbm: float
    bands: list[Band]
    spreading_factor: int | None = None


class CreateProfile:
    """Creates a new owned LPWAN profile (AC-02-04)."""

    def __init__(self, profile_repository: ProfileRepository) -> None:
        """Initializes the create use case.

        Args:
            profile_repository: Profile persistence port.
        """
        self._repo = profile_repository

    def execute(self, command: CreateProfileCommand) -> LpwanProfile:
        """Executes profile creation.

        Args:
            command: Creation parameters.

        Returns:
            Created LpwanProfile instance.

        Raises:
            SpreadingFactorNotAllowedError: If SF violates technology rules (RN-07).
            InvalidBandRangeError: If band min_mhz >= max_mhz.
        """
        profile = LpwanProfile(
            id=uuid4(),
            name=command.name,
            technology=command.technology,
            reference_sensitivity_dbm=command.reference_sensitivity_dbm,
            bands=command.bands,
            spreading_factor=command.spreading_factor,
            owner_id=command.user_id,
            is_predefined=False,
        )
        self._repo.save(profile)
        return profile
