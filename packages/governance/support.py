"""Small, injectable primitives shared by the governance modules.

``utc_now`` and ``new_identifier`` are the only side effects the audit trail performs, so they live behind
callables: the control plane passes the real implementations, a test passes a fixed clock and a counter, and
the recorded audit events become byte-for-byte reproducible.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
import uuid

#: Returns the current time; injectable so a test can pin the clock.
Clock = Callable[[], datetime]
#: Returns the random part of a new identifier; injectable so a test can predict identifiers.
IdSource = Callable[[], str]

AUDIT_EVENT_PREFIX: Final[str] = "AUD"
INVOCATION_ID_PREFIX: Final[str] = "INV"
DECISION_ID_PREFIX: Final[str] = "DEC"
TOOL_CALL_PREFIX: Final[str] = "TOOL"

MAX_PREFIX_LENGTH: Final[int] = 24


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(tz=UTC)


def uuid_suffix() -> str:
    """Return a random, identifier-safe suffix."""
    return uuid.uuid4().hex


def new_identifier(prefix: str, *, source: IdSource | None = None) -> str:
    """Return ``<prefix>-<random>`` for a governance record.

    Parameters
    ----------
    prefix
        Short uppercase prefix naming the record kind, for example ``AUD``.
    source
        Optional random-suffix source; the default is a UUID4 hex string.

    Raises
    ------
    ValueError
        If the prefix is blank or too long, or the source returns nothing.
    """
    if not prefix.strip():
        raise ValueError("an identifier prefix must not be blank")
    if len(prefix) > MAX_PREFIX_LENGTH:
        raise ValueError(f"an identifier prefix must not exceed {MAX_PREFIX_LENGTH} characters")
    suffix = (source or uuid_suffix)()
    if not suffix:
        raise ValueError("an identifier source must not return an empty suffix")
    return f"{prefix}-{suffix}"


__all__ = [
    "AUDIT_EVENT_PREFIX",
    "DECISION_ID_PREFIX",
    "INVOCATION_ID_PREFIX",
    "MAX_PREFIX_LENGTH",
    "TOOL_CALL_PREFIX",
    "Clock",
    "IdSource",
    "new_identifier",
    "utc_now",
    "uuid_suffix",
]
