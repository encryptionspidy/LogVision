"""
Rule-based anomaly detection engine.

Detects anomalies using:
1. Frequency spike detection (sliding window).
2. Critical keyword matching.
3. Repeated error pattern detection.

Returns per-entry anomaly flags and confidence scores.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Optional

from app.config.settings import DEFAULT_CONFIG, AnomalyConfig
from app.utils.helpers import clamp
from models.schemas import LogEntry, LogLevel, AnomalyResult


def detect_critical_keywords(
    entry: LogEntry,
    keywords: tuple[str, ...] | None = None,
) -> tuple[bool, float, str]:
    """
    Check if a log entry contains critical keywords.

    Args:
        entry: Parsed log entry.
        keywords: Tuple of keywords to check; uses config default if None.

    Returns:
        (is_match, confidence, detail_string)
    """
    kws = keywords or DEFAULT_CONFIG.anomaly.critical_keywords
    message_lower = entry.message.lower()

    matched = []
    for kw in kws:
        if kw in message_lower:
            matched.append(kw)

    if not matched:
        return False, 0.0, ""

    # More keyword matches → higher confidence
    confidence = clamp(0.5 + 0.1 * len(matched))
    detail = f"Critical keywords found: {', '.join(matched)}"
    return True, confidence, detail


def detect_frequency_spikes(
    entries: list[LogEntry],
    config: Optional[AnomalyConfig] = None,
) -> dict[int, tuple[float, str]]:
    """
    Detect entries that belong to frequency spikes.

    Groups entries by time window and flags windows where the count
    exceeds the threshold.

    Args:
        entries: All parsed log entries.
        config: Anomaly config override.

    Returns:
        Dict mapping line_number → (confidence, detail) for spiked entries.
    """
    cfg = config or DEFAULT_CONFIG.anomaly
    results: dict[int, tuple[float, str]] = {}

    # Group entries by time window
    windowed: dict[int, list[LogEntry]] = defaultdict(list)
    entries_with_time = [e for e in entries if e.timestamp is not None]

    if not entries_with_time:
        # Without timestamps, use sequential grouping
        window_size = cfg.frequency_spike_threshold
        for i, entry in enumerate(entries):
            window_idx = i // window_size
            windowed[window_idx].append(entry)
    else:
        # Sort by timestamp for windowing
        sorted_entries = sorted(entries_with_time, key=lambda e: e.timestamp)  # type: ignore
        if sorted_entries:
            base_time = sorted_entries[0].timestamp
            for entry in sorted_entries:
                delta = (entry.timestamp - base_time).total_seconds()  # type: ignore
                window_idx = int(delta // cfg.frequency_window_seconds)
                windowed[window_idx].append(entry)

    # Find spike windows
    for window_idx, window_entries in windowed.items():
        count = len(window_entries)
        if count >= cfg.frequency_spike_threshold:
            # Confidence proportional to how much the spike exceeds threshold
            ratio = count / cfg.frequency_spike_threshold
            confidence = clamp(0.4 + 0.15 * (ratio - 1))
            detail = f"Frequency spike: {count} entries in window (threshold: {cfg.frequency_spike_threshold})"
            for entry in window_entries:
                results[entry.line_number] = (confidence, detail)

    return results


def detect_repeated_errors(
    entries: list[LogEntry],
    min_repeats: int = 3,
) -> dict[int, tuple[float, str]]:
    """
    Detect error messages that repeat suspiciously.

    Args:
        entries: All parsed log entries.
        min_repeats: Minimum repetitions to flag.

    Returns:
        Dict mapping line_number → (confidence, detail) for repeated entries.
    """
    results: dict[int, tuple[float, str]] = {}

    # Count error-level messages
    error_entries = [
        e for e in entries
        if e.log_level in (LogLevel.ERROR, LogLevel.CRITICAL)
    ]

    message_counts: Counter = Counter()
    message_lines: dict[str, list[int]] = defaultdict(list)

    for entry in error_entries:
        # Normalize message for comparison (first 100 chars)
        msg_key = entry.message[:100].strip().lower()
        message_counts[msg_key] += 1
        message_lines[msg_key].append(entry.line_number)

    for msg_key, count in message_counts.items():
        if count >= min_repeats:
            confidence = clamp(0.3 + 0.1 * count)
            detail = f"Repeated error ({count} occurrences)"
            for line_num in message_lines[msg_key]:
                results[line_num] = (confidence, detail)

    return results


def run_rule_engine(
    entries: list[LogEntry],
    config: Optional[AnomalyConfig] = None,
) -> dict[int, AnomalyResult]:
    """
    Run all rule-based anomaly detectors on a list of log entries.

    Combines keyword, frequency, and repetition detection.
    Returns the highest-confidence result per entry.

    Args:
        entries: All parsed log entries.
        config: Anomaly config override.

    Returns:
        Dict mapping line_number → AnomalyResult.
    """
    cfg = config or DEFAULT_CONFIG.anomaly
    results: dict[int, AnomalyResult] = {}

    # Run detectors
    freq_spikes = detect_frequency_spikes(entries, cfg)
    repeated = detect_repeated_errors(entries)

    for entry in entries:
        anomalies: list[tuple[float, str, str]] = []

        # Keyword check
        is_kw, kw_conf, kw_detail = detect_critical_keywords(entry, cfg.critical_keywords)
        if is_kw:
            anomalies.append((kw_conf, "critical_keyword", kw_detail))

        # Frequency check
        if entry.line_number in freq_spikes:
            f_conf, f_detail = freq_spikes[entry.line_number]
            anomalies.append((f_conf, "frequency_spike", f_detail))

        # Repetition check
        if entry.line_number in repeated:
            r_conf, r_detail = repeated[entry.line_number]
            anomalies.append((r_conf, "repeated_error", r_detail))

        # High log level as mild indicator
        if entry.log_level == LogLevel.CRITICAL:
            anomalies.append((0.6, "critical_level", "Log level is CRITICAL"))
        elif entry.log_level == LogLevel.ERROR:
            anomalies.append((0.3, "error_level", "Log level is ERROR"))

        if anomalies:
            # Take highest confidence anomaly
            best = max(anomalies, key=lambda x: x[0])
            all_details = "; ".join(a[2] for a in anomalies if a[2])
            results[entry.line_number] = AnomalyResult(
                is_anomaly=True,
                confidence=best[0],
                anomaly_type=best[1],
                rule_score=best[0],
                ml_score=0.0,
                details=all_details,
            )
        else:
            results[entry.line_number] = AnomalyResult(
                is_anomaly=False,
                confidence=0.0,
                anomaly_type="none",
                rule_score=0.0,
                ml_score=0.0,
                details="",
            )

    return results
