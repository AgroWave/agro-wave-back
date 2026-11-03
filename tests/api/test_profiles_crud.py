"""API tests for LPWAN profiles CRUD endpoints (AC-02-04, AC-02-05, AC-02-06, AC-26, AC-27)."""

from uuid import UUID, uuid4

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from agrowave.modules.profiles.domain.ports import ProfileUsageQuery
from agrowave.modules.profiles.infrastructure.row_models import (
    ProfilesLpwanProfileRow,
)
from agrowave.modules.profiles.presentation.dependencies import set_profile_usage_query_override


def _create_authenticated_user(client: TestClient, email: str = "user@example.com") -> str:
    """Helper creating and activating a user, returning a valid Bearer JWT access token."""
    register_res = client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": email, "password": "Password123!"},
    )
    assert register_res.status_code == status.HTTP_201_CREATED

    # Query token from db or use confirm endpoint directly if we have token
    # For in-memory test, we can fetch token hash or query row from api_engine
    engine = client.app.dependency_overrides.get(list(client.app.dependency_overrides.keys())[0])()
    from agrowave.modules.identity.infrastructure.row_models import (
        IdentityUserRow,
    )

    with Session(engine) as session:
        user_row = session.query(IdentityUserRow).filter_by(email=email).one()
        user_row.email_confirmed = True
        session.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    return login_res.json()["access_token"]


class FakeProfileUsageQuery(ProfileUsageQuery):
    def __init__(self, in_use_ids: set[UUID]) -> None:
        self.in_use_ids = in_use_ids

    def is_profile_in_use(self, profile_id: UUID) -> bool:
        return profile_id in self.in_use_ids


def test_ac02_06_unauthenticated_returns_401(client: TestClient) -> None:
    """AC-02-06: Calls without a valid Bearer token respond with HTTP 401."""
    random_id = uuid4()
    assert client.get("/api/v1/profiles").status_code == status.HTTP_401_UNAUTHORIZED
    assert client.post("/api/v1/profiles", json={}).status_code == status.HTTP_401_UNAUTHORIZED
    assert (
        client.patch(f"/api/v1/profiles/{random_id}", json={}).status_code
        == status.HTTP_401_UNAUTHORIZED
    )
    assert (
        client.post(f"/api/v1/profiles/{random_id}/duplicate").status_code
        == status.HTTP_401_UNAUTHORIZED
    )
    assert (
        client.delete(f"/api/v1/profiles/{random_id}").status_code == status.HTTP_401_UNAUTHORIZED
    )


def test_ac02_04_create_own_profile(client: TestClient) -> None:
    """AC-02-04: Authenticated user creates an owned profile with HTTP 201."""
    token = _create_authenticated_user(client, "creator@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "Custom LoRaWAN Profile",
        "technology": "LORAWAN",
        "reference_sensitivity_dbm": -125.0,
        "spreading_factor": 8,
        "bands": [{"code": "902-928", "min_mhz": 902.0, "max_mhz": 928.0}],
    }
    response = client.post("/api/v1/profiles", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Custom LoRaWAN Profile"
    assert data["technology"] == "LORAWAN"
    assert data["spreading_factor"] == 8
    assert data["reference_sensitivity_dbm"] == -125.0
    assert data["is_predefined"] is False
    assert len(data["bands"]) == 1
    assert data["bands"][0]["code"] == "902-928"


def test_ac02_05_foreign_profile_returns_404(client: TestClient) -> None:
    """AC-02-05: Modifying, duplicating, or deleting another user's profile returns 404."""
    token_a = _create_authenticated_user(client, "user_a@example.com")
    token_b = _create_authenticated_user(client, "user_b@example.com")

    # User A creates a profile
    create_res = client.post(
        "/api/v1/profiles",
        json={
            "name": "User A Private Profile",
            "technology": "NB_IOT",
            "reference_sensitivity_dbm": -130.0,
            "bands": [{"code": "B1"}],
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    profile_id = create_res.json()["id"]

    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B attempts to patch
    patch_res = client.patch(
        f"/api/v1/profiles/{profile_id}",
        json={"name": "Attempt Takeover"},
        headers=headers_b,
    )
    assert patch_res.status_code == status.HTTP_404_NOT_FOUND

    # User B attempts to duplicate
    dup_res = client.post(
        f"/api/v1/profiles/{profile_id}/duplicate",
        headers=headers_b,
    )
    assert dup_res.status_code == status.HTTP_404_NOT_FOUND

    # User B attempts to delete
    del_res = client.delete(
        f"/api/v1/profiles/{profile_id}",
        headers=headers_b,
    )
    assert del_res.status_code == status.HTTP_404_NOT_FOUND


def test_ac27_predefined_profile_cannot_be_modified_or_deleted_returns_403(
    client: TestClient, api_engine
) -> None:
    """AC-27: Editing or deleting a predefined profile returns 403 PredefinedProfileReadOnly."""
    token = _create_authenticated_user(client, "regular_user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Seed one predefined profile in the test engine
    predefined_id = uuid4()
    with Session(api_engine) as session:
        session.add(
            ProfilesLpwanProfileRow(
                id=predefined_id,
                owner_id=None,
                is_predefined=True,
                name="System Predefined LoRa",
                technology="LORAWAN",
                spreading_factor=7,
                reference_sensitivity_dbm=-124.0,
            )
        )
        session.commit()

    # Attempt PATCH -> 403
    patch_res = client.patch(
        f"/api/v1/profiles/{predefined_id}",
        json={"name": "Tampered Predefined"},
        headers=headers,
    )
    assert patch_res.status_code == status.HTTP_403_FORBIDDEN
    assert patch_res.json()["code"] == "PredefinedProfileReadOnly"

    # Attempt DELETE -> 403
    del_res = client.delete(f"/api/v1/profiles/{predefined_id}", headers=headers)
    assert del_res.status_code == status.HTTP_403_FORBIDDEN
    assert del_res.json()["code"] == "PredefinedProfileReadOnly"


def test_ac27_duplicate_profile_returns_201(client: TestClient, api_engine) -> None:
    """AC-27: Duplicating a predefined profile creates an owned clone with HTTP 201."""
    token = _create_authenticated_user(client, "duplicator@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    predefined_id = uuid4()
    with Session(api_engine) as session:
        session.add(
            ProfilesLpwanProfileRow(
                id=predefined_id,
                owner_id=None,
                is_predefined=True,
                name="Predefined SF10",
                technology="LORAWAN",
                spreading_factor=10,
                reference_sensitivity_dbm=-130.0,
            )
        )
        session.commit()

    dup_res = client.post(
        f"/api/v1/profiles/{predefined_id}/duplicate",
        json={"name": "Cloned Profile"},
        headers=headers,
    )
    assert dup_res.status_code == status.HTTP_201_CREATED
    cloned_data = dup_res.json()
    assert cloned_data["id"] != str(predefined_id)
    assert cloned_data["name"] == "Cloned Profile"
    assert cloned_data["is_predefined"] is False
    assert cloned_data["technology"] == "LORAWAN"
    assert cloned_data["spreading_factor"] == 10


def test_ac26_profile_in_use_returns_409(client: TestClient) -> None:
    """AC-26: Editing or deleting a profile in use by scenarios returns 409 ResourceInUse."""
    token = _create_authenticated_user(client, "scenario_owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/api/v1/profiles",
        json={
            "name": "Profile in Use",
            "technology": "NB_IOT",
            "reference_sensitivity_dbm": -130.0,
            "bands": [],
        },
        headers=headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    profile_id = UUID(create_res.json()["id"])

    # Simulate scenario usage
    set_profile_usage_query_override(FakeProfileUsageQuery({profile_id}))

    try:
        # PATCH -> 409
        patch_res = client.patch(
            f"/api/v1/profiles/{profile_id}",
            json={"name": "Try Edit"},
            headers=headers,
        )
        assert patch_res.status_code == status.HTTP_409_CONFLICT
        assert patch_res.json()["code"] == "ResourceInUse"

        # DELETE -> 409
        del_res = client.delete(f"/api/v1/profiles/{profile_id}", headers=headers)
        assert del_res.status_code == status.HTTP_409_CONFLICT
        assert del_res.json()["code"] == "ResourceInUse"
    finally:
        set_profile_usage_query_override(None)
