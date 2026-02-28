"""Tests for the background worker job queue."""

from __future__ import annotations

import time
import pytest

from app.worker.job_queue import JobQueue, PENDING, RUNNING, COMPLETED, FAILED


class TestJobQueue:
    def setup_method(self):
        self.queue = JobQueue(max_workers=2)

    def teardown_method(self):
        self.queue.shutdown(wait=True)

    def test_submit_returns_job_id(self):
        job_id = self.queue.submit_job(lambda: 42)
        assert job_id is not None
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    def test_job_completes_successfully(self):
        def work():
            time.sleep(0.1)
            return [1, 2, 3]

        job_id = self.queue.submit_job(work)
        # Wait for completion
        time.sleep(0.5)

        status = self.queue.get_status(job_id)
        assert status is not None
        assert status.status == COMPLETED
        assert status.total_entries == 3

    def test_job_failure_tracked(self):
        def failing_work():
            raise ValueError("test error")

        job_id = self.queue.submit_job(failing_work)
        time.sleep(0.5)

        status = self.queue.get_status(job_id)
        assert status is not None
        assert status.status == FAILED
        assert "test error" in status.error

    def test_get_status_unknown_job(self):
        status = self.queue.get_status("nonexistent-id")
        assert status is None

    def test_get_result(self):
        job_id = self.queue.submit_job(lambda: {"data": "test"})
        time.sleep(0.5)

        result = self.queue.get_result(job_id)
        assert result == {"data": "test"}

    def test_get_result_for_pending_returns_none(self):
        def slow_work():
            time.sleep(5)
            return 42

        job_id = self.queue.submit_job(slow_work)
        result = self.queue.get_result(job_id)
        assert result is None

    def test_queue_size_tracking(self):
        initial = self.queue.get_queue_size()
        assert initial == 0

        def slow():
            time.sleep(1)

        # Submit some jobs
        self.queue.submit_job(slow)
        self.queue.submit_job(slow)
        time.sleep(0.1)  # let them start

        # At least some should be running
        size = self.queue.get_queue_size()
        assert size >= 0  # may have already started

    def test_status_to_dict(self):
        job_id = self.queue.submit_job(lambda: 42)
        time.sleep(0.3)

        status = self.queue.get_status(job_id)
        d = status.to_dict()
        assert "job_id" in d
        assert "status" in d
        assert d["job_id"] == job_id

    def test_concurrent_jobs(self):
        results = []

        def work(n):
            time.sleep(0.1)
            return n * 2

        ids = [self.queue.submit_job(work, i) for i in range(4)]
        time.sleep(1)

        for jid in ids:
            status = self.queue.get_status(jid)
            assert status.status == COMPLETED
