"""Ports (abstract interfaces) for the Identity domain."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from agrowave.modules.identity.domain.models import (
    OneTimeToken,
    OneTimeTokenPurpose,
    RevokedToken,
    User,
)


class UserRepository(ABC):
    """Port for persisting and querying User entities."""

    @abstractmethod
    def find_by_id(self, user_id: UUID) -> User | None:
        """Finds a user by their unique identifier."""

    @abstractmethod
    def find_by_email(self, email: str) -> User | None:
        """Finds a user by their unique email address."""

    @abstractmethod
    def save(self, user: User) -> None:
        """Saves or updates a user entity."""


class OneTimeTokenRepository(ABC):
    """Port for persisting and verifying single-use tokens."""

    @abstractmethod
    def find_by_hash_and_purpose(
        self, token_hash: str, purpose: OneTimeTokenPurpose
    ) -> OneTimeToken | None:
        """Finds a token by its hash and intended purpose."""

    @abstractmethod
    def save(self, token: OneTimeToken) -> None:
        """Saves or updates a single-use token."""


class TokenRevocationRepository(ABC):
    """Port for tracking and verifying revoked JWT identifiers (JTI)."""

    @abstractmethod
    def is_revoked(self, jti: str) -> bool:
        """Checks if a given token JTI is registered as revoked."""

    @abstractmethod
    def save(self, revoked_token: RevokedToken) -> None:
        """Registers a token JTI as revoked."""


class PasswordHasher(ABC):
    """Port for cryptographic password hashing and verification."""

    @abstractmethod
    def hash(self, password: str) -> str:
        """Generates a secure hash from a plain text password."""

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool:
        """Verifies that a plain text password matches the hash."""


class TokenService(ABC):
    """Port for JWT access token encoding and decoding."""

    @abstractmethod
    def create_access_token(
        self, user_id: UUID, email: str, role: str, expires_in_seconds: int = 900
    ) -> str:
        """Creates a signed JWT access token."""

    @abstractmethod
    def decode_access_token(self, token: str) -> dict[str, Any]:
        """Decodes and validates a signed JWT access token."""


class Notifier(ABC):
    """Port for dispatching transactional notification emails."""

    @abstractmethod
    def send_confirmation_email(self, to_email: str, token: str) -> None:
        """Sends an account confirmation link to the recipient."""

    @abstractmethod
    def send_password_reset_email(self, to_email: str, token: str) -> None:
        """Sends a password reset link to the recipient."""
