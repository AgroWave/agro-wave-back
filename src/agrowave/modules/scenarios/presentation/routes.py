"""FastAPI router for scenarios endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse

from agrowave.modules.identity.domain.models import User
from agrowave.modules.identity.presentation.dependencies import get_current_user
from agrowave.modules.scenarios.application.use_cases.create_scenario import (
    CreateScenario,
    CreateScenarioAccessNodeInput,
    CreateScenarioCommand,
    CreateScenarioEndNodeInput,
    CreateScenarioLinkInput,
)
from agrowave.modules.scenarios.application.use_cases.create_scenario_variant import (
    CreateScenarioVariant,
    CreateScenarioVariantCommand,
)
from agrowave.modules.scenarios.application.use_cases.delete_scenario import (
    DeleteScenario,
    DeleteScenarioCommand,
)
from agrowave.modules.scenarios.application.use_cases.duplicate_scenario import (
    DuplicateScenario,
    DuplicateScenarioCommand,
)
from agrowave.modules.scenarios.application.use_cases.get_scenario import (
    GetScenario,
    GetScenarioQuery,
)
from agrowave.modules.scenarios.application.use_cases.list_scenarios import (
    ListScenarios,
    ListScenariosQuery,
)
from agrowave.modules.scenarios.application.use_cases.update_scenario import (
    UpdateScenario,
    UpdateScenarioCommand,
)
from agrowave.modules.scenarios.application.use_cases.validate_scenario import (
    ValidateScenario,
    ValidateScenarioQuery,
)
from agrowave.modules.scenarios.domain.errors import (
    AreaOutsideColombiaError,
    AreaTooSmallError,
    AreaWouldExcludeNodesError,
    DemDoesNotCoverAreaError,
    DemNotAvailableError,
    EndNodeAlreadyLinkedError,
    FrequencyOutOfProfileError,
    HeightBelowMinimumError,
    InvalidBoundsError,
    LinkTooShortError,
    MixedProfileNotAllowedError,
    NodeOutsideAreaError,
    OrphanNodeError,
    ProfileNotFoundError,
    ScenarioNotFoundError,
    ScenariosDomainError,
)
from agrowave.modules.scenarios.domain.models import (
    Bounds,
    LongleyRiceParams,
    PropagationSetup,
    Scenario,
)
from agrowave.modules.scenarios.domain.ports import (
    DemLookup,
    ProfileLookup,
    ScenarioRepository,
    TerritoryBoundary,
)
from agrowave.modules.scenarios.presentation.dependencies import (
    get_dem_lookup,
    get_profile_lookup,
    get_scenario_repository,
    get_scenario_territory_boundary,
)
from agrowave.modules.scenarios.presentation.schemas import (
    AccessNodeResponseSchema,
    BoundsSchema,
    CreateScenarioRequest,
    CreateScenarioVariantRequest,
    DuplicateScenarioRequest,
    EndNodeResponseSchema,
    LinkResponseSchema,
    LongleyRiceParamsSchema,
    PropagationSetupSchema,
    RadioConfigResponseSchema,
    ScenarioResponse,
    ScenarioValidationResponse,
    TerrainRefResponseSchema,
    UpdateScenarioRequest,
    ValidationCauseResponse,
)

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


def _format_error(
    code: str, message: str, details: dict[str, object] | None = None
) -> dict[str, object]:
    """Formats standardized API error payloads."""
    return {"code": code, "message": message, "details": details or {}}


def _handle_domain_error(exc: ScenariosDomainError) -> JSONResponse:
    """Maps a ScenariosDomainError to its HTTP status and standardized error body."""
    if isinstance(exc, ScenarioNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_format_error("ScenarioNotFound", str(exc)),
        )
    if isinstance(exc, ProfileNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_format_error("ProfileNotFound", str(exc)),
        )
    if isinstance(exc, InvalidBoundsError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("InvalidBounds", str(exc)),
        )
    if isinstance(exc, AreaOutsideColombiaError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("AreaOutsideColombia", str(exc)),
        )
    if isinstance(exc, AreaTooSmallError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("AreaTooSmall", str(exc)),
        )
    if isinstance(exc, AreaWouldExcludeNodesError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error(
                "AreaWouldExcludeNodes",
                str(exc),
                {"excluded_nodes": exc.excluded_node_names},
            ),
        )
    if isinstance(exc, DemDoesNotCoverAreaError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("DemDoesNotCoverArea", str(exc)),
        )
    if isinstance(exc, DemNotAvailableError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("DemNotAvailable", str(exc)),
        )
    if isinstance(exc, MixedProfileNotAllowedError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("MixedProfileNotAllowed", str(exc)),
        )
    if isinstance(exc, EndNodeAlreadyLinkedError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("EndNodeAlreadyLinked", str(exc)),
        )
    if isinstance(exc, OrphanNodeError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("OrphanNode", str(exc)),
        )
    if isinstance(exc, LinkTooShortError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("LinkTooShort", str(exc)),
        )
    if isinstance(exc, HeightBelowMinimumError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("HeightBelowMinimum", str(exc)),
        )
    if isinstance(exc, NodeOutsideAreaError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("NodeOutsideArea", str(exc)),
        )
    if isinstance(exc, FrequencyOutOfProfileError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("FrequencyOutOfProfile", str(exc)),
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_format_error("ScenariosDomainError", str(exc)),
    )


def _to_propagation_domain(
    schema: PropagationSetupSchema | None,
) -> PropagationSetup | None:
    if schema is None:
        return None
    p = schema.parameters
    return PropagationSetup(
        model_id=schema.model_id,
        schema_version=schema.schema_version,
        parameters=LongleyRiceParams(
            ens0=p.ens0,
            ipol=p.ipol,
            eps=p.eps,
            sgm=p.sgm,
            klim=p.klim,
            mdvar=p.mdvar,
            qc=p.qc,
            qr=tuple(p.qr),
        ),
    )


def _to_scenario_response(scenario: Scenario) -> ScenarioResponse:
    """Converts a domain Scenario aggregate into ScenarioResponse."""
    assert scenario.study_area is not None
    b = scenario.study_area.bounds
    bounds_schema = BoundsSchema(
        south=b.south,
        west=b.west,
        north=b.north,
        east=b.east,
    )
    terrain_schema = (
        TerrainRefResponseSchema(
            dem_id=scenario.terrain_ref.dem_id,
            window=BoundsSchema(
                south=scenario.terrain_ref.window.south,
                west=scenario.terrain_ref.window.west,
                north=scenario.terrain_ref.window.north,
                east=scenario.terrain_ref.window.east,
            ),
        )
        if scenario.terrain_ref is not None
        else None
    )
    radio_schema = (
        RadioConfigResponseSchema(
            profile_id=scenario.radio_config.profile_id,
            technology=scenario.radio_config.technology,
            band_code=scenario.radio_config.band_code,
            frequency_mhz=scenario.radio_config.frequency_mhz,
        )
        if scenario.radio_config is not None
        else None
    )
    prop_schema = (
        PropagationSetupSchema(
            model_id=scenario.propagation_setup.model_id,
            schema_version=scenario.propagation_setup.schema_version,
            parameters=LongleyRiceParamsSchema(
                ens0=scenario.propagation_setup.parameters.ens0,
                ipol=scenario.propagation_setup.parameters.ipol,
                eps=scenario.propagation_setup.parameters.eps,
                sgm=scenario.propagation_setup.parameters.sgm,
                klim=scenario.propagation_setup.parameters.klim,
                mdvar=scenario.propagation_setup.parameters.mdvar,
                qc=scenario.propagation_setup.parameters.qc,
                qr=list(scenario.propagation_setup.parameters.qr),
            ),
        )
        if scenario.propagation_setup is not None
        else None
    )
    return ScenarioResponse(
        id=scenario.id,
        owner_id=scenario.owner_id,
        name=scenario.name,
        description=scenario.description,
        comparison_group_id=scenario.comparison_group_id,
        bounds=bounds_schema,
        terrain_ref=terrain_schema,
        radio_config=radio_schema,
        access_nodes=[
            AccessNodeResponseSchema(
                id=an.id,
                name=an.name,
                lat=an.position.lat,
                lng=an.position.lng,
                height_agl_m=an.height_agl.meters,
                antenna_ref=an.antenna.reference,
                antenna_gain_dbi=an.antenna.gain_dbi,
                polarization=an.antenna.polarization,
                sensitivity_dbm=an.sensitivity_dbm,
                sensitivity_origin=an.sensitivity_origin,
            )
            for an in scenario.deployment.access_nodes
        ],
        end_nodes=[
            EndNodeResponseSchema(
                id=en.id,
                name=en.name,
                lat=en.position.lat,
                lng=en.position.lng,
                height_agl_m=en.height_agl.meters,
                antenna_ref=en.antenna.reference,
                antenna_gain_dbi=en.antenna.gain_dbi,
                polarization=en.antenna.polarization,
                tx_power_nominal_dbm=en.tx_power.nominal_dbm,
                tx_power_tolerance_db=en.tx_power.tolerance_db,
                source_template_id=en.source_template_id,
            )
            for en in scenario.deployment.end_nodes
        ],
        links=[
            LinkResponseSchema(
                id=lk.id,
                end_node_id=lk.end_node_id,
                access_node_id=lk.access_node_id,
            )
            for lk in scenario.deployment.links
        ],
        propagation_setup=prop_schema,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
    )


@router.get("", response_model=list[ScenarioResponse])
def list_scenarios(
    current_user: User = Depends(get_current_user),
    scenario_repo: ScenarioRepository = Depends(get_scenario_repository),
) -> list[ScenarioResponse]:
    """Lists all scenarios owned by the authenticated user (UC-SC-05)."""
    use_case = ListScenarios(scenario_repository=scenario_repo)
    scenarios = use_case.execute(ListScenariosQuery(owner_id=current_user.id))
    return [_to_scenario_response(s) for s in scenarios]


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    body: CreateScenarioRequest,
    current_user: User = Depends(get_current_user),
    scenario_repo: ScenarioRepository = Depends(get_scenario_repository),
    territory_boundary: TerritoryBoundary = Depends(get_scenario_territory_boundary),
    profile_lookup: ProfileLookup = Depends(get_profile_lookup),
    dem_lookup: DemLookup = Depends(get_dem_lookup),
) -> ScenarioResponse | JSONResponse:
    """Creates and persists a new scenario (UC-SC-01)."""
    try:
        bounds = Bounds(
            south=body.bounds.south,
            west=body.bounds.west,
            north=body.bounds.north,
            east=body.bounds.east,
        )
        use_case = CreateScenario(
            scenario_repository=scenario_repo,
            territory_boundary=territory_boundary,
            profile_lookup=profile_lookup,
            dem_lookup=dem_lookup,
        )
        scenario = use_case.execute(
            CreateScenarioCommand(
                owner_id=current_user.id,
                name=body.name,
                description=body.description,
                bounds=bounds,
                dem_id=body.dem_id,
                profile_id=body.profile_id,
                band_code=body.band_code,
                frequency_mhz=body.frequency_mhz,
                access_nodes=[
                    CreateScenarioAccessNodeInput(
                        id=an.id,
                        name=an.name,
                        lat=an.lat,
                        lng=an.lng,
                        height_agl_m=an.height_agl_m,
                        antenna_ref=an.antenna_ref,
                        antenna_gain_dbi=an.antenna_gain_dbi,
                        polarization=an.polarization,
                        sensitivity_dbm=an.sensitivity_dbm,
                        sensitivity_origin=an.sensitivity_origin,
                    )
                    for an in body.access_nodes
                ],
                end_nodes=[
                    CreateScenarioEndNodeInput(
                        id=en.id,
                        name=en.name,
                        lat=en.lat,
                        lng=en.lng,
                        height_agl_m=en.height_agl_m,
                        antenna_ref=en.antenna_ref,
                        antenna_gain_dbi=en.antenna_gain_dbi,
                        polarization=en.polarization,
                        tx_power_nominal_dbm=en.tx_power_nominal_dbm,
                        tx_power_tolerance_db=en.tx_power_tolerance_db,
                        source_template_id=en.source_template_id,
                    )
                    for en in body.end_nodes
                ],
                links=[
                    CreateScenarioLinkInput(
                        id=lk.id,
                        end_node_id=lk.end_node_id,
                        access_node_id=lk.access_node_id,
                    )
                    for lk in body.links
                ],
                propagation_setup=_to_propagation_domain(body.propagation_setup),
            )
        )
        return _to_scenario_response(scenario)
    except ScenariosDomainError as exc:
        return _handle_domain_error(exc)


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: UUID,
    current_user: User = Depends(get_current_user),
    scenario_repo: ScenarioRepository = Depends(get_scenario_repository),
) -> ScenarioResponse | JSONResponse:
    """Retrieves a single scenario owned by the authenticated user."""
    try:
        use_case = GetScenario(scenario_repository=scenario_repo)
        scenario = use_case.execute(
            GetScenarioQuery(scenario_id=scenario_id, owner_id=current_user.id)
        )
        return _to_scenario_response(scenario)
    except ScenariosDomainError as exc:
        return _handle_domain_error(exc)


@router.put("/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario_id: UUID,
    body: UpdateScenarioRequest,
    current_user: User = Depends(get_current_user),
    scenario_repo: ScenarioRepository = Depends(get_scenario_repository),
    territory_boundary: TerritoryBoundary = Depends(get_scenario_territory_boundary),
    profile_lookup: ProfileLookup = Depends(get_profile_lookup),
    dem_lookup: DemLookup = Depends(get_dem_lookup),
) -> ScenarioResponse | JSONResponse:
    """Updates an existing scenario owned by the authenticated user (UC-SC-02)."""
    try:
        bounds = Bounds(
            south=body.bounds.south,
            west=body.bounds.west,
            north=body.bounds.north,
            east=body.bounds.east,
        )
        use_case = UpdateScenario(
            scenario_repository=scenario_repo,
            territory_boundary=territory_boundary,
            profile_lookup=profile_lookup,
            dem_lookup=dem_lookup,
        )
        scenario = use_case.execute(
            UpdateScenarioCommand(
                scenario_id=scenario_id,
                owner_id=current_user.id,
                name=body.name,
                description=body.description,
                bounds=bounds,
                dem_id=body.dem_id,
                profile_id=body.profile_id,
                band_code=body.band_code,
                frequency_mhz=body.frequency_mhz,
                access_nodes=[
                    CreateScenarioAccessNodeInput(
                        id=an.id,
                        name=an.name,
                        lat=an.lat,
                        lng=an.lng,
                        height_agl_m=an.height_agl_m,
                        antenna_ref=an.antenna_ref,
                        antenna_gain_dbi=an.antenna_gain_dbi,
                        polarization=an.polarization,
                        sensitivity_dbm=an.sensitivity_dbm,
                        sensitivity_origin=an.sensitivity_origin,
                    )
                    for an in body.access_nodes
                ],
                end_nodes=[
                    CreateScenarioEndNodeInput(
                        id=en.id,
                        name=en.name,
                        lat=en.lat,
                        lng=en.lng,
                        height_agl_m=en.height_agl_m,
                        antenna_ref=en.antenna_ref,
                        antenna_gain_dbi=en.antenna_gain_dbi,
                        polarization=en.polarization,
                        tx_power_nominal_dbm=en.tx_power_nominal_dbm,
                        tx_power_tolerance_db=en.tx_power_tolerance_db,
                        source_template_id=en.source_template_id,
                    )
                    for en in body.end_nodes
                ],
                links=[
                    CreateScenarioLinkInput(
                        id=lk.id,
                        end_node_id=lk.end_node_id,
                        access_node_id=lk.access_node_id,
                    )
                    for lk in body.links
                ],
                propagation_setup=_to_propagation_domain(body.propagation_setup),
            )
        )
        return _to_scenario_response(scenario)
    except ScenariosDomainError as exc:
        return _handle_domain_error(exc)


@router.post(
    "/{scenario_id}/duplicate",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_scenario(
    scenario_id: UUID,
    body: DuplicateScenarioRequest | None = None,
    current_user: User = Depends(get_current_user),
    scenario_repo: ScenarioRepository = Depends(get_scenario_repository),
) -> ScenarioResponse | JSONResponse:
    """Duplicates an existing scenario with a new comparison_group_id (UC-SC-03)."""
    try:
        use_case = DuplicateScenario(scenario_repository=scenario_repo)
        scenario = use_case.execute(
            DuplicateScenarioCommand(
                scenario_id=scenario_id,
                owner_id=current_user.id,
                name=body.name if body else None,
            )
        )
        return _to_scenario_response(scenario)
    except ScenariosDomainError as exc:
        return _handle_domain_error(exc)


@router.post(
    "/{scenario_id}/variants",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_scenario_variant(
    scenario_id: UUID,
    body: CreateScenarioVariantRequest,
    current_user: User = Depends(get_current_user),
    scenario_repo: ScenarioRepository = Depends(get_scenario_repository),
    profile_lookup: ProfileLookup = Depends(get_profile_lookup),
) -> ScenarioResponse | JSONResponse:
    """Creates a technology variant sharing comparison_group_id (UC-SC-04, RN-29)."""
    try:
        use_case = CreateScenarioVariant(
            scenario_repository=scenario_repo,
            profile_lookup=profile_lookup,
        )
        variant = use_case.execute(
            CreateScenarioVariantCommand(
                scenario_id=scenario_id,
                owner_id=current_user.id,
                target_profile_id=body.target_profile_id,
                band_code=body.band_code,
                frequency_mhz=body.frequency_mhz,
                name=body.name,
            )
        )
        return _to_scenario_response(variant)
    except ScenariosDomainError as exc:
        return _handle_domain_error(exc)


@router.post("/{scenario_id}/validate", response_model=ScenarioValidationResponse)
def validate_scenario(
    scenario_id: UUID,
    current_user: User = Depends(get_current_user),
    scenario_repo: ScenarioRepository = Depends(get_scenario_repository),
    dem_lookup: DemLookup = Depends(get_dem_lookup),
) -> ScenarioValidationResponse | JSONResponse:
    """Validates whether a scenario satisfies all preconditions to simulate (RN-31, AC-16)."""
    try:
        use_case = ValidateScenario(
            scenario_repository=scenario_repo,
            dem_lookup=dem_lookup,
        )
        result = use_case.execute(
            ValidateScenarioQuery(scenario_id=scenario_id, owner_id=current_user.id)
        )
        return ScenarioValidationResponse(
            simulable=result.simulable,
            causes=[ValidationCauseResponse(code=c.code, message=c.message) for c in result.causes],
        )
    except ScenariosDomainError as exc:
        return _handle_domain_error(exc)


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_scenario(
    scenario_id: UUID,
    current_user: User = Depends(get_current_user),
    scenario_repo: ScenarioRepository = Depends(get_scenario_repository),
) -> Response | JSONResponse:
    """Deletes a scenario without deleting its DEM, profile, or simulations (UC-SC-06, RN-30)."""
    try:
        use_case = DeleteScenario(scenario_repository=scenario_repo)
        use_case.execute(DeleteScenarioCommand(scenario_id=scenario_id, owner_id=current_user.id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ScenariosDomainError as exc:
        return _handle_domain_error(exc)
