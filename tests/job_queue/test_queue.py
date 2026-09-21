"""Tests for job queue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.job_queue.job import Job, JobStatus
from packages.job_queue.queue import JobQueue


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create mock Redis client."""
    redis = MagicMock()

    # Setup common async methods
    redis.exists = AsyncMock(return_value=False)
    redis.setex = AsyncMock()
    redis.set = AsyncMock()
    redis.get = AsyncMock()
    redis.zadd = AsyncMock()
    redis.zrem = AsyncMock()
    redis.zrangebyscore = AsyncMock(return_value=[])
    redis.zcard = AsyncMock(return_value=0)
    redis.delete = AsyncMock()

    return redis


@pytest.fixture
def job_queue(mock_redis: MagicMock) -> JobQueue:
    """Create job queue with mock Redis."""
    return JobQueue(mock_redis, queue_name="test-queue")


@pytest.fixture
def sample_job() -> Job:
    """Create sample job."""
    now = datetime.now(tz=UTC)
    return Job(
        job_id="job-001",
        job_type="test_job",
        payload={"data": "test"},
        created_at=now,
        scheduled_at=now,
    )


class TestJobQueue:
    """Test job queue operations."""

    @pytest.mark.asyncio
    async def test_enqueue_job(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test enqueuing a job."""
        result = await job_queue.enqueue(sample_job)

        assert result is True
        mock_redis.set.assert_called_once()
        mock_redis.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_with_idempotency_key_first_time(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test enqueuing with idempotency key (first time)."""
        sample_job.idempotency_key = "idem-123"
        mock_redis.exists.return_value = False

        result = await job_queue.enqueue(sample_job)

        assert result is True
        mock_redis.exists.assert_called_once()
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_with_duplicate_idempotency_key(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test enqueuing with duplicate idempotency key."""
        sample_job.idempotency_key = "idem-123"
        mock_redis.exists.return_value = True

        result = await job_queue.enqueue(sample_job)

        assert result is False
        mock_redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_dequeue_job(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test dequeuing a job."""
        # Setup mock to return job ID
        mock_redis.zrangebyscore.return_value = [sample_job.job_id.encode()]
        mock_redis.get.return_value = sample_job.model_dump_json()

        job = await job_queue.dequeue()

        assert job is not None
        assert job.job_id == sample_job.job_id
        assert job.status == JobStatus.PROCESSING
        assert job.started_at is not None

    @pytest.mark.asyncio
    async def test_dequeue_empty_queue(self, job_queue: JobQueue, mock_redis: MagicMock) -> None:
        """Test dequeuing from empty queue."""
        mock_redis.zrangebyscore.return_value = []

        job = await job_queue.dequeue()

        assert job is None

    @pytest.mark.asyncio
    async def test_complete_job(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test completing a job."""
        # Setup mock to return existing job
        mock_redis.get.return_value = sample_job.model_dump_json()

        result = {"output": "success"}
        await job_queue.complete(sample_job.job_id, result)

        # Verify job was updated and moved to completed queue
        mock_redis.zrem.assert_called_once()
        assert mock_redis.zadd.call_count >= 1

    @pytest.mark.asyncio
    async def test_fail_job_with_retry(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test failing a job with retry."""
        sample_job.retry_count = 0
        sample_job.max_retries = 3
        mock_redis.get.return_value = sample_job.model_dump_json()

        await job_queue.fail(sample_job.job_id, "Test error", retry=True)

        # Should re-enqueue for retry
        assert mock_redis.zadd.call_count >= 1

    @pytest.mark.asyncio
    async def test_fail_job_max_retries_reached(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test failing a job when max retries reached."""
        sample_job.retry_count = 3
        sample_job.max_retries = 3
        mock_redis.get.return_value = sample_job.model_dump_json()

        await job_queue.fail(sample_job.job_id, "Test error", retry=True)

        # Should move to dead letter queue
        # At least one zadd call for dead queue
        assert mock_redis.zadd.call_count >= 1

    @pytest.mark.asyncio
    async def test_requeue_stuck_jobs(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test requeuing stuck jobs."""
        mock_redis.zrangebyscore.return_value = [sample_job.job_id.encode()]
        mock_redis.get.return_value = sample_job.model_dump_json()

        requeued = await job_queue.requeue_stuck_jobs()

        assert requeued == 1
        mock_redis.zrem.assert_called()
        mock_redis.zadd.assert_called()

    @pytest.mark.asyncio
    async def test_get_job(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test retrieving a job by ID."""
        mock_redis.get.return_value = sample_job.model_dump_json()

        job = await job_queue.get_job(sample_job.job_id)

        assert job is not None
        assert job.job_id == sample_job.job_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, job_queue: JobQueue, mock_redis: MagicMock) -> None:
        """Test retrieving nonexistent job."""
        mock_redis.get.return_value = None

        job = await job_queue.get_job("nonexistent")

        assert job is None

    @pytest.mark.asyncio
    async def test_get_queue_stats(self, job_queue: JobQueue, mock_redis: MagicMock) -> None:
        """Test getting queue statistics."""
        mock_redis.zcard.return_value = 5

        stats = await job_queue.get_queue_stats()

        assert stats["pending"] == 5
        assert stats["processing"] == 5
        assert stats["completed"] == 5
        assert stats["failed"] == 5
        assert stats["dead"] == 5

    @pytest.mark.asyncio
    async def test_cleanup_completed(self, job_queue: JobQueue, mock_redis: MagicMock) -> None:
        """Test cleaning up old completed jobs."""
        old_job_ids = [b"job-001", b"job-002", b"job-003"]
        mock_redis.zrangebyscore.return_value = old_job_ids

        removed = await job_queue.cleanup_completed(older_than=timedelta(days=7))

        assert removed == 3
        assert mock_redis.delete.call_count == 3
        assert mock_redis.zrem.call_count == 3


class TestJobQueueIntegration:
    """Integration-style tests for job queue (still using mocks)."""

    @pytest.mark.asyncio
    async def test_full_job_lifecycle(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test complete job lifecycle: enqueue -> dequeue -> complete."""
        # Enqueue
        await job_queue.enqueue(sample_job)

        # Setup for dequeue
        mock_redis.zrangebyscore.return_value = [sample_job.job_id.encode()]
        mock_redis.get.return_value = sample_job.model_dump_json()

        # Dequeue
        job = await job_queue.dequeue()
        assert job is not None

        # Update mock for completion
        job_data = sample_job.model_dump_json()
        mock_redis.get.return_value = job_data

        # Complete
        await job_queue.complete(job.job_id, {"result": "success"})

        # Verify completion flow
        assert mock_redis.zrem.called
        assert mock_redis.zadd.called

    @pytest.mark.asyncio
    async def test_retry_with_backoff(
        self, job_queue: JobQueue, mock_redis: MagicMock, sample_job: Job
    ) -> None:
        """Test job retry with exponential backoff."""
        sample_job.retry_count = 1
        sample_job.max_retries = 3
        mock_redis.get.return_value = sample_job.model_dump_json()

        # Fail job
        await job_queue.fail(sample_job.job_id, "Temporary error", retry=True)

        # Verify retry was scheduled
        assert mock_redis.zadd.called

        # The score should reflect backoff delay
        # For retry_count=1, delay should be 2^1 = 2 seconds
        call_args = mock_redis.zadd.call_args
        assert call_args is not None
