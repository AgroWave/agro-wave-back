"""Argon2 password hasher implementation."""

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import VerifyMismatchError

from agrowave.modules.identity.domain.ports import PasswordHasher


class Argon2PasswordHasher(PasswordHasher):
    """Adapter implementing PasswordHasher port using argon2-cffi."""

    def __init__(self) -> None:
        """Initializes Argon2 password hasher with default parameters."""
        self._hasher = Argon2Hasher()

    def hash(self, password: str) -> str:
        """Hashes a password with Argon2.

        Args:
            password: Plain text password.

        Returns:
            Argon2 encoded hash string.
        """
        return self._hasher.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        """Verifies a plain password against an Argon2 hash.

        Args:
            password: Plain text password to check.
            hashed: Existing Argon2 hash string.

        Returns:
            True if password matches, False otherwise.
        """
        try:
            return self._hasher.verify(hashed, password)
        except VerifyMismatchError:
            return False
        except Exception:
            return False
