"""Unit tests for simulation application use cases (UC-SI-01 to UC-SI-04)."""

from typing import Any
from uuid import UUID, uuid4

import pytest

from agrowave.modules.simulation.application.use_cases.compare_simulations import (
    CompareSimulations,
)
from agrowave.modules.simulation.application.use_cases.create_simulation import (
    CreateSimulation,
    CreateSimulationInput,
)
from agrowave.modules.simulation.application.use_cases.delete_simulation import (
    DeleteSimulation,
)
from agrowave.modules.simulation.application.use_cases.fail_interrupted_simulations import (
    FailInterruptedSimulations,
)
from agrowave.modules.simulation.application.use_cases.get_simulation_results import (
    GetSimulationResults,
)
from agrowave.modules.simulation.application.use_cases.list_simulations import (
    ListSimulations,
)
from agrowave.modules.simulation.application.use_cases.retry_simulation import (
    RetrySimulation,
)
from agrowave.modules.simulation.application.use_cases.run_simulation import (
    ExecuteSimulationJob,
    RunSimulation,
)
from agrowave.modules.simulation.application.use_cases.update_simulation import (
    UpdateSimulation,
)
from agrowave.modules.simulation.domain.errors import (
    InvalidStatusTransitionError,
    PropagationEngineError,
    ScenarioNotSimulableError,
)
from agrowave.modules.simulation.domain.models import (
    PathLossQuantile,
    ScenarioSnapshot,
    Simulation,
    SimulationStatus,
    Technology,
)
from agrowave.modules.simulation.domain.ports import (
    EngineEvaluationResult,
    SampledTerrainProfile,
)


class InMemorySimulationRepository:
    """In-memory test double for SimulationRepository."""

    def __init__(self) -> None:
        self.items: dict[UUID, Simulation] = {}

    def add(self, simulation: Simulation) -> None:
        self.items[simulation.id] = simulation

    def save(self, simulation: Simulation) -> None:
        self.items[simulation.id] = simulation

    def get_by_id(self, simulation_id: UUID, owner_id: UUID) -> Simulation | None:
        sim = self.items.get(simulation_id)
        if sim is None or sim.owner_id != owner_id:
            return None
        return sim

    def get_by_id_unscoped(self, simulation_id: UUID) -> Simulation | None:
        return self.items.get(simulation_id)

    def list_by_owner(
        self,
        owner_id: UUID,
        q: str | None = None,
        technology: Technology | None = None,
        status: SimulationStatus | None = None,
        comparison_group_id: UUID | None = None,
        sort: str = "newest",
    ) -> list[Simulation]:
        results = [s for s in self.items.values() if s.owner_id == owner_id]
        if q:
            results = [s for s in results if q.lower() in s.name.lower()]
        if technology is not None:
            results = [s for s in results if s.technology == technology]
        if status is not None:
            results = [s for s in results if s.status == status]
        if comparison_group_id is not None:
            results = [s for s in results if s.comparison_group_id == comparison_group_id]
        return results

    def delete(self, simulation_id: UUID, owner_id: UUID) -> None:
        sim = self.get_by_id(simulation_id, owner_id)
        if sim is not None:
            del self.items[simulation_id]

    def mark_running_as_failed_on_startup(self, reason: str) -> int:
        count = 0
        for sim in self.items.values():
            if sim.status == SimulationStatus.RUNNING:
                sim.fail(reason)
                count += 1
        return count


class FakeSnapshotSource:
    """Fake ScenarioSnapshotSource that returns a snapshot or raises ScenarioNotSimulableError."""

    def __init__(
        self,
        snapshot: ScenarioSnapshot | None = None,
        causes: list[dict[str, Any]] | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.causes = causes

    def capture_simulable_snapshot(self, scenario_id: UUID, owner_id: UUID) -> ScenarioSnapshot:
        if self.causes:
            raise ScenarioNotSimulableError(self.causes)
        assert self.snapshot is not None
        return self.snapshot


class FakeTerrainProfileProvider:
    """Fake TerrainProfileProvider returning a deterministic terrain profile."""

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
            elevations_m=(2600.0, 2605.0, 2610.0),
            step_m=distance_m / 2.0,
        )


class FakePropagationEngine:
    """Fake PropagationEngine with configurable failure and warnings."""

    def __init__(
        self,
        should_fail: bool = False,
        warnings: tuple[tuple[str, str], ...] = (),
        p50_loss_db: float = 142.13,
    ) -> None:
        self.should_fail = should_fail
        self.warnings = warnings
        self.p50_loss_db = p50_loss_db

    def evaluate_link(
        self,
        profile: SampledTerrainProfile,
        frequency_mhz: float,
        tx_height_agl_m: float,
        rx_height_agl_m: float,
        polarization: str,
        propagation_params: dict[str, Any],
    ) -> EngineEvaluationResult:
        if self.should_fail:
            raise PropagationEngineError("ITM engine failed due to invalid parameters")
        return EngineEvaluationResult(
            quantiles=(
                PathLossQuantile(
                    reliability_pct=10.0, confidence_pct=50.0, loss_db=self.p50_loss_db - 4.0
                ),
                PathLossQuantile(
                    reliability_pct=50.0, confidence_pct=50.0, loss_db=self.p50_loss_db
                ),
                PathLossQuantile(
                    reliability_pct=90.0, confidence_pct=50.0, loss_db=self.p50_loss_db + 4.0
                ),
            ),
            warnings=self.warnings,
        )


class SyncJobRunner:
    """Synchronous job runner double for testing background execution."""

    def __init__(self, executor: ExecuteSimulationJob | None = None) -> None:
        self.enqueued_ids: list[UUID] = []
        self.executor = executor

    def enqueue(self, simulation_id: UUID) -> None:
        self.enqueued_ids.append(simulation_id)
        if self.executor is not None:
            self.executor.execute(simulation_id)


def _build_valid_snapshot() -> ScenarioSnapshot:
    an_id = str(uuid4())
    en_id = str(uuid4())
    link_id = str(uuid4())
    return ScenarioSnapshot(
        scenario_id=uuid4(),
        comparison_group_id=uuid4(),
        name="Escenario Calera",
        technology=Technology.LORAWAN,
        frequency_mhz=915.0,
        propagation_model_id="LONGLEY_RICE",
        propagation_params={
            "ipol": 1,
            "eps": 15.0,
            "sgm": 0.005,
            "klim": 5,
            "ens0": 314.0,
            "mdvar": 11,
            "qc": 50.0,
            "qr": [10.0, 50.0, 90.0],
        },
        dem_id=uuid4(),
        bounds={"south": 4.65, "west": -74.02, "north": 4.70, "east": -73.97},
        access_nodes=[
            {
                "id": an_id,
                "name": "GW-1",
                "lat": 4.66,
                "lng": -74.00,
                "height_agl_m": 6.0,
                "antenna_ref": "Dragino DLOS8N",
                "antenna_gain_dbi": 3.0,
                "polarization": "VERTICAL",
                "sensitivity_dbm": -137.0,
                "sensitivity_origin": "REFERENCE_TO_VERIFY",
            }
        ],
        end_nodes=[
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
        links=[
            {
                "id": link_id,
                "end_node_id": en_id,
                "access_node_id": an_id,
                "distance_km": 1.668,
            }
        ],
        dem_object_key="dems/owner/dem.tif",
        dem_resolution_m=30.0,
    )


def test_ac15_create_simulation_captures_snapshot() -> None:
    """Given valid scenario with AVAILABLE DEM, CreateSimulation persists CREATED with snapshot."""
    repo = InMemorySimulationRepository()
    snapshot = _build_valid_snapshot()
    source = FakeSnapshotSource(snapshot=snapshot)
    owner_id = uuid4()

    uc = CreateSimulation(repository=repo, snapshot_source=source)
    sim = uc.execute(
        CreateSimulationInput(
            owner_id=owner_id,
            scenario_id=snapshot.scenario_id,
            name="Simulacion Calera SF12",
            description="Prueba de instantanea",
        )
    )
    assert sim.status == SimulationStatus.CREATED
    assert sim.snapshot.scenario_id == snapshot.scenario_id
    assert len(sim.snapshot.links) == 1
    assert repo.get_by_id(sim.id, owner_id) is not None


def test_ac16_si_create_simulation_with_downloading_dem_rejected() -> None:
    """Given scenario with DOWNLOADING DEM, CreateSimulation raises ScenarioNotSimulableError."""
    repo = InMemorySimulationRepository()
    source = FakeSnapshotSource(
        causes=[{"code": "DemNotAvailable", "message": "Assigned DEM is in status DOWNLOADING."}]
    )
    uc = CreateSimulation(repository=repo, snapshot_source=source)

    with pytest.raises(ScenarioNotSimulableError) as exc_info:
        uc.execute(
            CreateSimulationInput(
                owner_id=uuid4(),
                scenario_id=uuid4(),
                name="Invalid Sim",
                description=None,
            )
        )
    assert exc_info.value.details["causes"][0]["code"] == "DemNotAvailable"


def test_ac18_engine_failure_marks_failed_and_retry_succeeds() -> None:
    """Given engine failure during execution, simulation ends FAILED and retry completes it."""
    repo = InMemorySimulationRepository()
    snapshot = _build_valid_snapshot()
    owner_id = uuid4()
    sim = CreateSimulation(
        repository=repo, snapshot_source=FakeSnapshotSource(snapshot=snapshot)
    ).execute(
        CreateSimulationInput(
            owner_id=owner_id,
            scenario_id=snapshot.scenario_id,
            name="Sim Retry Test",
            description=None,
        )
    )

    engine = FakePropagationEngine(should_fail=True)
    executor = ExecuteSimulationJob(
        repository=repo,
        profile_provider=FakeTerrainProfileProvider(),
        propagation_engine=engine,
    )
    runner = SyncJobRunner(executor=executor)

    RunSimulation(repository=repo, job_runner=runner).execute(
        simulation_id=sim.id,
        owner_id=owner_id,
    )
    failed_sim = repo.get_by_id(sim.id, owner_id)
    assert failed_sim is not None
    assert failed_sim.status == SimulationStatus.FAILED
    assert failed_sim.failure_reason is not None

    # Fix engine and retry
    engine.should_fail = False
    RetrySimulation(repository=repo, job_runner=runner).execute(
        simulation_id=sim.id,
        owner_id=owner_id,
    )
    completed_sim = repo.get_by_id(sim.id, owner_id)
    assert completed_sim is not None
    assert completed_sim.status == SimulationStatus.COMPLETED
    assert completed_sim.result is not None
    assert len(completed_sim.result.link_results) == 1


def test_ac22_engine_warnings_persisted_in_completed_simulation() -> None:
    """Given engine warnings (kwx != 0), simulation finishes COMPLETED with warnings (RN-43)."""
    repo = InMemorySimulationRepository()
    snapshot = _build_valid_snapshot()
    owner_id = uuid4()
    sim = CreateSimulation(
        repository=repo, snapshot_source=FakeSnapshotSource(snapshot=snapshot)
    ).execute(
        CreateSimulationInput(
            owner_id=owner_id,
            scenario_id=snapshot.scenario_id,
            name="Sim With KWX Warning",
            description=None,
        )
    )

    engine = FakePropagationEngine(
        should_fail=False,
        warnings=(("KWX_4", "Parámetros fuera del rango exacto de Longley-Rice (kwx=4)."),),
    )
    executor = ExecuteSimulationJob(
        repository=repo,
        profile_provider=FakeTerrainProfileProvider(),
        propagation_engine=engine,
    )
    runner = SyncJobRunner(executor=executor)

    RunSimulation(repository=repo, job_runner=runner).execute(
        simulation_id=sim.id,
        owner_id=owner_id,
    )
    res = GetSimulationResults(repository=repo).execute(simulation_id=sim.id, owner_id=owner_id)
    assert res.status == SimulationStatus.COMPLETED
    assert res.result is not None
    assert len(res.result.warnings) == 1
    assert res.result.warnings[0].code == "KWX_4"

    # Also test Update, List, Delete, Compare, and FailInterruptedSimulations
    updated = UpdateSimulation(repository=repo).execute(
        simulation_id=sim.id,
        owner_id=owner_id,
        name="Renamed Sim",
        description="Updated desc",
    )
    assert updated.name == "Renamed Sim"
    assert len(ListSimulations(repository=repo).execute(owner_id=owner_id, q="Renamed")) == 1

    # Running simulation cannot be deleted (AC-25)
    running_sim = Simulation.create(
        owner_id=owner_id,
        name="Running Sim",
        description=None,
        snapshot=snapshot,
    )
    running_sim.start()
    repo.add(running_sim)

    with pytest.raises(InvalidStatusTransitionError):
        DeleteSimulation(repository=repo).execute(simulation_id=running_sim.id, owner_id=owner_id)

    # Startup recovery marks RUNNING as FAILED
    recovered = FailInterruptedSimulations(repository=repo).execute()
    assert recovered == 1
    assert repo.get_by_id(running_sim.id, owner_id).status == SimulationStatus.FAILED  # type: ignore[union-attr]

    # CompareSimulations (AC-23)
    sim2 = CreateSimulation(
        repository=repo, snapshot_source=FakeSnapshotSource(snapshot=snapshot)
    ).execute(
        CreateSimulationInput(
            owner_id=owner_id,
            scenario_id=snapshot.scenario_id,
            name="Sim Variant 2",
            description=None,
        )
    )
    RunSimulation(repository=repo, job_runner=runner).execute(
        simulation_id=sim2.id, owner_id=owner_id
    )
    report = CompareSimulations(repository=repo).execute(
        simulation_ids=[sim.id, sim2.id],
        owner_id=owner_id,
    )
    assert len(report.simulations) == 2


def test_ac28_simulation_run_includes_coverage_result() -> None:
    """Given a simulation run with coverage engine, COMPLETED sim has coverage metrics (AC-28)."""
    from agrowave.modules.simulation.domain.coverage_models import (
        CoverageMetrics,
        CoverageResult,
    )

    repo = InMemorySimulationRepository()
    snapshot = _build_valid_snapshot()
    owner_id = uuid4()
    sim = CreateSimulation(
        repository=repo, snapshot_source=FakeSnapshotSource(snapshot=snapshot)
    ).execute(
        CreateSimulationInput(
            owner_id=owner_id,
            scenario_id=snapshot.scenario_id,
            name="Sim With Coverage",
            description="Testing AC-28",
        )
    )

    class FakeCoverageEngine:
        def compute_coverage(self, **kwargs: Any) -> CoverageResult:
            metrics = CoverageMetrics(
                effective_coverage_area_km2=15.42,
                coverage_percentage=78.5,
                max_coverage_radius_km=4.85,
                variability_index=0.62,
                total_area_km2=19.63,
                covered_samples_count=280,
                total_samples_count=360,
            )
            return CoverageResult(
                metrics=metrics,
                samples=(),
                access_node_id=UUID(str(snapshot.access_nodes[0]["id"])),
            )

    executor = ExecuteSimulationJob(
        repository=repo,
        profile_provider=FakeTerrainProfileProvider(),
        propagation_engine=FakePropagationEngine(),
        coverage_engine=FakeCoverageEngine(),
    )
    runner = SyncJobRunner(executor=executor)

    RunSimulation(repository=repo, job_runner=runner).execute(
        simulation_id=sim.id, owner_id=owner_id
    )

    completed_sim = repo.get_by_id(sim.id, owner_id)
    assert completed_sim is not None
    assert completed_sim.status == SimulationStatus.COMPLETED
    assert completed_sim.result is not None
    assert completed_sim.result.coverage_result is not None
    assert completed_sim.result.coverage_result.metrics.effective_coverage_area_km2 == 15.42
    assert completed_sim.result.coverage_result.metrics.coverage_percentage == 78.5
    assert completed_sim.result.coverage_result.metrics.max_coverage_radius_km == 4.85
    assert completed_sim.result.coverage_result.metrics.variability_index == 0.62

    # Check that summary exposes coverage metrics too
    summary = completed_sim.result.compute_summary()
    assert summary.coverage_metrics is not None
    assert summary.coverage_metrics.effective_coverage_area_km2 == 15.42
