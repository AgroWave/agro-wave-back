"""API tests for listing LPWAN profiles with filters (AC-02-03)."""

from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from agrowave.modules.identity.infrastructure.row_models import IdentityUserRow
from agrowave.modules.profiles.infrastructure.row_models import ProfilesLpwanProfileRow


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


def test_ac02_03_list_returns_predefined_and_own_only(client: TestClient, api_engine) -> None:
    """AC-02-03: Listing returns predefined and own profiles only, with optional filters."""
    token_1 = _create_authenticated_user(client, "user_one@example.com")
    token_2 = _create_authenticated_user(client, "user_two@example.com")

    # Seed predefined profile
    predefined_id = uuid4()
    with Session(api_engine) as session:
        session.add(
            ProfilesLpwanProfileRow(
                id=predefined_id,
                owner_id=None,
                is_predefined=True,
                name="Predefined LoRa",
                technology="LORAWAN",
                spreading_factor=7,
                reference_sensitivity_dbm=-124.0,
            )
        )
        session.commit()

    # User 1 creates an own profile
    client.post(
        "/api/v1/profiles",
        json={
            "name": "User 1 Custom LTE-M",
            "technology": "LTE_M",
            "reference_sensitivity_dbm": -130.0,
            "bands": [],
        },
        headers={"Authorization": f"Bearer {token_1}"},
    )

    # User 2 creates an own profile
    client.post(
        "/api/v1/profiles",
        json={
            "name": "User 2 Custom NB-IoT",
            "technology": "NB_IOT",
            "reference_sensitivity_dbm": -130.0,
            "bands": [],
        },
        headers={"Authorization": f"Bearer {token_2}"},
    )

    # User 1 lists profiles: should see predefined and user 1's profile, NOT user 2's
    headers_1 = {"Authorization": f"Bearer {token_1}"}
    res_1 = client.get("/api/v1/profiles", headers=headers_1)
    assert res_1.status_code == status.HTTP_200_OK
    names_1 = [p["name"] for p in res_1.json()]
    assert "Predefined LoRa" in names_1
    assert "User 1 Custom LTE-M" in names_1
    assert "User 2 Custom NB-IoT" not in names_1

    # Filter by technology=LORAWAN
    lora_res = client.get("/api/v1/profiles?technology=LORAWAN", headers=headers_1)
    assert lora_res.status_code == status.HTTP_200_OK
    assert len(lora_res.json()) == 1
    assert lora_res.json()[0]["technology"] == "LORAWAN"

    # Filter by owner=mine
    mine_res = client.get("/api/v1/profiles?owner=mine", headers=headers_1)
    assert mine_res.status_code == status.HTTP_200_OK
    assert len(mine_res.json()) == 1
    assert mine_res.json()[0]["name"] == "User 1 Custom LTE-M"

    # Filter by owner=predefined
    predef_res = client.get("/api/v1/profiles?owner=predefined", headers=headers_1)
    assert predef_res.status_code == status.HTTP_200_OK
    assert len(predef_res.json()) == 1
    assert predef_res.json()[0]["name"] == "Predefined LoRa"
