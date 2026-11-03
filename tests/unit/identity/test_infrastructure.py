"""Unit tests for identity infrastructure adapters (argon2, jwt, console notifier)."""

from uuid import uuid4

from agrowave.modules.identity.infrastructure.argon2_password_hasher import Argon2PasswordHasher
from agrowave.modules.identity.infrastructure.jwt_token_service import JwtTokenService


def test_argon2_password_hasher_hashes_and_verifies_correctly() -> None:
    hasher = Argon2PasswordHasher()
    plain = "MySecretPassword123!"

    hashed = hasher.hash(plain)

    assert hashed != plain
    assert hasher.verify(plain, hashed) is True
    assert hasher.verify("WrongPassword", hashed) is False


def test_jwt_token_service_encodes_and_decodes_claims() -> None:
    service = JwtTokenService(
        secret_key="test-secret-key-for-jwt-that-is-at-least-32-bytes-long", algorithm="HS256"
    )
    user_id = uuid4()
    email = "test@example.com"
    role = "USER"

    token = service.create_access_token(
        user_id=user_id, email=email, role=role, expires_in_seconds=900
    )

    payload = service.decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["role"] == role
    assert "jti" in payload
    assert "exp" in payload
