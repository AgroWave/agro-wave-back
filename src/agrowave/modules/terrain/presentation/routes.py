"""FastAPI router for DEM terrain operations."""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from fastapi.responses import JSONResponse

from agrowave.modules.identity.domain.models import User
from agrowave.modules.identity.presentation.dependencies import get_current_user
from agrowave.modules.terrain.application.use_cases.delete_dem import (
    DeleteDem,
    DeleteDemCommand,
)
from agrowave.modules.terrain.application.use_cases.get_dem import GetDem, GetDemQuery
from agrowave.modules.terrain.application.use_cases.list_dems import (
    ListDems,
    ListDemsQuery,
)
from agrowave.modules.terrain.application.use_cases.process_dem_download import (
    ProcessDemDownload,
    ProcessDemDownloadCommand,
)
from agrowave.modules.terrain.application.use_cases.request_dem_download import (
    RequestDemDownload,
    RequestDemDownloadCommand,
)
from agrowave.modules.terrain.application.use_cases.update_dem import (
    UpdateDem,
    UpdateDemCommand,
)
from agrowave.modules.terrain.domain.errors import (
    AreaOutsideColombiaError,
    AreaTooSmallError,
    DemNotFoundError,
    InvalidBoundsError,
    ResourceInUseError,
)
from agrowave.modules.terrain.domain.models import Bounds, Dem
from agrowave.modules.terrain.domain.ports import (
    DemObjectStore,
    DemRepository,
    DemUsageQuery,
    ElevationSource,
    TerritoryBoundary,
)
from agrowave.modules.terrain.presentation.dependencies import (
    get_dem_object_store,
    get_dem_repository,
    get_dem_usage_query,
    get_elevation_source,
    get_territory_boundary,
)
from agrowave.modules.terrain.presentation.schemas import (
    BoundsSchema,
    CreateDemRequest,
    DemResponse,
    UpdateDemRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dems", tags=["Terrain"])


def _format_error(code: str, message: str) -> dict[str, object]:
    """Formats standardized API error payloads."""
    return {"code": code, "message": message, "details": {}}


def _to_dem_response(dem: Dem) -> DemResponse:
    """Converts domain Dem entity to API response schema."""
    return DemResponse(
        id=dem.id,
        name=dem.name,
        description=dem.description,
        bounds=BoundsSchema(
            south=dem.bounds.south,
            west=dem.bounds.west,
            north=dem.bounds.north,
            east=dem.bounds.east,
        ),
        status=dem.status.value,
        resolution_m=dem.resolution_m,
        object_key=dem.object_key,
        size_bytes=dem.size_bytes,
        failure_reason=dem.failure_reason,
        created_at=dem.created_at,
        updated_at=dem.updated_at,
    )


def _run_process_dem_download_job(
    dem_id: UUID,
    repo: DemRepository,
    elevation_source: ElevationSource,
    object_store: DemObjectStore,
) -> None:
    """Background task function executing FABDEM download and COG upload."""
    try:
        job = ProcessDemDownload(
            repo=repo,
            elevation_source=elevation_source,
            object_store=object_store,
        )
        job.execute(ProcessDemDownloadCommand(dem_id=dem_id))
    except Exception as exc:
        logger.error("Error executing background DEM download for %s: %s", dem_id, exc)


@router.post("", response_model=DemResponse, status_code=status.HTTP_202_ACCEPTED)
def request_dem_download(
    body: CreateDemRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    dem_repo: DemRepository = Depends(get_dem_repository),
    territory_boundary: TerritoryBoundary = Depends(get_territory_boundary),
    elevation_source: ElevationSource = Depends(get_elevation_source),
    dem_object_store: DemObjectStore = Depends(get_dem_object_store),
) -> DemResponse | JSONResponse:
    """Requests a new DEM tile download asynchronously (AC-03-01)."""
    try:
        bounds = Bounds(
            south=body.bounds.south,
            west=body.bounds.west,
            north=body.bounds.north,
            east=body.bounds.east,
        )
        use_case = RequestDemDownload(repo=dem_repo, territory_boundary=territory_boundary)
        dem = use_case.execute(
            RequestDemDownloadCommand(
                owner_id=current_user.id,
                name=body.name,
                description=body.description,
                bounds=bounds,
            )
        )
        background_tasks.add_task(
            _run_process_dem_download_job,
            dem.id,
            dem_repo,
            elevation_source,
            dem_object_store,
        )
        return _to_dem_response(dem)
    except InvalidBoundsError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("InvalidBounds", str(exc)),
        )
    except AreaTooSmallError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("AreaTooSmall", str(exc)),
        )
    except AreaOutsideColombiaError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("AreaOutsideColombia", str(exc)),
        )


@router.get("", response_model=list[DemResponse])
def list_dems(
    search: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    dem_repo: DemRepository = Depends(get_dem_repository),
) -> list[DemResponse]:
    """Lists DEMs owned by the authenticated user (AC-03-07)."""
    use_case = ListDems(repo=dem_repo)
    dems = use_case.execute(ListDemsQuery(owner_id=current_user.id, search=search))
    return [_to_dem_response(d) for d in dems]


@router.get("/{dem_id}", response_model=DemResponse)
def get_dem(
    dem_id: UUID,
    current_user: User = Depends(get_current_user),
    dem_repo: DemRepository = Depends(get_dem_repository),
) -> DemResponse | JSONResponse:
    """Retrieves a single DEM by identifier (AC-03-08, AC-03-11)."""
    try:
        use_case = GetDem(repo=dem_repo)
        dem = use_case.execute(GetDemQuery(dem_id=dem_id, user_id=current_user.id))
        return _to_dem_response(dem)
    except DemNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_format_error("DemNotFound", str(exc)),
        )


@router.patch("/{dem_id}", response_model=DemResponse)
def update_dem(
    dem_id: UUID,
    body: UpdateDemRequest,
    current_user: User = Depends(get_current_user),
    dem_repo: DemRepository = Depends(get_dem_repository),
) -> DemResponse | JSONResponse:
    """Updates metadata for a DEM (AC-03-08, AC-03-11)."""
    try:
        use_case = UpdateDem(repo=dem_repo)
        dem = use_case.execute(
            UpdateDemCommand(
                dem_id=dem_id,
                user_id=current_user.id,
                name=body.name,
                description=body.description,
            )
        )
        return _to_dem_response(dem)
    except DemNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_format_error("DemNotFound", str(exc)),
        )


@router.delete(
    "/{dem_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_dem(
    dem_id: UUID,
    current_user: User = Depends(get_current_user),
    dem_repo: DemRepository = Depends(get_dem_repository),
    dem_object_store: DemObjectStore = Depends(get_dem_object_store),
    dem_usage_query: DemUsageQuery = Depends(get_dem_usage_query),
) -> Response | JSONResponse:
    """Deletes a DEM from database and object storage (AC-03-09, AC-03-10, RN-28)."""
    try:
        use_case = DeleteDem(
            repo=dem_repo,
            object_store=dem_object_store,
            usage_query=dem_usage_query,
        )
        use_case.execute(DeleteDemCommand(dem_id=dem_id, user_id=current_user.id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except DemNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_format_error("DemNotFound", str(exc)),
        )
    except ResourceInUseError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_format_error("ResourceInUse", str(exc)),
        )

