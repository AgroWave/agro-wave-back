"""Temporary ProfileUsageQuery adapter that reports no usage.

It returns False until the scenarios module is implemented (INC-04).
"""

from uuid import UUID

from agrowave.modules.profiles.domain.ports import ProfileUsageQuery


class NoScenariosProfileUsageQuery(ProfileUsageQuery):
    """Query port implementation before scenarios module exists."""

    def is_profile_in_use(self, profile_id: UUID) -> bool:
        """Always returns False as no scenarios exist yet (RN-09).

        Args:
            profile_id: Profile UUID.

        Returns:
            False.
        """
        return False
