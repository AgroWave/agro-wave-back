"""API tests for fetching node templates for a profile (AC-02-07)."""

from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from agrowave.modules.identity.infrastructure.row_models import IdentityUserRow
from agrowave.modules.profiles.infrastructure.row_models import (
    ProfilesLpwanProfileRow,
    ProfilesNodeTemplateRow,
)


def _create_authenticated_user(client: TestClient, email: str = "user@example.com") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": email, "password": "Password123!"},
    )
    engine = client.app.dependency_overrides.get(list(client.app.dependency_overrides.keys())[0])()
    with Session(engine) as session:
        user_row = session.query(IdentityUserRow).filter_by(email=email).one()
        user_row.email_confirmed = True
        session.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return login_res.json()["access_token"]


def test_ac02_07_templates_by_profile_technology(client: TestClient, api_engine) -> None:
    """AC-02-07: Fetching node templates returns templates matching the profile's technology."""
    token = _create_authenticated_user(client, "user_template@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    profile_id = uuid4()
    with Session(api_engine) as session:
        session.add(
            ProfilesLpwanProfileRow(
                id=profile_id,
                owner_id=None,
                is_predefined=True,
                name="LoRa SF7",
                technology="LORAWAN",
                spreading_factor=7,
                reference_sensitivity_dbm=-124.0,
            )
        )
        session.add(
            ProfilesNodeTemplateRow(
                id=uuid4(),
                technology="LORAWAN",
                role="END_NODE",
                name="Heltec WiFi LoRa V3",
                module_ref="Heltec WiFi LoRa V3",
                antenna_ref="LoRa U.FL IP-EX",
                antenna_gain_dbi=2.0,
                tx_power_nominal_dbm=21.0,
                tx_power_tolerance_db=1.0,
            )
        )
        session.add(
            ProfilesNodeTemplateRow(
                id=uuid4(),
                technology="NB_IOT",
                role="END_NODE",
                name="T-SIM7070G",
                module_ref="T-SIM7070G",
                antenna_gain_dbi=5.0,
                tx_power_nominal_dbm=20.0,
                tx_power_tolerance_db=2.7,
            )
        )
        session.commit()

    res = client.get(f"/api/v1/profiles/{profile_id}/node-templates", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    templates = res.json()
    assert len(templates) == 1
    assert templates[0]["technology"] == "LORAWAN"
    assert templates[0]["name"] == "Heltec WiFi LoRa V3"
    assert templates[0]["antenna"]["gain_dbi"] == 2.0
    assert templates[0]["tx_power"]["nominal_dbm"] == 21.0

    # Unknown profile returns 404
    unknown_res = client.get(f"/api/v1/profiles/{uuid4()}/node-templates", headers=headers)
    assert unknown_res.status_code == status.HTTP_404_NOT_FOUND


def test_ac02_07_unsourced_template_fields_are_null(client: TestClient, api_engine) -> None:
    """AC-02-07: Template fields without a source are returned as null, not as zero."""
    token = _create_authenticated_user(client, "user_template_null@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    profile_id = uuid4()
    with Session(api_engine) as session:
        session.add(
            ProfilesLpwanProfileRow(
                id=profile_id,
                owner_id=None,
                is_predefined=True,
                name="NB-IoT",
                technology="NB_IOT",
                spreading_factor=None,
                reference_sensitivity_dbm=-130.0,
            )
        )
        session.add(
            ProfilesNodeTemplateRow(
                id=uuid4(),
                technology="NB_IOT",
                role="ACCESS_NODE",
                name="NB-IoT access node",
                module_ref=None,
                antenna_ref=None,
                antenna_gain_dbi=None,
            )
        )
        session.commit()

    res = client.get(f"/api/v1/profiles/{profile_id}/node-templates", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    templates = res.json()
    assert len(templates) == 1
    assert templates[0]["antenna"]["gain_dbi"] is None, "unsourced gain must be null"
    assert templates[0]["antenna"]["reference"] is None, "unsourced antenna must be null"
    assert templates[0]["module_ref"] is None, "unsourced module must be null"
    assert templates[0]["tx_power"] is None, "access nodes have no transmit power"
