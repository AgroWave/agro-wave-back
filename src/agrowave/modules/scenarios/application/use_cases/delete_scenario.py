"""Use case for deleting a scenario (UC-SC-06, RN-30)."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.scenarios.domain.errors import ScenarioNotFoundError
from agrowave.modules.scenarios.domain.ports import ScenarioRepository


@dataclass(frozen=True)
class DeleteScenarioCommand:
    """Command to delete a scenario owned by a user."""

    scenario_id: UUID
    owner_id: UUID


class DeleteScenario:
    """Deletes a scenario without deleting its associated DEM, profile, or simulations (RN-30)."""

    def __init__(self, scenario_repository: ScenarioRepository) -> None:
        """Initializes DeleteScenario.

        Args:
            scenario_repository: Scenario repository port.
        """
        self._repo = scenario_repository

    def execute(self, command: DeleteScenarioCommand) -> None:
        """Deletes the scenario if owned by command.owner_id.

        Args:
            command: Scenario ID and owner ID.

        Raises:
            ScenarioNotFoundError: If not found or owned by another user.
        """
        scenario = self._repo.get_by_id(command.scenario_id)
        if scenario is None or scenario.owner_id != command.owner_id:
            raise ScenarioNotFoundError()
        self._repo.delete(command.scenario_id)
