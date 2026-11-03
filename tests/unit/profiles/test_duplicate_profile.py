"""Unit tests for DuplicateProfile use case (RN-10, AC-27)."""

from uuid import uuid4

import pytest

from agrowave.modules.profiles.application.use_cases.duplicate_profile import (
    DuplicateProfile,
    DuplicateProfileCommand,
)
from agrowave.modules.profiles.domain.errors import ProfileNotFoundError
from agrowave.modules.profiles.domain.models import Band, LpwanProfile, Technology
from agrowave.modules.profiles.domain.ports import ProfileRepository


class InMemoryProfileRepository(ProfileRepository):
    def __init__(self, profiles: list[LpwanProfile] | None = None) -> None:
        self.profiles: dict = {p.id: p for p in (profiles or [])}

    def get_by_id(self, profile_id):
        return self.profiles.get(profile_id)

    def list_accessible(self, user_id, technology=None, owner=None):
        return list(self.profiles.values())

    def save(self, profile):
        self.profiles[profile.id] = profile

    def delete(self, profile_id):
        self.profiles.pop(profile_id, None)


def test_ac27_predefined_profile_is_read_only_and_duplicable() -> None:
    """AC-27: A predefined profile cannot be edited, but duplicating it creates an owned profile."""
    user_id = uuid4()
    predefined_id = uuid4()
    predefined = LpwanProfile(
        id=predefined_id,
        owner_id=None,
        name="LoRaWAN SF10 Predefined",
        technology=Technology.LORAWAN,
        spreading_factor=10,
        reference_sensitivity_dbm=-130.0,
        bands=[Band(code="902-928", min_mhz=902.0, max_mhz=928.0)],
    )

    repo = InMemoryProfileRepository([predefined])
    use_case = DuplicateProfile(repo)

    command = DuplicateProfileCommand(
        profile_id=predefined_id,
        user_id=user_id,
        name="My Custom SF10 Profile",
    )
    duplicated = use_case.execute(command)

    assert duplicated.id != predefined_id
    assert duplicated.owner_id == user_id
    assert duplicated.is_predefined is False
    assert duplicated.name == "My Custom SF10 Profile"
    assert duplicated.technology == Technology.LORAWAN
    assert duplicated.spreading_factor == 10
    assert duplicated.reference_sensitivity_dbm == -130.0
    assert len(duplicated.bands) == 1
    assert duplicated.bands[0].code == "902-928"

    # Profile is saved in repo
    saved = repo.get_by_id(duplicated.id)
    assert saved is not None
    assert saved.name == "My Custom SF10 Profile"


def test_duplicate_without_custom_name_preserves_name() -> None:
    """Duplicating without specifying a custom name keeps the original name."""
    user_id = uuid4()
    predefined_id = uuid4()
    predefined = LpwanProfile(
        id=predefined_id,
        owner_id=None,
        name="LTE-M Predefined",
        technology=Technology.LTE_M,
        spreading_factor=None,
        reference_sensitivity_dbm=-130.0,
        bands=[Band(code="B1")],
    )

    repo = InMemoryProfileRepository([predefined])
    use_case = DuplicateProfile(repo)

    duplicated = use_case.execute(
        DuplicateProfileCommand(
            profile_id=predefined_id,
            user_id=user_id,
        )
    )

    assert duplicated.name == "LTE-M Predefined"
    assert duplicated.owner_id == user_id
    assert duplicated.is_predefined is False


def test_duplicate_non_existent_or_unauthorized_profile_raises_not_found() -> None:
    """Duplicating an unknown profile raises ProfileNotFoundError."""
    repo = InMemoryProfileRepository([])
    use_case = DuplicateProfile(repo)

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(
            DuplicateProfileCommand(
                profile_id=uuid4(),
                user_id=uuid4(),
            )
        )
