"""Job model for asynchronous processing."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import Any

from pydantic import Field

from packages.contracts.common import Identifier, PlatformModel, UtcDatetime


class JobStatus(StrEnum):
    """Status of a job in the queue."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


class Job(PlatformModel):
    """A job to be processed asynchronously."""

    job_id: Identifier
    job_type: str = Field(description="Type of job (e.g., 'incident_analysis', 'remediation')")
    payload: dict[str, Any] = Field(description="Job parameters")
    created_at: UtcDatetime
    scheduled_at: UtcDatetime = Field(description="When the job should be processed")
    started_at: UtcDatetime | None = None
    completed_at: UtcDatetime | None = None
    status: JobStatus = JobStatus.PENDING
    retry_count: int = Field(ge=0, default=0, description="Number of retry attempts")
    max_retries: int = Field(ge=0, default=3, description="Maximum retry attempts")
    visibility_timeout_seconds: int = Field(
        ge=1, default=300, description="Time before job becomes visible again if not completed"
    )
    error_message: str | None = None
    correlation_id: Identifier | None = Field(
        default=None, description="Correlation ID for distributed tracing"
    )
    idempotency_key: Identifier | None = Field(
        default=None, description="Key to prevent duplicate processing"
    )
    result: dict[str, Any] | None = Field(default=None, description="Job execution result")

    def is_retryable(self) -> bool:
        """Check if job can be retried."""
        return self.retry_count < self.max_retries and self.status == JobStatus.FAILED

    def next_retry_delay(self) -> timedelta:
        """Calculate exponential backoff delay for next retry."""
        # Exponential backoff: 2^retry_count seconds, capped at 1 hour
        delay_seconds = min(2**self.retry_count, 3600)
        return timedelta(seconds=delay_seconds)
