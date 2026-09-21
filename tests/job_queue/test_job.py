"""Tests for job model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.job_queue.job import Job, JobStatus


class TestJob:
    """Test job model."""

    def test_create_job(self) -> None:
        """Test creating a job."""
        now = datetime.now(tz=UTC)

        job = Job(
            job_id="job-001",
            job_type="incident_analysis",
            payload={"incident_id": "INC-001"},
            created_at=now,
            scheduled_at=now,
        )

        assert job.job_id == "job-001"
        assert job.job_type == "incident_analysis"
        assert job.status == JobStatus.PENDING
        assert job.retry_count == 0
        assert job.max_retries == 3

    def test_job_with_correlation_id(self) -> None:
        """Test job with correlation ID."""
        now = datetime.now(tz=UTC)

        job = Job(
            job_id="job-002",
            job_type="remediation",
            payload={},
            created_at=now,
            scheduled_at=now,
            correlation_id="corr-123",
        )

        assert job.correlation_id == "corr-123"

    def test_job_with_idempotency_key(self) -> None:
        """Test job with idempotency key."""
        now = datetime.now(tz=UTC)

        job = Job(
            job_id="job-003",
            job_type="test",
            payload={},
            created_at=now,
            scheduled_at=now,
            idempotency_key="idem-abc",
        )

        assert job.idempotency_key == "idem-abc"

    def test_is_retryable_when_under_max_retries(self) -> None:
        """Test job is retryable when under max retries."""
        now = datetime.now(tz=UTC)

        job = Job(
            job_id="job-004",
            job_type="test",
            payload={},
            created_at=now,
            scheduled_at=now,
            status=JobStatus.FAILED,
            retry_count=1,
            max_retries=3,
        )

        assert job.is_retryable() is True

    def test_is_not_retryable_when_max_retries_reached(self) -> None:
        """Test job is not retryable when max retries reached."""
        now = datetime.now(tz=UTC)

        job = Job(
            job_id="job-005",
            job_type="test",
            payload={},
            created_at=now,
            scheduled_at=now,
            status=JobStatus.FAILED,
            retry_count=3,
            max_retries=3,
        )

        assert job.is_retryable() is False

    def test_is_not_retryable_when_completed(self) -> None:
        """Test job is not retryable when completed."""
        now = datetime.now(tz=UTC)

        job = Job(
            job_id="job-006",
            job_type="test",
            payload={},
            created_at=now,
            scheduled_at=now,
            status=JobStatus.COMPLETED,
            retry_count=0,
            max_retries=3,
        )

        assert job.is_retryable() is False

    def test_next_retry_delay_exponential_backoff(self) -> None:
        """Test exponential backoff calculation."""
        now = datetime.now(tz=UTC)

        job = Job(
            job_id="job-007",
            job_type="test",
            payload={},
            created_at=now,
            scheduled_at=now,
            retry_count=0,
        )

        # First retry: 2^0 = 1 second
        assert job.next_retry_delay() == timedelta(seconds=1)

        job.retry_count = 1
        # Second retry: 2^1 = 2 seconds
        assert job.next_retry_delay() == timedelta(seconds=2)

        job.retry_count = 2
        # Third retry: 2^2 = 4 seconds
        assert job.next_retry_delay() == timedelta(seconds=4)

        job.retry_count = 10
        # Capped at 1 hour
        assert job.next_retry_delay() == timedelta(hours=1)

    def test_job_serialization(self) -> None:
        """Test job can be serialized and deserialized."""
        now = datetime.now(tz=UTC)

        original = Job(
            job_id="job-008",
            job_type="test",
            payload={"key": "value"},
            created_at=now,
            scheduled_at=now,
            correlation_id="corr-123",
        )

        # Serialize
        json_str = original.model_dump_json()

        # Deserialize
        import json

        data = json.loads(json_str)
        restored = Job(**data)

        assert restored.job_id == original.job_id
        assert restored.job_type == original.job_type
        assert restored.payload == original.payload
        assert restored.correlation_id == original.correlation_id
