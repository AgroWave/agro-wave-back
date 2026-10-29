"""Domain models and value objects for Identity and Access Management."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class Role(StrEnum):
    """User authorization roles."""

    USER = "USER"
    ADMIN = "ADMIN"


class OneTimeTokenPurpose(StrEnum):
    """Purposes for single-use verification tokens."""

    EMAIL_CONFIRMATION = "EMAIL_CONFIRMATION"
    PASSWORD_RESET = "PASSWORD_RESET"


@dataclass
class User:
    """User aggregate root in the identity context.

    Attributes:
        id: Unique identifier of the user.
        email: Unique email address of the user (RN-01).
        name: Full display name of the user.
        password_hash: Securely hashed password.
        role: Assigned system authorization role.
        email_confirmed: Whether the email has been confirmed (RN-02).
        password_changed_at: Timestamp when password was last updated (RN-04).
        created_at: Timestamp when user registered.
    """

    email: str
    name: str
    password_hash: str
    id: UUID = field(default_factory=uuid4)
    role: Role = Role.USER
    email_confirmed: bool = False
    password_changed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def confirm_email(self) -> None:
        """Marks the email as confirmed."""
        self.email_confirmed = True

    def change_password(self, new_password_hash: str) -> None:
        """Updates the password hash and sets password_changed_at timestamp (RN-04).

        Args:
            new_password_hash: New argon2 hashed password string.
        """
        self.password_hash = new_password_hash
        self.password_changed_at = datetime.now(UTC)


@dataclass
class OneTimeToken:
    """Single-use verification token entity (RN-03).

    Attributes:
        id: Unique token record identifier.
        user_id: User identifier to whom this token belongs.
        purpose: Verification purpose (email confirmation or password reset).
        token_hash: SHA-256 hash of the plain token.
        expires_at: Expiration timestamp.
        used_at: Timestamp when the token was consumed, or None.
    """

    user_id: UUID
    purpose: OneTimeTokenPurpose
    token_hash: str
    expires_at: datetime
    id: UUID = field(default_factory=uuid4)
    used_at: datetime | None = None

    def is_valid(self, now: datetime) -> bool:
        """Checks if the token is unused and not expired.

        Args:
            now: Current timestamp in UTC.

        Returns:
            True if token is valid, False otherwise.
        """
        return self.used_at is None and now < self.expires_at

    def mark_used(self, now: datetime) -> None:
        """Marks the token as consumed.

        Args:
            now: Current timestamp in UTC.
        """
        self.used_at = now


@dataclass
class RevokedToken:
    """Revoked JWT token identified by its JTI (RN-05).

    Attributes:
        jti: Unique JWT identifier claim.
        user_id: Identifier of the user who owned the token.
        expires_at: Timestamp when the token expires and can be purged.
    """

    jti: str
    user_id: UUID
    expires_at: datetime
