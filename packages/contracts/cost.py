"""Cost optimization evidence and recommendation contracts.

Cost evidence must be bounded, verifiable, and attribution-ready. Recommendations are non-mutating
suggestions that include assumptions, estimated impact, and risk assessment (ADR-0006).
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

from pydantic import Field, field_validator

from packages.contracts.common import (
    Confidence,
    Counter,
    Identifier,
    LongText,
    MachineName,
    PlatformModel,
    ServiceRef,
    ShortText,
    UtcDatetime,
    ValueModel,
)


class ResourceType(StrEnum):
    """Type of resource being measured for cost."""

    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    LLM_TOKENS = "llm_tokens"
    CI_MINUTES = "ci_minutes"
    CONTAINER_REGISTRY = "container_registry"


class CostCategory(StrEnum):
    """Category of cost optimization opportunity."""

    RIGHTSIZING = "rightsizing"
    AUTOSCALING = "autoscaling"
    IDLE_CLEANUP = "idle_cleanup"
    LOG_RETENTION = "log_retention"
    MODEL_SELECTION = "model_selection"
    RESOURCE_QUOTA = "resource_quota"


class ResourceUtilization(ValueModel):
    """Resource utilization metrics for a service."""

    service: ServiceRef
    resource_type: ResourceType
    measurement_window: timedelta
    measured_at: UtcDatetime
    requested: float = Field(description="Requested resource amount")
    actual_used: float = Field(description="Actual resource usage")
    unit: str = Field(description="Unit of measurement (cores, bytes, tokens, etc.)")
    utilization_percent: float = Field(ge=0.0, le=100.0, description="Usage as % of requested")
    replica_count: int = Field(ge=0, description="Number of replicas during measurement")

    @field_validator("actual_used", "requested")
    @classmethod
    def validate_non_negative(cls, v: float) -> float:
        """Ensure resource values are non-negative."""
        if v < 0:
            raise ValueError("Resource values must be non-negative")
        return v


class IdleResource(ValueModel):
    """Identification of an idle or underutilized resource."""

    resource_name: MachineName
    resource_type: ResourceType
    service: ServiceRef | None = None
    idle_duration: timedelta
    last_activity: UtcDatetime
    estimated_cost_per_day: float = Field(ge=0.0, description="Estimated daily cost in USD")
    utilization_percent: float = Field(ge=0.0, le=100.0)


class LLMUsageMetrics(ValueModel):
    """LLM token usage and cost metrics."""

    service: ServiceRef
    measurement_window: timedelta
    measured_at: UtcDatetime
    total_prompt_tokens: Counter
    total_completion_tokens: Counter
    total_requests: Counter
    estimated_cost: float = Field(ge=0.0, description="Estimated cost in USD")
    model_name: str
    average_tokens_per_request: float = Field(ge=0.0)


class StorageMetrics(ValueModel):
    """Storage usage and growth metrics."""

    service: ServiceRef
    measurement_window: timedelta
    measured_at: UtcDatetime
    total_bytes: Counter
    growth_rate_bytes_per_day: float
    object_count: Counter
    estimated_cost_per_month: float = Field(ge=0.0, description="Estimated monthly cost in USD")
    storage_type: str = Field(description="Type of storage (pv, registry, logs, etc.)")


class CIUsageMetrics(ValueModel):
    """CI/CD pipeline resource usage."""

    measurement_window: timedelta
    measured_at: UtcDatetime
    total_minutes: Counter
    total_runs: Counter
    average_duration_minutes: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0, description="Estimated cost in USD")
    workflow_breakdown: dict[str, Counter] = Field(
        default_factory=dict, description="Minutes per workflow name"
    )


class CostEvidence(PlatformModel):
    """Cost optimization evidence bundle."""

    evidence_id: Identifier
    collected_at: UtcDatetime
    service: ServiceRef | None = None
    resource_utilization: list[ResourceUtilization] = Field(default_factory=list)
    idle_resources: list[IdleResource] = Field(default_factory=list)
    llm_usage: list[LLMUsageMetrics] = Field(default_factory=list)
    storage_metrics: list[StorageMetrics] = Field(default_factory=list)
    ci_usage: CIUsageMetrics | None = None
    total_estimated_monthly_cost: float = Field(
        ge=0.0, description="Total estimated monthly cost in USD"
    )
    correlation_id: Identifier | None = None


class CostAssumption(ValueModel):
    """An assumption underlying a cost recommendation."""

    description: ShortText
    confidence: Confidence
    source: str = Field(description="Source of the assumption (measurement, estimate, etc.)")


class EstimatedImpact(ValueModel):
    """Estimated impact of a cost recommendation."""

    monthly_savings_usd: float = Field(description="Estimated monthly savings in USD")
    percentage_reduction: float = Field(
        ge=0.0, le=100.0, description="Estimated cost reduction as percentage"
    )
    affected_services: list[ServiceRef] = Field(min_length=1)
    implementation_effort: str = Field(
        description="Estimated effort: low, medium, high, or specific time estimate"
    )
    risk_level: str = Field(description="Risk assessment: low, medium, high")


class CostRecommendation(PlatformModel):
    """A non-mutating cost optimization recommendation with evidence and impact."""

    recommendation_id: Identifier
    created_at: UtcDatetime
    category: CostCategory
    title: ShortText
    description: LongText
    evidence_ids: list[Identifier] = Field(
        min_length=1, description="Evidence supporting this recommendation"
    )
    assumptions: list[CostAssumption] = Field(
        min_length=1, description="Assumptions underlying this recommendation"
    )
    estimated_impact: EstimatedImpact
    implementation_steps: list[ShortText] = Field(
        min_length=1, description="Concrete steps to implement this recommendation"
    )
    validation_criteria: list[ShortText] = Field(
        min_length=1, description="How to verify the recommendation achieved the expected impact"
    )
    confidence: Confidence
    service: ServiceRef | None = None
    current_state: dict[str, str | float | int] = Field(
        default_factory=dict, description="Current configuration or state"
    )
    proposed_state: dict[str, str | float | int] = Field(
        default_factory=dict, description="Proposed configuration or state"
    )
    correlation_id: Identifier | None = None


class CostOptimizationReport(PlatformModel):
    """Complete cost optimization analysis with evidence and recommendations."""

    report_id: Identifier
    generated_at: UtcDatetime
    analysis_period_start: UtcDatetime
    analysis_period_end: UtcDatetime
    evidence_summary: CostEvidence
    recommendations: list[CostRecommendation] = Field(default_factory=list)
    total_potential_monthly_savings: float = Field(
        ge=0.0, description="Sum of all recommendation savings in USD"
    )
    total_current_monthly_cost: float = Field(
        ge=0.0, description="Current estimated monthly cost in USD"
    )
    analyzed_services: list[ServiceRef] = Field(min_length=1)
