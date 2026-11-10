"""Use case for retrying a failed simulation (UC-SI-02)."""

from uuid import UUID

from agrowave.modules.simulation.domain.errors import SimulationNotFoundError
from agrowave.modules.simulation.domain.models import Simulation
from agrowave.modules.simulation.domain.ports import (
    SimulationJobRunner,
    SimulationRepository,
)


class RetrySimulation:
    """Transitions a FAILED simulation to RUNNING and re-enqueues execution (UC-SI-02, RN-30)."""

    def __init__(
        self,
        repository: SimulationRepository,
        job_runner: SimulationJobRunner,
    ) -> None:
        """Initializes the use case with repository and job runner ports."""
        self._repository = repository
        self._job_runner = job_runner

    def execute(self, simulation_id: UUID, owner_id: UUID) -> Simulation:
        """Retries a FAILED simulation.

        Args:
            simulation_id: Identifier of the failed simulation.
            owner_id: Identifier of the requesting user.

        Returns:
            Updated Simulation aggregate in RUNNING status.

        Raises:
            SimulationNotFoundError: If the simulation does not exist or belongs to another user.
            InvalidStatusTransitionError: If the simulation is not in FAILED status (RN-30).
        """
        simulation = self._repository.get_by_id(simulation_id=simulation_id, owner_id=owner_id)
        if simulation is None:
            raise SimulationNotFoundError(str(simulation_id))

        simulation.retry()
        self._repository.save(simulation)
        self._job_runner.enqueue(simulation.id)
        return simulation
