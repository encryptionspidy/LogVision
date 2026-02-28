"""
Deterministic severity scorer.

Computes a severity score from rule-based weight, frequency weight,
and anomaly score, then maps to a categorical level.

The scoring formula:
    score = rule_weight * level_base + frequency_weight * freq_score + anomaly_weight * anomaly_score

Mapping:
    score >= 0.80 → CRITICAL
    score >= 0.60 → HIGH
    score >= 0.35 → MEDIUM
    score <  0.35 → LOW
"""

from __future__ import annotations

from app.severity.config import (
    RULE_WEIGHT,
    FREQUENCY_WEIGHT,
    ANOMALY_WEIGHT,
    CRITICAL_THRESHOLD,
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
    LEVEL_BASE_SCORES,
)
from app.utils.helpers import clamp
from models.schemas import (
    LogEntry,
    AnomalyResult,
    SeverityResult,
    SeverityLevel,
)


def compute_frequency_score(
    entry: LogEntry,
    total_entries: int,
    error_count: int,
) -> float:
    """
    Compute a frequency-based score component.

    Based on the ratio of error-level entries to total entries,
    adjusted by whether this entry is itself an error.

    Args:
        entry: The log entry being scored.
        total_entries: Total number of entries in the batch.
        error_count: Count of ERROR/CRITICAL entries in the batch.

    Returns:
        Frequency score between 0.0 and 1.0.
    """
    if total_entries == 0:
        return 0.0

    error_ratio = error_count / total_entries

    # Base frequency score from the error ratio in the batch
    base = clamp(error_ratio * 2.0)  # 50% errors → 1.0

    # Boost if this entry is itself an error
    if entry.log_level.value in ("ERROR", "CRITICAL"):
        base = clamp(base + 0.2)

    return base


def score_entry(
    entry: LogEntry,
    anomaly: AnomalyResult,
    total_entries: int = 1,
    error_count: int = 0,
) -> SeverityResult:
    """
    Compute deterministic severity score for a single log entry.

    Args:
        entry: Parsed log entry.
        anomaly: Anomaly detection result for this entry.
        total_entries: Total entries in the batch.
        error_count: Total error-level entries in the batch.

    Returns:
        SeverityResult with level, score, and breakdown.
    """
    # Component 1: Level-based rule score
    level_base = LEVEL_BASE_SCORES.get(entry.log_level.value, 0.2)

    # Component 2: Frequency score
    freq_score = compute_frequency_score(
        entry, total_entries, error_count
    )

    # Component 3: Anomaly score (from evaluator)
    anomaly_score = anomaly.confidence

    # Weighted combination
    final_score = clamp(
        RULE_WEIGHT * level_base
        + FREQUENCY_WEIGHT * freq_score
        + ANOMALY_WEIGHT * anomaly_score
    )

    # Deterministic level mapping
    if final_score >= CRITICAL_THRESHOLD:
        level = SeverityLevel.CRITICAL
    elif final_score >= HIGH_THRESHOLD:
        level = SeverityLevel.HIGH
    elif final_score >= MEDIUM_THRESHOLD:
        level = SeverityLevel.MEDIUM
    else:
        level = SeverityLevel.LOW

    return SeverityResult(
        level=level,
        score=round(final_score, 4),
        breakdown={
            "level_base": round(level_base, 4),
            "frequency_score": round(freq_score, 4),
            "anomaly_score": round(anomaly_score, 4),
            "rule_weight": RULE_WEIGHT,
            "frequency_weight": FREQUENCY_WEIGHT,
            "anomaly_weight": ANOMALY_WEIGHT,
        },
    )


def score_entries(
    entries: list[LogEntry],
    anomalies: dict[int, AnomalyResult],
) -> dict[int, SeverityResult]:
    """
    Score all entries in a batch.

    Args:
        entries: All parsed log entries.
        anomalies: Anomaly results keyed by line_number.

    Returns:
        Dict mapping line_number → SeverityResult.
    """
    total = len(entries)
    error_count = sum(
        1 for e in entries
        if e.log_level.value in ("ERROR", "CRITICAL")
    )

    results: dict[int, SeverityResult] = {}
    for entry in entries:
        anomaly = anomalies.get(entry.line_number, AnomalyResult())
        results[entry.line_number] = score_entry(
            entry, anomaly, total, error_count
        )

    return results
