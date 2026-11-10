"""FastAPI router for simulation endpoints (/api/v1/simulations)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse

from agrowave.modules.identity.domain.models import User
from agrowave.modules.identity.presentation.dependencies import get_current_user
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
    RunSimulation,
)
from agrowave.modules.simulation.application.use_cases.update_simulation import (
    UpdateSimulation,
)
from agrowave.modules.simulation.domain.errors import (
    InvalidStatusTransitionError,
    NotComparableError,
    ScenarioNotSimulableError,
    SimulationDomainError,
    SimulationNotFoundError,
)
from agrowave.modules.simulation.domain.models import (
    Simulation,
    SimulationStatus,
    Technology,
)
from agrowave.modules.simulation.domain.ports import (
    ScenarioSnapshotSource,
    SimulationJobRunner,
    SimulationRepository,
)
from agrowave.modules.simulation.presentation.dependencies import (
    get_scenario_snapshot_source,
    get_simulation_job_runner,
    get_simulation_repository,
)
from agrowave.modules.simulation.presentation.schemas import (
    ComparedLinkMetricResponse,
    ComparedLinkRowResponse,
    ComparedSimulationSummaryResponse,
    ComparisonReportResponse,
    CreateSimulationRequest,
    ElevationProfileSeriesResponse,
    FresnelAnalysisResponse,
    LinkResultResponse,
    PathLossPredictionResponse,
    PathLossQuantileResponse,
    SimulationResponse,
    SimulationResultsResponse,
    SimulationSummaryResponse,
    SimulationWarningResponse,
    UpdateSimulationRequest,
)

router = APIRouter(prefix="/simulations", tags=["simulations"])


def _domain_error_response(err: SimulationDomainError) -> JSONResponse:
    """Maps a SimulationDomainError to the standard HTTP status and error body."""
    if isinstance(err, SimulationNotFoundError):
        http_status = status.HTTP_404_NOT_FOUND
    elif isinstance(err, InvalidStatusTransitionError):
        http_status = status.HTTP_409_CONFLICT
    elif isinstance(err, (ScenarioNotSimulableError, NotComparableError)):
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY

    return JSONResponse(
        status_code=http_status,
        content={
            "code": err.code,
            "message": err.message,
            "details": err.details,
        },
    )


def _to_summary_response(sim: Simulation) -> SimulationSummaryResponse | None:
    """Maps domain SimulationSummary to SimulationSummaryResponse."""
    if sim.summary is None:
        return None
    return SimulationSummaryResponse(
        viable_links_pct=sim.summary.viable_links_pct,
        min_margin_db=sim.summary.min_margin_db,
        mean_margin_db=sim.summary.mean_margin_db,
        fresnel_clear_count=sim.summary.fresnel_clear_count,
        fresnel_marginal_count=sim.summary.fresnel_marginal_count,
        fresnel_obstructed_count=sim.summary.fresnel_obstructed_count,
    )


def _to_simulation_response(sim: Simulation) -> SimulationResponse:
    """Maps a domain Simulation to SimulationResponse."""
    return SimulationResponse(
        id=sim.id,
        owner_id=sim.owner_id,
        scenario_id=sim.scenario_id,
        comparison_group_id=sim.comparison_group_id,
        name=sim.name,
        description=sim.description,
        status=sim.status.value,
        technology=sim.technology.value,
        propagation_model_id=sim.propagation_model_id,
        snapshot=sim.snapshot.to_dict(),
        summary=_to_summary_response(sim),
        failure_reason=sim.failure_reason,
        created_at=sim.created_at,
        started_at=sim.started_at,
        finished_at=sim.finished_at,
    )


def _to_simulation_results_response(sim: Simulation) -> SimulationResultsResponse:
    """Maps a domain Simulation and its results to SimulationResultsResponse."""
    link_results: list[LinkResultResponse] = []
    warnings: list[SimulationWarningResponse] = []
    if sim.result is not None:
        for lr in sim.result.link_results:
            link_results.append(
                LinkResultResponse(
                    id=lr.id,
                    link_id=lr.link_id,
                    end_node_name=lr.end_node_name,
                    access_node_name=lr.access_node_name,
                    distance_m=lr.distance_m,
                    fresnel=FresnelAnalysisResponse(
                        min_clearance_ratio=lr.fresnel.min_clearance_ratio,
                        min_clearance_at_m=lr.fresnel.min_clearance_at_m,
                        max_radius_m=lr.fresnel.max_radius_m,
                        verdict=lr.fresnel.verdict.value,
                    ),
                    path_loss=PathLossPredictionResponse(
                        free_space_loss_db=lr.path_loss.free_space_loss_db,
                        loss_by_quantile=[
                            PathLossQuantileResponse(
                                reliability_pct=q.reliability_pct,
                                confidence_pct=q.confidence_pct,
                                loss_db=q.loss_db,
                            )
                            for q in lr.path_loss.loss_by_quantile
                        ],
                    ),
                    received_power_dbm=lr.received_power_dbm,
                    sensitivity_used_dbm=lr.sensitivity_used_dbm,
                    sensitivity_origin=lr.sensitivity_origin.value,
                    margin_db=lr.margin_db,
                    viable=lr.viable,
                    profile_series=ElevationProfileSeriesResponse(
                        distances_m=list(lr.profile_series.distances_m),
                        terrain_with_curvature_m=list(lr.profile_series.terrain_with_curvature_m),
                        los_m=list(lr.profile_series.los_m),
                        f1_radius_m=list(lr.profile_series.f1_radius_m),
                        series_version=lr.profile_series.series_version,
                    ),
                )
            )
        for w in sim.result.warnings:
            warnings.append(
                SimulationWarningResponse(
                    id=w.id,
                    link_id=w.link_id,
                    source=w.source,
                    code=w.code,
                    message=w.message,
                )
            )

    return SimulationResultsResponse(
        id=sim.id,
        owner_id=sim.owner_id,
        scenario_id=sim.scenario_id,
        comparison_group_id=sim.comparison_group_id,
        name=sim.name,
        description=sim.description,
        status=sim.status.value,
        technology=sim.technology.value,
        propagation_model_id=sim.propagation_model_id,
        snapshot=sim.snapshot.to_dict(),
        summary=_to_summary_response(sim),
        failure_reason=sim.failure_reason,
        created_at=sim.created_at,
        started_at=sim.started_at,
        finished_at=sim.finished_at,
        link_results=link_results,
        warnings=warnings,
    )


@router.get("", response_model=list[SimulationResponse])
def list_simulations(
    q: str | None = Query(default=None),
    technology: Technology | None = Query(default=None),
    status_filter: SimulationStatus | None = Query(default=None, alias="status"),
    comparison_group_id: UUID | None = Query(default=None),
    sort: str = Query(default="newest"),
    current_user: User = Depends(get_current_user),
    repository: SimulationRepository = Depends(get_simulation_repository),
) -> list[SimulationResponse]:
    """Lists simulations owned by the current user with optional filters."""
    items = ListSimulations(repository=repository).execute(
        owner_id=current_user.id,
        q=q,
        technology=technology,
        status=status_filter,
        comparison_group_id=comparison_group_id,
        sort=sort,
    )
    return [_to_simulation_response(sim) for sim in items]


@router.post("", response_model=SimulationResponse, status_code=status.HTTP_201_CREATED)
def create_simulation(
    payload: CreateSimulationRequest,
    current_user: User = Depends(get_current_user),
    repository: SimulationRepository = Depends(get_simulation_repository),
    snapshot_source: ScenarioSnapshotSource = Depends(get_scenario_snapshot_source),
) -> SimulationResponse | JSONResponse:
    """Creates a new simulation in CREATED state with a scenario snapshot (UC-SI-01)."""
    try:
        sim = CreateSimulation(
            repository=repository,
            snapshot_source=snapshot_source,
        ).execute(
            CreateSimulationInput(
                owner_id=current_user.id,
                scenario_id=payload.scenario_id,
                name=payload.name,
                description=payload.description,
            )
        )
        return _to_simulation_response(sim)
    except SimulationDomainError as err:
        return _domain_error_response(err)


@router.get("/compare", response_model=ComparisonReportResponse)
def compare_simulations(
    ids: str = Query(..., description="Comma-separated simulation UUIDs to compare."),
    current_user: User = Depends(get_current_user),
    repository: SimulationRepository = Depends(get_simulation_repository),
) -> ComparisonReportResponse | JSONResponse:
    """Compares two or more COMPLETED simulations of the same group and model (UC-SI-03)."""
    try:
        raw_parts = [part.strip() for part in ids.split(",") if part.strip()]
        try:
            sim_ids = [UUID(part) for part in raw_parts]
        except ValueError as exc:
            raise NotComparableError("Invalid simulation UUID format in query") from exc

        report = CompareSimulations(repository=repository).execute(
            simulation_ids=sim_ids,
            owner_id=current_user.id,
        )
        return ComparisonReportResponse(
            comparison_group_id=report.comparison_group_id,
            propagation_model_id=report.propagation_model_id,
            simulations=[
                ComparedSimulationSummaryResponse(
                    simulation_id=s.simulation_id,
                    name=s.name,
                    technology=s.technology.value,
                    frequency_mhz=s.frequency_mhz,
                    summary=SimulationSummaryResponse(
                        viable_links_pct=s.summary.viable_links_pct,
                        min_margin_db=s.summary.min_margin_db,
                        mean_margin_db=s.summary.mean_margin_db,
                        fresnel_clear_count=s.summary.fresnel_clear_count,
                        fresnel_marginal_count=s.summary.fresnel_marginal_count,
                        fresnel_obstructed_count=s.summary.fresnel_obstructed_count,
                    ),
                )
                for s in report.simulations
            ],
            links=[
                ComparedLinkRowResponse(
                    link_key=row.link_key,
                    end_node_name=row.end_node_name,
                    access_node_name=row.access_node_name,
                    distance_m=row.distance_m,
                    metrics_by_simulation=[
                        ComparedLinkMetricResponse(
                            simulation_id=m.simulation_id,
                            simulation_name=m.simulation_name,
                            technology=m.technology.value,
                            path_loss_p50_db=m.path_loss_p50_db,
                            received_power_dbm=m.received_power_dbm,
                            sensitivity_used_dbm=m.sensitivity_used_dbm,
                            margin_db=m.margin_db,
                            viable=m.viable,
                            fresnel_verdict=m.fresnel_verdict.value,
                        )
                        for m in row.metrics_by_simulation
                    ],
                )
                for row in report.links
            ],
        )
    except SimulationDomainError as err:
        return _domain_error_response(err)


@router.get("/{simulation_id}", response_model=SimulationResponse)
def get_simulation(
    simulation_id: UUID,
    current_user: User = Depends(get_current_user),
    repository: SimulationRepository = Depends(get_simulation_repository),
) -> SimulationResponse | JSONResponse:
    """Retrieves a simulation by ID."""
    try:
        sim = GetSimulationResults(repository=repository).execute(
            simulation_id=simulation_id,
            owner_id=current_user.id,
        )
        return _to_simulation_response(sim)
    except SimulationDomainError as err:
        return _domain_error_response(err)


@router.get("/{simulation_id}/results", response_model=SimulationResultsResponse)
def get_simulation_results(
    simulation_id: UUID,
    current_user: User = Depends(get_current_user),
    repository: SimulationRepository = Depends(get_simulation_repository),
) -> SimulationResultsResponse | JSONResponse:
    """Retrieves a simulation along with its per-link results, profiles, and warnings."""
    try:
        sim = GetSimulationResults(repository=repository).execute(
            simulation_id=simulation_id,
            owner_id=current_user.id,
        )
        return _to_simulation_results_response(sim)
    except SimulationDomainError as err:
        return _domain_error_response(err)


@router.patch("/{simulation_id}", response_model=SimulationResponse)
def update_simulation(
    simulation_id: UUID,
    payload: UpdateSimulationRequest,
    current_user: User = Depends(get_current_user),
    repository: SimulationRepository = Depends(get_simulation_repository),
) -> SimulationResponse | JSONResponse:
    """Updates simulation name and description metadata (UC-SI-04)."""
    try:
        sim = UpdateSimulation(repository=repository).execute(
            simulation_id=simulation_id,
            owner_id=current_user.id,
            name=payload.name,
            description=payload.description,
        )
        return _to_simulation_response(sim)
    except SimulationDomainError as err:
        return _domain_error_response(err)


@router.post(
    "/{simulation_id}/run",
    response_model=SimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_simulation(
    simulation_id: UUID,
    current_user: User = Depends(get_current_user),
    repository: SimulationRepository = Depends(get_simulation_repository),
    job_runner: SimulationJobRunner = Depends(get_simulation_job_runner),
) -> SimulationResponse | JSONResponse:
    """Starts a CREATED simulation and schedules background execution (UC-SI-02)."""
    try:
        sim = RunSimulation(repository=repository, job_runner=job_runner).execute(
            simulation_id=simulation_id,
            owner_id=current_user.id,
        )
        return _to_simulation_response(sim)
    except SimulationDomainError as err:
        return _domain_error_response(err)


@router.post(
    "/{simulation_id}/retry",
    response_model=SimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_simulation(
    simulation_id: UUID,
    current_user: User = Depends(get_current_user),
    repository: SimulationRepository = Depends(get_simulation_repository),
    job_runner: SimulationJobRunner = Depends(get_simulation_job_runner),
) -> SimulationResponse | JSONResponse:
    """Retries a FAILED simulation (UC-SI-02)."""
    try:
        sim = RetrySimulation(repository=repository, job_runner=job_runner).execute(
            simulation_id=simulation_id,
            owner_id=current_user.id,
        )
        return _to_simulation_response(sim)
    except SimulationDomainError as err:
        return _domain_error_response(err)


@router.delete("/{simulation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_simulation(
    simulation_id: UUID,
    current_user: User = Depends(get_current_user),
    repository: SimulationRepository = Depends(get_simulation_repository),
) -> Response:
    """Deletes a simulation unless it is currently RUNNING (UC-SI-04, RN-33)."""
    try:
        DeleteSimulation(repository=repository).execute(
            simulation_id=simulation_id,
            owner_id=current_user.id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except SimulationDomainError as err:
        return _domain_error_response(err)
