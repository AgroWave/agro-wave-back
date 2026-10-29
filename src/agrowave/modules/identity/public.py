"""Public API surface for the Identity module (P4)."""

from uuid import UUID

from agrowave.modules.identity.domain.models import Role, User
from agrowave.modules.identity.domain.ports import UserRepository


class IdentityService:
    """Public facade for other modules querying identity resources."""

    def __init__(self, user_repo: UserRepository) -> None:
        """Initializes the facade with a user repository.

        Args:
            user_repo: User repository port implementation.
        """
        self._user_repo = user_repo

    def get_user_by_id(self, user_id: UUID) -> User | None:
        """Retrieves a user by id."""
        return self._user_repo.find_by_id(user_id)


__all__ = ["IdentityService", "Role", "User"]
