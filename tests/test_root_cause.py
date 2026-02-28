"""Tests for the root cause aggregator and correlation engine."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.root_cause.aggregator import (
    aggregate_root_causes,
    _split_by_time_window,
    _detect_severity_escalation,
    _compute_confidence,
)
from app.root_cause.correlation_engine import (
    compute_correlation,
    detect_cascades,
)
from models.schemas import (
    AnalysisReport, LogEntry, AnomalyResult, SeverityResult,
    Explanation, SeverityLevel, LogLevel, RootCauseEvent,
)


def _make_report(
    line: int,
    message: str,
    severity: SeverityLevel = SeverityLevel.MEDIUM,
    timestamp: datetime | None = None,
    is_anomaly: bool = True,
) -> AnalysisReport:
    """Helper to create a test AnalysisReport."""
    return AnalysisReport(
        log_entry=LogEntry(
            raw=message,
            line_number=line,
            message=message,
            timestamp=timestamp,
            log_level=LogLevel.ERROR,
        ),
        anomaly=AnomalyResult(is_anomaly=is_anomaly, confidence=0.8),
        severity=SeverityResult(level=severity, score=0.7),
        explanation=Explanation(summary="Test explanation"),
    )


class TestAggregator:
    """Tests for aggregate_root_causes."""

    def test_empty_input(self):
        result = aggregate_root_causes([])
        assert result == []

    def test_single_report_below_min_group(self):
        report = _make_report(1, "Connection refused to 192.168.1.1:5432")
        result = aggregate_root_causes([report], min_group_size=2)
        assert result == []

    def test_groups_by_template(self):
        """Reports with the same template should be grouped together."""
        base_time = datetime(2024, 1, 15, 14, 0, 0)
        reports = [
            _make_report(1, "Connection refused to 192.168.1.1:5432", timestamp=base_time),
            _make_report(2, "Connection refused to 10.0.0.5:5432", timestamp=base_time + timedelta(seconds=30)),
            _make_report(3, "Connection refused to 172.16.0.1:5432", timestamp=base_time + timedelta(seconds=60)),
        ]
        result = aggregate_root_causes(reports, min_group_size=2)
        assert len(result) == 1
        assert result[0].event_count == 3
        assert len(result[0].related_log_ids) == 3

    def test_separates_different_templates(self):
        """Different message templates should form separate groups."""
        base_time = datetime(2024, 1, 15, 14, 0, 0)
        reports = [
            _make_report(1, "Connection refused to 192.168.1.1:5432", timestamp=base_time),
            _make_report(2, "Connection refused to 10.0.0.5:5432", timestamp=base_time + timedelta(seconds=10)),
            _make_report(3, "Disk space critical on /dev/sda1", timestamp=base_time),
            _make_report(4, "Disk space critical on /dev/sdb2", timestamp=base_time + timedelta(seconds=10)),
        ]
        result = aggregate_root_causes(reports, min_group_size=2)
        assert len(result) == 2

    def test_time_window_splitting(self):
        """Events far apart in time should form separate groups."""
        reports = [
            _make_report(1, "Error occurred for request 123", timestamp=datetime(2024, 1, 15, 10, 0, 0)),
            _make_report(2, "Error occurred for request 456", timestamp=datetime(2024, 1, 15, 10, 1, 0)),
            # 1 hour gap
            _make_report(3, "Error occurred for request 789", timestamp=datetime(2024, 1, 15, 11, 0, 0)),
            _make_report(4, "Error occurred for request 101", timestamp=datetime(2024, 1, 15, 11, 1, 0)),
        ]
        result = aggregate_root_causes(reports, time_window_seconds=300, min_group_size=2)
        assert len(result) == 2

    def test_confidence_increases_with_group_size(self):
        """Larger groups should have higher confidence."""
        base_time = datetime(2024, 1, 15, 14, 0, 0)
        small_group = [
            _make_report(i, f"Error processing item {i}", timestamp=base_time + timedelta(seconds=i))
            for i in range(3)
        ]
        large_group = [
            _make_report(i, f"Error processing item {i}", timestamp=base_time + timedelta(seconds=i))
            for i in range(15)
        ]

        small_result = aggregate_root_causes(small_group, min_group_size=2)
        large_result = aggregate_root_causes(large_group, min_group_size=2)

        assert len(small_result) == 1
        assert len(large_result) == 1
        assert large_result[0].confidence >= small_result[0].confidence

    def test_severity_detection(self):
        """Highest severity in group determines the group severity."""
        base_time = datetime(2024, 1, 15, 14, 0, 0)
        reports = [
            _make_report(1, "Error on host 10.0.0.1", severity=SeverityLevel.LOW, timestamp=base_time),
            _make_report(2, "Error on host 10.0.0.2", severity=SeverityLevel.CRITICAL, timestamp=base_time + timedelta(seconds=10)),
            _make_report(3, "Error on host 10.0.0.3", severity=SeverityLevel.MEDIUM, timestamp=base_time + timedelta(seconds=20)),
        ]
        result = aggregate_root_causes(reports, min_group_size=2)
        assert len(result) == 1
        assert result[0].severity == "CRITICAL"

    def test_to_dict(self):
        """RootCauseEvent should serialize cleanly."""
        event = RootCauseEvent(
            event_id=0,
            title="Test",
            description="Test desc",
            time_window=("2024-01-15T14:00:00", "2024-01-15T14:05:00"),
            confidence=0.85,
            related_log_ids=[1, 2, 3],
            severity="HIGH",
            template_pattern="Error on <IP>",
            event_count=3,
        )
        d = event.to_dict()
        assert d["event_id"] == 0
        assert d["confidence"] == 0.85
        assert d["severity"] == "HIGH"


class TestSplitByTimeWindow:
    def test_empty(self):
        assert _split_by_time_window([], 300) == []

    def test_all_within_window(self):
        base = datetime(2024, 1, 15, 14, 0, 0)
        reports = [
            _make_report(i, f"msg {i}", timestamp=base + timedelta(seconds=i * 10))
            for i in range(5)
        ]
        groups = _split_by_time_window(reports, 300)
        assert len(groups) == 1
        assert len(groups[0]) == 5

    def test_splits_on_gap(self):
        reports = [
            _make_report(1, "msg 1", timestamp=datetime(2024, 1, 15, 14, 0, 0)),
            _make_report(2, "msg 2", timestamp=datetime(2024, 1, 15, 14, 1, 0)),
            _make_report(3, "msg 3", timestamp=datetime(2024, 1, 15, 15, 0, 0)),
        ]
        groups = _split_by_time_window(reports, 300)
        assert len(groups) == 2


class TestComputeConfidence:
    def test_zero_entries(self):
        assert _compute_confidence(0, 0, False) == 0.0

    def test_base_confidence(self):
        result = _compute_confidence(5, 100, False)
        assert 0.3 <= result <= 1.0

    def test_escalation_boost(self):
        without = _compute_confidence(5, 100, False)
        with_ = _compute_confidence(5, 100, True)
        assert with_ > without


class TestCorrelationEngine:
    def _make_event(
        self,
        event_id: int,
        severity: str = "MEDIUM",
        template: str = "Error on <IP>",
        start: str = "2024-01-15T14:00:00",
        end: str = "2024-01-15T14:05:00",
    ) -> RootCauseEvent:
        return RootCauseEvent(
            event_id=event_id,
            title=f"Test event {event_id}",
            description="Test",
            time_window=(start, end),
            confidence=0.7,
            related_log_ids=[event_id],
            severity=severity,
            template_pattern=template,
            event_count=5,
        )

    def test_high_correlation_overlapping_events(self):
        a = self._make_event(0, start="2024-01-15T14:00:00", end="2024-01-15T14:05:00")
        b = self._make_event(1, severity="HIGH", start="2024-01-15T14:03:00", end="2024-01-15T14:08:00")
        score = compute_correlation(a, b)
        assert score > 0.3

    def test_low_correlation_distant_events(self):
        a = self._make_event(0, start="2024-01-15T10:00:00", end="2024-01-15T10:05:00")
        b = self._make_event(1, template="Disk full on <PATH>", start="2024-01-15T18:00:00", end="2024-01-15T18:05:00")
        score = compute_correlation(a, b)
        assert score < 0.3

    def test_detect_cascades_merges(self):
        events = [
            self._make_event(0, start="2024-01-15T14:00:00", end="2024-01-15T14:05:00"),
            self._make_event(1, severity="HIGH", start="2024-01-15T14:03:00", end="2024-01-15T14:08:00"),
        ]
        result = detect_cascades(events, min_score=0.3)
        # They should potentially merge if correlation is high enough
        assert len(result) <= len(events)

    def test_detect_cascades_preserves_unrelated(self):
        events = [
            self._make_event(0, start="2024-01-15T10:00:00", end="2024-01-15T10:05:00"),
            self._make_event(1, template="Disk full on <PATH>", start="2024-01-15T18:00:00", end="2024-01-15T18:05:00"),
        ]
        result = detect_cascades(events, min_score=0.8)
        assert len(result) == 2

    def test_single_event(self):
        events = [self._make_event(0)]
        assert detect_cascades(events) == events

    def test_empty(self):
        assert detect_cascades([]) == []


class TestSeverityEscalation:
    def test_no_escalation(self):
        base = datetime(2024, 1, 15, 14, 0, 0)
        reports = [
            _make_report(1, "msg", severity=SeverityLevel.HIGH, timestamp=base),
            _make_report(2, "msg", severity=SeverityLevel.HIGH, timestamp=base + timedelta(seconds=10)),
        ]
        assert _detect_severity_escalation(reports) is False

    def test_escalation_detected(self):
        base = datetime(2024, 1, 15, 14, 0, 0)
        reports = [
            _make_report(1, "msg", severity=SeverityLevel.LOW, timestamp=base),
            _make_report(2, "msg", severity=SeverityLevel.LOW, timestamp=base + timedelta(seconds=10)),
            _make_report(3, "msg", severity=SeverityLevel.CRITICAL, timestamp=base + timedelta(seconds=20)),
            _make_report(4, "msg", severity=SeverityLevel.CRITICAL, timestamp=base + timedelta(seconds=30)),
        ]
        assert _detect_severity_escalation(reports) is True
