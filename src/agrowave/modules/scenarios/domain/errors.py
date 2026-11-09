"""Domain errors for the scenarios bounded context."""


class ScenariosDomainError(Exception):
    """Base exception for scenarios domain errors."""


class InvalidBoundsError(ScenariosDomainError):
    """Raised when south >= north or west >= east."""


class AreaOutsideColombiaError(ScenariosDomainError):
    """Raised when the study area falls outside continental Colombia (RN-12)."""


class AreaTooSmallError(ScenariosDomainError):
    """Raised when the study area has any side shorter than 1.5 km (RN-13)."""


class AreaWouldExcludeNodesError(ScenariosDomainError):
    """Raised when redefining the study area leaves existing nodes outside (RN-14).

    Attributes:
        excluded_node_names: Names of the nodes that would fall outside the new area.
    """

    def __init__(self, excluded_node_names: list[str]) -> None:
        """Initializes the error with the list of excluded node names."""
        self.excluded_node_names = excluded_node_names
        joined = ", ".join(excluded_node_names)
        super().__init__(f"Redefining the study area would exclude nodes: {joined} (RN-14).")


class DemDoesNotCoverAreaError(ScenariosDomainError):
    """Raised when the assigned DEM does not completely cover the study area (RN-26)."""


class DemNotAvailableError(ScenariosDomainError):
    """Raised when the assigned DEM is not in AVAILABLE status (RN-26, RN-31)."""


class MixedProfileNotAllowedError(ScenariosDomainError):
    """Raised when attempting to mix radio profiles in a scenario (RN-15)."""


class EndNodeAlreadyLinkedError(ScenariosDomainError):
    """Raised when an end node is already connected to a link (RN-17)."""


class OrphanNodeError(ScenariosDomainError):
    """Raised when a scenario deployment contains nodes without any link (RN-18)."""


class LinkTooShortError(ScenariosDomainError):
    """Raised when the horizontal distance of a link is less than 1.0 km (RN-19)."""


class HeightBelowMinimumError(ScenariosDomainError):
    """Raised when an antenna height AGL is below 0.5 m (RN-20)."""


class NodeOutsideAreaError(ScenariosDomainError):
    """Raised when a node is placed or moved outside the study area (RN-21)."""


class FrequencyOutOfProfileError(ScenariosDomainError):
    """Raised when the radio frequency in MHz is outside the profile band range (RN-22)."""


class ScenarioNotFoundError(ScenariosDomainError):
    """Raised when a scenario does not exist or belongs to another user."""


class ProfileNotFoundError(ScenariosDomainError):
    """Raised when the selected LPWAN profile does not exist or is not accessible."""
