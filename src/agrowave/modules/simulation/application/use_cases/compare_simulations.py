"""Use case for comparing completed simulations of the same group and model (UC-SI-03, RN-37)."""

from collections.abc import Sequence
from uuid import UUID

from agrowave.modules.simulation.domain.errors import SimulationNotFoundError
from agrowave.modules.simulation.domain.models import Simulation
from agrowave.modules.simulation.domain.ports import SimulationRepository
from agrowave.modules.simulation.domain.services import (
    ComparisonReport,
    ComparisonService,
)


class CompareSimulations:
    """Compares two or more completed simulations belonging to the same user and group (RN-37)."""

    def __init__(self, repository: SimulationRepository) -> None:
        """Initializes the use case with the simulation repository port."""
        self._repository = repository

    def execute(self, simulation_ids: Sequence[UUID], owner_id: UUID) -> ComparisonReport:
        """Loads the requested simulations and computes a side-by-side comparison report.

        Args:
            simulation_ids: Ordered sequence of simulation identifiers to compare.
            owner_id: Identifier of the requesting user.

        Returns:
            ComparisonReport with summary and per-link metrics across variants.

        Raises:
            SimulationNotFoundError: If any simulation does not exist or belongs to another user.
            NotComparableError: If simulations violate comparability rules (RN-37).
        """
        simulations: list[Simulation] = []
        seen: set[UUID] = set()
        for sim_id in simulation_ids:
            if sim_id in seen:
                continue
            seen.add(sim_id)
            sim = self._repository.get_by_id(simulation_id=sim_id, owner_id=owner_id)
            if sim is None:
                raise SimulationNotFoundError(str(sim_id))
            simulations.append(sim)

        return ComparisonService.compare(simulations)
