"""Domain errors for the LPWAN profiles module."""


class ProfilesDomainError(Exception):
    """Base domain exception for the profiles module."""


class SpreadingFactorNotAllowedError(ProfilesDomainError):
    """Raised when the spreading factor is not allowed for the technology (RN-07).

    LoRaWAN requires a spreading factor in 7..12; NB-IoT and LTE-M must not have one.
    """


class InvalidBandRangeError(ProfilesDomainError):
    """Raised when band frequency min_mhz is not strictly lower than max_mhz."""


class PredefinedProfileReadOnlyError(ProfilesDomainError):
    """Raised when an operation attempts to modify or delete a predefined profile (RN-10)."""


class ResourceInUseError(ProfilesDomainError):
    """Raised when attempting to modify or delete a profile that is currently in use (RN-09)."""


class ProfileNotFoundError(ProfilesDomainError):
    """Raised when a profile cannot be found."""
