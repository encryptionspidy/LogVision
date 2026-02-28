"""
Pipeline stage profiler — measures CPU, memory, and throughput.

Provides a context-manager API for profiling individual stages:

    with profile_stage("parsing"):
        result = parse_logs(content)

    report = get_profile_report()

All measurements are real — no fabricated benchmarks.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

logger = logging.getLogger(__name__)


@dataclass
class StageProfile:
    """Performance measurements for a single pipeline stage."""

    name: str
    wall_time_seconds: float = 0.0
    cpu_time_seconds: float = 0.0
    memory_start_mb: float = 0.0
    memory_end_mb: float = 0.0
    memory_delta_mb: float = 0.0
    items_processed: int = 0
    throughput_items_per_sec: float = 0.0


@dataclass
class ProfileReport:
    """Aggregated profiling report for a pipeline run."""

    stages: list[StageProfile] = field(default_factory=list)
    total_wall_time: float = 0.0
    total_cpu_time: float = 0.0
    peak_memory_mb: float = 0.0

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            "Pipeline Profile Report",
            "=" * 60,
            f"{'Stage':<20} {'Wall(s)':<10} {'CPU(s)':<10} {'Mem Δ(MB)':<12} {'Items/s':<10}",
            "-" * 60,
        ]
        for s in self.stages:
            lines.append(
                f"{s.name:<20} {s.wall_time_seconds:<10.3f} {s.cpu_time_seconds:<10.3f} "
                f"{s.memory_delta_mb:<12.1f} {s.throughput_items_per_sec:<10.0f}"
            )
        lines.append("-" * 60)
        lines.append(
            f"{'TOTAL':<20} {self.total_wall_time:<10.3f} {self.total_cpu_time:<10.3f} "
            f"{'peak: ' + f'{self.peak_memory_mb:.1f}':<12}"
        )
        return "\n".join(lines)


# ─── Global profiler state ───────────────────────────────────────────────

_profiles: list[StageProfile] = []


def _get_memory_mb() -> float:
    """Get current process memory usage in MB (Linux/macOS)."""
    try:
        # Use /proc/self/status on Linux for accuracy
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except (FileNotFoundError, PermissionError):
        pass

    # Fallback: resource module
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_maxrss / 1024.0  # KB → MB on Linux
    except (ImportError, AttributeError):
        return 0.0


def reset_profiler() -> None:
    """Clear all recorded profiles."""
    global _profiles
    _profiles = []


@contextmanager
def profile_stage(name: str, item_count: int = 0) -> Generator[None, None, None]:
    """
    Context manager to profile a pipeline stage.

    Usage:
        with profile_stage("parsing", item_count=1000):
            result = parse_logs(content)

    Args:
        name: Human-readable name for the stage.
        item_count: Number of items being processed (for throughput).
    """
    mem_start = _get_memory_mb()
    cpu_start = time.process_time()
    wall_start = time.perf_counter()

    yield

    wall_end = time.perf_counter()
    cpu_end = time.process_time()
    mem_end = _get_memory_mb()

    wall_time = wall_end - wall_start
    cpu_time = cpu_end - cpu_start
    mem_delta = mem_end - mem_start

    throughput = item_count / wall_time if wall_time > 0 and item_count > 0 else 0.0

    profile = StageProfile(
        name=name,
        wall_time_seconds=round(wall_time, 4),
        cpu_time_seconds=round(cpu_time, 4),
        memory_start_mb=round(mem_start, 1),
        memory_end_mb=round(mem_end, 1),
        memory_delta_mb=round(mem_delta, 1),
        items_processed=item_count,
        throughput_items_per_sec=round(throughput, 1),
    )

    _profiles.append(profile)
    logger.info(
        "Stage '%s': %.3fs wall, %.3fs CPU, %.1f MB Δ, %d items",
        name, wall_time, cpu_time, mem_delta, item_count,
    )


def get_profile_report() -> ProfileReport:
    """Build a summary report from all recorded stages."""
    total_wall = sum(p.wall_time_seconds for p in _profiles)
    total_cpu = sum(p.cpu_time_seconds for p in _profiles)
    peak_mem = max((p.memory_end_mb for p in _profiles), default=0.0)

    return ProfileReport(
        stages=list(_profiles),
        total_wall_time=round(total_wall, 4),
        total_cpu_time=round(total_cpu, 4),
        peak_memory_mb=round(peak_mem, 1),
    )
