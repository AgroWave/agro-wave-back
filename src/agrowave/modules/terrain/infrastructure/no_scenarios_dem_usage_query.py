"""Default implementation of DemUsageQuery before scenarios module exists."""

from uuid import UUID

from agrowave.modules.terrain.domain.ports import DemUsageQuery


class NoScenariosDemUsageQuery(DemUsageQuery):
    """Query port implementation returning False since scenarios are not yet linked."""

    def is_dem_in_use(self, dem_id: UUID) -> bool:
        """Checks if a DEM is in use by scenarios.

        Args:
            dem_id: Unique identifier of the DEM.

        Returns:
            False, as no scenarios exist yet (stubbed for INC-03).
        """
        return False

