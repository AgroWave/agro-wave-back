"""Use case for creating a simulation with an immutable scenario snapshot (UC-SI-01)."""

from dataclasses import dataclass
from uuid import UUID

from agrowave.modules.simulation.domain.models import Simulation
from agrowave.modules.simulation.domain.ports import (
    ScenarioSnapshotSource,
    SimulationRepository,
)


@dataclass(frozen=True)
class CreateSimulationInput:
    """Input data for creating a simulation from a scenario.

    Attributes:
        owner_id: Identifier of the user creating the simulation.
        scenario_id: Identifier of the source scenario.
        name: Name of the simulation.
        description: Optional description of the simulation.
    """

    owner_id: UUID
    scenario_id: UUID
    name: str
    description: str | None = None


class CreateSimulation:
    """Validates a scenario and creates a simulation in CREATED state (UC-SI-01, RN-31, RN-32)."""

    def __init__(
        self,
        repository: SimulationRepository,
        snapshot_source: ScenarioSnapshotSource,
    ) -> None:
        """Initializes the use case with repository and snapshot source ports."""
        self._repository = repository
        self._snapshot_source = snapshot_source

    def execute(self, data: CreateSimulationInput) -> Simulation:
        """Creates and persists a new simulation capturing the scenario snapshot.

        Args:
            data: Creation parameters including owner_id, scenario_id, name, and description.

        Returns:
            Newly created Simulation aggregate in CREATED status.

        Raises:
            ScenarioNotSimulableError: If the scenario is invalid or its DEM is not AVAILABLE.
        """
        snapshot = self._snapshot_source.capture_simulable_snapshot(
            scenario_id=data.scenario_id,
            owner_id=data.owner_id,
        )
        simulation = Simulation.create(
            owner_id=data.owner_id,
            name=data.name,
            description=data.description,
            snapshot=snapshot,
        )
        self._repository.add(simulation)
        return simulation
