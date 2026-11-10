"""Use case for marking interrupted RUNNING simulations as FAILED on startup."""

from agrowave.modules.simulation.domain.ports import SimulationRepository

STARTUP_INTERRUPTION_REASON = "interrumpido por reinicio"


class FailInterruptedSimulations:
    """Marks simulations left in RUNNING state as FAILED when the API process starts."""

    def __init__(self, repository: SimulationRepository) -> None:
        """Initializes the use case with the simulation repository port."""
        self._repository = repository

    def execute(self, reason: str = STARTUP_INTERRUPTION_REASON) -> int:
        """Marks all RUNNING simulations as FAILED with the given reason.

        Args:
            reason: Failure reason recorded on interrupted simulations.

        Returns:
            Number of simulations updated to FAILED.
        """
        return self._repository.mark_running_as_failed_on_startup(reason)
