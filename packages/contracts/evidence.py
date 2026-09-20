"""Evidence contract: bounded, citable observations used for diagnosis.

Agents must never ingest unbounded telemetry. Every evidence item therefore carries a collection
window, bounded text and payload sizes, and a redaction flag, and it can be cited by id from a
diagnosis. The limits here are the first line of defence for both cost control and prompt-injection
containment (ADR-0006, trust boundary TB-2).
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import Field, StringConstraints, computed_field, model_validator

from packages.contracts.common import (
    MAX_MAPPING_ENTRIES,
    Attributes,
    Counter,
    Identifier,
    PlatformModel,
    ServiceRef,
    ShortText,
    UtcDatetime,
    ValueModel,
    canonical_json,
)

MAX_EVIDENCE_WINDOW: Final[timedelta] = timedelta(hours=6)
MAX_EVIDENCE_PAYLOAD_BYTES: Final[int] = 16_384
MAX_EXCERPT_LENGTH: Final[int] = 2_000

Excerpt = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_EXCERPT_LENGTH)
]


class EvidenceKind(StrEnum):
    """Kinds of observation the platform can retrieve."""

    METRIC_SERIES = "metric_series"
    LOG_EXCERPT = "log_excerpt"
    TRACE_SUMMARY = "trace_summary"
    KUBERNETES_OBJECT = "kubernetes_object"
    DEPLOYMENT_EVENT = "deployment_event"
    CONFIGURATION_DIFF = "configuration_diff"


class EvidenceCollector(StrEnum):
    """Which adapter produced the evidence."""

    PROMETHEUS = "prometheus"
    KUBERNETES = "kubernetes"
    GITHUB = "github"
    OPENTELEMETRY_LOGS = "opentelemetry_logs"
    OPENTELEMETRY_TRACES = "opentelemetry_traces"
    PLATFORM = "platform"


class TimeWindow(ValueModel):
    """Inclusive-exclusive observation window, bounded in duration."""

    start: UtcDatetime
    end: UtcDatetime

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        """Reject empty, inverted or unbounded windows."""
        if self.end <= self.start:
            raise ValueError("window end must be later than window start")
        if self.end - self.start > MAX_EVIDENCE_WINDOW:
            raise ValueError(
                f"window must not exceed {MAX_EVIDENCE_WINDOW} (evidence must stay bounded)"
            )
        return self


class Evidence(PlatformModel):
    """A sanitized observation with provenance and a citation-ready excerpt."""

    evidence_id: Identifier
    kind: EvidenceKind
    collector: EvidenceCollector
    collected_at: UtcDatetime
    summary: ShortText
    service: ServiceRef | None = None
    window: TimeWindow | None = None
    excerpt: Excerpt | None = Field(
        default=None, description="Text that may be quoted into a prompt; already sanitized."
    )
    payload: Attributes | None = Field(
        default=None, description="Structured observation, bounded by MAX_EVIDENCE_PAYLOAD_BYTES."
    )
    labels: dict[str, str] = Field(default_factory=dict)
    redacted: bool = Field(
        default=True, description="Whether sanitisation/redaction has been applied."
    )
    incident_id: Identifier | None = None
    correlation_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        """Enforce the payload limits and the kind-specific requirements."""
        if self.excerpt is None and self.payload is None:
            raise ValueError("evidence must carry an excerpt or a structured payload")
        if self.labels and len(self.labels) > MAX_MAPPING_ENTRIES:
            raise ValueError(f"at most {MAX_MAPPING_ENTRIES} labels are allowed")
        if self.payload is not None and self.size_bytes > MAX_EVIDENCE_PAYLOAD_BYTES:
            raise ValueError(
                f"payload must not exceed {MAX_EVIDENCE_PAYLOAD_BYTES} bytes, got {self.size_bytes}"
            )
        time_series_kinds = {EvidenceKind.METRIC_SERIES, EvidenceKind.TRACE_SUMMARY}
        if self.kind in time_series_kinds and self.window is None:
            raise ValueError(f"{self.kind} evidence requires an observation window")
        return self

    @computed_field(  # type: ignore[prop-decorator]
        description="Serialized payload size in bytes, used for budget enforcement."
    )
    @property
    def size_bytes(self) -> int:
        """Return the canonical JSON size of the structured payload (0 when there is none)."""
        if self.payload is None:
            return 0
        return len(canonical_json(self.payload).encode("utf-8"))

    @computed_field(  # type: ignore[prop-decorator]
        description="Total bounded payload counter for budget accounting."
    )
    @property
    def evidence_bytes(self) -> Counter:
        """Return the size charged against the agent's evidence budget."""
        return self.size_bytes + len(self.excerpt or "")
