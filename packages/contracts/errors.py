"""API error contract shared by every platform endpoint and adapter.

One error shape means one client-side handling path, consistent correlation for support, and a rule that
keeps retry guidance honest: a 4xx that is not "too many requests" is never marked retryable.
"""

from __future__ import annotations

from typing import Annotated, Final, Self

from pydantic import Field, HttpUrl, StringConstraints, model_validator

from packages.contracts.common import Identifier, MachineName, PlatformModel, ShortText, ValueModel

MAX_ERROR_DETAILS: Final[int] = 16
RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({429, 502, 503, 504})

FieldPath = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class ErrorDetail(ValueModel):
    """Field-level or sub-reason detail for a failed request."""

    reason: ShortText
    field: FieldPath | None = None
    code: MachineName | None = None


class ApiError(PlatformModel):
    """The single error payload every endpoint returns for a failed request."""

    error_code: MachineName = Field(
        description="Stable machine-readable code, for example invalid_transition."
    )
    message: ShortText
    status_code: Annotated[int, Field(ge=400, le=599)]
    correlation_id: Identifier
    retryable: bool = False
    details: list[ErrorDetail] = Field(default_factory=list)
    documentation_url: HttpUrl | None = None

    @model_validator(mode="after")
    def validate_retry_guidance(self) -> Self:
        """Only transient statuses may be advertised as retryable, and details stay bounded."""
        if len(self.details) > MAX_ERROR_DETAILS:
            raise ValueError(f"at most {MAX_ERROR_DETAILS} error details are allowed")
        if self.retryable and self.status_code not in RETRYABLE_STATUS:
            raise ValueError(
                f"status {self.status_code} must not be marked retryable; "
                f"retryable statuses are {sorted(RETRYABLE_STATUS)}"
            )
        return self
