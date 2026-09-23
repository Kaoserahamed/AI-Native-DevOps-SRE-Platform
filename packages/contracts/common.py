"""Shared primitives for the versioned platform contracts.

Every top-level payload subclasses :class:`PlatformModel`, which pins ``schema_version`` and forbids
unknown fields, so a payload can never silently gain meaning. Embedded value objects subclass
:class:`ValueModel`. Timestamps must be timezone-aware (normalised to UTC), identifiers are
machine-friendly, and every field that can reach an agent prompt is bounded in length.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Any, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

SCHEMA_VERSION: Final[str] = "v1"
SCHEMA_VERSION_PATTERN: Final[str] = r"^v[0-9]+$"

MAX_IDENTIFIER_LENGTH: Final[int] = 128
MAX_PRINCIPAL_LENGTH: Final[int] = 254
MAX_VERSION_LENGTH: Final[int] = 64
MAX_SHORT_TEXT_LENGTH: Final[int] = 280
MAX_LONG_TEXT_LENGTH: Final[int] = 4000
MAX_MAPPING_ENTRIES: Final[int] = 32
MAX_MAPPING_VALUE_LENGTH: Final[int] = 512


def require_aware_utc(value: datetime) -> datetime:
    """Reject naive timestamps and normalise aware ones to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware (UTC)")
    return value.astimezone(UTC)


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Return a deterministic JSON encoding used for digests and action hashes."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    )


def sha256_digest(payload: Mapping[str, Any]) -> str:
    """Return the ``sha256:`` digest of a payload's canonical JSON encoding."""
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


UtcDatetime = Annotated[datetime, AfterValidator(require_aware_utc)]
Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=MAX_IDENTIFIER_LENGTH,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
MachineName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"
    ),
]
PrincipalId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=MAX_PRINCIPAL_LENGTH,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._%+:@-]*$",
    ),
]
VersionRef = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_VERSION_LENGTH,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/@:+-]*$",
    ),
]
Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_SHORT_TEXT_LENGTH),
]
LongText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_LONG_TEXT_LENGTH),
]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
Counter = Annotated[int, Field(ge=0)]
Labels = dict[str, Annotated[str, StringConstraints(max_length=MAX_MAPPING_VALUE_LENGTH)]]
Attributes = dict[str, Any]


class Severity(StrEnum):
    """Incident and alert severity, matching the on-call expectations in the SLO document."""

    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"


class Environment(StrEnum):
    """Deployment environment an action or observation applies to."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ActorType(StrEnum):
    """Who caused an auditable event. Only humans may approve production changes."""

    HUMAN = "human"
    AGENT = "agent"
    AUTOMATION = "automation"
    SYSTEM = "system"


class ValueModel(BaseModel):
    """Immutable value object embedded inside a versioned payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PlatformModel(ValueModel):
    """Base class for every versioned, wire-level contract payload."""

    schema_version: Annotated[str, StringConstraints(pattern=SCHEMA_VERSION_PATTERN)] = Field(
        default=SCHEMA_VERSION,
        description="Contract schema version. A breaking change requires a new version, never an edit.",
    )


class AggregateModel(PlatformModel):
    """Base class for stateful aggregates that a repository loads, mutates and saves.

    Wire-level contracts are frozen: a payload that arrives over a request must never be edited in
    place, because the caller's copy would silently change. Aggregates are the deliberate exception —
    the incident lifecycle and the job queue both move an object through states — so instead of
    immutability they get **assignment validation**: every attribute write re-runs the contract's
    validators, which is what stops a state transition from leaving the object in a state the
    contract forbids. Transitions that need a consistent set of fields should prefer
    :meth:`Incident.transitioned_to`, which builds the updated aggregate in one validated step.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, frozen=False)


class ServiceRef(ValueModel):
    """Identifies the workload an observation or action refers to."""

    name: MachineName
    environment: Environment
    namespace: MachineName | None = None
    revision: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = (
        Field(
            default=None,
            description="Revision under observation: image digest, commit SHA or manifest version.",
        )
    )
