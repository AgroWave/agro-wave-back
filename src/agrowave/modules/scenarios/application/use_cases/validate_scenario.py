"""Use case for validating whether a scenario is ready to simulate (RN-31, AC-16)."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.scenarios.domain.errors import ScenarioNotFoundError
from agrowave.modules.scenarios.domain.models import ValidationCause
from agrowave.modules.scenarios.domain.ports import DemLookup, ScenarioRepository


@dataclass(frozen=True)
class ValidateScenarioQuery:
    """Query to check if a scenario is ready for simulation."""

    scenario_id: UUID
    owner_id: UUID


@dataclass(frozen=True)
class ScenarioValidationResult:
    """Result of validating a scenario for simulation (RN-31).

    Attributes:
        simulable: True if all prerequisites for simulation are satisfied.
        causes: Tuple of blocking causes when simulable is False.
    """

    simulable: bool
    causes: tuple[ValidationCause, ...]


class ValidateScenario:
    """Evaluates whether a scenario is complete and ready to simulate (RN-31, AC-16)."""

    def __init__(
        self,
        scenario_repository: ScenarioRepository,
        dem_lookup: DemLookup,
    ) -> None:
        """Initializes ValidateScenario.

        Args:
            scenario_repository: Scenario repository port.
            dem_lookup: Port for looking up DEM availability status.
        """
        self._repo = scenario_repository
        self._dems = dem_lookup

    def execute(self, query: ValidateScenarioQuery) -> ScenarioValidationResult:
        """Evaluates simulation readiness for the specified scenario.

        Args:
            query: Scenario ID and owner ID.

        Returns:
            ScenarioValidationResult with simulable flag and blocking causes.

        Raises:
            ScenarioNotFoundError: If not found or not owned by user.
        """
        scenario = self._repo.get_by_id(query.scenario_id)
        if scenario is None or scenario.owner_id != query.owner_id:
            raise ScenarioNotFoundError()

        dem_available = False
        if scenario.terrain_ref is not None:
            dem_info = self._dems.get_dem(scenario.terrain_ref.dem_id, query.owner_id)
            if dem_info is not None and dem_info.status == "AVAILABLE":
                dem_available = True

        causes = tuple(scenario.validate_for_simulation(dem_available=dem_available))
        return ScenarioValidationResult(
            simulable=len(causes) == 0,
            causes=causes,
        )
