"""Unit tests for the CreateProfile, ListProfiles and ListNodeTemplates use cases."""

from uuid import uuid4

import pytest

from agrowave.modules.profiles.application.use_cases.create_profile import (
    CreateProfile,
    CreateProfileCommand,
)
from agrowave.modules.profiles.application.use_cases.list_node_templates import (
    ListNodeTemplates,
    ListNodeTemplatesQuery,
)
from agrowave.modules.profiles.application.use_cases.list_profiles import (
    ListProfiles,
    ListProfilesQuery,
)
from agrowave.modules.profiles.domain.errors import ProfileNotFoundError
from agrowave.modules.profiles.domain.models import (
    Antenna,
    Band,
    LpwanProfile,
    NodeRole,
    NodeTemplate,
    Polarization,
    Technology,
    TxPower,
)
from agrowave.modules.profiles.domain.ports import NodeTemplateRepository, ProfileRepository


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


class InMemoryNodeTemplateRepository(NodeTemplateRepository):
    def __init__(self, templates: list[NodeTemplate] | None = None) -> None:
        self.templates = templates or []

    def list_by_technology(self, technology: Technology) -> list[NodeTemplate]:
        return [t for t in self.templates if t.technology == technology]

    def get_by_id(self, template_id):
        for t in self.templates:
            if t.id == template_id:
                return t
        return None


def test_ac02_04_create_own_profile() -> None:
    """AC-02-04: Creating a profile assigns owner_id, sets is_predefined False and persists it."""
    user_id = uuid4()
    repo = InMemoryProfileRepository()
    use_case = CreateProfile(repo)

    command = CreateProfileCommand(
        user_id=user_id,
        name="Custom LoRaWAN",
        technology=Technology.LORAWAN,
        spreading_factor=8,
        reference_sensitivity_dbm=-127.0,
        bands=[Band(code="902-928", min_mhz=902.0, max_mhz=928.0)],
    )

    created = use_case.execute(command)

    assert created.owner_id == user_id
    assert created.is_predefined is False
    assert created.name == "Custom LoRaWAN"
    assert created.spreading_factor == 8
    assert created.reference_sensitivity_dbm == -127.0
    assert len(created.bands) == 1

    saved = repo.get_by_id(created.id)
    assert saved is not None
    assert saved.id == created.id


def test_ac02_03_list_returns_predefined_and_own_only() -> None:
    """AC-02-03: Listing returns predefined and own profiles, honoring the filters."""
    user_1 = uuid4()
    user_2 = uuid4()

    predefined_lora = LpwanProfile(
        id=uuid4(),
        owner_id=None,
        name="Predefined LoRa",
        technology=Technology.LORAWAN,
        spreading_factor=7,
        reference_sensitivity_dbm=-124.0,
    )
    predefined_nbiot = LpwanProfile(
        id=uuid4(),
        owner_id=None,
        name="Predefined NB-IoT",
        technology=Technology.NB_IOT,
        reference_sensitivity_dbm=-130.0,
    )
    user_1_lora = LpwanProfile(
        id=uuid4(),
        owner_id=user_1,
        name="User 1 LoRa",
        technology=Technology.LORAWAN,
        spreading_factor=10,
        reference_sensitivity_dbm=-130.0,
    )
    user_2_lora = LpwanProfile(
        id=uuid4(),
        owner_id=user_2,
        name="User 2 LoRa",
        technology=Technology.LORAWAN,
        spreading_factor=12,
        reference_sensitivity_dbm=-137.0,
    )

    repo = InMemoryProfileRepository(
        [
            predefined_lora,
            predefined_nbiot,
            user_1_lora,
            user_2_lora,
        ]
    )
    use_case = ListProfiles(repo)

    # 1. Unfiltered for user_1: predefined + user_1's profiles, NEVER user_2's
    results = use_case.execute(ListProfilesQuery(user_id=user_1))
    result_ids = {p.id for p in results}
    assert predefined_lora.id in result_ids
    assert predefined_nbiot.id in result_ids
    assert user_1_lora.id in result_ids
    assert user_2_lora.id not in result_ids

    # 2. Filtered by technology LORAWAN
    lora_results = use_case.execute(
        ListProfilesQuery(user_id=user_1, technology=Technology.LORAWAN)
    )
    assert len(lora_results) == 2
    assert all(p.technology == Technology.LORAWAN for p in lora_results)

    # 3. Filtered by owner = 'mine'
    mine_results = use_case.execute(ListProfilesQuery(user_id=user_1, owner="mine"))
    assert len(mine_results) == 1
    assert mine_results[0].id == user_1_lora.id

    # 4. Filtered by owner = 'predefined'
    predefined_results = use_case.execute(ListProfilesQuery(user_id=user_1, owner="predefined"))
    assert len(predefined_results) == 2
    assert all(p.is_predefined for p in predefined_results)


def test_ac02_07_templates_by_profile_technology() -> None:
    """AC-02-07: Fetching templates returns node templates matching profile's technology."""
    user_id = uuid4()
    profile_id = uuid4()
    profile = LpwanProfile(
        id=profile_id,
        owner_id=user_id,
        name="Custom LoRa Profile",
        technology=Technology.LORAWAN,
        spreading_factor=7,
        reference_sensitivity_dbm=-124.0,
    )

    lora_template = NodeTemplate(
        id=uuid4(),
        technology=Technology.LORAWAN,
        role=NodeRole.END_NODE,
        name="Heltec WiFi LoRa V3",
        module_ref="Heltec WiFi LoRa V3",
        antenna=Antenna(
            reference="LoRa U.FL IP-EX", gain_dbi=2.0, polarization=Polarization.VERTICAL
        ),
        tx_power=TxPower(nominal_dbm=21.0, tolerance_db=1.0),
    )
    nbiot_template = NodeTemplate(
        id=uuid4(),
        technology=Technology.NB_IOT,
        role=NodeRole.END_NODE,
        name="T-SIM7070G",
        antenna=Antenna(gain_dbi=5.0),
    )

    profile_repo = InMemoryProfileRepository([profile])
    template_repo = InMemoryNodeTemplateRepository([lora_template, nbiot_template])
    use_case = ListNodeTemplates(profile_repo, template_repo)

    templates = use_case.execute(ListNodeTemplatesQuery(profile_id=profile_id, user_id=user_id))
    assert len(templates) == 1
    assert templates[0].id == lora_template.id
    assert templates[0].technology == Technology.LORAWAN

    # Unauthorized access to another user's profile raises ProfileNotFoundError
    other_user = uuid4()
    with pytest.raises(ProfileNotFoundError):
        use_case.execute(ListNodeTemplatesQuery(profile_id=profile_id, user_id=other_user))
