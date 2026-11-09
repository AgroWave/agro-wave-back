"""Public API for the scenarios bounded context (P4: interfaces between modules)."""

from uuid import UUID

from agrowave.modules.scenarios.domain.models import Scenario
from agrowave.modules.scenarios.domain.ports import ScenarioRepository


class ScenariosService:
    """Public facade exposing scenario queries to other bounded contexts."""

    def __init__(self, scenario_repository: ScenarioRepository) -> None:
        """Initializes the scenarios public service facade.

        Args:
            scenario_repository: Scenario repository port.
        """
        self._repo = scenario_repository

    def get_scenario(self, scenario_id: UUID) -> Scenario | None:
        """Looks up a scenario by its unique identifier.

        Args:
            scenario_id: Scenario UUID.

        Returns:
            Scenario if found, None otherwise.
        """
        return self._repo.get_by_id(scenario_id)

    def is_profile_in_use(self, profile_id: UUID) -> bool:
        """Checks whether any persisted scenario references the given profile (RN-09).

        Args:
            profile_id: LPWAN profile UUID.

        Returns:
            True if at least one persisted scenario references the profile.
        """
        return self._repo.is_profile_in_use(profile_id)

    def is_dem_in_use(self, dem_id: UUID) -> bool:
        """Checks whether any persisted scenario references the given DEM (RN-28).

        Args:
            dem_id: DEM UUID.

        Returns:
            True if at least one persisted scenario references the DEM.
        """
        return self._repo.is_dem_in_use(dem_id)
