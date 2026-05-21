"""Exception types raised by the tiqopay SDK."""

from typing import Optional


class TiqopayError(Exception):
    """Raised when the tiqopay API returns a non-2xx response, or when a
    network/timeout error occurs after the retry budget is exhausted.

    Attributes:
        message: Human-readable error message (from the API body when present).
        status:  HTTP status code, or ``0`` for transport-level errors.
        code:    Machine-readable error code (e.g. ``invalid_param``,
                 ``kyb_verification_required``, ``rate_limit_exceeded``).
                 See https://tiqopay.com/developers/errors for the full list.
    """

    def __init__(
        self,
        message: str,
        status: int,
        code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code

    def __repr__(self) -> str:
        return f"TiqopayError(status={self.status!r}, code={self.code!r}, message={self.message!r})"
