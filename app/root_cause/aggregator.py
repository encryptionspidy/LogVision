"""
Root cause aggregator — groups log entries into root cause events.

Groups related log anomalies by:
1. Template similarity (reuses Drain-style template mining)
2. Time window proximity
3. Severity escalation patterns

Produces RootCauseEvent objects that collapse hundreds of individual
errors into actionable incident groups.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from app.clustering.template_miner import extract_template
from models.schemas import AnalysisReport, RootCauseEvent, SeverityLevel

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_TIME_WINDOW_SECONDS = 300  # 5 minutes
DEFAULT_MIN_GROUP_SIZE = 2


def _severity_rank(level: SeverityLevel) -> int:
    """Numeric rank for severity ordering."""
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}.get(level.value, 0)


def _dominant_severity(reports: list[AnalysisReport]) -> SeverityLevel:
    """Return the highest severity in a group of reports."""
    if not reports:
        return SeverityLevel.LOW
    return max(
        (r.severity.level for r in reports),
        key=lambda s: _severity_rank(s),
    )


def _compute_confidence(
    group_size: int,
    total_entries: int,
    has_escalation: bool,
) -> float:
    """
    Compute confidence score for a root cause group.

    Based on:
    - Group density (how many entries it covers)
    - Whether severity escalated within the group
    """
    if total_entries == 0:
        return 0.0

    density = min(group_size / max(total_entries, 1), 1.0)
    base_confidence = 0.3 + (density * 0.4)

    if has_escalation:
        base_confidence += 0.2

    if group_size >= 10:
        base_confidence += 0.1

    return round(min(base_confidence, 1.0), 3)


def _detect_severity_escalation(reports: list[AnalysisReport]) -> bool:
    """Check if severity escalated over time within a group."""
    if len(reports) < 2:
        return False

    timed = [
        r for r in reports
        if r.log_entry.timestamp is not None
    ]
    if len(timed) < 2:
        return False

    timed.sort(key=lambda r: r.log_entry.timestamp)  # type: ignore[arg-type]

    first_half = timed[: len(timed) // 2]
    second_half = timed[len(timed) // 2 :]

    avg_first = sum(_severity_rank(r.severity.level) for r in first_half) / len(first_half)
    avg_second = sum(_severity_rank(r.severity.level) for r in second_half) / len(second_half)

    return avg_second > avg_first + 0.5


def _generate_title(template: str, severity: SeverityLevel, count: int) -> str:
    """Generate a human-readable title for a root cause group."""
    # Truncate long templates
    short_template = template[:80] + "..." if len(template) > 80 else template
    return f"[{severity.value}] {short_template} ({count} occurrences)"


def _generate_description(
    template: str,
    reports: list[AnalysisReport],
    time_start: Optional[datetime],
    time_end: Optional[datetime],
) -> str:
    """Generate a description for a root cause group."""
    parts = []

    if time_start and time_end:
        duration = time_end - time_start
        minutes = int(duration.total_seconds() / 60)
        parts.append(
            f"Cluster of {len(reports)} related events between "
            f"{time_start.strftime('%H:%M:%S')} and {time_end.strftime('%H:%M:%S')} "
            f"(~{minutes} min window)."
        )
    else:
        parts.append(f"Cluster of {len(reports)} related events.")

    # Add example explanations
    explanations = [
        r.explanation.summary
        for r in reports[:3]
        if r.explanation.summary
    ]
    if explanations:
        parts.append("Likely caused by: " + "; ".join(set(explanations)))

    return " ".join(parts)


def aggregate_root_causes(
    reports: list[AnalysisReport],
    time_window_seconds: int = DEFAULT_TIME_WINDOW_SECONDS,
    min_group_size: int = DEFAULT_MIN_GROUP_SIZE,
) -> list[RootCauseEvent]:
    """
    Group analysis reports into root cause events.

    Algorithm:
    1. Extract template for each report's log message
    2. Group by template
    3. Sub-group by time window within each template group
    4. Score and annotate each group

    Args:
        reports: List of analysis reports (typically anomalous ones).
        time_window_seconds: Maximum gap between events in the same group.
        min_group_size: Minimum number of events to form a root cause group.

    Returns:
        List of RootCauseEvent objects, sorted by confidence (descending).
    """
    if not reports:
        return []

    # Step 1: Group by template
    template_groups: dict[str, list[AnalysisReport]] = defaultdict(list)
    for report in reports:
        template = extract_template(report.log_entry.message)
        template_groups[template].append(report)

    # Step 2: Sub-group by time window
    root_causes: list[RootCauseEvent] = []
    event_id = 0

    for template, group in template_groups.items():
        # Sort by timestamp (entries without timestamps go to the end)
        group.sort(
            key=lambda r: r.log_entry.timestamp or datetime.max
        )

        # Split into time-window sub-groups
        sub_groups = _split_by_time_window(group, time_window_seconds)

        for sub_group in sub_groups:
            if len(sub_group) < min_group_size:
                continue

            # Compute time bounds
            timestamps = [
                r.log_entry.timestamp
                for r in sub_group
                if r.log_entry.timestamp is not None
            ]
            time_start = min(timestamps) if timestamps else None
            time_end = max(timestamps) if timestamps else None

            # Detect escalation
            has_escalation = _detect_severity_escalation(sub_group)

            # Compute severity and confidence
            severity = _dominant_severity(sub_group)
            confidence = _compute_confidence(
                group_size=len(sub_group),
                total_entries=len(reports),
                has_escalation=has_escalation,
            )

            # Build event
            time_window = None
            if time_start and time_end:
                time_window = (
                    time_start.isoformat(),
                    time_end.isoformat(),
                )

            root_cause = RootCauseEvent(
                event_id=event_id,
                title=_generate_title(template, severity, len(sub_group)),
                description=_generate_description(
                    template, sub_group, time_start, time_end
                ),
                time_window=time_window,
                confidence=confidence,
                related_log_ids=[r.log_entry.line_number for r in sub_group],
                severity=severity.value,
                template_pattern=template,
                event_count=len(sub_group),
            )
            root_causes.append(root_cause)
            event_id += 1

    # Sort by confidence descending
    root_causes.sort(key=lambda e: e.confidence, reverse=True)

    logger.info(
        "Aggregated %d reports into %d root cause events",
        len(reports),
        len(root_causes),
    )

    return root_causes


def _split_by_time_window(
    sorted_reports: list[AnalysisReport],
    window_seconds: int,
) -> list[list[AnalysisReport]]:
    """
    Split a sorted list of reports into sub-groups separated by time gaps.

    Reports without timestamps are placed in a single catch-all group.
    """
    if not sorted_reports:
        return []

    timed: list[AnalysisReport] = []
    untimed: list[AnalysisReport] = []

    for r in sorted_reports:
        if r.log_entry.timestamp is not None:
            timed.append(r)
        else:
            untimed.append(r)

    groups: list[list[AnalysisReport]] = []

    if timed:
        current_group = [timed[0]]
        for r in timed[1:]:
            prev_ts = current_group[-1].log_entry.timestamp
            curr_ts = r.log_entry.timestamp
            gap = (curr_ts - prev_ts).total_seconds()  # type: ignore[operator]
            if gap <= window_seconds:
                current_group.append(r)
            else:
                groups.append(current_group)
                current_group = [r]
        groups.append(current_group)

    if untimed:
        groups.append(untimed)

    return groups
