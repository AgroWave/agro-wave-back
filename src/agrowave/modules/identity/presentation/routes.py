"""FastAPI router for identity and authentication endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from agrowave.modules.identity.application.use_cases.change_password import (
    ChangePassword,
    ChangePasswordCommand,
)
from agrowave.modules.identity.application.use_cases.confirm_email import (
    ConfirmEmail,
    ConfirmEmailCommand,
)
from agrowave.modules.identity.application.use_cases.login import (
    LoginUser,
    LoginUserCommand,
)
from agrowave.modules.identity.application.use_cases.logout import (
    LogoutUser,
    LogoutUserCommand,
)
from agrowave.modules.identity.application.use_cases.register import (
    RegisterUser,
    RegisterUserCommand,
)
from agrowave.modules.identity.application.use_cases.request_password_reset import (
    RequestPasswordReset,
    RequestPasswordResetCommand,
)
from agrowave.modules.identity.application.use_cases.reset_password import (
    ResetPassword,
    ResetPasswordCommand,
)
from agrowave.modules.identity.domain.errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidOrExpiredTokenError,
    InvalidPasswordError,
    UnconfirmedAccountError,
)
from agrowave.modules.identity.domain.models import User
from agrowave.modules.identity.domain.ports import (
    Notifier,
    OneTimeTokenRepository,
    PasswordHasher,
    TokenRevocationRepository,
    TokenService,
    UserRepository,
)
from agrowave.modules.identity.presentation.dependencies import (
    get_current_jti,
    get_current_user,
    get_notifier,
    get_one_time_token_repository,
    get_password_hasher,
    get_token_revocation_repository,
    get_token_service,
    get_user_repository,
)
from agrowave.modules.identity.presentation.schemas import (
    AuthTokenResponse,
    ChangePasswordRequest,
    ConfirmEmailRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    payload: RegisterRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: OneTimeTokenRepository = Depends(get_one_time_token_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
    notifier: Notifier = Depends(get_notifier),
) -> UserResponse | JSONResponse:
    """Registers a new user and sends email confirmation token (AC-29, AC-01-01)."""
    try:
        user = RegisterUser(
            user_repo=user_repo,
            token_repo=token_repo,
            hasher=hasher,
            notifier=notifier,
        ).execute(
            RegisterUserCommand(
                email=str(payload.email),
                name=payload.name,
                password=payload.password,
            )
        )
        return UserResponse.model_validate(user)
    except DuplicateEmailError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"code": "DuplicateEmail", "detail": str(exc)},
        )


@router.post(
    "/confirm-email",
    response_model=MessageResponse,
    summary="Confirm email address with verification token",
)
def confirm_email(
    payload: ConfirmEmailRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: OneTimeTokenRepository = Depends(get_one_time_token_repository),
) -> MessageResponse | JSONResponse:
    """Consumes email verification token to activate user account (AC-01-02)."""
    try:
        ConfirmEmail(user_repo=user_repo, token_repo=token_repo).execute(
            ConfirmEmailCommand(token=payload.token)
        )
        return MessageResponse(message="Email confirmed successfully")
    except InvalidOrExpiredTokenError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": "InvalidOrExpiredToken", "detail": str(exc)},
        )


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    summary="Authenticate and obtain JWT access token",
)
def login(
    payload: LoginRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
    token_service: TokenService = Depends(get_token_service),
) -> AuthTokenResponse | JSONResponse:
    """Authenticates credentials and returns signed JWT (AC-30, AC-01-03)."""
    try:
        result = LoginUser(
            user_repo=user_repo,
            hasher=hasher,
            token_service=token_service,
        ).execute(
            LoginUserCommand(
                email=str(payload.email),
                password=payload.password,
            )
        )
        return AuthTokenResponse(
            access_token=result.access_token,
            token_type=result.token_type,
            user=UserResponse.model_validate(result.user),
        )
    except InvalidCredentialsError as exc:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"code": "InvalidCredentials", "detail": str(exc)},
        )
    except UnconfirmedAccountError as exc:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"code": "UnconfirmedAccount", "detail": str(exc)},
        )


@router.post(
    "/request-password-reset",
    response_model=MessageResponse,
    summary="Request password reset email",
)
def request_password_reset(
    payload: RequestPasswordResetRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: OneTimeTokenRepository = Depends(get_one_time_token_repository),
    notifier: Notifier = Depends(get_notifier),
) -> MessageResponse:
    """Generates reset token and dispatches email if account exists (AC-01-06)."""
    RequestPasswordReset(
        user_repo=user_repo,
        token_repo=token_repo,
        notifier=notifier,
    ).execute(RequestPasswordResetCommand(email=str(payload.email)))
    return MessageResponse(
        message="If the email is registered, a password reset link has been sent"
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using reset token",
)
def reset_password(
    payload: ResetPasswordRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: OneTimeTokenRepository = Depends(get_one_time_token_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
) -> MessageResponse | JSONResponse:
    """Consumes reset token and sets new password (AC-31)."""
    try:
        ResetPassword(
            user_repo=user_repo,
            token_repo=token_repo,
            hasher=hasher,
        ).execute(
            ResetPasswordCommand(
                token=payload.token,
                new_password=payload.new_password,
            )
        )
        return MessageResponse(message="Password reset successfully")
    except InvalidOrExpiredTokenError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": "InvalidOrExpiredToken", "detail": str(exc)},
        )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password for authenticated user",
)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
) -> MessageResponse | JSONResponse:
    """Updates password and marks previous tokens invalidated (AC-01-07)."""
    try:
        ChangePassword(
            user_repo=user_repo,
            hasher=hasher,
        ).execute(
            ChangePasswordCommand(
                user_id=current_user.id,
                current_password=payload.current_password,
                new_password=payload.new_password,
            )
        )
        return MessageResponse(message="Password changed successfully")
    except InvalidPasswordError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": "InvalidPassword", "detail": str(exc)},
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout and revoke active access token",
)
def logout(
    current_user: User = Depends(get_current_user),
    jti: str = Depends(get_current_jti),
    revocation_repo: TokenRevocationRepository = Depends(get_token_revocation_repository),
) -> MessageResponse:
    """Revokes active token JTI in revocation store (AC-01-05)."""
    LogoutUser(revocation_repo=revocation_repo).execute(
        LogoutUserCommand(
            jti=jti,
            user_id=current_user.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    return MessageResponse(message="Logged out successfully")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retrieve authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Returns profile for currently authenticated user (AC-01-04)."""
    return UserResponse.model_validate(current_user)
