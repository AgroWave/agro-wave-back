"""Unit tests for simulation domain entities, value objects, and services (UC-SI-01 to UC-SI-04)."""

from uuid import uuid4

import pytest

from agrowave.modules.simulation.domain.errors import (
    InvalidStatusTransitionError,
    NotComparableError,
)
from agrowave.modules.simulation.domain.models import (
    ElevationProfileSeries,
    FresnelAnalysis,
    FresnelVerdict,
    LinkResult,
    PathLossPrediction,
    PathLossQuantile,
    ScenarioSnapshot,
    SensitivityOrigin,
    Simulation,
    SimulationResult,
    SimulationStatus,
    SimulationWarning,
    Technology,
)
from agrowave.modules.simulation.domain.services import (
    ComparisonService,
    FreeSpacePathLoss,
    FresnelAnalyzer,
    LinkBudget,
)


def _sample_snapshot(
    comparison_group_id=None,
    technology: Technology = Technology.LORAWAN,
    propagation_model_id: str = "LONGLEY_RICE",
) -> ScenarioSnapshot:
    cg_id = comparison_group_id or uuid4()
    return ScenarioSnapshot(
        scenario_id=uuid4(),
        comparison_group_id=cg_id,
        name="Scenario La Calera",
        technology=technology,
        frequency_mhz=915.0,
        propagation_model_id=propagation_model_id,
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
        access_nodes=[],
        end_nodes=[],
        links=[],
    )


def _sample_link_result(
    link_id=None,
    verdict: FresnelVerdict = FresnelVerdict.CLEAR,
    margin_db: float = 2.0,
    viable: bool = True,
) -> LinkResult:
    lid = link_id or uuid4()
    return LinkResult(
        link_id=lid,
        end_node_name="EN-1",
        access_node_name="GW-1",
        distance_m=1613.0,
        fresnel=FresnelAnalysis(
            min_clearance_ratio=0.85 if verdict == FresnelVerdict.CLEAR else -2.24,
            min_clearance_at_m=800.0,
            max_radius_m=11.5,
            verdict=verdict,
        ),
        path_loss=PathLossPrediction(
            free_space_loss_db=95.8,
            loss_by_quantile=(
                PathLossQuantile(reliability_pct=10.0, confidence_pct=50.0, loss_db=138.0),
                PathLossQuantile(reliability_pct=50.0, confidence_pct=50.0, loss_db=142.13),
                PathLossQuantile(reliability_pct=90.0, confidence_pct=50.0, loss_db=146.5),
            ),
        ),
        received_power_dbm=-128.0,
        sensitivity_used_dbm=-130.0,
        sensitivity_origin=SensitivityOrigin.REFERENCE_TO_VERIFY,
        margin_db=margin_db,
        viable=viable,
        profile_series=ElevationProfileSeries(
            distances_m=(0.0, 800.0, 1613.0),
            terrain_with_curvature_m=(2600.0, 2610.0, 2620.0),
            los_m=(2602.0, 2615.0, 2628.0),
            f1_radius_m=(0.0, 11.5, 0.0),
        ),
    )


def test_ac19_run_completed_simulation_raises_invalid_status_transition() -> None:
    """Given COMPLETED simulation, when start or retry is called, raises InvalidStatusTransition."""
    snapshot = _sample_snapshot()
    sim = Simulation.create(
        owner_id=uuid4(),
        name="Sim 1",
        description="Test sim",
        snapshot=snapshot,
    )
    assert sim.status == SimulationStatus.CREATED

    # Start moves CREATED -> RUNNING
    sim.start()
    assert sim.status == SimulationStatus.RUNNING
    assert sim.started_at is not None

    # Cannot delete while RUNNING (RN-33, AC-25)
    with pytest.raises(InvalidStatusTransitionError):
        sim.ensure_deletable()

    # Complete moves RUNNING -> COMPLETED
    result = SimulationResult(
        link_results=(_sample_link_result(),),
        warnings=(
            SimulationWarning(
                link_id=None,
                source="ITM",
                code="KWX_0",
                message="Nominal",
            ),
        ),
    )
    sim.complete(result)
    assert sim.status == SimulationStatus.COMPLETED
    assert sim.finished_at is not None
    assert sim.summary is not None
    assert sim.summary.viable_links_pct == 100.0
    assert sim.summary.fresnel_clear_count == 1

    # Calling start() or retry() on COMPLETED raises InvalidStatusTransitionError (AC-19)
    with pytest.raises(InvalidStatusTransitionError):
        sim.start()
    with pytest.raises(InvalidStatusTransitionError):
        sim.retry()


def test_ac18_domain_fail_and_retry_transition() -> None:
    """Given a RUNNING simulation that fails, retry transitions FAILED -> RUNNING."""
    sim = Simulation.create(
        owner_id=uuid4(),
        name="Sim Fail",
        description=None,
        snapshot=_sample_snapshot(),
    )
    sim.start()
    sim.fail("Motor ITM fuera de rango")
    assert sim.status == SimulationStatus.FAILED
    assert sim.failure_reason == "Motor ITM fuera de rango"

    sim.retry()
    assert sim.status == SimulationStatus.RUNNING
    assert sim.failure_reason is None


def test_ac20_link_budget_margin_and_viability() -> None:
    """Given Prx = -128 dBm and sensitivity = -130 dBm, margin is 2 dB and viable (RN-34, RN-42)."""
    # Ptx = 21 dBm, Gtx = 2 dBi, Grx = 3 dBi, PL = 154 dB => Prx = 21 + 2 + 3 - 154 = -128 dBm
    outcome = LinkBudget.evaluate(
        tx_power_dbm=21.0,
        tx_gain_dbi=2.0,
        rx_gain_dbi=3.0,
        path_loss_db=154.0,
        sensitivity_dbm=-130.0,
        sensitivity_origin=SensitivityOrigin.REFERENCE_TO_VERIFY,
    )
    assert outcome.received_power_dbm == pytest.approx(-128.0)
    assert outcome.margin_db == pytest.approx(2.0)
    assert outcome.viable is True
    assert outcome.sensitivity_used_dbm == pytest.approx(-130.0)
    assert outcome.sensitivity_origin == SensitivityOrigin.REFERENCE_TO_VERIFY

    # Non-viable case
    non_viable = LinkBudget.evaluate(
        tx_power_dbm=20.0,
        tx_gain_dbi=2.0,
        rx_gain_dbi=3.0,
        path_loss_db=160.0,
        sensitivity_dbm=-130.0,
        sensitivity_origin=SensitivityOrigin.USER_DEFINED,
    )
    assert non_viable.received_power_dbm == pytest.approx(-135.0)
    assert non_viable.margin_db == pytest.approx(-5.0)
    assert non_viable.viable is False
    assert non_viable.sensitivity_origin == SensitivityOrigin.USER_DEFINED


def test_ac21_fresnel_analyzer_verdicts_and_calera_regression() -> None:
    """Given profile with min ratio -2.24 F1 (Calera 1 ~1.613 km), verdict is OBSTRUCTED (RN-35)."""
    # At 915 MHz and d = 1613 m, midpoint d1 = d2 = 806.5 m:
    # lambda = 299.792458 / 915 = 0.327642 m
    # r1_mid = sqrt(0.327642 * 806.5 * 806.5 / 1613) ~= 11.494 m
    # Earth bulge at midpoint = 806.5 * 806.5 / (2 * (4/3) * 6371000) ~= 0.0383 m
    # If LoS at midpoint is 2702.0 m and terrain + bulge is 2702.0 + 2.24 * 11.494 = 2727.746 m,
    # then clearance = 2702.0 - 2727.746 = -25.746 m => ratio = -2.24 => OBSTRUCTED
    distances_m = [0.0, 806.5, 1613.0]
    elevations_obstructed_m = [2700.0, 2727.708, 2700.0]

    analysis_obs, series_obs = FresnelAnalyzer.analyze(
        distances_m=distances_m,
        elevations_m=elevations_obstructed_m,
        tx_height_agl_m=2.0,
        rx_height_agl_m=2.0,
        frequency_mhz=915.0,
    )
    assert analysis_obs.verdict == FresnelVerdict.OBSTRUCTED
    assert analysis_obs.min_clearance_ratio == pytest.approx(-2.24, abs=0.02)
    assert analysis_obs.min_clearance_at_m == pytest.approx(806.5)
    assert len(series_obs.distances_m) == 3

    # Marginal case: ratio around 0.35 in [0, 0.6)
    elevations_marginal_m = [2700.0, 2697.9, 2700.0]
    analysis_marg, _ = FresnelAnalyzer.analyze(
        distances_m=distances_m,
        elevations_m=elevations_marginal_m,
        tx_height_agl_m=2.0,
        rx_height_agl_m=2.0,
        frequency_mhz=915.0,
    )
    assert analysis_marg.verdict == FresnelVerdict.MARGINAL
    assert 0.0 <= analysis_marg.min_clearance_ratio < 0.6

    # Clear case: ratio >= 0.6
    elevations_clear_m = [2700.0, 2680.0, 2700.0]
    analysis_clear, _ = FresnelAnalyzer.analyze(
        distances_m=distances_m,
        elevations_m=elevations_clear_m,
        tx_height_agl_m=2.0,
        rx_height_agl_m=2.0,
        frequency_mhz=915.0,
    )
    assert analysis_clear.verdict == FresnelVerdict.CLEAR
    assert analysis_clear.min_clearance_ratio >= 0.6

    # Verify FreeSpacePathLoss at 1613 m and 915 MHz (~95.82 dB)
    fspl = FreeSpacePathLoss.calculate(distance_m=1613.0, frequency_mhz=915.0)
    assert fspl == pytest.approx(95.82, abs=0.1)


def test_ac24_compare_different_group_or_model_rejected() -> None:
    """Given simulations of different groups/models/status, raises NotComparableError."""
    owner_id = uuid4()
    group_a = uuid4()
    group_b = uuid4()
    shared_link_id = uuid4()

    sim1 = Simulation.create(
        owner_id=owner_id,
        name="LoRaWAN SF12",
        description=None,
        snapshot=_sample_snapshot(comparison_group_id=group_a, technology=Technology.LORAWAN),
    )
    sim1.start()
    sim1.complete(
        SimulationResult(link_results=(_sample_link_result(link_id=shared_link_id, margin_db=5.0),))
    )

    sim2 = Simulation.create(
        owner_id=owner_id,
        name="LTE-M",
        description=None,
        snapshot=_sample_snapshot(comparison_group_id=group_a, technology=Technology.LTE_M),
    )
    sim2.start()
    sim2.complete(
        SimulationResult(
            link_results=(
                _sample_link_result(link_id=shared_link_id, margin_db=-1.5, viable=False),
            )
        )
    )

    # AC-23: Same group, same model, both COMPLETED -> succeeds
    report = ComparisonService.compare([sim1, sim2])
    assert report.comparison_group_id == group_a
    assert len(report.simulations) == 2
    assert len(report.links) == 1
    assert len(report.links[0].metrics_by_simulation) == 2

    # AC-24: Different comparison_group_id -> NotComparableError
    sim_other_group = Simulation.create(
        owner_id=owner_id,
        name="Other Group",
        description=None,
        snapshot=_sample_snapshot(comparison_group_id=group_b),
    )
    sim_other_group.start()
    sim_other_group.complete(SimulationResult(link_results=(_sample_link_result(),)))

    with pytest.raises(NotComparableError):
        ComparisonService.compare([sim1, sim_other_group])

    # AC-24: Different propagation_model_id -> NotComparableError
    sim_other_model = Simulation.create(
        owner_id=owner_id,
        name="Other Model",
        description=None,
        snapshot=_sample_snapshot(comparison_group_id=group_a, propagation_model_id="ITU_P452"),
    )
    sim_other_model.start()
    sim_other_model.complete(SimulationResult(link_results=(_sample_link_result(),)))

    with pytest.raises(NotComparableError):
        ComparisonService.compare([sim1, sim_other_model])

    # AC-24: Non-completed simulation -> NotComparableError
    sim_created = Simulation.create(
        owner_id=owner_id,
        name="Created Sim",
        description=None,
        snapshot=_sample_snapshot(comparison_group_id=group_a),
    )
    with pytest.raises(NotComparableError):
        ComparisonService.compare([sim1, sim_created])
