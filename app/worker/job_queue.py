"""
Background job queue using ThreadPoolExecutor.

Provides non-blocking analysis pipeline execution:
- submit_job(file_path) -> job_id
- get_status(job_id) -> JobStatus
- get_result(job_id) -> Optional[list[AnalysisReport]]

Thread-safe, single-instance. No external dependencies (no Redis/Celery).
"""

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from models.schemas import JobStatus

logger = logging.getLogger(__name__)

# Job states
PENDING = "PENDING"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"

# Default pool size
DEFAULT_MAX_WORKERS = 4


class _JobRecord:
    """Internal record tracking a single job."""
    __slots__ = (
        "job_id", "status", "created_at", "completed_at",
        "total_entries", "error", "result", "future",
    )

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = PENDING
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at: Optional[str] = None
        self.total_entries: int = 0
        self.error: Optional[str] = None
        self.result: Any = None
        self.future: Any = None

    def to_status(self) -> JobStatus:
        return JobStatus(
            job_id=self.job_id,
            status=self.status,
            created_at=self.created_at,
            completed_at=self.completed_at,
            total_entries=self.total_entries,
            error=self.error,
        )


class JobQueue:
    """
    Thread-safe background job queue for analysis pipeline.

    Usage:
        queue = JobQueue()
        job_id = queue.submit_job(pipeline_fn, file_path)
        status = queue.get_status(job_id)
        result = queue.get_result(job_id)

    The queue manages a ThreadPoolExecutor and in-memory job store.
    """

    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="analysis-worker",
        )
        self._jobs: dict[str, _JobRecord] = {}
        self._lock = threading.Lock()
        logger.info("JobQueue initialized with %d workers", max_workers)

    def submit_job(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """
        Submit a job to the background queue.

        Args:
            fn: The callable to execute (e.g., the analysis pipeline).
            *args: Positional arguments for fn.
            **kwargs: Keyword arguments for fn.

        Returns:
            job_id: Unique identifier for the submitted job.
        """
        job_id = str(uuid.uuid4())

        with self._lock:
            record = _JobRecord(job_id)
            self._jobs[job_id] = record

        future = self._executor.submit(self._run_job, job_id, fn, *args, **kwargs)
        record.future = future

        logger.info("Submitted job %s", job_id)
        return job_id

    def _run_job(self, job_id: str, fn: Callable, *args: Any, **kwargs: Any) -> None:
        """Execute a job and update its status."""
        with self._lock:
            record = self._jobs.get(job_id)
            if record:
                record.status = RUNNING

        try:
            result = fn(*args, **kwargs)

            with self._lock:
                record = self._jobs.get(job_id)
                if record:
                    record.status = COMPLETED
                    record.completed_at = datetime.now(timezone.utc).isoformat()
                    record.result = result
                    if isinstance(result, list):
                        record.total_entries = len(result)

            logger.info("Job %s completed successfully", job_id)

        except Exception as e:
            logger.exception("Job %s failed: %s", job_id, e)
            with self._lock:
                record = self._jobs.get(job_id)
                if record:
                    record.status = FAILED
                    record.completed_at = datetime.now(timezone.utc).isoformat()
                    record.error = str(e)

    def get_status(self, job_id: str) -> Optional[JobStatus]:
        """
        Get the status of a job.

        Returns None if job_id is not found.
        """
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            return record.to_status()

    def get_result(self, job_id: str) -> Any:
        """
        Get the result of a completed job.

        Returns None if the job is not found or not yet completed.
        """
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None or record.status != COMPLETED:
                return None
            return record.result

    def get_queue_size(self) -> int:
        """Return number of PENDING or RUNNING jobs."""
        with self._lock:
            return sum(
                1 for r in self._jobs.values()
                if r.status in (PENDING, RUNNING)
            )

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor."""
        self._executor.shutdown(wait=wait)
        logger.info("JobQueue shut down")


# Module-level singleton
_global_queue: Optional[JobQueue] = None
_queue_lock = threading.Lock()


def get_job_queue(max_workers: int = DEFAULT_MAX_WORKERS) -> JobQueue:
    """Get or create the global job queue singleton."""
    global _global_queue
    with _queue_lock:
        if _global_queue is None:
            _global_queue = JobQueue(max_workers=max_workers)
        return _global_queue
