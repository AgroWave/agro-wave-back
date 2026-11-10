"""Use case for retrieving a simulation and its link results (RF-003, RF-030, RF-031)."""

from uuid import UUID

from agrowave.modules.simulation.domain.errors import SimulationNotFoundError
from agrowave.modules.simulation.domain.models import Simulation
from agrowave.modules.simulation.domain.ports import SimulationRepository


class GetSimulationResults:
    """Retrieves a simulation owned by the user along with its detailed results and warnings."""

    def __init__(self, repository: SimulationRepository) -> None:
        """Initializes the use case with the simulation repository port."""
        self._repository = repository

    def execute(self, simulation_id: UUID, owner_id: UUID) -> Simulation:
        """Fetches the simulation by ID and owner.

        Args:
            simulation_id: Identifier of the simulation.
            owner_id: Identifier of the requesting user.

        Returns:
            Simulation aggregate including summary, link results, and warnings if completed.

        Raises:
            SimulationNotFoundError: If the simulation does not exist or belongs to another user.
        """
        simulation = self._repository.get_by_id(simulation_id=simulation_id, owner_id=owner_id)
        if simulation is None:
            raise SimulationNotFoundError(str(simulation_id))
        return simulation
