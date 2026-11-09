"""Use case for querying a single scenario by ID (UC-SC-05)."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.scenarios.domain.errors import ScenarioNotFoundError
from agrowave.modules.scenarios.domain.models import Scenario
from agrowave.modules.scenarios.domain.ports import ScenarioRepository


@dataclass(frozen=True)
class GetScenarioQuery:
    """Query to retrieve a scenario owned by a user."""

    scenario_id: UUID
    owner_id: UUID


class GetScenario:
    """Retrieves a scenario owned by the authenticated user."""

    def __init__(self, scenario_repository: ScenarioRepository) -> None:
        """Initializes GetScenario.

        Args:
            scenario_repository: Scenario repository port.
        """
        self._repo = scenario_repository

    def execute(self, query: GetScenarioQuery) -> Scenario:
        """Retrieves the requested Scenario or raises ScenarioNotFoundError (RN-04).

        Args:
            query: Scenario ID and owner ID.

        Returns:
            Scenario aggregate.

        Raises:
            ScenarioNotFoundError: If not found or owned by another user.
        """
        scenario = self._repo.get_by_id(query.scenario_id)
        if scenario is None or scenario.owner_id != query.owner_id:
            raise ScenarioNotFoundError()
        return scenario
