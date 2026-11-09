"""Use case for listing scenarios owned by a user (UC-SC-05)."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.scenarios.domain.models import Scenario
from agrowave.modules.scenarios.domain.ports import ScenarioRepository


@dataclass(frozen=True)
class ListScenariosQuery:
    """Query to list scenarios owned by a user."""

    owner_id: UUID


class ListScenarios:
    """Lists all scenarios owned by the authenticated user (RN-04)."""

    def __init__(self, scenario_repository: ScenarioRepository) -> None:
        """Initializes ListScenarios.

        Args:
            scenario_repository: Scenario repository port.
        """
        self._repo = scenario_repository

    def execute(self, query: ListScenariosQuery) -> list[Scenario]:
        """Returns scenarios belonging to query.owner_id.

        Args:
            query: Owner user ID.

        Returns:
            List of Scenario aggregates.
        """
        return self._repo.list_by_owner(query.owner_id)
