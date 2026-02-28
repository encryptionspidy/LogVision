"""
Correlation engine — detects cascade patterns across root cause groups.

Analyzes temporal relationships between root cause events to identify
cascading failures:
  e.g., "Database connection failures between 14:00–14:05
         likely caused by service restart at 13:59."

Uses:
- Temporal proximity scoring
- Cross-template pattern matching
- Severity escalation chains
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from models.schemas import RootCauseEvent

logger = logging.getLogger(__name__)

# Correlation thresholds
TEMPORAL_PROXIMITY_SECONDS = 120   # 2 minutes
CASCADE_SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
MIN_CORRELATION_SCORE = 0.4


def _parse_time_window(
    event: RootCauseEvent,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse time_window tuple into datetime objects."""
    if not event.time_window:
        return None, None
    try:
        start = datetime.fromisoformat(event.time_window[0])
        end = datetime.fromisoformat(event.time_window[1])
        return start, end
    except (ValueError, IndexError):
        return None, None


def _temporal_overlap_score(
    event_a: RootCauseEvent,
    event_b: RootCauseEvent,
) -> float:
    """
    Score temporal proximity between two events.

    Returns 0.0–1.0:
    - 1.0 = fully overlapping time windows
    - 0.0 = no temporal relationship
    """
    a_start, a_end = _parse_time_window(event_a)
    b_start, b_end = _parse_time_window(event_b)

    if a_start is None or b_start is None:
        return 0.0

    # If they overlap
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end or a_start, b_end or b_start)

    if overlap_start <= overlap_end:
        return 1.0

    # If they're close in time
    gap = (overlap_start - overlap_end).total_seconds()
    if gap <= TEMPORAL_PROXIMITY_SECONDS:
        return max(0.0, 1.0 - (gap / TEMPORAL_PROXIMITY_SECONDS))

    return 0.0


def _severity_escalation_score(
    event_a: RootCauseEvent,
    event_b: RootCauseEvent,
) -> float:
    """
    Score whether event_b represents a severity escalation from event_a.

    Returns 0.0–0.5.
    """
    rank_a = CASCADE_SEVERITY_ORDER.get(event_a.severity, 0)
    rank_b = CASCADE_SEVERITY_ORDER.get(event_b.severity, 0)

    if rank_b > rank_a:
        # Escalation detected
        return min(0.5, (rank_b - rank_a) * 0.2)
    return 0.0


def _template_similarity_score(
    event_a: RootCauseEvent,
    event_b: RootCauseEvent,
) -> float:
    """
    Score template similarity between two events.

    Simple word-overlap approach.
    Returns 0.0–0.3.
    """
    words_a = set(event_a.template_pattern.lower().split())
    words_b = set(event_b.template_pattern.lower().split())

    if not words_a or not words_b:
        return 0.0

    overlap = len(words_a & words_b)
    union = len(words_a | words_b)

    jaccard = overlap / union if union > 0 else 0.0
    return round(jaccard * 0.3, 3)


def compute_correlation(
    event_a: RootCauseEvent,
    event_b: RootCauseEvent,
) -> float:
    """
    Compute correlation score between two root cause events.

    Combines:
    - Temporal proximity (weight: 0.5)
    - Severity escalation (weight: 0.3)
    - Template similarity (weight: 0.2)

    Returns:
        Score between 0.0 and 1.0.
    """
    temporal = _temporal_overlap_score(event_a, event_b) * 0.5
    escalation = _severity_escalation_score(event_a, event_b) * 0.3
    similarity = _template_similarity_score(event_a, event_b) * 0.2

    return round(temporal + escalation + similarity, 3)


def detect_cascades(
    events: list[RootCauseEvent],
    min_score: float = MIN_CORRELATION_SCORE,
) -> list[RootCauseEvent]:
    """
    Detect and merge cascading root cause events.

    Pairs of events with high correlation scores are merged into a single
    event with combined metadata.

    Args:
        events: Root cause events from the aggregator.
        min_score: Minimum correlation score to consider a cascade.

    Returns:
        Updated list of events with cascade relationships annotated.
    """
    if len(events) <= 1:
        return events

    # Build correlation matrix
    n = len(events)
    merged: set[int] = set()
    result: list[RootCauseEvent] = []

    for i in range(n):
        if i in merged:
            continue

        current = events[i]
        cascade_members = [i]

        for j in range(i + 1, n):
            if j in merged:
                continue

            score = compute_correlation(current, events[j])
            if score >= min_score:
                cascade_members.append(j)
                merged.add(j)

        if len(cascade_members) > 1:
            # Merge into a cascade event
            merged_event = _merge_cascade_events(
                [events[idx] for idx in cascade_members]
            )
            result.append(merged_event)
        else:
            result.append(current)

    logger.info(
        "Cascade detection: %d events → %d (merged %d cascades)",
        len(events),
        len(result),
        len(events) - len(result),
    )

    return result


def _merge_cascade_events(
    events: list[RootCauseEvent],
) -> RootCauseEvent:
    """Merge multiple cascade-related events into one."""
    if not events:
        raise ValueError("Cannot merge empty event list")

    # Use the highest-confidence event as the base
    events.sort(key=lambda e: e.confidence, reverse=True)
    primary = events[0]

    # Collect all related log IDs
    all_log_ids: list[int] = []
    all_templates: list[str] = []
    total_count = 0

    for e in events:
        all_log_ids.extend(e.related_log_ids)
        all_templates.append(e.template_pattern)
        total_count += e.event_count

    # Find broadest time window
    all_starts: list[str] = []
    all_ends: list[str] = []
    for e in events:
        if e.time_window:
            all_starts.append(e.time_window[0])
            all_ends.append(e.time_window[1])

    time_window = None
    if all_starts and all_ends:
        time_window = (min(all_starts), max(all_ends))

    # Build cascade description
    cascade_desc = (
        f"Cascade of {len(events)} related incident groups "
        f"({total_count} total events). "
        f"{primary.description}"
    )

    # Determine highest severity
    severity_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    highest_sev = max(events, key=lambda e: severity_rank.get(e.severity, 0))

    # Boost confidence for cascades
    boosted_confidence = min(primary.confidence + 0.1, 1.0)

    return RootCauseEvent(
        event_id=primary.event_id,
        title=f"[CASCADE] {primary.title}",
        description=cascade_desc,
        time_window=time_window,
        confidence=boosted_confidence,
        related_log_ids=sorted(set(all_log_ids)),
        severity=highest_sev.severity,
        template_pattern=primary.template_pattern,
        event_count=total_count,
    )
