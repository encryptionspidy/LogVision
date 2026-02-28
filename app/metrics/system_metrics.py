"""
System metrics collector — self-observability for the analyzer platform.

Tracks:
- Processing latency (per-request timing)
- Throughput (requests per second / total)
- Error rate
- Queue backlog

Thread-safe singleton pattern.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Rolling window for rate calculations
ROLLING_WINDOW_SECONDS = 300  # 5 minutes


@dataclass
class MetricsSnapshot:
    """Point-in-time metrics snapshot."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    throughput_rpm: float = 0.0  # requests per minute
    queue_backlog: int = 0
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate": round(self.error_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "throughput_rpm": round(self.throughput_rpm, 2),
            "queue_backlog": self.queue_backlog,
            "uptime_seconds": round(self.uptime_seconds, 1),
        }


class MetricsCollector:
    """
    Thread-safe metrics collector for system observability.

    Tracks request latencies, success/failure counts, and queue backlog.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.monotonic()
        self._total_requests = 0
        self._successful = 0
        self._failed = 0
        self._latencies: deque[tuple[float, float]] = deque()  # (timestamp, ms)
        self._queue_backlog = 0

    def record_request(self, duration_ms: float, success: bool = True) -> None:
        """
        Record a completed request.

        Args:
            duration_ms: Request duration in milliseconds.
            success: Whether the request succeeded.
        """
        now = time.time()
        with self._lock:
            self._total_requests += 1
            if success:
                self._successful += 1
            else:
                self._failed += 1
            self._latencies.append((now, duration_ms))
            # Prune old entries
            cutoff = now - ROLLING_WINDOW_SECONDS
            while self._latencies and self._latencies[0][0] < cutoff:
                self._latencies.popleft()

    def record_queue_size(self, size: int) -> None:
        """Update the current queue backlog."""
        with self._lock:
            self._queue_backlog = size

    def get_metrics(self) -> MetricsSnapshot:
        """Get a snapshot of current metrics."""
        with self._lock:
            now = time.time()
            uptime = time.monotonic() - self._start_time

            # Error rate
            error_rate = 0.0
            if self._total_requests > 0:
                error_rate = self._failed / self._total_requests

            # Latency stats from rolling window
            cutoff = now - ROLLING_WINDOW_SECONDS
            recent = [ms for ts, ms in self._latencies if ts >= cutoff]

            avg_latency = 0.0
            p95_latency = 0.0
            p99_latency = 0.0
            max_latency = 0.0

            if recent:
                sorted_latencies = sorted(recent)
                avg_latency = sum(sorted_latencies) / len(sorted_latencies)
                max_latency = sorted_latencies[-1]
                p95_latency = _percentile(sorted_latencies, 0.95)
                p99_latency = _percentile(sorted_latencies, 0.99)

            # Throughput (requests per minute in rolling window)
            window_requests = len(recent)
            window_minutes = ROLLING_WINDOW_SECONDS / 60.0
            throughput = window_requests / window_minutes if window_minutes > 0 else 0.0

            return MetricsSnapshot(
                total_requests=self._total_requests,
                successful_requests=self._successful,
                failed_requests=self._failed,
                error_rate=error_rate,
                avg_latency_ms=avg_latency,
                p95_latency_ms=p95_latency,
                p99_latency_ms=p99_latency,
                max_latency_ms=max_latency,
                throughput_rpm=throughput,
                queue_backlog=self._queue_backlog,
                uptime_seconds=uptime,
            )

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._start_time = time.monotonic()
            self._total_requests = 0
            self._successful = 0
            self._failed = 0
            self._latencies.clear()
            self._queue_backlog = 0


def _percentile(sorted_values: list[float], p: float) -> float:
    """Calculate the p-th percentile from a sorted list."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p
    f = int(k)
    c = f + 1
    if c >= len(sorted_values):
        return sorted_values[-1]
    d = k - f
    return sorted_values[f] + d * (sorted_values[c] - sorted_values[f])


# Module-level singleton
_collector: Optional[MetricsCollector] = None
_collector_lock = threading.Lock()


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector singleton."""
    global _collector
    with _collector_lock:
        if _collector is None:
            _collector = MetricsCollector()
        return _collector
