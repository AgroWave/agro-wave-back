"""API tests for DEM terrain endpoints (AC-03-01 to AC-03-11)."""

from pathlib import Path
from uuid import UUID

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from agrowave.modules.identity.infrastructure.row_models import IdentityUserRow
from agrowave.modules.terrain.domain.models import Bounds
from agrowave.modules.terrain.domain.ports import (
    DemObjectStore,
    DemUsageQuery,
    ElevationSource,
)
from agrowave.modules.terrain.presentation.dependencies import (
    get_dem_object_store,
    get_dem_usage_query,
    get_elevation_source,
)


def _create_authenticated_user(client: TestClient, email: str = "dem_user@example.com") -> str:
    """Helper creating and activating a user, returning a Bearer JWT access token."""
    register_res = client.post(
        "/api/v1/auth/register",
        json={"name": "DEM User", "email": email, "password": "Password123!"},
    )
    assert register_res.status_code == status.HTTP_201_CREATED

    engine = client.app.dependency_overrides.get(list(client.app.dependency_overrides.keys())[0])()
    from sqlmodel import select

    with Session(engine) as session:
        user_row = session.exec(select(IdentityUserRow).where(IdentityUserRow.email == email)).one()
        user_row.email_confirmed = True
        session.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    return login_res.json()["access_token"]


class FakeElevationSource(ElevationSource):
    """Stub elevation source."""

    def download_and_mosaic(self, bounds: Bounds, output_cog_path: Path) -> tuple[int, float]:
        output_cog_path.touch()
        return 2048, 30.0


class FakeDemObjectStore(DemObjectStore):
    """Stub object store tracking files in memory."""

    def __init__(self) -> None:
        self.files: set[str] = set()

    def upload_file(self, key: str, file_path: Path) -> None:
        self.files.add(key)

    def delete_file(self, key: str) -> None:
        self.files.discard(key)


class FakeDemUsageQuery(DemUsageQuery):
    """Stub DEM usage query."""

    def __init__(self, in_use_ids: set[UUID] | None = None) -> None:
        self.in_use_ids = in_use_ids or set()

    def is_dem_in_use(self, dem_id: UUID) -> bool:
        return dem_id in self.in_use_ids


def test_ac03_01_request_dem_download_returns_202(client: TestClient) -> None:
    """AC-03-01: Valid request returns 202 Accepted and creates DEM in DOWNLOADING status."""
    token = _create_authenticated_user(client, "ac01@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.app.dependency_overrides[get_elevation_source] = lambda: FakeElevationSource()
    client.app.dependency_overrides[get_dem_object_store] = lambda: FakeDemObjectStore()

    payload = {
        "name": "Sabana Centro",
        "description": "Cultivos de flores en Cundinamarca",
        "bounds": {
            "south": 4.85,
            "west": -74.05,
            "north": 4.95,
            "east": -73.95,
        },
    }
    response = client.post("/api/v1/dems", json=payload, headers=headers)
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["name"] == "Sabana Centro"
    assert data["status"] == "DOWNLOADING"
    assert data["resolution_m"] == 30.0
    assert "id" in data


def test_ac03_02_area_outside_colombia_rejected(client: TestClient) -> None:
    """AC-03-02: (RN-12) Area outside continental Colombia returns 422 AreaOutsideColombia."""
    token = _create_authenticated_user(client, "ac02@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Bounding box in Paris, France
    payload = {
        "name": "Paris Test",
        "bounds": {
            "south": 48.85,
            "west": 2.30,
            "north": 48.90,
            "east": 2.35,
        },
    }
    response = client.post("/api/v1/dems", json=payload, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "AreaOutsideColombia"


def test_ac03_03_area_too_small_rejected(client: TestClient) -> None:
    """AC-03-03: (RN-13) Area smaller than 1.5 km per side returns 422 AreaTooSmall."""
    token = _create_authenticated_user(client, "ac03@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Bounding box smaller than 1.5 km (~100m)
    payload = {
        "name": "Tiny Box",
        "bounds": {
            "south": 4.600,
            "west": -74.100,
            "north": 4.601,
            "east": -74.099,
        },
    }
    response = client.post("/api/v1/dems", json=payload, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "AreaTooSmall"


def test_ac03_04_invalid_bounds_rejected(client: TestClient) -> None:
    """AC-03-04: South >= North returns 422 InvalidBounds."""
    token = _create_authenticated_user(client, "ac04@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "Inverted Coordinates",
        "bounds": {
            "south": 5.0,
            "west": -74.0,
            "north": 4.0,
            "east": -73.0,
        },
    }
    response = client.post("/api/v1/dems", json=payload, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "InvalidBounds"


def test_ac03_07_list_dems(client: TestClient) -> None:
    """AC-03-07: Listing DEMs returns only user-owned DEMs and supports search filter."""
    token1 = _create_authenticated_user(client, "user1@example.com")
    token2 = _create_authenticated_user(client, "user2@example.com")
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    client.app.dependency_overrides[get_elevation_source] = lambda: FakeElevationSource()
    client.app.dependency_overrides[get_dem_object_store] = lambda: FakeDemObjectStore()

    # Create 2 DEMs for user1
    client.post(
        "/api/v1/dems",
        json={
            "name": "Boyaca Altiplano",
            "bounds": {"south": 5.5, "west": -73.4, "north": 5.6, "east": -73.3},
        },
        headers=headers1,
    )
    client.post(
        "/api/v1/dems",
        json={
            "name": "Valle del Cauca",
            "bounds": {"south": 3.4, "west": -76.5, "north": 3.5, "east": -76.4},
        },
        headers=headers1,
    )

    # Create 1 DEM for user2
    client.post(
        "/api/v1/dems",
        json={
            "name": "User2 DEM",
            "bounds": {"south": 5.5, "west": -73.4, "north": 5.6, "east": -73.3},
        },
        headers=headers2,
    )

    # User 1 lists DEMs
    res1 = client.get("/api/v1/dems", headers=headers1)
    assert res1.status_code == status.HTTP_200_OK
    items = res1.json()
    assert len(items) == 2
    assert {i["name"] for i in items} == {"Boyaca Altiplano", "Valle del Cauca"}

    # Search filter
    search_res = client.get("/api/v1/dems?search=Boyaca", headers=headers1)
    assert search_res.status_code == status.HTTP_200_OK
    filtered = search_res.json()
    assert len(filtered) == 1
    assert filtered[0]["name"] == "Boyaca Altiplano"


def test_ac03_08_get_and_update_dem(client: TestClient) -> None:
    """AC-03-08: Get and update DEM metadata."""
    token = _create_authenticated_user(client, "update_dem@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.app.dependency_overrides[get_elevation_source] = lambda: FakeElevationSource()
    client.app.dependency_overrides[get_dem_object_store] = lambda: FakeDemObjectStore()

    create_res = client.post(
        "/api/v1/dems",
        json={
            "name": "Original Name",
            "description": "Original description",
            "bounds": {"south": 4.85, "west": -74.05, "north": 4.95, "east": -73.95},
        },
        headers=headers,
    )
    dem_id = create_res.json()["id"]

    # Get DEM
    get_res = client.get(f"/api/v1/dems/{dem_id}", headers=headers)
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["name"] == "Original Name"

    # Update DEM
    patch_res = client.patch(
        f"/api/v1/dems/{dem_id}",
        json={"name": "Updated Name", "description": "Updated description"},
        headers=headers,
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["name"] == "Updated Name"
    assert patch_res.json()["description"] == "Updated description"


def test_ac03_09_delete_dem(client: TestClient) -> None:
    """AC-03-09: Delete DEM returns 204 and removes DEM."""
    token = _create_authenticated_user(client, "delete_dem@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    fake_store = FakeDemObjectStore()
    client.app.dependency_overrides[get_elevation_source] = lambda: FakeElevationSource()
    client.app.dependency_overrides[get_dem_object_store] = lambda: fake_store

    create_res = client.post(
        "/api/v1/dems",
        json={
            "name": "DEM to Delete",
            "bounds": {"south": 4.85, "west": -74.05, "north": 4.95, "east": -73.95},
        },
        headers=headers,
    )
    dem_id = create_res.json()["id"]

    del_res = client.delete(f"/api/v1/dems/{dem_id}", headers=headers)
    assert del_res.status_code == status.HTTP_204_NO_CONTENT

    # Verify not found afterwards
    get_res = client.get(f"/api/v1/dems/{dem_id}", headers=headers)
    assert get_res.status_code == status.HTTP_404_NOT_FOUND


def test_ac03_09_delete_dem_in_use_rejected(client: TestClient) -> None:
    """AC-03-09: (RN-28) Deleting DEM in use by scenarios returns 409 ResourceInUse."""
    token = _create_authenticated_user(client, "in_use@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.app.dependency_overrides[get_elevation_source] = lambda: FakeElevationSource()
    client.app.dependency_overrides[get_dem_object_store] = lambda: FakeDemObjectStore()

    create_res = client.post(
        "/api/v1/dems",
        json={
            "name": "In Use DEM",
            "bounds": {"south": 4.85, "west": -74.05, "north": 4.95, "east": -73.95},
        },
        headers=headers,
    )
    dem_id = UUID(create_res.json()["id"])

    # Override usage query to simulate DEM in use
    client.app.dependency_overrides[get_dem_usage_query] = lambda: FakeDemUsageQuery(
        in_use_ids={dem_id}
    )

    del_res = client.delete(f"/api/v1/dems/{dem_id}", headers=headers)
    assert del_res.status_code == status.HTTP_409_CONFLICT
    assert del_res.json()["code"] == "ResourceInUse"


def test_ac03_11_foreign_dem_isolation(client: TestClient) -> None:
    """AC-03-11: Attempting to access or mutate another user's DEM returns 404."""
    token1 = _create_authenticated_user(client, "owner@example.com")
    token2 = _create_authenticated_user(client, "intruder@example.com")
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    client.app.dependency_overrides[get_elevation_source] = lambda: FakeElevationSource()
    client.app.dependency_overrides[get_dem_object_store] = lambda: FakeDemObjectStore()

    create_res = client.post(
        "/api/v1/dems",
        json={
            "name": "Private DEM",
            "bounds": {"south": 4.85, "west": -74.05, "north": 4.95, "east": -73.95},
        },
        headers=headers1,
    )
    dem_id = create_res.json()["id"]

    # Intruder GET
    res_get = client.get(f"/api/v1/dems/{dem_id}", headers=headers2)
    assert res_get.status_code == status.HTTP_404_NOT_FOUND

    # Intruder PATCH
    res_patch = client.patch(
        f"/api/v1/dems/{dem_id}",
        json={"name": "Hacked"},
        headers=headers2,
    )
    assert res_patch.status_code == status.HTTP_404_NOT_FOUND

    # Intruder DELETE
    res_del = client.delete(f"/api/v1/dems/{dem_id}", headers=headers2)
    assert res_del.status_code == status.HTTP_404_NOT_FOUND
