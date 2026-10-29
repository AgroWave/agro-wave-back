"""FastAPI dependencies for identity and authentication."""

from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from agrowave.modules.identity.domain.models import Role, User
from agrowave.modules.identity.domain.ports import (
    Notifier,
    OneTimeTokenRepository,
    PasswordHasher,
    TokenRevocationRepository,
    TokenService,
    UserRepository,
)
from agrowave.modules.identity.infrastructure.argon2_password_hasher import (
    Argon2PasswordHasher,
)
from agrowave.modules.identity.infrastructure.console_notifier import (
    ConsoleNotifier,
)
from agrowave.modules.identity.infrastructure.jwt_token_service import (
    JwtTokenService,
)
from agrowave.modules.identity.infrastructure.sqlmodel_token_repositories import (
    SqlModelOneTimeTokenRepository,
    SqlModelTokenRevocationRepository,
)
from agrowave.modules.identity.infrastructure.sqlmodel_user_repository import (
    SqlModelUserRepository,
)
from agrowave.settings import get_settings

_engine: Engine | None = None


def set_identity_engine(engine: Engine) -> None:
    """Sets a custom database engine for identity repositories."""
    global _engine
    _engine = engine


def get_identity_engine() -> Engine:
    """Returns database engine for identity repositories."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(str(settings.database_url))
    return _engine


def get_user_repository(
    engine: Engine = Depends(get_identity_engine),
) -> UserRepository:
    """Provides UserRepository implementation."""
    return SqlModelUserRepository(engine)


def get_one_time_token_repository(
    engine: Engine = Depends(get_identity_engine),
) -> OneTimeTokenRepository:
    """Provides OneTimeTokenRepository implementation."""
    return SqlModelOneTimeTokenRepository(engine)


def get_token_revocation_repository(
    engine: Engine = Depends(get_identity_engine),
) -> TokenRevocationRepository:
    """Provides TokenRevocationRepository implementation."""
    return SqlModelTokenRevocationRepository(engine)


def get_password_hasher() -> PasswordHasher:
    """Provides PasswordHasher implementation."""
    return Argon2PasswordHasher()


def get_token_service() -> TokenService:
    """Provides TokenService implementation."""
    settings = get_settings()
    return JwtTokenService(
        secret_key=settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def get_notifier() -> Notifier:
    """Provides Notifier implementation."""
    return ConsoleNotifier()


def get_current_auth_context(
    authorization: str | None = Header(default=None),
    token_service: TokenService = Depends(get_token_service),
    revocation_repo: TokenRevocationRepository = Depends(get_token_revocation_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> tuple[User, str]:
    """Authenticates the incoming Bearer JWT token and returns (User, jti).

    Args:
        authorization: Authorization header value.
        token_service: Token decoding service.
        revocation_repo: Revoked token repository.
        user_repo: User repository.

    Returns:
        Tuple of (User entity, jti string).

    Raises:
        HTTPException: 401 if token is missing, invalid, expired, revoked,
            or if password was changed after token issuance (RN-04, RN-05).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = authorization[7:].strip()
    try:
        payload = token_service.decode_access_token(raw_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    jti = payload.get("jti")
    if not jti or revocation_repo.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_repo.find_by_id(UUID(sub))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Invalidate token if password was changed after token was issued (RN-04)
    iat = payload.get("iat")
    if user.password_changed_at is not None and iat is not None:
        changed_timestamp = int(user.password_changed_at.timestamp())
        if iat < changed_timestamp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password was changed; please log in again",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return user, jti


def get_current_user(
    auth_context: tuple[User, str] = Depends(get_current_auth_context),
) -> User:
    """Returns the authenticated User entity from auth context."""
    return auth_context[0]


def get_current_jti(
    auth_context: tuple[User, str] = Depends(get_current_auth_context),
) -> str:
    """Returns the active JWT ID from auth context."""
    return auth_context[1]


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensures that the authenticated user holds ADMIN role.

    Args:
        current_user: The authenticated user.

    Returns:
        User entity if role is ADMIN.

    Raises:
        HTTPException: 403 Forbidden if role is not ADMIN.
    """
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privilege required",
        )
    return current_user
