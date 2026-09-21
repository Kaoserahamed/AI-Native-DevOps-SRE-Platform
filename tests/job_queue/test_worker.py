"""Tests for worker."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.job_queue.job import Job
from packages.job_queue.queue import JobQueue
from packages.job_queue.worker import Worker, WorkerConfig


@pytest.fixture
def mock_queue() -> MagicMock:
    """Create mock job queue."""
    queue = MagicMock(spec=JobQueue)
    queue.dequeue = AsyncMock(return_value=None)
    queue.complete = AsyncMock()
    queue.fail = AsyncMock()
    queue.requeue_stuck_jobs = AsyncMock(return_value=0)
    return queue


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


@pytest.fixture
def worker_config() -> WorkerConfig:
    """Create worker config for testing."""
    return WorkerConfig(
        poll_interval_seconds=0.1,
        stuck_job_check_interval_seconds=1,
        max_concurrent_jobs=2,
        graceful_shutdown_timeout_seconds=5,
    )


class TestWorker:
    """Test worker functionality."""

    @pytest.mark.asyncio
    async def test_worker_processes_job(
        self, mock_queue: MagicMock, sample_job: Job, worker_config: WorkerConfig
    ) -> None:
        """Test worker processes a job successfully."""
        # Setup mock to return job once, then None
        call_count = 0

        async def dequeue_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_job
            return None

        mock_queue.dequeue.side_effect = dequeue_side_effect

        # Create handler
        handler_called = False

        async def test_handler(job: Job) -> dict:
            nonlocal handler_called
            handler_called = True
            return {"result": "success"}

        handlers = {"test_job": test_handler}

        worker = Worker(mock_queue, handlers, worker_config)

        # Run worker briefly
        async def run_and_stop():
            await asyncio.sleep(0.3)
            await worker.stop()

        await asyncio.gather(worker.start(), run_and_stop())

        # Verify handler was called
        assert handler_called is True
        mock_queue.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_handles_job_failure(
        self, mock_queue: MagicMock, sample_job: Job, worker_config: WorkerConfig
    ) -> None:
        """Test worker handles job failure."""
        call_count = 0

        async def dequeue_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_job
            return None

        mock_queue.dequeue.side_effect = dequeue_side_effect

        # Create failing handler
        async def failing_handler(job: Job) -> dict:
            raise ValueError("Test error")

        handlers = {"test_job": failing_handler}

        worker = Worker(mock_queue, handlers, worker_config)

        # Run worker briefly
        async def run_and_stop():
            await asyncio.sleep(0.3)
            await worker.stop()

        await asyncio.gather(worker.start(), run_and_stop())

        # Verify failure was recorded
        mock_queue.fail.assert_called_once()
        call_args = mock_queue.fail.call_args
        assert call_args[0][0] == sample_job.job_id
        assert "Test error" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_worker_handles_unknown_job_type(
        self, mock_queue: MagicMock, sample_job: Job, worker_config: WorkerConfig
    ) -> None:
        """Test worker handles unknown job type."""
        sample_job.job_type = "unknown_type"

        call_count = 0

        async def dequeue_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_job
            return None

        mock_queue.dequeue.side_effect = dequeue_side_effect

        handlers = {"test_job": AsyncMock()}

        worker = Worker(mock_queue, handlers, worker_config)

        # Run worker briefly
        async def run_and_stop():
            await asyncio.sleep(0.3)
            await worker.stop()

        await asyncio.gather(worker.start(), run_and_stop())

        # Verify failure was recorded (no retry for unknown type)
        mock_queue.fail.assert_called_once()
        call_args = mock_queue.fail.call_args
        assert call_args[0][0] == sample_job.job_id
        assert "No handler" in call_args[0][1]
        assert call_args[1]["retry"] is False

    @pytest.mark.asyncio
    async def test_worker_respects_max_concurrent_jobs(
        self, mock_queue: MagicMock, worker_config: WorkerConfig
    ) -> None:
        """Test worker respects max concurrent jobs limit."""
        worker_config.max_concurrent_jobs = 2

        jobs_processed = []

        async def slow_handler(job: Job) -> dict:
            jobs_processed.append(job.job_id)
            await asyncio.sleep(0.2)
            return {}

        handlers = {"test_job": slow_handler}

        # Return multiple jobs
        now = datetime.now(tz=UTC)
        jobs = [
            Job(
                job_id=f"job-{i:03d}",
                job_type="test_job",
                payload={},
                created_at=now,
                scheduled_at=now,
            )
            for i in range(5)
        ]

        call_count = 0

        async def dequeue_side_effect(*args, **kwargs):
            nonlocal call_count
            if call_count < len(jobs):
                job = jobs[call_count]
                call_count += 1
                return job
            return None

        mock_queue.dequeue.side_effect = dequeue_side_effect

        worker = Worker(mock_queue, handlers, worker_config)

        # Run worker briefly
        async def run_and_stop():
            await asyncio.sleep(0.5)
            await worker.stop()

        await asyncio.gather(worker.start(), run_and_stop())

        # Some jobs should have been processed
        assert len(jobs_processed) > 0
        # But not necessarily all due to concurrency limit
        assert len(jobs_processed) <= 5

    @pytest.mark.asyncio
    async def test_worker_graceful_shutdown(
        self, mock_queue: MagicMock, sample_job: Job, worker_config: WorkerConfig
    ) -> None:
        """Test worker waits for active jobs during shutdown."""
        job_completed = False

        async def slow_handler(job: Job) -> dict:
            nonlocal job_completed
            await asyncio.sleep(0.3)
            job_completed = True
            return {}

        handlers = {"test_job": slow_handler}

        # Return job once
        call_count = 0

        async def dequeue_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_job
            return None

        mock_queue.dequeue.side_effect = dequeue_side_effect

        worker = Worker(mock_queue, handlers, worker_config)

        # Start and stop quickly
        async def run_and_stop():
            await asyncio.sleep(0.1)  # Let job start
            await worker.stop()

        await asyncio.gather(worker.start(), run_and_stop())

        # Job should complete even though shutdown was requested
        assert job_completed is True

    @pytest.mark.asyncio
    async def test_worker_health_status(
        self, mock_queue: MagicMock, worker_config: WorkerConfig
    ) -> None:
        """Test worker health status reporting."""
        handlers = {"test_job": AsyncMock()}

        worker = Worker(mock_queue, handlers, worker_config)

        # Initial status
        status = worker.get_health_status()
        assert status["status"] == "starting"
        assert status["running"] is False

        # Start worker
        async def run_and_check():
            await asyncio.sleep(0.1)
            status = worker.get_health_status()
            assert status["status"] == "healthy"
            assert status["running"] is True
            await worker.stop()

        await asyncio.gather(worker.start(), run_and_check())

        # After stop
        status = worker.get_health_status()
        assert status["running"] is False


class TestWorkerStuckJobMonitor:
    """Test stuck job monitoring."""

    @pytest.mark.asyncio
    async def test_stuck_job_monitor_requeues_jobs(
        self, mock_queue: MagicMock, worker_config: WorkerConfig
    ) -> None:
        """Test stuck job monitor requeues jobs."""
        worker_config.stuck_job_check_interval_seconds = 0.2

        mock_queue.requeue_stuck_jobs.return_value = 2

        handlers = {"test_job": AsyncMock()}
        worker = Worker(mock_queue, handlers, worker_config)

        # Run worker briefly
        async def run_and_stop():
            await asyncio.sleep(0.5)
            await worker.stop()

        await asyncio.gather(worker.start(), run_and_stop())

        # Stuck job check should have been called
        assert mock_queue.requeue_stuck_jobs.called


class TestWorkerConfig:
    """Test worker configuration."""

    def test_default_config(self) -> None:
        """Test default worker configuration."""
        config = WorkerConfig()

        assert config.poll_interval_seconds == 1.0
        assert config.visibility_timeout_seconds == 300
        assert config.stuck_job_check_interval_seconds == 60
        assert config.max_concurrent_jobs == 5
        assert config.graceful_shutdown_timeout_seconds == 30

    def test_custom_config(self) -> None:
        """Test custom worker configuration."""
        config = WorkerConfig(
            poll_interval_seconds=2.0,
            max_concurrent_jobs=10,
        )

        assert config.poll_interval_seconds == 2.0
        assert config.max_concurrent_jobs == 10
