"""API tests for simulations endpoints (AC-15..AC-25, AC-05-01)."""

from datetime import UTC, datetime
from typing import Any
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
from agrowave.modules.simulation.domain.models import (
    PathLossQuantile,
    SimulationStatus,
)
from agrowave.modules.simulation.domain.ports import (
    EngineEvaluationResult,
    SampledTerrainProfile,
)
from agrowave.modules.simulation.infrastructure.row_models import SimulationSimulationRow
from agrowave.modules.simulation.presentation.dependencies import (
    get_propagation_engine,
    get_terrain_profile_provider,
)
from agrowave.modules.terrain.infrastructure.row_models import TerrainDemRow


def _create_authenticated_user(
    client: TestClient, email: str = "sim_user@example.com"
) -> tuple[str, UUID]:
    """Helper creating and activating a user, returning (access_token, user_id)."""
    register_res = client.post(
        "/api/v1/auth/register",
        json={"name": "Simulation User", "email": email, "password": "Password123!"},
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


class _FakeTerrainProfileProvider:
    """Deterministic terrain profile provider for API tests."""

    def extract_profile(
        self,
        dem_id: UUID,
        dem_object_key: str | None,
        window_bounds: dict[str, float],
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        distance_m: float,
        resolution_m: float = 30.0,
    ) -> SampledTerrainProfile:
        return SampledTerrainProfile(
            distances_m=(0.0, distance_m / 2.0, distance_m),
            elevations_m=(2600.0, 2602.0, 2605.0),
            step_m=distance_m / 2.0,
        )


class _FakePropagationEngine:
    """Deterministic propagation engine returning La Calera-like quantiles and KWX warning."""

    def evaluate_link(
        self,
        profile: SampledTerrainProfile,
        frequency_mhz: float,
        tx_height_agl_m: float,
        rx_height_agl_m: float,
        polarization: str,
        propagation_params: dict[str, Any],
    ) -> EngineEvaluationResult:
        return EngineEvaluationResult(
            quantiles=(
                PathLossQuantile(reliability_pct=10.0, confidence_pct=50.0, loss_db=138.0),
                PathLossQuantile(reliability_pct=50.0, confidence_pct=50.0, loss_db=142.13),
                PathLossQuantile(reliability_pct=90.0, confidence_pct=50.0, loss_db=146.5),
            ),
            warnings=(("KWX_4", "Parámetros fuera del rango exacto de Longley-Rice (kwx=4)."),),
        )


def _seed_profiles_and_dem(
    engine, owner_id: UUID, dem_status: str = "AVAILABLE"
) -> dict[str, UUID]:
    """Seeds predefined LoRaWAN and LTE-M profiles, templates, and a DEM."""
    lora_id = uuid4()
    ltem_id = uuid4()
    dem_id = uuid4()
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
                code="AU915",
                min_mhz=902.0,
                max_mhz=928.0,
            )
        )
        session.add(
            ProfilesNodeTemplateRow(
                id=uuid4(),
                technology="LORAWAN",
                role="END_NODE",
                name="Heltec WiFi LoRa V3",
                module_ref="Heltec V3",
                antenna_ref="LoRa U.FL IP-EX",
                antenna_gain_dbi=2.0,
                polarization="VERTICAL",
                tx_power_nominal_dbm=21.0,
                tx_power_tolerance_db=1.0,
            )
        )
        session.add(
            ProfilesNodeTemplateRow(
                id=uuid4(),
                technology="LORAWAN",
                role="ACCESS_NODE",
                name="Dragino DLOS8N",
                module_ref="DLOS8N",
                antenna_ref="Omni 3dBi",
                antenna_gain_dbi=3.0,
                polarization="VERTICAL",
                tx_power_nominal_dbm=None,
                tx_power_tolerance_db=None,
            )
        )

        session.add(
            ProfilesLpwanProfileRow(
                id=ltem_id,
                owner_id=None,
                is_predefined=True,
                name="LTE-M",
                technology="LTE_M",
                spreading_factor=None,
                reference_sensitivity_dbm=-130.0,
                created_at=now,
            )
        )
        session.add(
            ProfilesProfileBandRow(
                id=uuid4(),
                profile_id=ltem_id,
                code="B28",
                min_mhz=None,
                max_mhz=None,
            )
        )
        session.add(
            ProfilesNodeTemplateRow(
                id=uuid4(),
                technology="LTE_M",
                role="END_NODE",
                name="T-SIM7070G",
                module_ref="SIM7070G",
                antenna_ref=None,
                antenna_gain_dbi=5.0,
                polarization="VERTICAL",
                tx_power_nominal_dbm=20.0,
                tx_power_tolerance_db=2.7,
            )
        )
        session.add(
            ProfilesNodeTemplateRow(
                id=uuid4(),
                technology="LTE_M",
                role="ACCESS_NODE",
                name="Base Station LTE-M",
                module_ref=None,
                antenna_ref=None,
                antenna_gain_dbi=None,
                polarization="VERTICAL",
                tx_power_nominal_dbm=None,
                tx_power_tolerance_db=None,
            )
        )

        session.add(
            TerrainDemRow(
                id=dem_id,
                owner_id=owner_id,
                name="DEM Calera",
                description="Terreno de prueba",
                south=4.60,
                west=-74.10,
                north=4.80,
                east=-73.90,
                status=dem_status,
                resolution_m=30.0,
                object_key=f"dems/{owner_id}/{dem_id}.tif" if dem_status == "AVAILABLE" else None,
                size_bytes=4096 if dem_status == "AVAILABLE" else None,
                failure_reason=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    return {"lora_id": lora_id, "ltem_id": ltem_id, "dem_id": dem_id}


def _create_valid_scenario(
    client: TestClient,
    headers: dict[str, str],
    dem_id: UUID,
    profile_id: UUID,
    name: str = "Escenario Calera",
) -> dict[str, Any]:
    """Creates a complete simulable scenario via the API."""
    an_id = str(uuid4())
    en_id = str(uuid4())
    res = client.post(
        "/api/v1/scenarios",
        headers=headers,
        json={
            "name": name,
            "description": "Escenario completo",
            "bounds": {"south": 4.65, "west": -74.02, "north": 4.70, "east": -73.97},
            "dem_id": str(dem_id),
            "profile_id": str(profile_id),
            "band_code": "AU915",
            "frequency_mhz": 915.0,
            "access_nodes": [
                {
                    "id": an_id,
                    "name": "GW-1",
                    "lat": 4.66,
                    "lng": -74.00,
                    "height_agl_m": 6.0,
                    "antenna_ref": "Omni 3dBi",
                    "antenna_gain_dbi": 3.0,
                    "polarization": "VERTICAL",
                    "sensitivity_dbm": -137.0,
                    "sensitivity_origin": "REFERENCE_TO_VERIFY",
                }
            ],
            "end_nodes": [
                {
                    "id": en_id,
                    "name": "EN-1",
                    "lat": 4.675,
                    "lng": -74.00,
                    "height_agl_m": 2.0,
                    "antenna_ref": "LoRa U.FL",
                    "antenna_gain_dbi": 2.0,
                    "polarization": "VERTICAL",
                    "tx_power_nominal_dbm": 21.0,
                    "tx_power_tolerance_db": 1.0,
                }
            ],
            "links": [
                {
                    "end_node_id": en_id,
                    "access_node_id": an_id,
                }
            ],
            "propagation_setup": {
                "model_id": "LONGLEY_RICE",
                "parameters": {
                    "ipol": 1,
                    "eps": 15.0,
                    "sgm": 0.005,
                    "klim": 5,
                    "ens0": 314.0,
                    "mdvar": 11,
                    "qc": 50.0,
                    "qr": [10.0, 50.0, 90.0],
                },
            },
        },
    )
    assert res.status_code == status.HTTP_201_CREATED, res.text
    return res.json()


def test_ac17_run_simulation_completes_with_link_results(client: TestClient) -> None:
    """AC-15, AC-17, AC-20, AC-22: Create and run a simulation completing with link results."""
    token, user_id = _create_authenticated_user(client, "ac17@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    engine = client.app.dependency_overrides.get(list(client.app.dependency_overrides.keys())[0])()
    seeded = _seed_profiles_and_dem(engine, user_id, dem_status="AVAILABLE")

    client.app.dependency_overrides[get_terrain_profile_provider] = _FakeTerrainProfileProvider
    client.app.dependency_overrides[get_propagation_engine] = _FakePropagationEngine

    scenario = _create_valid_scenario(client, headers, seeded["dem_id"], seeded["lora_id"])

    # AC-15: Create simulation -> CREATED with snapshot
    create_res = client.post(
        "/api/v1/simulations",
        headers=headers,
        json={
            "scenario_id": scenario["id"],
            "name": "Sim LoRaWAN SF12",
            "description": "Prueba completa",
        },
    )
    assert create_res.status_code == status.HTTP_201_CREATED, create_res.text
    sim_data = create_res.json()
    assert sim_data["status"] == "CREATED"
    assert sim_data["snapshot"]["scenario_id"] == scenario["id"]

    # AC-17: Run simulation -> 202 and background job completes
    run_res = client.post(f"/api/v1/simulations/{sim_data['id']}/run", headers=headers)
    assert run_res.status_code == status.HTTP_202_ACCEPTED, run_res.text

    results_res = client.get(f"/api/v1/simulations/{sim_data['id']}/results", headers=headers)
    assert results_res.status_code == status.HTTP_200_OK, results_res.text
    results = results_res.json()
    assert results["status"] == "COMPLETED"
    assert results["summary"]["viable_links_pct"] == 100.0
    assert len(results["link_results"]) == 1
    lr = results["link_results"][0]
    assert lr["end_node_name"] == "EN-1"
    assert lr["access_node_name"] == "GW-1"
    assert lr["viable"] is True
    assert lr["sensitivity_origin"] == "REFERENCE_TO_VERIFY"
    assert len(lr["path_loss"]["loss_by_quantile"]) == 3
    assert len(lr["profile_series"]["distances_m"]) == 3
    assert len(results["warnings"]) == 1
    assert results["warnings"][0]["code"] == "KWX_4"

    # AC-19: Running an already COMPLETED simulation returns 409 InvalidStatusTransition
    rerun_res = client.post(f"/api/v1/simulations/{sim_data['id']}/run", headers=headers)
    assert rerun_res.status_code == status.HTTP_409_CONFLICT
    assert rerun_res.json()["code"] == "InvalidStatusTransition"


def test_ac23_and_ac24_compare_simulations(client: TestClient) -> None:
    """AC-23, AC-24: Compare two COMPLETED simulations of same group and reject different groups."""
    token, user_id = _create_authenticated_user(client, "ac23@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    engine = client.app.dependency_overrides.get(list(client.app.dependency_overrides.keys())[0])()
    seeded = _seed_profiles_and_dem(engine, user_id, dem_status="AVAILABLE")

    client.app.dependency_overrides[get_terrain_profile_provider] = _FakeTerrainProfileProvider
    client.app.dependency_overrides[get_propagation_engine] = _FakePropagationEngine

    sc_lora = _create_valid_scenario(
        client, headers, seeded["dem_id"], seeded["lora_id"], "Base LoRa"
    )
    var_res = client.post(
        f"/api/v1/scenarios/{sc_lora['id']}/variants",
        headers=headers,
        json={
            "target_profile_id": str(seeded["ltem_id"]),
            "band_code": "B28",
            "frequency_mhz": 700.0,
            "name": "Variante LTE-M",
        },
    )
    assert var_res.status_code == status.HTTP_201_CREATED
    sc_ltem = var_res.json()

    sim1 = client.post(
        "/api/v1/simulations",
        headers=headers,
        json={"scenario_id": sc_lora["id"], "name": "Sim LoRa"},
    ).json()
    client.post(f"/api/v1/simulations/{sim1['id']}/run", headers=headers)

    sim2 = client.post(
        "/api/v1/simulations",
        headers=headers,
        json={"scenario_id": sc_ltem["id"], "name": "Sim LTE-M"},
    ).json()
    client.post(f"/api/v1/simulations/{sim2['id']}/run", headers=headers)

    # AC-23: Compare both completed simulations of the same comparison group
    cmp_res = client.get(
        f"/api/v1/simulations/compare?ids={sim1['id']},{sim2['id']}",
        headers=headers,
    )
    assert cmp_res.status_code == status.HTTP_200_OK, cmp_res.text
    cmp_data = cmp_res.json()
    assert len(cmp_data["simulations"]) == 2
    assert len(cmp_data["links"]) == 1
    assert len(cmp_data["links"][0]["metrics_by_simulation"]) == 2

    # AC-24: Create a simulation in a different group and verify compare returns 422 NotComparable
    sc_other = _create_valid_scenario(
        client, headers, seeded["dem_id"], seeded["lora_id"], "Otro Grupo"
    )
    sim_other = client.post(
        "/api/v1/simulations",
        headers=headers,
        json={"scenario_id": sc_other["id"], "name": "Sim Otro Grupo"},
    ).json()
    client.post(f"/api/v1/simulations/{sim_other['id']}/run", headers=headers)

    bad_cmp = client.get(
        f"/api/v1/simulations/compare?ids={sim1['id']},{sim_other['id']}",
        headers=headers,
    )
    assert bad_cmp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert bad_cmp.json()["code"] == "NotComparable"


def test_ac25_delete_running_rejected_and_scenario_deletion_preserves_simulation(
    client: TestClient,
) -> None:
    """AC-25, RF-026: Running simulation cannot be deleted; deleting scenario preserves sim."""
    token, user_id = _create_authenticated_user(client, "ac25@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    engine = client.app.dependency_overrides.get(list(client.app.dependency_overrides.keys())[0])()
    seeded = _seed_profiles_and_dem(engine, user_id, dem_status="AVAILABLE")

    client.app.dependency_overrides[get_terrain_profile_provider] = _FakeTerrainProfileProvider
    client.app.dependency_overrides[get_propagation_engine] = _FakePropagationEngine

    scenario = _create_valid_scenario(client, headers, seeded["dem_id"], seeded["lora_id"])
    sim = client.post(
        "/api/v1/simulations",
        headers=headers,
        json={"scenario_id": scenario["id"], "name": "Sim RF-026"},
    ).json()
    client.post(f"/api/v1/simulations/{sim['id']}/run", headers=headers)

    # RF-026: Delete the scenario and verify simulation and its results still exist
    del_sc = client.delete(f"/api/v1/scenarios/{scenario['id']}", headers=headers)
    assert del_sc.status_code == status.HTTP_204_NO_CONTENT

    get_sim = client.get(f"/api/v1/simulations/{sim['id']}/results", headers=headers)
    assert get_sim.status_code == status.HTTP_200_OK
    assert get_sim.json()["status"] == "COMPLETED"
    assert len(get_sim.json()["link_results"]) == 1

    # AC-25: Force a simulation into RUNNING and verify DELETE returns 409 InvalidStatusTransition
    with Session(engine) as session:
        row = session.get(SimulationSimulationRow, UUID(sim["id"]))
        assert row is not None
        row.status = SimulationStatus.RUNNING.value
        session.add(row)
        session.commit()

    del_running = client.delete(f"/api/v1/simulations/{sim['id']}", headers=headers)
    assert del_running.status_code == status.HTTP_409_CONFLICT
    assert del_running.json()["code"] == "InvalidStatusTransition"


def test_ac05_01_authorization_and_ownership_isolation(client: TestClient) -> None:
    """AC-05-01: Unauthenticated requests return 401; foreign owner requests return 404."""
    unauth = client.get("/api/v1/simulations")
    assert unauth.status_code == status.HTTP_401_UNAUTHORIZED

    token_a, user_a = _create_authenticated_user(client, "owner_a_sim@example.com")
    token_b, _ = _create_authenticated_user(client, "owner_b_sim@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    engine = client.app.dependency_overrides.get(list(client.app.dependency_overrides.keys())[0])()
    seeded = _seed_profiles_and_dem(engine, user_a, dem_status="AVAILABLE")
    scenario_a = _create_valid_scenario(client, headers_a, seeded["dem_id"], seeded["lora_id"])

    sim_a = client.post(
        "/api/v1/simulations",
        headers=headers_a,
        json={"scenario_id": scenario_a["id"], "name": "Private Sim A"},
    ).json()

    # User B cannot access, update, run, or delete User A's simulation (404)
    assert (
        client.get(f"/api/v1/simulations/{sim_a['id']}/results", headers=headers_b).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        client.patch(
            f"/api/v1/simulations/{sim_a['id']}", headers=headers_b, json={"name": "Hack"}
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        client.post(f"/api/v1/simulations/{sim_a['id']}/run", headers=headers_b).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        client.delete(f"/api/v1/simulations/{sim_a['id']}", headers=headers_b).status_code
        == status.HTTP_404_NOT_FOUND
    )


def test_ac29_export_coverage_data_for_radio_mobile(client: TestClient) -> None:
    """AC-29: Export coverage data in Radio Mobile compatible format (UC-CO-04)."""
    token, user_id = _create_authenticated_user(client, "ac29@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    engine = client.app.dependency_overrides.get(list(client.app.dependency_overrides.keys())[0])()
    seeded = _seed_profiles_and_dem(engine, user_id, dem_status="AVAILABLE")

    client.app.dependency_overrides[get_terrain_profile_provider] = _FakeTerrainProfileProvider
    client.app.dependency_overrides[get_propagation_engine] = _FakePropagationEngine

    scenario = _create_valid_scenario(client, headers, seeded["dem_id"], seeded["lora_id"])

    create_res = client.post(
        "/api/v1/simulations",
        headers=headers,
        json={
            "scenario_id": scenario["id"],
            "name": "Sim For Export",
            "description": "Radio Mobile comparison export",
        },
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    sim_id = create_res.json()["id"]

    # Before running -> 409
    export_before_run = client.get(
        f"/api/v1/simulations/{sim_id}/coverage/export",
        headers=headers,
    )
    assert export_before_run.status_code == status.HTTP_409_CONFLICT

    # Run simulation
    run_res = client.post(
        f"/api/v1/simulations/{sim_id}/run",
        headers=headers,
    )
    assert run_res.status_code == status.HTTP_202_ACCEPTED

    # Export coverage data -> 200 OK
    export_res = client.get(
        f"/api/v1/simulations/{sim_id}/coverage/export",
        headers=headers,
    )
    assert export_res.status_code == status.HTTP_200_OK
    data = export_res.json()
    assert data["simulation_id"] == sim_id
    assert data["technology"] == "LORAWAN"
    assert "metrics" in data
    assert data["metrics"]["effective_coverage_area_km2"] >= 0.0
    assert data["metrics"]["coverage_percentage"] >= 0.0
    assert data["metrics"]["max_coverage_radius_km"] >= 0.0
    assert data["metrics"]["variability_index"] >= 0.0
    assert len(data["samples"]) > 0
    first_sample = data["samples"][0]
    assert "latitude" in first_sample
    assert "longitude" in first_sample
    assert "received_power_dbm" in first_sample
    assert "viable" in first_sample
    assert "distance_km" in first_sample
    assert "azimuth_deg" in first_sample
