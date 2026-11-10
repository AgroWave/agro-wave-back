"""Domain errors for the simulation bounded context."""

from typing import Any


class SimulationDomainError(Exception):
    """Base error for simulation domain violations.

    Attributes:
        code: Machine-readable error code for API responses.
        message: Human-readable error description.
        details: Optional dictionary with structured context.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initializes a simulation domain error."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class ScenarioNotSimulableError(SimulationDomainError):
    """Raised when attempting to create a simulation for an invalid scenario (RN-31)."""

    def __init__(self, causes: list[dict[str, Any]]) -> None:
        """Initializes the error with the list of validation causes."""
        super().__init__(
            code="ScenarioNotSimulable",
            message="The scenario is not ready for simulation (RN-31).",
            details={"causes": causes},
        )


class InvalidStatusTransitionError(SimulationDomainError):
    """Raised when a simulation status transition or deletion is not allowed (RN-30, RN-33)."""

    def __init__(self, current_status: str, attempted_action: str) -> None:
        """Initializes the error with the current status and attempted action."""
        super().__init__(
            code="InvalidStatusTransition",
            message=(
                f"Cannot perform '{attempted_action}' while simulation is in "
                f"status '{current_status}' (RN-30, RN-33)."
            ),
            details={
                "current_status": current_status,
                "attempted_action": attempted_action,
            },
        )


class NotComparableError(SimulationDomainError):
    """Raised when simulations cannot be compared side by side (RN-37)."""

    def __init__(self, reason: str) -> None:
        """Initializes the error with the comparability violation reason."""
        super().__init__(
            code="NotComparable",
            message=f"Simulations cannot be compared: {reason} (RN-37).",
            details={"reason": reason},
        )


class SimulationNotFoundError(SimulationDomainError):
    """Raised when a simulation does not exist or belongs to another owner."""

    def __init__(self, simulation_id: str) -> None:
        """Initializes the error with the missing simulation identifier."""
        super().__init__(
            code="SimulationNotFound",
            message=f"Simulation '{simulation_id}' was not found.",
            details={"simulation_id": simulation_id},
        )


class TerrainProfileExtractionError(SimulationDomainError):
    """Raised when reading an elevation profile from the DEM COG fails."""

    def __init__(self, reason: str) -> None:
        """Initializes the error with the extraction failure reason."""
        super().__init__(
            code="TerrainProfileExtractionError",
            message=f"Could not extract terrain profile: {reason}.",
            details={"reason": reason},
        )


class PropagationEngineError(SimulationDomainError):
    """Raised when the propagation model engine fails to evaluate a link."""

    def __init__(self, reason: str) -> None:
        """Initializes the error with the engine failure reason."""
        super().__init__(
            code="PropagationEngineError",
            message=f"Propagation engine failure: {reason}.",
            details={"reason": reason},
        )
