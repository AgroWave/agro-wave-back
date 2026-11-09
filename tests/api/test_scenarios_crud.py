"""API tests for scenarios endpoints (AC-01..AC-14, AC-16, AC-26-SC, AC-28, AC-04-01)."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agrowave.modules.identity.infrastructure.row_models import IdentityUserRow
from agrowave.modules.profiles.infrastructure.row_models import (
    ProfilesLpwanProfileRow,
    ProfilesNodeTemplateRow,
    ProfilesProfileBandRow,
)
from agrowave.modules.terrain.domain.models import Bounds
from agrowave.modules.terrain.domain.ports import DemObjectStore, ElevationSource
from agrowave.modules.terrain.infrastructure.row_models import TerrainDemRow
from agrowave.modules.terrain.presentation.dependencies import (
    get_dem_object_store,
    get_elevation_source,
)


def _create_authenticated_user(
    client: TestClient, email: str = "scenario_user@example.com"
) -> tuple[str, UUID]:
    """Helper creating and activating a user, returning (access_token, user_id)."""
    register_res = client.post(
        "/api/v1/auth/register",
        json={"name": "Scenario User", "email": email, "password": "Password123!"},
    )
    assert register_res.status_code == status.HTTP_201_CREATED

    engine = client.app.dependency_overrides.get(list(client.app.dependency_overrides.keys())[0])()
    with Session(engine) as session:
        user_row = session.exec(select(IdentityUserRow).where(IdentityUserRow.email == email)).one()
        user_row.email_confirmed = True
        user_id = user_row.id
        session.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    return login_res.json()["access_token"], user_id


class _FakeElevationSource(ElevationSource):
    """Stub elevation source."""

    def download_and_mosaic(self, bounds: Bounds, output_cog_path: Path) -> tuple[int, float]:
        output_cog_path.touch()
        return 2048, 30.0


class _FakeDemObjectStore(DemObjectStore):
    """Stub object store."""

    def upload_file(self, key: str, file_path: Path) -> None:
        pass

    def delete_file(self, key: str) -> None:
        pass


def _seed_predefined_profiles_and_templates(engine) -> dict[str, UUID]:
    """Seeds predefined LoRaWAN and NB-IoT profiles and node templates in SQLite."""
    lora_id = uuid4()
    nbiot_id = uuid4()
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(
            ProfilesLpwanProfileRow(
                id=lora_id,
                owner_id=None,
                is_predefined=True,
                name="LoRaWAN SF12",
                technology="LORAWAN",
                spreading_factor=12,
                reference_sensitivity_dbm=-137.0,
                created_at=now,
            )
        )
        session.add(
            ProfilesProfileBandRow(
                id=uuid4(),
                profile_id=lora_id,
                code="US915",
                min_mhz=902.0,
                max_mhz=928.0,
            )
        )
        session.add(
            ProfilesLpwanProfileRow(
                id=nbiot_id,
                owner_id=None,
                is_predefined=True,
                name="NB-IoT Cat-NB1",
                technology="NB_IOT",
                spreading_factor=None,
                reference_sensitivity_dbm=-141.0,
                created_at=now,
            )
        )
        session.add(
            ProfilesProfileBandRow(
                id=uuid4(),
                profile_id=nbiot_id,
                code="B28",
                min_mhz=703.0,
                max_mhz=748.0,
            )
        )
        session.add(
            ProfilesNodeTemplateRow(
                id=uuid4(),
                technology="NB_IOT",
                role="END_NODE",
                name="Quectel BG95",
                module_ref="BG95-M3",
                antenna_ref="Taoglas FXP611",
                antenna_gain_dbi=2.1,
                polarization="VERTICAL",
                tx_power_nominal_dbm=23.0,
                tx_power_tolerance_db=2.0,
            )
        )
        session.add(
            ProfilesNodeTemplateRow(
                id=uuid4(),
                technology="NB_IOT",
                role="ACCESS_NODE",
                name="Estación Base NB-IoT",
                module_ref="3GPP Rel-13",
                antenna_ref="Sectorial",
                antenna_gain_dbi=None,
                polarization="VERTICAL",
                tx_power_nominal_dbm=None,
                tx_power_tolerance_db=None,
            )
        )
        session.commit()
    return {"LORAWAN": lora_id, "NB_IOT": nbiot_id}


def _seed_dem(
    engine,
    owner_id: UUID,
    status_str: str = "AVAILABLE",
    south: float = 4.55,
    west: float = -74.15,
    north: float = 4.70,
    east: float = -74.00,
) -> UUID:
    """Seeds a DEM row directly in the test database."""
    dem_id = uuid4()
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(
            TerrainDemRow(
                id=dem_id,
                owner_id=owner_id,
                name="Cundinamarca DEM",
                description="Test DEM",
                south=south,
                west=west,
                north=north,
                east=east,
                status=status_str,
                resolution_m=30.0,
                object_key=f"dems/{dem_id}/fabdem.tif" if status_str == "AVAILABLE" else None,
                size_bytes=2048 if status_str == "AVAILABLE" else None,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    return dem_id


def test_ac01_ac02_ac03_study_area_validation(client: TestClient) -> None:
    """AC-01..AC-03: Study area validation inside Colombia and >= 1.5 km."""
    token, _ = _create_authenticated_user(client, "area@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # AC-01: Valid area >= 1.5 km inside Colombia
    valid_res = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Sabana Valida",
            "bounds": {"south": 4.58, "west": -74.12, "north": 4.64, "east": -74.06},
        },
        headers=headers,
    )
    assert valid_res.status_code == status.HTTP_201_CREATED
    assert valid_res.json()["name"] == "Sabana Valida"

    # AC-02: Area smaller than 1.5 km per side -> 422 AreaTooSmall
    small_res = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Finca Pequena",
            "bounds": {"south": 4.600, "west": -74.100, "north": 4.605, "east": -74.095},
        },
        headers=headers,
    )
    assert small_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert small_res.json()["code"] == "AreaTooSmall"

    # AC-03: Area outside continental Colombia -> 422 AreaOutsideColombia
    outside_res = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Fuera de Colombia",
            "bounds": {"south": -34.65, "west": -58.45, "north": -34.55, "east": -58.35},
        },
        headers=headers,
    )
    assert outside_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert outside_res.json()["code"] == "AreaOutsideColombia"


def test_ac04_redefine_area_excluding_nodes_rejected(client: TestClient) -> None:
    """AC-04 (RN-14): Redefining study area excluding nodes returns 422."""
    token, _ = _create_authenticated_user(client, "ac04@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    access_id = str(uuid4())
    end_id = str(uuid4())
    create_res = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Con Nodos",
            "bounds": {"south": 4.58, "west": -74.12, "north": 4.66, "east": -74.04},
            "access_nodes": [
                {
                    "id": access_id,
                    "name": "Gateway Norte",
                    "lat": 4.65,
                    "lng": -74.05,
                    "height_agl_m": 15.0,
                    "antenna_gain_dbi": 5.5,
                    "sensitivity_dbm": -137.0,
                }
            ],
            "end_nodes": [
                {
                    "id": end_id,
                    "name": "Sensor Sur",
                    "lat": 4.60,
                    "lng": -74.10,
                    "height_agl_m": 2.0,
                    "antenna_gain_dbi": 1.1,
                    "tx_power_nominal_dbm": 20.0,
                }
            ],
            "links": [{"end_node_id": end_id, "access_node_id": access_id}],
        },
        headers=headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    scenario_id = create_res.json()["id"]

    # Shrink north boundary to 4.63 so Gateway Norte (lat=4.65) falls outside
    update_res = client.put(
        f"/api/v1/scenarios/{scenario_id}",
        json={
            "name": "Con Nodos",
            "bounds": {"south": 4.58, "west": -74.12, "north": 4.63, "east": -74.04},
            "access_nodes": create_res.json()["access_nodes"],
            "end_nodes": create_res.json()["end_nodes"],
            "links": create_res.json()["links"],
        },
        headers=headers,
    )
    assert update_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert update_res.json()["code"] == "AreaWouldExcludeNodes"
    assert "Gateway Norte" in update_res.json()["details"]["excluded_nodes"]


def test_ac05_assign_dem_coverage_validation(client: TestClient, api_engine) -> None:
    """AC-05 (RN-26, RN-27): Assigning a covering DEM succeeds; non-covering fails."""
    token, user_id = _create_authenticated_user(client, "ac05@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    covering_dem_id = _seed_dem(
        api_engine, user_id, south=4.55, west=-74.15, north=4.70, east=-74.00
    )
    small_dem_id = _seed_dem(api_engine, user_id, south=4.60, west=-74.10, north=4.62, east=-74.08)

    ok_res = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Con DEM Cobertura",
            "bounds": {"south": 4.58, "west": -74.12, "north": 4.64, "east": -74.06},
            "dem_id": str(covering_dem_id),
        },
        headers=headers,
    )
    assert ok_res.status_code == status.HTTP_201_CREATED
    assert ok_res.json()["terrain_ref"]["dem_id"] == str(covering_dem_id)
    assert ok_res.json()["terrain_ref"]["window"] == {
        "south": 4.58,
        "west": -74.12,
        "north": 4.64,
        "east": -74.06,
    }

    fail_res = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Sin Cobertura",
            "bounds": {"south": 4.58, "west": -74.12, "north": 4.64, "east": -74.06},
            "dem_id": str(small_dem_id),
        },
        headers=headers,
    )
    assert fail_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert fail_res.json()["code"] == "DemDoesNotCoverArea"


def test_ac07_assign_downloading_dem_to_scenario(client: TestClient, api_engine) -> None:
    """AC-07 (RF-008): Assigning a DOWNLOADING DEM succeeds without blocking scenario edition."""
    token, user_id = _create_authenticated_user(client, "ac07@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    downloading_dem_id = _seed_dem(api_engine, user_id, status_str="DOWNLOADING")

    res = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Con DEM Descargando",
            "bounds": {"south": 4.58, "west": -74.12, "north": 4.64, "east": -74.06},
            "dem_id": str(downloading_dem_id),
        },
        headers=headers,
    )
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["terrain_ref"]["dem_id"] == str(downloading_dem_id)


def test_ac08_to_ac12_deployment_and_radio_invariants(client: TestClient, api_engine) -> None:
    """AC-08..AC-12: Deployment and radio frequency invariants."""
    token, _ = _create_authenticated_user(client, "invariants@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    profiles = _seed_predefined_profiles_and_templates(api_engine)
    lora_id = str(profiles["LORAWAN"])

    base_bounds = {"south": 4.58, "west": -74.12, "north": 4.66, "east": -74.04}
    an_id = str(uuid4())
    en1_id = str(uuid4())

    # AC-08: EndNode in two links -> 422 EndNodeAlreadyLinked
    an2_id = str(uuid4())
    res_ac08 = client.post(
        "/api/v1/scenarios",
        json={
            "name": "AC08",
            "bounds": base_bounds,
            "access_nodes": [
                {
                    "id": an_id,
                    "name": "GW-1",
                    "lat": 4.60,
                    "lng": -74.10,
                    "height_agl_m": 15.0,
                    "antenna_gain_dbi": 5.5,
                    "sensitivity_dbm": -137.0,
                },
                {
                    "id": an2_id,
                    "name": "GW-2",
                    "lat": 4.64,
                    "lng": -74.06,
                    "height_agl_m": 15.0,
                    "antenna_gain_dbi": 5.5,
                    "sensitivity_dbm": -137.0,
                },
            ],
            "end_nodes": [
                {
                    "id": en1_id,
                    "name": "Sensor-1",
                    "lat": 4.62,
                    "lng": -74.08,
                    "height_agl_m": 2.0,
                    "antenna_gain_dbi": 1.1,
                    "tx_power_nominal_dbm": 20.0,
                }
            ],
            "links": [
                {"end_node_id": en1_id, "access_node_id": an_id},
                {"end_node_id": en1_id, "access_node_id": an2_id},
            ],
        },
        headers=headers,
    )
    assert res_ac08.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert res_ac08.json()["code"] == "EndNodeAlreadyLinked"

    # AC-09: Link shorter than 1.0 km -> 422 LinkTooShort
    res_ac09 = client.post(
        "/api/v1/scenarios",
        json={
            "name": "AC09",
            "bounds": base_bounds,
            "access_nodes": [
                {
                    "id": an_id,
                    "name": "GW-1",
                    "lat": 4.600,
                    "lng": -74.100,
                    "height_agl_m": 15.0,
                    "antenna_gain_dbi": 5.5,
                    "sensitivity_dbm": -137.0,
                }
            ],
            "end_nodes": [
                {
                    "id": en1_id,
                    "name": "Sensor-1",
                    "lat": 4.602,
                    "lng": -74.099,
                    "height_agl_m": 2.0,
                    "antenna_gain_dbi": 1.1,
                    "tx_power_nominal_dbm": 20.0,
                }
            ],
            "links": [{"end_node_id": en1_id, "access_node_id": an_id}],
        },
        headers=headers,
    )
    assert res_ac09.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert res_ac09.json()["code"] == "LinkTooShort"

    # AC-10: Height below 0.5 m -> 422 HeightBelowMinimum
    res_ac10 = client.post(
        "/api/v1/scenarios",
        json={
            "name": "AC10",
            "bounds": base_bounds,
            "access_nodes": [
                {
                    "id": an_id,
                    "name": "GW-1",
                    "lat": 4.60,
                    "lng": -74.10,
                    "height_agl_m": 0.2,
                    "antenna_gain_dbi": 5.5,
                    "sensitivity_dbm": -137.0,
                }
            ],
            "end_nodes": [
                {
                    "id": en1_id,
                    "name": "Sensor-1",
                    "lat": 4.63,
                    "lng": -74.07,
                    "height_agl_m": 2.0,
                    "antenna_gain_dbi": 1.1,
                    "tx_power_nominal_dbm": 20.0,
                }
            ],
            "links": [{"end_node_id": en1_id, "access_node_id": an_id}],
        },
        headers=headers,
    )
    assert res_ac10.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert res_ac10.json()["code"] == "HeightBelowMinimum"

    # AC-11: Node outside study area -> 422 NodeOutsideArea
    res_ac11 = client.post(
        "/api/v1/scenarios",
        json={
            "name": "AC11",
            "bounds": base_bounds,
            "access_nodes": [
                {
                    "id": an_id,
                    "name": "GW-1",
                    "lat": 4.60,
                    "lng": -74.10,
                    "height_agl_m": 15.0,
                    "antenna_gain_dbi": 5.5,
                    "sensitivity_dbm": -137.0,
                }
            ],
            "end_nodes": [
                {
                    "id": en1_id,
                    "name": "Sensor Outside",
                    "lat": 4.70,
                    "lng": -74.00,
                    "height_agl_m": 2.0,
                    "antenna_gain_dbi": 1.1,
                    "tx_power_nominal_dbm": 20.0,
                }
            ],
            "links": [{"end_node_id": en1_id, "access_node_id": an_id}],
        },
        headers=headers,
    )
    assert res_ac11.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert res_ac11.json()["code"] == "NodeOutsideArea"

    # AC-12: Frequency outside profile band (868 MHz on US915) -> 422 FrequencyOutOfProfile
    res_ac12 = client.post(
        "/api/v1/scenarios",
        json={
            "name": "AC12",
            "bounds": base_bounds,
            "profile_id": lora_id,
            "band_code": "US915",
            "frequency_mhz": 868.0,
        },
        headers=headers,
    )
    assert res_ac12.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert res_ac12.json()["code"] == "FrequencyOutOfProfile"


def test_ac14_and_ac16_variants_and_validate_endpoint(client: TestClient, api_engine) -> None:
    """AC-14 & AC-16: Creating variant shares comparison_group_id; validate checks DEM."""
    token, user_id = _create_authenticated_user(client, "variant@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    profiles = _seed_predefined_profiles_and_templates(api_engine)
    pending_dem_id = _seed_dem(api_engine, user_id, status_str="DOWNLOADING")
    available_dem_id = _seed_dem(api_engine, user_id, status_str="AVAILABLE")

    an_id = str(uuid4())
    en_id = str(uuid4())
    create_res = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Escenario LoRaWAN",
            "description": "Base para variantes",
            "bounds": {"south": 4.58, "west": -74.12, "north": 4.66, "east": -74.04},
            "dem_id": str(pending_dem_id),
            "profile_id": str(profiles["LORAWAN"]),
            "band_code": "US915",
            "frequency_mhz": 915.0,
            "access_nodes": [
                {
                    "id": an_id,
                    "name": "GW-1",
                    "lat": 4.60,
                    "lng": -74.10,
                    "height_agl_m": 15.0,
                    "antenna_ref": "Dragino",
                    "antenna_gain_dbi": 5.5,
                    "polarization": "VERTICAL",
                    "sensitivity_dbm": -137.0,
                    "sensitivity_origin": "REFERENCE_TO_VERIFY",
                }
            ],
            "end_nodes": [
                {
                    "id": en_id,
                    "name": "Sensor-1",
                    "lat": 4.63,
                    "lng": -74.07,
                    "height_agl_m": 2.0,
                    "antenna_ref": "Taoglas",
                    "antenna_gain_dbi": 1.1,
                    "polarization": "VERTICAL",
                    "tx_power_nominal_dbm": 20.0,
                    "tx_power_tolerance_db": 1.5,
                }
            ],
            "links": [{"end_node_id": en_id, "access_node_id": an_id}],
            "propagation_setup": {
                "model_id": "LONGLEY_RICE",
                "schema_version": 1,
                "parameters": {
                    "ens0": 314.0,
                    "ipol": 1,
                    "eps": 15.0,
                    "sgm": 0.005,
                    "klim": 5,
                    "mdvar": 11,
                    "qc": 50.0,
                    "qr": [10.0, 50.0, 90.0],
                },
            },
        },
        headers=headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    base_data = create_res.json()
    scenario_id = base_data["id"]

    # AC-16: Validate while DEM is PENDING -> simulable=False with DemNotAvailable
    val_pending = client.post(f"/api/v1/scenarios/{scenario_id}/validate", headers=headers)
    assert val_pending.status_code == status.HTTP_200_OK
    assert val_pending.json()["simulable"] is False
    assert any(c["code"] == "DemNotAvailable" for c in val_pending.json()["causes"])

    # Update to AVAILABLE DEM and re-validate -> simulable=True
    put_payload = dict(base_data)
    put_payload["dem_id"] = str(available_dem_id)
    put_payload["profile_id"] = str(profiles["LORAWAN"])
    put_payload["band_code"] = "US915"
    put_payload["frequency_mhz"] = 915.0
    put_res = client.put(f"/api/v1/scenarios/{scenario_id}", json=put_payload, headers=headers)
    assert put_res.status_code == status.HTTP_200_OK

    val_ok = client.post(f"/api/v1/scenarios/{scenario_id}/validate", headers=headers)
    assert val_ok.status_code == status.HTTP_200_OK
    assert val_ok.json()["simulable"] is True
    assert val_ok.json()["causes"] == []

    # AC-14: Create NB-IoT variant -> shares comparison_group_id
    var_res = client.post(
        f"/api/v1/scenarios/{scenario_id}/variants",
        json={
            "target_profile_id": str(profiles["NB_IOT"]),
            "band_code": "B28",
            "frequency_mhz": 725.0,
            "name": "Escenario NB-IoT",
        },
        headers=headers,
    )
    assert var_res.status_code == status.HTTP_201_CREATED
    var_data = var_res.json()
    assert var_data["id"] != scenario_id
    assert var_data["comparison_group_id"] == base_data["comparison_group_id"]
    assert var_data["radio_config"]["technology"] == "NB_IOT"
    assert var_data["access_nodes"][0]["sensitivity_dbm"] == -141.0
    assert var_data["end_nodes"][0]["tx_power_nominal_dbm"] == 23.0


def test_ac26_sc_and_ac28_and_ac04_01_resource_in_use_and_foreign_isolation(
    client: TestClient, api_engine
) -> None:
    """AC-26-SC, AC-28, AC-04-01: ResourceInUse (409) and foreign isolation (404)."""
    token1, user1_id = _create_authenticated_user(client, "owner_sc@example.com")
    token2, _ = _create_authenticated_user(client, "other_sc@example.com")
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    client.app.dependency_overrides[get_elevation_source] = lambda: _FakeElevationSource()
    client.app.dependency_overrides[get_dem_object_store] = lambda: _FakeDemObjectStore()

    # Create a custom profile owned by user 1
    prof_res = client.post(
        "/api/v1/profiles",
        json={
            "name": "Custom LoRa Profile",
            "technology": "LORAWAN",
            "reference_sensitivity_dbm": -135.0,
            "spreading_factor": 10,
            "bands": [{"code": "US915", "min_mhz": 902.0, "max_mhz": 928.0}],
        },
        headers=headers1,
    )
    assert prof_res.status_code == status.HTTP_201_CREATED
    custom_prof_id = prof_res.json()["id"]

    # Seed an available DEM owned by user 1
    dem_id = _seed_dem(api_engine, user1_id, status_str="AVAILABLE")

    # Create a scenario using both custom_prof_id and dem_id
    sc_res = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Active Scenario",
            "bounds": {"south": 4.58, "west": -74.12, "north": 4.64, "east": -74.06},
            "dem_id": str(dem_id),
            "profile_id": custom_prof_id,
            "band_code": "US915",
            "frequency_mhz": 915.0,
        },
        headers=headers1,
    )
    assert sc_res.status_code == status.HTTP_201_CREATED
    scenario_id = sc_res.json()["id"]

    # AC-04-01: User 2 cannot access, update, or delete User 1's scenario (404)
    assert client.get(f"/api/v1/scenarios/{scenario_id}", headers=headers2).status_code == 404
    assert client.delete(f"/api/v1/scenarios/{scenario_id}", headers=headers2).status_code == 404

    # AC-26-SC (RN-09): Editing or deleting custom_prof_id while in use returns 409 ResourceInUse
    patch_prof = client.patch(
        f"/api/v1/profiles/{custom_prof_id}",
        json={"name": "Renamed"},
        headers=headers1,
    )
    assert patch_prof.status_code == status.HTTP_409_CONFLICT
    assert patch_prof.json()["code"] == "ResourceInUse"

    del_prof = client.delete(f"/api/v1/profiles/{custom_prof_id}", headers=headers1)
    assert del_prof.status_code == status.HTTP_409_CONFLICT
    assert del_prof.json()["code"] == "ResourceInUse"

    # AC-28 (RN-28): Deleting dem_id while in use returns 409 ResourceInUse
    del_dem = client.delete(f"/api/v1/dems/{dem_id}", headers=headers1)
    assert del_dem.status_code == status.HTTP_409_CONFLICT
    assert del_dem.json()["code"] == "ResourceInUse"

    # RN-30: Deleting the scenario frees both the profile and the DEM without deleting them
    del_sc = client.delete(f"/api/v1/scenarios/{scenario_id}", headers=headers1)
    assert del_sc.status_code == status.HTTP_204_NO_CONTENT

    # Now DEM and Profile still exist and can be deleted cleanly
    assert client.get(f"/api/v1/dems/{dem_id}", headers=headers1).status_code == 200
    assert client.delete(f"/api/v1/dems/{dem_id}", headers=headers1).status_code == 204
    assert client.delete(f"/api/v1/profiles/{custom_prof_id}", headers=headers1).status_code == 204
