"""Change password use case implementation (UC-ID-06, RN-04)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from agrowave.modules.identity.domain.errors import InvalidPasswordError, UserNotFoundError
from agrowave.modules.identity.domain.ports import PasswordHasher, UserRepository


@dataclass(frozen=True)
class ChangePasswordCommand:
    """Command payload for changing an authenticated user's password."""

    user_id: UUID
    current_password: str
    new_password: str


class ChangePassword:
    """Changes password for a user and updates timestamp (RN-04)."""

    def __init__(
        self,
        user_repo: UserRepository | Any,
        hasher: PasswordHasher | Any,
    ) -> None:
        """Initializes the change password use case with dependencies.

        Args:
            user_repo: User repository implementation.
            hasher: Password hasher implementation.
        """
        self._user_repo = user_repo
        self._hasher = hasher

    def execute(self, command: ChangePasswordCommand) -> None:
        """Executes the password change.

        Args:
            command: Command containing the user id, current password, and new password.

        Raises:
            UserNotFoundError: If the user does not exist.
            InvalidPasswordError: If the provided current password does not match.
        """
        user = self._user_repo.find_by_id(command.user_id)
        if user is None:
            raise UserNotFoundError(str(command.user_id))

        if not self._hasher.verify(command.current_password, user.password_hash):
            raise InvalidPasswordError()

        new_password_hash = self._hasher.hash(command.new_password)
        user.change_password(new_password_hash)
        self._user_repo.save(user)
