"""Alert contract: the normalized entry point of the incident lifecycle.

Alert rules fire from Prometheus, Kubernetes or the anomaly detector; the API normalises them into this
shape before anything else sees them. Labels are bounded and restricted to machine-friendly keys because
they are attacker-influenceable telemetry (trust boundary TB-2) that ends up in evidence and prompts.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final, Self

from pydantic import Field, HttpUrl, field_validator, model_validator

from packages.contracts.common import (
    MAX_MAPPING_ENTRIES,
    Identifier,
    Labels,
    LongText,
    MachineName,
    PlatformModel,
    ServiceRef,
    Severity,
    ShortText,
    UtcDatetime,
)

LABEL_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{1,62}$")


class AlertSource(StrEnum):
    """Origin of a normalized alert."""

    PROMETHEUS = "prometheus"
    KUBERNETES = "kubernetes"
    GITHUB = "github"
    ANOMALY_DETECTION = "anomaly_detection"
    MANUAL = "manual"


class Alert(PlatformModel):
    """A single alert that may or may not open an incident.

    ``fingerprint`` is stable across a firing series so that duplicate deliveries deduplicate into one
    alert, and ``slo`` links the alert to the objective it threatens.
    """

    alert_id: Identifier
    fingerprint: Identifier = Field(description="Stable identity of the firing rule and target labels.")
    name: MachineName
    severity: Severity
    service: ServiceRef
    source: AlertSource
    summary: ShortText
    description: LongText | None = None
    fired_at: UtcDatetime
    resolved_at: UtcDatetime | None = None
    labels: Labels = Field(default_factory=dict)
    runbook_url: HttpUrl | None = None
    slo: Identifier | None = None
    correlation_id: Identifier | None = None

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, labels: dict[str, str]) -> dict[str, str]:
        """Keep label cardinality and key shape under control."""
        if len(labels) > MAX_MAPPING_ENTRIES:
            raise ValueError(f"at most {MAX_MAPPING_ENTRIES} labels are allowed, got {len(labels)}")
        for key in labels:
            if LABEL_KEY_PATTERN.match(key) is None:
                raise ValueError(f"label key {key!r} must match {LABEL_KEY_PATTERN.pattern}")
        return labels

    @model_validator(mode="after")
    def validate_timeline(self) -> Self:
        """A resolution can never precede the moment the alert fired."""
        if self.resolved_at is not None and self.resolved_at < self.fired_at:
            raise ValueError("resolved_at must not be earlier than fired_at")
        return self
