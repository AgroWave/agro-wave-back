"""Use case for deleting a simulation (UC-SI-04, RF-006, RN-33)."""

from uuid import UUID

from agrowave.modules.simulation.domain.errors import SimulationNotFoundError
from agrowave.modules.simulation.domain.ports import SimulationRepository


class DeleteSimulation:
    """Deletes a simulation owned by the user unless it is currently RUNNING (RN-33)."""

    def __init__(self, repository: SimulationRepository) -> None:
        """Initializes the use case with the simulation repository port."""
        self._repository = repository

    def execute(self, simulation_id: UUID, owner_id: UUID) -> None:
        """Deletes the specified simulation after verifying it is not RUNNING.

        Args:
            simulation_id: Identifier of the simulation to delete.
            owner_id: Identifier of the requesting user.

        Raises:
            SimulationNotFoundError: If the simulation does not exist or belongs to another user.
            InvalidStatusTransitionError: If the simulation is in RUNNING status (RN-33).
        """
        simulation = self._repository.get_by_id(simulation_id=simulation_id, owner_id=owner_id)
        if simulation is None:
            raise SimulationNotFoundError(str(simulation_id))
        simulation.ensure_deletable()
        self._repository.delete(simulation_id=simulation_id, owner_id=owner_id)
