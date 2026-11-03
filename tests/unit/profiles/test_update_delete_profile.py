"""Unit tests for updating and deleting LPWAN profiles (RN-09, RN-10, AC-26, AC-27)."""

from uuid import uuid4

import pytest

from agrowave.modules.profiles.application.use_cases.delete_profile import (
    DeleteProfile,
    DeleteProfileCommand,
)
from agrowave.modules.profiles.application.use_cases.update_profile import (
    UpdateProfile,
    UpdateProfileCommand,
)
from agrowave.modules.profiles.domain.errors import (
    PredefinedProfileReadOnlyError,
    ProfileNotFoundError,
    ResourceInUseError,
)
from agrowave.modules.profiles.domain.models import Band, LpwanProfile, Technology
from agrowave.modules.profiles.domain.ports import ProfileRepository, ProfileUsageQuery


class InMemoryProfileRepository(ProfileRepository):
    def __init__(self, profiles: list[LpwanProfile] | None = None) -> None:
        self.profiles: dict = {p.id: p for p in (profiles or [])}

    def get_by_id(self, profile_id):
        return self.profiles.get(profile_id)

    def list_accessible(self, user_id, technology=None, owner=None):
        res = []
        for p in self.profiles.values():
            if p.is_predefined or p.owner_id == user_id:
                if technology and p.technology != technology:
                    continue
                if owner == "mine" and p.owner_id != user_id:
                    continue
                if owner == "predefined" and not p.is_predefined:
                    continue
                res.append(p)
        return res

    def save(self, profile):
        self.profiles[profile.id] = profile

    def delete(self, profile_id):
        self.profiles.pop(profile_id, None)


class FakeProfileUsageQuery(ProfileUsageQuery):
    def __init__(self, in_use_ids: set | None = None) -> None:
        self.in_use_ids = in_use_ids or set()

    def is_profile_in_use(self, profile_id) -> bool:
        return profile_id in self.in_use_ids


def test_ac26_profile_in_use_cannot_be_edited_or_deleted() -> None:
    """AC-26: Editing or deleting a profile in use raises ResourceInUseError (RN-09)."""
    user_id = uuid4()
    profile_id = uuid4()
    profile = LpwanProfile(
        id=profile_id,
        owner_id=user_id,
        name="My Profile",
        technology=Technology.LORAWAN,
        spreading_factor=7,
        reference_sensitivity_dbm=-124.0,
        bands=[Band(code="902-928", min_mhz=902.0, max_mhz=928.0)],
    )

    repo = InMemoryProfileRepository([profile])
    usage_query = FakeProfileUsageQuery(in_use_ids={profile_id})

    update_use_case = UpdateProfile(repo, usage_query)
    delete_use_case = DeleteProfile(repo, usage_query)

    # Attempting to update profile in use
    with pytest.raises(ResourceInUseError):
        update_use_case.execute(
            UpdateProfileCommand(
                profile_id=profile_id,
                user_id=user_id,
                name="Updated Name",
            )
        )

    # Attempting to delete profile in use
    with pytest.raises(ResourceInUseError):
        delete_use_case.execute(
            DeleteProfileCommand(
                profile_id=profile_id,
                user_id=user_id,
            )
        )


def test_predefined_profile_cannot_be_edited_or_deleted() -> None:
    """Predefined profiles cannot be edited or deleted by normal users (RN-10)."""
    user_id = uuid4()
    predefined_id = uuid4()
    predefined = LpwanProfile(
        id=predefined_id,
        owner_id=None,
        name="LoRaWAN SF7 Predefined",
        technology=Technology.LORAWAN,
        spreading_factor=7,
        reference_sensitivity_dbm=-124.0,
        bands=[Band(code="902-928", min_mhz=902.0, max_mhz=928.0)],
    )

    repo = InMemoryProfileRepository([predefined])
    usage_query = FakeProfileUsageQuery()

    update_use_case = UpdateProfile(repo, usage_query)
    delete_use_case = DeleteProfile(repo, usage_query)

    with pytest.raises(PredefinedProfileReadOnlyError):
        update_use_case.execute(
            UpdateProfileCommand(
                profile_id=predefined_id,
                user_id=user_id,
                name="Hacked Name",
            )
        )

    with pytest.raises(PredefinedProfileReadOnlyError):
        delete_use_case.execute(
            DeleteProfileCommand(
                profile_id=predefined_id,
                user_id=user_id,
            )
        )


def test_foreign_profile_returns_not_found() -> None:
    """Profiles owned by another user are inaccessible and raise ProfileNotFoundError."""
    owner_a = uuid4()
    user_b = uuid4()
    profile_id = uuid4()
    profile = LpwanProfile(
        id=profile_id,
        owner_id=owner_a,
        name="User A Profile",
        technology=Technology.NB_IOT,
        reference_sensitivity_dbm=-130.0,
        bands=[Band(code="B1")],
    )

    repo = InMemoryProfileRepository([profile])
    usage_query = FakeProfileUsageQuery()

    update_use_case = UpdateProfile(repo, usage_query)
    delete_use_case = DeleteProfile(repo, usage_query)

    with pytest.raises(ProfileNotFoundError):
        update_use_case.execute(
            UpdateProfileCommand(
                profile_id=profile_id,
                user_id=user_b,
                name="Attempt Update",
            )
        )

    with pytest.raises(ProfileNotFoundError):
        delete_use_case.execute(
            DeleteProfileCommand(
                profile_id=profile_id,
                user_id=user_b,
            )
        )
