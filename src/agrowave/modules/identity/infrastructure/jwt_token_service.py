"""JWT token service implementation using PyJWT."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt

from agrowave.modules.identity.domain.ports import TokenService


class JwtTokenService(TokenService):
    """Adapter implementing TokenService port using PyJWT."""

    def __init__(self, secret_key: str, algorithm: str = "HS256") -> None:
        """Initializes JWT token service with signing secret and algorithm.

        Args:
            secret_key: Symmetric secret key for signing tokens.
            algorithm: JWT signing algorithm name.
        """
        self._secret_key = secret_key
        self._algorithm = algorithm

    def create_access_token(
        self, user_id: UUID, email: str, role: str, expires_in_seconds: int = 900
    ) -> str:
        """Creates a signed JWT access token with JTI and user claims.

        Args:
            user_id: Unique user identifier.
            email: User email address.
            role: Authorization role name.
            expires_in_seconds: Token validity duration in seconds (defaults to 15 min).

        Returns:
            Encoded JWT token string.
        """
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """Decodes and validates a signed JWT token.

        Args:
            token: Encoded JWT string.

        Returns:
            Dictionary containing the verified payload claims.

        Raises:
            jwt.PyJWTError: If the token signature is invalid or expired.
        """
        payload: dict[str, Any] = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        return payload
