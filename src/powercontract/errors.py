class PowerContractError(Exception):
    """Base error for invalid input or unsupported specifications."""


class SpecError(PowerContractError):
    """Raised when a contract file is invalid."""


class CaptureError(PowerContractError):
    """Raised when a capture cannot be parsed safely."""
