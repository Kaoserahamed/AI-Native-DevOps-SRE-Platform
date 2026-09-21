"""Redis-backed job queue with reliability features."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import logging
from typing import Any

from packages.contracts.common import Identifier
from packages.job_queue.job import Job, JobStatus

logger = logging.getLogger(__name__)


class JobQueue:
    """Reliable job queue using Redis."""

    def __init__(self, redis_client: Any, queue_name: str = "jobs") -> None:
        """Initialize job queue.

        Parameters
        ----------
        redis_client
            Redis async client
        queue_name
            Name of the queue (used as key prefix)
        """
        self.redis = redis_client
        self.queue_name = queue_name

        # Redis keys
        self.pending_key = f"{queue_name}:pending"
        self.processing_key = f"{queue_name}:processing"
        self.completed_key = f"{queue_name}:completed"
        self.failed_key = f"{queue_name}:failed"
        self.dead_key = f"{queue_name}:dead"
        self.job_data_prefix = f"{queue_name}:job:"
        self.idempotency_prefix = f"{queue_name}:idem:"

    def _job_key(self, job_id: Identifier) -> str:
        """Get Redis key for job data."""
        return f"{self.job_data_prefix}{job_id}"

    def _idempotency_key(self, idem_key: Identifier) -> str:
        """Get Redis key for idempotency tracking."""
        return f"{self.idempotency_prefix}{idem_key}"

    async def enqueue(self, job: Job) -> bool:
        """Enqueue a job for processing.

        Returns
        -------
        bool
            True if enqueued, False if duplicate (idempotency key exists)
        """
        # Check idempotency key if provided
        if job.idempotency_key:
            idem_key = self._idempotency_key(job.idempotency_key)
            exists = await self.redis.exists(idem_key)
            if exists:
                logger.info("Job with idempotency key %s already exists", job.idempotency_key)
                return False

            # Set idempotency key with TTL (24 hours)
            await self.redis.setex(idem_key, 86400, job.job_id)

        # Store job data
        job_key = self._job_key(job.job_id)
        job_json = job.model_dump_json()
        await self.redis.set(job_key, job_json)

        # Add to pending queue with score = scheduled_at timestamp
        score = job.scheduled_at.timestamp()
        await self.redis.zadd(self.pending_key, {job.job_id: score})

        logger.info("Enqueued job %s (type: %s)", job.job_id, job.job_type)
        return True

    async def dequeue(self, visibility_timeout: int = 300) -> Job | None:
        """Dequeue next available job.

        Parameters
        ----------
        visibility_timeout
            Seconds before job becomes visible again if not completed

        Returns
        -------
        Job | None
            Next job to process, or None if queue is empty
        """
        now = datetime.now(tz=UTC).timestamp()

        # Get jobs scheduled for now or earlier
        results = await self.redis.zrangebyscore(self.pending_key, 0, now, start=0, num=1)

        if not results:
            return None

        job_id = results[0].decode("utf-8") if isinstance(results[0], bytes) else results[0]

        # Move to processing queue
        await self.redis.zrem(self.pending_key, job_id)

        # Set visibility timeout
        timeout_at = now + visibility_timeout
        await self.redis.zadd(self.processing_key, {job_id: timeout_at})

        # Load job data
        job_key = self._job_key(job_id)
        job_json = await self.redis.get(job_key)

        if not job_json:
            logger.error("Job data missing for %s", job_id)
            return None

        job_data = json.loads(job_json)
        job = Job(**job_data)

        # Update job status
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(tz=UTC)

        await self._save_job(job)

        logger.info("Dequeued job %s (type: %s)", job.job_id, job.job_type)
        return job

    async def complete(self, job_id: Identifier, result: dict[str, Any] | None = None) -> None:
        """Mark job as completed.

        Parameters
        ----------
        job_id
            Job identifier
        result
            Optional result data
        """
        # Load job
        job = await self.get_job(job_id)
        if not job:
            logger.warning("Cannot complete non-existent job %s", job_id)
            return

        # Update job
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(tz=UTC)
        job.result = result

        await self._save_job(job)

        # Move to completed queue
        await self.redis.zrem(self.processing_key, job_id)
        score = datetime.now(tz=UTC).timestamp()
        await self.redis.zadd(self.completed_key, {job_id: score})

        logger.info("Completed job %s", job_id)

    async def fail(self, job_id: Identifier, error_message: str, retry: bool = True) -> None:
        """Mark job as failed and optionally retry.

        Parameters
        ----------
        job_id
            Job identifier
        error_message
            Error description
        retry
            Whether to retry the job
        """
        # Load job
        job = await self.get_job(job_id)
        if not job:
            logger.warning("Cannot fail non-existent job %s", job_id)
            return

        # Update job
        job.status = JobStatus.FAILED
        job.error_message = error_message
        job.retry_count += 1

        await self._save_job(job)

        # Remove from processing
        await self.redis.zrem(self.processing_key, job_id)

        # Check if retryable
        if retry and job.is_retryable():
            # Re-enqueue with backoff delay
            delay = job.next_retry_delay()
            job.scheduled_at = datetime.now(tz=UTC) + delay
            job.status = JobStatus.PENDING

            await self._save_job(job)

            score = job.scheduled_at.timestamp()
            await self.redis.zadd(self.pending_key, {job_id: score})

            logger.info(
                "Job %s failed (attempt %d/%d), retrying in %s",
                job_id,
                job.retry_count,
                job.max_retries,
                delay,
            )
        else:
            # Move to dead letter queue
            job.status = JobStatus.DEAD
            await self._save_job(job)

            score = datetime.now(tz=UTC).timestamp()
            await self.redis.zadd(self.dead_key, {job_id: score})

            logger.error(
                "Job %s moved to dead letter queue after %d attempts", job_id, job.retry_count
            )

    async def requeue_stuck_jobs(self) -> int:
        """Requeue jobs that exceeded visibility timeout.

        Returns
        -------
        int
            Number of jobs requeued
        """
        now = datetime.now(tz=UTC).timestamp()

        # Find jobs with expired visibility timeout
        results = await self.redis.zrangebyscore(self.processing_key, 0, now)

        requeued = 0
        for job_id_bytes in results:
            job_id = (
                job_id_bytes.decode("utf-8") if isinstance(job_id_bytes, bytes) else job_id_bytes
            )

            job = await self.get_job(job_id)
            if not job:
                continue

            # Move back to pending
            await self.redis.zrem(self.processing_key, job_id)

            job.status = JobStatus.PENDING
            job.scheduled_at = datetime.now(tz=UTC)
            await self._save_job(job)

            score = job.scheduled_at.timestamp()
            await self.redis.zadd(self.pending_key, {job_id: score})

            requeued += 1
            logger.warning("Requeued stuck job %s", job_id)

        return requeued

    async def get_job(self, job_id: Identifier) -> Job | None:
        """Retrieve job by ID."""
        job_key = self._job_key(job_id)
        job_json = await self.redis.get(job_key)

        if not job_json:
            return None

        job_data = json.loads(job_json)
        return Job(**job_data)

    async def _save_job(self, job: Job) -> None:
        """Save job data to Redis."""
        job_key = self._job_key(job.job_id)
        job_json = job.model_dump_json()
        await self.redis.set(job_key, job_json)

    async def get_queue_stats(self) -> dict[str, int]:
        """Get queue statistics.

        Returns
        -------
        dict[str, int]
            Counts by status
        """
        return {
            "pending": await self.redis.zcard(self.pending_key),
            "processing": await self.redis.zcard(self.processing_key),
            "completed": await self.redis.zcard(self.completed_key),
            "failed": await self.redis.zcard(self.failed_key),
            "dead": await self.redis.zcard(self.dead_key),
        }

    async def cleanup_completed(self, older_than: timedelta = timedelta(days=7)) -> int:
        """Remove completed jobs older than specified age.

        Parameters
        ----------
        older_than
            Remove jobs completed before this duration

        Returns
        -------
        int
            Number of jobs removed
        """
        cutoff = (datetime.now(tz=UTC) - older_than).timestamp()

        # Get old completed jobs
        job_ids = await self.redis.zrangebyscore(self.completed_key, 0, cutoff)

        removed = 0
        for job_id_bytes in job_ids:
            job_id = (
                job_id_bytes.decode("utf-8") if isinstance(job_id_bytes, bytes) else job_id_bytes
            )

            # Remove job data
            job_key = self._job_key(job_id)
            await self.redis.delete(job_key)

            # Remove from completed queue
            await self.redis.zrem(self.completed_key, job_id)

            removed += 1

        if removed > 0:
            logger.info("Cleaned up %d completed jobs older than %s", removed, older_than)

        return removed
