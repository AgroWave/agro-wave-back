"""FastAPI router for LPWAN profiles endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse

from agrowave.modules.identity.domain.models import User
from agrowave.modules.identity.presentation.dependencies import get_current_user
from agrowave.modules.profiles.application.use_cases.create_profile import (
    CreateProfile,
    CreateProfileCommand,
)
from agrowave.modules.profiles.application.use_cases.delete_profile import (
    DeleteProfile,
    DeleteProfileCommand,
)
from agrowave.modules.profiles.application.use_cases.duplicate_profile import (
    DuplicateProfile,
    DuplicateProfileCommand,
)
from agrowave.modules.profiles.application.use_cases.list_node_templates import (
    ListNodeTemplates,
    ListNodeTemplatesQuery,
)
from agrowave.modules.profiles.application.use_cases.list_profiles import (
    ListProfiles,
    ListProfilesQuery,
)
from agrowave.modules.profiles.application.use_cases.update_profile import (
    UpdateProfile,
    UpdateProfileCommand,
)
from agrowave.modules.profiles.domain.errors import (
    InvalidBandRangeError,
    PredefinedProfileReadOnlyError,
    ProfileNotFoundError,
    ResourceInUseError,
    SpreadingFactorNotAllowedError,
)
from agrowave.modules.profiles.domain.models import Band, LpwanProfile, NodeTemplate, Technology
from agrowave.modules.profiles.domain.ports import (
    NodeTemplateRepository,
    ProfileRepository,
    ProfileUsageQuery,
)
from agrowave.modules.profiles.presentation.dependencies import (
    get_node_template_repository,
    get_profile_repository,
    get_profile_usage_query,
)
from agrowave.modules.profiles.presentation.schemas import (
    AntennaResponse,
    BandResponse,
    CreateProfileRequest,
    DuplicateProfileRequest,
    NodeTemplateResponse,
    ProfileResponse,
    TxPowerResponse,
    UpdateProfileRequest,
)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


def _format_error(
    code: str, message: str, details: dict[str, object] | None = None
) -> dict[str, object]:
    """Formats error responses according to the API contract."""
    return {"code": code, "message": message, "details": details or {}}


def _to_profile_response(profile: LpwanProfile) -> ProfileResponse:
    """Maps domain profile entity to Pydantic response."""
    return ProfileResponse(
        id=profile.id,
        name=profile.name,
        technology=profile.technology,
        reference_sensitivity_dbm=profile.reference_sensitivity_dbm,
        bands=[
            BandResponse(code=b.code, min_mhz=b.min_mhz, max_mhz=b.max_mhz) for b in profile.bands
        ],
        spreading_factor=profile.spreading_factor,
        owner_id=profile.owner_id,
        is_predefined=profile.is_predefined,
        created_at=profile.created_at,
    )


def _to_template_response(template: NodeTemplate) -> NodeTemplateResponse:
    """Maps domain node template entity to Pydantic response."""
    tx_power = (
        TxPowerResponse(
            nominal_dbm=template.tx_power.nominal_dbm,
            tolerance_db=template.tx_power.tolerance_db,
        )
        if template.tx_power is not None
        else None
    )
    antenna = AntennaResponse(
        reference=template.antenna.reference,
        gain_dbi=template.antenna.gain_dbi,
        polarization=template.antenna.polarization,
    )
    return NodeTemplateResponse(
        id=template.id,
        technology=template.technology,
        role=template.role,
        name=template.name,
        module_ref=template.module_ref,
        antenna=antenna,
        tx_power=tx_power,
    )


@router.get("", response_model=list[ProfileResponse])
def list_profiles(
    technology: Technology | None = Query(default=None),
    owner: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
) -> list[ProfileResponse]:
    """Lists predefined profiles and profiles owned by the current user (AC-02-03)."""
    use_case = ListProfiles(profile_repo)
    profiles = use_case.execute(
        ListProfilesQuery(
            user_id=current_user.id,
            technology=technology,
            owner=owner,
        )
    )
    return [_to_profile_response(p) for p in profiles]


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    body: CreateProfileRequest,
    current_user: User = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
) -> ProfileResponse | JSONResponse:
    """Creates a custom LPWAN profile owned by the current user (AC-02-04)."""
    bands = [Band(code=b.code, min_mhz=b.min_mhz, max_mhz=b.max_mhz) for b in body.bands]
    use_case = CreateProfile(profile_repo)
    try:
        profile = use_case.execute(
            CreateProfileCommand(
                user_id=current_user.id,
                name=body.name,
                technology=body.technology,
                reference_sensitivity_dbm=body.reference_sensitivity_dbm,
                bands=bands,
                spreading_factor=body.spreading_factor,
            )
        )
        return _to_profile_response(profile)
    except SpreadingFactorNotAllowedError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("SpreadingFactorNotAllowed", str(exc)),
        )
    except InvalidBandRangeError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("InvalidBandRange", str(exc)),
        )


@router.patch("/{profile_id}", response_model=ProfileResponse)
def update_profile(
    profile_id: UUID,
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
    usage_query: ProfileUsageQuery = Depends(get_profile_usage_query),
) -> ProfileResponse | JSONResponse:
    """Updates an owned LPWAN profile (RN-09, RN-10)."""
    bands = (
        [Band(code=b.code, min_mhz=b.min_mhz, max_mhz=b.max_mhz) for b in body.bands]
        if body.bands is not None
        else None
    )
    use_case = UpdateProfile(profile_repo, usage_query)
    try:
        profile = use_case.execute(
            UpdateProfileCommand(
                profile_id=profile_id,
                user_id=current_user.id,
                name=body.name,
                reference_sensitivity_dbm=body.reference_sensitivity_dbm,
                bands=bands,
                spreading_factor=body.spreading_factor,
            )
        )
        return _to_profile_response(profile)
    except ProfileNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_format_error("ProfileNotFound", str(exc)),
        )
    except PredefinedProfileReadOnlyError as exc:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_format_error("PredefinedProfileReadOnly", str(exc)),
        )
    except ResourceInUseError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_format_error("ResourceInUse", str(exc)),
        )
    except SpreadingFactorNotAllowedError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("SpreadingFactorNotAllowed", str(exc)),
        )
    except InvalidBandRangeError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_format_error("InvalidBandRange", str(exc)),
        )


@router.post(
    "/{profile_id}/duplicate",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_profile(
    profile_id: UUID,
    body: DuplicateProfileRequest | None = None,
    current_user: User = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
) -> ProfileResponse | JSONResponse:
    """Duplicates a predefined or owned profile into a custom profile (AC-27)."""
    use_case = DuplicateProfile(profile_repo)
    try:
        target_name = body.name if body is not None else None
        clone = use_case.execute(
            DuplicateProfileCommand(
                profile_id=profile_id,
                user_id=current_user.id,
                name=target_name,
            )
        )
        return _to_profile_response(clone)
    except ProfileNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_format_error("ProfileNotFound", str(exc)),
        )


@router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_profile(
    profile_id: UUID,
    current_user: User = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
    usage_query: ProfileUsageQuery = Depends(get_profile_usage_query),
) -> Response:
    """Deletes an owned LPWAN profile (RN-09, RN-10)."""
    use_case = DeleteProfile(profile_repo, usage_query)
    try:
        use_case.execute(
            DeleteProfileCommand(
                profile_id=profile_id,
                user_id=current_user.id,
            )
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProfileNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_format_error("ProfileNotFound", str(exc)),
        )
    except PredefinedProfileReadOnlyError as exc:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_format_error("PredefinedProfileReadOnly", str(exc)),
        )
    except ResourceInUseError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_format_error("ResourceInUse", str(exc)),
        )


@router.get("/{profile_id}/node-templates", response_model=list[NodeTemplateResponse])
def list_profile_node_templates(
    profile_id: UUID,
    current_user: User = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
    template_repo: NodeTemplateRepository = Depends(get_node_template_repository),
) -> list[NodeTemplateResponse] | JSONResponse:
    """Lists reference node templates for a profile's technology (AC-02-07)."""
    use_case = ListNodeTemplates(profile_repo, template_repo)
    try:
        templates = use_case.execute(
            ListNodeTemplatesQuery(
                profile_id=profile_id,
                user_id=current_user.id,
            )
        )
        return [_to_template_response(t) for t in templates]
    except ProfileNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_format_error("ProfileNotFound", str(exc)),
        )
