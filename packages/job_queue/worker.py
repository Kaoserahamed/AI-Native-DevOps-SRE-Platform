"""Worker for processing queued jobs with graceful shutdown."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
import signal
from typing import Any

from packages.job_queue.job import Job
from packages.job_queue.queue import JobQueue

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Configuration for worker behavior."""

    poll_interval_seconds: float = 1.0
    visibility_timeout_seconds: int = 300
    stuck_job_check_interval_seconds: int = 60
    max_concurrent_jobs: int = 5
    graceful_shutdown_timeout_seconds: int = 30


JobHandler = Callable[[Job], Awaitable[dict[str, Any] | None]]


class Worker:
    """Asynchronous job worker with graceful shutdown."""

    def __init__(
        self,
        queue: JobQueue,
        handlers: dict[str, JobHandler],
        config: WorkerConfig | None = None,
    ) -> None:
        """Initialize worker.

        Parameters
        ----------
        queue
            Job queue to process from
        handlers
            Map of job_type -> handler function
        config
            Worker configuration
        """
        self.queue = queue
        self.handlers = handlers
        self.config = config or WorkerConfig()

        self.running = False
        self.shutdown_requested = False
        self.active_jobs: set[asyncio.Task[None]] = set()
        self.health_status = "starting"

    async def start(self) -> None:
        """Start the worker loop."""
        logger.info("Worker starting with %d handlers", len(self.handlers))
        self.running = True
        self.health_status = "healthy"

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

        # Start background tasks
        stuck_job_task = asyncio.create_task(self._stuck_job_monitor())

        try:
            while self.running:
                if self.shutdown_requested:
                    logger.info("Shutdown requested, stopping main loop")
                    break

                # Check if we can process more jobs
                if len(self.active_jobs) >= self.config.max_concurrent_jobs:
                    await asyncio.sleep(self.config.poll_interval_seconds)
                    continue

                # Try to dequeue a job
                job = await self.queue.dequeue(self.config.visibility_timeout_seconds)

                if job is None:
                    await asyncio.sleep(self.config.poll_interval_seconds)
                    continue

                # Process job in background
                task = asyncio.create_task(self._process_job(job))
                self.active_jobs.add(task)
                task.add_done_callback(self.active_jobs.discard)

        except Exception as exc:
            logger.exception("Worker error: %s", exc)
            self.health_status = "unhealthy"
        finally:
            stuck_job_task.cancel()
            await self._graceful_shutdown()

    async def stop(self) -> None:
        """Request worker shutdown."""
        logger.info("Worker stop requested")
        self.shutdown_requested = True
        self.running = False

    async def _process_job(self, job: Job) -> None:
        """Process a single job."""
        logger.info("Processing job %s (type: %s)", job.job_id, job.job_type)

        try:
            # Find handler
            handler = self.handlers.get(job.job_type)
            if not handler:
                error_msg = f"No handler registered for job type: {job.job_type}"
                logger.error(error_msg)
                await self.queue.fail(job.job_id, error_msg, retry=False)
                return

            # Execute handler
            result = await handler(job)

            # Mark as complete
            await self.queue.complete(job.job_id, result)

            logger.info("Job %s completed successfully", job.job_id)

        except Exception as exc:
            logger.exception("Job %s failed: %s", job.job_id, exc)
            await self.queue.fail(job.job_id, str(exc), retry=True)

    async def _stuck_job_monitor(self) -> None:
        """Background task to requeue stuck jobs."""
        while self.running:
            try:
                await asyncio.sleep(self.config.stuck_job_check_interval_seconds)

                if self.shutdown_requested:
                    break

                requeued = await self.queue.requeue_stuck_jobs()
                if requeued > 0:
                    logger.warning("Requeued %d stuck jobs", requeued)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Error in stuck job monitor: %s", exc)

    async def _graceful_shutdown(self) -> None:
        """Wait for active jobs to complete."""
        if not self.active_jobs:
            logger.info("No active jobs, shutdown complete")
            return

        logger.info("Waiting for %d active jobs to complete", len(self.active_jobs))
        self.health_status = "draining"

        try:
            await asyncio.wait_for(
                asyncio.gather(*self.active_jobs, return_exceptions=True),
                timeout=self.config.graceful_shutdown_timeout_seconds,
            )
            logger.info("All active jobs completed")
        except TimeoutError:
            logger.warning(
                "Graceful shutdown timeout, %d jobs still running", len(self.active_jobs)
            )

        self.health_status = "stopped"

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        try:
            loop = asyncio.get_running_loop()

            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

            logger.info("Signal handlers registered")
        except NotImplementedError:
            # Signal handlers not available on Windows
            logger.warning("Signal handlers not available on this platform")

    def get_health_status(self) -> dict[str, Any]:
        """Get worker health status.

        Returns
        -------
        dict[str, Any]
            Health status information
        """
        return {
            "status": self.health_status,
            "running": self.running,
            "active_jobs": len(self.active_jobs),
            "max_concurrent_jobs": self.config.max_concurrent_jobs,
            "shutdown_requested": self.shutdown_requested,
        }
