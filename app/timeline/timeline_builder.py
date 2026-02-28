"""
Timeline builder — generates chronological anomaly timelines.

Creates time-bucketed event summaries for visualization, including:
- Event counts per time bucket
- Severity distribution per bucket
- Spike detection using z-score
- Top events per bucket for detail drill-down
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from models.schemas import AnalysisReport, TimelineEvent, SeverityLevel

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_BUCKET_MINUTES = 15
DEFAULT_HOURS = 6
SPIKE_ZSCORE_THRESHOLD = 2.0


def _bucket_key(dt: datetime, bucket_minutes: int) -> datetime:
    """Round a datetime down to the nearest bucket boundary."""
    minute = (dt.minute // bucket_minutes) * bucket_minutes
    return dt.replace(minute=minute, second=0, microsecond=0)


def build_timeline(
    reports: list[AnalysisReport],
    hours: int = DEFAULT_HOURS,
    bucket_minutes: int = DEFAULT_BUCKET_MINUTES,
    reference_time: Optional[datetime] = None,
) -> list[TimelineEvent]:
    """
    Build a timeline of events from analysis reports.

    Groups reports into time buckets, counts events, and detects spikes.

    Args:
        reports: List of analysis reports (typically from DB).
        hours: How many hours of history to include.
        bucket_minutes: Size of each time bucket in minutes.
        reference_time: End of the timeline window (default: now).

    Returns:
        List of TimelineEvent objects, ordered chronologically.
    """
    if not reports:
        return []

    ref = reference_time or datetime.utcnow()
    cutoff = ref - timedelta(hours=hours)

    # Filter to time window and reports with timestamps
    filtered = [
        r for r in reports
        if r.log_entry.timestamp is not None
        and r.log_entry.timestamp >= cutoff
    ]

    if not filtered:
        return []

    # Bucket reports
    buckets: dict[datetime, list[AnalysisReport]] = defaultdict(list)
    for report in filtered:
        key = _bucket_key(report.log_entry.timestamp, bucket_minutes)  # type: ignore[arg-type]
        buckets[key].append(report)

    # Generate all bucket slots (even empty ones)
    bucket_start = _bucket_key(cutoff, bucket_minutes)
    bucket_end = _bucket_key(ref, bucket_minutes)
    all_slots: list[datetime] = []
    current = bucket_start
    while current <= bucket_end:
        all_slots.append(current)
        current += timedelta(minutes=bucket_minutes)

    # Compute counts for spike detection
    counts = [len(buckets.get(slot, [])) for slot in all_slots]
    mean_count, std_count = _mean_std(counts)

    # Build timeline events
    timeline: list[TimelineEvent] = []
    for slot in all_slots:
        slot_reports = buckets.get(slot, [])
        count = len(slot_reports)

        # Severity distribution
        severity_counts: dict[str, int] = defaultdict(int)
        for r in slot_reports:
            severity_counts[r.severity.level.value] += 1

        # Spike detection
        is_spike = False
        if std_count > 0:
            z_score = (count - mean_count) / std_count
            is_spike = z_score >= SPIKE_ZSCORE_THRESHOLD

        # Top events (most severe, limited to 5)
        top = sorted(
            slot_reports,
            key=lambda r: _severity_rank(r.severity.level),
            reverse=True,
        )[:5]
        top_events = [
            {
                "line_number": r.log_entry.line_number,
                "message": r.log_entry.message[:200],
                "severity": r.severity.level.value,
                "score": r.severity.score,
            }
            for r in top
        ]

        end_time = slot + timedelta(minutes=bucket_minutes)
        timeline.append(TimelineEvent(
            bucket_start=slot.isoformat(),
            bucket_end=end_time.isoformat(),
            event_count=count,
            severity_counts=dict(severity_counts),
            is_spike=is_spike,
            top_events=top_events,
        ))

    logger.info(
        "Built timeline: %d buckets (%d-min) over %dh, %d spikes",
        len(timeline),
        bucket_minutes,
        hours,
        sum(1 for e in timeline if e.is_spike),
    )

    return timeline


def _severity_rank(level: SeverityLevel) -> int:
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}.get(level.value, 0)


def _mean_std(values: list[int]) -> tuple[float, float]:
    """Compute mean and standard deviation."""
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(variance)
