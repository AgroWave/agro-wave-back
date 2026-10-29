"""Login user use case implementation (UC-ID-03, RN-02)."""

from dataclasses import dataclass
from typing import Any

from agrowave.modules.identity.domain.errors import InvalidCredentialsError, UnconfirmedAccountError
from agrowave.modules.identity.domain.models import User
from agrowave.modules.identity.domain.ports import PasswordHasher, TokenService, UserRepository


@dataclass(frozen=True)
class LoginUserCommand:
    """Command payload for logging in a user."""

    email: str
    password: str


@dataclass(frozen=True)
class LoginResult:
    """Authentication result holding access token and user information."""

    access_token: str
    user: User
    token_type: str = "bearer"


class LoginUser:
    """Authenticates user credentials and issues a signed JWT access token."""

    def __init__(
        self,
        user_repo: UserRepository | Any,
        hasher: PasswordHasher | Any,
        token_service: TokenService | Any,
    ) -> None:
        """Initializes the login use case with dependencies.

        Args:
            user_repo: User repository implementation.
            hasher: Password hasher implementation.
            token_service: Token issuance service implementation.
        """
        self._user_repo = user_repo
        self._hasher = hasher
        self._token_service = token_service

    def execute(self, command: LoginUserCommand) -> LoginResult:
        """Executes user authentication.

        Args:
            command: Login credentials (email and password).

        Returns:
            LoginResult containing the access token and user information.

        Raises:
            InvalidCredentialsError: If credentials do not match any user.
            UnconfirmedAccountError: If the account has not been confirmed yet (RN-02).
        """
        user = self._user_repo.find_by_email(command.email)
        if user is None:
            raise InvalidCredentialsError()

        if not self._hasher.verify(command.password, user.password_hash):
            raise InvalidCredentialsError()

        if not user.email_confirmed:
            raise UnconfirmedAccountError(user.email)

        token = self._token_service.create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role.value,
            expires_in_seconds=900,  # 15 minutes
        )

        return LoginResult(access_token=token, token_type="bearer", user=user)
