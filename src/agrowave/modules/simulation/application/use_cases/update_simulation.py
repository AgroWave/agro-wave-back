"""Use case for updating simulation name and description metadata (UC-SI-04, RF-005)."""

from uuid import UUID

from agrowave.modules.simulation.domain.errors import SimulationNotFoundError
from agrowave.modules.simulation.domain.models import Simulation
from agrowave.modules.simulation.domain.ports import SimulationRepository


class UpdateSimulation:
    """Updates the name and description of a simulation owned by the user."""

    def __init__(self, repository: SimulationRepository) -> None:
        """Initializes the use case with the simulation repository port."""
        self._repository = repository

    def execute(
        self,
        simulation_id: UUID,
        owner_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Simulation:
        """Updates metadata for the specified simulation.

        Args:
            simulation_id: Identifier of the simulation.
            owner_id: Identifier of the requesting user.
            name: Optional new simulation name.
            description: Optional new simulation description.

        Returns:
            Updated Simulation aggregate.

        Raises:
            SimulationNotFoundError: If the simulation does not exist or belongs to another user.
        """
        simulation = self._repository.get_by_id(simulation_id=simulation_id, owner_id=owner_id)
        if simulation is None:
            raise SimulationNotFoundError(str(simulation_id))
        simulation.update_info(name=name, description=description)
        self._repository.save(simulation)
        return simulation
