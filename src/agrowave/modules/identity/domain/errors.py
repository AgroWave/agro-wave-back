"""Domain errors for the Identity module."""


class IdentityDomainError(Exception):
    """Base exception for all identity domain errors."""


class DuplicateEmailError(IdentityDomainError):
    """Raised when registering an email that already exists (RN-01)."""

    def __init__(self, email: str) -> None:
        """Initializes with the conflicting email address."""
        super().__init__(f"Email '{email}' is already registered.")
        self.email = email


class UnconfirmedAccountError(IdentityDomainError):
    """Raised when attempting login on an unconfirmed account (RN-02)."""

    def __init__(self, email: str) -> None:
        """Initializes with the unconfirmed email address."""
        super().__init__(f"Account for '{email}' has not been confirmed.")
        self.email = email


class InvalidOrExpiredTokenError(IdentityDomainError):
    """Raised when a single-use token is missing, already used, or expired (RN-03)."""

    def __init__(self) -> None:
        """Initializes with a static description."""
        super().__init__("The verification token is invalid or has expired.")


class InvalidCredentialsError(IdentityDomainError):
    """Raised when email or password is incorrect."""

    def __init__(self) -> None:
        """Initializes with a generic credentials failure message."""
        super().__init__("Invalid email or password.")


class UserNotFoundError(IdentityDomainError):
    """Raised when a requested user does not exist."""

    def __init__(self, identifier: str) -> None:
        """Initializes with the user identifier that was not found."""
        super().__init__(f"User '{identifier}' not found.")
        self.identifier = identifier


class InvalidPasswordError(IdentityDomainError):
    """Raised when the current password provided for change is incorrect."""

    def __init__(self) -> None:
        """Initializes with a password mismatch message."""
        super().__init__("Current password does not match.")
