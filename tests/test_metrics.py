"""Tests for the system metrics collector."""

from __future__ import annotations

import time
import pytest

from app.metrics.system_metrics import MetricsCollector, _percentile


class TestMetricsCollector:
    def setup_method(self):
        self.collector = MetricsCollector()

    def test_initial_state(self):
        metrics = self.collector.get_metrics()
        assert metrics.total_requests == 0
        assert metrics.error_rate == 0.0
        assert metrics.avg_latency_ms == 0.0

    def test_record_successful_request(self):
        self.collector.record_request(50.0, success=True)
        metrics = self.collector.get_metrics()
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.avg_latency_ms == 50.0

    def test_record_failed_request(self):
        self.collector.record_request(100.0, success=False)
        metrics = self.collector.get_metrics()
        assert metrics.total_requests == 1
        assert metrics.failed_requests == 1
        assert metrics.error_rate == 1.0

    def test_error_rate_calculation(self):
        for _ in range(7):
            self.collector.record_request(10.0, success=True)
        for _ in range(3):
            self.collector.record_request(10.0, success=False)

        metrics = self.collector.get_metrics()
        assert abs(metrics.error_rate - 0.3) < 0.01

    def test_latency_percentiles(self):
        for i in range(100):
            self.collector.record_request(float(i + 1), success=True)

        metrics = self.collector.get_metrics()
        assert metrics.p95_latency_ms >= 90
        assert metrics.p99_latency_ms >= 95
        assert metrics.max_latency_ms == 100.0

    def test_queue_backlog(self):
        self.collector.record_queue_size(5)
        metrics = self.collector.get_metrics()
        assert metrics.queue_backlog == 5

    def test_to_dict(self):
        self.collector.record_request(25.0)
        d = self.collector.get_metrics().to_dict()
        assert "total_requests" in d
        assert "avg_latency_ms" in d
        assert "uptime_seconds" in d
        assert isinstance(d["avg_latency_ms"], float)

    def test_reset(self):
        self.collector.record_request(50.0)
        self.collector.reset()
        metrics = self.collector.get_metrics()
        assert metrics.total_requests == 0

    def test_uptime_tracking(self):
        time.sleep(0.1)
        metrics = self.collector.get_metrics()
        assert metrics.uptime_seconds >= 0.1


class TestPercentile:
    def test_empty(self):
        assert _percentile([], 0.95) == 0.0

    def test_single(self):
        assert _percentile([42.0], 0.95) == 42.0

    def test_known_values(self):
        values = [float(i) for i in range(1, 101)]
        p50 = _percentile(values, 0.50)
        assert 49 <= p50 <= 51
        p95 = _percentile(values, 0.95)
        assert 94 <= p95 <= 96
